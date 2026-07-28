#!/usr/bin/env python3
"""Produce bounded C++20 project, lexical, and direct-body syntax facts.

Only first-party ``.cpp``, ``.cc``, and ``.cxx`` translation units in an exact,
current Clang++ C++20 compilation database are accepted. Headers enter the
analysis only when Clang dependency output assigns them to one of those units.
The AST facts retain namespaces, declaring class contexts, overload signatures,
operator spellings, and template declaration context. They do not prove ODR,
ABI, instantiation, dispatch, or runtime behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_CLANG = (21, 0, 0)
SOURCE_SUFFIXES = frozenset({".cpp", ".cc", ".cxx"})
HEADER_SUFFIXES = frozenset({".h", ".hpp", ".hh", ".hxx", ".ipp", ".inl", ".tpp"})
ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"build", "dist", "target", "out", ".native-build", "coverage"})
INTERNAL_DIRS = frozenset({
    ".git", ".agents", ".claude", ".engineering", ".venv", "venv",
    "__pycache__", "reports",
})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
VERSION_RE = re.compile(r"(?:Apple )?clang version\s+(\d+)\.(\d+)\.(\d+)", re.I)
RAW_COMMENT_RE = re.compile(
    r"^comment\s+'.*?'\s*(?:\[[^\]]+\]\s*)?Loc=<.*?:(\d+):(\d+)>$",
    re.M | re.S,
)
FUNCTION_KINDS = frozenset({
    "FunctionDecl", "CXXMethodDecl", "CXXConstructorDecl",
    "CXXDestructorDecl", "CXXConversionDecl",
})
CALL_KINDS = frozenset({"CallExpr", "CXXMemberCallExpr", "CXXOperatorCallExpr"})
BRANCH_KINDS = frozenset({
    "IfStmt", "ForStmt", "CXXForRangeStmt", "WhileStmt", "DoStmt",
    "SwitchStmt", "ConditionalOperator", "BinaryConditionalOperator",
})


class Terminal(Exception):
    """A fail-closed terminal state with stable status and process semantics."""

    def __init__(self, status: str, kind: str, detail: str, *, code: int = 0):
        super().__init__(detail)
        self.status = status
        self.kind = kind
        self.code = code


def add_fact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--clangxx")
    parser.add_argument("--compile-database", type=Path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def clear_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def terminal_return_code(payload: dict[str, Any], producer_code: int = 0) -> int:
    return producer_code if producer_code else (2 if payload.get("status") == "failed" else 0)


def _run(argv: list[str], cwd: Path, *, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative(path: Path, root: Path) -> str:
    return path.resolve(strict=False).relative_to(root).as_posix()


def _resolve_tool(value: str | None) -> Path | None:
    raw = value or "clang++"
    if os.sep in raw or (os.altsep and os.altsep in raw):
        path = Path(raw)
        return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None
    discovered = shutil.which(raw)
    return Path(discovered).resolve() if discovered else None


def _probe_clangxx(root: Path, requested: str | None) -> dict[str, Any]:
    clangxx = _resolve_tool(requested)
    if clangxx is None:
        raise Terminal("unsupported", "clangxx_tool_missing", "Clang++ 21+ is required.")
    result = _run([str(clangxx), "--version"], root, timeout=20)
    if result.returncode:
        raise Terminal(
            "failed", "clangxx_version_probe_failed",
            (result.stderr or result.stdout).strip() or "Clang++ version probe failed.", code=2,
        )
    match = VERSION_RE.search(result.stdout + result.stderr)
    if match is None:
        raise Terminal(
            "failed", "clangxx_version_probe_failed", "Clang++ version was not recognized.", code=2
        )
    version = tuple(map(int, match.groups()))
    if version < MINIMUM_CLANG:
        raise Terminal(
            "unsupported", "clangxx_version_too_old",
            f"Clang++ {'.'.join(match.groups())} is below 21.0.0.",
        )
    return {
        "path": str(clangxx), "version": ".".join(match.groups()),
        "minimum_version": "21.0.0", "state": "ready",
    }


def _walk_candidates(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        linked = [name for name in dirnames if (current / name).is_symlink()]
        paths.extend(current / name for name in linked)
        dirnames[:] = [
            name for name in sorted(dirnames)
            if name not in linked and name.casefold() not in INTERNAL_DIRS
        ]
        for name in sorted(filenames):
            path = current / name
            if path.suffix in ALL_SUFFIXES or path.is_symlink():
                paths.append(path)
    return paths


def _source_role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parents = {part.casefold() for part in relative.parts[:-1]}
    if path.is_symlink():
        return "symlink", "external-or-indirect-source"
    if parents & BUILD_DIRS:
        return "build", "build-output"
    if parents & VENDOR_DIRS:
        return "vendor", "vendor"
    if parents & GENERATED_DIRS or GENERATED_RE.search(text[:4096]):
        return "generated", "generated"
    if parents & TEST_DIRS:
        return "test", "test"
    return ("source", None) if path.suffix in SOURCE_SUFFIXES else ("header-candidate", None)


def _inventory(root: Path) -> tuple[list[dict[str, Any]], dict[Path, dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    readable: dict[Path, dict[str, Any]] = {}
    for path in _walk_candidates(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            inventory.append({
                "file": relative, "role": "symlink", "reason": "external-or-indirect-source"
            })
            continue
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append({
                "file": relative, "role": "failed", "reason": "read-error", "detail": str(exc)
            })
            continue
        role, reason = _source_role(path, root, text)
        row = {
            "file": relative, "role": role, "source_sha256": hash_bytes(content),
            "source_bytes": len(content), **({"reason": reason} if reason else {}),
        }
        inventory.append(row)
        readable[path.resolve()] = {**row, "path": path.resolve(), "source": content, "text": text}
    return inventory, readable


def _manifest(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        dirnames[:] = [
            name for name in sorted(dirnames)
            if name.casefold() not in INTERNAL_DIRS and name != ".native-build"
        ]
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            rows[relative] = (
                "symlink:" + os.readlink(path) if path.is_symlink() else hash_bytes(path.read_bytes())
            )
    return rows


def _manifest_hash(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _analysis_flags(arguments: list[str], source: str) -> list[str]:
    flags: list[str] = []
    skip = False
    for token in arguments[1:]:
        if skip:
            skip = False
            continue
        if token in {"-o", "-MF", "-MT", "-MQ", "--output"}:
            skip = True
            continue
        if token in {"-c", source}:
            continue
        flags.append(token)
    return flags


def _analysis_argv(entry: dict[str, Any], clangxx: Path, *extra: str) -> list[str]:
    return [
        str(clangxx), *_analysis_flags(entry["arguments"], entry["file"]),
        *extra, entry["file"],
    ]


def _language_modes(arguments: list[str]) -> list[str]:
    modes: list[str] = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            modes.append(arguments[index + 1])
        elif token.startswith("-x="):
            modes.append(token[3:])
        elif token.startswith("-x") and token != "-x":
            modes.append(token[2:])
    return modes


def _is_cpp_command(arguments: list[str], source: str, clangxx: Path) -> bool:
    if "-c" not in arguments or source not in arguments:
        return False
    standards = [token for token in arguments if token.startswith("-std=")]
    if standards != ["-std=c++20"]:
        return False
    modes = _language_modes(arguments)
    if modes and modes[-1] not in {"c++", "c++-cpp-output"}:
        return False
    return _resolve_tool(arguments[0]) == clangxx and Path(source).suffix in SOURCE_SUFFIXES


def _eligible_tus(readable: dict[Path, dict[str, Any]]) -> set[Path]:
    return {
        path for path, row in readable.items()
        if path.suffix in SOURCE_SUFFIXES and row["role"] == "source"
    }


def _parse_dependencies(text: str, root: Path, directory: Path) -> list[Path]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise ValueError("dependency output has no target separator")
    dependencies: list[Path] = []
    for raw in shlex.split(flattened.split(":", 1)[1]):
        path = Path(raw)
        path = path if path.is_absolute() else directory / path
        path = path.resolve(strict=False)
        if _inside(path, root) and path.suffix in HEADER_SUFFIXES:
            dependencies.append(path)
    return list(dict.fromkeys(dependencies))


def _load_database(
    root: Path,
    clangxx: Path,
    readable: dict[Path, dict[str, Any]],
    database: Path,
    target: Path,
) -> tuple[list[dict[str, Any]], dict[Path, list[Path]], list[Path]]:
    if not database.is_file():
        raise Terminal(
            "unsupported", "compile_database_missing",
            "A current complete C++20 compile_commands.json is required.",
        )
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal("failed", "compile_database_malformed", str(exc), code=2) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal(
            "failed", "compile_database_malformed",
            "Compilation database must be a non-empty object array.", code=2,
        )
    entries: list[dict[str, Any]] = []
    actual: set[Path] = set()
    eligible = _eligible_tus(readable)
    for row in payload:
        if not {"directory", "file"} <= set(row) or not set(row) <= {
            "directory", "file", "arguments", "command", "output"
        }:
            raise Terminal(
                "failed", "compile_database_malformed",
                "Each compile command requires directory, file, and exactly one command form.", code=2,
            )
        directory = Path(row["directory"])
        if not directory.is_absolute():
            raise Terminal(
                "unsupported", "compile_database_mismatched_directory",
                "Every compile command directory must be absolute.",
            )
        directory = directory.resolve(strict=False)
        raw_source = Path(row["file"])
        source = raw_source if raw_source.is_absolute() else directory / raw_source
        source = source.resolve(strict=False)
        if not _inside(source, root):
            raise Terminal(
                "unsupported", "compile_database_mismatched_directory",
                "Every compile command source must resolve inside the project root.",
            )
        if source.suffix not in SOURCE_SUFFIXES or source not in eligible:
            continue
        has_arguments = isinstance(row.get("arguments"), list)
        has_command = isinstance(row.get("command"), str)
        if has_arguments == has_command:
            raise Terminal(
                "failed", "compile_database_malformed",
                "Each compile command requires exactly one of arguments or command.", code=2,
            )
        arguments = list(row["arguments"]) if has_arguments else shlex.split(row["command"])
        if any(not isinstance(token, str) or not token for token in arguments):
            raise Terminal(
                "failed", "compile_database_malformed",
                "Compile-command arguments must be non-empty strings.", code=2,
            )
        raw_file = str(row["file"])
        arguments = [str(source) if token == raw_file else token for token in arguments]
        if not _is_cpp_command(arguments, str(source), clangxx):
            raise Terminal(
                "unsupported", "compile_database_non_cpp20_command",
                "Every compile command must use the selected Clang++ in explicit C++20 mode.",
            )
        if source in actual:
            raise Terminal(
                "failed", "compile_database_malformed",
                "Duplicate translation-unit entries are not allowed.", code=2,
            )
        actual.add(source)
        entries.append({"directory": str(directory), "file": str(source), "arguments": arguments})
    expected = {path for path in eligible if _selected(path, target)}
    missing = sorted(expected - actual)
    dependencies: dict[Path, list[Path]] = {}
    for entry in sorted(entries, key=lambda item: item["file"]):
        source = Path(entry["file"])
        result = _run(
            _analysis_argv(entry, clangxx, "-MM", "-MT", _relative(source, root)),
            Path(entry["directory"]),
        )
        if result.returncode:
            raise Terminal(
                "failed", "clang_dependency_failed",
                result.stderr.strip() or f"Dependency scan failed for {_relative(source, root)}.", code=2,
            )
        try:
            dependencies[source] = _parse_dependencies(
                result.stdout, root, Path(entry["directory"])
            )
        except ValueError as exc:
            raise Terminal("failed", "clang_dependency_failed", str(exc), code=2) from exc
    freshness: set[Path] = {root / "Makefile", *actual}
    for paths in dependencies.values():
        freshness.update(paths)
    existing = [path for path in freshness if path.is_file()]
    if existing and database.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in existing):
        raise Terminal(
            "partial", "compile_database_stale",
            "compile_commands.json predates a compiler-owned input.",
        )
    return sorted(entries, key=lambda item: item["file"]), dependencies, missing


def _selected(path: Path, target: Path) -> bool:
    return path == target or (target.is_dir() and _inside(path, target))


def _plain_location(location: Any) -> dict[str, Any]:
    if not isinstance(location, dict):
        return {}
    for key in ("expansionLoc", "spellingLoc"):
        if key in location:
            return _plain_location(location[key])
    return location


def _location_file(location: Any) -> str | None:
    if not isinstance(location, dict):
        return None
    if isinstance(location.get("file"), str):
        return location["file"]
    for key in ("expansionLoc", "spellingLoc"):
        nested = _location_file(location.get(key))
        if nested:
            return nested
    return None


def _node_file(node: dict[str, Any], inherited: str | None) -> str | None:
    return (
        _location_file(node.get("loc"))
        or _location_file(node.get("range", {}).get("begin"))
        or inherited
    )


def _macro_location(location: Any) -> bool:
    return isinstance(location, dict) and (
        "spellingLoc" in location or "expansionLoc" in location
    )


def _macro_node(node: dict[str, Any]) -> bool:
    return any(
        _macro_location(location)
        for location in (
            node.get("loc"), node.get("range", {}).get("begin"),
            node.get("range", {}).get("end"),
        )
    )


def _offset(location: Any) -> int | None:
    value = _plain_location(location).get("offset")
    return value if isinstance(value, int) else None


def _line_from(node: dict[str, Any], source: str, side: str) -> int | None:
    location = node.get("loc") if side == "loc" else node.get("range", {}).get(side)
    plain = _plain_location(location)
    line = plain.get("line")
    if isinstance(line, int):
        return line
    offset = plain.get("offset")
    return source.count("\n", 0, offset) + 1 if isinstance(offset, int) else None


def _span(node: dict[str, Any], source: bytes) -> dict[str, Any] | None:
    begin = _plain_location(node.get("range", {}).get("begin"))
    end = _plain_location(node.get("range", {}).get("end"))
    start, final = begin.get("offset"), end.get("offset")
    if not isinstance(start, int) or not isinstance(final, int):
        return None
    token = end.get("tokLen", 1)
    final += token if isinstance(token, int) else 1
    if start < 0 or final > len(source) or final <= start:
        return None
    start_before, end_before = source[:start], source[:final]
    return {
        "start_byte": start, "end_byte": final,
        "start": {"line": start_before.count(b"\n") + 1, "column": start - start_before.rfind(b"\n")},
        "end": {"line": end_before.count(b"\n") + 1, "column": final - end_before.rfind(b"\n")},
    }


def _scope_contexts(ast: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    contexts: dict[str, tuple[str, ...]] = {}

    def visit(node: dict[str, Any], scope: tuple[str, ...]) -> None:
        kind, name = node.get("kind"), node.get("name")
        current = scope
        if kind == "NamespaceDecl" and isinstance(name, str) and name:
            current = (*scope, name)
        elif (
            kind in {"CXXRecordDecl", "RecordDecl"}
            and isinstance(name, str) and name and not node.get("isImplicit")
        ):
            current = (*scope, name)
        identifier = node.get("id")
        if isinstance(identifier, str) and kind in {"NamespaceDecl", "CXXRecordDecl", "RecordDecl"}:
            contexts[identifier] = current
        for child in node.get("inner", []):
            if isinstance(child, dict):
                visit(child, current)

    visit(ast, ())
    return contexts


def _callee_spelling(node: dict[str, Any]) -> str | None:
    if node.get("kind") in {"DeclRefExpr", "MemberExpr", "UnresolvedLookupExpr"}:
        reference = node.get("referencedDecl", {})
        name = reference.get("name") or node.get("name")
        if isinstance(name, str):
            return name
    for child in node.get("inner", []):
        if isinstance(child, dict):
            found = _callee_spelling(child)
            if found:
                return found
    return None


def _body_facts(
    body: dict[str, Any], qualified_name: str, source: str
) -> tuple[int, int, list[dict[str, Any]]]:
    branch_score = 0
    omitted = 0
    calls: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], ancestors: tuple[str, ...]) -> None:
        nonlocal branch_score, omitted
        if node is not body and node.get("kind") in {*FUNCTION_KINDS, "LambdaExpr"}:
            return
        if _macro_node(node):
            omitted += 1
            return
        kind = node.get("kind", "")
        if kind in BRANCH_KINDS:
            branch_score += 1
        elif kind == "BinaryOperator" and node.get("opcode") in {"&&", "||"}:
            branch_score += 1
        if kind in CALL_KINDS:
            spelling = _callee_spelling(node)
            line = _line_from(node, source, "begin")
            if spelling and line is not None:
                calls.append({
                    "spelling": spelling, "line": line, "function": qualified_name,
                    "enclosures": ["if"] if "IfStmt" in ancestors else [],
                    "evidence_scope": "direct-call-spelling-syntax-only",
                })
        child_ancestors = (*ancestors, kind)
        for child in node.get("inner", []):
            if isinstance(child, dict):
                visit(child, child_ancestors)

    visit(body, ())
    return branch_score, omitted, calls


def _ast_facts(
    ast: dict[str, Any],
    root: Path,
    selected_files: set[str],
    readable: dict[Path, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contexts = _scope_contexts(ast)
    declarations: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    def visit(
        node: dict[str, Any],
        inherited_file: str | None,
        scope: tuple[str, ...],
        template_depth: int,
    ) -> None:
        current_file = _node_file(node, inherited_file)
        kind, name = node.get("kind"), node.get("name")
        current_scope = scope
        child_template_depth = template_depth
        if kind == "NamespaceDecl" and isinstance(name, str) and name:
            current_scope = (*scope, name)
        elif (
            kind in {"CXXRecordDecl", "RecordDecl"}
            and isinstance(name, str) and name and not node.get("isImplicit")
        ):
            current_scope = (*scope, name)
        elif kind in {"FunctionTemplateDecl", "ClassTemplateDecl"}:
            child_template_depth += 1

        if kind in FUNCTION_KINDS and isinstance(name, str) and not node.get("isImplicit"):
            if current_file is not None:
                path = Path(current_file).resolve(strict=False)
                if _inside(path, root):
                    relative = _relative(path, root)
                    if relative in selected_files and path in readable:
                        parent = node.get("parentDeclContextId")
                        declaring_scope = contexts.get(parent, scope) if isinstance(parent, str) else scope
                        qualified_name = "::".join((*declaring_scope, name)) if declaring_scope else name
                        source_bytes = readable[path]["source"]
                        source_text = readable[path]["text"]
                        location = _span(node, source_bytes)
                        signature = node.get("type", {}).get("qualType", "unavailable")
                        line = _line_from(node, source_text, "loc") or _line_from(node, source_text, "begin")
                        if location is not None and line is not None:
                            declaration = {
                                "name": name, "qualified_name": qualified_name,
                                "namespace": "::".join(declaring_scope[:-1] if declaring_scope else ()),
                                "kind": kind, "signature": signature,
                                "template": template_depth > 0, "template_depth": template_depth,
                                "operator": name.startswith("operator"), "line": line,
                                "span": location, "source_sha256": readable[path]["source_sha256"],
                                "spelling_sha256": hash_bytes(
                                    source_bytes[location["start_byte"] : location["end_byte"]]
                                ),
                                "file": relative,
                            }
                            declarations.append(declaration)
                            body = next(
                                (
                                    child for child in node.get("inner", [])
                                    if isinstance(child, dict) and child.get("kind") in {"CompoundStmt", "CXXTryStmt"}
                                ),
                                None,
                            )
                            if body is not None:
                                body_span = _span(body, source_bytes)
                                if body_span is not None:
                                    spelling = source_bytes[
                                        body_span["start_byte"] : body_span["end_byte"]
                                    ]
                                    normalized = re.sub(rb"\s+", b" ", spelling.strip())
                                    score, macro_omitted, body_calls = _body_facts(
                                        body, qualified_name, source_text
                                    )
                                    functions.append({
                                        **declaration,
                                        "body_span": body_span,
                                        "end_line": body_span["end"]["line"],
                                        "loc": body_span["end"]["line"] - line + 1,
                                        "branch_score": score,
                                        "macro_nodes_omitted": macro_omitted,
                                        "normalized_body_sha256": hash_bytes(normalized),
                                        "evidence_scope": "direct-body-c++-syntax-only",
                                    })
                                    calls.extend({"file": relative, **call} for call in body_calls)
        for child in node.get("inner", []):
            if isinstance(child, dict):
                visit(child, current_file, current_scope, child_template_depth)

    visit(ast, None, (), 0)
    return declarations, functions, calls


def _raw_command(clangxx: Path, entry: dict[str, Any], path: Path) -> list[str]:
    language = "c++" if path.suffix in SOURCE_SUFFIXES else "c++-header"
    return [
        str(clangxx), *_analysis_flags(entry["arguments"], entry["file"]),
        "-x", language, "-fsyntax-only", "-Xclang", "-dump-raw-tokens", str(path),
    ]


def _comment_span(source: bytes, line: int, column: int) -> tuple[int, int] | None:
    lines = source.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        return None
    start = sum(len(item) for item in lines[: line - 1]) + column - 1
    if source[start : start + 2] == b"//":
        newline = source.find(b"\n", start)
        return start, len(source) if newline < 0 else newline
    if source[start : start + 2] == b"/*":
        close = source.find(b"*/", start + 2)
        return None if close < 0 else (start, close + 2)
    return None


def _comments(path: Path, raw: str) -> list[dict[str, Any]]:
    source = path.read_bytes()
    rows: list[dict[str, Any]] = []
    for match in RAW_COMMENT_RE.finditer(raw):
        line, column = map(int, match.groups())
        span = _comment_span(source, line, column)
        if span is None:
            continue
        start, end = span
        spelling = source[start:end].decode("utf-8")
        rows.append({
            "text": spelling, "form": "line" if spelling.startswith("//") else "block",
            "line": line, "start_byte": start, "end_byte": end,
            "spelling_sha256": hash_bytes(source[start:end]),
        })
    return rows


def _dedupe(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        unique[key] = row
    return sorted(unique.values(), key=lambda row: tuple(row[field] for field in fields))


def _payload(
    *,
    status: str,
    kind: str,
    detail: str,
    root: Path,
    target: Path,
    before: dict[str, str],
    after: dict[str, str],
    inventory: list[dict[str, Any]],
    tool: dict[str, Any] | None = None,
    database: dict[str, Any] | None = None,
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "language": "cpp",
        "analyzer": "clang++-c++20-raw-tokens+recursive-ast-json",
        "status": status,
        "failure_kind": kind,
        "detail": detail,
        "project_root": str(root),
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "syntax_standard": "c++20",
        "translation_unit_suffixes": sorted(SOURCE_SUFFIXES),
        "header_suffixes": sorted(HEADER_SUFFIXES),
        "claim_boundary": (
            "advisory direct-spelling and recursive AST syntax for the exact C++20 "
            "compile-command snapshot"
        ),
        "boundaries": {
            "header_ownership": "compile-command dependency closure only",
            "odr": "not proven",
            "abi": "not analyzed",
        },
        "limits": [
            "namespace and declaring-class names plus spelled signatures distinguish overload leads, not canonical USRs",
            "templates are declaration spelling only; instantiations, specializations, constraints, SFINAE, and ODR are not complete",
            "inline/header definitions are observed source spellings; ODR consistency and link selection are not proven",
            "ABI, object layout, mangling compatibility, visibility, and binary boundaries are not analyzed",
            "virtual and dynamic dispatch, callbacks, reflection, plugins, and runtime call targets are unresolved",
            "macro meaning, inactive branches, generated compiler code, and build variants outside the database are unresolved",
            "exact normalized body spelling is not semantic or behavioral equivalence",
            "filename clusters do not authorize a move or endorse a project layout",
        ],
        "tool": tool or {},
        "compile_database": database or {"state": "not-evaluated"},
        "inventory": inventory,
        "files": files or [],
        "source_manifest": {
            "before_sha256": _manifest_hash(before),
            "after_sha256": _manifest_hash(after),
            "preserved": before == after,
            "changed": sorted(path for path in before.keys() & after.keys() if before[path] != after[path]),
            "missing": sorted(before.keys() - after.keys()),
            "unexpected": sorted(after.keys() - before.keys()),
        },
    }


def produce(
    project_root: Path,
    target: Path,
    *,
    clangxx: str | None = None,
    compile_database: Path | None = None,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve()
    target = target if target.is_absolute() else root / target
    target = Path(os.path.abspath(target))
    if not root.is_dir() or not target.exists() or not _inside(target, root):
        return {
            "schema_version": 1, "language": "cpp",
            "analyzer": "clang++-c++20-raw-tokens+recursive-ast-json",
            "status": "failed", "failure_kind": "invalid_project_or_target",
            "inventory": [], "files": [], "source_manifest": {"preserved": True},
        }, 2
    before = _manifest(root)
    inventory, readable = _inventory(root)
    tool: dict[str, Any] = {}
    try:
        tool = _probe_clangxx(root, clangxx)
        clangxx_path = Path(tool["path"])
        database_path = (
            compile_database.resolve()
            if compile_database is not None
            else root / "compile_commands.json"
        )
        entries, dependencies, missing_tus = _load_database(
            root, clangxx_path, readable, database_path, target
        )
        owned = {Path(entry["file"]) for entry in entries}
        for paths in dependencies.values():
            owned.update(paths)
        for row in inventory:
            path = root / row["file"]
            if row["role"] == "header-candidate":
                if path.resolve() in owned:
                    row["role"] = "header"
                    row["compiler_owned"] = True
                else:
                    row["role"] = "ambiguous-header"
                    row["reason"] = "not-in-compile-command-dependency-closure"
                    row["compiler_owned"] = False
            elif row["role"] == "source":
                row["compiler_owned"] = path.resolve() in owned
        selected_paths = sorted(path for path in owned if _selected(path, target))
        if not selected_paths:
            raise Terminal(
                "unsupported", "target_has_no_compile_owned_cpp_files",
                "Target contains no compile-owned first-party C++ source.",
            )
        selected_relative = {_relative(path, root) for path in selected_paths}
        declarations: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []
        for entry in entries:
            source = Path(entry["file"])
            if source not in selected_paths and not any(
                dependency in selected_paths for dependency in dependencies[source]
            ):
                continue
            result = _run(
                _analysis_argv(entry, clangxx_path, "-Xclang", "-ast-dump=json", "-fsyntax-only"),
                Path(entry["directory"]),
            )
            if result.returncode:
                raise Terminal(
                    "failed", "clang_ast_failed",
                    result.stderr.strip() or f"Clang AST failed for {_relative(source, root)}.", code=2,
                )
            try:
                ast = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise Terminal("failed", "clang_ast_malformed", str(exc), code=2) from exc
            ast_declarations, ast_functions, ast_calls = _ast_facts(
                ast, root, selected_relative, readable
            )
            declarations.extend(ast_declarations)
            functions.extend(ast_functions)
            calls.extend(ast_calls)
        declarations = _dedupe(
            declarations, ("file", "qualified_name", "signature", "line", "kind")
        )
        functions = _dedupe(
            functions, ("file", "qualified_name", "signature", "line", "kind")
        )
        calls = _dedupe(calls, ("file", "function", "line", "spelling"))
        facts_by_file = {
            relative: {
                "file": relative, "source_sha256": readable[path]["source_sha256"],
                "comments": [], "declarations": [], "functions": [], "calls": [],
            }
            for path in selected_paths
            if path in readable and (relative := _relative(path, root))
        }
        for declaration in declarations:
            facts_by_file[declaration["file"]]["declarations"].append(
                {key: value for key, value in declaration.items() if key != "file"}
            )
        for function in functions:
            facts_by_file[function["file"]]["functions"].append(
                {key: value for key, value in function.items() if key != "file"}
            )
        for call in calls:
            facts_by_file[call["file"]]["calls"].append(
                {key: value for key, value in call.items() if key != "file"}
            )
        for path in selected_paths:
            entry = next(
                (
                    candidate for candidate in entries
                    if Path(candidate["file"]) == path
                    or path in dependencies[Path(candidate["file"])]
                ),
                None,
            )
            if entry is None:
                raise Terminal(
                    "failed", "compile_database_ownership_failed",
                    f"No compile command owns {_relative(path, root)}.", code=2,
                )
            raw = _run(
                _raw_command(clangxx_path, entry, path), Path(entry["directory"])
            )
            raw_text = raw.stdout + raw.stderr
            if raw.returncode or not raw_text.strip():
                raise Terminal(
                    "failed", "clang_raw_tokens_failed",
                    (raw.stderr or raw.stdout).strip() or f"Raw tokens failed for {_relative(path, root)}.",
                    code=2,
                )
            facts_by_file[_relative(path, root)]["comments"] = _comments(path, raw_text)
        files = [facts_by_file[path] for path in sorted(facts_by_file)]
        after = _manifest(root)
        if before != after:
            raise Terminal(
                "failed", "source_mutated", "Project fingerprints changed during analysis.", code=2
            )
        return _payload(
            status="partial" if missing_tus else "complete",
            kind="compile_database_incomplete" if missing_tus else "none",
            detail=(
                "Useful syntax facts were produced, but the compilation database "
                "does not cover every first-party C++ translation unit in the target."
                if missing_tus
                else "Complete for the exact current C++20 compile-command snapshot."
            ),
            root=root, target=target, before=before, after=after, inventory=inventory,
            tool=tool,
            database={
                "path": (
                    "compile_commands.json"
                    if database_path == root / "compile_commands.json"
                    else str(database_path)
                ),
                "state": (
                    "valid-current-partial-target-c++20-mode"
                    if missing_tus
                    else "valid-current-complete-c++20-mode"
                ),
                "entries": len(entries),
                "translation_units": [_relative(Path(entry["file"]), root) for entry in entries],
                "missing_target_translation_units": [
                    _relative(path, root) for path in missing_tus
                ],
                "owned_headers": sorted({
                    _relative(path, root) for paths in dependencies.values() for path in paths
                }),
                "ownership_edges": [
                    {
                        "translation_unit": _relative(source, root),
                        "headers": sorted(_relative(path, root) for path in paths),
                    }
                    for source, paths in sorted(dependencies.items())
                ],
            },
            files=files,
        ), 0
    except Terminal as terminal:
        after = _manifest(root)
        return _payload(
            status=terminal.status, kind=terminal.kind, detail=str(terminal),
            root=root, target=target, before=before, after=after,
            inventory=inventory, tool=tool,
        ), terminal.code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    add_fact_arguments(parser)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root,
        args.target,
        clangxx=args.clangxx,
        compile_database=args.compile_database,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
