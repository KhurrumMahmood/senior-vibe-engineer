#!/usr/bin/env python3
"""Validate and prove accepted read-only C# structure proposals."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PROJECTS = ("CSharpCohort.App.csproj", "CSharpCohort.Tests.csproj")
BOUNDARY_GATES = {
    "namespace_identity": "same_namespace",
    "assembly_identity": "same_app_and_test_assemblies",
    "public_api": "compatibility_shims_retained_new_type_reviewed",
    "abi": "not_claimed_separate_release_approval",
    "runtime_behavior": "native_test_and_smoke_only",
    "framework_registration": "none",
    "reflection_runtime_names": "none_selected",
    "delegates_method_groups": "none_selected",
    "override_interface_dispatch": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "conditional_build_variants": "none",
    "project_graph": "exact_two_dependency_free_projects",
}
FOLDER_GATES = {
    "project_convention": "group-four-same-prefix-csharp-siblings",
    "namespace_identity": "unchanged",
    "type_identity": "unchanged",
    "assembly_identity": "unchanged",
    "public_api": "unchanged_by_source_location",
    "abi": "not_claimed_separate_release_approval",
    "runtime_behavior": "native_test_and_smoke_only",
    "framework_registration": "none",
    "reflection_path_resource": "none_selected",
    "delegates_method_groups": "none_selected",
    "override_interface_dispatch": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "conditional_build_variants": "none",
    "project_graph": "exact_two_dependency_free_projects",
}


def _accepted_evidence() -> Any:
    sys.dont_write_bytecode = True
    path = Path(__file__).with_name("csharp_accepted_evidence.py")
    if not path.is_file():
        raise RuntimeError("copied C# accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("csharp_structure_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C# accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _accepted_evidence()


def _skills_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _hash(path: Path) -> str:
    return EVIDENCE.file_hash(path)


def _accepted_verdict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") == "accepted"
        and isinstance(value.get("reviewer"), str)
        and bool(value["reviewer"].strip())
        and isinstance(value.get("notes"), str)
        and bool(value["notes"].strip())
    )


def _load_acceptance(
    root: Path,
    supplied: Path,
    skill: str,
    gates: dict[str, str],
) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "C# structure acceptance")
    payload = EVIDENCE.read_json(path, "C# structure acceptance")
    if (
        payload.get("schema_version") != "csharp-structure-acceptance-v1"
        or payload.get("language") != "csharp"
        or payload.get("consumer") != skill
        or not EVIDENCE.valid_hashed_object(payload, "acceptance_sha256")
        or not _accepted_verdict(payload.get("candidate_verdict"))
        or not _accepted_verdict(payload.get("proposal_verdict"))
    ):
        raise EVIDENCE.EvidenceError(
            "partial",
            "acceptance_invalid",
            "fresh exact candidate and proposal acceptance is required",
        )
    if payload["proposal_verdict"].get("boundary_verdicts") != gates:
        raise EVIDENCE.EvidenceError(
            "partial",
            "csharp_boundary_unresolved",
            "every exact C# structure boundary requires the accepted verdict",
        )
    if not isinstance(payload.get("selection"), dict):
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted selection must be an object"
        )
    return path, payload


def _artifact_paths(
    root: Path,
    acceptance: dict[str, Any],
    *,
    producer_kind: str,
    producer: Path,
    map_path: Path,
    facts_path: Path,
) -> None:
    expected = {
        producer_kind: producer,
        "csharp-map": map_path,
        "csharp-facts": facts_path,
    }
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list) or len(rows) != 3:
        raise EVIDENCE.EvidenceError(
            "partial", "artifact_binding_invalid", "exactly three accepted artifacts are required"
        )
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"kind", "path", "sha256"}:
            raise EVIDENCE.EvidenceError(
                "partial", "artifact_binding_invalid", "accepted artifact row is malformed"
            )
        kind = row.get("kind")
        path = expected.get(kind)
        if path is None or kind in seen:
            raise EVIDENCE.EvidenceError(
                "partial", "artifact_binding_invalid", "accepted artifact kinds changed"
            )
        if (
            row.get("path") != path.relative_to(root).as_posix()
            or row.get("sha256") != _hash(path)
        ):
            raise EVIDENCE.EvidenceError(
                "partial", "artifact_hash_mismatch", f"accepted artifact changed: {kind}"
            )
        seen.add(kind)
    if seen != set(expected):
        raise EVIDENCE.EvidenceError(
            "partial", "artifact_binding_invalid", "accepted artifact set is incomplete"
        )


def _validate_source_hashes(root: Path, acceptance: dict[str, Any]) -> None:
    rows = acceptance.get("source_hashes")
    if not isinstance(rows, list) or not rows:
        raise EVIDENCE.EvidenceError(
            "partial", "source_hash_mismatch", "accepted source hash inventory is missing"
        )
    seen: set[str] = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "sha256"}
            or not isinstance(row.get("path"), str)
            or row["path"] in seen
        ):
            raise EVIDENCE.EvidenceError(
                "partial", "source_hash_mismatch", "accepted source hash row is invalid"
            )
        path = EVIDENCE.safe_project_path(root, row["path"], "accepted C# source")
        if _hash(path) != row.get("sha256"):
            raise EVIDENCE.EvidenceError(
                "partial", "source_hash_mismatch", f"accepted source changed: {row['path']}"
            )
        seen.add(row["path"])


def _validate_authority(
    skill: str,
    acceptance: dict[str, Any],
    map_payload: dict[str, Any],
    facts: dict[str, Any],
    dotnet: Path,
) -> None:
    skills = _skills_root()
    paths = {
        "selected_skill_sha256": skills / skill / "scripts/propose_csharp.py",
        "structure_helper_sha256": Path(__file__),
        "map_consumer_sha256": skills / "map-subsystem/scripts/map_csharp.py",
        "lexical_helper_sha256": skills / "_csharp/CSharpSyntaxFacts.cs",
        "lexical_provider_sha256": skills / "_csharp/csharp_facts.py",
        "semantic_helper_sha256": skills / "_csharp-semantic/CSharpSemanticFacts.cs",
        "semantic_provider_sha256": skills / "_csharp-semantic/csharp_semantic_facts.py",
    }
    authority = acceptance.get("authority")
    if not isinstance(authority, dict) or set(authority) != {
        *paths,
        "dotnet_sha256",
        "csc_sha256",
        "code_analysis_sha256",
        "csharp_analysis_sha256",
        "reference_pack_sha256",
        "reference_count",
        "sdk_version",
        "runtime_version",
    }:
        raise EVIDENCE.EvidenceError(
            "partial", "authority_invalid", "exact C# structure authority is required"
        )
    for key, path in paths.items():
        if not path.is_file() or authority.get(key) != _hash(path):
            raise EVIDENCE.EvidenceError(
                "partial", "authority_stale", f"accepted helper changed: {key}"
            )
    semantic = map_payload.get("semantic_authority")
    if not isinstance(semantic, dict):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "map semantic authority is missing"
        )
    map_keys = {
        "dotnet_sha256": "dotnet_sha256",
        "csc_sha256": "csc_sha256",
        "code_analysis_sha256": "code_analysis_sha256",
        "csharp_analysis_sha256": "csharp_analysis_sha256",
        "reference_pack_sha256": "reference_pack_sha256",
        "reference_count": "reference_count",
        "sdk_version": "sdk_version",
        "runtime_version": "runtime_version",
    }
    if any(authority[key] != semantic.get(source) for key, source in map_keys.items()):
        raise EVIDENCE.EvidenceError(
            "partial", "authority_stale", "accepted SDK/Roslyn authority changed"
        )
    if semantic.get("fact_pack_sha256") != facts.get("fact_pack_sha256"):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "map and semantic fact pack diverged"
        )
    try:
        resolved_dotnet = dotnet.resolve(strict=True)
    except OSError as exc:
        raise EVIDENCE.EvidenceError(
            "partial", "tool_evidence_stale", "accepted dotnet is unavailable"
        ) from exc
    if not resolved_dotnet.is_file() or _hash(resolved_dotnet) != authority["dotnet_sha256"]:
        raise EVIDENCE.EvidenceError(
            "partial", "tool_evidence_stale", "accepted dotnet changed"
        )


def _validate_map(map_payload: dict[str, Any], facts: dict[str, Any]) -> None:
    if (
        map_payload.get("schema_version") != "csharp-subsystem-map-v1"
        or map_payload.get("status") != "complete"
        or map_payload.get("failure_kind") != "none"
        or map_payload.get("manifest_state") != "current-complete-and-coherent"
        or map_payload.get("source_preservation", {}).get("verified") is not True
        or map_payload.get("target") != "src/CSharpCohort"
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "complete current C# subsystem map is required"
        )
    native = map_payload.get("native_checks", {})
    commands = facts.get("commands", {})
    if (
        native.get("lexical_state") != "valid-current-and-replayed"
        or native.get("semantic_compile_returncode") != 0
        or native.get("semantic_test_compile_returncode") != 0
        or native.get("semantic_test_returncode") != 0
        or native.get("semantic_smoke_returncode") != 0
        or native.get("semantic_test_stdout") != commands.get("test", {}).get("stdout")
        or native.get("semantic_smoke_stdout") != commands.get("smoke", {}).get("stdout")
        or native.get("roslyn_diagnostics") != []
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "map native evidence does not verify"
        )
    inventory = facts.get("source_inventory", [])
    expected_source = {
        row["path"]: row["sha256"] for row in inventory if row.get("role") == "source"
    }
    expected_test = {
        row["path"]: row["sha256"] for row in inventory if row.get("role") == "test"
    }
    actual_source = {
        row.get("path"): row.get("sha256") for row in map_payload.get("source_inventory", [])
    }
    actual_test = {
        row.get("path"): row.get("sha256") for row in map_payload.get("test_inventory", [])
    }
    expected_excluded = sorted(
        [row for row in inventory if row.get("role") in {"generated", "vendor"}],
        key=lambda row: row["path"],
    )
    if (
        actual_source != expected_source
        or actual_test != expected_test
        or map_payload.get("excluded_inventory") != expected_excluded
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "map and fact source universes diverged"
        )
    if not isinstance(map_payload.get("qualified_declarations"), list) or not isinstance(
        map_payload.get("direct_resolved_calls"), list
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "map_evidence_invalid", "map declarations or calls are unavailable"
        )


def _exact_rows(selected: Any, available: list[dict[str, Any]], label: str) -> None:
    if not isinstance(selected, list) or not selected:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", f"accepted {label} must be non-empty"
        )
    available_rows = {EVIDENCE.canonical_hash(row) for row in available}
    selected_rows = [EVIDENCE.canonical_hash(row) for row in selected]
    if len(selected_rows) != len(set(selected_rows)) or any(
        row not in available_rows for row in selected_rows
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", f"accepted {label} changed from mapped evidence"
        )


def _safe_relative(raw: Any, label: str) -> str:
    if (
        not isinstance(raw, str)
        or not raw
        or "\\" in raw
        or Path(raw).is_absolute()
        or ".." in Path(raw).parts
    ):
        raise EVIDENCE.EvidenceError(
            "failed", "selection_invalid", f"unsafe {label} path"
        )
    return raw


def _boundary_scope(
    root: Path,
    producer: dict[str, Any],
    mapped: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    expected_keys = {
        "candidate_id",
        "target",
        "domain",
        "declarations",
        "source_blocks",
        "caller_impact",
        "namespace_impact",
        "assembly_impact",
        "api_impact",
        "abi_impact",
        "runtime_impact",
        "exact_edits",
        "create_files",
        "manifest_sources_after",
        "project_compile_after",
        "test_surface",
    }
    if set(selection) != expected_keys:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted boundary selection shape changed"
        )
    if (
        producer.get("status") != "complete"
        or producer.get("failure_kind") != "none"
        or producer.get("summary") != {"confirmed_omnibus": 1}
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "producer_artifact_invalid", "confirmed C# omnibus evidence is required"
        )
    candidates = [
        row
        for row in producer.get("findings", [])
        if row.get("candidate_id") == selection.get("candidate_id")
        and row.get("file") == selection.get("target")
    ]
    if len(candidates) != 1:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "one exact accepted omnibus candidate is required"
        )
    candidate = candidates[0]
    domain = selection.get("domain")
    exported = candidate.get("clusters", {}).get(domain)
    if not isinstance(exported, list) or not exported:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted omnibus domain changed"
        )
    declarations = [
        row
        for row in mapped["qualified_declarations"]
        if f'{row.get("containing_type")}.{row.get("name")}' in set(exported)
    ]
    if selection.get("declarations") != declarations:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted extracted declarations changed"
        )
    target = EVIDENCE.safe_project_path(root, selection["target"], "accepted omnibus source")
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks = [
        {"path": selection["target"], "line": row["line"], "text": lines[row["line"] - 1]}
        for row in declarations
    ]
    if selection.get("source_blocks") != blocks:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted source blocks changed"
        )
    symbol_ids = {row["symbol_id"] for row in declarations}
    callers = [
        row for row in mapped["direct_resolved_calls"] if row.get("target_symbol_id") in symbol_ids
    ]
    if selection.get("caller_impact") != callers:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted caller impact changed"
        )
    expected_edits = [
        {
            "path": selection["target"],
            "before": block["text"],
            "after": (
                f'    public static int {row["name"]}() => '
                f'ExportOperations.{row["name"]}();\n'
            ),
            "expected_occurrences": 1,
        }
        for row, block in zip(declarations, blocks, strict=True)
    ]
    new_path = "src/CSharpCohort/ExportOperations.cs"
    expected_create = [
        {
            "path": new_path,
            "contents": (
                "namespace CSharpCohort;\n\npublic static class ExportOperations\n{\n"
                + "".join(block["text"] for block in blocks)
                + "}\n"
            ),
        }
    ]
    if selection.get("exact_edits") != expected_edits or selection.get("create_files") != expected_create:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted exact boundary edits changed"
        )
    if (root / new_path).exists():
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted new boundary file already exists"
        )
    if (
        selection.get("namespace_impact")
        != {"before": "CSharpCohort", "after": "CSharpCohort", "changed": False}
        or selection.get("assembly_impact")
        != {"projects": list(PROJECTS), "changed": False}
        or selection.get("api_impact")
        != {
            "compatibility_shims": True,
            "existing_public_signatures_changed": False,
            "new_public_type": "CSharpCohort.ExportOperations",
        }
        or selection.get("abi_impact")
        != {"claimed_compatible": False, "separate_release_approval_required": True}
        or selection.get("runtime_impact")
        != {"claimed_equivalent": False, "native_test_and_smoke_required": True}
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted boundary impact verdict changed"
        )
    return {
        "proposal_kind": "extract-domain-boundary",
        **selection,
    }


def _folder_scope(
    root: Path,
    producer: dict[str, Any],
    mapped: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    expected_keys = {
        "finding_evidence_sha256",
        "parent",
        "prefix",
        "files",
        "project_convention",
        "exact_moves",
        "declarations",
        "caller_impact",
        "reference_impact",
        "namespace_impact",
        "type_identity_impact",
        "assembly_impact",
        "api_impact",
        "manifest_sources_after",
        "project_compile_after",
        "test_surface",
    }
    if set(selection) != expected_keys:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted folder selection shape changed"
        )
    if selection.get("project_convention") != "group-four-same-prefix-csharp-siblings":
        raise EVIDENCE.EvidenceError(
            "partial",
            "project_convention_required",
            "the exact accepted four-sibling C# project convention is required",
        )
    if (
        producer.get("schema_version") != 1
        or producer.get("status") != "complete"
        or producer.get("outcome") != "drift-found"
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "producer_artifact_invalid", "complete C# topology evidence is required"
        )
    findings = [
        row
        for row in producer.get("findings", [])
        if row.get("evidence_sha256") == selection.get("finding_evidence_sha256")
        and row.get("file") == selection.get("parent")
        and row.get("prefix") == selection.get("prefix")
    ]
    if len(findings) != 1:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "one exact accepted topology finding is required"
        )
    finding = findings[0]
    files = finding.get("files")
    if (
        selection.get("files") != files
        or finding.get("count") != 4
        or finding.get("pattern") != "flat_prefix_cluster"
        or not isinstance(files, list)
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted four-file prefix cluster changed"
        )
    selected_paths = set(files)
    declarations = [
        row for row in mapped["qualified_declarations"] if row.get("path") in selected_paths
    ]
    if selection.get("declarations") != declarations:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted moved declarations changed"
        )
    symbols = {row["symbol_id"] for row in declarations}
    callers = [
        row for row in mapped["direct_resolved_calls"] if row.get("target_symbol_id") in symbols
    ]
    references = [
        row
        for row in mapped["direct_resolved_references"]
        if row.get("target_symbol_id") in symbols
    ]
    if selection.get("caller_impact") != callers or selection.get("reference_impact") != references:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted folder caller/reference impact changed"
        )
    replacements = {
        path: path.replace("/CSharpCohort/", "/CSharpCohort/Billing/") for path in files
    }
    moves = [
        {"from": source, "to": destination}
        for source, destination in replacements.items()
    ]
    if selection.get("exact_moves") != moves:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted exact C# moves changed"
        )
    for row in moves:
        source = EVIDENCE.safe_project_path(root, row["from"], "accepted moved C# source")
        destination = root / _safe_relative(row["to"], "accepted move destination")
        if source.suffix != ".cs" or destination.exists():
            raise EVIDENCE.EvidenceError(
                "partial", "selection_invalid", "accepted move source/destination is stale"
            )
    type_ids = sorted(
        row["symbol_id"]
        for row in declarations
        if row["kind"]
        in {"class", "record", "record-class", "struct", "interface", "enum"}
    )
    if (
        selection.get("namespace_impact")
        != {"before": ["CSharpCohort"], "after": ["CSharpCohort"], "changed": False}
        or selection.get("type_identity_impact")
        != {"symbol_ids": type_ids, "changed": False}
        or selection.get("assembly_impact")
        != {"projects": list(PROJECTS), "changed": False}
        or selection.get("api_impact")
        != {"public_signatures_changed": False, "source_location_only": True}
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted folder identity impact changed"
        )
    return {
        "proposal_kind": "move-prefix-cluster",
        **selection,
    }


def _compile_paths(root: Path, project: str) -> list[str]:
    try:
        tree = ET.parse(root / project)
    except (OSError, ET.ParseError) as exc:
        raise EVIDENCE.EvidenceError(
            "failed", "project_contract_invalid", f"invalid project XML: {project}"
        ) from exc
    return [
        node.attrib["Include"]
        for node in tree.getroot().findall(".//Compile")
        if set(node.attrib) == {"Include"}
    ]


def _validate_after_contract(root: Path, scope: dict[str, Any]) -> None:
    replacements = {
        row["from"]: row["to"] for row in scope.get("exact_moves", [])
    }
    additions = [row["path"] for row in scope.get("create_files", [])]
    if len(replacements) != len(scope.get("exact_moves", [])) or len(additions) != len(
        set(additions)
    ):
        raise EVIDENCE.EvidenceError(
            "failed", "selection_invalid", "duplicate accepted moves or new files"
        )
    expected_manifests: dict[str, list[str]] = {}
    for name in ("csharp-project.json", "csharp-semantic-project.json"):
        manifest = EVIDENCE.read_json(
            EVIDENCE.safe_project_path(root, name, "C# manifest"), "C# manifest"
        )
        sources = manifest.get("sources")
        if not isinstance(sources, list):
            raise EVIDENCE.EvidenceError(
                "failed", "project_contract_invalid", f"manifest sources missing: {name}"
            )
        expected_manifests[name] = [replacements.get(path, path) for path in sources]
        expected_manifests[name].extend(additions)
    if scope.get("manifest_sources_after") != expected_manifests:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted manifest after-state changed"
        )
    expected_projects: dict[str, list[str]] = {}
    for project in PROJECTS:
        paths = [replacements.get(path, path) for path in _compile_paths(root, project)]
        insertion = len(paths) - (1 if project.endswith("Tests.csproj") else 0)
        for path in additions:
            paths.insert(insertion, path)
            insertion += 1
        expected_projects[project] = paths
    if scope.get("project_compile_after") != expected_projects:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted project compile after-state changed"
        )
    if scope.get("test_surface") != [
        "tests/CSharpCohortTests.cs",
        "src/CSharpCohort/Program.cs",
    ]:
        raise EVIDENCE.EvidenceError(
            "partial", "selection_invalid", "accepted native test/smoke surface changed"
        )


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in {"reports", ".native-build", ".engineering", ".git"}
            for part in path.relative_to(root).parts
        )
    }


def _apply_scope(root: Path, scope: dict[str, Any]) -> None:
    for row in scope.get("exact_moves", []):
        source = root / _safe_relative(row["from"], "move source")
        destination = root / _safe_relative(row["to"], "move destination")
        if not source.is_file() or source.is_symlink() or destination.exists():
            raise EVIDENCE.EvidenceError(
                "failed", "disposable_apply_failed", "accepted move is stale"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for row in scope.get("exact_edits", []):
        path = root / _safe_relative(row["path"], "edit source")
        text = path.read_text(encoding="utf-8")
        if text.count(row["before"]) != row.get("expected_occurrences"):
            raise EVIDENCE.EvidenceError(
                "failed", "disposable_apply_failed", "accepted edit anchor changed"
            )
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in scope.get("create_files", []):
        path = root / _safe_relative(row["path"], "new source")
        if path.exists():
            raise EVIDENCE.EvidenceError(
                "failed", "disposable_apply_failed", "accepted new source already exists"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")
    for name, sources in scope["manifest_sources_after"].items():
        path = root / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["sources"] = sources
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, compile_paths in scope["project_compile_after"].items():
        project = root / name
        tree = ET.parse(project)
        item_group = tree.getroot().find("ItemGroup")
        if item_group is None:
            raise EVIDENCE.EvidenceError(
                "failed", "disposable_apply_failed", f"project ItemGroup missing: {name}"
            )
        for node in list(item_group):
            if node.tag == "Compile":
                item_group.remove(node)
        for path in compile_paths:
            ET.SubElement(item_group, "Compile", {"Include": path})
        ET.indent(tree, space="  ")
        tree.write(project, encoding="unicode", xml_declaration=False)


def _run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
    environment = {
        **os.environ,
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "NUGET_XMLDOC_MODE": "skip",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
    }
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"argv": argv, "returncode": 124, "stdout": "", "stderr": str(exc)}
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
    }


def _native(root: Path, dotnet: Path) -> dict[str, Any]:
    commands: dict[str, Any] = {}
    for project in PROJECTS:
        label = "app" if project.endswith("App.csproj") else "tests"
        commands[f"restore_{label}"] = _run(
            [
                str(dotnet),
                "restore",
                project,
                "--configfile",
                "NuGet.Config",
                "--packages",
                ".native-build/packages",
            ],
            root,
        )
        if commands[f"restore_{label}"]["returncode"] == 0:
            commands[f"build_{label}"] = _run(
                [str(dotnet), "build", project, "--no-restore"], root
            )
        else:
            commands[f"build_{label}"] = {
                "argv": [],
                "returncode": 125,
                "stdout": "",
                "stderr": "restore failed",
            }
    commands["test"] = _run(
        [
            str(dotnet),
            ".native-build/bin/tests/net10.0/CSharpCohort.Tests.dll",
        ],
        root,
    )
    commands["smoke"] = _run(
        [
            str(dotnet),
            ".native-build/bin/app/net10.0/CSharpCohort.App.dll",
        ],
        root,
    )
    passed = (
        all(row["returncode"] == 0 for row in commands.values())
        and commands["test"]["stdout"] == "csharp-lexical-tests:ok\n"
        and commands["smoke"]["stdout"] == "csharp-lexical:12:queued\n"
    )
    return {"status": "passed" if passed else "failed", "commands": commands}


def _report(skill: str, scope: dict[str, Any]) -> str:
    title = (
        "C# boundary proposal"
        if skill == "propose-boundary"
        else "C# folder-reorganization proposal"
    )
    return f"""# {title}

