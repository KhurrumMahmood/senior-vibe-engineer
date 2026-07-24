#!/usr/bin/env python3
"""Render one manifest-selected C# subsystem from copied bounded providers."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA = "csharp-subsystem-map-v1"
EXPECTED_AUTHORITY = {
    "kind": "sdk-bundled-roslyn-after-direct-csc-native-gates",
    "sdk_version": "10.0.302",
    "runtime_version": "10.0.10",
    "dotnet_sha256": "ed8eb05ce0598b40df34f464d16063b30896c7e28dc1ac9e94554a8aff9676ed",
    "csc_sha256": "c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81",
    "code_analysis_sha256": "eabc44a97ca36c415af0d7a4db353c170fad26da897b11862927bdb3402f3786",
    "csharp_analysis_sha256": "daff05fe558690b194b93e99d1299f2a85afba55c41fba5718dba6bdfd36bfe9",
    "reference_pack_sha256": "9719ee9a053103d3de4b3bfb91f230d9a58325f47e7ac90a2147649d288f2fdd",
    "reference_count": 167,
    "helper_sha256": "0475a903da8973491775d627da2ca48c274e0c0684063ec229a26e439f5ed980",
}
LEXICAL_HELPER_SHA256 = (
    "65474b5a3e53cee8bfe035f925ad14d97f291f21baac1c4de5c12ae2f6ffdd16"
)
LIMITS = [
    "Complete means only that the exact manifest-selected C# 14/.NET 10 source and test snapshot compiled, replayed its native test and smoke programs, and bound without Roslyn error diagnostics under the pinned SDK authority.",
    "Direct calls and references are compiler-resolved static edges present in the Roslyn fact pack; they do not establish runtime reachability, virtual/interface dispatch targets, or behavior.",
    "Reflection and runtime-name lookup, delegates and method groups, override dispatch, interface dispatch, and dynamic dispatch remain unresolved even when the fact pack records their source locations.",
    "Generated/vendor inputs, source generators, analyzers, compiler plugins, conditional compilation variants, and generated partial declarations are outside the authored source map.",
    "Solution and project-reference graphs, NuGet restore, MSBuild evaluation, framework registration and routing, external callers, serialization, interop, trimming/AOT, ABI compatibility, and runtime mutation authority are not mapped.",
]
BOUNDARIES = [
    {
        "kind": "runtime_dispatch_and_reachability",
        "state": "unresolved",
        "detail": "Static binding does not prove runtime reachability, behavior, or virtual/dynamic targets.",
    },
    {
        "kind": "reflection_and_runtime_names",
        "state": "unresolved",
        "detail": "Reflection and string-based runtime lookup are retained only as boundary evidence.",
    },
    {
        "kind": "delegates_and_method_groups",
        "state": "unresolved",
        "detail": "Delegate construction, method groups, and invocation targets are not expanded into runtime edges.",
    },
    {
        "kind": "override_dispatch",
        "state": "unresolved",
        "detail": "Declared override metadata does not establish a complete hierarchy or dispatched runtime target.",
    },
    {
        "kind": "interface_dispatch",
        "state": "unresolved",
        "detail": "Explicit implementation metadata does not establish interface dispatch or every implementation.",
    },
    {
        "kind": "generated_and_source_generator_inputs",
        "state": "unresolved",
        "detail": "Generated/vendor files and source-generator or analyzer output are excluded from authored declarations.",
    },
    {
        "kind": "project_and_solution_graph",
        "state": "unresolved",
        "detail": "Project references, solutions, NuGet restore, MSBuild variants, and external consumers are not evaluated.",
    },
    {
        "kind": "framework_registration",
        "state": "unresolved",
        "detail": "Framework routing, dependency injection, serialization, and convention-based registration are not inferred.",
    },
]
STRUCTURAL_KEYS = (
    "namespaces",
    "files",
    "qualified_declarations",
    "types",
    "methods",
    "properties",
    "public_surface",
    "private_surface",
    "other_visibility",
    "direct_resolved_calls",
    "direct_resolved_references",
    "namespace_edges",
    "observed_boundary_evidence",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _json(path: Path, payload: Any) -> None:
    _atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load copied C# provider: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _providers() -> tuple[ModuleType | None, ModuleType | None]:
    skills = next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "_csharp/csharp_facts.py").is_file()
            or (parent / "_csharp-semantic/csharp_semantic_facts.py").is_file()
        ),
        None,
    )
    if skills is None:
        return None, None
    lexical_path = skills / "_csharp/csharp_facts.py"
    semantic_path = skills / "_csharp-semantic/csharp_semantic_facts.py"
    lexical = _load(lexical_path, "csharp_map_lexical") if lexical_path.is_file() else None
    semantic = (
        _load(semantic_path, "csharp_map_semantic")
        if semantic_path.is_file()
        else None
    )
    return lexical, semantic


def _safe_destination(root: Path, supplied: Path, allowed: Path, label: str) -> Path:
    destination = Path(
        os.path.abspath(supplied if supplied.is_absolute() else root / supplied)
    )
    try:
        relative = destination.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"{label} must stay beneath {allowed.relative_to(root)}") from exc
    if not relative.parts:
        raise ValueError(f"{label} must name a file")
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} cannot traverse a symbolic link")
    return destination


def _safe_target(root: Path, supplied: Path) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    target = candidate.resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("target must stay inside project root") from exc
    if candidate.is_symlink() or not (target.is_file() or target.is_dir()):
        raise ValueError("target must be a regular file or directory")
    return target


def _selected(root: Path, target: Path, relative: str) -> bool:
    candidate = root / relative
    return candidate == target if target.is_file() else target in candidate.parents


def _analysis_summary(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {
        key: payload.get(key)
        for key in (
            "schema_version",
            "status",
            "failure_kind",
            "failure_detail",
            "project_root",
            "manifest_path",
            "manifest_sha256",
            "project_contract_sha256",
            "source_manifest_sha256",
            "fact_pack_sha256",
        )
        if key in payload
    }


def _empty(
    *,
    root: Path,
    name: str,
    target: Path,
    status: str,
    failure_kind: str,
    lexical: dict[str, Any] | None = None,
    semantic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "name": name,
        "target": _display_target(root, target),
        "status": status,
        "failure_kind": failure_kind,
        "manifest_state": "incomplete",
        "manifest_evidence": {},
        "source_inventory": [],
        "test_inventory": [],
        "excluded_inventory": [],
        "semantic_authority": {},
        "native_checks": {},
        "source_preservation": {
            "verified": bool(
                lexical
                and lexical.get("source_manifest", {}).get("preserved")
                and (semantic is None or semantic.get("source_preservation", {}).get("unchanged"))
            )
        },
        "provider_outcomes": {
            "csharp_lexical": _analysis_summary(lexical),
            "csharp_semantic": _analysis_summary(semantic),
        },
        **{key: [] for key in STRUCTURAL_KEYS},
        "unresolved": {"calls": 0, "references": 0, "examples": []},
        "unresolved_boundaries": BOUNDARIES,
        "limits": LIMITS,
    }


def _display_target(root: Path, target: Path) -> str:
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return str(target)


def _current_manifest(path: Path, expected: dict[str, Any]) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")) == expected
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def _authority(
    semantic: dict[str, Any], lexical_provider: ModuleType, semantic_provider: ModuleType
) -> tuple[dict[str, Any], str | None]:
    authority = semantic.get("semantic_authority", {})
    tools = semantic.get("tools", {})
    assemblies = tools.get("assemblies", [])
    provider_path = Path(semantic_provider.__file__).resolve()
    helper_path = provider_path.with_name("CSharpSemanticFacts.cs")
    lexical_provider_path = Path(lexical_provider.__file__).resolve()
    lexical_helper_path = lexical_provider_path.with_name("CSharpSyntaxFacts.cs")
    actual = {
        "kind": authority.get("kind"),
        "sdk_version": authority.get("sdk_version"),
        "runtime_version": authority.get("runtime_version"),
        "dotnet_sha256": tools.get("dotnet", {}).get("sha256"),
        "csc_sha256": tools.get("csc", {}).get("sha256"),
        "code_analysis_sha256": assemblies[0].get("sha256") if len(assemblies) == 2 else None,
        "csharp_analysis_sha256": assemblies[1].get("sha256") if len(assemblies) == 2 else None,
        "reference_pack_sha256": tools.get("reference_pack", {}).get("manifest_sha256"),
        "reference_count": tools.get("reference_pack", {}).get("assembly_count"),
        "helper_sha256": authority.get("helper_sha256"),
    }
    if actual != EXPECTED_AUTHORITY:
        return {}, "csharp_semantic_authority_mismatch"
    if (
        not helper_path.is_file()
        or _sha256(helper_path) != EXPECTED_AUTHORITY["helper_sha256"]
        or authority.get("provider_sha256") != _sha256(provider_path)
    ):
        return {}, "csharp_semantic_authority_mismatch"
    if (
        not lexical_helper_path.is_file()
        or _sha256(lexical_helper_path) != LEXICAL_HELPER_SHA256
    ):
        return {}, "csharp_lexical_authority_mismatch"
    fact_pack = dict(semantic)
    recorded_fact_hash = fact_pack.pop("fact_pack_sha256", None)
    if recorded_fact_hash != _object_hash(fact_pack):
        return {}, "csharp_semantic_fact_pack_hash_mismatch"
    return {
        **actual,
        "lexical_helper_sha256": LEXICAL_HELPER_SHA256,
        "lexical_provider_sha256": _sha256(lexical_provider_path),
        "provider_sha256": authority["provider_sha256"],
        "roslyn_assembly": authority.get("roslyn_assembly"),
        "code_analysis_assembly": authority.get("code_analysis_assembly"),
        "fact_pack_sha256": recorded_fact_hash,
    }, None


def _manifest_evidence(
    root: Path, lexical: dict[str, Any], semantic: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    lexical_manifest = lexical.get("project_manifest")
    semantic_manifest = semantic.get("manifest")
    if not isinstance(lexical_manifest, dict) or not isinstance(semantic_manifest, dict):
        return {}, "csharp_manifest_evidence_missing"
    if (
        lexical_manifest.get("sources") != semantic_manifest.get("sources")
        or lexical_manifest.get("tests") != semantic_manifest.get("tests")
    ):
        return {}, "csharp_manifest_universe_mismatch"
    lexical_path = root / "csharp-project.json"
    semantic_path = Path(semantic["manifest_path"])
    if (
        not _current_manifest(lexical_path, lexical_manifest)
        or not _current_manifest(semantic_path, semantic_manifest)
        or semantic.get("manifest_sha256") != _sha256(semantic_path)
    ):
        return {}, "csharp_manifest_stale"
    lexical_inventory = {
        row["file"]: row.get("source_sha256")
        for row in lexical.get("inventory", [])
        if row.get("role") in {"source", "test"}
    }
    semantic_inventory = {
        row["path"]: row["sha256"]
        for row in semantic.get("source_inventory", [])
        if row.get("role") in {"source", "test"}
    }
    manifest_paths = [*lexical_manifest["sources"], *lexical_manifest["tests"]]
    if (
        list(lexical_inventory) != manifest_paths
        and set(lexical_inventory) != set(manifest_paths)
    ):
        return {}, "csharp_lexical_inventory_mismatch"
    if any(
        lexical_inventory.get(path) != semantic_inventory.get(path)
        or lexical_inventory.get(path) != _sha256(root / path)
        for path in manifest_paths
    ):
        return {}, "csharp_provider_snapshot_mismatch"
    return {
        "state": "current-complete-and-coherent",
        "lexical": {
            "path": "csharp-project.json",
            "sha256": _sha256(lexical_path),
            "contract_sha256": _object_hash(lexical_manifest),
        },
        "semantic": {
            "path": semantic_path.relative_to(root).as_posix(),
            "sha256": semantic["manifest_sha256"],
            "contract_sha256": semantic["project_contract_sha256"],
        },
        "selected_paths_sha256": _object_hash(
            {
                "sources": lexical_manifest["sources"],
                "tests": lexical_manifest["tests"],
                "hashes": lexical_inventory,
            }
        ),
    }, None


def _declaration(row: dict[str, Any], namespace: str) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "path": row["path"],
            "namespace": namespace,
            "line": row["line"],
            "role": row.get("role"),
            "kind": row["kind"],
            "name": row.get("name"),
            "containing_type": row.get("containing_type"),
            "symbol_id": row.get("symbol_id"),
            "signature": row.get("signature"),
            "visibility": row.get("accessibility"),
            "parameters": row.get("parameters"),
            "return_type": row.get("return_type"),
            "type": row.get("type"),
            "override": row.get("override", False),
            "overridden_symbol_id": row.get("overridden_symbol_id"),
            "explicit_interface_implementations": row.get(
                "explicit_interface_implementations", []
            ),
            "partial": row.get("partial", False),
        }.items()
        if value is not None
    }


def _edge(row: dict[str, Any], direction: str, target_path: str | None) -> dict[str, Any]:
    caller = row.get("caller") or {}
    return {
        "path": row["path"],
        "line": row["line"],
        "role": row.get("role"),
        "source": row.get("source"),
        "context": row.get("context"),
        "caller_symbol_id": caller.get("symbol_id"),
        "caller_signature": caller.get("signature"),
        "target_symbol_id": row.get("target_symbol_id"),
        "target_signature": row.get("target_signature"),
        "target_owner_path": target_path,
        "target_kind": row.get("target_kind"),
        "direction": direction,
    }


def _direction(source_selected: bool, target_selected: bool) -> str:
    if source_selected and target_selected:
        return "internal"
    return "outbound" if source_selected else "inbound"


def _inventory_rows(
    paths: list[str], hashes: dict[str, str], selected: set[str] | None = None
) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "sha256": hashes[path],
            **({"selected": path in selected} if selected is not None else {}),
        }
        for path in paths
    ]


def _map_payload(
    *,
    root: Path,
    name: str,
    target: Path,
    lexical: dict[str, Any],
    semantic: dict[str, Any],
    lexical_provider: ModuleType,
    semantic_provider: ModuleType,
) -> tuple[dict[str, Any], str | None]:
    manifest_evidence, failure = _manifest_evidence(root, lexical, semantic)
    if failure:
        return {}, failure
    authority, failure = _authority(semantic, lexical_provider, semantic_provider)
    if failure:
        return {}, failure
    project = lexical["project_manifest"]
    selected_paths = {
        path for path in project["sources"] if _selected(root, target, path)
    }
    if not selected_paths:
        return {}, "csharp_target_has_no_manifest_sources"
    lexical_files = {row["file"]: row for row in lexical["files"]}
    if set(lexical_files) != selected_paths:
        return {}, "csharp_lexical_selected_snapshot_mismatch"
    lexical_hashes = {
        row["file"]: row["source_sha256"]
        for row in lexical["inventory"]
        if row.get("source_sha256")
    }
    namespace_by_path = {
        path: lexical_files[path].get("namespace") or "<global>"
        for path in selected_paths
    }
    for row in lexical["inventory"]:
        if row.get("role") == "source" and row["file"] not in namespace_by_path:
            namespace_by_path[row["file"]] = "<outside-selected-namespace-unrecorded>"
    declarations_all = semantic["declarations"]
    selected_declarations = [
        row
        for row in declarations_all
        if row.get("role") == "source" and row["path"] in selected_paths
    ]
    declarations = sorted(
        (
            _declaration(row, namespace_by_path.get(row["path"], "<global>"))
            for row in selected_declarations
        ),
        key=lambda row: (row["path"], row["line"], row.get("symbol_id") or ""),
    )
    symbol_paths = {
        row["symbol_id"]: row["path"]
        for row in declarations_all
        if row.get("symbol_id") and row.get("role") in {"source", "test"}
    }
    selected_symbols = {
        row["symbol_id"] for row in selected_declarations if row.get("symbol_id")
    }
    calls: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for source_rows, destination in (
        (semantic["calls"], calls),
        (semantic["references"], references),
    ):
        for row in source_rows:
            if not row.get("resolved"):
                continue
            source_selected = row["path"] in selected_paths
            target_selected = row.get("target_symbol_id") in selected_symbols
            if source_selected or target_selected:
                destination.append(
                    _edge(
                        row,
                        _direction(source_selected, target_selected),
                        symbol_paths.get(row.get("target_symbol_id")),
                    )
                )
    def edge_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row["path"],
            row["line"],
            row.get("source") or "",
            row.get("target_symbol_id") or "",
            row["direction"],
        )
    calls.sort(key=edge_key)
    references = sorted(
        {json.dumps(row, sort_keys=True): row for row in references}.values(),
        key=edge_key,
    )
    unresolved_rows = [
        {
            "kind": kind,
            "path": row["path"],
            "line": row["line"],
            "source": row.get("source"),
            "candidate_signatures": row.get("candidate_signatures", []),
        }
        for kind, rows in (
            ("call", semantic["calls"]),
            ("reference", semantic["references"]),
        )
        for row in rows
        if row["path"] in selected_paths and not row.get("resolved")
    ]
    namespace_edges: set[tuple[str, str, str]] = set()
    all_namespace_by_path = {
        row["path"]: next(
            (
                declaration["signature"].rsplit(".", 1)[0]
                for declaration in declarations_all
                if declaration["path"] == row["path"]
                and declaration["kind"] in {"class", "struct", "record", "interface", "enum"}
                and "." in declaration["signature"]
            ),
            "<unknown>",
        )
        for row in semantic["source_inventory"]
    }
    for edge in [*calls, *references]:
        target_path = edge.get("target_owner_path")
        if edge["path"] not in selected_paths or target_path is None:
            continue
        source_namespace = namespace_by_path[edge["path"]]
        target_namespace = all_namespace_by_path.get(target_path, "<unknown>")
        if source_namespace != target_namespace:
            namespace_edges.add(
                (source_namespace, target_namespace, edge["direction"])
            )
    observed = [
        row
        for row in semantic["boundaries"]
        if row.get("path") in selected_paths
        or row.get("symbol_id") in selected_symbols
        or row.get("kind") in {"excluded_generated_input", "excluded_vendor_input"}
        or any(signature in {item.get("signature") for item in selected_declarations} for signature in row.get("signatures", []))
    ]
    files = []
    for path in sorted(selected_paths):
        file_declarations = [row for row in declarations if row["path"] == path]
        source = root / path
        files.append(
            {
                "path": path,
                "namespace": namespace_by_path[path],
                "sha256": lexical_hashes[path],
                "bytes": source.stat().st_size,
                "loc": len(source.read_text(encoding="utf-8").splitlines()),
                "declarations": len(file_declarations),
                "public": sum(row["visibility"] == "Public" for row in file_declarations),
                "private": sum(row["visibility"] == "Private" for row in file_declarations),
                "other_visibility": sum(
                    row["visibility"] not in {"Public", "Private"}
                    for row in file_declarations
                ),
            }
        )
    source_rows = [
        row for row in semantic["source_inventory"] if row["role"] == "source"
    ]
    test_rows = [row for row in semantic["source_inventory"] if row["role"] == "test"]
    excluded_rows = [
        row
        for row in semantic["source_inventory"]
        if row["role"] in {"generated", "vendor"}
    ]
    commands = semantic["commands"]
    payload = {
        "schema_version": SCHEMA,
        "name": name,
        "target": target.relative_to(root).as_posix(),
        "status": "complete",
        "failure_kind": "none",
        "manifest_state": "current-complete-and-coherent",
        "manifest_evidence": manifest_evidence,
        "source_inventory": _inventory_rows(
            project["sources"], {row["path"]: row["sha256"] for row in source_rows}, selected_paths
        ),
        "test_inventory": _inventory_rows(
            project["tests"], {row["path"]: row["sha256"] for row in test_rows}
        ),
        "excluded_inventory": sorted(excluded_rows, key=lambda row: row["path"]),
        "semantic_authority": authority,
        "native_checks": {
            "lexical_state": lexical["native_evidence"]["state"],
            "lexical_test_stdout": lexical["native_evidence"]["test_stdout"],
            "lexical_smoke_stdout": lexical["native_evidence"]["smoke_stdout"],
            "semantic_compile_returncode": commands["compile"]["returncode"],
            "semantic_test_compile_returncode": commands["compile_tests"]["returncode"],
            "semantic_test_returncode": commands["test"]["returncode"],
            "semantic_test_stdout": commands["test"]["stdout"],
            "semantic_smoke_returncode": commands["smoke"]["returncode"],
            "semantic_smoke_stdout": commands["smoke"]["stdout"],
            "roslyn_diagnostics": semantic["diagnostics"],
        },
        "source_preservation": {
            "verified": bool(
                lexical["source_manifest"]["preserved"]
                and semantic["source_preservation"]["unchanged"]
            ),
            "lexical_before_sha256": lexical["source_manifest"]["before_sha256"],
            "lexical_after_sha256": lexical["source_manifest"]["after_sha256"],
            "semantic_source_manifest_sha256": semantic["source_manifest_sha256"],
        },
        "provider_outcomes": {
            "csharp_lexical": _analysis_summary(lexical),
            "csharp_semantic": _analysis_summary(semantic),
        },
        "namespaces": [
            {"name": namespace, "files": sorted(paths)}
            for namespace, paths in sorted(
                _group_namespaces(namespace_by_path, selected_paths).items()
            )
        ],
        "files": files,
        "qualified_declarations": declarations,
        "types": [
            row
            for row in declarations
            if row["kind"] in {"class", "struct", "record", "interface", "enum"}
        ],
        "methods": [row for row in declarations if row["kind"] == "method"],
        "properties": [row for row in declarations if row["kind"] == "property"],
        "public_surface": [row for row in declarations if row["visibility"] == "Public"],
        "private_surface": [row for row in declarations if row["visibility"] == "Private"],
        "other_visibility": [
            row for row in declarations if row["visibility"] not in {"Public", "Private"}
        ],
        "direct_resolved_calls": calls,
        "direct_resolved_references": references,
        "namespace_edges": [
            {
                "source_namespace": source,
                "target_namespace": destination,
                "direction": direction,
            }
            for source, destination, direction in sorted(namespace_edges)
        ],
        "unresolved": {
            "calls": sum(row["kind"] == "call" for row in unresolved_rows),
            "references": sum(
                row["kind"] == "reference" for row in unresolved_rows
            ),
            "examples": unresolved_rows[:20],
        },
        "observed_boundary_evidence": sorted(
            observed,
            key=lambda row: (
                row.get("path", ""), row.get("line", 0), row.get("kind", "")
            ),
        ),
        "unresolved_boundaries": BOUNDARIES,
        "limits": LIMITS,
    }
    return payload, None


def _group_namespaces(
    namespace_by_path: dict[str, str], selected_paths: set[str]
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for path in sorted(selected_paths):
        grouped[namespace_by_path[path]].append(path)
    return grouped


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        f"subsystem: {payload['name']}",
        f"target: {payload['target']}",
        f"status: {payload['status']}",
        f"files: {len(payload['files'])}",
        f"public_symbols: {len(payload['public_surface'])}",
        "---",
        "",
        f"# {payload['name']}",
        "",
        f"Status: **{payload['status']}**",
        f"Manifest: **{payload['manifest_state']}**",
        "",
    ]
    if payload["status"] != "complete":
        lines.extend(
            [
                f"No structural map is available: `{payload['failure_kind']}`.",
                "",
                "All declaration, surface, and direct-edge arrays were replaced with empty arrays.",
                "",
                "## Unresolved boundaries",
                "",
                *[
                    f"- `{row['kind']}` — {row['detail']}"
                    for row in payload["unresolved_boundaries"]
                ],
                "",
                "## Limits",
                "",
                *[f"- {item}" for item in LIMITS],
                "",
            ]
        )
        return "\n".join(lines)
    authority = payload["semantic_authority"]
    lines.extend(
        [
            "## Evidence authority",
            "",
            f"- SDK/runtime: `{authority['sdk_version']}` / `{authority['runtime_version']}`",
            f"- Roslyn helper SHA-256: `{authority['helper_sha256']}`",
            f"- Semantic fact-pack SHA-256: `{authority['fact_pack_sha256']}`",
            f"- Native test: `{payload['native_checks']['semantic_test_stdout'].rstrip()}`",
            f"- Native smoke: `{payload['native_checks']['semantic_smoke_stdout'].rstrip()}`",
            "",
            "## Source and test inventory",
            "",
            "| Role | Selected | Path | SHA-256 |",
            "|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| source | {'yes' if row['selected'] else 'no'} | `{row['path']}` | `{row['sha256']}` |"
        for row in payload["source_inventory"]
    )
    lines.extend(
        f"| test | n/a | `{row['path']}` | `{row['sha256']}` |"
        for row in payload["test_inventory"]
    )
    lines.extend(
        [
            "",
            "## Selected files",
            "",
            "| Path | Namespace | LOC | Declarations | Public | Private |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| `{row['path']}` | `{row['namespace']}` | {row['loc']} | {row['declarations']} | {row['public']} | {row['private']} |"
        for row in payload["files"]
    )
    lines.extend(
        [
            "",
            "## Namespaces, types, methods, and properties",
            "",
            "| Visibility | Kind | Symbol | Signature | Location |",
            "|---|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| `{row['visibility']}` | `{row['kind']}` | `{row['symbol_id']}` | `{row['signature']}` | `{row['path']}:{row['line']}` |"
        for row in payload["qualified_declarations"]
    )
    lines.extend(
        [
            "",
            "## Exact direct Roslyn edges",
            "",
            f"Resolved calls/references: **{len(payload['direct_resolved_calls'])} / {len(payload['direct_resolved_references'])}**.",
            f"Unresolved selected calls/references retained: **{payload['unresolved']['calls']} / {payload['unresolved']['references']}**.",
            "",
            "### Calls",
            "",
        ]
    )
    lines.extend(
        f"- `{row['direction']}` `{row['caller_symbol_id']}` → `{row['target_symbol_id']}` at `{row['path']}:{row['line']}`"
        for row in payload["direct_resolved_calls"]
    )
    lines.extend(["", "### References", ""])
    lines.extend(
        f"- `{row['direction']}` `{row['source']}` → `{row['target_symbol_id']}` at `{row['path']}:{row['line']}`"
        for row in payload["direct_resolved_references"]
    )
    lines.extend(["", "## Unresolved boundaries", ""])
    lines.extend(
        f"- `{row['kind']}` — {row['detail']}"
        for row in payload["unresolved_boundaries"]
    )
    lines.extend(["", "## Limits", "", *[f"- {item}" for item in LIMITS], ""])
    return "\n".join(lines)


def _write(root: Path, output: Path, evidence: Path, payload: dict[str, Any]) -> None:
    markdown = _markdown(payload)
    payload["artifacts"] = {
        "markdown": output.relative_to(root).as_posix(),
        "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
        "evidence": evidence.relative_to(root).as_posix(),
    }
    _atomic(output, markdown)
    _json(evidence, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument(
        "--semantic-manifest",
        type=Path,
        default=Path("csharp-semantic-project.json"),
    )
    parser.add_argument("--dotnet", required=True)
    args = parser.parse_args(argv)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.name) is None:
        parser.error("name must be a simple slug")
    try:
        root = args.project_root.resolve(strict=True)
        target = _safe_target(root, args.target)
        output = _safe_destination(
            root, args.output, root / ".engineering/docs/subsystems", "output"
        )
        evidence = _safe_destination(
            root, args.evidence, root / "reports/map" / args.name, "evidence"
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    fact_pack = root / f"reports/csharp-semantic/map-subsystem/{args.name}-facts.json"
    for path in (output, evidence, fact_pack):
        path.unlink(missing_ok=True)
    try:
        lexical_provider, semantic_provider = _providers()
    except (ImportError, OSError, RuntimeError, SyntaxError) as exc:
        payload = _empty(
            root=root,
            name=args.name,
            target=target,
            status="partial",
            failure_kind=f"csharp_provider_load_failed:{type(exc).__name__}",
        )
        _write(root, output, evidence, payload)
        return 2
    if lexical_provider is None or semantic_provider is None:
        missing = (
            "csharp_lexical_provider_missing"
            if lexical_provider is None
            else "csharp_semantic_provider_missing"
        )
        payload = _empty(
            root=root,
            name=args.name,
            target=target,
            status="partial",
            failure_kind=missing,
        )
        _write(root, output, evidence, payload)
        return 2
    lexical, lexical_code = lexical_provider.produce(
        root, target, dotnet=args.dotnet
    )
    if lexical.get("status") != "complete":
        payload = _empty(
            root=root,
            name=args.name,
            target=target,
            status=lexical.get("status", "failed"),
            failure_kind=lexical.get("failure_kind", "csharp_lexical_failed"),
            lexical=lexical,
        )
        _write(root, output, evidence, payload)
        return lexical_code
    semantic, semantic_code = semantic_provider.collect(
        project_root=root,
        manifest_path=args.semantic_manifest,
        output=fact_pack,
        dotnet=args.dotnet,
    )
    if semantic.get("status") != "complete":
        payload = _empty(
            root=root,
            name=args.name,
            target=target,
            status=semantic.get("status", "failed"),
            failure_kind=semantic.get("failure_kind", "csharp_semantic_failed"),
            lexical=lexical,
            semantic=semantic,
        )
        _write(root, output, evidence, payload)
        return semantic_code
    payload, failure = _map_payload(
        root=root,
        name=args.name,
        target=target,
        lexical=lexical,
        semantic=semantic,
        lexical_provider=lexical_provider,
        semantic_provider=semantic_provider,
    )
    if failure:
        payload = _empty(
            root=root,
            name=args.name,
            target=target,
            status="partial",
            failure_kind=failure,
            lexical=lexical,
            semantic=semantic,
        )
        _write(root, output, evidence, payload)
        return 2
    _write(root, output, evidence, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
