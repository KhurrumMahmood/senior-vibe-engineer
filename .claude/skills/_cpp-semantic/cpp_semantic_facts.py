#!/usr/bin/env python3
"""Collect bounded C++20 compile-database and Clang semantic facts."""

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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "cpp-semantic-facts-v1"
SOURCE_SUFFIXES = frozenset({".cc", ".cpp", ".cxx", ".c++", ".C", ".ii"})
HEADER_SUFFIXES = frozenset({".hpp", ".hh", ".hxx", ".h++", ".ipp", ".inl", ".tpp"})
AMBIGUOUS_HEADER_SUFFIXES = frozenset({".h", ".inc"})
ALL_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES | AMBIGUOUS_HEADER_SUFFIXES
INTERNAL_PARTS = frozenset({".agents", ".claude", ".engineering", ".git", "reports"})
LIMITS = [
    "complete only for the exact current C++20 compile_commands.json snapshot and compiler-owned dependency closure",
    "overload resolution is reported per compiler-resolved declaration; overload sets are never collapsed by spelling",
    "templates are reported only for observed definitions and instantiations; uninstantiated or alternate specializations remain unresolved",
    "operators, virtual dispatch, ADL, function pointers, callbacks, dynamic registration, and external consumers remain review boundaries",
    "macros, inactive preprocessor variants, generated sources, vendor sources, tests, alternate build variants, modules, Objective-C++, and CUDA are excluded",
    "linkage facts do not prove reachability; ODR, ABI, layout, calling convention, symbol visibility, lifetime, aliasing, concurrency, UB, and whole-program behavior remain unresolved",
]


class Terminal(Exception):
    """A terminal fact-pack state with stable status and failure kind."""

    def __init__(self, status: str, kind: str, message: str):
        super().__init__(message)
        self.status = status
        self.kind = kind


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _run(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=root, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root).as_posix()


def _role(relative: str) -> str:
    parts = {part.lower() for part in Path(relative).parts}
    if parts & {"test", "tests", "testdata", "fixtures"}:
        return "test"
    if parts & {"generated", "gen"}:
        return "generated"
    if "vendor" in parts:
        return "vendor"
    if parts & {"build", ".native-build", "dist", "out"}:
        return "build"
    return "production"


def _candidate_paths(root: Path) -> list[Path]:
    paths = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in INTERNAL_PARTS for part in relative.parts):
            continue
        if (path.is_file() or path.is_symlink()) and path.suffix in ALL_SUFFIXES:
            paths.append(path)
    return sorted(paths)


def eligible_translation_units(root: Path) -> list[Path]:
    return [
        path.resolve()
        for path in _candidate_paths(root)
        if path.suffix in SOURCE_SUFFIXES
        and not path.is_symlink()
        and _role(path.relative_to(root).as_posix()) == "production"
    ]


