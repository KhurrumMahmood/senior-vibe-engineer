#!/usr/bin/env python3
"""Map a C++20 subsystem from compiler-attributed project facts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SOURCE_SUFFIXES = {".cc", ".cpp", ".cxx", ".c++", ".C", ".ii"}
HEADER_SUFFIXES = {".hpp", ".hh", ".hxx", ".h++", ".ipp", ".inl", ".tpp", ".h", ".inc"}
CPP_SUFFIXES = SOURCE_SUFFIXES | HEADER_SUFFIXES
LIMITATIONS = [
    "the map is complete only for the exact recorded C++20 compile-command snapshot",
    "virtual and dynamic dispatch targets are not resolved",
    "reflection, runtime loading, and generated runtime registrations are not resolved",
    "template declarations and compiler-observed references are reported, but all possible template instantiations are not enumerated",
    "macro-generated declarations and inactive conditional-compilation branches are not mapped",
    "link-time optimization, ABI and object layout, modules, Objective-C++, CUDA, and other build variants are not analyzed",
]


class UserError(Exception):
    """Unsafe CLI input for which no artifact path can be trusted."""


class Terminal(Exception):
    """A terminal outcome that replaces both artifacts."""

    def __init__(self, status: str, kind: str, message: str, *, exit_code: int = 0, **facts):
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.exit_code = exit_code
        self.facts = facts


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(argv: list[str], *, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _has_symlink(path: Path, root: Path) -> bool:
    if not _inside(path, root):
        return True
    current = path
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _relative(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root).as_posix()


def _validate_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    root_input = Path(args.project_root)
    if not root_input.is_dir() or root_input.is_symlink():
        raise UserError("project root must be a regular directory")
    root = root_input.resolve()
    target_input = Path(args.target)
    target = target_input if target_input.is_absolute() else root / target_input
    target = Path(os.path.abspath(target))
    if not _inside(target, root):
        raise UserError("target must stay inside project root")
    output = Path(args.output).resolve(strict=False)
    evidence = Path(args.evidence).resolve(strict=False)
    docs = root / ".claude" / "docs" / "subsystems"
    reports = root / "reports" / "map"
    if output == docs or not _inside(output, docs):
        raise UserError("output must stay below .claude/docs/subsystems")
    if evidence == reports or not _inside(evidence, reports):
        raise UserError("evidence must stay below reports/map")
    if _has_symlink(output.parent, root) or _has_symlink(evidence.parent, root):
        raise UserError("artifact output must not traverse a symbolic link")
    return root, target, output, evidence


def _version(value: str, flag: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise UserError(f"{flag} must be a numeric major.minor[.patch] version")
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0])[:3])


def _resolve_tool(value: str) -> str | None:
    if "/" in value:
        path = Path(value)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(value)


def _tool_version(tool: str, root: Path) -> tuple[tuple[int, int, int] | None, str]:
    completed = _run([tool, "--version"], cwd=root)
    text = (completed.stdout + completed.stderr).strip()
    match = re.search(r"(?:clangd?|Apple clang)\s+(?:version\s+)?(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if completed.returncode != 0 or match is None:
        return None, text or "version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _role(relative: str) -> str:
    parts = Path(relative).parts
    if any(part in {"test", "tests", "testdata"} for part in parts):
        return "test"
    if any(part in {"generated", "gen"} for part in parts):
        return "generated"
    if "vendor" in parts:
        return "vendor"
    if any(part in {"build", ".native-build", "dist", "out"} for part in parts):
        return "build"
    return "source"


def _candidates(root: Path) -> list[Path]:
    rows = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in {".agents", ".claude", ".git", ".native-build", "reports"} for part in relative.parts):
            continue
        if (path.is_file() or path.is_symlink()) and path.suffix in CPP_SUFFIXES:
            rows.append(path)
    return sorted(rows)


def _eligible_sources(root: Path) -> list[Path]:
    return [
        path.resolve() for path in _candidates(root)
        if path.suffix in SOURCE_SUFFIXES and not path.is_symlink() and _role(path.relative_to(root).as_posix()) == "source"
    ]


def _manifest(root: Path) -> tuple[str, dict[str, str]]:
    files: dict[str, str] = {}
    digest = hashlib.sha256()
    for path in _candidates(root):
        relative = path.relative_to(root).as_posix()
        value = f"symlink:{os.readlink(path)}" if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()
        files[relative] = value
        digest.update(relative.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest(), files


def _analysis_argv(entry: dict, clangxx: str, *extra: str) -> list[str]:
    raw = entry["arguments"]
    source = entry["file"]
    filtered: list[str] = []
    skip = False
    for token in raw[1:]:
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


def _language_mode(arguments: list[str]) -> str | None:
    modes = []
    for index, token in enumerate(arguments):
        if token == "-x" and index + 1 < len(arguments):
            modes.append(arguments[index + 1])
        elif token.startswith("-x="):
            modes.append(token[3:])
        elif token.startswith("-x") and token != "-x":
            modes.append(token[2:])
    return modes[-1] if modes else None


def _is_cpp20(arguments: list[str], source: str) -> bool:
    standards = [token for token in arguments if token.startswith("-std=")]
    mode = _language_mode(arguments)
    driver = Path(arguments[0]).name
    return (
        bool(arguments) and "-c" in arguments and source in arguments
        and standards and standards[-1] == "-std=c++20"
        and (mode in {None, "c++", "c++-cpp-output"})
        and (mode is not None or driver in {"c++", "clang++", "g++"})
        and Path(source).suffix in SOURCE_SUFFIXES
    )


def _parse_dependencies(text: str, root: Path, source: Path) -> list[str]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise ValueError("dependency output has no target separator")
    result = []
    for item in shlex.split(flattened.split(":", 1)[1]):
        path = Path(item)
        path = path if path.is_absolute() else source.parent / path
        path = path.resolve(strict=False)
        if path != source and _inside(path, root) and path.suffix in HEADER_SUFFIXES:
            result.append(_relative(root, path))
    return list(dict.fromkeys(result))


def _compile_output(arguments: list[str], root: Path) -> str | None:
    for index, token in enumerate(arguments[:-1]):
        if token in {"-o", "--output"}:
            output = Path(arguments[index + 1])
            output = output if output.is_absolute() else root / output
            if _inside(output.resolve(strict=False), root):
                return _relative(root, output)
    return None


def _load_database(root: Path, clangxx: str) -> tuple[list[dict], dict[str, list[str]]]:
    database = root / "compile_commands.json"
    if not database.is_file():
        if (root / "compile_flags.txt").exists():
            raise Terminal("unsupported", "clangd_fallback_forbidden", "compile_flags.txt cannot substitute for a complete compile_commands.json.")
        raise Terminal("unsupported", "compile_database_missing", "A current, complete C++20 compile_commands.json is required; fallback flags are forbidden.")
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal("failed", "compile_database_malformed", f"Compilation database is malformed: {exc}", exit_code=2) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal("failed", "compile_database_malformed", "Compilation database must be a non-empty array of objects.", exit_code=2)
    actual: set[Path] = set()
    entries = []
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row.get("arguments"), list) or any(not isinstance(token, str) or not token for token in row.get("arguments", [])):
            raise Terminal("failed", "compile_database_malformed", "Each entry requires exact directory, file, and non-empty string arguments fields.", exit_code=2)
        directory = Path(row["directory"])
        source = Path(row["file"])
        if not directory.is_absolute() or directory.resolve(strict=False) != root or not source.is_absolute() or not _inside(source.resolve(strict=False), root):
            raise Terminal("unsupported", "compile_database_mismatched_directory", "Every compile command must name the current root and a source inside it.")
        if not _is_cpp20(row["arguments"], row["file"]):
            raise Terminal("unsupported", "compile_database_wrong_language", "Every entry must be an explicit C++20 compile command; C, Objective-C++, and fallback modes are rejected.")
        compiler = _resolve_tool(row["arguments"][0])
        if compiler is None or Path(compiler).resolve() != Path(clangxx).resolve():
            raise Terminal("unsupported", "compile_database_wrong_language", "Every entry must use the version-gated Clang++ executable.")
        resolved = source.resolve()
        if resolved in actual:
            raise Terminal("failed", "compile_database_malformed", "Duplicate translation-unit entries are forbidden.", exit_code=2)
        actual.add(resolved)
        entries.append({"directory": str(root), "file": str(resolved), "arguments": row["arguments"], "compile_output": _compile_output(row["arguments"], root)})
    expected = set(_eligible_sources(root))
    if actual != expected:
        raise Terminal(
            "partial", "compile_database_incomplete",
            f"Compilation database does not exactly cover eligible production C++ translation units (missing={sorted(_relative(root, p) for p in expected - actual)}, extra={sorted(_relative(root, p) for p in actual - expected)}).",
            expected_translation_units=sorted(_relative(root, p) for p in expected),
            database_translation_units=sorted(_relative(root, p) for p in actual),
        )
    dependencies: dict[str, list[str]] = {}
    for entry in sorted(entries, key=lambda row: row["file"]):
        source = Path(entry["file"])
        completed = _run(_analysis_argv(entry, clangxx, "-MM", "-MT", _relative(root, source)), cwd=root)
        if completed.returncode != 0:
            raise Terminal("failed", "clang_dependency_failed", completed.stderr.strip() or "Clang++ dependency emission failed.", exit_code=2)
        try:
            dependencies[_relative(root, source)] = _parse_dependencies(completed.stdout, root, source)
        except ValueError as exc:
            raise Terminal("failed", "clang_dependency_failed", str(exc), exit_code=2) from exc
    inputs = {root / "Makefile", *actual}
    for headers in dependencies.values():
        inputs.update(root / path for path in headers)
    existing = [path for path in inputs if path.is_file()]
    if database.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in existing):
        raise Terminal("partial", "compile_database_stale", "compile_commands.json is older than a build file, translation unit, or compiler-owned header.", dependency_inventory=dependencies)
    return sorted(entries, key=lambda row: row["file"]), dependencies


def _clangd_checks(clangd: str, root: Path, entries: list[dict]) -> list[dict]:
    checks = []
    for entry in entries:
        relative = _relative(root, Path(entry["file"]))
        completed = _run([clangd, f"--check={entry['file']}", f"--compile-commands-dir={root}", "--log=verbose"], cwd=root)
        combined = completed.stdout + completed.stderr
        attributed = "Compile command from CDB is" in combined
        checks.append({"translation_unit": relative, "process_exit": completed.returncode, "compile_database_attributed": attributed})
        if completed.returncode != 0:
            raise Terminal("failed", "clangd_check_failed", f"clangd check failed for {relative}.", exit_code=2, clangd_checks=checks, diagnostic_state="errors")
        if not attributed:
            raise Terminal("unsupported", "clangd_fallback_forbidden", f"clangd did not attribute {relative} to compile_commands.json; exit zero is insufficient.", clangd_checks=checks)
    return checks


def _location_file(node: dict, inherited: str | None) -> str | None:
    def extract(value: dict) -> str | None:
        if "file" in value:
            return value["file"]
        for key in ("spellingLoc", "expansionLoc"):
            if isinstance(value.get(key), dict) and value[key].get("file"):
                return value[key]["file"]
        return None
    return extract(node.get("loc", {})) or extract(node.get("range", {}).get("begin", {})) or inherited


def _line(node: dict) -> int | None:
    def extract(value: dict) -> int | None:
        if isinstance(value.get("line"), int):
            return value["line"]
        for key in ("spellingLoc", "expansionLoc"):
            if isinstance(value.get(key), dict) and isinstance(value[key].get("line"), int):
                return value[key]["line"]
        return None
    return extract(node.get("loc", {})) or extract(node.get("range", {}).get("begin", {}))


DECL_KINDS = {
    "NamespaceDecl": "namespace", "CXXRecordDecl": "class", "ClassTemplateDecl": "class-template",
    "FunctionDecl": "function", "FunctionTemplateDecl": "function-template", "CXXMethodDecl": "method",
    "CXXConstructorDecl": "constructor", "CXXDestructorDecl": "destructor", "EnumDecl": "enum",
    "EnumConstantDecl": "enumerator", "TypeAliasDecl": "type-alias", "TypedefDecl": "typedef", "VarDecl": "variable",
}
SCOPE_KINDS = {"NamespaceDecl", "CXXRecordDecl", "ClassTemplateDecl", "EnumDecl"}
CALLABLE_KINDS = {"FunctionDecl", "FunctionTemplateDecl", "CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl"}


def _ast_facts(ast: dict, root: Path, allowed: set[str], translation_unit: str) -> tuple[list[dict], list[dict]]:
    declarations: list[dict] = []
    raw_refs: list[dict] = []
    id_rows: dict[str, dict] = {}

    def walk(node: dict, inherited_file: str | None, scope: list[str], enclosing: dict | None, access: str, parent_kind: str | None) -> None:
        current_file = _location_file(node, inherited_file)
        relative = None
        if current_file:
            path = Path(current_file).resolve(strict=False)
            if _inside(path, root):
                relative = _relative(root, path)
        kind = node.get("kind")
        name = node.get("name")
        if kind == "ClassTemplateSpecializationDecl":
            return
        row = None
        skip_template_child = parent_kind in {"ClassTemplateDecl", "FunctionTemplateDecl"} and kind in {"CXXRecordDecl", "FunctionDecl", "CXXMethodDecl"}
        if kind in DECL_KINDS and name and relative in allowed and not node.get("isImplicit") and not skip_template_child:
            signature = node.get("type", {}).get("qualType")
            if kind in {"ClassTemplateDecl", "FunctionTemplateDecl"}:
                templated = next((child for child in node.get("inner", []) if child.get("kind") in {"CXXRecordDecl", "FunctionDecl", "CXXMethodDecl"}), None)
                signature = templated.get("type", {}).get("qualType") if templated else signature
            qualified = "::".join([*scope, name]) if scope else name
            row = {
                "id": node.get("id"), "name": name, "qualified_name": qualified,
                "kind": DECL_KINDS[kind], "file": relative, "line": _line(node) or 0,
                "signature": signature or "unavailable", "access": access,
                "definition": bool(node.get("completeDefinition")) or any(child.get("kind") in {"CompoundStmt", "CXXCtorInitializer"} for child in node.get("inner", [])),
                "template": kind in {"ClassTemplateDecl", "FunctionTemplateDecl"},
                "previous_decl": node.get("previousDecl"),
            }
            declarations.append(row)
            if row["id"]:
                id_rows[row["id"]] = row
        reference_id = None
        reference_name = None
        reference_kind = None
        if kind == "DeclRefExpr" and isinstance(node.get("referencedDecl"), dict):
            ref = node["referencedDecl"]
            reference_id, reference_name, reference_kind = ref.get("id"), ref.get("name"), ref.get("kind")
        elif kind == "MemberExpr":
            reference_id, reference_name, reference_kind = node.get("referencedMemberDecl"), node.get("name"), "member"
        if reference_id and enclosing and relative in allowed:
            raw_refs.append({
                "source": enclosing, "target_id": reference_id, "target_name": reference_name,
                "target_kind": reference_kind, "file": relative, "line": _line(node) or 0,
                "translation_unit": translation_unit,
            })
        next_enclosing = row if kind in CALLABLE_KINDS and row else enclosing
        next_scope = scope
        if kind in SCOPE_KINDS and name and row:
            next_scope = [*scope, name]
        child_access = "public" if kind == "CXXRecordDecl" and node.get("tagUsed") in {"struct", "union"} else ("private" if kind in {"CXXRecordDecl", "ClassTemplateDecl"} else access)
        current = child_access
        for child in node.get("inner", []):
            if child.get("kind") == "AccessSpecDecl":
                current = child.get("access", current)
                continue
            walk(child, current_file, next_scope, next_enclosing, current, kind)

    current_file = None
    for child in ast.get("inner", []):
        child_file = _location_file(child, current_file)
        walk(child, current_file, [], None, "public", None)
        current_file = child_file or current_file

    for ref in raw_refs:
        target = id_rows.get(ref.pop("target_id"))
        if target:
            ref["target"] = target
    for row in declarations:
        previous = id_rows.get(row.pop("previous_decl", None))
        if previous and "::" in previous["qualified_name"]:
            row["qualified_name"] = previous["qualified_name"]
    refs = [ref for ref in raw_refs if "target" in ref]
    return declarations, refs


def _identity(row: dict) -> tuple:
    return (row["qualified_name"], row["kind"], row["signature"], row["file"], row["line"])


def _inventory(root: Path, selected_tus: set[str], owned: set[str]) -> list[dict]:
    rows = []
    for path in _candidates(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            role = "symlink"
        elif _role(relative) != "source":
            role = _role(relative)
        elif path.suffix in HEADER_SUFFIXES:
            role = "public-header" if relative.startswith("include/") and relative in owned else ("private-header" if relative in owned else "ambiguous-header")
        else:
            role = "source"
        rows.append({"path": relative, "role": role, "included": relative in selected_tus or relative in owned, "sha256": None if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


def _build_graph(root: Path, make: str, entries: list[dict]) -> tuple[list[dict], list[dict], str]:
    if not (root / "Makefile").is_file():
        return [], [], "unavailable-no-Makefile"
    completed = _run([make, "-rRqp"], cwd=root)
    if completed.returncode not in {0, 1}:
        raise Terminal("failed", "make_database_failed", completed.stderr.strip() or "Make database query failed.", exit_code=2)
    compile_rows = []
    outputs = {entry["compile_output"]: _relative(root, Path(entry["file"])) for entry in entries if entry["compile_output"]}
    for output, source in sorted(outputs.items()):
        compile_rows.append({"target": output, "source": source, "relationship": "compile-command-output"})
    raw_edges = []
    for line in completed.stdout.splitlines():
        if not line or line[0].isspace() or line.startswith("#") or ":" not in line or "=" in line.split(":", 1)[0]:
            continue
        left, right = line.split(":", 1)
        targets = left.split()
        dependencies = [token for token in right.split() if token != "|"]
        for target in targets:
            target_path = Path(target)
            normalized_target = _relative(root, root / target_path) if not target_path.is_absolute() else (_relative(root, target_path) if _inside(target_path.resolve(strict=False), root) else None)
            if not normalized_target:
                continue
            for dependency in dependencies:
                dep_path = Path(dependency)
                normalized_dep = _relative(root, root / dep_path) if not dep_path.is_absolute() else (_relative(root, dep_path) if _inside(dep_path.resolve(strict=False), root) else None)
                if normalized_dep:
                    raw_edges.append({"target": normalized_target, "depends_on": normalized_dep, "relationship": "make-prerequisite"})
    interesting = set(outputs)
    changed = True
    while changed:
        changed = False
        for edge in raw_edges:
            if edge["depends_on"] in interesting and edge["target"] not in interesting:
                interesting.add(edge["target"])
                changed = True
    edges = [edge for edge in raw_edges if edge["target"] in interesting and (edge["depends_on"] in interesting or edge["depends_on"] in outputs.values())]
    targets = sorted({row["target"] for row in compile_rows} | {edge["target"] for edge in edges})
    return [{"path": path, "kind": "compile-output" if path in outputs else "make-target"} for path in targets], compile_rows + edges, "complete-make-database"


def _selected_entries(entries: list[dict], dependencies: dict[str, list[str]], target: Path, root: Path) -> list[dict]:
    selected = []
    for entry in entries:
        source = Path(entry["file"])
        dep_paths = [root / dep for dep in dependencies[_relative(root, source)]]
        if source == target or (target.is_dir() and _inside(source, target)) or any(dep == target or (target.is_dir() and _inside(dep, target)) for dep in dep_paths):
            selected.append(entry)
    return selected


def _render(payload: dict) -> str:
    lines = [
        "---", f"subsystem: {payload['name']}", "language: cpp", f"status: {payload['status']}",
        f"diagnostic_state: {payload.get('diagnostic_state', 'not-run')}", f"source_snapshot_sha256: {payload.get('source_snapshot_sha256', 'unavailable')}",
        f"regenerated: {payload['generated_at']}", "---", "", f"# {payload['name']}", "", f"Status: **{payload['status']}**", "",
    ]
    if payload.get("message"):
        lines.extend([payload["message"], ""])
    if payload["status"] == "complete":
        lines.extend(["## Files and compiler targets", ""])
        for row in payload["source_inventory"]:
            if row["included"]:
                lines.append(f"- `{row['path']}` — {row['role']}")
        for row in payload["build_targets"]:
            lines.append(f"- `{row['path']}` — {row['kind']}")
        lines.extend(["", "## Public surface", ""])
        for row in payload["public_surface"]:
            lines.append(f"- `{row['qualified_name']}` — {row['kind']} `{row['signature']}` at `{row['file']}:{row['line']}`")
        if not payload["public_surface"]:
            lines.append("- No public compiler-attributed declarations.")
        lines.extend(["", "## Dependency and reference edges", ""])
        for row in payload["dependency_edges"]:
            lines.append(f"- `{row['translation_unit']}` → `{row['header']}` — compiler include dependency")
        for row in payload["reference_edges"]:
            lines.append(f"- `{row['source']['qualified_name']}` → `{row['target']['qualified_name']}` — compiler-resolved reference at `{row['file']}:{row['line']}`")
        for row in payload["build_relationships"]:
            if "depends_on" in row:
                lines.append(f"- `{row['target']}` → `{row['depends_on']}` — {row['relationship']}")
            else:
                lines.append(f"- `{row['source']}` → `{row['target']}` — {row['relationship']}")
        lines.extend(["", "## Compiler diagnostics", "", f"- Diagnostic state: **{payload['diagnostic_state']}**.", "- Complete/partial/failed records analysis coverage; diagnostic state records whether the accepted compiler run was clean."])
    lines.extend(["", "## Explicit limitations", ""])
    lines.extend(f"- {item}." for item in payload["limitations"])
    lines.append("")
    return "\n".join(lines)


def _base(args: argparse.Namespace, root: Path, target: Path) -> dict:
    return {
        "schema_version": 1, "language": "cpp", "analyzer": "clang++-compile-db+dependency-output+ast-json",
        "name": args.name, "target": target.relative_to(root).as_posix() if target != root else ".",
        "generated_at": _now(), "limitations": LIMITATIONS,
    }


def _write(output: Path, evidence: Path, payload: dict) -> None:
    markdown = _render(payload)
    payload["artifact_hashes"] = {
        "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
        "evidence_payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    _atomic_text(output, markdown)
    _atomic_json(evidence, payload)


def _verify(root: Path, output: Path, evidence: Path) -> int:
    try:
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        hashes = payload.pop("artifact_hashes")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"map_cpp.py: artifact verification failed: {exc}", file=sys.stderr)
        return 2
    current_source, _files = _manifest(root)
    checks = {
        "source_snapshot": current_source == payload.get("source_snapshot_sha256"),
        "markdown": output.is_file() and hashlib.sha256(output.read_bytes()).hexdigest() == hashes.get("markdown_sha256"),
        "evidence_payload": hashlib.sha256(_canonical(payload)).hexdigest() == hashes.get("evidence_payload_sha256"),
        "complete_status": payload.get("status") == "complete",
    }
    if not all(checks.values()):
        print(f"map_cpp.py: stale or invalid artifacts: {json.dumps(checks, sort_keys=True)}", file=sys.stderr)
        return 2
    print(f"verified {output} and {evidence} against source snapshot {current_source}")
    return 0


def _execute(args: argparse.Namespace, root: Path, target: Path) -> dict:
    if _has_symlink(target, root):
        raise Terminal("unsupported", "unsafe_target", "C++ map target must not traverse a symbolic link.")
    if not target.exists() or not (target.is_file() or target.is_dir()):
        raise Terminal("unsupported", "target_missing", "C++ map target must be an existing file or directory.")
    if _role(_relative(root, target)) != "source":
        raise Terminal("unsupported", "excluded_target", "Generated, vendor, test, and build targets are excluded.")
    clangxx = _resolve_tool(args.clangxx)
    if clangxx is None:
        raise Terminal("unsupported", "clangxx_missing", "Clang++ 21+ is required.")
    clang_version, clang_probe = _tool_version(clangxx, root)
    if clang_version is None:
        raise Terminal("unsupported", "clangxx_version_unknown", clang_probe)
    if clang_version < args.minimum_clang:
        raise Terminal("unsupported", "clangxx_version_too_old", f"Clang++ {clang_version} is below {args.minimum_clang}.")
    clangd = _resolve_tool(args.clangd)
    if clangd is None:
        raise Terminal("unsupported", "clangd_missing", "clangd 21+ is required.")
    clangd_version, clangd_probe = _tool_version(clangd, root)
    if clangd_version is None:
        raise Terminal("unsupported", "clangd_version_unknown", clangd_probe)
    if clangd_version < args.minimum_clangd:
        raise Terminal("unsupported", "clangd_version_too_old", f"clangd {clangd_version} is below {args.minimum_clangd}.")
    make = _resolve_tool(args.make)
    if make is None:
        raise Terminal("unsupported", "make_missing", "Make is required to attribute build-target relationships.")
    before_digest, before_files = _manifest(root)
    entries, dependencies = _load_database(root, clangxx)
    selected_entries = _selected_entries(entries, dependencies, target, root)
    if not selected_entries:
        raise Terminal("unsupported", "target_has_no_translation_units", "Target has no C++20 translation unit in the compiler dependency closure.")
    checks = _clangd_checks(clangd, root, entries)
    allowed = set(dependencies) | {header for values in dependencies.values() for header in values}
    all_declarations: dict[tuple, dict] = {}
    all_references: list[dict] = []
    for entry in entries:
        translation_unit = _relative(root, Path(entry["file"]))
        completed = _run(_analysis_argv(entry, clangxx, "-Xclang", "-ast-dump=json", "-fsyntax-only"), cwd=root)
        if completed.returncode != 0:
            raise Terminal("failed", "clang_analysis_failed", completed.stderr.strip() or f"Clang++ AST analysis failed for {translation_unit}.", exit_code=2, diagnostic_state="errors")
        try:
            ast = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise Terminal("failed", "clang_ast_malformed", str(exc), exit_code=2, diagnostic_state="errors") from exc
        declarations, references = _ast_facts(ast, root, allowed, translation_unit)
        for row in declarations:
            all_declarations[_identity(row)] = row
        all_references.extend(references)
    selected_tus = {_relative(root, Path(entry["file"])) for entry in selected_entries}
    owned = {header for source in selected_tus for header in dependencies[source]}
    selected_files = selected_tus | owned
    declarations = sorted((row for row in all_declarations.values() if row["file"] in selected_files), key=lambda row: (row["file"], row["line"], row["qualified_name"], row["signature"]))
    public_map = {}
    for row in declarations:
        if row["file"] not in owned or not row["file"].startswith("include/") or row["access"] != "public" or row["kind"] in {"enumerator", "namespace", "variable"}:
            continue
        key = (row["qualified_name"], row["kind"], row["signature"])
        if key not in public_map or row["definition"]:
            public_map[key] = row
    public = sorted(public_map.values(), key=lambda row: (row["qualified_name"], row["kind"], row["signature"]))
    reference_map = {}
    for ref in all_references:
        source, destination = ref["source"], ref["target"]
        if destination["file"] not in selected_files or destination["kind"] in {"enumerator", "namespace", "variable"}:
            continue
        if source["file"] not in allowed:
            continue
        row = {"source": {key: source[key] for key in ("qualified_name", "kind", "signature", "file", "line")}, "target": {key: destination[key] for key in ("qualified_name", "kind", "signature", "file", "line")}, "file": ref["file"], "line": ref["line"], "translation_unit": ref["translation_unit"], "direction": "internal" if source["file"] in selected_files else "inbound"}
        reference_map[(row["source"]["qualified_name"], row["source"]["signature"], row["target"]["qualified_name"], row["target"]["signature"], row["file"], row["line"])] = row
    references = sorted(reference_map.values(), key=lambda row: (row["direction"], row["file"], row["line"], row["target"]["qualified_name"]))
    build_targets, build_relationships, build_state = _build_graph(root, make, entries)
    after_digest, after_files = _manifest(root)
    if before_files != after_files:
        raise Terminal("failed", "source_mutated", "Source fingerprints changed during read-only mapping.", exit_code=2)
    return {
        "status": "complete", "failure_kind": "none", "diagnostic_state": "clean",
        "message": "Complete for the exact current C++20 compile-command snapshot, compiler dependency closure, and compiler-observed static references.",
        "toolchain": {"clangxx": {"path": clangxx, "version": ".".join(map(str, clang_version)), "probe": clang_probe}, "clangd": {"path": clangd, "version": ".".join(map(str, clangd_version)), "probe": clangd_probe}, "make": {"path": make}},
        "compile_database": {"path": "compile_commands.json", "sha256": hashlib.sha256((root / "compile_commands.json").read_bytes()).hexdigest(), "state": "valid-current-complete-c++20-mode", "entries": len(entries)},
        "translation_units": sorted(selected_tus), "owned_headers": sorted(owned),
        "source_inventory": _inventory(root, selected_tus, owned), "declarations": declarations, "public_surface": public,
        "dependency_edges": [{"translation_unit": source, "header": header, "attribution": "clang++-MM"} for source in sorted(selected_tus) for header in dependencies[source]],
        "reference_edges": references, "build_targets": build_targets, "build_relationships": build_relationships,
        "clangd_checks": checks, "source_snapshot_sha256": before_digest,
        "source_fingerprints": {"before": before_digest, "after": after_digest, "files": before_files, "unchanged": True},
        "native_verification": "Run the host-owned restrictive C++20 build, tests, and executable smoke separately before and after mapping.",
        "completeness": {"compile_database": "complete", "translation_unit_inventory": "complete", "dependency_inventory": "complete", "declarations_public_surface_and_static_references": "complete", "build_target_relationships": build_state, "virtual_dynamic_dispatch": "unsupported", "reflection_runtime_loading": "unsupported", "all_template_instantiations": "unsupported"},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--clangxx", default="clang++")
    parser.add_argument("--clangd", default="clangd")
    parser.add_argument("--make", default="make")
    parser.add_argument("--minimum-clang", default="21.0.0")
    parser.add_argument("--minimum-clangd", default="21.0.0")
    parser.add_argument("--verify-artifacts", action="store_true")
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
            raise UserError("name must be lowercase kebab-case")
        args.minimum_clang = _version(args.minimum_clang, "--minimum-clang")
        args.minimum_clangd = _version(args.minimum_clangd, "--minimum-clangd")
        root, target, output, evidence = _validate_paths(args)
        if args.verify_artifacts:
            return _verify(root, output, evidence)
        base = _base(args, root, target)
        try:
            result = _execute(args, root, target)
        except Terminal as terminal:
            payload = {**base, "status": terminal.status, "failure_kind": terminal.kind, "message": str(terminal), **terminal.facts}
            _write(output, evidence, payload)
            return terminal.exit_code
        _write(output, evidence, {**base, **result})
        return 0
    except UserError as exc:
        print(f"map_cpp.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
