#!/usr/bin/env python3
"""Build and verify a durable Cargo-backed Rust subsystem map.

The mapper deliberately separates evidence classes. Cargo metadata and compiler
JSON establish the selected workspace/build model, rust-analyzer is used only
through stable LSP methods, and source scanning records bounded declarations and
unresolved semantic boundaries. It never treats textual matches as expansion,
dispatch, generated-code, or cross-configuration proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = "rust-map-v1"
ANALYZER = "cargo-metadata+compiler-json+rust-analyzer-lsp"
EXCLUDED_SNAPSHOT_PARTS = {
    ".git",
    ".agents",
    ".claude",
    ".engineering",
    "reports",
}
OUTPUT_PREFIX = Path(".engineering/docs/subsystems")
EVIDENCE_PREFIX = Path("reports/map")
RUST_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _display_external(path: str, target_dir: Path) -> str:
    candidate = Path(path)
    try:
        relative = candidate.resolve(strict=False).relative_to(target_dir.resolve(strict=False))
        return f"$CARGO_TARGET_DIR/{relative.as_posix()}"
    except ValueError:
        return candidate.name


def _atomic_write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_destination(raw: str, project_root: Path, prefix: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes project root: {candidate}") from exc
    if relative == prefix or prefix not in relative.parents:
        raise ValueError(f"artifact path must be below {prefix.as_posix()}: {relative.as_posix()}")
    current = project_root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError(f"artifact path traverses symlink: {current}")
    return candidate


def _safe_target(raw: str, project_root: Path) -> Path:
    target = Path(raw)
    if not target.is_absolute():
        target = project_root / target
    try:
        target = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"target does not exist: {target}") from exc
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"target escapes project root: {target}") from exc
    return target


def _resolve_tool(raw: str) -> str | None:
    if os.sep in raw:
        candidate = Path(raw)
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    return shutil.which(raw)


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _source_snapshot(project_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for directory, directory_names, file_names in os.walk(project_root, followlinks=False):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(project_root)
        retained_directories = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_SNAPSHOT_PARTS
            and not (relative_directory / name).parts[0].startswith("cargo-target-")
        )
        directory_names[:] = []
        for name in retained_directories:
            child = directory_path / name
            if child.is_symlink():
                rows.append(
                    {
                        "path": child.relative_to(project_root).as_posix(),
                        "sha256": _sha256_text(f"symlink:{os.readlink(child)}"),
                        "kind": "symlink",
                    }
                )
            else:
                directory_names.append(name)
        for name in sorted(file_names):
            path = directory_path / name
            relative = path.relative_to(project_root).as_posix()
            if path.is_symlink():
                digest = _sha256_text(f"symlink:{os.readlink(path)}")
                kind = "symlink"
            elif path.is_file():
                digest = _sha256_bytes(path.read_bytes())
                kind = "file"
            else:
                continue
            rows.append({"path": relative, "sha256": digest, "kind": kind})
    return rows


def _tool_version(tool: str | None, argument: str = "--version") -> str | None:
    if tool is None:
        return None
    try:
        completed = subprocess.run(
            [tool, argument], capture_output=True, text=True, check=False, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = (completed.stdout or completed.stderr).strip().splitlines()
    return value[0] if completed.returncode == 0 and value else None


def _cargo_environment(target_dir: Path, rustc: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    env["CARGO_TARGET_DIR"] = str(target_dir)
    if rustc is not None:
        env["RUSTC"] = rustc
    return env


def _cargo_metadata(
    cargo: str, project_root: Path, env: dict[str, str]
) -> tuple[dict[str, Any] | None, str]:
    completed = _run(
        [cargo, "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"],
        cwd=project_root,
        env=env,
    )
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip()
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"Cargo metadata emitted malformed JSON: {exc}"
    return payload, ""


def _workspace_model(
    metadata: dict[str, Any], project_root: Path
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    member_ids = set(metadata.get("workspace_members", []))
    packages = [
        package for package in metadata.get("packages", []) if package.get("id") in member_ids
    ]
    packages.sort(key=lambda package: package.get("name", ""))
    by_id = {package["id"]: package for package in packages}
    package_names = {package["name"] for package in packages}
    workspace = {
        "root": _relative(Path(metadata.get("workspace_root", project_root)), project_root),
        "members": sorted(package["name"] for package in packages),
        "resolver": metadata.get("resolve", {}).get("version") if metadata.get("resolve") else None,
    }
    package_rows: list[dict[str, Any]] = []
    dependency_rows: list[dict[str, str]] = []
    target_rows: list[dict[str, Any]] = []
    for package in packages:
        package_rows.append(
            {
                "name": package["name"],
                "version": package["version"],
                "manifest": _relative(Path(package["manifest_path"]), project_root),
                "edition": package.get("edition"),
                "rust_version": package.get("rust_version"),
                "features": {
                    key: value for key, value in sorted(package.get("features", {}).items())
                },
            }
        )
        for dependency in package.get("dependencies", []):
            if dependency.get("name") in package_names:
                dependency_rows.append(
                    {
                        "source": package["name"],
                        "target": dependency["name"],
                        "kind": dependency.get("kind") or "normal",
                    }
                )
        for target in package.get("targets", []):
            for kind in target.get("kind", []):
                target_rows.append(
                    {
                        "package": package["name"],
                        "name": target.get("name"),
                        "kind": kind,
                        "source": _relative(Path(target["src_path"]), project_root),
                        "crate_types": sorted(target.get("crate_types", [])),
                        "edition": target.get("edition"),
                        "doctest": bool(target.get("doctest", False)),
                    }
                )
    dependency_rows.sort(key=lambda row: (row["source"], row["target"], row["kind"]))
    target_rows.sort(key=lambda row: (row["package"], row["kind"], row["name"] or ""))
    return workspace, package_rows, dependency_rows, target_rows, by_id


def _compiler_check(
    cargo: str,
    project_root: Path,
    env: dict[str, str],
    target_dir: Path,
    packages_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    command = [
        cargo,
        "check",
        "--message-format=json",
        "--locked",
        "--offline",
        "--workspace",
        "--all-targets",
        "--all-features",
    ]
    completed = _run(command, cwd=project_root, env=env, timeout=240)
    diagnostics: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    build_scripts: list[dict[str, Any]] = []
    malformed_lines = 0
    for line in completed.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        reason = message.get("reason")
        if reason == "compiler-message":
            diagnostic = message.get("message", {})
            spans = []
            for span in diagnostic.get("spans", []):
                if span.get("is_primary"):
                    spans.append(
                        {
                            "file": _relative(Path(span.get("file_name", "")), project_root),
                            "line": span.get("line_start"),
                            "column": span.get("column_start"),
                        }
                    )
            diagnostics.append(
                {
                    "level": diagnostic.get("level"),
                    "message": diagnostic.get("message"),
                    "code": (diagnostic.get("code") or {}).get("code"),
                    "primary_spans": spans,
                }
            )
        elif reason == "compiler-artifact":
            package = packages_by_id.get(message.get("package_id"), {})
            artifacts.append(
                {
                    "package": package.get("name", message.get("package_id")),
                    "target": message.get("target", {}).get("name"),
                    "kinds": sorted(message.get("target", {}).get("kind", [])),
                    "profile": message.get("profile", {}),
                    "filenames": sorted(
                        _display_external(path, target_dir) for path in message.get("filenames", [])
                    ),
                    "fresh": bool(message.get("fresh", False)),
                }
            )
        elif reason == "build-script-executed":
            package = packages_by_id.get(message.get("package_id"), {})
            build_scripts.append(
                {
                    "package": package.get("name", message.get("package_id")),
                    "cfgs": sorted(message.get("cfgs", [])),
                    "env": sorted(
                        ({"name": pair[0], "value": pair[1]} for pair in message.get("env", [])),
                        key=lambda row: (row["name"], row["value"]),
                    ),
                    "out_dir": _display_external(message.get("out_dir", ""), target_dir),
                    "generated_contents_inspected": False,
                }
            )
    diagnostics.sort(key=lambda row: (row["level"] or "", row["message"] or ""))
    artifacts.sort(key=lambda row: (row["package"] or "", row["target"] or "", row["kinds"]))
    build_scripts.sort(key=lambda row: row["package"] or "")
    compiler = {
        "state": "clean" if completed.returncode == 0 else "failed",
        "command": [
            "cargo",
            "check",
            "--message-format=json",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ],
        "diagnostics": diagnostics,
        "artifacts": artifacts,
        "malformed_message_lines": malformed_lines,
        "stderr": completed.stderr.strip(),
    }
    return compiler, build_scripts


def _rustc_cfg(
    rustc: str | None, project_root: Path, env: dict[str, str]
) -> tuple[dict[str, list[str]], str | None]:
    if rustc is None:
        return {}, "rustc is unavailable; selected host cfg values were not queried"
    completed = _run([rustc, "--print", "cfg"], cwd=project_root, env=env, timeout=30)
    if completed.returncode != 0:
        return {}, (completed.stderr or completed.stdout).strip()
    values: dict[str, list[str]] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            value = value.strip().strip('"')
        else:
            key, value = line.strip(), "true"
        values.setdefault(key, []).append(value)
    return {key: sorted(set(items)) for key, items in sorted(values.items())}, None


def _split_cfg_arguments(value: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(value):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return [item for item in result if item]


def _cfg_state(expression: str, active: dict[str, set[str]]) -> str:
    expression = expression.strip()
    wrapper = re.fullmatch(r"(all|any|not)\((.*)\)", expression)
    if wrapper:
        operator, body = wrapper.groups()
        states = [_cfg_state(item, active) for item in _split_cfg_arguments(body)]
        if operator == "not" and len(states) == 1:
            return {"selected": "unselected", "unselected": "selected"}.get(states[0], "unknown")
        if operator == "all":
            if "unselected" in states:
                return "unselected"
            return (
                "selected" if states and all(state == "selected" for state in states) else "unknown"
            )
        if "selected" in states:
            return "selected"
        return (
            "unselected" if states and all(state == "unselected" for state in states) else "unknown"
        )
    match = re.fullmatch(rf"({RUST_IDENT})\s*=\s*\"([^\"]+)\"", expression)
    if match:
        key, value = match.groups()
        if key not in active:
            return "unknown"
        return "selected" if value in active[key] else "unselected"
    if re.fullmatch(RUST_IDENT, expression):
        if expression not in active:
            return "unknown"
        return "selected" if "true" in active[expression] else "unselected"
    return "unknown"


def _module_base(source: Path) -> Path:
    if source.name in {"lib.rs", "main.rs", "mod.rs"}:
        return source.parent
    return source.parent / source.stem


def _scan_source_lines(
    source: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    modules: list[dict[str, Any]] = []
    reexports: list[dict[str, Any]] = []
    cfgs: list[dict[str, Any]] = []
    macros: list[dict[str, Any]] = []
    dispatch: list[dict[str, Any]] = []
    pending_cfg: tuple[str, int] | None = None
    block_depth = 0
    for line_number, original in enumerate(
        source.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = original
        if block_depth:
            block_depth += line.count("/*") - line.count("*/")
            if block_depth > 0:
                continue
            line = line.split("*/", 1)[-1]
        if "/*" in line:
            before, after = line.split("/*", 1)
            block_depth = 1 + after.count("/*") - after.count("*/")
            line = before
        line = line.split("//", 1)[0]
        cfg_match = re.match(r"^\s*#\[cfg\((.+)\)\]\s*$", line)
        if cfg_match:
            pending_cfg = (cfg_match.group(1).strip(), line_number)
            continue
        module_match = re.match(rf"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+({RUST_IDENT})\s*;", line)
        if module_match:
            modules.append(
                {
                    "name": module_match.group(1),
                    "line": line_number,
                    "cfg": pending_cfg[0] if pending_cfg else None,
                }
            )
        reexport_match = re.match(r"^\s*pub(?:\([^)]*\))?\s+use\s+([^;]+);", line)
        if reexport_match:
            reexports.append({"path": reexport_match.group(1).strip(), "line": line_number})
        if pending_cfg and line.strip():
            cfgs.append(
                {
                    "expression": pending_cfg[0],
                    "line": pending_cfg[1],
                    "item": line.strip(),
                }
            )
            pending_cfg = None
        definition = re.search(rf"\bmacro_rules!\s*({RUST_IDENT})", line)
        if definition:
            macros.append(
                {
                    "name": definition.group(1),
                    "kind": "macro_rules-definition",
                    "line": line_number,
                    "expansion_resolved": False,
                }
            )
        for invocation in re.finditer(rf"\b({RUST_IDENT})!\s*[([{{]", line):
            name = invocation.group(1)
            if name != "macro_rules":
                macros.append(
                    {
                        "name": name,
                        "kind": "macro-invocation",
                        "line": line_number,
                        "expansion_resolved": False,
                    }
                )
        for trait in re.finditer(rf"\bdyn\s+({RUST_IDENT}(?:::{RUST_IDENT})*)", line):
            dispatch.append(
                {
                    "trait": trait.group(1),
                    "line": line_number,
                    "runtime_targets_resolved": False,
                }
            )
    return modules, reexports, cfgs, macros, dispatch


def _resolve_module(source: Path, name: str) -> Path | None:
    base = _module_base(source)
    candidates = [base / f"{name}.rs", base / name / "mod.rs"]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _target_package(metadata: dict[str, Any], target: Path) -> dict[str, Any] | None:
    for package in metadata.get("packages", []):
        manifest_parent = Path(package["manifest_path"]).resolve(strict=False).parent
        if manifest_parent == target:
            return package
    return None


def _map_modules(
    package: dict[str, Any],
    project_root: Path,
    active_cfg: dict[str, set[str]],
) -> tuple[
    set[Path],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    library_targets = [
        target for target in package.get("targets", []) if "lib" in target.get("kind", [])
    ]
    if not library_targets:
        return set(), [], [], [], [], []
    root = Path(library_targets[0]["src_path"])
    pending = [root]
    reachable: set[Path] = set()
    edges: list[dict[str, Any]] = []
    reexports: list[dict[str, Any]] = []
    cfg_rows: list[dict[str, Any]] = []
    macro_rows: list[dict[str, Any]] = []
    dispatch_rows: list[dict[str, Any]] = []
    module_children: dict[tuple[Path, str], Path] = {}
    raw_reexports: list[tuple[Path, dict[str, Any]]] = []
    while pending:
        source = pending.pop()
        if source in reachable or source.is_symlink() or not source.is_file():
            continue
        reachable.add(source)
        modules, source_reexports, cfgs, macros, dispatch = _scan_source_lines(source)
        source_relative = _relative(source, project_root)
        for cfg in cfgs:
            cfg_rows.append(
                {
                    "source": source_relative,
                    **cfg,
                    "state": _cfg_state(cfg["expression"], active_cfg),
                    "evidence": "all-features selected host compiler/build-script cfg",
                }
            )
        macro_rows.extend({"source": source_relative, **row} for row in macros)
        dispatch_rows.extend({"source": source_relative, **row} for row in dispatch)
        raw_reexports.extend((source, row) for row in source_reexports)
        for module in modules:
            resolved = _resolve_module(source, module["name"])
            state = _cfg_state(module["cfg"], active_cfg) if module["cfg"] else "selected"
            if resolved is None or resolved.is_symlink() or state != "selected":
                continue
            try:
                resolved.resolve(strict=False).relative_to(project_root)
            except ValueError:
                continue
            module_children[(source, module["name"])] = resolved
            edges.append(
                {
                    "source": source_relative,
                    "target": _relative(resolved, project_root),
                    "module": module["name"],
                    "line": module["line"],
                    "cfg_state": state,
                }
            )
            pending.append(resolved)
    for source, row in raw_reexports:
        pieces = [piece.strip() for piece in row["path"].split("::")]
        resolved_to = None
        if len(pieces) >= 2:
            child = module_children.get((source, pieces[0]))
            if child is not None:
                resolved_to = f"{_relative(child, project_root)}::{pieces[-1]}"
        reexports.append(
            {
                "source": _relative(source, project_root),
                "path": row["path"],
                "line": row["line"],
                "resolved_to": resolved_to,
                "resolution": "module-declaration" if resolved_to else "unresolved",
            }
        )
    edges.sort(key=lambda row: (row["source"], row["line"], row["target"]))
    reexports.sort(key=lambda row: (row["source"], row["line"], row["path"]))
    cfg_rows.sort(key=lambda row: (row["source"], row["line"]))
    macro_rows.sort(key=lambda row: (row["source"], row["line"], row["kind"]))
    dispatch_rows.sort(key=lambda row: (row["source"], row["line"], row["trait"]))
    return reachable, edges, reexports, cfg_rows, macro_rows, dispatch_rows


def _source_inventory(
    project_root: Path, target: Path, reachable: set[Path]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for directory, directory_names, file_names in os.walk(project_root, followlinks=False):
        directory_path = Path(directory)
        retained_directories = sorted(
            name
            for name in directory_names
            if name not in {".git", ".agents", ".claude", ".engineering", "reports"}
        )
        directory_names[:] = []
        for name in retained_directories:
            child = directory_path / name
            if child.is_symlink():
                rows.append(
                    {
                        "path": child.relative_to(project_root).as_posix(),
                        "role": "symlink-excluded",
                        "included": False,
                        "reason": "symlinked directories are not traversed as first-party evidence",
                    }
                )
            else:
                directory_names.append(name)
        for name in sorted(file_names):
            if not name.endswith(".rs"):
                continue
            path = directory_path / name
            relative = path.relative_to(project_root)
            parts = set(relative.parts)
            if path.is_symlink():
                role, included, reason = (
                    "symlink-excluded",
                    False,
                    "symlinked sources are not first-party evidence",
                )
            elif "target" in parts:
                role, included, reason = "target-output", False, "Cargo target output is generated"
            elif "vendor" in parts:
                role, included, reason = "vendor", False, "vendored code is not first-party"
            elif "generated" in parts:
                role, included, reason = "generated", False, "generated tree is not first-party"
            elif path == target / "build.rs":
                role, included, reason = (
                    "custom-build",
                    False,
                    "build script provenance is separate from production modules",
                )
            elif "tests" in parts:
                role, included, reason = "test", False, "test target is not production code"
            elif "examples" in parts:
                role, included, reason = "example", False, "example target is not production code"
            elif "benches" in parts:
                role, included, reason = "bench", False, "benchmark target is not production code"
            elif path in reachable:
                role, included, reason = (
                    "production-module",
                    True,
                    "reachable from selected library target",
                )
            elif target in path.parents and "src" in parts:
                role, included, reason = (
                    "unreachable-source",
                    False,
                    "not reachable from selected library target",
                )
            elif "src" in parts:
                role, included, reason = (
                    "workspace-consumer",
                    False,
                    "outside selected subsystem package",
                )
            else:
                role, included, reason = "auxiliary", False, "not a selected production module"
            rows.append(
                {
                    "path": relative.as_posix(),
                    "role": role,
                    "included": included,
                    "reason": reason,
                }
            )
    rows.sort(key=lambda row: row["path"])
    return rows


class _LspClient:
    """Minimal JSON-RPC/LSP client; no rust-analyzer private CLI is used."""

    def __init__(self, executable: str, project_root: Path, env: dict[str, str]) -> None:
        self.project_root = project_root
        self.process = subprocess.Popen(
            [executable],
            cwd=project_root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.messages: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self.next_id = 1
        self.reader = threading.Thread(target=self._read_messages, daemon=True)
        self.reader.start()

    def _read_messages(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                headers: dict[str, str] = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        return
                    if line in {b"\r\n", b"\n"}:
                        break
                    key, _, value = line.decode("ascii", errors="replace").partition(":")
                    headers[key.lower()] = value.strip()
                length = int(headers["content-length"])
                body = self.process.stdout.read(length)
                self.messages.put(json.loads(body.decode("utf-8")))
        except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            self.messages.put(exc)

    def send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.process.stdin.flush()

    def notify(self, method: str, params: Any = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self.send(payload)

    def _answer_server_request(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method == "workspace/configuration":
            result: Any = [{} for _ in message.get("params", {}).get("items", [])]
        elif method == "workspace/workspaceFolders":
            result = [{"uri": self.project_root.as_uri(), "name": self.project_root.name}]
        else:
            result = None
        self.send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def request(
        self,
        method: str,
        params: Any,
        timeout: float = 60.0,
        content_retries: int = 3,
    ) -> Any:
        request_id = self.next_id
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"LSP request timed out: {method}")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"LSP request timed out: {method}") from exc
            if isinstance(message, Exception):
                raise RuntimeError(f"LSP reader failed: {message}") from message
            if "id" in message and "method" in message:
                self._answer_server_request(message)
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                if message["error"].get("code") == -32801 and content_retries:
                    time.sleep(0.1)
                    return self.request(
                        method,
                        params,
                        timeout=max(deadline - time.monotonic(), 1),
                        content_retries=content_retries - 1,
                    )
                raise RuntimeError(f"LSP {method} error: {message['error']}")
            return message.get("result")

    def close(self) -> None:
        try:
            if self.process.poll() is None:
                self.request("shutdown", None, timeout=10)
                self.notify("exit")
                self.process.wait(timeout=10)
        except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError):
            self.process.kill()
            self.process.wait(timeout=5)


def _flatten_document_symbols(
    symbols: Any, source: str, parent: str | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(symbols, list):
        return rows
    for symbol in symbols:
        if not isinstance(symbol, dict):
            continue
        name = symbol.get("name")
        container = symbol.get("containerName") or parent
        selection = symbol.get("selectionRange") or symbol.get("location", {}).get("range") or {}
        start = selection.get("start", {})
        row = {
            "source": source,
            "name": name,
            "kind": symbol.get("kind"),
            "container": container,
            "detail": symbol.get("detail"),
            "line": start.get("line", 0) + 1,
            "column": start.get("character", 0) + 1,
            "lsp_position": {"line": start.get("line", 0), "character": start.get("character", 0)},
        }
        rows.append(row)
        rows.extend(_flatten_document_symbols(symbol.get("children"), source, name))
    return rows


def _uri_to_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def _semantic_lsp(
    rust_analyzer: str | None,
    project_root: Path,
    env: dict[str, str],
    reachable: set[Path],
    semantic_files: set[Path],
    public_reexports: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "protocol": "LSP",
        "methods": [
            "initialize",
            "textDocument/documentSymbol",
            "textDocument/definition",
            "workspace/symbol",
        ],
        "unstable_cli_used": False,
    }
    if rust_analyzer is None:
        return (
            {**base, "state": "tool-missing", "detail": "rust-analyzer executable not found"},
            [],
            [],
        )
    client: _LspClient | None = None
    document_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    try:
        client = _LspClient(rust_analyzer, project_root, env)
        client.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": project_root.as_uri(),
                "capabilities": {
                    "workspace": {
                        "configuration": True,
                        "workspaceFolders": True,
                        "symbol": {},
                    },
                    "textDocument": {
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "definition": {"linkSupport": True},
                    },
                },
                "workspaceFolders": [{"uri": project_root.as_uri(), "name": project_root.name}],
                "initializationOptions": {"cargo": {"allFeatures": True}},
            },
            timeout=60,
        )
        client.notify("initialized", {})
        workspace_symbols: list[dict[str, Any]] = []
        readiness_names = sorted(
            {row["path"].rsplit("::", 1)[-1] for row in public_reexports if row.get("resolved_to")}
        )
        readiness_query = readiness_names[0] if readiness_names else None
        if readiness_query:
            ready_deadline = time.monotonic() + 30
            while time.monotonic() < ready_deadline:
                result = client.request("workspace/symbol", {"query": readiness_query}, timeout=10)
                workspace_symbols = result if isinstance(result, list) else []
                if any(row.get("name") == readiness_query for row in workspace_symbols):
                    break
                time.sleep(0.1)
        for source in sorted(reachable):
            relative = _relative(source, project_root)
            symbols = client.request(
                "textDocument/documentSymbol",
                {"textDocument": {"uri": source.as_uri()}},
                timeout=60,
            )
            document_rows.extend(_flatten_document_symbols(symbols, relative))
        public_names = sorted(
            {row["path"].rsplit("::", 1)[-1] for row in public_reexports if row.get("resolved_to")}
        )
        for source in sorted(semantic_files - reachable):
            source_lines = source.read_text(encoding="utf-8").splitlines()
            for line_index, source_line in enumerate(source_lines):
                for symbol_name in public_names:
                    for match in re.finditer(rf"\b{re.escape(symbol_name)}\b", source_line):
                        definitions = client.request(
                            "textDocument/definition",
                            {
                                "textDocument": {"uri": source.as_uri()},
                                "position": {
                                    "line": line_index,
                                    "character": match.start(),
                                },
                            },
                            timeout=60,
                        )
                        if isinstance(definitions, dict):
                            definitions = [definitions]
                        for definition in definitions or []:
                            target_uri = definition.get("targetUri") or definition.get("uri", "")
                            target_path = _uri_to_path(target_uri)
                            if target_path is None:
                                continue
                            try:
                                declaration = (
                                    target_path.resolve(strict=False)
                                    .relative_to(project_root)
                                    .as_posix()
                                )
                            except ValueError:
                                continue
                            reference_rows.append(
                                {
                                    "symbol": symbol_name,
                                    "declaration": declaration,
                                    "source": _relative(source, project_root),
                                    "line": line_index + 1,
                                    "column": match.start() + 1,
                                    "direction": "inbound",
                                    "evidence": "textDocument/definition",
                                }
                            )
        for row in document_rows:
            row.pop("lsp_position", None)
        document_rows.sort(key=lambda row: (row["source"], row["line"], row["name"] or ""))
        reference_rows = list(
            {
                (
                    row["symbol"],
                    row["declaration"],
                    row["source"],
                    row["line"],
                    row["column"],
                    row["direction"],
                    row["evidence"],
                ): row
                for row in reference_rows
            }.values()
        )
        reference_rows.sort(key=lambda row: (row["source"], row["line"], row["column"]))
        return (
            {
                **base,
                "state": "complete",
                "detail": "document symbols and bounded public-symbol relationships came from stable LSP requests",
                "files_queried": len(reachable),
                "relationship_count": len(reference_rows),
                "workspace_symbol_query": readiness_query,
                "workspace_symbol_ready": any(
                    row.get("name") == readiness_query for row in workspace_symbols
                ),
            },
            document_rows,
            reference_rows,
        )
    except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as exc:
        for row in document_rows:
            row.pop("lsp_position", None)
        return {**base, "state": "failed", "detail": str(exc)}, document_rows, reference_rows
    finally:
        if client is not None:
            client.close()


def _active_cfg(
    package: dict[str, Any], rustc_cfg: dict[str, list[str]], build_scripts: list[dict[str, Any]]
) -> dict[str, set[str]]:
    active = {key: set(values) for key, values in rustc_cfg.items()}
    active["feature"] = set(package.get("features", {}).keys())
    for script in build_scripts:
        if script.get("package") != package.get("name"):
            continue
        for value in script.get("cfgs", []):
            match = re.fullmatch(rf"({RUST_IDENT})=\"([^\"]+)\"", value)
            if match:
                active.setdefault(match.group(1), set()).add(match.group(2))
            else:
                active.setdefault(value, set()).add("true")
    return active


def _base_payload(
    *,
    name: str,
    target: Path,
    project_root: Path,
    snapshot: list[dict[str, str]],
    cargo: str | None,
    rustc: str | None,
    rust_analyzer: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "target": _relative(target, project_root),
        "status": "partial",
        "diagnostic_state": "unavailable",
        "failure_kind": None,
        "analyzer": ANALYZER,
        "tools": {
            "cargo": {"available": cargo is not None, "version": _tool_version(cargo)},
            "rustc": {"available": rustc is not None, "version": _tool_version(rustc)},
            "rust_analyzer": {
                "available": rust_analyzer is not None,
                "version": _tool_version(rust_analyzer),
            },
        },
        "workspace": {"root": ".", "members": [], "resolver": None},
        "packages": [],
        "package_dependency_edges": [],
        "cargo_targets": [],
        "compiler": {
            "state": "unavailable",
            "command": [
                "cargo",
                "check",
                "--message-format=json",
                "--locked",
                "--offline",
                "--workspace",
                "--all-targets",
                "--all-features",
            ],
            "diagnostics": [],
            "artifacts": [],
            "malformed_message_lines": 0,
            "stderr": "",
        },
        "build_scripts": [],
        "selected_host_cfg": {},
        "source_inventory": [],
        "module_edges": [],
        "public_reexports": [],
        "cfg_boundaries": [],
        "macro_boundaries": [],
        "trait_dispatch_boundaries": [],
        "document_symbols": [],
        "reference_edges": [],
        "semantic_analysis": {
            "state": "not-run",
            "protocol": "LSP",
            "methods": [],
            "unstable_cli_used": False,
            "detail": "semantic analyzer did not run",
        },
        "completeness": {
            "cargo_project_model": "unresolved",
            "selected_build_diagnostics": "unresolved",
            "selected_module_graph": "unresolved",
            "stable_lsp_symbols_and_definitions": "unresolved",
            "macro_expansion": "unresolved",
            "procedural_macro_expansion": "unresolved",
            "generated_build_output_contents": "unresolved",
            "runtime_trait_dispatch": "unresolved",
            "unselected_cfg_and_target_variants": "unresolved",
            "include_macro_contents": "unresolved",
        },
        "limits": [
            "macro_rules and procedural-macro expansions are not expanded into source facts",
            "build-script execution is recorded, but OUT_DIR contents are not treated as first-party source",
            "only --all-features on the selected host target is compiler-checked",
            "dyn trait spelling does not resolve runtime implementations",
            "include! content and unselected target triples require separate evidence",
        ],
        "source_snapshot": snapshot,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Rust subsystem map: {payload['name']}",
        "",
        f"Status: **{payload['status']}**",
        "",
        f"Diagnostic state: **{payload['diagnostic_state']}**",
        "",
        f"Target: `{payload['target']}`",
        "",
        "## Evidence boundary",
        "",
        "Cargo locked/offline metadata and compiler JSON define the selected project/build facts. "
        "rust-analyzer contributes document symbols and bounded definitions through stable LSP only; "
        "no unstable rust-analyzer CLI or private rustc interface is used.",
        "",
    ]
    if payload.get("failure_kind"):
        lines.extend(
            [
                "## Terminal condition",
                "",
                f"`{payload['failure_kind']}` — {payload.get('failure_detail') or 'see evidence JSON'}",
                "",
            ]
        )
    lines.extend(["## Workspace", ""])
    members = payload.get("workspace", {}).get("members", [])
    lines.append(
        "Members: " + (", ".join(f"`{member}`" for member in members) if members else "unresolved")
    )
    lines.extend(["", "## Selected production module graph", ""])
    if payload.get("module_edges"):
        for edge in payload["module_edges"]:
            lines.append(f"- `{edge['source']}` → `{edge['target']}` (`mod {edge['module']}`)")
    else:
        lines.append("No compiler-gated module edges were established.")
    lines.extend(["", "## Public re-exports", ""])
    if payload.get("public_reexports"):
        for row in payload["public_reexports"]:
            destination = row.get("resolved_to") or "unresolved"
            lines.append(f"- `{row['path']}` from `{row['source']}` → `{destination}`")
    else:
        lines.append("No bounded public re-export facts were established.")
    lines.extend(["", "## Cargo target provenance", ""])
    if payload.get("cargo_targets"):
        for row in payload["cargo_targets"]:
            lines.append(f"- `{row['package']}` `{row['kind']}`: `{row['source']}`")
    else:
        lines.append("Cargo target provenance is unresolved.")
    lines.extend(["", "## Semantic evidence", ""])
    semantic = payload.get("semantic_analysis", {})
    lines.append(
        f"rust-analyzer state: **{semantic.get('state', 'unresolved')}**; protocol: "
        f"**{semantic.get('protocol', 'LSP')}**; unstable CLI used: "
        f"**{str(semantic.get('unstable_cli_used', False)).lower()}**."
    )
    public_names = sorted(
        {row["name"] for row in payload.get("document_symbols", []) if row.get("name")}
        | {
            row["resolved_to"].rsplit("::", 1)[-1]
            for row in payload.get("public_reexports", [])
            if row.get("resolved_to")
        }
    )
    if public_names:
        lines.append(
            "Observed names include: " + ", ".join(f"`{name}`" for name in public_names[:30]) + "."
        )
    lines.extend(["", "## Explicit unresolved boundaries", ""])
    for key, value in payload.get("completeness", {}).items():
        if value == "unresolved":
            lines.append(f"- `{key}`: unresolved")
    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "A partial status is useful and intentional: selected Cargo/compiler facts remain actionable, "
        "while macros, generated output, cfg/feature/target variants, and runtime trait dispatch are not "
        "promoted beyond their evidence. Missing tooling is a recoverable limit, never a permanent "
        "unsupported-language claim."
    )
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any], markdown: str, output: Path, evidence: Path) -> None:
    payload_without_hashes = dict(payload)
    payload_without_hashes.pop("artifact_hashes", None)
    payload["artifact_hashes"] = {
        "markdown_sha256": _sha256_text(markdown),
        "evidence_payload_sha256": _sha256_text(_canonical_json(payload_without_hashes)),
    }
    _atomic_write(output, markdown)
    _atomic_write(
        evidence, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def _verify(project_root: Path, output: Path, evidence: Path) -> int:
    checks = {
        "artifacts_present": output.is_file() and evidence.is_file(),
        "markdown": False,
        "evidence_payload": False,
        "source_snapshot": False,
        "schema": False,
        "terminal_status": False,
    }
    if checks["artifacts_present"]:
        try:
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            hashes = payload.get("artifact_hashes", {})
            without_hashes = dict(payload)
            without_hashes.pop("artifact_hashes", None)
            checks["markdown"] = _sha256_bytes(output.read_bytes()) == hashes.get("markdown_sha256")
            checks["evidence_payload"] = _sha256_text(
                _canonical_json(without_hashes)
            ) == hashes.get("evidence_payload_sha256")
            checks["source_snapshot"] = payload.get("source_snapshot") == _source_snapshot(
                project_root
            )
            checks["schema"] = payload.get("schema_version") == SCHEMA_VERSION
            checks["terminal_status"] = payload.get("status") in {"complete", "partial", "failed"}
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    if all(checks.values()):
        print(f"verified Rust subsystem map artifacts: {output} and {evidence}")
        return 0
    print(json.dumps(checks, sort_keys=True), file=sys.stderr)
    return 2


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-analyzer", default="rust-analyzer")
    parser.add_argument("--cargo-target-dir")
    parser.add_argument("--verify-artifacts", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        project_root = Path(args.project_root).resolve(strict=True)
        if not project_root.is_dir():
            raise ValueError(f"project root is not a directory: {project_root}")
        target = _safe_target(args.target, project_root)
        output = _safe_destination(args.output, project_root, OUTPUT_PREFIX)
        evidence = _safe_destination(args.evidence, project_root, EVIDENCE_PREFIX)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.verify_artifacts:
        return _verify(project_root, output, evidence)

    cargo = _resolve_tool(args.cargo)
    rustc = _resolve_tool(args.rustc)
    rust_analyzer = _resolve_tool(args.rust_analyzer)
    cargo_target_dir = (
        Path(args.cargo_target_dir).resolve(strict=False)
        if args.cargo_target_dir
        else Path(tempfile.mkdtemp(prefix="rust-map-cargo-target-"))
    )
    cargo_target_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _source_snapshot(project_root)
    payload = _base_payload(
        name=args.name,
        target=target,
        project_root=project_root,
        snapshot=snapshot,
        cargo=cargo,
        rustc=rustc,
        rust_analyzer=rust_analyzer,
    )
    env = _cargo_environment(cargo_target_dir, rustc)

    if cargo is None:
        payload["failure_kind"] = "cargo_missing"
        payload["failure_detail"] = (
            "Cargo is unavailable; source inventory is retained without project-model claims"
        )
        payload["source_inventory"] = _source_inventory(project_root, target, set())
        markdown = _render_markdown(payload)
        _write_artifacts(payload, markdown, output, evidence)
        print(f"wrote partial Rust subsystem map: {output}")
        return 0

    metadata, metadata_error = _cargo_metadata(cargo, project_root, env)
    if metadata is None:
        payload["status"] = "failed"
        payload["failure_kind"] = "cargo_metadata_failed"
        payload["failure_detail"] = metadata_error
        payload["source_inventory"] = _source_inventory(project_root, target, set())
        markdown = _render_markdown(payload)
        _write_artifacts(payload, markdown, output, evidence)
        print(metadata_error, file=sys.stderr)
        return 2

    workspace, packages, dependencies, cargo_targets, packages_by_id = _workspace_model(
        metadata, project_root
    )
    payload.update(
        {
            "workspace": workspace,
            "packages": packages,
            "package_dependency_edges": dependencies,
            "cargo_targets": cargo_targets,
        }
    )
    payload["completeness"]["cargo_project_model"] = "complete-selected-locked-offline"
    package = _target_package(metadata, target)
    if package is None:
        payload["status"] = "failed"
        payload["failure_kind"] = "target_package_not_found"
        payload["failure_detail"] = "target must be the directory of a Cargo workspace package"
        payload["source_inventory"] = _source_inventory(project_root, target, set())
        markdown = _render_markdown(payload)
        _write_artifacts(payload, markdown, output, evidence)
        return 2

    compiler, build_scripts = _compiler_check(
        cargo, project_root, env, cargo_target_dir, packages_by_id
    )
    payload["compiler"] = compiler
    payload["build_scripts"] = build_scripts
    if compiler["state"] != "clean":
        payload["status"] = "failed"
        payload["diagnostic_state"] = "failed"
        payload["failure_kind"] = "cargo_check_failed"
        payload["failure_detail"] = (
            compiler.get("stderr") or "compiler diagnostics contain the failure"
        )
        payload["source_inventory"] = _source_inventory(project_root, target, set())
        markdown = _render_markdown(payload)
        _write_artifacts(payload, markdown, output, evidence)
        print(payload["failure_detail"], file=sys.stderr)
        return 2

    payload["diagnostic_state"] = "clean"
    payload["completeness"]["selected_build_diagnostics"] = "complete-selected-build"
    rustc_cfg, rustc_cfg_error = _rustc_cfg(rustc, project_root, env)
    payload["selected_host_cfg"] = rustc_cfg
    if rustc_cfg_error:
        payload["rustc_cfg_detail"] = rustc_cfg_error
    active_cfg = _active_cfg(package, rustc_cfg, build_scripts)
    reachable, module_edges, reexports, cfgs, macros, dispatch = _map_modules(
        package, project_root, active_cfg
    )
    source_inventory = _source_inventory(project_root, target, reachable)
    payload.update(
        {
            "source_inventory": source_inventory,
            "module_edges": module_edges,
            "public_reexports": reexports,
            "cfg_boundaries": cfgs,
            "macro_boundaries": macros,
            "trait_dispatch_boundaries": dispatch,
        }
    )
    payload["completeness"]["selected_module_graph"] = "complete-selected-simple-mod-declarations"
    semantic_roles = {
        "production-module",
        "workspace-consumer",
        "test",
        "example",
        "bench",
        "custom-build",
    }
    semantic_files = {
        project_root / row["path"] for row in source_inventory if row["role"] in semantic_roles
    }
    semantic, symbols, references = _semantic_lsp(
        rust_analyzer,
        project_root,
        env,
        reachable,
        semantic_files,
        reexports,
    )
    payload["semantic_analysis"] = semantic
    payload["document_symbols"] = symbols
    payload["reference_edges"] = references
    if semantic["state"] == "complete":
        payload["completeness"]["stable_lsp_symbols_and_definitions"] = "complete-selected-queries"
    elif semantic["state"] == "tool-missing":
        payload["failure_kind"] = "rust_analyzer_missing"
        payload["failure_detail"] = semantic["detail"]
    else:
        payload["failure_kind"] = "rust_analyzer_failed"
        payload["failure_detail"] = semantic["detail"]
    if rustc is None and payload["failure_kind"] is None:
        payload["failure_kind"] = "rustc_missing"
        payload["failure_detail"] = (
            "rustc cfg/version probing was unavailable; Cargo-selected facts remain useful"
        )

    if _source_snapshot(project_root) != snapshot:
        payload["status"] = "failed"
        payload["diagnostic_state"] = "failed"
        payload["failure_kind"] = "source_mutation_detected"
        payload["failure_detail"] = "mapping changed the audited project source snapshot"
        payload["source_snapshot"] = _source_snapshot(project_root)
        markdown = _render_markdown(payload)
        _write_artifacts(payload, markdown, output, evidence)
        return 2

    markdown = _render_markdown(payload)
    _write_artifacts(payload, markdown, output, evidence)
    print(f"wrote partial Rust subsystem map: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
