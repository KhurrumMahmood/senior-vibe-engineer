#!/usr/bin/env python3
"""codegen-emits-new-paths lint rule (ADR 0007 deploy gate).

Scope: files under ``app/services/extraction/extraction_compiler/`` (and
the legacy alias ``core/services/extraction/extraction_compiler/`` if it
ever returns).

Flags any Python string literal that names a forbidden post-redesign
import path::

    "from core.services."
    "import core.services"

Why: the extraction compiler emits Python source code that gets stored
in ``SiteConfig.extraction_recipe`` and exec'd at runtime. Once
the project-structure redesign retires the ``core.services`` shim, any
extraction_recipe that still imports from ``core.services.X`` will raise
``ModuleNotFoundError`` on the next crawl. The codegen sites under
``extraction_compiler/`` are the *only* place these strings should ever
be written, and they must always emit ``app.services.<domain>.X``.

Allow-list: ``# noqa: codegen-emits-new-paths: <reason>`` on the line of
the offending string literal. The reason must be non-empty (``\\S``) so
the pragma cannot be spammed.

Usage::

    scripts/lint/codegen_emits_new_paths.py <file-or-dir> [...]
    scripts/lint/codegen_emits_new_paths.py --stdin --filename=<name>

Exit status::

    0  clean
    1  one or more violations found
    2  invocation error

Stdlib-only; safe under bare ``python3`` without a populated ``.venv``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

FORBIDDEN_SUBSTRINGS = (
    "from core.services",
    "import core.services",
)

NOQA_RE = re.compile(r"#\s*noqa:\s*codegen-emits-new-paths:\s*\S")

# Files where this rule applies. The lint is intentionally narrow —
# `core.services.X` is a legitimate string in plenty of other places
# (test fixtures, documentation, audit scripts). It is forbidden ONLY in
# the codegen emit sites that produce the runtime-exec'd extraction_recipe.
SCOPED_PATH_RE = re.compile(
    r"(?:^|/)(?:app|core)/services/extraction/extraction_compiler/"
)


def _line_has_noqa(lines: list[str], lineno: int) -> bool:
    if lineno - 1 < 0 or lineno - 1 >= len(lines):
        return False
    return bool(NOQA_RE.search(lines[lineno - 1]))


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: codegen-emits-new-paths: "
            f"syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        s = node.value
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden not in s:
                continue
            if _line_has_noqa(lines, node.lineno):
                continue
            msg = (
                f"emitted source contains {forbidden!r} — "
                f"extraction_recipe stored in DB will fail at runtime once "
                f"the core.services shim is removed; emit "
                f"app.services.<domain>.X instead, or mark with "
                f"`# noqa: codegen-emits-new-paths: <reason>`"
            )
            hits.append((node.lineno, node.col_offset, msg))
            break
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    if not SCOPED_PATH_RE.search(path):
        return 0, False
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{path}: codegen-emits-new-paths: cannot read — {exc}",
            file=sys.stderr,
        )
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(
            f"{path}:{line}:{col + 1}: codegen-emits-new-paths: {msg}"
        )
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: codegen_emits_new_paths.py <file-or-dir> [...]  |  "
            "codegen_emits_new_paths.py --stdin --filename=<name>",
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
        if not SCOPED_PATH_RE.search(filename):
            return 0
        src = sys.stdin.read()
        hits = check_source(src, filename)
        for line, col, msg in hits:
            print(
                f"{filename}:{line}:{col + 1}: codegen-emits-new-paths: {msg}"
            )
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