def source_manifest(root: Path) -> tuple[str, list[dict[str, str]]]:
    rows = []
    for path in _candidate_paths(root):
        digest = (
            f"symlink:{os.readlink(path)}"
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        rows.append({"path": path.relative_to(root).as_posix(), "sha256": digest})
    return _hash(rows), rows


def _resolve_tool(value: str) -> str | None:
    if "/" in value:
        path = Path(value)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(value)


def _version(tool: str, root: Path) -> tuple[tuple[int, int, int] | None, str]:
    result = _run([tool, "--version"], root)
    text = (result.stdout + result.stderr).strip()
    match = re.search(
        r"(?:Apple\s+)?clang\s+version\s+(\d+)\.(\d+)(?:\.(\d+))?", text, re.I
    )
    if result.returncode or match is None:
        return None, text or "clang++ version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _mode(arguments: list[str]) -> str | None:
    values = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            values.append(arguments[index + 1])
        elif token.startswith("-x="):
            values.append(token[3:])
        elif token.startswith("-x") and token != "-x":
            values.append(token[2:])
    return values[-1] if values else None


def _is_cpp20(arguments: list[str], source: str) -> bool:
    standards = [token for token in arguments if token.startswith("-std=")]
    mode = _mode(arguments)
    return (
        bool(arguments)
        and "-c" in arguments
        and source in arguments
        and standards
        and standards[-1] == "-std=c++20"
        and mode in {None, "c++", "c++-cpp-output"}
        and Path(source).suffix in SOURCE_SUFFIXES
    )


def analysis_argv(entry: dict[str, Any], clangxx: str, *extra: str) -> list[str]:
    source = entry["file"]
    filtered = []
    skip = False
    for token in entry["arguments"][1:]:
        if skip:
            skip = False
            continue
        if token in {"-o", "-MF", "-MT", "-MQ", "--output"}:
            skip = True
            continue
        if token in {"-c", source}:
            continue
        filtered.append(token)
    return [clangxx, *filtered, *extra, source]


def _dependencies(text: str, root: Path, source: Path) -> list[str]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise Terminal("failed", "clang_dependency_failed", "dependency output has no target")
    rows = []
    for token in shlex.split(flattened.split(":", 1)[1]):
        path = Path(token)
        path = path if path.is_absolute() else source.parent / path
        path = path.resolve(strict=False)
        if path == source or not _inside(path, root) or path.suffix not in ALL_SUFFIXES:
            continue
        rows.append(_relative(root, path))
    return list(dict.fromkeys(rows))


def load_database(
    root: Path, clangxx: str
) -> tuple[list[dict[str, Any]], dict[str, list[str]], int]:
    database = root / "compile_commands.json"
    if not database.is_file():
        raise Terminal("partial", "compile_database_missing", "current complete compile_commands.json required")
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal("failed", "compile_database_malformed", str(exc)) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal("failed", "compile_database_malformed", "database must be a non-empty object array")
    actual: set[Path] = set()
    entries = []
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row["arguments"], list):
            raise Terminal("failed", "compile_database_malformed", "exact directory/file/arguments required")
        if any(not isinstance(token, str) or not token for token in row["arguments"]):
            raise Terminal("failed", "compile_database_malformed", "arguments must be strings")
        directory = Path(row["directory"])
        source = Path(row["file"])
        if not directory.is_absolute() or directory.resolve(strict=False) != root:
            raise Terminal("partial", "compile_database_mismatched_directory", "database belongs to another root")
        if not source.is_absolute() or not _inside(source.resolve(strict=False), root):
            raise Terminal("partial", "compile_database_mismatched_directory", "source leaves project root")
        if not _is_cpp20(row["arguments"], row["file"]):
            raise Terminal("partial", "compile_database_non_cpp20", "every entry must use explicit C++20 mode")
        compiler = _resolve_tool(row["arguments"][0])
        if compiler is None or Path(compiler).resolve() != Path(clangxx).resolve():
            raise Terminal("partial", "compile_database_compiler_mismatch", "database must use selected clang++")
        resolved = source.resolve()
        if resolved in actual:
            raise Terminal("failed", "compile_database_malformed", "duplicate translation unit")
        actual.add(resolved)
        entries.append({"directory": str(root), "file": str(resolved), "arguments": row["arguments"]})
    expected = set(eligible_translation_units(root))
    if actual != expected:
        missing = sorted(_relative(root, path) for path in expected - actual)
        extra = sorted(_relative(root, path) for path in actual - expected)
        raise Terminal("partial", "compile_database_incomplete", f"database mismatch: missing={missing} extra={extra}")
    dependency_rows = {}
    for entry in sorted(entries, key=lambda row: row["file"]):
        source = Path(entry["file"])
        result = _run(analysis_argv(entry, clangxx, "-MM", "-MT", _relative(root, source)), root)
        if result.returncode:
            raise Terminal("failed", "clang_dependency_failed", result.stderr.strip())
        dependency_rows[_relative(root, source)] = _dependencies(result.stdout, root, source)
    inputs = [root / "Makefile", *actual]
    for paths in dependency_rows.values():
        inputs.extend(root / path for path in paths)
    input_mtime = max((path.stat().st_mtime_ns for path in inputs if path.is_file()), default=0)
    if database.stat().st_mtime_ns < input_mtime:
        raise Terminal("partial", "compile_database_stale", "database is older than a compiler input")
    return sorted(entries, key=lambda row: row["file"]), dependency_rows, input_mtime


def _location_file(node: dict[str, Any], current: str | None) -> str | None:
    location = node.get("loc", {})
    begin = node.get("range", {}).get("begin", {})
    return location.get("file") or begin.get("file") or current


