#!/usr/bin/env python3
"""Offline SwiftPM/compiler-AST facts for bounded read-only consumers.

This is a Swift-local union fact pack, not a universal semantic model. It owns
the selected SwiftPM package/target/configuration identity, restrictive native
gates, and deterministic normalized ``swiftc -dump-ast`` declarations,
references, calls, overloads, default arguments, and direct property writes.
Consumers own their candidates, reviews, reports, and terminal status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "swift-semantic-facts-v1"
MINIMUM_SWIFT = (6, 0, 0)
PINNED_SEMANTIC_SWIFT = (6, 3, 3)
ARTIFACT_DIRS = frozenset({".agents", ".build", ".git", ".swiftpm", "reports"})
BUILD_DIRS = frozenset({".build", "build", "dist", "out"})
GENERATED_DIRS = frozenset({"generated", "derivedsources", "gen"})
VENDOR_DIRS = frozenset({"vendor", "vendors", "third_party", "third-party"})
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
CALLABLE_KINDS = frozenset({6, 9, 12})
TYPE_KINDS = frozenset({5, 10, 11, 23})
AST_TIMEOUT_SECONDS = 20.0
MAX_AST_FILES = 32
MAX_AST_BYTES = 8 * 1024 * 1024
LIMITS = [
    "dependency-free SwiftPM regular library/executable targets in one selected debug or release configuration only",
    "Apple Swift 6.3.3 swiftc compiler-AST output is the pinned semantic boundary; other compiler versions are unsupported until replayed",
    "a fresh successful restrictive build is required before one bounded offline swiftc typecheck/dump-ast invocation",
    "normalized compiler declaration locations identify selected static symbols; exact resolved decl references identify direct references and calls",
    "conditional compilation, attached/freestanding macros, plugins, generated code, reflection, @objc/dynamic dispatch, and selectors are not expanded",
    "protocol/existential runtime dispatch, runtime reachability, side effects, and deletion/refactor safety remain unresolved",
    "Xcode projects/workspaces/schemes, Apple-framework behavior, resources, package dependencies, and mixed-language targets are outside this contract",
    "native XCTest and Testing modules remain unavailable under the active Command Line Tools; fixture-owned check and smoke executables are required",
    "ASCII identifier queries only; Unicode identifier spellings are not a selected consumer contract",
    "compiler-AST work has one 20-second wall-clock budget, at most 32 selected files, and an 8 MiB captured-output ceiling",
]


class SwiftFactError(ValueError):
    """An invalid or stale fact-pack handoff."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def safe_output(root: Path, supplied: Path, relative_root: str) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(candidate))
    allowed = root / relative_root
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise SwiftFactError("unsafe_output", f"output must stay beneath {relative_root}/") from exc
    if not relative.parts:
        raise SwiftFactError("unsafe_output", "output must name a file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise SwiftFactError("unsafe_output", "output must not traverse a symbolic link")
    return output


def _run(argv: list[str], cwd: Path, *, timeout: float = 240) -> subprocess.CompletedProcess[str]:
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


def _check(identifier: str, argv: list[str], result: subprocess.CompletedProcess[str]) -> dict:
    return {
        "id": identifier,
        "command": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _which(configured: str | Path) -> Path | None:
    path = Path(configured)
    if path.is_absolute():
        return path if path.is_file() and os.access(path, os.X_OK) else None
    resolved = shutil.which(str(path))
    return Path(resolved).resolve() if resolved else None


def _version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?:Apple )?Swift version\s+(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if match is None:
        match = re.search(r"(?m)^\s*(\d+)\.(\d+)(?:\.(\d+))?\s*$", text)
    return tuple(int(value or 0) for value in match.groups()) if match else None


def _probe_version(
    path: Path | None,
    root: Path,
    name: str,
    *,
    exact: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    if path is None:
        return {"state": "missing", "failure_kind": f"{name}_missing"}
    result = _run([str(path), "--version"], root, timeout=20)
    rendered = result.stdout + result.stderr
    parsed = _version(rendered)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_failed",
            "detail": rendered.strip()[-2000:],
        }
    if parsed is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}_version_malformed",
            "detail": rendered.strip()[-2000:],
        }
    supported = parsed == exact if exact is not None else parsed >= MINIMUM_SWIFT
    failure_kind = None
    if not supported:
        failure_kind = f"{name}_too_old" if parsed < MINIMUM_SWIFT else f"{name}_version_unsupported"
    return {
        "state": "ready" if supported else ("too-old" if parsed < MINIMUM_SWIFT else "unsupported"),
        "path": str(path),
        "version": ".".join(map(str, parsed)),
        "version_tuple": list(parsed),
        "required_version": ".".join(map(str, exact)) if exact is not None else None,
        "failure_kind": failure_kind,
    }


