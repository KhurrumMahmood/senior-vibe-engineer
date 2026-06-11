#!/usr/bin/env python3
"""Detect ``transaction.atomic`` blocks that hold a DB connection while
doing slow / external work.

The smell: a Django transaction holds a connection from the pool for as
long as its body runs. If the body issues an HTTP request, an AI call, a
``time.sleep``, a subprocess, or dispatches a Celery task in a way that
expects the row to be visible immediately, the connection is pinned for
seconds-to-minutes while waiting on something the database doesn't care
about. Under load, every other request waiting for a connection blocks.

This detector AST-walks a target directory and reports every slow-op
call that lives inside the body of:

- a ``with transaction.atomic(): ...`` block, or
- a function decorated with ``@transaction.atomic`` /
  ``@transaction.atomic(...)``.

Slow-op shapes flagged:

- **HTTP libraries (high)**: ``requests.<verb>(...)``,
  ``httpx.<verb>(...)``, ``urllib.request.urlopen(...)``,
  ``urlopen(...)``, ``Session().<verb>(...)``.
- **AI / SDK calls (high)**: any ``ai_runtime.*`` import path, plus
  ``client.messages.create(...)``, ``client.chat.completions.create(...)``,
  ``openai.*``, ``anthropic.*``.
- **Cloud uploads (high)**: ``boto3.*``, ``<s3>.put_object(...)``,
  ``<s3>.upload_*(...)``.
- **Subprocess (high)**: ``subprocess.<run|Popen|call|check_output>``,
  ``os.system(...)``.
- **Sleep (high)**: ``time.sleep(...)`` — guaranteed-to-block.
- **Celery dispatch (medium)**: ``<task>.delay(...)``,
  ``<task>.apply_async(...)``, ``TaskDispatchService.safe_dispatch(...)``.
  Even with ``safe_dispatch`` and ``transaction.on_commit``, dispatching
  inside a transaction is worth a sanity check — the scout disambiguates.
- **Network helpers (medium)**: ``proxy_*`` /
  ``scraperapi*`` / ``crawl_*`` named helper calls — ambiguous, scout
  resolves.

Exemptions (excluded from output):

- Any line in the atomic body (including the ``with`` or ``def`` line)
  with a ``# atomic-overreach: <reason>`` allow-list marker. Reason
  must be non-empty.
- Calls inside ``transaction.on_commit(lambda: ...)`` — those are
  deferred until after the transaction commits and are explicitly
  the canonical way to defer side effects.

Output (one JSON record per line at ``--output``):

    {"file": "core/views/foo.py", "block_kind": "with",
     "block_lineno": 222, "block_endline": 285,
     "enclosing_symbol": "scrape_test_view",
     "call_lineno": 245, "call_method": "requests.get",
     "category": "http", "confidence": "high",
     "evidence": "response = requests.get(url, ...)"}

Stdlib-only. Runs under ``python3``.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any


# -- Slow-op classifiers -----------------------------------------------------

# Shapes are matched against the dotted-call name that ``_call_dotted``
# extracts (e.g. ``requests.get`` from ``requests.get(...)``,
# ``client.messages.create`` from ``self.client.messages.create(...)``).
# Each shape is paired with a category + confidence.

# (regex-on-dotted-name, category, confidence)
SLOW_OP_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    # HTTP libraries — high confidence.
    (re.compile(r"^requests\.(get|post|put|patch|delete|head|options|request)$"),
     "http", "high"),
    (re.compile(r"^httpx\.(get|post|put|patch|delete|head|options|request|stream)$"),
     "http", "high"),
    (re.compile(r"^urllib\.request\.urlopen$"), "http", "high"),
    (re.compile(r"^urlopen$"), "http", "high"),
    (re.compile(r"\.Session$"), "http", "medium"),  # constructing a Session is cheap; using it isn't
    (re.compile(r"\.get_session$"), "http", "medium"),
    (re.compile(r"^aiohttp\."), "http", "high"),

    # AI / SDK calls — high confidence.
    (re.compile(r"^ai_runtime\."), "ai", "high"),
    (re.compile(r"\.messages\.create$"), "ai", "high"),  # Anthropic
    (re.compile(r"\.chat\.completions\.create$"), "ai", "high"),  # OpenAI
    (re.compile(r"\.completions\.create$"), "ai", "high"),
    (re.compile(r"\.embeddings\.create$"), "ai", "high"),
    (re.compile(r"^openai\."), "ai", "high"),
    (re.compile(r"^Anthropic\("), "ai", "high"),
    (re.compile(r"^OpenAI\("), "ai", "high"),

    # Cloud uploads — high confidence.
    (re.compile(r"^boto3\."), "cloud", "high"),
    (re.compile(r"\.put_object$"), "cloud", "high"),
    (re.compile(r"\.upload_file$"), "cloud", "high"),
    (re.compile(r"\.upload_fileobj$"), "cloud", "high"),

    # Subprocess — high confidence.
    (re.compile(r"^subprocess\.(run|Popen|call|check_output|check_call)$"),
     "subprocess", "high"),
    (re.compile(r"^os\.system$"), "subprocess", "high"),

    # Blocking sleep — high confidence (guaranteed wait).
    (re.compile(r"^time\.sleep$"), "sleep", "high"),

    # Celery dispatch — medium (safe_dispatch + on_commit may guard, scout resolves).
    (re.compile(r"\.delay$"), "celery", "medium"),
    (re.compile(r"\.apply_async$"), "celery", "medium"),
    (re.compile(r"^safe_dispatch$"), "celery", "medium"),
    (re.compile(r"\.safe_dispatch$"), "celery", "medium"),

    # Project-specific network helpers — low (ambiguous wrapper names; scout disambiguates).
    (re.compile(r"^scrape_url$"), "network_helper", "low"),
    (re.compile(r"^scrape_with_proxy$"), "network_helper", "low"),
    (re.compile(r"^fetch_url$"), "network_helper", "low"),
    (re.compile(r"^download_"), "network_helper", "low"),
    (re.compile(r"\.scrape$"), "network_helper", "low"),
    (re.compile(r"\.crawl$"), "network_helper", "low"),
    (re.compile(r"\.fetch$"), "network_helper", "low"),
)

ALLOWLIST_RE = re.compile(r"#\s*atomic-overreach:\s*\S")

_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})
_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
)


# -- Helpers -----------------------------------------------------------------


def _walk_python_files(
    target: Path, skip_globs: tuple[str, ...]
) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix == ".py" else []
    files: list[Path] = []
    for path in target.rglob("*.py"):
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in skip_globs):
            continue
        files.append(path)
    return files


def _call_dotted(call: ast.Call) -> str:
    """Render the call's func into a dotted name like ``requests.get`` or
    ``client.messages.create``. Returns an empty string when the func is
    something we can't name (a subscription, a parenthesized expression,
    etc.)."""
    parts: list[str] = []
    node: Any = call.func
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            break
        elif isinstance(node, ast.Call):
            # e.g. ``Anthropic(api_key=...).messages.create(...)`` — render
            # the inner call's callable shape so rules can match it.
            inner = _call_dotted(node)
            if inner:
                parts.append(inner)
            break
        else:
            return ""
    return ".".join(reversed(parts))


def _classify_call(name: str) -> tuple[str, str] | None:
    if not name:
        return None
    for pattern, category, confidence in SLOW_OP_RULES:
        if pattern.search(name):
            return category, confidence
    return None


def _is_atomic_with(node: ast.With | ast.AsyncWith) -> bool:
    """True iff any context item is ``transaction.atomic()`` or
    ``transaction.atomic`` (no-call form)."""
    for item in node.items:
        ctx = item.context_expr
        # transaction.atomic()
        if isinstance(ctx, ast.Call):
            ctx = ctx.func
        if isinstance(ctx, ast.Attribute) and ctx.attr == "atomic":
            base = ctx.value
            if isinstance(base, ast.Name) and base.id == "transaction":
                return True
            # Sometimes imported as ``from django.db.transaction import atomic``
            # then used as ``with atomic():`` — handled by the bare-name
            # check below.
        if isinstance(ctx, ast.Name) and ctx.id == "atomic":
            return True
    return False


def _is_atomic_decorator(deco: ast.expr) -> bool:
    """True iff the decorator is ``@transaction.atomic`` or
    ``@transaction.atomic(...)``."""
    if isinstance(deco, ast.Call):
        deco = deco.func
    if isinstance(deco, ast.Attribute) and deco.attr == "atomic":
        base = deco.value
        if isinstance(base, ast.Name) and base.id == "transaction":
            return True
    if isinstance(deco, ast.Name) and deco.id == "atomic":
        return True
    return False


def _enclosing_symbol(
    tree: ast.AST,
    target_lineno: int,
) -> str:
    """Find the innermost function/class containing ``target_lineno`` and
    return its name. Used so a finding inside a method gets attributed
    to ``ClassName.method_name``, while a finding at module scope gets
    the module name."""
    owner: ast.AST | None = None
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        if start <= target_lineno <= end:
            if owner is None:
                owner = node
            elif node.lineno > owner.lineno:
                owner = node
    if owner is None:
        return "<module>"
    return getattr(owner, "name", "<module>")


def _range_has_allowlist(
    lines: list[str], start: int, end: int,
) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if ALLOWLIST_RE.search(lines[idx]):
            return True
    return False


def _segment_source(
    src_lines: list[str], lineno: int, limit: int = 240,
) -> str:
    if lineno < 1 or lineno > len(src_lines):
        return ""
    raw = src_lines[lineno - 1].strip()
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _inside_on_commit(
    call: ast.Call, atomic_root: ast.AST,
) -> bool:
    """True iff the call is wrapped in a
    ``transaction.on_commit(lambda: <call>)`` — those are explicitly
    deferred and not the smell we're hunting."""
    # Walk descendants of atomic_root and find on_commit calls; check if
    # ``call`` is inside one of their lambdas/closures by line range.
    for node in ast.walk(atomic_root):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "on_commit":
            base = func.value
            if isinstance(base, ast.Name) and base.id == "transaction":
                start = getattr(node, "lineno", -1)
                end = getattr(node, "end_lineno", start)
                cl = getattr(call, "lineno", -1)
                if start <= cl <= end:
                    return True
        if isinstance(func, ast.Name) and func.id == "on_commit":
            start = getattr(node, "lineno", -1)
            end = getattr(node, "end_lineno", start)
            cl = getattr(call, "lineno", -1)
            if start <= cl <= end:
                return True
    return False


