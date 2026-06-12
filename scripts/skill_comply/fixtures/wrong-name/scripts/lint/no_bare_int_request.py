#!/usr/bin/env python3
"""no-bare-int-request lint rule.

Flags a bare ``int(...)`` call whose argument is itself a
``request.POST.get(...)`` / ``request.GET.get(...)`` lookup — i.e. raw
coercion of user-supplied request data without the canonical ``safe_int``
helper. A missing key makes ``.get(...)`` return ``None`` and ``int(None)``
raise ``TypeError``; junk input raises ``ValueError``. ``safe_int`` swallows
both with a default, so user input must route through it.

Matches (fires)::

    int(request.POST.get("page"))
    int(request.GET.get("per_page", "25"))

Does NOT match (legitimate)::

    safe_int(request.GET.get("qty"))   # already canonical — func is safe_int
    int(product_id)                    # not a request lookup
    int(request.POST.get("x")) + 1     # still fires: the int(...) call matches

False-positive boundary: the OUTER call must be the builtin ``int`` (an
``ast.Name`` with id ``int``), and its first positional arg must be a call to
``<something>.POST.get`` or ``<something>.GET.get``. ``safe_int(...)`` has a
different ``func`` name and is ignored.

Allow-list: add ``# noqa: no-bare-int-request: <reason>`` on any line of the
matched span. The reason must be non-empty so the allow-list cannot be spammed
with a bare pragma.

Usage:

    scripts/lint/no_bare_int_request.py <file.py> [<file.py> ...]
    scripts/lint/no_bare_int_request.py --stdin --filename=<display-name>

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error (unreadable file, bad CLI)

Stdlib-only; safe to invoke under bare ``python3`` from a worktree that does
not yet have a populated ``.venv``.
"""
from __future__ import annotations

import ast
import re
import sys

from ast_lint import run_lint

# DEFECT (skill-comply wrong-name fixture): the emitted tag below is DRIFTED from
# the wired/manifest rule name "no-bare-int-request". The matcher itself is
# correct, so verify_rule (C3) passes on exit codes — but the scorer counts
# historical-fire hits by the wired tag, sees zero "no-bare-int-request: " lines,
# and C4 fails. Same scorecard signature as a matcher that misses the bug.
RULE = "no-bare-int-req"

# Reason must contain at least one non-whitespace character after the colon.
NOQA_RE = re.compile(r"#\s*noqa:\s*(?:[A-Za-z0-9-]+,\s*)*" + re.escape(RULE) + r":\s*\S")

# Request attributes whose .get(...) returns untrusted user input.
REQUEST_DICT_ATTRS = {"POST", "GET"}


def _is_request_get_call(node: ast.AST) -> bool:
    """True if *node* is ``<x>.POST.get(...)`` / ``<x>.GET.get(...)``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # func must be an attribute access ending in `.get`
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return False
    # the object the `.get` is called on must be `<x>.POST` or `<x>.GET`
    inner = func.value
    return isinstance(inner, ast.Attribute) and inner.attr in REQUEST_DICT_ATTRS


def _is_bare_int_call(node: ast.AST) -> bool:
    """True if *node* is ``int(<request .get call>)`` — the builtin int, not
    ``safe_int`` or any other name."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # Outer call must be the bare builtin `int` — an ast.Name with id "int".
    # `safe_int(...)` is an ast.Name with id "safe_int" → excluded.
    # `x.int(...)` would be an ast.Attribute → excluded.
    if not isinstance(func, ast.Name) or func.id != "int":
        return False
    if not node.args:
        return False
    return _is_request_get_call(node.args[0])


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(
            f"{filename}:{exc.lineno or 0}: {RULE}: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return []
    lines = src.splitlines()
    hits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not _is_bare_int_call(node):
            continue
        start = node.lineno
        end = getattr(node, "end_lineno", None) or start
        if _range_has_noqa(lines, start, end):
            continue
        msg = (
            "bare int(request.POST/GET.get(...)) — raw int() raises on a "
            "missing key (TypeError) or junk input (ValueError); parse user "
            "input through safe_int(...) instead "
            "(allow-list: # noqa: no-bare-int-request: <reason>)"
        )
        hits.append((start, node.col_offset, msg))
    return hits


def main(argv: list[str]) -> int:
    return run_lint(argv, rule_name=RULE, check_source=check_source)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