def _snapshot(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        relative_parent = parent.relative_to(root)
        directories[:] = [
            name
            for name in directories
            if name not in ARTIFACT_DIRS and not (parent / name).is_symlink()
        ]
        for name in sorted(files):
            path = parent / name
            relative = (relative_parent / name).as_posix()
            if any(part in ARTIFACT_DIRS for part in Path(relative).parts):
                continue
            if path.is_symlink():
                rows[relative] = f"symlink:{os.readlink(path)}"
            elif path.is_file():
                rows[relative] = _sha256(path)
    return rows


def _manifest_hash(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _swiftpm_base(swift: Path, root: Path, state: Path) -> list[str]:
    return [
        str(swift),
        "package",
        "--package-path",
        str(root),
        "--cache-path",
        str(state / "cache"),
        "--config-path",
        str(state / "config"),
        "--security-path",
        str(state / "security"),
        "--scratch-path",
        str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache",
        "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
    ]


def _role_for_path(relative: Path) -> str:
    lowered = {part.lower() for part in relative.parts}
    if lowered & BUILD_DIRS:
        return "build"
    if lowered & GENERATED_DIRS:
        return "generated"
    if lowered & VENDOR_DIRS:
        return "vendor"
    if lowered & TEST_DIRS:
        return "test"
    return "unowned"


def _inventory(
    root: Path, description: dict[str, Any], target_name: str
) -> tuple[list[dict], list[Path], dict]:
    targets = description.get("targets", [])
    selected = next((row for row in targets if row.get("name") == target_name), None)
    if selected is None:
        raise SwiftFactError("target_not_found", f"SwiftPM target {target_name!r} was not found")
    if selected.get("type") not in {"library", "executable"}:
        raise SwiftFactError(
            "target_shape_outside_contract", "selected target must be a library or executable"
        )
    selected_sources: set[str] = set()
    consumer_sources: set[str] = set()
    declared_roles: dict[str, str] = {}
    for target in targets:
        base = str(target.get("path", "")).rstrip("/")
        sources = {f"{base}/{source}" for source in target.get("sources", [])}
        target_type = target.get("type")
        if target.get("name") == target_name:
            selected_sources.update(sources)
            role = "selected-production"
        elif target_type == "test":
            role = "test"
        elif target_name in target.get("target_dependencies", []):
            consumer_sources.update(sources)
            role = "selected-consumer"
        else:
            role = "other-target"
        for source in sources:
            declared_roles[source] = role
    rows: list[dict] = []
    seen: set[str] = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        relative_parent = parent.relative_to(root)
        directories[:] = [name for name in directories if name != ".git"]
        for name in sorted(files):
            if not name.endswith(".swift"):
                continue
            path = parent / name
            relative = (relative_parent / name).as_posix()
            role = (
                "symlink-excluded"
                if path.is_symlink()
                else declared_roles.get(relative, _role_for_path(Path(relative)))
            )
            included = (
                role in {"selected-production", "selected-consumer"} and not path.is_symlink()
            )
            rows.append(
                {
                    "path": relative,
                    "role": role,
                    "included": included,
                    "sha256": _sha256(path) if path.is_file() and not path.is_symlink() else None,
                }
            )
            seen.add(relative)
    missing = sorted(selected_sources - seen)
    if missing:
        raise SwiftFactError(
            "selected_source_missing", f"selected SwiftPM sources are missing: {', '.join(missing)}"
        )
    unsafe = [
        row["path"]
        for row in rows
        if row["role"] == "symlink-excluded" and row["path"] in selected_sources
    ]
    if unsafe:
        raise SwiftFactError(
            "unsafe_selected_source", f"selected sources are symbolic links: {', '.join(unsafe)}"
        )
    semantic = [root / row["path"] for row in rows if row["included"]]
    rows.sort(key=lambda row: row["path"])
    return rows, semantic, selected


def _base_name(display: str | None) -> str:
    if not isinstance(display, str):
        return ""
    return display.split("(", 1)[0].split(".")[-1]


_AST_DECLARATION = re.compile(
    r"^(?P<indent> *)\((?P<node>actor_decl|class_decl|constructor_decl|enum_decl|func_decl|protocol_decl|struct_decl|var_decl)\b(?P<body>.*)$"
)
_AST_RANGE = re.compile(
    r"range=\[(?P<path>.+?\.swift):(?P<line>\d+):(?P<column>\d+) - (?:line:|.+?\.swift:)(?P<end_line>\d+):(?P<end_column>\d+)\]"
)
_AST_LOCATION = re.compile(
    r"location=(?P<path>.+?\.swift):(?P<line>\d+):(?P<column>\d+)"
)
_AST_TARGET = re.compile(
    r'@(?P<path>[^"@]+\.swift):(?P<line>\d+):(?P<column>\d+)'
)
_AST_INTERFACE = re.compile(r'interface_type="(?P<interface>[^"]*)"')
_AST_DISPLAY = re.compile(r'\] "(?P<display>[^"]+)"')
_AST_TYPE_EXPR = re.compile(r'typerepr="(?P<name>[A-Za-z_][A-Za-z0-9_]*)"')
_AST_STRING_LITERAL = re.compile(r'value="(?P<value>[^"\\]*(?:\\.[^"\\]*)*)"')
_HEX_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


def _ast_path(raw: str, root: Path) -> str | None:
    path = Path(raw)
    if path.is_absolute():
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return None
    normalized = Path(os.path.normpath(raw))
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return normalized.as_posix()


def _ast_location(line: str, root: Path) -> dict[str, Any] | None:
    match = _AST_LOCATION.search(line)
    if match is None:
        return None
    path = _ast_path(match.group("path"), root)
    if path is None:
        return None
    return {
        "path": path,
        "line": int(match.group("line")),
        "column": int(match.group("column")),
        "external": False,
    }


def _ast_range(line: str, root: Path) -> dict[str, Any] | None:
    match = _AST_RANGE.search(line)
    if match is None:
        return None
    path = _ast_path(match.group("path"), root)
    if path is None:
        return None
    return {
        "path": path,
        "line": int(match.group("line")),
        "column": int(match.group("column")),
        "end_line": int(match.group("end_line")),
        "end_column": int(match.group("end_column")),
    }


def _ast_target(line: str, root: Path) -> dict[str, Any] | None:
    declaration = re.search(r'decl="(?P<decl>[^"]+)"', line)
    if declaration is None:
        return None
    target = _AST_TARGET.search(declaration.group("decl"))
    if target is None:
        return None
    path = _ast_path(target.group("path"), root)
    if path is None:
        return None
    return {
        "decl": declaration.group("decl"),
        "path": path,
        "line": int(target.group("line")),
        "column": int(target.group("column")),
    }


def _declaration_kind(node: str, *, top_level: bool) -> int:
    return {
        "actor_decl": 5,
        "class_decl": 5,
        "constructor_decl": 9,
        "enum_decl": 10,
        "func_decl": 12 if top_level else 6,
        "protocol_decl": 11,
        "struct_decl": 23,
        "var_decl": 13 if top_level else 8,
    }[node]


def _name_column(root: Path, location: dict[str, Any], name: str) -> int:
    source = root / location["path"]
    try:
        line = source.read_text(encoding="utf-8").splitlines()[location["line"] - 1]
    except (OSError, UnicodeDecodeError, IndexError):
        return location["column"]
    match = re.search(rf"\b{re.escape(name)}\b", line)
    return match.start() + 1 if match else location["column"]


def _semantic_id(module: str, declaration: dict[str, Any]) -> str:
    identity = {
        "module": module,
        "path": declaration["file"],
        "line": declaration["line"],
        "column": declaration["column"],
        "kind": declaration["kind"],
        "display_name": declaration["display_name"],
        "interface_type": declaration["interface_type"],
        "parent": declaration["parent"],
    }
    return f"swiftc-declaration:{_canonical_hash(identity)}"


def _normalize_ast(raw: str, root: Path) -> str:
    normalized = raw.replace(f"{root.as_posix()}/", "")
    normalized = _HEX_ADDRESS.sub("0xADDR", normalized)
    return normalized.rstrip() + "\n"


def _ast_declarations(
    lines: list[str],
    root: Path,
    module: str,
    roles: dict[str, str],
) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    type_stack: list[tuple[int, str]] = []
    type_nodes = {"actor_decl", "class_decl", "enum_decl", "protocol_decl", "struct_decl"}
    for index, line in enumerate(lines):
        match = _AST_DECLARATION.match(line)
        if match is None:
            continue
        indent = len(match.group("indent"))
        while type_stack and type_stack[-1][0] >= indent:
            type_stack.pop()
        node = match.group("node")
        location = _ast_range(line, root)
        display = _AST_DISPLAY.search(line)
        interface = _AST_INTERFACE.search(line)
        if location is None or display is None or interface is None or " implicit " in line:
            continue
        display_name = display.group("display")
        name = "init" if node == "constructor_decl" else _base_name(display_name)
        parent = type_stack[-1][1] if type_stack else None
        top_level = parent is None and indent == 2
        if node == "var_decl" and not (
            top_level or (type_stack and indent == type_stack[-1][0] + 2)
        ):
            continue
        if node == "func_decl" and not (
            top_level or (type_stack and indent == type_stack[-1][0] + 2)
        ):
            continue
        column = _name_column(root, location, name)
        declaration = {
            "name": name,
            "display_name": display_name,
            "kind": _declaration_kind(node, top_level=top_level),
            "file": location["path"],
            "role": roles.get(location["path"], "unowned"),
            "line": location["line"],
            "column": column,
            "end_line": location["end_line"],
            "end_column": location["end_column"],
            "parent": parent,
            "top_level": top_level,
            "detail": interface.group("interface"),
            "interface_type": interface.group("interface"),
            "semantic_identity_kind": "swiftc-declaration-location-signature",
            "definitions": [
                {
                    "path": location["path"],
                    "line": location["line"],
                    "column": column,
                    "external": False,
                }
            ],
            "hover": {
                "contents": {
                    "kind": "plaintext",
                    "value": interface.group("interface"),
                }
            },
            "prepare_rename": {
                "placeholder": name,
                "provider": "swiftc-dump-ast",
            },
            "_ast_index": index,
            "_ast_indent": indent,
            "_node": node,
        }
        declaration["semantic_id"] = _semantic_id(module, declaration)
        declaration["symbol_id"] = declaration["semantic_id"]
        declarations.append(declaration)
        if node in type_nodes:
            type_stack.append((indent, name))
    return declarations


def _definition_occurrence(
    name: str,
    location: dict[str, Any],
    symbol: dict[str, Any],
    evidence: str,
) -> dict[str, Any]:
    definition = dict(symbol["definitions"][0])
    return {
        "name": name,
        "source": location["path"],
        "line": location["line"],
        "column": location["column"],
        "definitions": [definition],
        "definition_semantic_ids": [symbol["semantic_id"]],
        "evidence": evidence,
    }


def _target_symbol(
    target: dict[str, Any],
    declarations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    exact = [
        row
        for row in declarations
        if row["file"] == target["path"]
        and row["line"] == target["line"]
        and row["column"] == target["column"]
    ]
    return exact[0] if len(exact) == 1 else None


def _compiler_occurrences(
    lines: list[str],
    root: Path,
    module: str,
    declarations: list[dict[str, Any]],
    queries: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    query_symbols = [row for row in declarations if row["name"] in queries]
    type_symbols = {
        row["name"]: row for row in query_symbols if row["kind"] in TYPE_KINDS
    }
    occurrences = [
        _definition_occurrence(
            row["name"],
            {"path": row["file"], "line": row["line"], "column": row["column"]},
            row,
            "swiftc-dump-ast-declaration",
        )
        for row in query_symbols
    ]
    calls: list[dict[str, Any]] = []
    overloads: list[dict[str, Any]] = []
    for line in lines:
        location = _ast_location(line, root)
        if location is None:
            continue
        target = _ast_target(line, root)
        if target is not None and target["decl"].startswith(f"{module}.(file)."):
            symbol = _target_symbol(target, declarations)
            constructor = re.search(
                rf"^{re.escape(module)}\.\(file\)\.(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.init\(",
                target["decl"],
            )
            if constructor is not None and "function_ref=single apply" in line:
                owner = type_symbols.get(constructor.group("owner"))
                interface = re.search(r'type="(?P<type>[^"]+)"', line)
                overload = {
                    "source": location["path"],
                    "line": location["line"],
                    "column": location["column"],
                    "owner": constructor.group("owner"),
                    "selected_declaration": {
                        "path": target["path"],
                        "line": target["line"],
                        "column": target["column"],
                    },
                    "selected_interface_type": interface.group("type") if interface else None,
                    "evidence": "swiftc-dump-ast-declref-single-apply",
                }
                overloads.append(overload)
                if owner is not None:
                    occurrences.append(
                        _definition_occurrence(
                            owner["name"], location, owner, "swiftc-dump-ast-constructor"
                        )
                    )
            elif symbol is not None:
                if symbol["name"] in queries:
                    occurrences.append(
                        _definition_occurrence(
                            symbol["name"], location, symbol, "swiftc-dump-ast-declref"
                        )
                    )
                if "function_ref=single apply" in line and symbol["kind"] in CALLABLE_KINDS:
                    calls.append(
                        {
                            "source": location["path"],
                            "line": location["line"],
                            "column": location["column"],
                            "target_name": symbol["name"],
                            "target_semantic_id": symbol["semantic_id"],
                            "target_interface_type": symbol["interface_type"],
                            "target_declaration": dict(symbol["definitions"][0]),
                            "evidence": "swiftc-dump-ast-declref-single-apply",
                        }
                    )
        if "(type_expr" in line and "(type_expr implicit" not in line:
            type_name = _AST_TYPE_EXPR.search(line)
            if type_name and type_name.group("name") in type_symbols:
                symbol = type_symbols[type_name.group("name")]
                occurrences.append(
                    _definition_occurrence(
                        symbol["name"], location, symbol, "swiftc-dump-ast-type-expr"
                    )
                )

    for declaration in declarations:
        source = root / declaration["file"]
        try:
            source_lines = source.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        start = declaration["line"] - 1
        signature = ""
        for source_line in source_lines[start : min(start + 8, declaration["end_line"])]:
            signature += source_line + "\n"
            if "{" in source_line:
                break
        first_line = source_lines[start] if start < len(source_lines) else ""
        for name, symbol in type_symbols.items():
            if not re.search(rf"\b{re.escape(name)}\b", declaration["interface_type"]):
                continue
            for offset, source_line in enumerate(signature.splitlines()):
                for match in re.finditer(rf"\b{re.escape(name)}\b", source_line):
                    if declaration["name"] == name and offset == 0 and source_line == first_line:
                        continue
                    occurrences.append(
                        _definition_occurrence(
                            name,
                            {
                                "path": declaration["file"],
                                "line": declaration["line"] + offset,
                                "column": match.start() + 1,
                            },
                            symbol,
                            "swiftc-dump-ast-interface-type",
                        )
                    )

    occurrences = list(
        {
            (
                row["name"],
                row["source"],
                row["line"],
                row["column"],
                tuple(row["definition_semantic_ids"]),
            ): row
            for row in occurrences
        }.values()
    )
    calls = list(
        {
            (row["source"], row["line"], row["column"], row["target_semantic_id"]): row
            for row in calls
        }.values()
    )
    overloads = list(
        {
            (
                row["source"],
                row["line"],
                row["column"],
                row["selected_declaration"]["path"],
                row["selected_declaration"]["line"],
            ): row
            for row in overloads
        }.values()
    )
    return occurrences, calls, overloads


def _compiler_property_writes(
    lines: list[str],
    root: Path,
    declarations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    writes: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if "(assign_expr " not in line or "(assign_expr implicit" in line:
            continue
        assignment = _ast_location(line, root)
        if assignment is None:
            continue
        indent = len(line) - len(line.lstrip())
        children: list[str] = []
        for child in lines[index + 1 :]:
            child_indent = len(child) - len(child.lstrip())
            if child.strip() and child_indent <= indent:
                break
            children.append(child)
        member: tuple[dict[str, Any], dict[str, Any]] | None = None
        literal: str | None = None
        for child in children:
            if member is None and "member_ref_expr" in child:
                target = _ast_target(child, root)
                location = _ast_location(child, root)
                symbol = _target_symbol(target, declarations) if target else None
                if location and symbol and symbol["kind"] == 8:
                    member = (symbol, location)
            if literal is None and "string_literal_expr" in child:
                value = _AST_STRING_LITERAL.search(child)
                if value:
                    literal = value.group("value")
        if member is None or literal is None:
            continue
        symbol, location = member
        if location["path"] != assignment["path"] or location["line"] != assignment["line"]:
            continue
        writes.append(
            {
                "owner": symbol["parent"],
                "field": symbol["name"],
                "field_semantic_id": symbol["semantic_id"],
                "file": location["path"],
                "line": location["line"],
                "column": location["column"],
                "literal": literal,
                "evidence": "swiftc-dump-ast-assign-member-string-literal",
            }
        )
    return list(
        {
            (row["field_semantic_id"], row["file"], row["line"], row["literal"]): row
            for row in writes
        }.values()
    )


def _compiler_default_arguments(
    lines: list[str], root: Path, declarations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in lines:
        if "default_argument_expr" not in line:
            continue
        location = _ast_location(line, root)
        owner = re.search(r'default_args_owner="(?P<owner>[^"]+)" param=(?P<param>\d+)', line)
        if location is None or owner is None:
            continue
        target_match = _AST_TARGET.search(owner.group("owner"))
        if target_match is None:
            continue
        target = {
            "path": _ast_path(target_match.group("path"), root),
            "line": int(target_match.group("line")),
            "column": int(target_match.group("column")),
        }
        if target["path"] is None:
            continue
        symbol = _target_symbol(target, declarations)
        if symbol is None:
            continue
        rows.append(
            {
                "source": location["path"],
                "line": location["line"],
                "column": location["column"],
                "target_name": symbol["name"],
                "target_semantic_id": symbol["semantic_id"],
                "parameter_index": int(owner.group("param")),
                "evidence": "swiftc-dump-ast-default-argument-expr",
            }
        )
    return rows


def _compiler_function_bodies(
    lines: list[str],
    symbols: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    overloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        if symbol["kind"] not in CALLABLE_KINDS:
            continue
        subtree = lines[symbol["_ast_index"] + 1 :]
        body_lines: list[str] = []
        for line in subtree:
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent <= symbol["_ast_indent"]:
                break
            body_lines.append(line)
        direct_calls = [
            row
            for row in calls
            if row["source"] == symbol["file"]
            and symbol["line"] < row["line"] <= symbol["end_line"]
        ]
        selected_overloads = [
            row
            for row in overloads
            if row["source"] == symbol["file"]
            and symbol["line"] < row["line"] <= symbol["end_line"]
        ]
        rows.append(
            {
                "name": symbol["name"],
                "semantic_id": symbol["semantic_id"],
                "file": symbol["file"],
                "line": symbol["line"],
                "end_line": symbol["end_line"],
                "interface_type": symbol["interface_type"],
                "has_return_statement": any("(return_stmt" in line for line in body_lines),
                "direct_call_target_ids": sorted(
                    {row["target_semantic_id"] for row in direct_calls}
                ),
                "direct_call_targets": sorted({row["target_name"] for row in direct_calls}),
                "selected_overloads": selected_overloads,
                "evidence": "swiftc-dump-ast-function-subtree",
            }
        )
    return rows


def _compiler_facts(
    swiftc: Path,
    root: Path,
    module: str,
    files: list[Path],
    roles: dict[str, str],
    queries: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if len(files) > MAX_AST_FILES:
        raise SwiftFactError(
            "compiler_ast_scope_exceeded",
            f"bounded compiler-AST scope exceeded: {len(files)} files",
        )
    relative_files = [source.relative_to(root).as_posix() for source in sorted(files)]
    argv = [
        str(swiftc),
        "-typecheck",
        "-dump-ast",
        "-module-name",
        module,
        *relative_files,
    ]
    result = _run(argv, root, timeout=AST_TIMEOUT_SECONDS)
    raw = result.stdout + result.stderr
    if result.returncode:
        kind = "compiler_ast_timeout" if result.returncode == 124 else "compiler_ast_failed"
        raise SwiftFactError(kind, raw[-4000:] or f"swiftc exited {result.returncode}")
    if len(raw.encode("utf-8")) > MAX_AST_BYTES:
        raise SwiftFactError(
            "compiler_ast_scope_exceeded",
            f"compiler AST exceeded {MAX_AST_BYTES} captured bytes",
        )
    normalized = _normalize_ast(raw, root)
    lines = normalized.splitlines()
    source_files = {
        path
        for line in lines
        if line.startswith("(source_file ")
        for match in [re.search(r'^\(source_file "(?P<path>.+?\.swift)"', line)]
        if match is not None
        for path in [_ast_path(match.group("path"), root)]
        if path is not None
    }
    if source_files != set(relative_files):
        raise SwiftFactError(
            "compiler_ast_incomplete",
            f"compiler AST sources differ from selected inputs: {sorted(source_files)}",
        )
    declarations = _ast_declarations(lines, root, module, roles)
    query_set = set(queries)
    symbols = [row for row in declarations if row["name"] in query_set]
    occurrences, calls, overloads = _compiler_occurrences(
        lines, root, module, declarations, query_set
    )
    property_writes = _compiler_property_writes(lines, root, declarations)
    defaults = _compiler_default_arguments(lines, root, declarations)
    bodies = _compiler_function_bodies(lines, symbols, calls, overloads)
    public_symbols = [
        {key: value for key, value in row.items() if not key.startswith("_")} for row in symbols
    ]
    public_symbols.sort(key=lambda row: (row["file"], row["line"], row["column"], row["name"]))
    occurrences.sort(key=lambda row: (row["source"], row["line"], row["column"], row["name"]))
    details = {
        "normalization": "absolute-root-elision+hex-address-elision-v1",
        "normalized_ast_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "normalized_ast_bytes": len(normalized.encode()),
        "selected_sources": relative_files,
        "resolved_calls": sorted(
            calls, key=lambda row: (row["source"], row["line"], row["column"])
        ),
        "selected_overloads": sorted(
            overloads, key=lambda row: (row["source"], row["line"], row["column"])
        ),
        "default_arguments": sorted(
            defaults, key=lambda row: (row["source"], row["line"], row["column"])
        ),
        "property_writes": sorted(
            property_writes, key=lambda row: (row["file"], row["line"], row["column"])
        ),
        "function_bodies": sorted(bodies, key=lambda row: (row["file"], row["line"])),
    }
    semantic = {
        "state": "complete",
        "protocol": "swiftc-dump-ast",
        "unstable_cli_used": False,
        "capabilities": {
            "declaration_identity": True,
            "direct_references": True,
            "direct_calls": True,
            "overload_selection": True,
            "default_arguments": True,
            "literal_property_writes": True,
            "static_function_bodies": True,
        },
        "query_count": len(queries),
        "selected_symbol_count": len(public_symbols),
        "wall_clock_budget_seconds": AST_TIMEOUT_SECONDS,
        "normalized_ast_sha256": details["normalized_ast_sha256"],
    }
    check = {
        "returncode": 0,
        "command": argv,
        "detail": "offline compiler AST extracted and normalized",
    }
    return semantic, public_symbols, occurrences, {"details": details, "check": check}


def _terminal(
    root: Path, target_name: str, configuration: str, queries: list[str]
) -> dict[str, Any]:
    snapshot = _snapshot(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "language": "swift",
        "analyzer": "swiftpm+swiftc-dump-ast",
        "status": "partial",
        "failure_kind": None,
        "failure_detail": None,
        "read_only": True,
        "identity": {
            "target_name": target_name,
            "configuration": configuration,
            "package_sha256": _sha256(root / "Package.swift")
            if (root / "Package.swift").is_file()
            else None,
        },
        "query_names": sorted(set(queries)),
        "query_plan_sha256": _canonical_hash(sorted(set(queries))),
        "tools": {},
        "native_checks": [],
        "source_inventory": [],
        "source_hashes": [
            {"path": path, "sha256": value}
            for path, value in sorted(snapshot.items())
            if not value.startswith("symlink:")
        ],
        "source_manifest_sha256": _manifest_hash(snapshot),
        "compiler": {"fresh_scratch": False, "selected_sources_compiled": False},
        "semantic": {
            "state": "not-run",
            "capabilities": {
                "declaration_identity": False,
                "direct_references": False,
                "direct_calls": False,
                "overload_selection": False,
                "default_arguments": False,
                "literal_property_writes": False,
                "static_function_bodies": False,
            },
        },
        "symbols": [],
        "definition_occurrences": [],
        "compiler_details": {},
        "limits": LIMITS,
    }


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    payload["fact_pack_sha256"] = _canonical_hash(without_hash)
    return payload


def _tool_terminal(payload: dict[str, Any], tools: dict[str, Any]) -> bool:
    payload["tools"] = tools
    order = ("swift", "swiftc", "swift_format")
    for name in order:
        state = tools[name]["state"]
        if state == "ready":
            continue
        payload["status"] = "failed" if state == "failed" else "partial"
        payload["failure_kind"] = tools[name]["failure_kind"]
        payload["failure_detail"] = tools[name].get("detail")
        return True
    return False


def collect(
    root: Path,
    target_name: str,
    queries: Iterable[str],
    *,
    configuration: str = "debug",
    swift: str | Path = "swift",
    swiftc: str | Path = "swiftc",
    swift_format: str | Path = "swift-format",
    check_product: str,
    expected_check: str,
    smoke_product: str,
    expected_smoke: str,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Collect one content-bound selected-configuration semantic pack."""
    root = Path(os.path.realpath(root.resolve(strict=True)))
    query_names = sorted(
        {query for query in queries if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", query)}
    )
    payload = _terminal(root, target_name, configuration, query_names)
    if configuration not in {"debug", "release"}:
        payload.update(status="failed", failure_kind="configuration_invalid")
        return _finalize(payload)
    if not (root / "Package.swift").is_file():
        payload.update(status="partial", failure_kind="swiftpm_manifest_missing")
        return _finalize(payload)
    paths = {
        "swift": _which(swift),
        "swiftc": _which(swiftc),
        "swift_format": _which(swift_format),
    }
    tools = {
        "swift": _probe_version(paths["swift"], root, "swift", exact=PINNED_SEMANTIC_SWIFT),
        "swiftc": _probe_version(
            paths["swiftc"], root, "swiftc", exact=PINNED_SEMANTIC_SWIFT
        ),
        "swift_format": _probe_version(paths["swift_format"], root, "swift_format"),
    }
    if _tool_terminal(payload, tools):
        return _finalize(payload)

    owned_state = state_dir is None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if owned_state:
        temporary = tempfile.TemporaryDirectory(prefix="swift-semantic-a3-")
        state = Path(temporary.name)
    else:
        state = Path(os.path.abspath(state_dir))
        if state.exists() and (state.is_symlink() or any(state.iterdir())):
            payload.update(status="partial", failure_kind="compiler_state_not_fresh")
            return _finalize(payload)
        state.mkdir(parents=True, exist_ok=True)
    payload["compiler"]["fresh_scratch"] = True
    try:
        for name in ("cache", "config", "security", "build"):
            (state / name).mkdir(parents=True, exist_ok=True)
        assert paths["swift"] and paths["swiftc"] and paths["swift_format"]
        base = _swiftpm_base(paths["swift"], root, state)
        dump_argv = [*base, "dump-package"]
        dump = _run(dump_argv, root)
        payload["native_checks"].append(_check("swiftpm-dump-package", dump_argv, dump))
        if dump.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_dump_failed",
                failure_detail=(dump.stderr or dump.stdout)[-2000:],
            )
            return _finalize(payload)
        try:
            manifest = json.loads(dump.stdout)
        except json.JSONDecodeError as exc:
            payload.update(
                status="failed", failure_kind="swiftpm_dump_invalid", failure_detail=str(exc)
            )
            return _finalize(payload)
        if manifest.get("dependencies"):
            payload.update(status="partial", failure_kind="swiftpm_dependencies_outside_contract")
            return _finalize(payload)
        if any(row.get("resources") or row.get("settings") for row in manifest.get("targets", [])):
            payload.update(
                status="partial", failure_kind="swiftpm_settings_or_resources_outside_contract"
            )
            return _finalize(payload)

        describe_argv = [*base, "describe", "--type", "json"]
        describe = _run(describe_argv, root)
        payload["native_checks"].append(_check("swiftpm-describe", describe_argv, describe))
        if describe.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_describe_failed",
                failure_detail=(describe.stderr or describe.stdout)[-2000:],
            )
            return _finalize(payload)
        try:
            description = json.loads(describe.stdout)
        except json.JSONDecodeError as exc:
            payload.update(
                status="failed", failure_kind="swiftpm_describe_invalid", failure_detail=str(exc)
            )
            return _finalize(payload)
        if any(
            row.get("type") not in {"library", "executable", "test"}
            for row in description.get("targets", [])
        ):
            payload.update(status="partial", failure_kind="swiftpm_target_shape_outside_contract")
            return _finalize(payload)
        try:
            inventory, semantic_files, selected = _inventory(root, description, target_name)
        except SwiftFactError as exc:
            payload.update(status="partial", failure_kind=exc.kind, failure_detail=str(exc))
            return _finalize(payload)
        payload["source_inventory"] = inventory
        before = _snapshot(root)
        payload["source_hashes"] = [
            {"path": path, "sha256": value}
            for path, value in sorted(before.items())
            if not value.startswith("symlink:")
        ]
        payload["source_manifest_sha256"] = _manifest_hash(before)
        target_graph = [
            {
                "name": row.get("name"),
                "type": row.get("type"),
                "path": row.get("path"),
                "sources": row.get("sources", []),
                "target_dependencies": row.get("target_dependencies", []),
            }
            for row in description.get("targets", [])
        ]
        payload["identity"] = {
            "package_name": description.get("name"),
            "package_sha256": _sha256(root / "Package.swift"),
            "tools_version": description.get("tools_version"),
            "target_name": target_name,
            "target_type": selected.get("type"),
            "target_path": selected.get("path"),
            "target_sources": selected.get("sources", []),
            "target_graph_sha256": _canonical_hash(target_graph),
            "configuration": configuration,
            "toolchain_sha256": _canonical_hash(tools),
        }

        build_argv = [
            str(paths["swift"]),
            "build",
            "--package-path",
            str(root),
            "--cache-path",
            str(state / "cache"),
            "--config-path",
            str(state / "config"),
            "--security-path",
            str(state / "security"),
            "--scratch-path",
            str(state / "build"),
            "--disable-dependency-cache",
            "--manifest-cache",
            "local",
            "--disable-netrc",
            "--disable-keychain",
            "--disable-prefetching",
            "--disable-automatic-resolution",
            "--configuration",
            configuration,
        ]
        build = _run(build_argv, root)
        payload["native_checks"].append(_check("swiftpm-build", build_argv, build))
        if build.returncode:
            payload.update(
                status="failed",
                failure_kind="swiftpm_build_failed",
                failure_detail=(build.stdout + build.stderr)[-3000:],
            )
            return _finalize(payload)
        payload["compiler"]["selected_sources_compiled"] = True

        parse_argv = [str(paths["swiftc"]), "-frontend", "-parse", "<each-selected-source>"]
        parse_runs = [
            _run([str(paths["swiftc"]), "-frontend", "-parse", str(source)], root)
            for source in semantic_files
        ]
        parse = subprocess.CompletedProcess(
            parse_argv,
            next((row.returncode for row in parse_runs if row.returncode), 0),
            "\n".join(row.stdout for row in parse_runs),
            "\n".join(row.stderr for row in parse_runs),
        )
        payload["native_checks"].append(_check("compiler-parse", parse_argv, parse))
        if parse.returncode:
            payload.update(
                status="failed",
                failure_kind="compiler_parse_failed",
                failure_detail=parse.stderr[-2000:],
            )
            return _finalize(payload)

        format_argv = [str(paths["swift_format"]), "lint", "--strict", "--recursive", "Sources"]
        formatted = _run(format_argv, root)
        payload["native_checks"].append(_check("swift-format-lint", format_argv, formatted))
        if formatted.returncode:
            payload.update(
                status="failed",
                failure_kind="swift_format_failed",
                failure_detail=(formatted.stdout + formatted.stderr)[-3000:],
            )
            return _finalize(payload)
        for identifier, product, expected in (
            ("direct-check", check_product, expected_check),
            ("executable-smoke", smoke_product, expected_smoke),
        ):
            executable = state / "build" / configuration / product
            run = _run([str(executable)], root, timeout=30)
            payload["native_checks"].append(_check(identifier, [str(executable)], run))
            if run.returncode or run.stdout.strip() != expected:
                payload.update(
                    status="failed",
                    failure_kind=f"{identifier.replace('-', '_')}_failed",
                    failure_detail=(run.stdout + run.stderr)[-2000:],
                )
                return _finalize(payload)

        roles = {row["path"]: row["role"] for row in inventory}
        compiler_files = [
            root / row["path"]
            for row in inventory
            if row["role"] == "selected-production" and row["included"]
        ]
        try:
            semantic, symbols, definition_occurrences, compiler_result = _compiler_facts(
                paths["swiftc"],
                root,
                target_name,
                compiler_files,
                roles,
                query_names,
            )
        except SwiftFactError as exc:
            semantic = {
                "state": "failed",
                "failure_kind": exc.kind,
                "detail": str(exc),
                "capabilities": payload["semantic"]["capabilities"],
                "wall_clock_budget_seconds": AST_TIMEOUT_SECONDS,
            }
            symbols = []
            definition_occurrences = []
            compiler_result = {
                "details": {},
                "check": {
                    "returncode": 1,
                    "command": [str(paths["swiftc"]), "-typecheck", "-dump-ast"],
                    "detail": str(exc),
                },
            }
        compiler_check = subprocess.CompletedProcess(
            compiler_result["check"]["command"],
            compiler_result["check"]["returncode"],
            compiler_result["check"].get("detail", ""),
            "",
        )
        payload["native_checks"].append(
            _check(
                "compiler-ast",
                compiler_result["check"]["command"],
                compiler_check,
            )
        )
        payload["semantic"] = semantic
        payload["symbols"] = symbols
        payload["definition_occurrences"] = definition_occurrences
        payload["compiler_details"] = compiler_result["details"]
        if semantic.get("state") != "complete":
            payload.update(
                status="failed",
                failure_kind=semantic.get("failure_kind", "compiler_ast_incomplete"),
                failure_detail=semantic.get("detail"),
            )
        else:
            payload.update(status="complete", failure_kind=None, failure_detail=None)
        after = _snapshot(root)
        if before != after:
            payload.update(
                status="failed",
                failure_kind="unexpected_source_mutation",
                failure_detail="native semantic analysis changed a non-artifact host file",
            )
        payload["source_preserved"] = before == after
        return _finalize(payload)
    finally:
        if temporary is not None:
            temporary.cleanup()


def load_fact_pack(
    path: Path,
    root: Path,
    target_name: str,
    required_queries: Iterable[str],
) -> dict[str, Any]:
    """Validate a supplied fact pack against source/configuration and query scope."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SwiftFactError("fact_pack_invalid", f"cannot read fact pack: {exc}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SwiftFactError("fact_pack_invalid", "incompatible Swift semantic fact pack")
    supplied = payload.get("fact_pack_sha256")
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    if supplied != _canonical_hash(without_hash):
        raise SwiftFactError("fact_pack_invalid", "Swift semantic fact pack hash does not verify")
    if payload.get("identity", {}).get("target_name") != target_name:
        raise SwiftFactError(
            "fact_pack_scope_mismatch", "fact pack target does not match consumer target"
        )
    missing = sorted(set(required_queries) - set(payload.get("query_names", [])))
    if missing:
        raise SwiftFactError(
            "fact_pack_scope_mismatch", f"fact pack misses required queries: {', '.join(missing)}"
        )
    root = Path(os.path.realpath(root.resolve(strict=True)))
    if _manifest_hash(_snapshot(root)) != payload.get("source_manifest_sha256"):
        raise SwiftFactError("fact_pack_stale", "fact pack source manifest is stale")
    for row in payload.get("source_hashes", []):
        source = root / row.get("path", "")
        if not source.is_file() or source.is_symlink() or _sha256(source) != row.get("sha256"):
            raise SwiftFactError("fact_pack_stale", f"fact pack is stale for {row.get('path')}")
    package = root / "Package.swift"
    if not package.is_file() or _sha256(package) != payload.get("identity", {}).get(
        "package_sha256"
    ):
        raise SwiftFactError("fact_pack_stale", "fact pack package configuration is stale")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--configuration", choices=("debug", "release"), default="debug")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--swift", default="swift")
    parser.add_argument("--swiftc", default="swiftc")
    parser.add_argument("--swift-format", default="swift-format")
    parser.add_argument("--check-product", required=True)
    parser.add_argument("--expected-check", required=True)
    parser.add_argument("--smoke-product", required=True)
    parser.add_argument("--expected-smoke", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
        output = safe_output(root, args.output, "reports/swift-semantic-facts")
        payload = collect(
            root,
            args.target_name,
            args.query,
            configuration=args.configuration,
            swift=args.swift,
            swiftc=args.swiftc,
            swift_format=args.swift_format,
            check_product=args.check_product,
            expected_check=args.expected_check,
            smoke_product=args.smoke_product,
            expected_smoke=args.expected_smoke,
            state_dir=args.state_dir,
        )
        atomic_json(output, payload)
        print(f"wrote Swift semantic fact pack: {output}")
        return 2 if payload["status"] == "failed" else 0
    except (OSError, SwiftFactError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
