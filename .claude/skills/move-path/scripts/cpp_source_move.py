#!/usr/bin/env python3
"""Move one closed-executable C++20 implementation unit under reviewed authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "cpp-source-move-evidence-v1"
REPORT_SCHEMA = "cpp-source-move-report-v1"
SOURCE_SUFFIXES = frozenset({".cc", ".cpp", ".cxx", ".c++", ".C"})
HEADER_SUFFIXES = frozenset({".hpp", ".hh", ".hxx", ".h++"})
AMBIGUOUS_HEADER_SUFFIXES = frozenset({".h", ".inc"})
EXCLUDED_PARTS = frozenset({"build", "generated", "vendor", "dist", "out"})
CPP_CONFIG_KEYS = frozenset(
    {
        "clangxx",
        "make",
        "nm",
        "compile_database",
        "source_roots",
        "native_target",
        "smoke",
        "smoke_expected_stdout",
        "moved_object",
        "artifact_kind",
        "external_consumers",
    }
)
INCLUDE_RE = re.compile(
    rb"(?m)^(?P<prefix>[ \t]*#[ \t]*include[ \t]*)"
    rb'(?P<open>[<\"])(?P<path>[^>\"\r\n]+)[>\"]'
)
ANY_INCLUDE_RE = re.compile(rb"(?m)^[ \t]*#[ \t]*include[ \t]+(?P<value>[^\r\n]+)")
CONDITIONAL_RE = re.compile(rb"(?m)^[ \t]*#[ \t]*(?:if|ifdef|ifndef|elif)\b")
TEMPLATE_RE = re.compile(rb"\b(?:extern[ \t]+)?template[ \t]*<")
SOURCE_INCLUDE_RE = re.compile(
    rb"(?m)^[ \t]*#[ \t]*include[ \t]*[<\"][^>\"\r\n]+"
    rb"\.(?:cc|cpp|cxx|c\+\+|C)[>\"]"
)
ABI_BOUNDARY_RE = re.compile(
    rb'extern[ \t]+"C"|__declspec|__attribute__[ \t]*\(\([^)]*visibility'
)


class UserError(RuntimeError):
    """Invalid or unsafe input that must not mutate authored source."""


@dataclass(frozen=True)
class FileState:
    content: bytes
    mode: int


@dataclass(frozen=True)
class TreeState:
    files: dict[str, FileState]
    symlinks: dict[str, str]


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return _sha(rendered.encode("utf-8"))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _relative(raw: Any, *, field: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise UserError(f"{field} must be a non-empty relative path")
    value = PurePosixPath(raw)
    if value.is_absolute() or "." in value.parts or ".." in value.parts:
        raise UserError(f"{field} must be a normalized relative path")
    return value.as_posix()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts and relative.parts[0] == ".git":
        return True
    try:
        path.resolve().relative_to(report_dir.resolve())
    except ValueError:
        return False
    return True


def _snapshot(root: Path, report_dir: Path) -> TreeState:
    files: dict[str, FileState] = {}
    symlinks: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks[relative] = os.readlink(path)
        elif path.is_file():
            files[relative] = FileState(
                path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            )
    return TreeState(files, symlinks)


def _source_state(state: TreeState, compile_database: str) -> TreeState:
    files = {
        path: value
        for path, value in state.files.items()
        if path != compile_database and not path.startswith(".native-build/")
    }
    symlinks = {
        path: value
        for path, value in state.symlinks.items()
        if not path.startswith(".native-build/")
    }
    return TreeState(files, symlinks)


def _tree_payload(state: TreeState) -> dict[str, Any]:
    return {
        "files": [
            {"path": path, "sha256": _sha(value.content), "mode": value.mode}
            for path, value in sorted(state.files.items())
        ],
        "symlinks": [
            {"path": path, "target": target}
            for path, target in sorted(state.symlinks.items())
        ],
    }


def _tree_hash(state: TreeState) -> str:
    return _canonical_hash(_tree_payload(state))


def _materialize(root: Path, state: TreeState) -> None:
    for relative, value in state.files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.content)
        path.chmod(value.mode)
    for relative, target in state.symlinks.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)


def _restore(root: Path, report_dir: Path, state: TreeState) -> None:
    current = _snapshot(root, report_dir)
    for relative in sorted(current.symlinks, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for relative in sorted(current.files, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and not _excluded(
            path, root, report_dir
        ):
            try:
                path.rmdir()
            except OSError:
                pass
    _materialize(root, state)


def _run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env={
                **os.environ,
                "ALL_PROXY": "http://127.0.0.1:9",
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "argv": argv,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _binary(
    raw: Any,
    *,
    name: str,
    root: Path,
    version_args: list[str] | None = None,
    minimum: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        raise UserError(f"cpp_{name}_missing")
    candidate = Path(raw)
    if candidate.parent == Path("."):
        found = shutil.which(raw)
        if found is None:
            raise UserError(f"cpp_{name}_missing")
        candidate = Path(found)
    path = candidate.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise UserError(f"cpp_{name}_missing")
    fact: dict[str, Any] = {"path": str(path), "sha256": _sha(path.read_bytes())}
    if version_args is not None and minimum is not None:
        version = _run([str(path), *version_args], root, timeout=30)
        if not version["passed"]:
            raise UserError(f"cpp_{name}_version_probe_failed")
        match = re.search(r"(\d+(?:\.\d+)+)", version["stdout"] + version["stderr"])
        if match is None:
            raise UserError(f"cpp_{name}_version_unrecognized")
        parts = tuple(int(item) for item in match.group(1).split("."))
        if parts < minimum:
            raise UserError(f"cpp_{name}_too_old")
        fact["version"] = match.group(1)
    return fact


def _load_plan(path: Path, root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserError(f"cpp_plan_invalid: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise UserError("cpp_plan_invalid")
    moves = payload.get("moves")
    if not isinstance(moves, list) or len(moves) != 1:
        raise UserError("cpp_requires_exactly_one_move")
    move = moves[0]
    if not isinstance(move, dict) or move.get("mode") != "file":
        raise UserError("cpp_requires_one_file_move")
    source = _relative(move.get("from"), field="moves[0].from")
    destination = _relative(move.get("to"), field="moves[0].to")
    source_path = PurePosixPath(source)
    destination_path = PurePosixPath(destination)
    if (
        source_path.suffix not in SOURCE_SUFFIXES
        or destination_path.suffix != source_path.suffix
    ):
        raise UserError("cpp_requires_matching_source_suffix")
    if source_path.name != destination_path.name:
        raise UserError("cpp_identity_change_refused")
    if source == destination:
        raise UserError("cpp_source_and_destination_match")
    if (payload.get("rewrite") or {}).get("code_imports") != "update-cpp20":
        raise UserError("cpp_rewrite_mode_required")
    config = payload.get("cpp")
    if not isinstance(config, dict):
        raise UserError("cpp_config_required")
    if set(config) != CPP_CONFIG_KEYS:
        raise UserError("cpp_identity_or_scope_change_refused")
    if (
        config.get("artifact_kind") != "closed-executable"
        or config.get("external_consumers") != "none-known"
    ):
        raise UserError("cpp_external_consumer_uncertain")
    roots = config.get("source_roots")
    if not isinstance(roots, list) or not roots:
        raise UserError("cpp_source_roots_invalid")
    source_roots = tuple(
        _relative(value, field="cpp.source_roots") for value in roots
    )
    if len(set(source_roots)) != len(source_roots):
        raise UserError("cpp_source_roots_invalid")
    compile_database = _relative(
        config.get("compile_database"), field="cpp.compile_database"
    )
    smoke = _relative(config.get("smoke"), field="cpp.smoke")
    moved_object = _relative(
        config.get("moved_object"), field="cpp.moved_object"
    )
    native_target = config.get("native_target")
    expected = config.get("smoke_expected_stdout")
    if not isinstance(native_target, str) or not native_target:
        raise UserError("cpp_native_target_invalid")
    if not isinstance(expected, str):
        raise UserError("cpp_smoke_expected_stdout_invalid")
    plan_resolved = path.resolve()
    if not _inside(plan_resolved, root) or plan_resolved.is_symlink():
        raise UserError("cpp_plan_outside_root")
    return {
        "raw": payload,
        "plan_relative": plan_resolved.relative_to(root).as_posix(),
        "source": source,
        "destination": destination,
        "source_roots": source_roots,
        "compile_database": compile_database,
        "native_target": native_target,
        "smoke": smoke,
        "smoke_expected_stdout": expected,
        "moved_object": moved_object,
        "clangxx": _binary(
            config.get("clangxx"),
            name="clangxx",
            root=root,
            version_args=["--version"],
            minimum=(21, 0),
        ),
        "make": _binary(
            config.get("make"),
            name="make",
            root=root,
            version_args=["--version"],
            minimum=(3, 81),
        ),
        "nm": _binary(config.get("nm"), name="nm", root=root),
    }


def _role_refused(path: str) -> bool:
    return bool(EXCLUDED_PARTS.intersection(PurePosixPath(path).parts))


def _has_symlink(path: Path, root: Path) -> bool:
    current = path
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _expected_sources(root: Path, plan: dict[str, Any]) -> tuple[list[Path], list[dict[str, Any]]]:
    sources: list[Path] = []
    blocked: list[dict[str, Any]] = []
    for relative in plan["source_roots"]:
        source_root = root / relative
        if not source_root.is_dir() or _has_symlink(source_root, root):
            blocked.append({"kind": "cpp_symlink_boundary", "path": relative})
            continue
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                blocked.append(
                    {
                        "kind": "cpp_symlink_boundary",
                        "path": path.relative_to(root).as_posix(),
                    }
                )
            elif path.is_file() and path.suffix in SOURCE_SUFFIXES:
                sources.append(path.resolve())
    return sources, blocked


def _dependency_argv(arguments: list[str], source: str) -> list[str]:
    result = [arguments[0]]
    index = 1
    skip_values = {"-o", "-MF", "-MT", "-MQ", "-MJ"}
    dependency_flags = {"-M", "-MM", "-MD", "-MMD", "-MP", "-MG"}
    while index < len(arguments):
        token = arguments[index]
        if token in skip_values:
            index += 2
            continue
        if token in dependency_flags or token == "-c" or token == source:
            index += 1
            continue
        result.append(token)
        index += 1
    return [*result, "-MM", "-MT", "cpp-move-deps", source]


def _parse_dependencies(stdout: str, root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    rendered = stdout.replace("\\\n", " ")
    _, separator, body = rendered.partition(":")
    if not separator:
        return [], [{"kind": "cpp_compiler_dependency_output_invalid"}]
    try:
        tokens = shlex.split(body)
    except ValueError:
        return [], [{"kind": "cpp_compiler_dependency_output_invalid"}]
    dependencies: list[str] = []
    blocked: list[dict[str, Any]] = []
    for raw in tokens:
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve()
        if not _inside(resolved, root):
            blocked.append(
                {"kind": "cpp_external_header_dependency", "path": str(resolved)}
            )
            continue
        relative = resolved.relative_to(root).as_posix()
        if not resolved.is_file() or resolved.is_symlink():
            blocked.append({"kind": "cpp_symlink_boundary", "path": relative})
            continue
        dependencies.append(relative)
    return sorted(set(dependencies)), blocked


def _database(
    root: Path, plan: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    expected, blocked = _expected_sources(root, plan)
    database_path = root / plan["compile_database"]
    try:
        raw = database_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [], [*blocked, {"kind": "cpp_compile_database_invalid"}], None
    if not isinstance(payload, list):
        return [], [*blocked, {"kind": "cpp_compile_database_invalid"}], _sha(raw)
    entries: list[dict[str, Any]] = []
    actual: list[Path] = []
    compiler = Path(plan["clangxx"]["path"])
    for row in payload:
        if not isinstance(row, dict) or set(row) != {"directory", "file", "arguments"}:
            blocked.append({"kind": "cpp_compile_database_invalid"})
            continue
        arguments = row.get("arguments")
        if (
            not isinstance(arguments, list)
            or not arguments
            or not all(isinstance(item, str) and item for item in arguments)
        ):
            blocked.append({"kind": "cpp_compile_database_invalid"})
            continue
        try:
            directory = Path(row["directory"]).resolve()
            file_path = Path(row["file"]).resolve()
        except (TypeError, OSError):
            blocked.append({"kind": "cpp_compile_database_invalid"})
            continue
        if directory != root or not _inside(file_path, root):
            blocked.append({"kind": "cpp_compile_database_invalid"})
            continue
        relative = file_path.relative_to(root).as_posix()
        actual.append(file_path)
        standards = [item for item in arguments if item.startswith("-std=")]
        macro_flags = [
            item
            for item in arguments
            if item.startswith(("-D", "-U"))
            or item in {"-include", "-imacros"}
            or item.startswith("@")
            or "modules" in item
            or "pch" in item.lower()
        ]
        if macro_flags:
            blocked.append(
                {
                    "kind": "cpp_macro_variant_uncertain",
                    "source": relative,
                    "flags": macro_flags,
                }
            )
        if (
            standards[-1:] != ["-std=c++20"]
            or "-c" not in arguments
            or arguments.count(str(file_path)) != 1
            or Path(arguments[0]).resolve() != compiler
            or arguments.count("-o") != 1
        ):
            blocked.append(
                {"kind": "cpp_compile_database_wrong_mode", "source": relative}
            )
        entries.append(
            {"source": relative, "file": str(file_path), "arguments": arguments}
        )
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        blocked.append(
            {
                "kind": "cpp_compile_database_incomplete",
                "expected": sorted(path.relative_to(root).as_posix() for path in expected),
                "actual": sorted(path.relative_to(root).as_posix() for path in actual),
            }
        )
    impacts: list[dict[str, Any]] = []
    if not blocked:
        all_headers: set[str] = set()
        for entry in entries:
            dependency = _run(
                _dependency_argv(entry["arguments"], entry["file"]), root
            )
            if not dependency["passed"]:
                blocked.append(
                    {
                        "kind": "cpp_compiler_dependency_failed",
                        "source": entry["source"],
                    }
                )
                continue
            dependencies, dependency_blocked = _parse_dependencies(
                dependency["stdout"], root
            )
            blocked.extend(dependency_blocked)
            headers = [path for path in dependencies if path != entry["source"]]
            for header in headers:
                suffix = PurePosixPath(header).suffix
                if suffix in AMBIGUOUS_HEADER_SUFFIXES:
                    blocked.append(
                        {
                            "kind": "cpp_ambiguous_header_dependency",
                            "source": entry["source"],
                            "header": header,
                        }
                    )
                elif suffix not in HEADER_SUFFIXES:
                    blocked.append(
                        {
                            "kind": "cpp_header_role_uncertain",
                            "source": entry["source"],
                            "header": header,
                        }
                    )
                if _role_refused(header):
                    blocked.append(
                        {
                            "kind": "cpp_excluded_header_dependency",
                            "source": entry["source"],
                            "header": header,
                        }
                    )
                all_headers.add(header)
            impacts.append({"source": entry["source"], "headers": sorted(headers)})
        freshness = [root / "Makefile", *expected, *(root / path for path in all_headers)]
        if not all(path.is_file() for path in freshness):
            blocked.append({"kind": "cpp_compile_database_invalid"})
        elif database_path.stat().st_mtime_ns < max(
            path.stat().st_mtime_ns for path in freshness
        ):
            blocked.append({"kind": "cpp_compile_database_stale"})
    return sorted(impacts, key=lambda row: row["source"]), blocked, _sha(raw)


def _change(
    file_before: str,
    file_after: str,
    kind: str,
    old: str,
    new: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    return {
        "file_before": file_before,
        "file_after": file_after,
        "kind": kind,
        "old": old,
        "new": new,
        "start": start,
        "end": end,
    }


def _uncertain_owned_code(
    root: Path, impacts: list[dict[str, Any]], source_roots: tuple[str, ...]
) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    owned: set[str] = set()
    for row in impacts:
        owned.add(row["source"])
        owned.update(row["headers"])
    for relative in sorted(owned):
        content = (root / relative).read_bytes()
        if CONDITIONAL_RE.search(content):
            blocked.append({"kind": "cpp_macro_variant_uncertain", "path": relative})
        if TEMPLATE_RE.search(content):
            blocked.append(
                {"kind": "cpp_template_ownership_uncertain", "path": relative}
            )
        if ABI_BOUNDARY_RE.search(content):
            blocked.append({"kind": "cpp_abi_boundary_uncertain", "path": relative})
        literal_spans = {
            (match.start(), match.end()) for match in INCLUDE_RE.finditer(content)
        }
        for match in ANY_INCLUDE_RE.finditer(content):
            if (match.start(), match.end()) not in literal_spans:
                blocked.append(
                    {"kind": "cpp_macro_include_uncertain", "path": relative}
                )
    for root_name in source_roots:
        for path in sorted((root / root_name).rglob("*")):
            if path.is_file() and not path.is_symlink() and path.suffix in SOURCE_SUFFIXES:
                if SOURCE_INCLUDE_RE.search(path.read_bytes()):
                    blocked.append(
                        {
                            "kind": "cpp_odr_source_include_uncertain",
                            "path": path.relative_to(root).as_posix(),
                        }
                    )
    return blocked


def _plan_changes(
    root: Path,
    report_dir: Path,
    plan_path: Path,
    plan: dict[str, Any],
    impacts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = plan["source"]
    destination = plan["destination"]
    source_path = root / source
    destination_path = root / destination
    blocked: list[dict[str, Any]] = []
    if _role_refused(source) or _role_refused(destination):
        blocked.append({"kind": "cpp_source_role_refused", "path": source})
    if not source_path.is_file() or source_path.is_symlink():
        blocked.append(
            {
                "kind": "cpp_symlink_boundary" if source_path.is_symlink() else "cpp_source_missing",
                "path": source,
            }
        )
    if destination_path.exists() or destination_path.is_symlink():
        blocked.append({"kind": "cpp_destination_exists", "path": destination})
    if _has_symlink(source_path, root) or _has_symlink(destination_path.parent, root):
        blocked.append({"kind": "cpp_symlink_boundary", "path": source})
    source_impact = next((row for row in impacts if row["source"] == source), None)
    if source_impact is None:
        blocked.append({"kind": "cpp_source_not_compiler_owned", "path": source})
    if blocked:
        return [], blocked
    blocked.extend(_uncertain_owned_code(root, impacts, plan["source_roots"]))
    content = source_path.read_bytes()
    changes: list[dict[str, Any]] = []
    owned_headers = set(source_impact["headers"])
    for match in INCLUDE_RE.finditer(content):
        if match.group("open") != b'"':
            continue
        old = match.group("path").decode("utf-8")
        local = (source_path.parent / old).resolve()
        if not _inside(local, root) or not local.is_file():
            continue
        relative_header = local.relative_to(root).as_posix()
        if relative_header not in owned_headers:
            blocked.append(
                {
                    "kind": "cpp_include_lineage_uncertain",
                    "path": source,
                    "include": old,
                }
            )
            continue
        new = os.path.relpath(local, destination_path.parent).replace(os.sep, "/")
        if new != old:
            changes.append(
                _change(
                    source,
                    destination,
                    "cpp_relative_include",
                    old,
                    new,
                    match.start("path"),
                    match.end("path"),
                )
            )
    makefile = root / "Makefile"
    if not makefile.is_file() or makefile.is_symlink():
        blocked.append({"kind": "cpp_makefile_missing"})
    else:
        make_content = makefile.read_bytes()
        old_bytes = source.encode("utf-8")
        start = 0
        found = 0
        while True:
            index = make_content.find(old_bytes, start)
            if index < 0:
                break
            changes.append(
                _change(
                    "Makefile",
                    "Makefile",
                    "cpp_make_path",
                    source,
                    destination,
                    index,
                    index + len(old_bytes),
                )
            )
            found += 1
            start = index + len(old_bytes)
        if not found:
            blocked.append({"kind": "cpp_make_source_path_missing", "path": source})
    old_identity = source.encode("utf-8")
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or _excluded(path, root, report_dir)
            or path.relative_to(root).as_posix()
            in {
                source,
                "Makefile",
                plan["compile_database"],
                plan_path.relative_to(root).as_posix(),
            }
            or path.relative_to(root).as_posix().startswith(".native-build/")
        ):
            continue
        if old_identity in path.read_bytes():
            blocked.append(
                {
                    "kind": "cpp_external_consumer_uncertain",
                    "path": path.relative_to(root).as_posix(),
                }
            )
    return sorted(changes, key=lambda row: (row["file_before"], row["start"])), blocked


def _apply_changes(content: bytes, changes: list[dict[str, Any]]) -> bytes:
    result = content
    for row in sorted(changes, key=lambda item: item["start"], reverse=True):
        old = row["old"].encode("utf-8")
        if result[row["start"] : row["end"]] != old:
            raise UserError(f"cpp_stale_edit_span:{row['file_before']}")
        result = (
            result[: row["start"]]
            + row["new"].encode("utf-8")
            + result[row["end"] :]
        )
    return result


def _expected(
    before: TreeState, plan: dict[str, Any], changes: list[dict[str, Any]]
) -> TreeState:
    files = dict(before.files)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in changes:
        grouped.setdefault(row["file_before"], []).append(row)
    source_value = files.pop(plan["source"])
    source_content = _apply_changes(
        source_value.content, grouped.pop(plan["source"], [])
    )
    files[plan["destination"]] = FileState(source_content, source_value.mode)
    for relative, rows in grouped.items():
        value = files[relative]
        files[relative] = FileState(_apply_changes(value.content, rows), value.mode)
    return TreeState(files, dict(before.symlinks))


def _mutate(root: Path, plan: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in changes:
        grouped.setdefault(row["file_before"], []).append(row)
    source_path = root / plan["source"]
    source_content = _apply_changes(
        source_path.read_bytes(), grouped.pop(plan["source"], [])
    )
    destination = root / plan["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(source_path.stat().st_mode)
    destination.write_bytes(source_content)
    destination.chmod(mode)
    source_path.unlink()
    for relative, rows in grouped.items():
        path = root / relative
        path.write_bytes(_apply_changes(path.read_bytes(), rows))


def _symbols(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    result = _run(
        [plan["nm"]["path"], "-gUj", str(root / plan["moved_object"])], root
    )
    symbols = sorted(set(result["stdout"].splitlines())) if result["passed"] else []
    if not symbols:
        result["passed"] = False
        if not result["stderr"]:
            result["stderr"] = "no defined global symbols"
    return {**result, "symbols": symbols}


def _native(root: Path, plan: dict[str, Any], *, refresh: bool) -> dict[str, Any]:
    targets = (["clean", "compile-db"] if refresh else []) + [plan["native_target"]]
    make = _run(
        [plan["make"]["path"], *targets, f"CXX={plan['clangxx']['path']}"], root
    )
    smoke = (
        _run([str(root / plan["smoke"])], root)
        if make["passed"]
        else {
            "argv": [str(root / plan["smoke"])],
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": "native target failed",
        }
    )
    if smoke["passed"] and smoke["stdout"] != plan["smoke_expected_stdout"]:
        smoke["passed"] = False
        smoke["stderr"] = "unexpected smoke stdout"
    symbols = _symbols(root, plan) if make["passed"] else {
        "argv": [plan["nm"]["path"]],
        "passed": False,
        "returncode": None,
        "stdout": "",
        "stderr": "native target failed",
        "symbols": [],
    }
    return {"make": make, "smoke": smoke, "symbols": symbols}


def _native_passed(native: dict[str, Any]) -> bool:
    return all(native[name]["passed"] for name in ("make", "smoke", "symbols"))


def _old_identity(
    root: Path, report_dir: Path, plan: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if (root / plan["source"]).exists() or (root / plan["source"]).is_symlink():
        rows.append({"path": plan["source"], "kind": "old_source_exists"})
    old = plan["source"].encode("utf-8")
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if (
            relative in {plan["compile_database"], plan["plan_relative"]}
            or relative.startswith(".native-build/")
        ):
            continue
        if old in path.read_bytes():
            rows.append({"path": relative, "kind": "old_path_text"})
    return rows


def _analysis(
    root: Path, report_dir: Path, plan_path: Path, plan: dict[str, Any]
) -> dict[str, Any]:
    full = _snapshot(root, report_dir)
    before = _source_state(full, plan["compile_database"])
    impacts_before, database_blocked, database_hash = _database(root, plan)
    changes, change_blocked = _plan_changes(
        root, report_dir, plan_path, plan, impacts_before
    )
    blocked = [*database_blocked, *change_blocked]
    expected = _expected(before, plan, changes) if not change_blocked else before
    native_before: dict[str, Any] = {}
    native_after: dict[str, Any] = {}
    impacts_after: list[dict[str, Any]] = []
    if not blocked:
        native_before = _native(root, plan, refresh=False)
        if not _native_passed(native_before):
            blocked.append({"kind": "cpp_native_preflight_failed"})
    if not blocked:
        with tempfile.TemporaryDirectory(prefix="cpp-source-move-") as raw:
            virtual_root = Path(raw).resolve()
            _materialize(virtual_root, full)
            _mutate(virtual_root, plan, changes)
            native_after = _native(virtual_root, plan, refresh=True)
            impacts_after, after_blocked, _ = _database(virtual_root, plan)
            blocked.extend(after_blocked)
            virtual_source = _source_state(
                _snapshot(virtual_root, virtual_root / "reports/move-path"),
                plan["compile_database"],
            )
            if not _native_passed(native_after):
                blocked.append({"kind": "cpp_virtual_postflight_failed"})
            if _tree_hash(virtual_source) != _tree_hash(expected):
                blocked.append({"kind": "cpp_virtual_after_tree_mismatch"})
            before_headers = {
                row["source"]: row["headers"] for row in impacts_before
            }
            after_headers = {row["source"]: row["headers"] for row in impacts_after}
            moved_headers = before_headers.pop(plan["source"], None)
            if moved_headers is not None:
                before_headers[plan["destination"]] = moved_headers
            if before_headers != after_headers:
                blocked.append({"kind": "cpp_header_ownership_changed"})
            if (
                native_before["symbols"]["symbols"]
                != native_after["symbols"]["symbols"]
            ):
                blocked.append({"kind": "cpp_abi_identity_changed"})
    return {
        "full": full,
        "before": before,
        "expected": expected,
        "changes": changes,
        "blocked": blocked,
        "database_hash": database_hash,
        "impacts_before": impacts_before,
        "impacts_after": impacts_after,
        "native_before": native_before,
        "native_after": native_after,
    }


def _evidence(
    plan_path: Path, plan: dict[str, Any], facts: dict[str, Any]
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "plan_sha256": _sha(plan_path.read_bytes()),
        "plan": plan["raw"],
        "adapter_sha256": _sha(Path(__file__).read_bytes()),
        "source": plan["source"],
        "destination": plan["destination"],
        "source_tree_sha256": _tree_hash(facts["before"]),
        "expected_after_tree_sha256": _tree_hash(facts["expected"]),
        "compile_database_sha256": facts["database_hash"],
        "tooling": {
            "clangxx": plan["clangxx"],
            "make": plan["make"],
            "nm": plan["nm"],
        },
        "exact_changes": facts["changes"],
        "compiler_impacts_before": facts["impacts_before"],
        "compiler_impacts_after": facts["impacts_after"],
        "symbols": facts["native_before"].get("symbols", {}).get("symbols", []),
    }
    payload["evidence_sha256"] = _canonical_hash(payload)
    return payload


def _load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserError(f"cpp_evidence_invalid: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise UserError("cpp_evidence_invalid")
    claimed = payload.get("evidence_sha256")
    raw = dict(payload)
    raw.pop("evidence_sha256", None)
    if claimed != _canonical_hash(raw):
        raise UserError("cpp_evidence_hash_invalid")
    return payload


def _status(blocked: list[dict[str, Any]]) -> str:
    kinds = {row["kind"] for row in blocked}
    if any(
        "refused" in kind
        or "uncertain" in kind
        or "ambiguous" in kind
        or "symlink" in kind
        for kind in kinds
    ):
        return "unsupported"
    if any("invalid" in kind or "failed" in kind for kind in kinds):
        return "failed"
    return "partial"


def _report(
    *,
    mode: str,
    status: str,
    plan: dict[str, Any] | None,
    blocked: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    impacts_before: list[dict[str, Any]] | None = None,
    impacts_after: list[dict[str, Any]] | None = None,
    native: dict[str, Any] | None = None,
    symbols_after: list[str] | None = None,
    evidence_sha: str | None = None,
    exact: dict[str, Any] | None = None,
    rolled_back: bool = False,
    old_identity: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    native_value = native or {}
    symbols_before = native_value.get("symbols", {}).get("symbols", [])
    return {
        "schema": REPORT_SCHEMA,
        "cpp": {
            "mode": mode,
            "status": status,
            "source": plan["source"] if plan else None,
            "destination": plan["destination"] if plan else None,
            "blocked": blocked,
            "exact_changes": changes,
            "compiler_impacts_before": impacts_before or [],
            "compiler_impacts_after": impacts_after or [],
            "native_preflight" if mode == "dry-run" else "native": native_value,
            "identity_proof": {
                "symbols_before": symbols_before,
                "symbols_after": symbols_after if symbols_after is not None else symbols_before,
                "passed": symbols_after is None or symbols_before == symbols_after,
            },
            "evidence_sha256": evidence_sha,
            "exact_after_tree": exact or {},
            "old_identity_remaining": old_identity or [],
            "rolled_back": rolled_back,
        },
    }


def _write_report(report_dir: Path, payload: dict[str, Any]) -> None:
    _atomic_json(report_dir / "report.json", payload)


def run(
    *,
    root: Path,
    plan_path: Path,
    report_dir: Path,
    mode: str,
    evidence_path: Path | None,
    approval: str | None,
) -> tuple[int, dict[str, Any]]:
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_output = report_dir / "evidence.json"
    try:
        plan = _load_plan(plan_path, root)
    except UserError as exc:
        evidence_output.unlink(missing_ok=True)
        payload = _report(
            mode=mode,
            status="failed",
            plan=None,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload

    if mode == "dry-run":
        facts = _analysis(root, report_dir, plan_path, plan)
        if facts["blocked"]:
            evidence_output.unlink(missing_ok=True)
            payload = _report(
                mode=mode,
                status=_status(facts["blocked"]),
                plan=plan,
                blocked=facts["blocked"],
                changes=facts["changes"],
                impacts_before=facts["impacts_before"],
                impacts_after=facts["impacts_after"],
                native=facts["native_before"],
                symbols_after=facts["native_after"].get("symbols", {}).get(
                    "symbols", []
                ),
            )
            _write_report(report_dir, payload)
            return 2, payload
        evidence = _evidence(plan_path, plan, facts)
        _atomic_json(evidence_output, evidence)
        payload = _report(
            mode=mode,
            status="complete",
            plan=plan,
            blocked=[],
            changes=facts["changes"],
            impacts_before=facts["impacts_before"],
            impacts_after=facts["impacts_after"],
            native=facts["native_before"],
            symbols_after=facts["native_after"]["symbols"]["symbols"],
            evidence_sha=evidence["evidence_sha256"],
        )
        _write_report(report_dir, payload)
        return 0, payload

    if evidence_path is None:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "cpp_evidence_required"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    try:
        evidence = _load_evidence(evidence_path)
    except UserError as exc:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload

    plan_mismatch = (
        evidence.get("plan_sha256") != _sha(plan_path.read_bytes())
        or evidence.get("plan") != plan["raw"]
        or evidence.get("adapter_sha256") != _sha(Path(__file__).read_bytes())
    )
    if mode == "check":
        current = _source_state(
            _snapshot(root, report_dir), plan["compile_database"]
        )
        impacts, database_blocked, _ = _database(root, plan)
        native = _native(root, plan, refresh=False) if not database_blocked else {}
        old_identity = _old_identity(root, report_dir, plan)
        blocked = list(database_blocked)
        if plan_mismatch:
            blocked.append({"kind": "cpp_evidence_plan_mismatch"})
        if _tree_hash(current) != evidence.get("expected_after_tree_sha256"):
            blocked.append({"kind": "cpp_after_tree_mismatch"})
        if impacts != evidence.get("compiler_impacts_after"):
            blocked.append({"kind": "cpp_header_ownership_changed"})
        if old_identity:
            blocked.append({"kind": "cpp_old_identity_remaining"})
        if native and (
            not _native_passed(native)
            or native["symbols"]["symbols"] != evidence.get("symbols")
        ):
            blocked.append({"kind": "cpp_native_check_failed"})
        payload = _report(
            mode=mode,
            status="complete" if not blocked else "failed",
            plan=plan,
            blocked=blocked,
            changes=[],
            impacts_after=impacts,
            native=native,
            evidence_sha=evidence.get("evidence_sha256"),
            exact={
                "passed": not any(
                    row["kind"] == "cpp_after_tree_mismatch" for row in blocked
                )
            },
            old_identity=old_identity,
        )
        _write_report(report_dir, payload)
        return (0 if not blocked else 2), payload

    if approval != evidence.get("evidence_sha256"):
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "cpp_evidence_approval_mismatch"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    facts = _analysis(root, report_dir, plan_path, plan)
    current_evidence = _evidence(plan_path, plan, facts)
    if facts["blocked"] or plan_mismatch or current_evidence != evidence:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[*facts["blocked"], {"kind": "cpp_stale_evidence"}],
            changes=facts["changes"],
            impacts_before=facts["impacts_before"],
            impacts_after=facts["impacts_after"],
        )
        _write_report(report_dir, payload)
        return 2, payload

    try:
        _mutate(root, plan, facts["changes"])
        native = _native(root, plan, refresh=True)
        impacts_after, database_blocked, _ = _database(root, plan)
        current = _source_state(
            _snapshot(root, report_dir), plan["compile_database"]
        )
        exact_passed = _tree_hash(current) == evidence["expected_after_tree_sha256"]
        old_identity = _old_identity(root, report_dir, plan)
        if (
            not _native_passed(native)
            or native["symbols"]["symbols"] != evidence["symbols"]
            or impacts_after != evidence["compiler_impacts_after"]
            or database_blocked
            or not exact_passed
            or old_identity
        ):
            raise UserError("cpp_postflight_failed")
    except (OSError, UserError) as exc:
        _restore(root, report_dir, facts["full"])
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=facts["changes"],
            impacts_before=facts["impacts_before"],
            impacts_after=locals().get("impacts_after", []),
            native=locals().get("native", {}),
            rolled_back=True,
        )
        _write_report(report_dir, payload)
        return 2, payload
    payload = _report(
        mode=mode,
        status="complete",
        plan=plan,
        blocked=[],
        changes=facts["changes"],
        impacts_before=facts["impacts_before"],
        impacts_after=impacts_after,
        native=native,
        evidence_sha=evidence["evidence_sha256"],
        exact={"passed": True, "actual_fingerprint": _tree_hash(current)},
        old_identity=[],
    )
    _write_report(report_dir, payload)
    return 0, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--approve-evidence-sha256")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if not root.is_dir() or root.is_symlink():
        print("project root must be a non-symlink directory", file=sys.stderr)
        return 2
    mode = "dry-run" if args.dry_run else "apply" if args.apply else "check"
    code, payload = run(
        root=root,
        plan_path=args.plan.resolve(),
        report_dir=args.report_dir.resolve(),
        mode=mode,
        evidence_path=args.evidence.resolve() if args.evidence else None,
        approval=args.approve_evidence_sha256,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
