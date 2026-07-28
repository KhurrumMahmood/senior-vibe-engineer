#!/usr/bin/env python3
"""Produce bounded C17 syntax facts from Clang raw tokens and AST JSON.

The producer is intentionally C-local. It accepts only an exact, current,
complete C17 compilation database, inventories compiler-owned source, and
emits the four facts needed by the C syntax cohort: real comments, function
spans, direct-body branch counts, and direct spelled calls. Macro-origin AST
subtrees are omitted. These are advisory syntax facts, never runtime claims.
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
from pathlib import Path
from typing import Any, Iterable


MINIMUM_CLANG = (21, 0, 0)
SOURCE_SUFFIXES = frozenset({".c", ".i"})
HEADER_SUFFIXES = frozenset({".h", ".inc"})
ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party", "deps"})
BUILD_DIRS = frozenset({"build", "dist", "target", "out", ".native-build", "coverage", "reports"})
INTERNAL_DIRS = frozenset({".git", ".agents", ".claude", ".engineering", ".venv", "venv", "__pycache__"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
VERSION_RE = re.compile(r"(?:Apple )?clang version\s+(\d+)\.(\d+)\.(\d+)", re.I)
RAW_COMMENT_RE = re.compile(
    r"^comment\s+'.*?'\s*(?:\[[^\]]+\]\s*)?Loc=<.*?:(\d+):(\d+)>$",
    re.M | re.S,
)
BRANCH_KINDS = frozenset({
    "IfStmt", "ForStmt", "WhileStmt", "DoStmt", "SwitchStmt",
    "ConditionalOperator", "BinaryConditionalOperator",
})
CALLEE_WRAPPERS = frozenset({
    "ImplicitCastExpr", "ParenExpr", "UnaryOperator", "CStyleCastExpr",
})


class Terminal(Exception):
    """Bounded terminal result with a stable report status."""

    def __init__(self, status: str, kind: str, detail: str, *, code: int = 0):
        super().__init__(detail)
        self.status = status
        self.kind = kind
        self.code = code


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(argv: list[str], cwd: Path, *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
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
    raw = value or "clang"
    if os.sep in raw or (os.altsep and os.altsep in raw):
        path = Path(raw)
        return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None
    discovered = shutil.which(raw)
    return Path(discovered).resolve() if discovered else None


def _probe_clang(root: Path, requested: str | None) -> dict[str, Any]:
    clang = _resolve_tool(requested)
    if clang is None:
        raise Terminal("unsupported", "clang_tool_missing", "Clang 21+ is required.")
    result = _run([str(clang), "--version"], root, timeout=20)
    if result.returncode != 0:
        raise Terminal(
            "failed",
            "clang_version_probe_failed",
            (result.stderr or result.stdout).strip() or "Clang version probe failed.",
            code=2,
        )
    match = VERSION_RE.search(result.stdout + result.stderr)
    if match is None:
        raise Terminal(
            "failed",
            "clang_version_probe_failed",
            "Clang version output was not recognized.",
            code=2,
        )
    version = tuple(map(int, match.groups()))
    if version < MINIMUM_CLANG:
        raise Terminal(
            "unsupported",
            "clang_version_too_old",
            f"Clang {'.'.join(match.groups())} is below 21.0.0.",
        )
    return {
        "path": str(clang),
        "version": ".".join(match.groups()),
        "minimum_version": "21.0.0",
        "state": "ready",
    }


def _walk_candidates(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if name not in INTERNAL_DIRS and name not in BUILD_DIRS
        ]
        for name in sorted(filenames):
            path = current / name
            if path.suffix.casefold() in ALL_SUFFIXES or path.is_symlink():
                paths.append(path)
    return paths


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
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
    return "source", None


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
        role, reason = _role(path, root, text)
        row = {
            "file": relative,
            "role": role,
            "source_sha256": _hash_bytes(content),
            "source_bytes": len(content),
            **({"reason": reason} if reason else {}),
        }
        inventory.append(row)
        readable[path.resolve()] = {**row, "path": path.resolve(), "text": text}
    return inventory, readable


def _manifest(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if name not in {".git", "reports", ".native-build", "__pycache__"}
        ]
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                rows[relative] = "symlink:" + os.readlink(path)
            else:
                rows[relative] = _hash_bytes(path.read_bytes())
        for name in sorted(set(os.listdir(current)) - set(dirnames) - set(filenames)):
            path = current / name
            if path.is_symlink():
                rows[path.relative_to(root).as_posix()] = "symlink:" + os.readlink(path)
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


def _analysis_argv(entry: dict[str, Any], clang: Path, *extra: str) -> list[str]:
    return [
        str(clang),
        *_analysis_flags(entry["arguments"], entry["file"]),
        *extra,
        entry["file"],
    ]


def _is_c_command(arguments: list[str], source: str) -> bool:
    if "-c" not in arguments or "-std=c17" not in arguments or source not in arguments:
        return False
    for index, token in enumerate(arguments):
        language = token[3:] if token.startswith("-x=") else None
        if token == "-x" and index + 1 < len(arguments):
            language = arguments[index + 1]
        if language and language not in {"c", "cpp-output", "c-cpp-output"}:
            return False
        if token.startswith("-std=") and token != "-std=c17":
            return False
    return Path(source).suffix.casefold() in SOURCE_SUFFIXES


def _eligible_tus(root: Path, readable: dict[Path, dict[str, Any]]) -> set[Path]:
    return {
        path
        for path, row in readable.items()
        if path.suffix.casefold() in SOURCE_SUFFIXES and row["role"] == "source"
    }


def _parse_dependencies(text: str, root: Path, source: Path) -> list[Path]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise ValueError("dependency output has no target separator")
    result: list[Path] = []
    for item in shlex.split(flattened.split(":", 1)[1]):
        path = Path(item)
        path = path if path.is_absolute() else source.parent / path
        path = path.resolve(strict=False)
        if path != source and _inside(path, root) and path.suffix.casefold() in HEADER_SUFFIXES:
            result.append(path)
    return list(dict.fromkeys(result))


def _load_database(
    root: Path,
    clang: Path,
    readable: dict[Path, dict[str, Any]],
    database: Path,
    target: Path,
) -> tuple[list[dict[str, Any]], dict[Path, list[Path]], list[Path]]:
    if not database.is_file():
        raise Terminal(
            "unsupported", "compile_database_missing",
            "A current, complete C17 compile_commands.json is required.",
        )
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal(
            "failed", "compile_database_malformed", str(exc), code=2
        ) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal(
            "failed", "compile_database_malformed",
            "Compilation database must be a non-empty JSON object array.", code=2,
        )
    entries: list[dict[str, Any]] = []
    actual: set[Path] = set()
    eligible = _eligible_tus(root, readable)
    for row in payload:
        if not {"directory", "file"} <= set(row) or not set(row) <= {
            "directory", "file", "arguments", "command", "output"
        }:
            raise Terminal(
                "failed", "compile_database_malformed",
                "Each compile command requires directory, file, and exactly one command form.",
                code=2,
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
        if source.suffix.casefold() not in SOURCE_SUFFIXES or source not in eligible:
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
        if not _is_c_command(arguments, str(source)):
            raise Terminal(
                "unsupported", "compile_database_non_c_command",
                "Every compile command must be explicit C17 mode.",
            )
        compiler = _resolve_tool(arguments[0])
        if compiler is None or compiler != clang:
            raise Terminal(
                "unsupported", "compile_database_non_c_command",
                "Every compile command must use the version-gated Clang executable.",
            )
        if source in actual:
            raise Terminal(
                "failed", "compile_database_malformed",
                "Duplicate translation-unit entries are not allowed.", code=2,
            )
        actual.add(source)
        entries.append({
            "directory": str(directory), "file": str(source), "arguments": arguments
        })
    expected = {path for path in eligible if _selected(path, target)}
    missing = sorted(expected - actual)
    dependencies: dict[Path, list[Path]] = {}
    for entry in sorted(entries, key=lambda item: item["file"]):
        source = Path(entry["file"])
        result = _run(
            _analysis_argv(entry, clang, "-MM", "-MT", _relative(source, root)),
            Path(entry["directory"]),
        )
        if result.returncode != 0:
            raise Terminal(
                "failed", "clang_dependency_failed",
                result.stderr.strip() or f"Dependency scan failed for {_relative(source, root)}.",
                code=2,
            )
        try:
            dependencies[source] = _parse_dependencies(result.stdout, root, source)
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


def _macro_location(location: Any) -> bool:
    return isinstance(location, dict) and (
        "spellingLoc" in location or "expansionLoc" in location
    )


def _macro_node(node: dict[str, Any]) -> bool:
    locations = [node.get("loc"), node.get("range", {}).get("begin"), node.get("range", {}).get("end")]
    return any(_macro_location(location) for location in locations)


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


def _node_file(node: dict[str, Any], current: str | None) -> str | None:
    return (
        _location_file(node.get("loc"))
        or _location_file(node.get("range", {}).get("begin"))
        or current
    )


def _plain_location(location: Any) -> dict[str, Any]:
    if not isinstance(location, dict):
        return {}
    if "expansionLoc" in location:
        return _plain_location(location["expansionLoc"])
    if "spellingLoc" in location:
        return _plain_location(location["spellingLoc"])
    return location


def _line(node: dict[str, Any], side: str = "begin") -> int | None:
    location = node.get("loc") if side == "loc" else node.get("range", {}).get(side)
    value = _plain_location(location).get("line")
    return value if isinstance(value, int) else None


def _source_line(node: dict[str, Any], source: str, side: str = "begin") -> int | None:
    explicit = _line(node, side)
    if explicit is not None:
        return explicit
    location = node.get("loc") if side == "loc" else node.get("range", {}).get(side)
    offset = _plain_location(location).get("offset")
    return source.count("\n", 0, offset) + 1 if isinstance(offset, int) else None


def _direct_callee(node: dict[str, Any]) -> str | None:
    inner = node.get("inner", [])
    if not inner:
        return None
    current = inner[0]
    while current.get("kind") in CALLEE_WRAPPERS and len(current.get("inner", [])) == 1:
        current = current["inner"][0]
    reference = current.get("referencedDecl", {})
    if current.get("kind") != "DeclRefExpr" or reference.get("kind") != "FunctionDecl":
        return None
    name = reference.get("name")
    return name if isinstance(name, str) else None


def _body_facts(
    body: dict[str, Any], function: str, source: str
) -> tuple[int, int, list[dict[str, Any]]]:
    score = 0
    omitted = 0
    calls: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], ancestors: tuple[str, ...]) -> None:
        nonlocal score, omitted
        if node is not body and node.get("kind") == "FunctionDecl":
            return
        if _macro_node(node):
            omitted += 1
            return
        kind = node.get("kind", "")
        if kind in BRANCH_KINDS:
            score += 1
        elif kind == "BinaryOperator" and node.get("opcode") in {"&&", "||"}:
            score += 1
        if kind == "CallExpr":
            spelling = _direct_callee(node)
            line = _source_line(node, source)
            if spelling and line is not None:
                calls.append({
                    "spelling": spelling,
                    "line": line,
                    "function": function,
                    "enclosures": ["if"] if "IfStmt" in ancestors else [],
                    "evidence_scope": "direct-call-spelling-syntax-only",
                })
        child_ancestors = (*ancestors, kind)
        for child in node.get("inner", []):
            if isinstance(child, dict):
                visit(child, child_ancestors)

    visit(body, ())
    return score, omitted, calls


def _ast_facts(
    ast: dict[str, Any], root: Path, selected_files: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    functions: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    current_file: str | None = None
    for node in ast.get("inner", []):
        if not isinstance(node, dict):
            continue
        current_file = _node_file(node, current_file)
        if node.get("kind") != "FunctionDecl" or node.get("isImplicit") or _macro_node(node):
            continue
        body = next(
            (child for child in node.get("inner", []) if child.get("kind") == "CompoundStmt"),
            None,
        )
        if body is None or current_file is None:
            continue
        path = Path(current_file).resolve(strict=False)
        if not _inside(path, root):
            continue
        relative = _relative(path, root)
        if relative not in selected_files:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        start_line = _source_line(node, source, "loc") or _source_line(node, source)
        end_line = _source_line(node, source, "end")
        name = node.get("name")
        if not isinstance(name, str) or start_line is None or end_line is None:
            continue
        branch_score, omitted, function_calls = _body_facts(body, name, source)
        functions.append({
            "file": relative,
            "name": name,
            "kind": "function",
            "line": start_line,
            "end_line": end_line,
            "loc": end_line - start_line + 1,
            "branch_score": branch_score,
            "macro_nodes_omitted": omitted,
            "evidence_scope": "direct-body-syntax-only",
        })
        calls.extend({"file": relative, **call} for call in function_calls)
    return functions, calls


def _raw_command(clang: Path, entry: dict[str, Any], path: Path) -> list[str]:
    language = "c-cpp-output" if path.suffix.casefold() == ".i" else "c-header" if path.suffix.casefold() in HEADER_SUFFIXES else "c"
    return [
        str(clang),
        *_analysis_flags(entry["arguments"], entry["file"]),
        "-x",
        language,
        "-fsyntax-only",
        "-Xclang",
        "-dump-raw-tokens",
        str(path),
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
            "text": spelling,
            "form": "line" if spelling.startswith("//") else "block",
            "line": line,
            "start_byte": start,
            "end_byte": end,
            "spelling_sha256": _hash_bytes(source[start:end]),
        })
    return rows


def _terminal_payload(
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
        "language": "c",
        "analyzer": "clang-c17-raw-tokens+ast-json",
        "status": status,
        "failure_kind": kind,
        "detail": detail,
        "project_root": str(root),
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "syntax_standard": "c17",
        "claim_boundary": (
            "advisory raw-comment and direct-body AST syntax for the exact compile-command "
            "snapshot; no macro meaning, inactive-branch completeness, call identity, "
            "runtime control flow, performance, or behavior"
        ),
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
    clang: str | None = None,
    compile_database: Path | None = None,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve()
    target = target if target.is_absolute() else root / target
    target = Path(os.path.abspath(target))
    if not root.is_dir() or not target.exists() or not _inside(target, root):
        payload = {
            "schema_version": 1,
            "language": "c",
            "analyzer": "clang-c17-raw-tokens+ast-json",
            "status": "failed",
            "failure_kind": "invalid_project_or_target",
            "inventory": [],
            "files": [],
            "source_manifest": {"preserved": True},
        }
        return payload, 2
    before = _manifest(root)
    inventory, readable = _inventory(root)
    tool: dict[str, Any] = {}
    try:
        tool = _probe_clang(root, clang)
        clang_path = Path(tool["path"])
        database_path = (
            compile_database.resolve()
            if compile_database is not None
            else root / "compile_commands.json"
        )
        entries, dependencies, missing_tus = _load_database(
            root, clang_path, readable, database_path, target
        )
        owned = {Path(entry["file"]) for entry in entries}
        for paths in dependencies.values():
            owned.update(paths)
        selected_paths = sorted(path for path in owned if _selected(path, target))
        if not selected_paths:
            raise Terminal(
                "unsupported", "target_has_no_compile_owned_c_files",
                "Target contains no compile-owned first-party C source.",
            )
        selected_relative = {_relative(path, root) for path in selected_paths}
        facts_by_file = {
            relative: {
                "file": relative,
                "source_sha256": readable[path]["source_sha256"],
                "comments": [],
                "functions": [],
                "calls": [],
            }
            for path in selected_paths
            if (relative := _relative(path, root)) and path in readable
        }
        for entry in entries:
            source = Path(entry["file"])
            relevant = source in selected_paths or any(
                dependency in selected_paths for dependency in dependencies[source]
            )
            if not relevant:
                continue
            result = _run(
                _analysis_argv(
                    entry, clang_path, "-Xclang", "-ast-dump=json", "-fsyntax-only"
                ),
                Path(entry["directory"]),
            )
            if result.returncode != 0:
                raise Terminal(
                    "failed", "clang_ast_failed",
                    result.stderr.strip() or f"Clang AST failed for {_relative(source, root)}.",
                    code=2,
                )
            try:
                ast = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise Terminal("failed", "clang_ast_malformed", str(exc), code=2) from exc
            functions, calls = _ast_facts(ast, root, selected_relative)
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
                    candidate
                    for candidate in entries
                    if Path(candidate["file"]) == path or path in dependencies[Path(candidate["file"])]
                ),
                None,
            )
            if entry is None:
                raise Terminal(
                    "failed", "compile_database_ownership_failed",
                    f"No compile command owns {_relative(path, root)}.", code=2,
                )
            raw = _run(_raw_command(clang_path, entry, path), Path(entry["directory"]))
            raw_text = raw.stdout + raw.stderr
            if raw.returncode != 0 or not raw_text.strip():
                raise Terminal(
                    "failed", "clang_raw_tokens_failed",
                    (raw.stderr or raw.stdout).strip() or f"Raw tokens failed for {_relative(path, root)}.",
                    code=2,
                )
            facts_by_file[_relative(path, root)]["comments"] = _comments(path, raw_text)
        files = []
        for _path, row in sorted(facts_by_file.items()):
            row["functions"].sort(key=lambda item: (item["line"], item["name"]))
            row["calls"].sort(key=lambda item: (item["line"], item["spelling"]))
            files.append(row)
        after = _manifest(root)
        if before != after:
            raise Terminal(
                "failed", "source_mutated",
                "Project fingerprints changed during read-only C analysis.", code=2,
            )
        payload = _terminal_payload(
            status="partial" if missing_tus else "complete",
            kind="compile_database_incomplete" if missing_tus else "none",
            detail=(
                "Useful syntax facts were produced, but the compilation database "
                "does not cover every first-party C translation unit in the target."
                if missing_tus
                else "Complete for the exact current C17 compile-command snapshot."
            ),
            root=root,
            target=target,
            before=before,
            after=after,
            inventory=inventory,
            tool=tool,
            database={
                "path": (
                    "compile_commands.json"
                    if database_path == root / "compile_commands.json"
                    else str(database_path)
                ),
                "state": (
                    "valid-current-partial-target-c-mode"
                    if missing_tus
                    else "valid-current-complete-c-mode"
                ),
                "entries": len(entries),
                "translation_units": [_relative(Path(entry["file"]), root) for entry in entries],
                "missing_target_translation_units": [
                    _relative(path, root) for path in missing_tus
                ],
                "owned_headers": sorted(
                    _relative(path, root)
                    for paths in dependencies.values()
                    for path in paths
                ),
            },
            files=files,
        )
        return payload, 0
    except Terminal as terminal:
        after = _manifest(root)
        payload = _terminal_payload(
            status=terminal.status,
            kind=terminal.kind,
            detail=str(terminal),
            root=root,
            target=target,
            before=before,
            after=after,
            inventory=inventory,
            tool=tool,
        )
        return payload, terminal.code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--clang")
    parser.add_argument("--compile-database", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root,
        args.target,
        clang=args.clang,
        compile_database=args.compile_database,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
