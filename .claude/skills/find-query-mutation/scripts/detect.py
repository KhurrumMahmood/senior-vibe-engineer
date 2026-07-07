#!/usr/bin/env python3
"""Detect read-named functions that mutate persisted state.

AST-walks the target directory. For each ``FunctionDef`` /
``AsyncFunctionDef`` whose name matches
``^(get|fetch|load|list|find|check)(_.*)?$``, reports any mutation
call in the body. Matches the shape the ``no_query_mutation.py`` lint
rule catches, but widens the scan to the whole target directory so
untouched files are surfaced.

Mutation shapes flagged:

- ``<obj>.save(...)`` / ``<obj>.delete(...)``
- ``<qs>.update(...)`` / ``<qs>.update_or_create(...)`` /
  ``<qs>.create(...)`` / ``<qs>.bulk_create(...)`` /
  ``<qs>.bulk_update(...)``
- ``<qs>.get_or_create(...)`` (read-write combo — still surprising in
  a method named ``get_foo``)

Exemptions (excluded from output):

- Functions named exactly ``get_or_create`` or ``update_or_create`` —
  user-defined wrappers around the Django method of the same name.
- Any line in the function body (including the ``def`` line) with
  ``# hidden-mutation: <reason>`` where reason is non-empty.
- Test / migration / ``__init__`` files (see ``_DEFAULT_SKIP_*``).

Output (one JSON record per line at ``--output``):

    {"file": "core/services/foo.py", "symbol": "get_active_job",
     "method": "save", "lineno": 45, "func_lineno": 40,
     "evidence": "obj.save()"}

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

# Route Python parsing through the shared per-language adapter registry so
# this detector capability-gates on Python and gracefully skips other
# languages instead of crashing on them. The analysis below stays exact
# Python-AST / Django-specific (labels python/django are unchanged).
PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402

READ_PREFIXES = ("get_", "fetch_", "load_", "list_", "find_", "check_")
# Mirror the lint rule — keep the set identical so findings can be
# cross-referenced.
MUTATION_METHODS = frozenset({
    "save",
    "delete",
    "update",
    "update_or_create",
    "create",
    "bulk_create",
    "bulk_update",
    "get_or_create",
})
# Stdlib-mirroring names — these are explicit by convention.
EXEMPT_NAMES = frozenset({"get_or_create", "update_or_create"})

HIDDEN_RE = re.compile(r"#\s*hidden-mutation:\s*\S")

_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})
_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
    "__init__.py",
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


def _func_name_is_readish(name: str) -> bool:
    if name in EXEMPT_NAMES:
        return False
    return any(name.startswith(p) for p in READ_PREFIXES)


def _is_mutation_call(node: ast.Call) -> str | None:
    """Return the mutation method name if the call looks like
    ``<receiver>.<mutator>(...)``, else None."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in MUTATION_METHODS:
        return func.attr
    return None


def _range_has_hidden_mutation(
    lines: list[str], start: int, end: int,
) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if HIDDEN_RE.search(lines[idx]):
            return True
    return False


def _segment_source(src_lines: list[str], lineno: int, limit: int = 240) -> str:
    if lineno < 1 or lineno > len(src_lines):
        return ""
    raw = src_lines[lineno - 1].strip()
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _innermost_function(
    tree: ast.AST,
    target: ast.AST,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Find the innermost function/method that contains ``target``. Used
    to dedupe: a mutation at line N is attributed only to its innermost
    enclosing function, not to every containing read-named wrapper."""
    owner: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        tlineno = getattr(target, "lineno", -1)
        if start <= tlineno <= end:
            if owner is None or node.lineno > owner.lineno:
                owner = node
    return owner


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

    readish_funcs = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _func_name_is_readish(n.name)
    ]

    for func in readish_funcs:
        func_end = getattr(func, "end_lineno", func.lineno)
        # The hidden-mutation marker covers the whole function body.
        if _range_has_hidden_mutation(src_lines, func.lineno, func_end):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            meth = _is_mutation_call(node)
            if meth is None:
                continue
            owner = _innermost_function(tree, node)
            if owner is not func:
                continue
            out.append({
                "file": rel,
                "symbol": func.name,
                "method": meth,
                "lineno": node.lineno,
                "func_lineno": func.lineno,
                "evidence": _segment_source(src_lines, node.lineno),
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
            f"[detect_query_mutation] ERROR: {args.target} not found",
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

    by_method: dict[str, int] = {}
    for r in records:
        by_method[r["method"]] = by_method.get(r["method"], 0) + 1
    print(
        f"[detect_query_mutation] wrote {args.output} "
        f"({len(records)} hits across {len(files)} files) "
        f"by_method={by_method}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
