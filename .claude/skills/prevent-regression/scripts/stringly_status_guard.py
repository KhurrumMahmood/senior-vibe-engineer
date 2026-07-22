#!/usr/bin/env python3
"""Bundled blocking guard for the closed first-party string-state invariant.

Flags Django ``status``/``phase``/``state`` string fields without a
``TextChoices`` authority plus bare-string comparisons and assignments on
those attributes. Vendor boundaries may use
``# noqa: stringly-status: <reason>``. The script is stdlib-only and is the
installed counterpart of the repository's ``stringly-status`` wrapper.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Iterable


RULE = "stringly-status"
STATE_FIELDS = {"status", "phase", "state"}
FIELD_CALLS = {"CharField", "TextField"}
NOQA_RE = re.compile(r"#\s*noqa:\s*stringly-status:\s*\S")
SKIP_DIRS = {".venv", "__pycache__", "migrations", "node_modules", "staticfiles"}


def _expand_paths(paths: Iterable[str]) -> list[str]:
    """Return stable Python files without a repository path helper."""
    result: list[str] = []
    seen: set[str] = set()

    def add(path: Path | str) -> None:
        display = os.fspath(path)
        key = str(Path(display).resolve()) if Path(display).exists() else display
        if key not in seen:
            seen.add(key)
            result.append(display)

    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for directory, directories, files in os.walk(path):
                directories[:] = [
                    name for name in sorted(directories)
                    if not name.startswith(".") and name not in SKIP_DIRS
                ]
                for filename in sorted(files):
                    candidate = Path(directory) / filename
                    if candidate.suffix == ".py":
                        add(candidate)
        elif not path.exists() or path.suffix == ".py":
            add(path)
    return result


def _looks_like_choices_name(name: str) -> bool:
    return name.endswith(("Choices", "Status", "State", "Phase"))


def _is_field_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute) and func.attr in FIELD_CALLS
    ) or (isinstance(func, ast.Name) and func.id in FIELD_CALLS)


def _has_textchoices(call: ast.Call) -> bool:
    choices = next((kw.value for kw in call.keywords if kw.arg == "choices"), None)
    if isinstance(choices, ast.Attribute):
        value = choices.value
        return (
            isinstance(value, ast.Name) and _looks_like_choices_name(value.id)
        ) or (
            isinstance(value, ast.Attribute) and _looks_like_choices_name(value.attr)
        )
    return isinstance(choices, ast.Name) and _looks_like_choices_name(choices.id)


def _inside_model(path: list[ast.AST]) -> bool:
    for node in path:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if (isinstance(base, ast.Attribute) and base.attr == "Model") or (
                isinstance(base, ast.Name) and base.id == "Model"
            ):
                return True
    return False


def _literal(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _state_attr(node: ast.AST) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) and node.attr in STATE_FIELDS else None


def _literal_container(node: ast.AST) -> bool:
    return (
        isinstance(node, (ast.Tuple, ast.List, ast.Set))
        and bool(node.elts)
        and all(_literal(item) is not None for item in node.elts)
    )


def _emit(
    node: ast.AST, lines: list[str], message: str, hits: list[tuple[int, int, str]]
) -> None:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", None) or start
    if not any(NOQA_RE.search(lines[index]) for index in range(start - 1, min(end, len(lines)))):
        hits.append((start, getattr(node, "col_offset", 0), message))


def _check_field(node: ast.Assign, lines: list[str], hits: list[tuple[int, int, str]]) -> None:
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return
    target = node.targets[0]
    if target.id in STATE_FIELDS and isinstance(node.value, ast.Call) and _is_field_call(node.value) and not _has_textchoices(node.value):
        _emit(
            node,
            lines,
            f"field `{target.id}` is a string-typed state field without `choices=<TextChoices>` — define a `models.TextChoices` enum or mark with `# noqa: {RULE}: <reason>`",
            hits,
        )


def _check_compare(node: ast.Compare, lines: list[str], hits: list[tuple[int, int, str]]) -> None:
    if len(node.ops) != 1:
        return
    left, right, op = node.left, node.comparators[0], node.ops[0]
    attr = None
    if isinstance(op, (ast.Eq, ast.NotEq)):
        if _state_attr(left) and _literal(right) is not None:
            attr = _state_attr(left)
        elif _state_attr(right) and _literal(left) is not None:
            attr = _state_attr(right)
    elif isinstance(op, (ast.In, ast.NotIn)) and _state_attr(left) and _literal_container(right):
        attr = _state_attr(left)
    if attr:
        _emit(
            node,
            lines,
            f"comparison on `.{attr}` uses a string literal — reference the `TextChoices` enum member or mark with `# noqa: {RULE}: <reason>`",
            hits,
        )


def _check_assignment(
    node: ast.Assign | ast.AnnAssign, lines: list[str], hits: list[tuple[int, int, str]]
) -> None:
    if isinstance(node, ast.AnnAssign):
        targets = [node.target]
        value = node.value
    else:
        targets = node.targets
        value = node.value
    if _literal(value) is None:
        return
    for target in targets:
        if isinstance(target, ast.Attribute) and target.attr in STATE_FIELDS:
            _emit(
                target,
                lines,
                f"assignment to `.{target.attr}` uses a string literal — reference the `TextChoices` enum member or mark with `# noqa: {RULE}: <reason>`",
                hits,
            )


def check_source(source: str, filename: str) -> list[tuple[int, int, str]]:
    """Return all closed-state violations in one Python source string."""
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    hits: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, path: list[ast.AST]) -> None:
        if isinstance(node, ast.Assign):
            if _inside_model(path):
                _check_field(node, lines, hits)
            _check_assignment(node, lines, hits)
        elif isinstance(node, ast.AnnAssign):
            _check_assignment(node, lines, hits)
        elif isinstance(node, ast.Compare):
            _check_compare(node, lines, hits)
        for child in ast.iter_child_nodes(node):
            visit(child, path + [node])

    visit(tree, [])
    return hits


def _check_path(path: str) -> tuple[int, bool]:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{path}: {RULE}: cannot read — {exc}", file=sys.stderr)
        return 0, True
    try:
        hits = check_source(source, path)
    except SyntaxError as exc:
        print(
            f"{path}:{exc.lineno or 0}: {RULE}: syntax error — {exc.msg}",
            file=sys.stderr,
        )
        return 0, True
    for line, column, message in hits:
        print(f"{path}:{line}:{column + 1}: {RULE}: {message}")
    return len(hits), False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Python files or directories to check.")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--filename", default="<stdin>")
    args = parser.parse_args(argv)
    if args.stdin:
        try:
            hits = check_source(sys.stdin.read(), args.filename)
        except SyntaxError as exc:
            print(
                f"{args.filename}:{exc.lineno or 0}: {RULE}: syntax error — {exc.msg}",
                file=sys.stderr,
            )
            return 2
        for line, column, message in hits:
            print(f"{args.filename}:{line}:{column + 1}: {RULE}: {message}")
        return 1 if hits else 0
    if not args.paths:
        parser.error("provide one or more files/directories, or --stdin")
    total = 0
    io_error = False
    for path in _expand_paths(args.paths):
        count, had_error = _check_path(path)
        total += count
        io_error = io_error or had_error
    return 2 if io_error else (1 if total else 0)


if __name__ == "__main__":
    raise SystemExit(main())
