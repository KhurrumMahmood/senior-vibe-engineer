#!/usr/bin/env python3
"""Map a bounded C subsystem from a trustworthy Clang compilation database."""
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


INTERNAL_PARTS = {".agents", ".claude", ".engineering", ".git", "reports"}
LIMITATIONS = [
    "macro expansion and macro-generated declarations are not mapped",
    "inactive preprocessor branches are not mapped",
    "Function-pointer call targets are not resolved",
    "ABI and object layout are not analyzed",
    "arbitrary build variants beyond the recorded compile commands are not analyzed",
    "C++, Objective-C, CUDA, OpenCL, assembly, and framework semantics are excluded",
]


class UserError(Exception):
    """Unsafe or malformed CLI input that must not write artifacts."""


class Terminal(Exception):
    """A safe terminal outcome that must replace both final artifacts."""

    def __init__(self, status: str, kind: str, message: str, *, exit_code: int = 0, **facts):
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.exit_code = exit_code
        self.facts = facts


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(argv: list[str], *, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
        )
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
    docs = root / ".engineering" / "docs" / "subsystems"
    reports = root / "reports" / "map"
    if output == docs or not _inside(output, docs):
        raise UserError("output must stay below .engineering/docs/subsystems")
    if evidence == reports or not _inside(evidence, reports):
        raise UserError("evidence must stay below reports/map")
    if _has_symlink(output.parent, root) or _has_symlink(evidence.parent, root):
        raise UserError("artifact output must not traverse a symbolic link")
    return root, target, output, evidence


def _version_argument(value: str, flag: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise UserError(f"{flag} must be a numeric major.minor[.patch] version")
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0])[:3])


def _resolve_tool(value: str) -> str | None:
    if "/" in value:
        path = Path(value)
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(value)


def _tool_version(tool: str, label: str, root: Path) -> tuple[tuple[int, int, int] | None, str]:
    completed = _run([tool, "--version"], cwd=root)
    text = (completed.stdout + completed.stderr).strip()
    match = re.search(r"(?:clangd?|Apple clang)\s+(?:version\s+)?(\d+)\.(\d+)(?:\.(\d+))?", text, re.I)
    if completed.returncode != 0 or match is None:
        return None, text or f"{label} version probe failed"
    return tuple(int(part or 0) for part in match.groups()), text.splitlines()[0]


def _relative(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root).as_posix()


def _base_role(relative: str) -> str:
    parts = Path(relative).parts
    if any(part in {"test", "tests", "testdata"} for part in parts):
        return "test"
    if "generated" in parts or "gen" in parts:
        return "generated"
    if "vendor" in parts:
        return "vendor"
    if any(part in {"build", ".native-build", "dist", "out"} for part in parts):
        return "build"
    return "source"


def _candidate_paths(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if not any(part in INTERNAL_PARTS for part in path.relative_to(root).parts)
        and (path.is_file() or path.is_symlink())
        and path.suffix.lower() in {".c", ".i", ".h", ".inc"}
    )


def _eligible_translation_units(root: Path) -> list[Path]:
    return [
        path.resolve() for path in _candidate_paths(root)
        if path.suffix.lower() in {".c", ".i"}
        and not path.is_symlink()
        and _base_role(path.relative_to(root).as_posix()) == "source"
    ]


def _selected(path: Path, target: Path) -> bool:
    return path == target or (target.is_dir() and _inside(path, target))


