#!/usr/bin/env python3
"""Silent-catch lint rule.

Flags a very specific smell: an ``except`` handler that catches a broad
exception type (bare ``except:``, ``except Exception:``, or
``except BaseException:``) whose body is *exactly* one of

    pass
    continue
    return              # bare return — value is None
    return None

Such handlers swallow failures without logging or re-raising, which makes
silent data loss indistinguishable from success. Ruff's ``BLE001`` flags
broad exceptions generally — this rule is narrower and tuned for the
Flavor-3 "silent catch" pattern surfaced by the ``/find-dormant`` skill
(see reports/dormant/scan-20260419-062049-services/ for the triage that
motivated the rule).

Allow-list: add ``# noqa: silent-catch: <reason>`` on any line of the
handler (the ``except`` line itself or the body line). The reason must
be non-empty so the allow-list cannot be spammed with a bare pragma.

Usage:

    scripts/lint/silent_catch.py <file-or-dir> [<file-or-dir> ...]
    scripts/lint/silent_catch.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error (unreadable file, bad CLI)

Stdlib-only; safe to invoke under bare ``python3`` from a worktree that
does not yet have a populated ``.venv``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

BROAD_EXC_NAMES = {"Exception", "BaseException"}

# Reason must contain at least one non-whitespace character after the colon
# — `# noqa: silent-catch:` alone would be trivially abusable.
NOQA_RE = re.compile(r"#\s*noqa:\s*silent-catch:\s*\S")


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    if isinstance(t, ast.Name) and t.id in BROAD_EXC_NAMES:
        return True
    return False


def _body_is_silent(body: list[ast.stmt]) -> bool:
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, (ast.Pass, ast.Continue)):
        return True
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return True
        if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
            return True
    return False


def _body_shape(body: list[ast.stmt]) -> str:
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return "pass"
    if isinstance(stmt, ast.Continue):
        return "continue"
    return "return None"


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    # Inclusive 1-indexed line range. Walk the handler's source span and
    # accept the allow-list if any line carries the pragma.
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: silent-catch: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if not _is_broad_except(node):
            continue
        if not _body_is_silent(node.body):
            continue
        end_line = max(
            (getattr(s, "end_lineno", None) or s.lineno) for s in node.body
        )
        if _range_has_noqa(lines, node.lineno, end_line):
            continue
        shape = _body_shape(node.body)
        msg = (
            f"except swallows via `{shape}` — log the failure "
            f"(logger.warning(..., exc_info=True)) or mark with "
            f"`# noqa: silent-catch: <reason>`"
        )
        hits.append((node.lineno, node.col_offset, msg))
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path}: silent-catch: cannot read — {exc}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: silent-catch: {msg}")
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: silent_catch.py <file-or-dir> [...]  |  "
            "silent_catch.py --stdin --filename=<name>",
            file=sys.stderr,
        )
        return 2

    if argv[0] == "--stdin":
        filename = "<stdin>"
        rest = argv[1:]
        for a in rest:
            if a.startswith("--filename="):
                filename = a.split("=", 1)[1]
                break
        src = sys.stdin.read()
        hits = check_source(src, filename)
        for line, col, msg in hits:
            print(f"{filename}:{line}:{col + 1}: silent-catch: {msg}")
        return 1 if hits else 0

    total_hits = 0
    had_io_error = False
    for path in expand_python_paths(argv):
        count, io_err = _check_path(path)
        total_hits += count
        had_io_error = had_io_error or io_err
    if had_io_error:
        return 2
    return 1 if total_hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
