#!/usr/bin/env python3
"""Detect stringly-typed state and tuple-inferred identity smells.

AST-walks the target directory looking for smell 2 from
`.claude/docs/architectural-smells.md` in two sub-shapes:

**Sub-pattern A — stringly-typed state.**

- ``<expr>.status == "literal"`` (also ``!=`` / reversed operand order).
- ``<expr>.status in ("a", "b")`` / ``not in [...]`` / set literals.
- Django model field ``status``/``phase``/``state`` declared as
  ``models.CharField(...)``/``models.TextField(...)`` with no
  ``choices=<TextChoices>`` kwarg.
- Dict literal ``{"status": "pending"}`` appearing in the same file as a
  bare-string ``.status`` comparison — flagged as the softer signal
  ``possible_state_literal``.

**Sub-pattern B — tuple-inferred identity.**

- ``<Model>.objects.filter(status=...).first()`` or ``... [0]`` where the
  filter kwargs include BOTH a state-ish kwarg (``status`` / ``state`` /
  ``phase``) AND a time-based kwarg (``*_at__*`` lookup, e.g.
  ``created_at__gt``, ``finished_at__isnull``). Assignment-target name
  heuristic (``job`` / ``task`` / ``run`` / ``export`` / ``active`` in the
  LHS identifier) strengthens the confidence.

Output (one JSON record per line at ``--output``):

    {"file": "core/views/crawling.py", "symbol": "is_pending",
     "pattern": "stringly_compare", "field": "status",
     "literal": "pending", "lineno": 42,
     "evidence": "job.status == 'pending'"}

    {"file": "core/views/collections.py", "symbol": "start_collection_crawl",
     "pattern": "tuple_identity", "model_hint": "UrlCrawlJob",
     "filter_kwargs": ["status", "current_url_status"],
     "assigned_to": "active_job", "lineno": 349,
     "evidence": "UrlCrawlJob.objects.filter(status=...).first()"}

No verification here — scouts apply the bucketing rules from
``knowledge/verification.md`` (enum-already-used, legacy allow-list, etc.).

Stdlib-only. Runs under ``python3``.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

# Route Python parsing through the shared per-language adapter registry so
# this detector capability-gates on Python and gracefully skips other
# languages instead of crashing on them. The analysis below stays exact
# Python-AST / Django-specific (labels python/django are unchanged).
PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402

STATE_FIELD_NAMES = frozenset({"status", "phase", "state"})
STATE_FIELD_CALLS = frozenset({"CharField", "TextField"})
# Assignment targets that hint at "find the active thing" usage.
ACTIVE_HINT_SUBSTRINGS = ("job", "task", "run", "export", "active")
# Container of ``__`` lookups on *_at timestamp fields treated as
# time-based. Kept deliberately broad — the SUSPECT scan errs toward
# surfacing; scouts disambiguate.
TIME_LOOKUP_SUFFIXES = (
    "__gt", "__gte", "__lt", "__lte", "__range", "__isnull",
    "__date", "__year", "__month", "__day",
)
TIME_FIELD_SUFFIX = "_at"

_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})
_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
)


def _walk_python_files(
    target: Path, skip_globs: tuple[str, ...]
) -> list[Path]:
    files: list[Path] = []
    for path in target.rglob("*.py"):
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in skip_globs):
            continue
        files.append(path)
    return files


def _state_attr_name(node: ast.AST) -> str | None:
    """Return the attr name if ``node`` is ``<anything>.status`` etc."""
    if isinstance(node, ast.Attribute) and node.attr in STATE_FIELD_NAMES:
        return node.attr
    return None


def _string_literal_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_string_literal_container(node: ast.AST) -> list[str] | None:
    """Return the contained literals if ``node`` is a non-empty
    tuple/list/set of string literals; else None."""
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return None
    if not node.elts:
        return None
    vals: list[str] = []
    for elt in node.elts:
        v = _string_literal_value(elt)
        if v is None:
            return None
        vals.append(v)
    return vals


def _is_models_field_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in STATE_FIELD_CALLS:
        return True
    if isinstance(func, ast.Name) and func.id in STATE_FIELD_CALLS:
        return True
    return False


def _has_textchoices_choices(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg != "choices":
            continue
        choices = kw.value
        if isinstance(choices, ast.Attribute):
            base = choices.value
            if isinstance(base, ast.Name) and _looks_like_choices_name(base.id):
                return True
            if isinstance(base, ast.Attribute) and _looks_like_choices_name(base.attr):
                return True
        if isinstance(choices, ast.Name) and _looks_like_choices_name(choices.id):
            return True
    return False


def _looks_like_choices_name(name: str) -> bool:
    return any(
        name.endswith(suffix)
        for suffix in ("Choices", "Status", "State", "Phase")
    )


def _inside_model_class(path: list[ast.AST]) -> bool:
    for node in path:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Model":
                return True
            if isinstance(base, ast.Name) and base.id == "Model":
                return True
    return False


def _enclosing_symbol(path: list[ast.AST]) -> str:
    """Return the nearest FunctionDef/AsyncFunctionDef/ClassDef name, or
    ``<module>`` if the node is at module level."""
    for node in reversed(path):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node.name
    return "<module>"


def _segment_source(src_lines: list[str], node: ast.AST, limit: int = 240) -> str:
    """Return a one-line evidence string for the given node. Uses the
    node's first source line and truncates aggressively."""
    lineno = getattr(node, "lineno", None)
    if lineno is None or lineno < 1 or lineno > len(src_lines):
        return ""
    raw = src_lines[lineno - 1].strip()
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _looks_like_time_kwarg(keyword_arg: str | None) -> bool:
    """Return True when ``keyword_arg`` is something like ``created_at__gt``
    or ``finished_at__isnull``."""
    if not keyword_arg:
        return False
    # Split on __; first segment is the field name, rest are lookups.
    parts = keyword_arg.split("__")
    field_part = parts[0]
    if not field_part.endswith(TIME_FIELD_SUFFIX):
        return False
    if len(parts) == 1:
        # Bare `created_at=` assignment isn't a time-based *lookup*,
        # just a kwarg; still a tuple-identity signal if paired with state.
        return True
    # Otherwise a lookup tail like `__gt`, `__isnull`, `__date` counts.
    for suffix in TIME_LOOKUP_SUFFIXES:
        if keyword_arg.endswith(suffix):
            return True
    return False


