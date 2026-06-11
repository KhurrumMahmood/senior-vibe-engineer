"""Structural guard: every skill-script file read is decode-safe.

Propagated from host-a (precedent read-decode-safety.v1). `read_text`
decodes as UTF-8 (or locale) and raises UnicodeDecodeError -- a ValueError
subclass, *not* an OSError -- on the first non-UTF-8 byte. A read whose only
guard is `except OSError`, or a parse-only handler (json.JSONDecodeError /
yaml.YAMLError / SyntaxError), therefore crashes the whole detector with a
traceback when it scans a latin-1/binary file, instead of skipping it
(arbitrary-source scanners) or failing with a clean message (artifact
readers).

A read is safe when an enclosing try catches UnicodeDecodeError / UnicodeError
/ ValueError / Exception / BaseException (or is a bare except), or when the
call passes errors="replace"/"ignore"/etc. This is a static AST scan, so it
covers every current and future skill script and cannot re-drift -- there is
no allowlist.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

COVERING = {
    "UnicodeDecodeError",
    "UnicodeError",
    "ValueError",
    "Exception",
    "BaseException",
}
SAFE_ERRORS = {"replace", "ignore", "surrogateescape", "backslashreplace"}


def _handler_names(handler: ast.ExceptHandler) -> list[str]:
    if handler.type is None:
        return ["<bare>"]
    elts = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names = []
    for node in elts:
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return names


def _handlers_cover(handlers: list[ast.ExceptHandler]) -> bool:
    return any(
        name in COVERING for handler in handlers for name in _handler_names(handler)
    )


def _read_has_safe_errors(call: ast.Call) -> bool:
    return any(
        kw.arg == "errors"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value in SAFE_ERRORS
        for kw in call.keywords
    )


def _exposed_read_lines(tree: ast.AST) -> list[int]:
    offenders: list[int] = []

    def walk(node: ast.AST, covered: bool) -> None:
        if isinstance(node, ast.Try):
            inner = covered or _handlers_cover(node.handlers)
            for child in node.body:
                walk(child, inner)
            for child in node.handlers + node.orelse + node.finalbody:
                walk(child, covered)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_text"
            and not covered
            and not _read_has_safe_errors(node)
        ):
            offenders.append(node.lineno)
        for child in ast.iter_child_nodes(node):
            walk(child, covered)

    walk(tree, False)
    return offenders


def test_skill_detector_reads_guard_against_decode_errors() -> None:
    skills_root = PROJECT_ROOT / ".claude" / "skills"
    offenders: list[str] = []
    for script in sorted(skills_root.glob("*/scripts/*.py")):
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for lineno in _exposed_read_lines(tree):
            offenders.append(f"{script.relative_to(PROJECT_ROOT)}:{lineno}")

    assert offenders == [], (
        "skill-script read_text() calls that can raise an uncaught "
        "UnicodeDecodeError. Catch (OSError, UnicodeDecodeError) and skip "
        "(arbitrary-source scanners) or fail cleanly (required-artifact "
        "readers); never let the decode error escape as a traceback. See "
        "precedent read-decode-safety.v1:\n" + "\n".join(offenders)
    )