def _is_macro(node: dict[str, Any]) -> bool:
    locations = [node.get("loc", {}), *node.get("range", {}).values()]
    return any(
        isinstance(location, dict)
        and ("spellingLoc" in location or "expansionLoc" in location)
        for location in locations
    )


def _descendants(node: dict[str, Any], kinds: set[str]) -> Iterable[dict[str, Any]]:
    for child in node.get("inner", []):
        if child.get("kind") in kinds:
            yield child
        yield from _descendants(child, kinds)


def _line(source: str, node: dict[str, Any]) -> int | None:
    location = node.get("loc", {})
    begin = node.get("range", {}).get("begin", {})
    offset = location.get("offset", begin.get("offset"))
    if isinstance(offset, int):
        return source.count("\n", 0, max(offset, 0)) + 1
    value = location.get("line", begin.get("line"))
    return value if isinstance(value, int) else None


def _slice(source: str, node: dict[str, Any]) -> str:
    begin = node.get("range", {}).get("begin", {})
    end = node.get("range", {}).get("end", {})
    start, finish = begin.get("offset"), end.get("offset")
    if not isinstance(start, int) or not isinstance(finish, int):
        return ""
    return source[start : finish + int(end.get("tokLen", 1))]


def _ast_facts(ast: dict[str, Any], root: Path) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "declarations": [],
        "direct_references": [],
        "aggregate_initializers": [],
        "state_operations": [],
        "boundaries": [],
    }
    texts: dict[str, str] = {}

    def text(relative: str) -> str:
        if relative not in texts:
            texts[relative] = (root / relative).read_text(encoding="utf-8", errors="replace")
        return texts[relative]

    def walk(
        node: dict[str, Any],
        file_hint: str | None,
        namespaces: tuple[str, ...],
        records: tuple[str, ...],
        function: str | None,
        parents: tuple[str, ...],
        template: bool,
        anonymous_namespace: bool,
    ) -> None:
        location = node.get("loc", {})
        begin = node.get("range", {}).get("begin", {})
        explicit_file = location.get("file") or begin.get("file")
        relative = file_hint
        if explicit_file:
            candidate = Path(explicit_file).resolve(strict=False)
            relative = _relative(root, candidate) if _inside(candidate, root) else None
        kind = node.get("kind")
        name = node.get("name")
        source = text(relative) if relative and (root / relative).is_file() else ""
        line = _line(source, node) if source else None
        next_namespaces = namespaces
        next_anonymous = anonymous_namespace
        if kind == "NamespaceDecl":
            component = name if name else "<anonymous>"
            next_namespaces = (*namespaces, component)
            next_anonymous = anonymous_namespace or not bool(name)
        next_records = records
        if kind in {"CXXRecordDecl", "RecordDecl"} and name and not node.get("isImplicit"):
            next_records = (*records, name)
        next_template = template or kind in {
            "FunctionTemplateDecl", "ClassTemplateDecl", "ClassTemplateSpecializationDecl"
        }
        qualified_parts = [*namespaces, *records, name] if name else [*namespaces, *records]
        qualified = "::".join(part for part in qualified_parts if part)
        next_function = function
        if kind in {"FunctionDecl", "CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl"} and name:
            next_function = qualified

        declaration_kinds = {
            "FunctionDecl": "function",
            "CXXMethodDecl": "method",
            "CXXConstructorDecl": "constructor",
            "CXXDestructorDecl": "destructor",
            "VarDecl": "variable",
            "FieldDecl": "field",
            "TypeAliasDecl": "type_alias",
            "TypedefDecl": "typedef",
            "CXXRecordDecl": "record",
            "RecordDecl": "record",
            "EnumDecl": "enum",
        }
        if (
            kind in declaration_kinds
            and name
            and relative
            and isinstance(line, int)
            and not node.get("isImplicit")
        ):
            definition = kind not in {"FunctionDecl", "CXXMethodDecl"} or any(
                child.get("kind") == "CompoundStmt" for child in node.get("inner", [])
            )
            type_value = node.get("type", {}).get("qualType")
            mangled = node.get("mangledName")
            symbol_key = mangled or f"{qualified}|{type_value}|{declaration_kinds[kind]}"
            groups["declarations"].append(
                {
                    "ast_id": node.get("id"),
                    "previous_ast_id": node.get("previousDecl"),
                    "symbol_key": symbol_key,
                    "name": name,
                    "qualified_name": qualified,
                    "namespace": "::".join(namespaces),
                    "owner": "::".join([*namespaces, *records]) if records else None,
                    "kind": declaration_kinds[kind],
                    "file": relative,
                    "line": line,
                    "type": type_value,
                    "linkage": "internal" if anonymous_namespace or node.get("storageClass") == "static" else "external",
                    "definition": definition,
                    "template": next_template,
                    "operator": name.startswith("operator"),
                    "virtual": bool(node.get("virtual")) or any(
                        child.get("kind") == "OverrideAttr" for child in node.get("inner", [])
                    ),
                    "header_owned": Path(relative).suffix in HEADER_SUFFIXES | AMBIGUOUS_HEADER_SUFFIXES,
                    "macro_expansion": _is_macro(node),
                }
            )

        if kind == "DeclRefExpr" and relative and isinstance(line, int):
            target = node.get("referencedDecl", {})
            groups["direct_references"].append(
                {
                    "name": target.get("name"),
                    "target_ast_id": target.get("id"),
                    "target_kind": target.get("kind"),
                    "target_type": target.get("type", {}).get("qualType"),
                    "file": relative,
                    "line": line,
                    "function": function,
                    "context": "direct_call" if any(parent in {"CallExpr", "CXXOperatorCallExpr"} for parent in parents[-3:]) else "value_or_address",
                    "macro_expansion": _is_macro(node),
                }
            )
        if kind == "MemberExpr" and relative and isinstance(line, int):
            groups["direct_references"].append(
                {
                    "name": name,
                    "target_ast_id": node.get("referencedMemberDecl"),
                    "target_kind": "FieldDecl",
                    "target_type": node.get("type", {}).get("qualType"),
                    "file": relative,
                    "line": line,
                    "function": function,
                    "context": "member_reference",
                    "macro_expansion": _is_macro(node),
                }
            )
        if kind == "BinaryOperator" and node.get("opcode") == "=" and relative and isinstance(line, int):
            members = list(_descendants(node, {"MemberExpr"}))
            strings = list(_descendants(node, {"StringLiteral"}))
            if len(members) == 1 and len(strings) == 1:
                literal = strings[0].get("value")
                groups["state_operations"].append(
                    {
                        "field_ast_id": members[0].get("referencedMemberDecl"),
                        "field": members[0].get("name"),
                        "literal": literal,
                        "file": relative,
                        "line": line,
                        "function": function,
                        "operation": "direct_assignment",
                        "macro_expansion": _is_macro(node)
                        or _is_macro(members[0])
                        or _is_macro(strings[0]),
                    }
                )
        if kind == "InitListExpr" and relative and isinstance(line, int):
            snippet = _slice(source, node)
            fields = sorted(set(re.findall(r"\.([A-Za-z_]\w*)\s*=", snippet)))
            if fields:
                type_info = node.get("type", {})
                groups["aggregate_initializers"].append(
                    {
                        "record": type_info.get("desugaredQualType", type_info.get("qualType")),
                        "fields": fields,
                        "file": relative,
                        "line": line,
                        "function": function,
                        "context": "return" if "ReturnStmt" in parents else "initializer",
                        "snippet": " ".join(snippet.split())[:300],
                        "macro_expansion": _is_macro(node),
                    }
                )
        if kind in {"CallExpr", "CXXOperatorCallExpr"} and relative and isinstance(line, int):
            refs = list(_descendants(node, {"DeclRefExpr", "MemberExpr"}))
            function_targets = [
                item for item in refs
                if item.get("referencedDecl", {}).get("kind") in {"FunctionDecl", "CXXMethodDecl"}
            ]
            if not function_targets:
                groups["boundaries"].append(
                    {"kind": "function_pointer_or_dynamic_call", "file": relative, "line": line, "function": function}
                )

        if kind in {"FunctionTemplateDecl", "ClassTemplateDecl", "ClassTemplateSpecializationDecl"} and relative:
            groups["boundaries"].append(
                {"kind": "template", "name": qualified, "file": relative, "line": line}
            )
        if kind in {"FunctionDecl", "CXXMethodDecl"} and name and name.startswith("operator") and relative:
            groups["boundaries"].append(
                {"kind": "operator", "name": qualified, "file": relative, "line": line}
            )
        if kind == "CXXMethodDecl" and node.get("virtual") and relative:
            groups["boundaries"].append(
                {"kind": "virtual_dispatch", "name": qualified, "file": relative, "line": line}
            )
        for child in node.get("inner", []):
            walk(
                child, relative, next_namespaces, next_records, next_function,
                (*parents, kind or ""), next_template, next_anonymous,
            )

    current_file = None
    for child in ast.get("inner", []):
        location = child.get("loc", {})
        begin = child.get("range", {}).get("begin", {})
        explicit_file = location.get("file") or begin.get("file")
        current_file = explicit_file
        hint = None
        if current_file:
            candidate = Path(current_file).resolve(strict=False)
            if _inside(candidate, root):
                hint = _relative(root, candidate)
        walk(child, hint, (), (), None, ("TranslationUnitDecl",), False, False)
    return groups


