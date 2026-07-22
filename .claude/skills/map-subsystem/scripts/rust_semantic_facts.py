#!/usr/bin/env python3
"""Bounded Cargo/compiler/LSP facts shared by Rust semantic consumers.

This is intentionally not a Rust AST.  It reuses the accepted Rust subsystem
mapper for the selected Cargo model and asks stable LSP ``definition`` only for
consumer-supplied names.  Consumers retain their own schemas and judgments.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rust-semantic-facts-v1"
LIMITS = [
    "runtime reachability is not inferred",
    "macro_rules and procedural-macro expansions are not semantic evidence",
    "build output and include! contents are not inspected",
    "only all-features on the selected host target is compiler-checked",
    "unselected cfg and target variants remain unresolved",
    "traits, generics, unsafe, FFI, reflection strings, and external API behavior remain unresolved",
]


def _map_script() -> Path | None:
    local = Path(__file__).resolve().with_name("map_rust.py")
    if local.is_file():
        return local
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".claude" / "skills" / "map-subsystem" / "scripts" / "map_rust.py"
        if candidate.is_file():
            return candidate
        candidate = parent / "map-subsystem" / "scripts" / "map_rust.py"
        if candidate.is_file():
            return candidate
    return None


def _mapper():
    script = _map_script()
    if script is None:
        raise RuntimeError("bounded Rust map runtime is missing from the assembled closure")
    spec = importlib.util.spec_from_file_location("rust_semantic_map_runtime", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Rust map runtime: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool_release(rendered: str | None) -> tuple[int, int] | None:
    match = re.search(r"\b(\d+)\.(\d+)(?:\.\d+)?\b", rendered or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def _finalize(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    if not payload.get("source_hashes"):
        payload["source_hashes"] = [
            {"path": row["path"], "sha256": _sha256(root / row["path"]), "role": row["role"]}
            for row in payload.get("source_inventory", [])
            if (root / row["path"]).is_file() and not (root / row["path"]).is_symlink()
        ]
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    canonical = json.dumps(without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["fact_pack_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload


def _unsafe_ffi_boundaries(project_root: Path, files: list[Path]) -> list[dict[str, Any]]:
    """Record lexical unsafe/FFI regions so consumers can refuse semantic promotion."""
    rows: list[dict[str, Any]] = []
    start_pattern = re.compile(r'\bunsafe\s+(?:fn\b|\{)|\bextern(?:\s+"[^"]+")?\s*(?:fn\b|\{)')
    for source in files:
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        start: int | None = None
        depth = 0
        opened = False
        kind = ""
        for line_no, line in enumerate(lines, 1):
            if start is None:
                match = start_pattern.search(line)
                if match is None:
                    continue
                start = line_no
                kind = "unsafe" if "unsafe" in match.group(0) else "ffi"
            depth += line.count("{") - line.count("}")
            opened = opened or "{" in line
            if (opened and depth <= 0) or (not opened and ";" in line):
                rows.append(
                    {
                        "source": source.relative_to(project_root).as_posix(),
                        "start_line": start,
                        "end_line": line_no,
                        "kind": kind,
                        "reason": "unsafe/FFI source is not promoted into semantic claims",
                    }
                )
                start = None
                depth = 0
                opened = False
        if start is not None:
            rows.append(
                {
                    "source": source.relative_to(project_root).as_posix(),
                    "start_line": start,
                    "end_line": len(lines),
                    "kind": kind,
                    "reason": "unterminated unsafe/FFI lexical boundary",
                }
            )
    return rows


def _attribute_boundaries(project_root: Path, files: list[Path]) -> list[dict[str, Any]]:
    """Inventory attributes without deciding whether an unknown attribute is procedural."""
    rows: list[dict[str, Any]] = []
    known = {
        "allow",
        "warn",
        "deny",
        "forbid",
        "inline",
        "cold",
        "must_use",
        "deprecated",
        "doc",
        "cfg",
        "cfg_attr",
        "test",
        "derive",
        "repr",
    }
    pattern = re.compile(r"^\s*#\[([A-Za-z_][A-Za-z0-9_:]*)")
    for source in files:
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            match = pattern.search(line)
            if match is None:
                continue
            name = match.group(1)
            rows.append(
                {
                    "source": source.relative_to(project_root).as_posix(),
                    "line": line_no,
                    "name": name,
                    "classification": "known_builtin_or_derive"
                    if name in known
                    else "procedural_or_unknown",
                    "expanded": False,
                }
            )
    return rows


def _macro_regions(project_root: Path, files: list[Path]) -> list[dict[str, Any]]:
    """Record lexical macro_rules bodies; their contents are never source semantics."""
    rows: list[dict[str, Any]] = []
    for source in files:
        start: int | None = None
        depth = 0
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if start is None:
                if "macro_rules!" not in line:
                    continue
                start = line_no
            depth += line.count("{") - line.count("}")
            if depth <= 0 and "}" in line:
                rows.append(
                    {
                        "source": source.relative_to(project_root).as_posix(),
                        "start_line": start,
                        "end_line": line_no,
                        "expanded": False,
                    }
                )
                start = None
                depth = 0
        if start is not None:
            rows.append(
                {
                    "source": source.relative_to(project_root).as_posix(),
                    "start_line": start,
                    "end_line": line_no,
                    "expanded": False,
                }
            )
    return rows


def _definition_edges(
    mapper: Any,
    rust_analyzer: str | None,
    project_root: Path,
    env: dict[str, str],
    files: list[Path],
    queries: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    methods = [
        "initialize",
        "workspace/symbol",
        "textDocument/documentSymbol",
        "textDocument/definition",
    ]
    if rust_analyzer is None:
        return {"state": "tool-missing", "protocol": "LSP", "methods": methods}, [], []
    client = None
    rows: list[dict[str, Any]] = []
    document_rows: list[dict[str, Any]] = []
    document_failures: list[str] = []
    try:
        client = mapper._LspClient(rust_analyzer, project_root, env)
        client.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": project_root.as_uri(),
                "capabilities": {
                    "workspace": {"configuration": True, "workspaceFolders": True},
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
        # Stable workspace-symbol polling is the readiness barrier.  Inactive
        # cfg files can legitimately be absent from rust-analyzer's active VFS,
        # so a document-symbol request for every inventoried file is not one.
        readiness = queries[0] if queries else ""
        deadline = time.monotonic() + 30
        while readiness and time.monotonic() < deadline:
            symbols = client.request("workspace/symbol", {"query": readiness}, timeout=10)
            if any(row.get("name") == readiness for row in symbols or []):
                break
            time.sleep(0.1)
        preloaded: dict[Path, Any] = {}
        if not readiness and files:
            while time.monotonic() < deadline:
                try:
                    preloaded[files[0]] = client.request(
                        "textDocument/documentSymbol",
                        {"textDocument": {"uri": files[0].as_uri()}},
                        timeout=10,
                    )
                    break
                except RuntimeError:
                    time.sleep(0.1)
        for source in files:
            if source in preloaded:
                symbols = preloaded[source]
            else:
                try:
                    symbols = client.request(
                        "textDocument/documentSymbol",
                        {"textDocument": {"uri": source.as_uri()}},
                        timeout=60,
                    )
                except RuntimeError:
                    document_failures.append(source.relative_to(project_root).as_posix())
                    continue
            document_rows.extend(
                mapper._flatten_document_symbols(
                    symbols, source.relative_to(project_root).as_posix()
                )
            )
        for source in files:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
            for line_index, line in enumerate(lines):
                for query in queries:
                    for match in re.finditer(rf"\b{re.escape(query)}\b", line):
                        definitions = client.request(
                            "textDocument/definition",
                            {
                                "textDocument": {"uri": source.as_uri()},
                                "position": {"line": line_index, "character": match.start()},
                            },
                            timeout=60,
                        )
                        if isinstance(definitions, dict):
                            definitions = [definitions]
                        targets: list[dict[str, Any]] = []
                        for definition in definitions or []:
                            uri = definition.get("targetUri") or definition.get("uri", "")
                            path = mapper._uri_to_path(uri)
                            if path is None:
                                continue
                            try:
                                relative = (
                                    path.resolve(strict=False).relative_to(project_root).as_posix()
                                )
                            except ValueError:
                                relative = f"external:{path.name}"
                            target_range = (
                                definition.get("targetSelectionRange")
                                or definition.get("range")
                                or {}
                            )
                            start = target_range.get("start", {})
                            targets.append(
                                {
                                    "file": relative,
                                    "line": int(start.get("line", 0)) + 1,
                                    "column": int(start.get("character", 0)) + 1,
                                }
                            )
                        rows.append(
                            {
                                "name": query,
                                "source": source.relative_to(project_root).as_posix(),
                                "line": line_index + 1,
                                "column": match.start() + 1,
                                "definitions": targets,
                                "evidence": "textDocument/definition",
                            }
                        )
        for row in document_rows:
            row.pop("lsp_position", None)
        document_rows.sort(key=lambda row: (row["source"], row["line"], row["name"] or ""))
        return (
            {
                "state": "partial" if document_failures else "complete",
                "protocol": "LSP",
                "methods": methods,
                "unstable_cli_used": False,
                "query_count": len(queries),
                "document_failures": document_failures,
            },
            rows,
            document_rows,
        )
    except (OSError, RuntimeError, TimeoutError) as exc:
        return (
            {"state": "failed", "protocol": "LSP", "methods": methods, "detail": str(exc)},
            rows,
            document_rows,
        )
    finally:
        if client is not None:
            client.close()


def collect(
    project_root: Path,
    target: str,
    queries: list[str],
    *,
    cargo: str = "cargo",
    rustc: str = "rustc",
    rust_analyzer: str = "rust-analyzer",
    cargo_target_dir: Path | None = None,
) -> dict[str, Any]:
    """Return selected, content-addressed Rust facts without editing source."""
    mapper = _mapper()
    root = project_root.resolve(strict=True)
    selected = mapper._safe_target(target, root)
    cargo_path = mapper._resolve_tool(cargo)
    rustc_path = mapper._resolve_tool(rustc)
    ra_path = mapper._resolve_tool(rust_analyzer)
    owned_target = cargo_target_dir is None
    target_dir = cargo_target_dir or Path(tempfile.mkdtemp(prefix="rust-semantic-target-"))
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot = mapper._source_snapshot(root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_only": True,
        "status": "partial",
        "diagnostic_state": "unavailable",
        "target": selected.relative_to(root).as_posix(),
        "analyzer": "cargo-metadata+compiler-json+rust-analyzer-stable-lsp",
        "tools": {
            "cargo": {
                "available": cargo_path is not None,
                "version": mapper._tool_version(cargo_path),
            },
            "rustc": {
                "available": rustc_path is not None,
                "version": mapper._tool_version(rustc_path),
            },
            "rust_analyzer": {
                "available": ra_path is not None,
                "version": mapper._tool_version(ra_path),
            },
        },
        "workspace": {},
        "packages": [],
        "cargo_targets": [],
        "compiler": {"state": "unavailable", "diagnostics": []},
        "source_inventory": [],
        "source_hashes": [],
        "module_edges": [],
        "public_reexports": [],
        "cfg_boundaries": [],
        "macro_boundaries": [],
        "trait_dispatch_boundaries": [],
        "unsafe_ffi_boundaries": [],
        "attribute_boundaries": [],
        "macro_regions": [],
        "document_symbols": [],
        "definition_edges": [],
        "semantic_analysis": {"state": "not-run", "protocol": "LSP"},
        "limits": LIMITS,
        "source_snapshot": snapshot,
        "failure_kind": None,
    }
    try:
        if cargo_path is None:
            payload["failure_kind"] = "cargo_missing"
            payload["source_inventory"] = mapper._source_inventory(root, selected, set())
            return _finalize(payload, root)
        cargo_release = _tool_release(payload["tools"]["cargo"]["version"])
        rustc_release = _tool_release(payload["tools"]["rustc"]["version"])
        if (cargo_release is not None and cargo_release < (1, 85)) or (
            rustc_release is not None and rustc_release < (1, 85)
        ):
            payload["failure_kind"] = "rust_toolchain_too_old"
            payload["failure_detail"] = (
                "Rust 1.85 or newer is required for the selected Cargo contract"
            )
            payload["source_inventory"] = mapper._source_inventory(root, selected, set())
            return _finalize(payload, root)
        ra_release = _tool_release(payload["tools"]["rust_analyzer"]["version"])
        if ra_release is not None and ra_release < (1, 85):
            ra_path = None
            payload["tools"]["rust_analyzer"]["accepted"] = False
        env = mapper._cargo_environment(target_dir, rustc_path)
        metadata, error = mapper._cargo_metadata(cargo_path, root, env)
        if metadata is None:
            payload.update(
                status="failed", failure_kind="cargo_metadata_failed", failure_detail=error
            )
            payload["source_inventory"] = mapper._source_inventory(root, selected, set())
            return _finalize(payload, root)
        workspace, packages, dependencies, cargo_targets, packages_by_id = mapper._workspace_model(
            metadata, root
        )
        payload.update(
            workspace=workspace,
            packages=packages,
            package_dependency_edges=dependencies,
            cargo_targets=cargo_targets,
        )
        package = mapper._target_package(metadata, selected)
        if package is None:
            payload.update(status="failed", failure_kind="target_package_not_found")
            payload["source_inventory"] = mapper._source_inventory(root, selected, set())
            return _finalize(payload, root)
        compiler, build_scripts = mapper._compiler_check(
            cargo_path, root, env, target_dir, packages_by_id
        )
        payload.update(compiler=compiler, build_scripts=build_scripts)
        if compiler["state"] != "clean":
            payload.update(
                status="failed", diagnostic_state="failed", failure_kind="cargo_check_failed"
            )
            payload["source_inventory"] = mapper._source_inventory(root, selected, set())
            return _finalize(payload, root)
        payload["diagnostic_state"] = "clean"
        rustc_cfg, cfg_error = mapper._rustc_cfg(rustc_path, root, env)
        payload["selected_host_cfg"] = rustc_cfg
        if cfg_error:
            payload["rustc_cfg_detail"] = cfg_error
        active = mapper._active_cfg(package, rustc_cfg, build_scripts)
        reachable, module_edges, reexports, cfgs, macros, dispatch = mapper._map_modules(
            package, root, active
        )
        inventory = mapper._source_inventory(root, selected, reachable)
        payload.update(
            source_inventory=inventory,
            module_edges=module_edges,
            public_reexports=reexports,
            cfg_boundaries=cfgs,
            macro_boundaries=macros,
            trait_dispatch_boundaries=dispatch,
        )
        semantic_roles = {"production-module", "workspace-consumer"}
        files = [root / row["path"] for row in inventory if row["role"] in semantic_roles]
        selected_semantic, definitions, symbols = _definition_edges(
            mapper, ra_path, root, env, files, sorted(set(queries))
        )
        payload["semantic_analysis"] = {
            "state": "complete" if selected_semantic.get("state") == "complete" else "partial",
            "document_symbols": selected_semantic,
            "selected_definitions": selected_semantic,
            "protocol": "LSP",
            "unstable_cli_used": False,
        }
        payload["document_symbols"] = symbols
        payload["definition_edges"] = definitions
        payload["bounded_public_edges"] = []
        payload["unsafe_ffi_boundaries"] = _unsafe_ffi_boundaries(root, files)
        payload["attribute_boundaries"] = _attribute_boundaries(root, files)
        payload["macro_regions"] = _macro_regions(root, files)
        payload["source_hashes"] = [
            {"path": row["path"], "sha256": _sha256(root / row["path"]), "role": row["role"]}
            for row in inventory
            if (root / row["path"]).is_file() and not (root / row["path"]).is_symlink()
        ]
        if payload["semantic_analysis"]["state"] == "complete" and rustc_path is not None:
            payload["status"] = "complete"
        else:
            payload["failure_kind"] = (
                "rustc_missing" if rustc_path is None else "rust_analyzer_missing_old_or_failed"
            )
        if mapper._source_snapshot(root) != snapshot:
            payload.update(
                status="failed", diagnostic_state="failed", failure_kind="source_mutation_detected"
            )
        return _finalize(payload, root)
    finally:
        if owned_target:
            shutil.rmtree(target_dir, ignore_errors=True)


def load_or_collect(
    *,
    facts: Path | None,
    project_root: Path,
    target: str,
    queries: list[str],
    cargo: str,
    rustc: str,
    rust_analyzer: str,
    cargo_target_dir: Path | None,
) -> dict[str, Any]:
    if facts is not None:
        payload = json.loads(facts.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("incompatible Rust semantic fact pack")
        supplied_hash = payload.get("fact_pack_sha256")
        without_hash = dict(payload)
        without_hash.pop("fact_pack_sha256", None)
        canonical = json.dumps(
            without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        if supplied_hash != hashlib.sha256(canonical.encode()).hexdigest():
            raise ValueError("Rust semantic fact pack hash does not verify")
        if payload.get("target") != target:
            raise ValueError("Rust semantic fact pack target does not match the consumer target")
        for row in payload.get("source_hashes", []):
            source = project_root / row["path"]
            if not source.is_file() or source.is_symlink() or _sha256(source) != row["sha256"]:
                raise ValueError(f"Rust semantic fact pack is stale for {row['path']}")
        return payload
    return collect(
        project_root,
        target,
        queries,
        cargo=cargo,
        rustc=rustc,
        rust_analyzer=rust_analyzer,
        cargo_target_dir=cargo_target_dir,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-analyzer", default="rust-analyzer")
    parser.add_argument("--cargo-target-dir", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve(strict=True)
    output = args.output if args.output.is_absolute() else root / args.output
    output = Path(os.path.abspath(output))
    allowed = root / "reports/rust-semantic-facts"
    try:
        relative = output.relative_to(allowed)
    except ValueError:
        parser.error("output must stay beneath reports/rust-semantic-facts/")
    if not relative.parts:
        parser.error("output must name a fact-pack file")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            parser.error("output must not traverse a symbolic link")
    payload = collect(
        root,
        args.target,
        args.query,
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
        cargo_target_dir=args.cargo_target_dir,
    )
    _mapper()._atomic_write(
        output, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    print(f"wrote Rust semantic fact pack: {output}")
    return 2 if payload["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
