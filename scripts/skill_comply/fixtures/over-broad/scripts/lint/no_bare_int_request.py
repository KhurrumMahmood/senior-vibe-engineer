#!/usr/bin/env python3
"""no-bare-int-request lint rule — OVER-BROAD variant (skill-comply defect fixture).

Intent (per pattern.md): flag a bare ``int(...)`` of *user-supplied* request
``POST``/``GET`` data. This implementation DRIFTS — it fires on the ``int()``
wrapper of *any* ``.get(...)`` call regardless of receiver, so it also flags
``int(request.session.get(...))``, ``int(config.get(...))``, ``int(d.get(...))``.

It still catches the real bug, so the skill's own differential verifier (C3) and
the historical-fire check (C4) both pass — its self-consistent fixtures never
exercise the innocent-code firing. The over-breadth surfaces only when the rule
is run across its whole enforcement scope, which is exactly what the scorer's C8
(bounded incidental firing) does.

Stdlib-only. CLI contract per ast_lint (--stdin --filename / file args; 0/1/2).
"""
from __future__ import annotations

import ast
import re
import sys

from ast_lint import run_lint

RULE = "no-bare-int-request"

NOQA_RE = re.compile(r"#\s*noqa:\s*(?:[A-Za-z0-9-]+,\s*)*" + re.escape(RULE) + r":\s*\S")


def _is_any_get_call(node: ast.AST) -> bool:
    """OVER-BROAD: True for ANY ``<expr>.get(...)`` call — no POST/GET scoping,
    no check on what the ``.get`` is called on."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    )


def _is_bare_int_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Name) or func.id != "int":
        return False
    if not node.args:
        return False
    return _is_any_get_call(node.args[0])


def _range_has_noqa(lines: list[str], start: int, end: int) -> bool:
    for idx in range(start - 1, min(end, len(lines))):
        if NOQA_RE.search(lines[idx]):
            return True
    return False


def check_source(src: str, filename: str) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as exc:
        print(f"{filename}:{exc.lineno or 0}: {RULE}: syntax error — {exc.msg}", file=sys.stderr)
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
            "bare int(...get(...)) — parse user input through safe_int(...) "
            "(allow-list: # noqa: no-bare-int-request: <reason>)"
        )
        hits.append((start, node.col_offset, msg))
    return hits


def main(argv: list[str]) -> int:
    return run_lint(argv, rule_name=RULE, check_source=check_source)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