def _source_digest(root: Path) -> tuple[str, dict[str, str]]:
    files = {}
    digest = hashlib.sha256()
    for path in _candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        value = f"symlink:{os.readlink(path)}" if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()
        files[relative] = value
        digest.update(relative.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest(), files


def _analysis_argv(entry: dict, clang: str, *extra: str) -> list[str]:
    raw = entry["arguments"]
    source = entry["file"]
    filtered = []
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
    return [clang, *filtered, *extra, source]


def _is_c_command(arguments: list[str], source: str) -> bool:
    if "-c" not in arguments or "-std=c17" not in arguments or source not in arguments:
        return False
    joined = " ".join(arguments)
    if re.search(r"(?:^|\s)-std=(?:gnu\+\+|c\+\+)", joined):
        return False
    for index, token in enumerate(arguments):
        language = token[3:] if token.startswith("-x=") else None
        if token == "-x" and index + 1 < len(arguments):
            language = arguments[index + 1]
        if language and language not in {"c", "cpp-output", "c-cpp-output"}:
            return False
    return Path(source).suffix.lower() in {".c", ".i"}


def _parse_dependencies(text: str, root: Path, source: Path) -> list[str]:
    flattened = text.replace("\\\n", " ")
    if ":" not in flattened:
        raise ValueError("dependency output has no target separator")
    dependencies = shlex.split(flattened.split(":", 1)[1])
    result = []
    for item in dependencies:
        path = Path(item)
        path = path if path.is_absolute() else source.parent / path
        path = path.resolve(strict=False)
        if path == source or not _inside(path, root):
            continue
        if path.suffix.lower() in {".h", ".inc"}:
            result.append(_relative(root, path))
    return list(dict.fromkeys(result))


def _load_database(root: Path, clang: str) -> tuple[list[dict], dict[str, list[str]]]:
    database = root / "compile_commands.json"
    if not database.is_file():
        if (root / "compile_flags.txt").exists():
            raise Terminal(
                "unsupported", "clangd_fallback_forbidden",
                "compile_flags.txt cannot substitute for a complete compile_commands.json.",
            )
        raise Terminal(
            "unsupported", "compile_database_missing",
            "A trustworthy compile_commands.json is required; clangd fallback is forbidden.",
        )
    try:
        payload = json.loads(database.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Terminal("failed", "compile_database_malformed", f"Compilation database is malformed: {exc}", exit_code=2) from exc
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise Terminal("failed", "compile_database_malformed", "Compilation database must be a non-empty JSON array of objects.", exit_code=2)
    entries = []
    actual = set()
    for row in payload:
        if set(row) != {"directory", "file", "arguments"} or not isinstance(row["arguments"], list) or any(not isinstance(item, str) for item in row["arguments"]):
            raise Terminal("failed", "compile_database_malformed", "Each entry requires exact directory, file, and string arguments fields.", exit_code=2)
        directory = Path(row["directory"])
        source = Path(row["file"])
        if not directory.is_absolute() or directory.resolve(strict=False) != root:
            raise Terminal("unsupported", "compile_database_mismatched_directory", "Every compile command directory must name the current project root.")
        if not source.is_absolute() or not _inside(source.resolve(strict=False), root):
            raise Terminal("unsupported", "compile_database_mismatched_directory", "Every compile command source must stay inside the current project root.")
        if not _is_c_command(row["arguments"], row["file"]):
            raise Terminal("unsupported", "compile_database_non_c_command", "Every entry must be an explicit C17 compile command; C++ and fallback commands are rejected.")
        compiler = _resolve_tool(row["arguments"][0])
        if compiler is None or Path(compiler).resolve() != Path(clang).resolve():
            raise Terminal("unsupported", "compile_database_non_c_command", "Every entry must use the version-gated Clang executable.")
        resolved = source.resolve()
        if resolved in actual:
            raise Terminal("failed", "compile_database_malformed", "Duplicate translation-unit entries are not allowed.", exit_code=2)
        actual.add(resolved)
        entries.append({"directory": str(root), "file": str(resolved), "arguments": row["arguments"]})
    expected = set(_eligible_translation_units(root))
    if actual != expected:
        missing = sorted(_relative(root, path) for path in expected - actual)
        extra = sorted(_relative(root, path) for path in actual - expected)
        raise Terminal(
            "partial", "compile_database_incomplete",
            f"Compilation database does not exactly cover eligible C translation units (missing={missing}, extra={extra}).",
            expected_translation_units=sorted(_relative(root, path) for path in expected),
            database_translation_units=sorted(_relative(root, path) for path in actual),
        )
    dependencies = {}
    for entry in sorted(entries, key=lambda item: item["file"]):
        source = Path(entry["file"])
        completed = _run(_analysis_argv(entry, clang, "-MM", "-MT", _relative(root, source)), cwd=root)
        if completed.returncode != 0:
            raise Terminal("failed", "clang_dependency_failed", completed.stderr.strip() or "Clang dependency emission failed.", exit_code=2)
        try:
            dependencies[_relative(root, source)] = _parse_dependencies(completed.stdout, root, source)
        except ValueError as exc:
            raise Terminal("failed", "clang_dependency_failed", str(exc), exit_code=2) from exc
    inputs = {root / "Makefile", *actual}
    for paths in dependencies.values():
        inputs.update(root / path for path in paths)
    existing = [path for path in inputs if path.is_file()]
    if existing and database.stat().st_mtime_ns < max(path.stat().st_mtime_ns for path in existing):
        raise Terminal(
            "partial", "compile_database_stale",
            "compile_commands.json is older than a Makefile, translation unit, or compiler-owned header.",
            dependency_inventory=dependencies,
        )
    return sorted(entries, key=lambda item: item["file"]), dependencies


def _clangd_check(clangd: str, root: Path, entries: list[dict]) -> list[dict]:
    checks = []
    for entry in entries:
        relative = _relative(root, Path(entry["file"]))
        completed = _run([
            clangd, f"--check={entry['file']}", f"--compile-commands-dir={root}", "--log=verbose",
        ], cwd=root)
        combined = completed.stdout + completed.stderr
        attributed = "Compile command from CDB is" in combined
        checks.append({
            "translation_unit": relative,
            "process_exit": completed.returncode,
            "compile_database_attributed": attributed,
        })
        if completed.returncode != 0:
            raise Terminal("failed", "clangd_check_failed", f"clangd check failed for {relative}.", exit_code=2, clangd_checks=checks)
        if not attributed:
            raise Terminal(
                "unsupported", "clangd_fallback_forbidden",
                f"clangd did not attribute {relative} to the compilation database; process exit zero is insufficient.",
                clangd_checks=checks,
            )
    return checks


def _node_file(node: dict, current: str | None) -> str | None:
    loc = node.get("loc", {})
    begin = node.get("range", {}).get("begin", {})
    return loc.get("file") or begin.get("file") or current


def _declarations(ast: dict, root: Path, allowed: set[str]) -> list[dict]:
    kind_names = {
        "FunctionDecl": "function", "VarDecl": "variable", "TypedefDecl": "typedef",
        "RecordDecl": "record", "EnumDecl": "enum",
    }
    rows = []
    current_file = None
    for node in ast.get("inner", []):
        current_file = _node_file(node, current_file)
        kind = kind_names.get(node.get("kind"))
        name = node.get("name")
        line = node.get("loc", {}).get("line") or node.get("range", {}).get("begin", {}).get("line")
        if not kind or not name or not isinstance(line, int) or current_file is None or node.get("isImplicit"):
            continue
        path = Path(current_file).resolve(strict=False)
        if not _inside(path, root):
            continue
        relative = _relative(root, path)
        if relative not in allowed:
            continue
        row = {
            "name": name,
            "kind": kind,
            "file": relative,
            "line": line,
            "type": node.get("type", {}).get("qualType", "unavailable"),
            "linkage": "internal" if node.get("storageClass") == "static" else "external",
        }
        if kind == "function":
            row["definition"] = any(child.get("kind") == "CompoundStmt" for child in node.get("inner", []))
        rows.append(row)
    unique = {(row["file"], row["line"], row["kind"], row["name"]): row for row in rows}
    return sorted(unique.values(), key=lambda row: (row["file"], row["line"], row["kind"], row["name"]))


def _inventory(root: Path, selected_tus: list[str], owned: set[str]) -> list[dict]:
    rows = []
    for path in _candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            role = "symlink"
        else:
            base = _base_role(relative)
            if base != "source":
                role = base
            elif path.suffix.lower() in {".h", ".inc"}:
                if relative not in owned:
                    role = "ambiguous-header"
                elif relative.startswith("include/"):
                    role = "public-header"
                else:
                    role = "private-header"
            else:
                role = "source"
        rows.append({
            "path": relative,
            "role": role,
            "included": relative in selected_tus or relative in owned,
        })
    return rows


def _render(payload: dict) -> str:
    lines = [
        "---", f"subsystem: {payload['name']}", "language: c",
        f"status: {payload['status']}", f"regenerated: {payload['generated_at']}",
        "---", "", f"# {payload['name']}", "", f"Status: **{payload['status']}**", "",
    ]
    if payload.get("message"):
        lines.extend([payload["message"], ""])
    if payload["status"] == "complete":
        lines.extend(["## Translation units and headers", ""])
        lines.extend(f"- Translation unit: `{path}`" for path in payload["translation_units"])
        lines.extend(f"- Compiler-owned header: `{path}`" for path in payload["owned_headers"])
        lines.extend(f"- Ambiguous orphan header: `{path}`" for path in payload["ambiguous_headers"])
        lines.extend(["", "## Public surface", ""])
        if payload["public_surface"]:
            lines.extend(
                f"- `{row['name']}` — {row['kind']} at `{row['file']}:{row['line']}`"
                for row in payload["public_surface"]
            )
        else:
            lines.append("- No public declarations.")
        lines.extend(["", "## Conservative dependency edges", ""])
        if payload["dependency_edges"]:
            lines.extend(
                f"- `{row['header']}` → `{row['translation_unit']}` (compiler dependency)"
                for row in payload["dependency_edges"]
            )
        else:
            lines.append("- No project-header dependency edges.")
    lines.extend(["", "## Explicit limitations", ""])
    lines.extend(f"- {item}." for item in payload["limitations"])
    lines.append("")
    return "\n".join(lines)


def _base_payload(args: argparse.Namespace, root: Path, target: Path) -> dict:
    return {
        "schema_version": 1,
        "language": "c",
        "analyzer": "clang-compile-db+dependency-output+ast-json",
        "name": args.name,
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "generated_at": _now(),
        "limitations": LIMITATIONS,
    }


def _write(output: Path, evidence: Path, payload: dict) -> None:
    _atomic_json(evidence, payload)
    _atomic_text(output, _render(payload))


def _execute(args: argparse.Namespace, root: Path, target: Path) -> dict:
    if _has_symlink(target, root):
        raise Terminal("unsupported", "unsafe_target", "C map target must not traverse a symbolic link.")
    if not target.exists() or not (target.is_file() or target.is_dir()):
        raise Terminal("unsupported", "target_missing", "C map target must be an existing file or directory.")
    if _base_role(_relative(root, target)) != "source":
        raise Terminal("unsupported", "excluded_target", "Generated, vendor, test, and build targets are excluded.")
    clang = _resolve_tool(args.clang)
    if clang is None:
        raise Terminal("unsupported", "clang_missing", "Clang 21+ is required.")
    clang_version, clang_text = _tool_version(clang, "clang", root)
    if clang_version is None:
        raise Terminal("unsupported", "clang_version_unknown", clang_text)
    if clang_version < args.minimum_clang:
        raise Terminal("unsupported", "clang_version_too_old", f"Clang {clang_version} is below {args.minimum_clang}.")
    clangd = _resolve_tool(args.clangd)
    if clangd is None:
        raise Terminal("unsupported", "clangd_missing", "clangd 21+ is required.")
    clangd_version, clangd_text = _tool_version(clangd, "clangd", root)
    if clangd_version is None:
        raise Terminal("unsupported", "clangd_version_unknown", clangd_text)
    if clangd_version < args.minimum_clangd:
        raise Terminal("unsupported", "clangd_version_too_old", f"clangd {clangd_version} is below {args.minimum_clangd}.")
    before_digest, before_files = _source_digest(root)
    entries, dependencies = _load_database(root, clang)
    selected_entries = [entry for entry in entries if _selected(Path(entry["file"]), target)]
    if not selected_entries:
        raise Terminal("unsupported", "target_has_no_translation_units", "Target contains no compile-database C translation unit.")
    declarations = []
    allowed = set(dependencies) | {item for paths in dependencies.values() for item in paths}
    for entry in selected_entries:
        completed = _run(_analysis_argv(entry, clang, "-Xclang", "-ast-dump=json", "-fsyntax-only"), cwd=root)
        if completed.returncode != 0:
            raise Terminal(
                "failed", "clang_analysis_failed",
                completed.stderr.strip() or f"Clang AST analysis failed for {_relative(root, Path(entry['file']))}.",
                exit_code=2,
            )
        try:
            ast = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise Terminal("failed", "clang_ast_malformed", str(exc), exit_code=2) from exc
        declarations.extend(_declarations(ast, root, allowed))
    checks = _clangd_check(clangd, root, entries)
    declaration_map = {(row["file"], row["line"], row["kind"], row["name"]): row for row in declarations}
    declarations = sorted(declaration_map.values(), key=lambda row: (row["file"], row["line"], row["name"]))
    selected_tus = [_relative(root, Path(entry["file"])) for entry in selected_entries]
    owned = {
        header for source, headers in dependencies.items()
        if source in selected_tus for header in headers
    }
    all_headers = {
        path.relative_to(root).as_posix() for path in _candidate_paths(root)
        if path.suffix.lower() in {".h", ".inc"} and _base_role(path.relative_to(root).as_posix()) == "source"
    }
    public = [row for row in declarations if row["file"] in owned and row["file"].startswith("include/") and row["linkage"] != "internal"]
    dependency_edges = [
        {"header": header, "translation_unit": source}
        for source in selected_tus for header in dependencies[source]
    ]
    tu_edges = []
    for left_index, left in enumerate(selected_tus):
        for right in selected_tus[left_index + 1:]:
            shared = sorted(set(dependencies[left]) & set(dependencies[right]))
            if shared:
                tu_edges.append({"left": left, "right": right, "shared_headers": shared, "resolution": "shared-compiler-dependency"})
    after_digest, after_files = _source_digest(root)
    if before_files != after_files:
        raise Terminal("failed", "source_mutated", "Source fingerprints changed during read-only mapping.", exit_code=2)
    return {
        "status": "complete",
        "failure_kind": "none",
        "message": "Complete for the exact current C17 compile-command snapshot and its compiler dependency closure.",
        "toolchain": {
            "clang": {"path": clang, "version": ".".join(map(str, clang_version)), "probe": clang_text},
            "clangd": {"path": clangd, "version": ".".join(map(str, clangd_version)), "probe": clangd_text},
        },
        "compile_database": {"path": "compile_commands.json", "state": "valid-current-complete-c-mode", "entries": len(entries)},
        "translation_units": selected_tus,
        "owned_headers": sorted(owned),
        "ambiguous_headers": sorted(all_headers - owned),
        "source_inventory": _inventory(root, selected_tus, owned),
        "declarations": declarations,
        "public_surface": public,
        "dependency_edges": dependency_edges,
        "translation_unit_edges": tu_edges,
        "clangd_checks": checks,
        "source_fingerprints": {"before": before_digest, "after": after_digest, "unchanged": True},
        "native_verification": "Run the host-owned restrictive C17 build/test separately before and after mapping.",
        "completeness": {
            "compile_database": "complete",
            "translation_unit_inventory": "complete",
            "dependency_inventory": "complete",
            "declarations_and_public_surface": "complete",
            "cross_translation_unit_edges": "complete",
            "function_pointer_call_resolution": "unsupported",
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--clangd", default="clangd")
    parser.add_argument("--minimum-clang", default="21.0.0")
    parser.add_argument("--minimum-clangd", default="21.0.0")
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
            raise UserError("name must be lowercase kebab-case")
        args.minimum_clang = _version_argument(args.minimum_clang, "--minimum-clang")
        args.minimum_clangd = _version_argument(args.minimum_clangd, "--minimum-clangd")
        root, target, output, evidence = _validate_paths(args)
        base = _base_payload(args, root, target)
        try:
            result = _execute(args, root, target)
        except Terminal as terminal:
            payload = {
                **base,
                "status": terminal.status,
                "failure_kind": terminal.kind,
                "message": str(terminal),
                **terminal.facts,
            }
            _write(output, evidence, payload)
            return terminal.exit_code
        payload = {**base, **result}
        _write(output, evidence, payload)
        return 0
    except UserError as exc:
        print(f"map_c.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
