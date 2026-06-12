#!/usr/bin/env python3
"""no-bare-int-request lint rule (DEFECTIVE FIXTURE — do not adopt).

Intended to flag raw coercion of user-supplied request data without the
canonical ``safe_int`` helper. Looks complete: stdlib-only, correct CLI
contract, reason-required noqa, and a fixture pair that ``verify_rule.py``
passes.

The injected CONSEQUENTIAL defect: the matcher only catches the SUBSCRIPT form
``int(request.POST["key"])`` / ``int(request.GET["key"])``. The real codebase
(and the seeded anchor bug) uses the ``.get(...)`` form,
``int(request.POST.get("page"))``. So this rule fires ZERO times on the very
bug it was supposedly built for — it is a guard in name only. Its own bad
fixture is tailored to the subscript form, so the skill's differential verifier
(BAD fires, GOOD clean) is satisfied and a naive "do the files exist + does
verify_rule pass?" check would wrongly green-light it.

Only the historical-fire check (C4) — run the rule against the pre-anchor
blob and require hits>0 — exposes the theater.

Allow-list: ``# noqa: no-bare-int-request: <reason>`` (reason required).

Usage / exit codes identical to the conformant rule.

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys

from ast_lint import run_lint

RULE = "no-bare-int-request"

NOQA_RE = re.compile(r"#\s*noqa:\s*(?:[A-Za-z0-9-]+,\s*)*" + re.escape(RULE) + r":\s*\S")

REQUEST_DICT_ATTRS = {"POST", "GET"}


def _is_request_subscript(node: ast.AST) -> bool:
    """True if *node* is ``<x>.POST[...]`` / ``<x>.GET[...]``.

    DEFECT: this only recognises subscript access, never ``.get(...)``.
    """
    if not isinstance(node, ast.Subscript):
        return False
    inner = node.value
    return isinstance(inner, ast.Attribute) and inner.attr in REQUEST_DICT_ATTRS


def _is_bare_int_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Name) or func.id != "int":
        return False
    if not node.args:
        return False
    return _is_request_subscript(node.args[0])


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
            "bare int(request.POST/GET[...]) — parse user input through "
            "safe_int(...) instead "
            "(allow-list: # noqa: no-bare-int-request: <reason>)"
        )
        hits.append((start, node.col_offset, msg))
    return hits


def main(argv: list[str]) -> int:
    return run_lint(argv, rule_name=RULE, check_source=check_source)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