Status: `ready_for_human_review`; project sources remain unchanged.

The exact accepted `{scope['proposal_kind']}` after-tree passed an independently
applied disposable build, native test, and executable smoke check. The proposal
retains the accepted namespaces, assemblies, API/ABI caveats, project manifests,
and explicit compile-item after-state.

This artifact is read-only. It does not authorize moving, editing, creating, or
deleting project source. Revalidate all hash-bound evidence and obtain separate
mutation approval before applying it.
"""


def _refusal_bundle(
    skill: str, error: Any
) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = {
        "schema_version": "csharp-structure-proposal-evidence-v1",
        "language": "csharp",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "detail": error.detail,
        "source_mutations": 0,
        "human_authority": "required",
    }
    scope = {
        "schema_version": "csharp-structure-proposal-scope-v1",
        "language": "csharp",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "read_only": True,
        "mutation_authorized": False,
        "source_mutations": 0,
        "declarations": [],
        "caller_impact": [],
        "reference_impact": [],
        "exact_moves": [],
        "exact_edits": [],
        "create_files": [],
        "manifest_sources_after": {},
        "project_compile_after": {},
    }
    report = (
        f"# {skill} — C# refusal\n\nStatus: `{error.status}`.\n\n"
        f"Refused `{error.failure_kind}`: {error.detail}\n\nNo C# source was changed.\n"
    )
    return evidence, scope, report


def main(skill: str) -> int:
    """Run one bounded proposal consumer without invoking any detector."""
    if skill not in {"propose-boundary", "propose-folder-reorganization"}:
        raise RuntimeError(f"unsupported C# structure proposal skill: {skill}")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--omnibus", type=Path)
    parser.add_argument("--topology", type=Path)
    parser.add_argument("--map-evidence", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    gates = BOUNDARY_GATES if skill == "propose-boundary" else FOLDER_GATES
    producer_arg = args.omnibus if skill == "propose-boundary" else args.topology
    if producer_arg is None or (args.topology if skill == "propose-boundary" else args.omnibus) is not None:
        parser.error("supply exactly the producer artifact required by the selected skill")
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, skill)
        producer_path = EVIDENCE.safe_project_path(
            root, producer_arg, "C# structure producer artifact"
        )
        map_path = EVIDENCE.safe_project_path(root, args.map_evidence, "C# subsystem map")
        facts_path = EVIDENCE.safe_project_path(root, args.facts, "C# semantic facts")
        acceptance_path, acceptance = _load_acceptance(
            root, args.acceptance, skill, gates
        )
        producer_kind = (
            "confirmed-omnibus" if skill == "propose-boundary" else "lexical-topology"
        )
        _artifact_paths(
            root,
            acceptance,
            producer_kind=producer_kind,
            producer=producer_path,
            map_path=map_path,
            facts_path=facts_path,
        )
        _validate_source_hashes(root, acceptance)
        validated_facts_path, facts = EVIDENCE.validate_fact_pack(root, facts_path)
        if validated_facts_path != facts_path:
            raise EVIDENCE.EvidenceError(
                "partial", "artifact_binding_invalid", "semantic fact path changed"
            )
        producer = EVIDENCE.read_json(producer_path, "C# structure producer artifact")
        mapped = EVIDENCE.read_json(map_path, "C# subsystem map")
        _validate_map(mapped, facts)
        _validate_authority(skill, acceptance, mapped, facts, args.dotnet)
        if skill == "propose-boundary":
            selected = _boundary_scope(root, producer, mapped, acceptance["selection"])
        else:
            selected = _folder_scope(root, producer, mapped, acceptance["selection"])
        scope = {
            "schema_version": "csharp-structure-proposal-scope-v1",
            "language": "csharp",
            "skill": skill,
            "status": "ready_for_human_review",
            "read_only": True,
            "mutation_authorized": False,
            "source_mutations": 0,
            **selected,
            "boundary_verdicts": acceptance["proposal_verdict"]["boundary_verdicts"],
            "human_authority": {
                "candidate_verdict": acceptance["candidate_verdict"],
                "proposal_verdict": acceptance["proposal_verdict"],
            },
        }
        _validate_after_contract(root, scope)
        before = _snapshot(root)
        with tempfile.TemporaryDirectory(prefix="csharp-structure-proposal-") as raw:
            current = Path(raw) / "current"
            shutil.copytree(
                root,
                current,
                ignore=shutil.ignore_patterns(
                    ".git", ".native-build", ".engineering", "reports", "obj"
                ),
            )
            current_native = _native(current, args.dotnet)
            disposable = Path(raw) / "after"
            shutil.copytree(
                root,
                disposable,
                ignore=shutil.ignore_patterns(
                    ".git", ".native-build", ".engineering", "reports", "obj"
                ),
            )
            _apply_scope(disposable, scope)
            after_native = _native(disposable, args.dotnet)
        if current_native["status"] != "passed" or after_native["status"] != "passed":
            raise EVIDENCE.EvidenceError(
                "failed",
                "native_verification_failed",
                "current and disposable after-trees must pass build/test/smoke",
            )
        after = _snapshot(root)
        if after != before:
            raise EVIDENCE.EvidenceError(
                "failed", "source_mutated", "read-only proposal changed the host project"
            )
        evidence = {
            "schema_version": "csharp-structure-proposal-evidence-v1",
            "language": "csharp",
            "skill": skill,
            "status": "ready_for_human_review",
            "outcome": "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "evidence_binding": {
                "producer_path": producer_path.relative_to(root).as_posix(),
                "producer_sha256": _hash(producer_path),
                "map_path": map_path.relative_to(root).as_posix(),
                "map_sha256": _hash(map_path),
                "facts_path": facts_path.relative_to(root).as_posix(),
                "facts_sha256": _hash(facts_path),
                "fact_pack_sha256": facts["fact_pack_sha256"],
                "acceptance_path": acceptance_path.relative_to(root).as_posix(),
                "acceptance_sha256": _hash(acceptance_path),
            },
            "native_verification": {
                "current_tree": current_native,
                "disposable_after_tree": after_native,
            },
            "source_preservation": {"verified": True},
            "human_authority": acceptance,
            "scope_sha256": EVIDENCE.canonical_hash(scope),
            "limits": [
                "one exact accepted producer candidate and integrated subsystem-map snapshot only",
                "native build/test/smoke do not establish reflection, framework, external, conditional-variant, ABI, or runtime equivalence",
                "the proposal grants no source mutation authority",
            ],
        }
        scope["artifact_sha256"] = EVIDENCE.canonical_hash(scope)
        evidence["scope_sha256"] = EVIDENCE.canonical_hash(scope)
        evidence["artifact_sha256"] = EVIDENCE.canonical_hash(evidence)
        EVIDENCE.replace_bundle(
            output,
            {
                "proposal.md": _report(skill, scope),
                "evidence.json": evidence,
                "scope.json": scope,
            },
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, skill)
            evidence, scope, report = _refusal_bundle(skill, exc)
            EVIDENCE.replace_bundle(
                output,
                {"proposal.md": report, "evidence.json": evidence, "scope.json": scope},
            )
        except EVIDENCE.EvidenceError:
            pass
        print(
            f"csharp_structure_proposals.py: {exc.failure_kind}: {exc.detail}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main("propose-boundary"))