# -- Atomic-block discovery --------------------------------------------------


def _atomic_blocks(
    tree: ast.AST,
) -> list[tuple[ast.AST, str, int, int]]:
    """Return every atomic region in the tree. Each entry is
    ``(root_node, block_kind, lineno, end_lineno)`` where:

    - ``block_kind`` is ``"with"`` for a ``with transaction.atomic():``
      block, or ``"decorator"`` for a function with
      ``@transaction.atomic``.
    - ``root_node`` is the AST subtree to walk for slow-op calls — for
      a ``with`` block, the with-statement body's enclosing node; for a
      decorator, the function definition itself.
    """
    out: list[tuple[ast.AST, str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)) and _is_atomic_with(node):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            out.append((node, "with", start, end))
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if _is_atomic_decorator(deco):
                    start = node.lineno
                    end = getattr(node, "end_lineno", start)
                    out.append((node, "decorator", start, end))
                    break
    return out


def _scan_file(
    filepath: Path, rel: str,
) -> list[dict[str, Any]]:
    try:
        src = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=str(filepath))
    except SyntaxError:
        return []
    src_lines = src.splitlines()
    blocks = _atomic_blocks(tree)
    if not blocks:
        return []

    out: list[dict[str, Any]] = []
    for root, kind, b_start, b_end in blocks:
        if _range_has_allowlist(src_lines, b_start, b_end):
            continue
        for sub in ast.walk(root):
            if not isinstance(sub, ast.Call):
                continue
            # Skip the ``transaction.atomic()`` call itself if we land on it.
            dotted = _call_dotted(sub)
            if dotted in {"transaction.atomic", "atomic"}:
                continue
            verdict = _classify_call(dotted)
            if verdict is None:
                continue
            category, confidence = verdict
            cl = getattr(sub, "lineno", b_start)
            # Per-call allow-list: ``# atomic-overreach: reason`` on the
            # specific call line.
            if _range_has_allowlist(
                src_lines, cl, getattr(sub, "end_lineno", cl),
            ):
                continue
            if _inside_on_commit(sub, root):
                continue
            symbol = _enclosing_symbol(tree, cl)
            out.append({
                "file": rel,
                "block_kind": kind,
                "block_lineno": b_start,
                "block_endline": b_end,
                "enclosing_symbol": symbol,
                "call_lineno": cl,
                "call_method": dotted,
                "category": category,
                "confidence": confidence,
                "evidence": _segment_source(src_lines, cl),
            })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path,
                        help="Directory to scan")
    parser.add_argument("--project-root", required=True, type=Path,
                        help="Project root (used for relative paths)")
    parser.add_argument("--output", required=True, type=Path,
                        help="Output JSONL file")
    parser.add_argument("--skip-file-glob", action="append", default=[],
                        help="Extra file globs to skip (repeatable)")
    args = parser.parse_args(argv)

    if not args.target.exists():
        print(
            f"[detect_transaction_overreach] ERROR: {args.target} not found",
            file=sys.stderr,
        )
        return 2

    skip_globs = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)
    project_root = args.project_root.resolve()
    files = _walk_python_files(args.target, skip_globs)
    records: list[dict[str, Any]] = []
    for filepath in files:
        try:
            rel = str(filepath.relative_to(project_root))
        except ValueError:
            rel = str(filepath)
        records.extend(_scan_file(filepath, rel))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    by_category: dict[str, int] = {}
    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
    print(
        f"[detect_transaction_overreach] wrote {args.output} "
        f"({len(records)} hits across {len(files)} files) "
        f"by_category={by_category}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
