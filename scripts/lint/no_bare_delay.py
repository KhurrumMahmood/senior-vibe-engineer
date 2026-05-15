#!/usr/bin/env python3
"""safe-dispatch lint rule.

Flags direct Celery task dispatches — ``<task>.delay(...)`` and
``<task>.apply_async(...)`` — in application code. Callers must route
through :meth:`app.services._common.task_dispatch.TaskDispatchService.safe_dispatch`
so broker failures (Redis down, network partition) surface as controlled
503 responses with on_failure domain cleanup, instead of 500 stacktraces
with half-built rows.

This rule is deliberately **name-based** — it matches any attribute
access whose final component is ``.delay`` or ``.apply_async``. That
catches ``my_task.delay(...)``, ``module.my_task.delay(...)``, and the
``task.apply_async(...)`` shapes. Non-Celery ``.delay()`` usage is rare
enough in this codebase that we prefer one allow-list pragma per
legitimate case over a more complex AST heuristic.

Allow-list: ``# noqa: safe-dispatch: <reason>`` on the call line. Reason
must be non-empty (same discipline as silent-catch).

Target scope: ``core/tasks/*.py`` and ``core/views/*.py``. Other paths
are skipped — tests may instantiate fake tasks whose ``.delay`` is not a
Celery method. Run with explicit paths to override.

Usage:

    scripts/lint/no_bare_delay.py <file-or-dir> [...]
    scripts/lint/no_bare_delay.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error (unreadable file, bad CLI)

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

DISPATCH_METHODS = {"delay", "apply_async"}

# Match `# noqa: safe-dispatch: <at-least-one-non-space-char>`
NOQA_RE = re.compile(r"#\s*noqa:\s*safe-dispatch:\s*\S")


def _is_bare_dispatch(call: ast.Call) -> tuple[bool, str]:
    """Return (True, attr-name) when the call is <something>.<dispatch>(...)."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in DISPATCH_METHODS:
        # Skip chained cases like safe_dispatch(...).delay — unlikely but
        # harmless to guard against.
        return True, func.attr
    return False, ""


def _line_has_noqa(lines: list[str], lineno: int, end_lineno: int) -> bool:
    for idx in range(lineno - 1, min(end_lineno, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: safe-dispatch: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        matched, attr = _is_bare_dispatch(node)
        if not matched:
            continue
        end = getattr(node, "end_lineno", None) or node.lineno
        if _line_has_noqa(lines, node.lineno, end):
            continue
        msg = (
            f"bare `.{attr}()` dispatch — route through "
            f"`TaskDispatchService.safe_dispatch(task, args=..., "
            f"kwargs=..., on_failure=...)` or mark with "
            f"`# noqa: safe-dispatch: <reason>`"
        )
        hits.append((node.lineno, node.col_offset, msg))
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path}: safe-dispatch: cannot read — {exc}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: safe-dispatch: {msg}")
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: no_bare_delay.py <file-or-dir> [...]  |  "
            "no_bare_delay.py --stdin --filename=<name>",
            file=sys.stderr,
        )
        return 2

    if argv[0] == "--stdin":
        filename = "<stdin>"
        for a in argv[1:]:
            if a.startswith("--filename="):
                filename = a.split("=", 1)[1]
                break
        src = sys.stdin.read()
        hits = check_source(src, filename)
        for line, col, msg in hits:
            print(f"{filename}:{line}:{col + 1}: safe-dispatch: {msg}")
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
