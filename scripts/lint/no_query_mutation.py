#!/usr/bin/env python3
"""Query-mutation lint rule.

Flags functions whose name begins with a read-promising prefix
(``get_``, ``fetch_``, ``load_``, ``list_``, ``find_``, ``check_``)
whose body mutates persisted state. See
``.claude/docs/architectural-smells.md`` smell 3 (query mutation) and
the CLAUDE.md Canonical Pattern "Query methods are side-effect free".

Mutation shapes flagged:

- ``<obj>.save(...)`` / ``<obj>.delete(...)``
- ``<qs>.update(...)`` / ``<qs>.update_or_create(...)`` /
  ``<qs>.create(...)`` / ``<qs>.bulk_create(...)`` /
  ``<qs>.bulk_update(...)``
- ``<qs>.get_or_create(...)`` (read-write combo — still surprising in a
  method named ``get_foo``)

Exemptions:

- Functions named exactly ``get_or_create`` or ``update_or_create`` —
  user-defined wrappers around the Django method of the same name. If
  you must keep the name, the hidden-mutation comment still works.
- Allow-list via ``# hidden-mutation: <reason>`` on any line of the
  function body (including the ``def`` line). Reason must be non-empty.

Canonical bad shape::

    def get_active_job(site):
        job = Job.objects.filter(site=site).first()
        if not job:
            job = Job.objects.create(site=site)  # ← mutation
        return job

Canonical good shape::

    def get_active_job(site):
        return Job.objects.filter(site=site).first()

    def get_or_create_active_job(site):
        return Job.objects.get_or_create(site=site)

Usage:

    scripts/lint/no_query_mutation.py <file-or-dir> [<file-or-dir> ...]
    scripts/lint/no_query_mutation.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from path_utils import expand_python_paths

READ_PREFIXES = ("get_", "fetch_", "load_", "list_", "find_", "check_")

# Methods whose presence inside a read-named function is suspicious.
# `save` and `delete` are the strongest signal; the queryset-level
# mutators catch the "heal missing data" pattern.
MUTATION_METHODS = {
    "save",
    "delete",
    "update",
    "update_or_create",
    "create",
    "bulk_create",
    "bulk_update",
    "get_or_create",
}

# Functions named exactly these are stdlib-mirroring names — the
# read-write contract is already explicit in the name itself.
EXEMPT_NAMES = {"get_or_create", "update_or_create"}

HIDDEN_RE = re.compile(r"#\s*hidden-mutation:\s*\S")


def _is_mutation_call(node: ast.Call) -> str | None:
    """Return the mutation method name if the call looks like
    ``<receiver>.<mutator>(...)``, else None. Heuristic: any Attribute
    callable whose ``.attr`` is in MUTATION_METHODS counts.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in MUTATION_METHODS:
        return func.attr
    return None


def _func_name_is_readish(name: str) -> bool:
    if name in EXEMPT_NAMES:
        return False
    return any(name.startswith(p) for p in READ_PREFIXES)


def _range_has_hidden_mutation(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if HIDDEN_RE.search(lines[idx]):
            return True
    return False


def _function_mutations(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[int, int, str]]:
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            meth = _is_mutation_call(node)
            if meth is None:
                continue
            # Skip the call if it's nested inside a different (inner)
            # function — that function owns the responsibility, not the
            # outer one. ast.walk doesn't track scope, so we re-check.
            # But keeping this simple: flag all mutations inside the
            # outer function body; inner functions get their own rule
            # application when the walk hits them as separate defs.
            hits.append((node.lineno, node.col_offset, meth))
    return hits


def _inside_another_function(
    tree: ast.AST, target: ast.AST
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    # Find the innermost function that contains ``target``. We use this to
    # dedupe: a mutation at line N is attributed to its innermost
    # enclosing function only.
    owner = None
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


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: query-mutation: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []

    readish_funcs = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _func_name_is_readish(n.name)
    ]

    for func in readish_funcs:
        end_line = getattr(func, "end_lineno", func.lineno)
        if _range_has_hidden_mutation(lines, func.lineno, end_line):
            continue
        mutations: list[tuple[int, int, str]] = []
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            meth = _is_mutation_call(node)
            if meth is None:
                continue
            # Only attribute the mutation to ``func`` if ``func`` is its
            # innermost enclosing function — otherwise an inner def
            # would cause duplicate flags.
            owner = _inside_another_function(tree, node)
            if owner is not func:
                continue
            mutations.append((node.lineno, node.col_offset, meth))
        if not mutations:
            continue
        # Emit one finding per function, summarizing the mutations. Fewer
        # duplicate messages on noisy functions and the fix is usually
        # structural anyway (rename or split).
        summary = ", ".join(sorted({m for _, _, m in mutations}))
        first_line, first_col, _ = mutations[0]
        msg = (
            f"function `{func.name}` promises a read but calls "
            f"`{summary}` — rename to `get_or_create_*` / split into "
            f"reader + mutator, or mark with `# hidden-mutation: <reason>`"
        )
        hits.append((first_line, first_col, msg))
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    try:
        src = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path}: query-mutation: cannot read — {exc}", file=sys.stderr)
        return 0, True
    hits = check_source(src, path)
    for line, col, msg in hits:
        print(f"{path}:{line}:{col + 1}: query-mutation: {msg}")
    return len(hits), False


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: no_query_mutation.py <file-or-dir> [...]  |  "
            "no_query_mutation.py --stdin --filename=<name>",
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
            print(f"{filename}:{line}:{col + 1}: query-mutation: {msg}")
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
