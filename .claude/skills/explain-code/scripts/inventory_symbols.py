#!/usr/bin/env python3
"""Enumerate /explain-code targets without a repository runtime dependency.

The Python path is the frozen reference oracle: it preserves the existing AST
public-surface and ranking rules. TypeScript v1 is intentionally narrower. It
collects *named, direct, top-level* ``export`` declarations from ``.ts`` and
``.tsx`` files using a lexical scanner. It does not resolve imports, aliases,
barrels, or default expressions; those exports are emitted in ``unexplained``
so an explanation cannot quietly claim coverage it did not earn.

The result is a stable JSON artifact consumed by the /explain-code scouts and
the family-local renderer. This script is stdlib-only so a copied skill can run
with isolated host Python tools.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


PYTHON_SUFFIXES = frozenset({".py"})
TYPESCRIPT_SUFFIXES = frozenset({".ts", ".tsx"})
SOURCE_SUFFIXES = PYTHON_SUFFIXES | TYPESCRIPT_SUFFIXES
IGNORED_DIRECTORY_NAMES = frozenset(
    {
        "__pycache__",
        "__tests__",
        ".next",
        "build",
        "coverage",
        "dist",
        "generated",
        "migrations",
        "node_modules",
        "test",
        "tests",
        "vendor",
    }
)
TEST_FILE_RE = re.compile(
    r"(?:^test_|^tests_|^spec_|_test\.|\.test\.|\.spec\.)", re.IGNORECASE
)
TS_IDENTIFIER = r"[$A-Za-z_][\w$]*"
TS_DIRECT_EXPORTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "function",
        re.compile(
            rf"^\s*export\s+(?:default\s+)?(?:declare\s+)?(?:async\s+)?function\s*\*?\s+(?P<name>{TS_IDENTIFIER})\b"
        ),
    ),
    (
        "class",
        re.compile(
            rf"^\s*export\s+(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?class\s+(?P<name>{TS_IDENTIFIER})\b"
        ),
    ),
    (
        "enum",
        re.compile(
            rf"^\s*export\s+(?:declare\s+)?(?:const\s+)?enum\s+(?P<name>{TS_IDENTIFIER})\b"
        ),
    ),
    (
        "interface",
        re.compile(
            rf"^\s*export\s+(?:declare\s+)?interface\s+(?P<name>{TS_IDENTIFIER})\b"
        ),
    ),
    (
        "type",
        re.compile(rf"^\s*export\s+type\s+(?P<name>{TS_IDENTIFIER})\b"),
    ),
    (
        "namespace",
        re.compile(
            rf"^\s*export\s+(?:declare\s+)?(?:namespace|module)\s+(?P<name>{TS_IDENTIFIER})\b"
        ),
    ),
)
TS_VARIABLE_EXPORT_RE = re.compile(
    r"^\s*export\s+(?:declare\s+)?(?:const|let|var)\s+(?P<bindings>.*)",
    re.DOTALL,
)
TS_UNRESOLVED_EXPORT_RE = re.compile(
    r"^\s*export\s+(?:(?:type\s+)?\{|\*|default\b|=\s*)"
)
TS_BRANCH_RE = re.compile(r"\b(?:if|for|while|catch|case)\b|&&|\|\||\?")


def _is_public(name: str, dunder_all: set[str] | None) -> bool:
    """A Python name is public iff it is non-private and allowed by __all__."""
    return not name.startswith("_") and (dunder_all is None or name in dunder_all)


def _loc(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    return max(1, end - node.lineno + 1) if end is not None else 1


def _python_branch_count(node: ast.AST) -> int:
    branch_nodes: tuple[type[ast.AST], ...] = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.BoolOp,
        ast.IfExp,
    )
    return sum(1 for child in ast.walk(node) if isinstance(child, branch_nodes))


def _symbol_key(file_rel: Path, symbol: str) -> str:
    return f"{file_rel.stem}__{symbol.rsplit('.', 1)[-1]}"


def _rank_score(*, loc: int, branches: int, has_doc: bool, kind: str) -> int:
    score = branches + (0 if has_doc else 10) + (5 if loc > 50 else 0)
    return min(score, 20) if kind == "class" else score


def _build_entry(
    *,
    file_rel: Path,
    symbol: str,
    kind: str,
    lineno: int,
    loc: int,
    branch_count: int,
    has_docstring: bool,
) -> dict[str, Any]:
    return {
        "symbol_key": _symbol_key(file_rel, symbol),
        "file": str(file_rel),
        "symbol": symbol,
        "kind": kind,
        "lineno": lineno,
        "loc": loc,
        "branch_count": branch_count,
        "has_docstring": has_docstring,
        "rank_score": _rank_score(
            loc=loc,
            branches=branch_count,
            has_doc=has_docstring,
            kind=kind,
        ),
    }


def _dunder_all(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return None
        names = {
            element.value
            for element in node.value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
        return names
    return None


def _read_source(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"warn: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _inventory_python_file(path: Path, file_rel: Path) -> tuple[list[dict[str, Any]], int]:
    source = _read_source(path)
    if source is None:
        return [], 0
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"warn: cannot parse {path}: {exc.msg}", file=sys.stderr)
        return [], 0

    dunder_all = _dunder_all(tree)
    public: list[dict[str, Any]] = []
    total = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            if _is_public(node.name, dunder_all):
                public.append(
                    _build_entry(
                        file_rel=file_rel,
                        symbol=node.name,
                        kind="function",
                        lineno=node.lineno,
                        loc=_loc(node),
                        branch_count=_python_branch_count(node),
                        has_docstring=bool(ast.get_docstring(node)),
                    )
                )
        elif isinstance(node, ast.ClassDef):
            total += 1
            class_public = _is_public(node.name, dunder_all)
            if class_public:
                public.append(
                    _build_entry(
                        file_rel=file_rel,
                        symbol=node.name,
                        kind="class",
                        lineno=node.lineno,
                        loc=_loc(node),
                        branch_count=_python_branch_count(node),
                        has_docstring=bool(ast.get_docstring(node)),
                    )
                )
                for method in node.body:
                    if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if method.name.startswith("_") and method.name != "__init__":
                        continue
                    public.append(
                        _build_entry(
                            file_rel=file_rel,
                            symbol=f"{node.name}.{method.name}",
                            kind="method",
                            lineno=method.lineno,
                            loc=_loc(method),
                            branch_count=_python_branch_count(method),
                            has_docstring=bool(ast.get_docstring(method)),
                        )
                    )
        elif isinstance(node, ast.Assign):
            total += 1
            for target in node.targets:
                if isinstance(target, ast.Name) and _is_public(target.id, dunder_all):
                    public.append(
                        _build_entry(
                            file_rel=file_rel,
                            symbol=target.id,
                            kind="module-var",
                            lineno=node.lineno,
                            loc=_loc(node),
                            branch_count=_python_branch_count(node),
                            has_docstring=False,
                        )
                    )
    return public, total


def _mask_typescript_noncode(source: str) -> str:
    """Replace comments, strings, and regex literals while retaining lines.

    This is deliberately a collector, not a TypeScript parser. Masking is only
    enough to prevent words such as ``export`` in non-code from becoming public
    symbols, and to keep brace counting useful for top-level declarations.
    """
    out: list[str] = []
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                out.extend((" ", " "))
                index += 2
                state = "line-comment"
                continue
            if char == "/" and following == "*":
                out.extend((" ", " "))
                index += 2
                state = "block-comment"
                continue
            if char in {"'", '"', "`"}:
                out.append(" ")
                index += 1
                state = {"'": "single", '"': "double", "`": "template"}[char]
                continue
            if char == "/" and _looks_like_regex_start(source, index):
                out.append(" ")
                index += 1
                state = "regex"
                continue
            out.append(char)
            index += 1
            continue
        if state == "line-comment":
            out.append("\n" if char == "\n" else " ")
            index += 1
            if char == "\n":
                state = "code"
            continue
        if state == "block-comment":
            if char == "*" and following == "/":
                out.extend((" ", " "))
                index += 2
                state = "code"
            else:
                out.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if state in {"regex", "regex-class"}:
            if char == "\\":
                out.append(" ")
                index += 1
                if index < len(source):
                    escaped = source[index]
                    out.append("\n" if escaped == "\n" else " ")
                    index += 1
                continue
            if char == "\n":
                out.append("\n")
                index += 1
                state = "code"
                continue
            out.append(" ")
            index += 1
            if state == "regex" and char == "[":
                state = "regex-class"
            elif state == "regex-class" and char == "]":
                state = "regex"
            elif state == "regex" and char == "/":
                state = "code"
            continue
        quote = {"single": "'", "double": '"', "template": "`"}[state]
        if char == "\\":
            out.append(" ")
            index += 1
            if index < len(source):
                escaped = source[index]
                out.append("\n" if escaped == "\n" else " ")
                index += 1
            continue
        out.append("\n" if char == "\n" else " ")
        index += 1
        if char == quote:
            state = "code"
    return "".join(out)


def _looks_like_regex_start(source: str, slash_index: int) -> bool:
    """Recognize expression-position regex starts without parsing TypeScript.

    The accepted v1 only needs enough lexical awareness to avoid counting
    braces inside ordinary regex literals. Division remains code when the
    preceding token can end an expression.
    """
    before = source[:slash_index].rstrip()
    if not before:
        return True
    if before.endswith(("=", "(", "[", "{", ",", ":", ";", "!", "?", "=>", "&&", "||")):
        return True
    word_match = re.search(r"([A-Za-z_$][\w$]*)$", before)
    return bool(
        word_match
        and word_match.group(1)
        in {"case", "delete", "in", "instanceof", "new", "return", "throw", "typeof", "void", "yield"}
    )


def _top_level_line_indexes(masked_lines: list[str]) -> set[int]:
    depth = 0
    top_level: set[int] = set()
    for index, line in enumerate(masked_lines):
        if depth == 0:
            top_level.add(index)
        depth += line.count("{") - line.count("}")
        depth = max(depth, 0)
    return top_level


def _typescript_has_docstring(source_lines: list[str], declaration_line: int) -> bool:
    index = declaration_line - 1
    while index >= 0 and not source_lines[index].strip():
        index -= 1
    if index < 0 or "*/" not in source_lines[index]:
        return False
    while index >= 0:
        if "/**" in source_lines[index]:
            return True
        if "/*" in source_lines[index]:
            return False
        index -= 1
    return False


def _typescript_declaration_end(masked_lines: list[str], start: int, kind: str) -> int:
    """Return a conservative, line-based lexical span end for ranking only."""
    block_kinds = {"class", "enum", "function", "interface", "namespace"}
    depth = 0
    opened = False
    for index in range(start, len(masked_lines)):
        line = masked_lines[index]
        if kind in block_kinds:
            for char in line:
                if char == "{":
                    depth += 1
                    opened = True
                elif char == "}" and opened:
                    depth -= 1
            if opened and depth <= 0:
                return index
        elif ";" in line:
            return index
        elif index > start and not line.strip():
            return index - 1
    return start if not opened and kind in block_kinds else len(masked_lines) - 1


def _typescript_direct_export(line: str) -> tuple[str, str] | None:
    for kind, pattern in TS_DIRECT_EXPORTS:
        match = pattern.match(line)
        if match:
            return kind, match.group("name")
    return None


def _typescript_statement_end(masked_lines: list[str], start: int) -> int:
    """Find the first top-level semicolon for one lexical declaration."""
    round_depth = 0
    square_depth = 0
    brace_depth = 0
    for index in range(start, len(masked_lines)):
        for char in masked_lines[index]:
            if char == "(":
                round_depth += 1
            elif char == ")":
                round_depth = max(0, round_depth - 1)
            elif char == "[":
                square_depth += 1
            elif char == "]":
                square_depth = max(0, square_depth - 1)
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth = max(0, brace_depth - 1)
            elif char == ";" and round_depth == square_depth == brace_depth == 0:
                return index
    return start


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    round_depth = 0
    square_depth = 0
    brace_depth = 0
    for index, char in enumerate(text):
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth = max(0, round_depth - 1)
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth = max(0, square_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "," and round_depth == square_depth == brace_depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _typescript_variable_exports(statement: str) -> tuple[list[str], bool]:
    """Return simple identifier bindings and whether any binding was unknown."""
    match = TS_VARIABLE_EXPORT_RE.match(statement)
    if not match:
        return [], False
    names: list[str] = []
    unknown = False
    for binding in _split_top_level_commas(match.group("bindings").rstrip(";")):
        name_match = re.match(rf"\s*(?P<name>{TS_IDENTIFIER})\b", binding)
        if name_match:
            names.append(name_match.group("name"))
        elif binding.strip():
            unknown = True
    return names, unknown


def _typescript_export_statement(source_lines: list[str], start: int) -> str:
    pieces: list[str] = []
    for line in source_lines[start:]:
        pieces.append(line.strip())
        if ";" in line:
            break
    return " ".join(pieces).rstrip(";").strip()


def _inventory_typescript_file(
    path: Path, file_rel: Path
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    source = _read_source(path)
    if source is None:
        return [], 0, []
    source_lines = source.splitlines()
    masked_lines = _mask_typescript_noncode(source).splitlines()
    public: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    total = 0
    for index in sorted(_top_level_line_indexes(masked_lines)):
        masked_line = masked_lines[index]
        if re.match(r"^\s*export\s+(?:declare\s+)?(?:const|let|var)\b", masked_line):
            end = _typescript_statement_end(masked_lines, index)
            statement = "\n".join(masked_lines[index : end + 1])
            names, unknown_binding = _typescript_variable_exports(statement)
            segment = statement
            for name in names:
                public.append(
                    _build_entry(
                        file_rel=file_rel,
                        symbol=name,
                        kind="module-var",
                        lineno=index + 1,
                        loc=max(1, end - index + 1),
                        branch_count=len(TS_BRANCH_RE.findall(segment)),
                        has_docstring=_typescript_has_docstring(source_lines, index),
                    )
                )
            total += len(names) + (1 if unknown_binding else 0)
            if unknown_binding:
                unexplained.append(
                    {
                        "file": str(file_rel),
                        "symbol": _typescript_export_statement(source_lines, index),
                        "kind": "unresolved-export-binding",
                        "lineno": index + 1,
                        "reason": "TypeScript v1 cannot enumerate this exported binding pattern lexically.",
                    }
                )
            continue
        direct = _typescript_direct_export(masked_line)
        if direct is not None:
            kind, name = direct
            total += 1
            end = _typescript_declaration_end(masked_lines, index, kind)
            segment = "\n".join(masked_lines[index : end + 1])
            public.append(
                _build_entry(
                    file_rel=file_rel,
                    symbol=name,
                    kind=kind,
                    lineno=index + 1,
                    loc=max(1, end - index + 1),
                    branch_count=len(TS_BRANCH_RE.findall(segment)),
                    has_docstring=_typescript_has_docstring(source_lines, index),
                )
            )
            continue
        if TS_UNRESOLVED_EXPORT_RE.match(masked_line):
            total += 1
            statement = _typescript_export_statement(source_lines, index)
            unexplained.append(
                {
                    "file": str(file_rel),
                    "symbol": statement,
                    "kind": "unresolved-export",
                    "lineno": index + 1,
                    "reason": "TypeScript v1 does not resolve export aliases or re-exports.",
                }
            )
            continue
        if re.match(
            rf"^\s*(?:declare\s+)?(?:async\s+)?function\s+{TS_IDENTIFIER}\b|^\s*(?:abstract\s+)?class\s+{TS_IDENTIFIER}\b|^\s*(?:const|let|var)\s+{TS_IDENTIFIER}\b",
            masked_line,
        ):
            total += 1
    return public, total, unexplained


def _is_ignored(path: Path, target: Path) -> bool:
    try:
        relative = path.relative_to(target)
    except ValueError:
        return False
    parts = relative.parts
    if any(part.casefold() in IGNORED_DIRECTORY_NAMES for part in parts[:-1]):
        return True
    name = path.name.casefold()
    return (
        TEST_FILE_RE.search(name) is not None
        or name.endswith(".d.ts")
        or ".generated." in name
        or name.startswith("generated_")
    )


def _collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix.casefold() in SOURCE_SUFFIXES else []
    if not target.is_dir():
        return []
    return [
        path
        for path in sorted(target.rglob("*"))
        if path.is_file()
        and path.suffix.casefold() in SOURCE_SUFFIXES
        and not _is_ignored(path, target)
    ]


def _display_path(path: Path, repo_root: Path) -> Path:
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path


def _resolve_collisions(entries: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for entry in entries:
        key = entry["symbol_key"]
        counts[key] = counts.get(key, 0) + 1
    candidates: dict[str, int] = {}
    for entry in entries:
        if counts[entry["symbol_key"]] <= 1:
            continue
        file_stem = str(Path(entry["file"]).with_suffix(""))
        safe_path = re.sub(r"[^A-Za-z0-9]+", "_", file_stem).strip("_")
        safe_symbol = re.sub(r"[^A-Za-z0-9]+", "_", entry["symbol"]).strip("_")
        candidate = f"{safe_path}__{safe_symbol}"
        candidates[candidate] = candidates.get(candidate, 0) + 1
        entry["symbol_key"] = candidate
    for entry in entries:
        if candidates.get(entry["symbol_key"], 0) > 1:
            entry["symbol_key"] = f"{entry['symbol_key']}__line_{entry['lineno']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="Python, TS, or TSX file/directory")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max", type=int, default=15, help="Max annotations (default: 15)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root used for stable relative file names (default: cwd)",
    )
    args = parser.parse_args(argv)
    target_arg = str(args.target)
    target = args.target.resolve()
    repo_root = args.repo_root.resolve()
    if not target.exists():
        print(f"error: target not found: {args.target}", file=sys.stderr)
        return 1
    files = _collect_files(target)
    if not files:
        print(f"error: no supported source files under {args.target}", file=sys.stderr)
        return 1

    all_public: list[dict[str, Any]] = []
    all_unexplained: list[dict[str, Any]] = []
    total_symbols = 0
    languages: set[str] = set()
    for path in files:
        file_rel = _display_path(path, repo_root)
        if path.suffix.casefold() == ".py":
            entries, file_total = _inventory_python_file(path, file_rel)
            languages.add("python")
            all_public.extend(entries)
            total_symbols += file_total
        else:
            entries, file_total, unresolved = _inventory_typescript_file(path, file_rel)
            languages.add("typescript")
            all_public.extend(entries)
            total_symbols += file_total
            all_unexplained.extend(unresolved)
    if not all_public:
        print(f"error: no public symbols in {args.target}", file=sys.stderr)
        return 1

    _resolve_collisions(all_public)
    all_public.sort(key=lambda entry: (-entry["rank_score"], entry["file"], entry["lineno"], entry["symbol"]))
    all_unexplained.sort(key=lambda entry: (entry["file"], entry["lineno"], entry["symbol"]))
    budget = max(1, args.max)
    selected = all_public[:budget]
    payload = {
        "schema_version": 1,
        "language": next(iter(languages)) if len(languages) == 1 else "mixed",
        "target": target_arg,
        "files": [str(_display_path(path, repo_root)) for path in files],
        "symbol_count_total": total_symbols,
        "public_symbol_count": len(all_public),
        "max": budget,
        "targets": selected,
        "overflow": [
            {
                "symbol_key": entry["symbol_key"],
                "file": entry["file"],
                "symbol": entry["symbol"],
                "reason": "budget-cap",
            }
            for entry in all_public[budget:]
        ],
        "unexplained": all_unexplained,
    }
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {args.output}: {exc}", file=sys.stderr)
        return 2
    print(
        f"wrote {args.output}: {len(selected)} annotated / {len(all_public)} public / "
        f"{total_symbols} total / {len(all_unexplained)} unresolved exports"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