def _is_state_kwarg(keyword_arg: str | None) -> bool:
    if not keyword_arg:
        return False
    base = keyword_arg.split("__")[0]
    return base in STATE_FIELD_NAMES


def _model_hint_from_filter_chain(call: ast.Call) -> str | None:
    """Walk ``.filter()`` chains to find the ``Model`` name before
    ``.objects``. Returns ``Model`` for ``Model.objects.filter(...)``
    and similar. Best-effort; returns None on unrecognized shapes."""
    func = call.func
    # `<something>.filter(...)` — walk down until we hit `.objects`.
    while isinstance(func, ast.Attribute):
        if func.attr == "objects":
            base = func.value
            if isinstance(base, ast.Name):
                return base.id
            if isinstance(base, ast.Attribute):
                return base.attr
            return None
        # Walk through chained QuerySet calls (.filter().exclude()...)
        inner = func.value
        if isinstance(inner, ast.Call):
            func = inner.func
            continue
        if isinstance(inner, ast.Attribute):
            func = inner
            continue
        break
    return None


def _collect_filter_call_kwargs(call: ast.Call) -> list[str]:
    """Return the kwarg names of a ``.filter(...)`` call."""
    return [kw.arg for kw in call.keywords if kw.arg]


def _find_terminal_filter_usage(
    node: ast.AST,
) -> tuple[ast.Call, str] | None:
    """If ``node`` is ``<qs>.first()`` or ``<qs>[0]`` whose base chain
    contains a ``.filter(...)`` call, return (filter_call, terminal_shape).
    terminal_shape is ``first`` or ``index0``."""
    # Case: .first()
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "first":
            filter_call = _walk_for_filter(func.value)
            if filter_call is not None:
                return filter_call, "first"
    # Case: <qs>[0]
    if isinstance(node, ast.Subscript):
        slc = node.slice
        idx = slc
        if isinstance(idx, ast.Constant) and idx.value == 0:
            filter_call = _walk_for_filter(node.value)
            if filter_call is not None:
                return filter_call, "index0"
    return None


def _walk_for_filter(node: ast.AST) -> ast.Call | None:
    """Walk down a chained QuerySet expression looking for the nearest
    ``.filter(...)`` call."""
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, ast.Call):
            func = cur.func
            if isinstance(func, ast.Attribute) and func.attr == "filter":
                return cur
            # Chained: <qs>.exclude().order_by() — step inward.
            if isinstance(func, ast.Attribute):
                cur = func.value
                continue
            return None
        if isinstance(cur, ast.Attribute):
            cur = cur.value
            continue
        return None
    return None


def _assigned_target_name(stmt_stack: list[ast.AST]) -> str | None:
    """Walk up the enclosing stack to find the nearest Assign/AnnAssign
    target; returns the target identifier if it's a simple Name."""
    for parent in reversed(stmt_stack):
        if isinstance(parent, ast.Assign):
            if len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
                return parent.targets[0].id
            return None
        if isinstance(parent, ast.AnnAssign):
            if isinstance(parent.target, ast.Name):
                return parent.target.id
            return None
    return None


