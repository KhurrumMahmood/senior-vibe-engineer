#!/usr/bin/env python3
"""Collect bounded C17 compile-database and Clang direct-reference facts."""

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


SCHEMA = "c-semantic-facts-v1"
INTERNAL_PARTS = frozenset({".agents", ".claude", ".engineering", ".git", "reports"})
LIMITS = [
    "complete only for the exact current C17 compile_commands.json snapshot and compiler-owned dependency closure",
    "function-pointer targets, callbacks, dynamic registration, dlsym/reflection-like lookup, and external consumers are unresolved",
    "macro expansion, macro-generated declarations, inactive preprocessor variants, and unrecorded build variants are unresolved",
    "pointer aliasing, unions, concurrency, volatile behavior, undefined behavior, ABI/layout, and whole-program runtime behavior are unresolved",
    "C++, Objective-C, CUDA, OpenCL, assembly, frameworks, generated sources, vendor sources, tests, and build outputs are excluded",
]


class Terminal(Exception):
    """A terminal fact-pack state with a stable failure kind."""

    def __init__(self, status: str, kind: str, message: str):
        super().__init__(message)
        self.status = status
        self.kind = kind


def _run(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=root, capture_output=True, text=True, check=False, timeout=90
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace one JSON artifact."""
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


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    rows = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in INTERNAL_PARTS for part in relative.parts):
            continue
        if (path.is_file() or path.is_symlink()) and path.suffix.lower() in {
            ".c",
            ".i",
            ".h",
            ".inc",
        }:
            rows.append(path)
    return sorted(rows)


def _eligible_translation_units(root: Path) -> list[Path]:
    return [
        path.resolve()
        for path in _candidate_paths(root)
        if path.suffix.lower() in {".c", ".i"}
        and not path.is_symlink()
        and _role(path.relative_to(root).as_posix()) == "production"
    ]


def _manifest(root: Path) -> tuple[str, list[dict[str, str]]]:
    rows = []
    for path in _candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        digest = (
            f"symlink:{os.readlink(path)}"
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        rows.append({"path": relative, "sha256": digest})
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
        return None, text or "clang version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _analysis_argv(entry: dict[str, Any], clang: str, *extra: str) -> list[str]:
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
    return [clang, *filtered, *extra, source]


def _is_c17(arguments: list[str], source: str) -> bool:
    if not arguments or "-c" not in arguments or source not in arguments:
        return False
    standards = [token for token in arguments if token.startswith("-std=")]
    if not standards or standards[-1] != "-std=c17":
        return False
    modes = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            modes.append(arguments[index + 1])
        elif token.startswith("-x="):
            modes.append(token[3:])
    if modes and modes[-1] not in {"c", "cpp-output", "c-cpp-output"}:
        return False
    return Path(source).suffix.lower() in {".c", ".i"}


def _dependencies(text: str, root: Path, source: Path) -> list[str]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise Terminal("failed", "clang_dependency_failed", "dependency output has no target")
    rows = []
    for token in shlex.split(flattened.split(":", 1)[1]):
        path = Path(token)
        path = path if path.is_absolute() else source.parent / path
        path = path.resolve(strict=False)
        if path == source or not _inside(path, root):
            continue
        if path.suffix.lower() in {".h", ".inc"}:
            rows.append(_relative(root, path))
    return list(dict.fromkeys(rows))


def _load_database(
    root: Path, clang: str
) -> tuple[list[dict[str, Any]], dict[str, list[str]], int]:
    database = root / "compile_commands.json"
    if not database.is_file():
        kind = "clang_fallback_forbidden" if (root / "compile_flags.txt").exists() else "compile_database_missing"
        raise Terminal("partial", kind, "a current complete compile_commands.json is required")
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal("failed", "compile_database_malformed", str(exc)) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal("failed", "compile_database_malformed", "database must be a non-empty object array")
    entries = []
    actual = set()
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row["arguments"], list):
            raise Terminal("failed", "compile_database_malformed", "entries require exact directory/file/arguments")
        if any(not isinstance(token, str) or not token for token in row["arguments"]):
            raise Terminal("failed", "compile_database_malformed", "arguments must be non-empty strings")
        directory = Path(row["directory"])
        source = Path(row["file"])
        if not directory.is_absolute() or directory.resolve(strict=False) != root:
            raise Terminal("partial", "compile_database_mismatched_directory", "database belongs to another root")
        if not source.is_absolute() or not _inside(source.resolve(strict=False), root):
            raise Terminal("partial", "compile_database_mismatched_directory", "source leaves project root")
        if not _is_c17(row["arguments"], row["file"]):
            raise Terminal("partial", "compile_database_non_c17", "every entry must be explicit C17")
        compiler = _resolve_tool(row["arguments"][0])
        if compiler is None or Path(compiler).resolve() != Path(clang).resolve():
            raise Terminal("partial", "compile_database_compiler_mismatch", "database must use selected Clang")
        resolved = source.resolve()
        if resolved in actual:
            raise Terminal("failed", "compile_database_malformed", "duplicate translation unit")
        actual.add(resolved)
        entries.append({"directory": str(root), "file": str(resolved), "arguments": row["arguments"]})
    expected = set(_eligible_translation_units(root))
    if actual != expected:
        raise Terminal(
            "partial",
            "compile_database_incomplete",
            f"database mismatch: missing={sorted(_relative(root, p) for p in expected-actual)} extra={sorted(_relative(root, p) for p in actual-expected)}",
        )
    dependency_rows = {}
    for entry in sorted(entries, key=lambda row: row["file"]):
        source = Path(entry["file"])
        result = _run(_analysis_argv(entry, clang, "-MM", "-MT", _relative(root, source)), root)
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


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, max(offset, 0)) + 1


def _source_slice(node: dict[str, Any], source: str) -> str:
    begin = node.get("range", {}).get("begin", {})
    end = node.get("range", {}).get("end", {})
    start = begin.get("offset")
    finish = end.get("offset")
    if not isinstance(start, int) or not isinstance(finish, int):
        return ""
    return source[start : finish + int(end.get("tokLen", 1))]


def _is_macro_expansion(node: dict[str, Any]) -> bool:
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


def _ast_facts(ast: dict[str, Any], root: Path, source_path: Path) -> dict[str, list[dict[str, Any]]]:
    source_text = source_path.read_text(encoding="utf-8")
    declarations = []
    references = []
    compounds = []
    state_operations = []
    boundaries = []
    current_top_file: str | None = None

    def walk(
        node: dict[str, Any],
        file_hint: str | None,
        owner: str | None,
        function: str | None,
        parents: tuple[str, ...],
    ) -> None:
        raw_file = _location_file(node, file_hint)
        kind = node.get("kind")
        resolved_file = None
        if raw_file:
            candidate = Path(raw_file).resolve(strict=False)
            if _inside(candidate, root):
                resolved_file = _relative(root, candidate)
        relative = resolved_file or file_hint
        name = node.get("name")
        location = node.get("loc", {})
        begin = node.get("range", {}).get("begin", {})
        offset = location.get("offset", begin.get("offset"))
        line = location.get("line", begin.get("line"))
        if relative == _relative(root, source_path) and isinstance(offset, int):
            line = _line_for_offset(source_text, offset)

        next_owner = owner
        if kind in {"RecordDecl", "EnumDecl"} and name:
            next_owner = name
        next_function = function
        if kind == "FunctionDecl" and name:
            next_function = name

        declaration_kinds = {
            "FunctionDecl": "function",
            "VarDecl": "variable",
            "FieldDecl": "field",
            "TypedefDecl": "typedef",
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
            definition = kind != "FunctionDecl" or any(
                child.get("kind") == "CompoundStmt" for child in node.get("inner", [])
            )
            declarations.append(
                {
                    "ast_id": node.get("id"),
                    "name": name,
                    "kind": declaration_kinds[kind],
                    "file": relative,
                    "line": line,
                    "type": node.get("type", {}).get("qualType"),
                    "owner": owner if kind == "FieldDecl" else None,
                    "linkage": "internal" if node.get("storageClass") == "static" else "external",
                    "definition": definition,
                    "macro_expansion": _is_macro_expansion(node),
                }
            )

        if kind == "DeclRefExpr" and relative and isinstance(line, int):
            target = node.get("referencedDecl", {})
            references.append(
                {
                    "name": target.get("name"),
                    "target_ast_id": target.get("id"),
                    "target_kind": target.get("kind"),
                    "target_type": target.get("type", {}).get("qualType"),
                    "file": relative,
                    "line": line,
                    "function": function,
                    "context": "direct_call" if "CallExpr" in parents[-3:] else "value_or_address",
                    "macro_expansion": _is_macro_expansion(node),
                }
            )

        if kind == "MemberExpr" and relative and isinstance(line, int):
            references.append(
                {
                    "name": name,
                    "target_ast_id": node.get("referencedMemberDecl"),
                    "target_kind": "FieldDecl",
                    "target_type": node.get("type", {}).get("qualType"),
                    "file": relative,
                    "line": line,
                    "function": function,
                    "context": "member_reference",
                    "macro_expansion": _is_macro_expansion(node),
                }
            )

        if kind == "BinaryOperator" and node.get("opcode") == "=" and relative:
            members = list(_descendants(node, {"MemberExpr"}))
            strings = list(_descendants(node, {"StringLiteral"}))
            if len(members) == 1 and len(strings) == 1:
                literal = strings[0].get("value")
                if isinstance(literal, str) and literal.startswith('"'):
                    try:
                        literal = json.loads(literal)
                    except json.JSONDecodeError:
                        pass
                state_operations.append(
                    {
                        "field_ast_id": members[0].get("referencedMemberDecl"),
                        "field": members[0].get("name"),
                        "literal": literal,
                        "file": relative,
                        "line": line,
                        "function": function,
                        "operation": "direct_assignment",
                        "macro_expansion": _is_macro_expansion(node)
                        or any(_is_macro_expansion(item) for item in [*members, *strings]),
                    }
                )

        if kind == "CompoundLiteralExpr" and relative == _relative(root, source_path):
            snippet = _source_slice(node, source_text)
            type_name = node.get("type", {}).get("qualType")
            fields = sorted(set(re.findall(r"\.([A-Za-z_]\w*)\s*=", snippet)))
            compounds.append(
                {
                    "record": type_name,
                    "fields": fields,
                    "file": relative,
                    "line": line,
                    "function": function,
                    "context": "return" if "ReturnStmt" in parents else "initializer",
                    "snippet": " ".join(snippet.split())[:240],
                    "macro_expansion": _is_macro_expansion(node),
                }
            )

        if kind == "CallExpr" and relative:
            refs = list(_descendants(node, {"DeclRefExpr"}))
            if refs:
                target = refs[0].get("referencedDecl", {})
                if target.get("kind") != "FunctionDecl":
                    boundaries.append(
                        {
                            "kind": "function_pointer_call",
                            "file": relative,
                            "line": line,
                            "function": function,
                            "name": target.get("name"),
                        }
                    )

        for child in node.get("inner", []):
            walk(child, relative, next_owner, next_function, (*parents, kind or ""))

    for child in ast.get("inner", []):
        current_top_file = _location_file(child, current_top_file)
        top_hint = None
        if current_top_file:
            candidate = Path(current_top_file).resolve(strict=False)
            if _inside(candidate, root):
                top_hint = _relative(root, candidate)
        walk(child, top_hint, None, None, ("TranslationUnitDecl",))
    return {
        "declarations": declarations,
        "direct_references": references,
        "compound_literals": compounds,
        "state_operations": state_operations,
        "boundaries": boundaries,
    }


def _macro_boundaries(root: Path, included: set[str]) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(included):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            match = re.match(r"\s*#\s*(define|if|ifdef|ifndef|elif|else|endif)\b(.*)", line)
            if match:
                rows.append(
                    {
                        "kind": "macro_or_inactive_variant",
                        "file": relative,
                        "line": line_number,
                        "directive": match.group(1),
                        "syntax": line.strip()[:180],
                    }
                )
    return rows


def _empty(status: str, kind: str, message: str) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA,
        "language": "c",
        "status": status,
        "failure_kind": kind,
        "message": message,
        "read_only": True,
        "compile_database": {"state": "rejected"},
        "source_inventory": [],
        "declarations": [],
        "direct_references": [],
        "compound_literals": [],
        "state_operations": [],
        "boundaries": [],
        "limits": LIMITS,
    }
    payload["fact_pack_sha256"] = _hash(payload)
    return payload


def collect(project_root: Path, *, clang: str = "clang") -> dict[str, Any]:
    """Collect one project-wide fact pack or a fresh terminal replacement."""
    root = project_root.resolve()
    if not root.is_dir() or project_root.is_symlink():
        return _empty("partial", "unsafe_project_root", "project root must be a regular directory")
    selected_clang = _resolve_tool(clang)
    if selected_clang is None:
        return _empty("partial", "clang_missing", "Clang 21+ is required")
    version, probe = _version(selected_clang, root)
    if version is None:
        return _empty("partial", "clang_version_unknown", probe)
    if version < (21, 0, 0):
        return _empty("partial", "clang_version_too_old", f"Clang {version} is below 21.0.0")
    before_sha, before_files = _manifest(root)
    try:
        entries, dependencies, input_mtime = _load_database(root, selected_clang)
        groups = {
            "declarations": [],
            "direct_references": [],
            "compound_literals": [],
            "state_operations": [],
            "boundaries": [],
        }
        for entry in entries:
            result = _run(
                _analysis_argv(entry, selected_clang, "-Xclang", "-ast-dump=json", "-fsyntax-only"),
                root,
            )
            if result.returncode:
                raise Terminal("failed", "clang_ast_failed", result.stderr.strip() or "Clang AST failed")
            try:
                ast = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise Terminal("failed", "clang_ast_malformed", str(exc)) from exc
            facts = _ast_facts(ast, root, Path(entry["file"]))
            for key in groups:
                groups[key].extend(facts[key])
    except Terminal as exc:
        return _empty(exc.status, exc.kind, str(exc))
    owned_headers = {item for paths in dependencies.values() for item in paths}
    selected_tus = {_relative(root, Path(entry["file"])) for entry in entries}
    inventory = []
    for path in _candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        role = "symlink" if path.is_symlink() else _role(relative)
        included = relative in selected_tus or relative in owned_headers
        if role == "production" and path.suffix.lower() in {".h", ".inc"} and not included:
            role = "ambiguous-header"
        inventory.append({"path": relative, "role": role, "included": included})
    included = selected_tus | owned_headers
    groups["boundaries"].extend(_macro_boundaries(root, included))
    after_sha, after_files = _manifest(root)
    if before_files != after_files:
        return _empty("failed", "source_mutated", "source changed during read-only collection")
    for key in groups:
        groups[key] = list(
            {
                json.dumps(row, sort_keys=True, ensure_ascii=False): row for row in groups[key]
            }.values()
        )
        groups[key].sort(key=lambda row: (row.get("file", ""), row.get("line") or 0, row.get("name", "")))
    payload = {
        "schema_version": SCHEMA,
        "language": "c",
        "status": "complete",
        "failure_kind": None,
        "read_only": True,
        "toolchain": {"clang": {"path": selected_clang, "version": ".".join(map(str, version)), "probe": probe}},
        "compile_database": {
            "path": "compile_commands.json",
            "state": "valid-current-complete-c17",
            "sha256": hashlib.sha256((root / "compile_commands.json").read_bytes()).hexdigest(),
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
    *, project_root: Path, facts: Path | None, clang: str = "clang"
) -> dict[str, Any]:
    """Load a current fact pack, or collect one when no pack was supplied."""
    root = project_root.resolve()
    if facts is None:
        return collect(root, clang=clang)
    path = facts if facts.is_absolute() else root / facts
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _empty("partial", "c_semantic_fact_pack_invalid", str(exc))
    if payload.get("schema_version") != SCHEMA or payload.get("status") != "complete":
        return _empty("partial", "c_semantic_fact_pack_incomplete", "fact pack is not complete C evidence")
    current_sha, _ = _manifest(root)
    database = root / "compile_commands.json"
    if current_sha != payload.get("source_manifest_sha256") or not database.is_file():
        return _empty("partial", "c_semantic_fact_pack_stale", "source or database changed")
    database_sha = hashlib.sha256(database.read_bytes()).hexdigest()
    if database_sha != payload.get("compile_database", {}).get("sha256"):
        return _empty("partial", "c_semantic_fact_pack_stale", "compile database changed")
    current_inputs = [root / "Makefile"]
    current_inputs.extend(
        root / path for path in payload.get("compile_database", {}).get("translation_units", [])
    )
    for paths in payload.get("dependency_closure", {}).values():
        current_inputs.extend(root / path for path in paths)
    newest_current_input = max(
        (path.stat().st_mtime_ns for path in current_inputs if path.is_file()), default=0
    )
    if database.stat().st_mtime_ns < newest_current_input:
        return _empty("partial", "c_semantic_fact_pack_stale", "compile database is stale")
    return payload


def in_target(row: dict[str, Any], root: Path, target: str) -> bool:
    """Return whether a fact row belongs to the selected regular target."""
    selected = (root / target).resolve(strict=False)
    path = (root / row.get("file", row.get("path", ""))).resolve(strict=False)
    return path == selected or (selected.is_dir() and _inside(path, selected))


def safe_output(root: Path, supplied: Path, report_root: str) -> Path:
    """Contain a report path below one lens-owned report directory."""
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
    parser.add_argument("--clang", default="clang")
    return parser


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clang", default="clang")
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = safe_output(root, args.output, "reports/c-semantic")
    except ValueError as exc:
        parser.error(str(exc))
    payload = collect(root, clang=args.clang)
    atomic_json(output, payload)
    return 0 if payload["status"] == "complete" else (1 if payload["status"] == "failed" else 2)


if __name__ == "__main__":
    raise SystemExit(_cli())