def _macro_boundaries(root: Path, included: set[str]) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(included):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = re.match(r"\s*#\s*(define|if|ifdef|ifndef|elif|else|endif)\b", line)
            if match:
                rows.append({"kind": "macro_or_inactive_variant", "file": relative, "line": number, "directive": match.group(1)})
    return rows


def _empty(status: str, kind: str, message: str) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA,
        "language": "cpp",
        "status": status,
        "failure_kind": kind,
        "message": message,
        "read_only": True,
        "compile_database": {"state": "rejected"},
        "source_inventory": [],
        "declarations": [],
        "direct_references": [],
        "aggregate_initializers": [],
        "state_operations": [],
        "boundaries": [],
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _hash(payload)
    return payload


def collect(project_root: Path, *, clangxx: str = "clang++") -> dict[str, Any]:
    root = project_root.resolve()
    if not root.is_dir() or project_root.is_symlink():
        return _empty("partial", "unsafe_project_root", "project root must be a regular directory")
    selected = _resolve_tool(clangxx)
    if selected is None:
        return _empty("partial", "clangxx_missing", "Clang++ 21+ is required")
    version, probe = _version(selected, root)
    if version is None:
        return _empty("partial", "clangxx_version_unknown", probe)
    if version < (21, 0, 0):
        return _empty("partial", "clangxx_version_too_old", f"Clang++ {version} is below 21")
    before_sha, before_files = source_manifest(root)
    try:
        entries, dependencies, input_mtime = load_database(root, selected)
        groups: dict[str, list[dict[str, Any]]] = {
            "declarations": [], "direct_references": [], "aggregate_initializers": [],
            "state_operations": [], "boundaries": [],
        }
        for entry in entries:
            result = _run(analysis_argv(entry, selected, "-Xclang", "-ast-dump=json", "-fsyntax-only"), root)
            if result.returncode:
                raise Terminal("failed", "clang_ast_failed", result.stderr.strip() or "Clang AST failed")
            try:
                ast = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise Terminal("failed", "clang_ast_malformed", str(exc)) from exc
            facts = _ast_facts(ast, root)
            for key in groups:
                groups[key].extend(facts[key])
    except Terminal as exc:
        return _empty(exc.status, exc.kind, str(exc))
    selected_tus = {_relative(root, Path(entry["file"])) for entry in entries}
    owned_headers = {item for values in dependencies.values() for item in values}
    inventory = []
    for path in _candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        role = "symlink" if path.is_symlink() else _role(relative)
        included = relative in selected_tus or relative in owned_headers
        if role == "production" and path.suffix in AMBIGUOUS_HEADER_SUFFIXES and not included:
            role = "ambiguous-header"
        inventory.append({"path": relative, "role": role, "included": included})
    included = selected_tus | owned_headers
    groups["boundaries"].extend(_macro_boundaries(root, included))
    by_spelling: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in groups["declarations"]:
        if row["kind"] in {"function", "method"}:
            by_spelling[(row["qualified_name"], row["file"])].add(row.get("type") or "")
    for (qualified, file), types in by_spelling.items():
        if len(types) > 1:
            groups["boundaries"].append(
                {"kind": "overload_set", "name": qualified, "file": file, "types": sorted(types)}
            )
    header_definitions = Counter(
        (row["symbol_key"], row["file"])
        for row in groups["declarations"]
        if row["definition"] and row["header_owned"]
    )
    for (symbol, file), count in header_definitions.items():
        if count > 1:
            groups["boundaries"].append(
                {"kind": "odr_header_definition", "symbol_key": symbol, "file": file, "translation_unit_observations": count}
            )
    after_sha, after_files = source_manifest(root)
    if before_files != after_files:
        return _empty("failed", "source_mutated", "source changed during read-only collection")
    for key in groups:
        unique = {json.dumps(row, sort_keys=True, ensure_ascii=False): row for row in groups[key]}
        groups[key] = sorted(
            unique.values(), key=lambda row: (row.get("file", ""), row.get("line") or 0, row.get("name", ""))
        )
    payload = {
        "schema_version": SCHEMA,
        "language": "cpp",
        "status": "complete",
        "failure_kind": None,
        "read_only": True,
        "toolchain": {"clangxx": {"path": selected, "version": ".".join(map(str, version)), "probe": probe}},
        "compile_database": {
            "path": "compile_commands.json",
            "state": "valid-current-complete-c++20",
            "sha256": sha256(root / "compile_commands.json"),
            "mtime_ns": (root / "compile_commands.json").stat().st_mtime_ns,
            "newest_input_mtime_ns": input_mtime,
            "translation_units": sorted(selected_tus),
        },
        "dependency_closure": dependencies,
        "source_inventory": inventory,
        "source_manifest_sha256": before_sha,
        "source_files": before_files,
        "source_preservation": {"before": before_sha, "after": after_sha, "unchanged": True},
        **groups,
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _hash(payload)
    return payload


def load_or_collect(
    *, project_root: Path, facts: Path | None, clangxx: str = "clang++"
) -> dict[str, Any]:
    root = project_root.resolve()
    if facts is None:
        return collect(root, clangxx=clangxx)
    path = facts if facts.is_absolute() else root / facts
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _empty("partial", "cpp_semantic_fact_pack_invalid", str(exc))
    claimed = payload.get("fact_pack_sha256")
    unhashed = dict(payload)
    unhashed.pop("fact_pack_sha256", None)
    if (
        payload.get("schema_version") != SCHEMA
        or payload.get("status") != "complete"
        or claimed != _hash(unhashed)
    ):
        return _empty("partial", "cpp_semantic_fact_pack_incomplete", "fact pack is incomplete or tampered")
    current_sha, _ = source_manifest(root)
    database = root / "compile_commands.json"
    if current_sha != payload.get("source_manifest_sha256") or not database.is_file():
        return _empty("partial", "cpp_semantic_fact_pack_stale", "source or database changed")
    if sha256(database) != payload.get("compile_database", {}).get("sha256"):
        return _empty("partial", "cpp_semantic_fact_pack_stale", "compile database changed")
    inputs = [root / "Makefile"]
    inputs.extend(root / item for item in payload["compile_database"].get("translation_units", []))
    for values in payload.get("dependency_closure", {}).values():
        inputs.extend(root / item for item in values)
    newest = max((path.stat().st_mtime_ns for path in inputs if path.is_file()), default=0)
    if database.stat().st_mtime_ns < newest:
        return _empty("partial", "cpp_semantic_fact_pack_stale", "compile database is stale")
    return payload


def in_target(row: dict[str, Any], root: Path, target: str) -> bool:
    selected = (root / target).resolve(strict=False)
    path = (root / row.get("file", row.get("path", ""))).resolve(strict=False)
    return path == selected or (selected.is_dir() and _inside(path, selected))


def safe_output(root: Path, supplied: Path, report_root: str) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / report_root
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"output must stay beneath {report_root}/") from exc
    if not relative.parts:
        raise ValueError("output must name a report file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output must not traverse a symbolic link")
    return output


def common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--clangxx", default="clang++")
    return parser


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clangxx", default="clang++")
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = safe_output(root, args.output, "reports/cpp-semantic")
    except ValueError as exc:
        parser.error(str(exc))
    payload = collect(root, clangxx=args.clangxx)
    atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(_cli())