def _has_active_hint(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return any(hint in lowered for hint in ACTIVE_HINT_SUBSTRINGS)


def _dict_literal_has_state_key(node: ast.AST) -> bool:
    """Return True for dict literals whose keys include ``status``/
    ``phase``/``state`` as string literals with string-literal values."""
    if not isinstance(node, ast.Dict):
        return False
    for key, value in zip(node.keys, node.values, strict=False):
        if key is None:
            continue
        key_s = _string_literal_value(key)
        if key_s is None or key_s not in STATE_FIELD_NAMES:
            continue
        if _string_literal_value(value) is not None:
            return True
    return False


def _scan_file(filepath: Path, rel: str) -> list[dict[str, Any]]:
    adapter = get_adapter(filepath)
    if adapter is None or CAP_PYTHON_AST not in adapter.capabilities:
        return []
    try:
        src = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    tree = adapter.parse(src)
    if tree is None:
        return []
    src_lines = src.splitlines()
    out: list[dict[str, Any]] = []

    def emit(record: dict[str, Any]) -> None:
        record["file"] = rel
        out.append(record)

    def visit(node: ast.AST, path: list[ast.AST]) -> None:
        # Sub-pattern A1: model field declaration without TextChoices.
        if isinstance(node, ast.Assign) and _inside_model_class(path):
            _emit_field_declaration(node, src_lines, path, emit)

        # Sub-pattern A2: bare-string comparisons on .status/.phase/.state.
        if isinstance(node, ast.Compare):
            _emit_stringly_compare(node, src_lines, path, emit)

        # Sub-pattern A3: dict literal with state key + string literal value.
        if _dict_literal_has_state_key(node):
            emit({
                "pattern": "possible_state_literal",
                "symbol": _enclosing_symbol(path),
                "lineno": node.lineno,
                "evidence": _segment_source(src_lines, node),
            })

        # Sub-pattern B: tuple-inferred identity via .filter(...).first() / [0]
        term = _find_terminal_filter_usage(node)
        if term is not None:
            filter_call, terminal_shape = term
            kwargs = _collect_filter_call_kwargs(filter_call)
            has_state = any(_is_state_kwarg(k) for k in kwargs)
            has_time = any(_looks_like_time_kwarg(k) for k in kwargs)
            if has_state and has_time:
                assigned = _assigned_target_name(path)
                emit({
                    "pattern": "tuple_identity",
                    "symbol": _enclosing_symbol(path),
                    "model_hint": _model_hint_from_filter_chain(filter_call),
                    "filter_kwargs": kwargs,
                    "terminal": terminal_shape,
                    "assigned_to": assigned,
                    "active_hint": _has_active_hint(assigned),
                    "lineno": node.lineno,
                    "evidence": _segment_source(src_lines, node),
                })

        for child in ast.iter_child_nodes(node):
            visit(child, path + [node])

    visit(tree, [])
    return out


def _emit_field_declaration(
    node: ast.Assign,
    src_lines: list[str],
    path: list[ast.AST],
    emit: Any,
) -> None:
    if len(node.targets) != 1:
        return
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return
    if target.id not in STATE_FIELD_NAMES:
        return
    value = node.value
    if not isinstance(value, ast.Call):
        return
    if not _is_models_field_call(value):
        return
    if _has_textchoices_choices(value):
        return
    emit({
        "pattern": "stringly_field",
        "symbol": _enclosing_symbol(path),
        "field": target.id,
        "lineno": node.lineno,
        "evidence": _segment_source(src_lines, node),
    })


def _emit_stringly_compare(
    node: ast.Compare,
    src_lines: list[str],
    path: list[ast.AST],
    emit: Any,
) -> None:
    if len(node.ops) != 1:
        return
    op = node.ops[0]
    left = node.left
    right = node.comparators[0]

    if isinstance(op, (ast.Eq, ast.NotEq)):
        attr = _state_attr_name(left)
        lit = _string_literal_value(right) if attr else None
        if attr is None:
            attr = _state_attr_name(right)
            lit = _string_literal_value(left) if attr else None
        if attr and lit is not None:
            emit({
                "pattern": "stringly_compare",
                "symbol": _enclosing_symbol(path),
                "field": attr,
                "literal": lit,
                "op": "==" if isinstance(op, ast.Eq) else "!=",
                "lineno": node.lineno,
                "evidence": _segment_source(src_lines, node),
            })
            return

    if isinstance(op, (ast.In, ast.NotIn)):
        attr = _state_attr_name(left)
        if not attr:
            return
        lits = _is_string_literal_container(right)
        if lits is None:
            return
        emit({
            "pattern": "stringly_compare",
            "symbol": _enclosing_symbol(path),
            "field": attr,
            "literals": lits,
            "op": "in" if isinstance(op, ast.In) else "not in",
            "lineno": node.lineno,
            "evidence": _segment_source(src_lines, node),
        })


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
            f"[detect_implicit_state] ERROR: {args.target} not found",
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

    # Stderr summary for orchestrator log tailing.
    by_pattern: dict[str, int] = {}
    for r in records:
        by_pattern[r["pattern"]] = by_pattern.get(r["pattern"], 0) + 1
    print(
        f"[detect_implicit_state] wrote {args.output} "
        f"({len(records)} hits across {len(files)} files) "
        f"by-pattern={by_pattern}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
