#!/usr/bin/env python3
"""Fat-view lint rule.

Flags view functions (or View-subclass methods) whose body exceeds a LOC
budget. Fat views tend to own business logic that belongs in a service —
see ``.claude/docs/architectural-smells.md`` smell 4 (layer violation).

This rule only measures size. Shape-level detection (domain loops, LLM
calls, multi-model transactions) is the ``/find-layer-violation``
SUSPECT skill's job. Size is the cheapest signal that catches most of
the same targets without false positives from legitimately-branching
views.

The LOC-budget machinery is framework-agnostic, but the default
view-*detection* heuristics are Django-shaped: ``VIEW_BASE_HINTS``
holds Django/DRF view base-class names, and ``HTTP_METHODS`` holds
Django's HTTP-method handler names. These two constants are the
per-framework override seam — a host on another stack (e.g. FastAPI,
Express) should replace their contents to match its view base classes
and handler names; the detection logic and budgets stay unchanged.

Rules:

- A **view function** is any module-level function whose name starts
  with ``_`` → **excluded**; or any function whose name does NOT start
  with ``_`` (public) → **included** if the file is a view file.
- A **View-subclass method** is any ``def`` inside a ``class Foo(View)``
  / ``class Foo(APIView)`` / ``...(ViewSet)`` / ``...(TemplateView)``
  etc. ``get`` / ``post`` / ``put`` / ``patch`` / ``delete`` / ``head``
  / ``options`` are the HTTP-method handlers.
- **LOC budget:** 80 for module functions, 120 for View-class HTTP
  methods (classes justify slightly more because the class owns routing
  boilerplate).
- Body LOC is computed from ``end_lineno - lineno + 1`` minus comment /
  blank lines — approximate but cheap and stable.

Budgets are tunable via ``--fn-budget`` and ``--method-budget``.

Allow-list: ``# noqa: fat-view: <reason>`` on any line of the function
body. Reason must be non-empty.

Usage:

    scripts/lint/no_fat_view.py <file-or-dir> [<file-or-dir> ...]
    scripts/lint/no_fat_view.py --fn-budget 100 <file-or-dir>
    scripts/lint/no_fat_view.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error

Stdlib-only.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

DEFAULT_FN_BUDGET = 80
DEFAULT_METHOD_BUDGET = 120

# Framework seam: Django/DRF view base classes. Override per host stack.
VIEW_BASE_HINTS = (
    "View",
    "APIView",
    "ViewSet",
    "ModelViewSet",
    "GenericViewSet",
    "TemplateView",
    "ListView",
    "DetailView",
    "CreateView",
    "UpdateView",
    "DeleteView",
    "FormView",
    "RedirectView",
)

# Framework seam: Django HTTP-method handler names. Override per host stack.
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

NOQA_RE = re.compile(r"#\s*noqa:\s*fat-view:\s*\S")


def _is_view_class(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        name = None
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        if name in VIEW_BASE_HINTS:
            return True
    return False


def _body_loc(node: ast.AST, lines: list[str]) -> int:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None) or start
    if start is None or end is None:
        return 0
    count = 0
    for idx in range(start - 1, min(end, len(lines))):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(
    src: str,
    filename: str,
    fn_budget: int = DEFAULT_FN_BUDGET,
    method_budget: int = DEFAULT_METHOD_BUDGET,
) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: fat-view: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []

    # Module-level view functions
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        loc = _body_loc(node, lines)
        if loc <= fn_budget:
            continue
        end_line = getattr(node, "end_lineno", node.lineno)
        if _range_has_noqa(lines, node.lineno, end_line):
            continue
        msg = (
            f"view function `{node.name}` is {loc} LOC (budget "
            f"{fn_budget}) — extract a service or mark with "
            f"`# noqa: fat-view: <reason>`"
        )
        hits.append((node.lineno, node.col_offset, msg))

    # View-class HTTP methods
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_view_class(node):
            continue
        for member in node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if member.name not in HTTP_METHODS:
                continue
            loc = _body_loc(member, lines)
            if loc <= method_budget:
                continue
            end_line = getattr(member, "end_lineno", member.lineno)
            if _range_has_noqa(lines, member.lineno, end_line):
                continue
            msg = (
                f"view method `{node.name}.{member.name}` is {loc} LOC "
                f"(budget {method_budget}) — extract a service or "
                f"mark with `# noqa: fat-view: <reason>`"
            )
            hits.append((member.lineno, member.col_offset, msg))

    return hits


def _check_path(
    path: str,
    fn_budget: int,
    method_budget: int,
) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path}: fat-view: cannot read — {exc}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path, fn_budget, method_budget)
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: fat-view: {msg}")
    return len(hits), False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--fn-budget",
        type=int,
        default=DEFAULT_FN_BUDGET,
        help=f"LOC budget for module-level view functions (default {DEFAULT_FN_BUDGET})",
    )
    parser.add_argument(
        "--method-budget",
        type=int,
        default=DEFAULT_METHOD_BUDGET,
        help=f"LOC budget for View-class HTTP methods (default {DEFAULT_METHOD_BUDGET})",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read source from stdin; pair with --filename",
    )
    parser.add_argument("--filename", default="<stdin>")
    parser.add_argument("paths", nargs="*", help="Python files to check")
    args = parser.parse_args(argv)

    if args.stdin:
        src = sys.stdin.read()
        hits = check_source(src, args.filename, args.fn_budget, args.method_budget)
        for line, col, msg in hits:
            print(f"{args.filename}:{line}:{col + 1}: fat-view: {msg}")
        return 1 if hits else 0

    if not args.paths:
        parser.print_usage(sys.stderr)
        return 2

    total_hits = 0
    had_io_error = False
    for path in expand_python_paths(args.paths):
        count, io_err = _check_path(path, args.fn_budget, args.method_budget)
        total_hits += count
        had_io_error = had_io_error or io_err
    if had_io_error:
        return 2
    return 1 if total_hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
