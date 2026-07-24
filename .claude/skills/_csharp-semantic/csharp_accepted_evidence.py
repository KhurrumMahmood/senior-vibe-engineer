#!/usr/bin/env python3
"""Validate accepted, content-addressed C# semantic evidence for proposals."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


FACT_SCHEMA = "csharp-roslyn-semantic-facts-v1"
SDK_VERSION = "10.0.302"
RUNTIME_VERSION = "10.0.10"
DOTNET_SHA256 = "ed8eb05ce0598b40df34f464d16063b30896c7e28dc1ac9e94554a8aff9676ed"
CSC_SHA256 = "c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81"
CODE_ANALYSIS_SHA256 = "eabc44a97ca36c415af0d7a4db353c170fad26da897b11862927bdb3402f3786"
CSHARP_ANALYSIS_SHA256 = "daff05fe558690b194b93e99d1299f2a85afba55c41fba5718dba6bdfd36bfe9"
REFERENCE_PACK_SHA256 = "9719ee9a053103d3de4b3bfb91f230d9a58325f47e7ac90a2147649d288f2fdd"
REFERENCE_COUNT = 167

STATE_GATES = {
    "closed_domain": "accepted",
    "serialization_wire_values": "accepted_exact_strings",
    "external_callers": "none",
    "framework_registration": "none",
    "reflection_runtime_names": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "partial_declarations": "none_selected",
    "override_interface_dispatch": "none_selected",
    "delegates_dynamic_dispatch": "none_selected",
    "conditional_build_variants": "none",
    "binary_compatibility": "accepted_change_for_proposal_only",
}

DUPLICATION_GATES = {
    "resolved_callers": "accepted_exact",
    "behavioral_equivalence": "not_established_no_mutation_authority",
    "runtime_equivalence": "not_established_no_mutation_authority",
    "overload_ambiguity": "none_selected",
    "override_interface_dispatch": "none_selected",
    "delegates_dynamic_reflection": "none_selected",
    "partial_declarations": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "binary_compatibility": "separate_approval_required",
}

CONSOLIDATION_SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}


class EvidenceError(RuntimeError):
    """A classified terminal accepted-evidence failure."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def valid_hashed_object(payload: dict[str, Any], field: str) -> bool:
    claimed = payload.get(field)
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return isinstance(claimed, str) and claimed == canonical_hash(unsigned)


def safe_project_path(root: Path, supplied: str | Path, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise EvidenceError("partial", "unsafe_path", f"{label} must stay inside project root") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise EvidenceError("partial", "unsafe_path", f"{label} cannot traverse a symbolic link")
    if not candidate.is_file():
        raise EvidenceError("partial", "evidence_unavailable", f"{label} is unavailable")
    return candidate


def safe_output(root: Path, supplied: str | Path, skill: str) -> Path:
    raw = Path(supplied)
    output = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    allowed = root / "reports" / skill / "csharp"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise EvidenceError(
            "failed", "unsafe_output", f"output must stay beneath reports/{skill}/csharp"
        ) from exc
    if not relative.parts:
        raise EvidenceError("failed", "unsafe_output", "output must name one bounded job")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise EvidenceError("failed", "unsafe_output", "output cannot traverse a symbolic link")
    return output


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("partial", "evidence_unavailable", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("failed", "evidence_invalid", f"{label} must be a JSON object")
    return payload


def _safe_manifest_relative(root: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise EvidenceError("failed", "project_contract_invalid", f"invalid {label} path")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise EvidenceError("failed", "project_contract_invalid", f"unsafe {label} path")
    path = root / raw
    if not path.is_file() or path.is_symlink():
        raise EvidenceError("partial", "evidence_stale", f"missing or linked {label}: {raw}")
    return path


def _validate_tools(facts: dict[str, Any]) -> None:
    tools = facts.get("tools")
    if not isinstance(tools, dict):
        raise EvidenceError("partial", "tool_evidence_invalid", "tool evidence is missing")
    if tools.get("sdk_version") != SDK_VERSION or tools.get("runtime_version") != RUNTIME_VERSION:
        raise EvidenceError("partial", "tool_evidence_invalid", "pinned SDK/runtime evidence changed")
    expected = [
        (tools.get("dotnet"), DOTNET_SHA256),
        (tools.get("csc"), CSC_SHA256),
    ]
    assemblies = tools.get("assemblies")
    if not isinstance(assemblies, list) or len(assemblies) != 2:
        raise EvidenceError("partial", "tool_evidence_invalid", "two pinned Roslyn assemblies are required")
    expected.extend(zip(assemblies, (CODE_ANALYSIS_SHA256, CSHARP_ANALYSIS_SHA256), strict=True))
    for row, digest in expected:
        if not isinstance(row, dict) or row.get("sha256") != digest:
            raise EvidenceError("partial", "tool_evidence_invalid", "pinned tool hash evidence changed")
        try:
            path = Path(row["path"]).resolve(strict=True)
        except (KeyError, OSError, TypeError) as exc:
            raise EvidenceError("partial", "tool_evidence_stale", "pinned tool is unavailable") from exc
        if not path.is_file() or file_hash(path) != digest:
            raise EvidenceError("partial", "tool_evidence_stale", f"pinned tool changed: {path}")
    reference = tools.get("reference_pack")
    if (
        not isinstance(reference, dict)
        or reference.get("assembly_count") != REFERENCE_COUNT
        or reference.get("manifest_sha256") != REFERENCE_PACK_SHA256
    ):
        raise EvidenceError("partial", "tool_evidence_invalid", "reference-pack evidence changed")
    try:
        directory = Path(reference["path"]).resolve(strict=True)
    except (KeyError, OSError, TypeError) as exc:
        raise EvidenceError("partial", "tool_evidence_stale", "reference pack is unavailable") from exc
    rows = [
        {"name": path.name, "sha256": file_hash(path)}
        for path in sorted(directory.glob("*.dll"))
    ]
    if len(rows) != REFERENCE_COUNT or canonical_hash(rows) != REFERENCE_PACK_SHA256:
        raise EvidenceError("partial", "tool_evidence_stale", "reference pack changed")


def _validate_native_evidence(facts: dict[str, Any]) -> None:
    commands = facts.get("commands")
    manifest = facts.get("manifest")
    if not isinstance(commands, dict) or not isinstance(manifest, dict):
        raise EvidenceError("partial", "native_evidence_invalid", "native command evidence is missing")
    for name in ("compile", "compile_tests", "test", "smoke", "compile_helper", "semantic_read"):
        row = commands.get(name)
        if not isinstance(row, dict) or row.get("returncode") != 0:
            raise EvidenceError("partial", "native_evidence_invalid", f"successful {name} evidence is required")
    if (
        commands["test"].get("stdout") != manifest.get("test_output")
        or commands["smoke"].get("stdout") != manifest.get("smoke_output")
        or facts.get("diagnostics") != []
        or facts.get("source_preservation") != {"unchanged": True}
    ):
        raise EvidenceError("partial", "native_evidence_invalid", "native outputs or diagnostics changed")


def validate_fact_pack(root: Path, supplied: str | Path) -> tuple[Path, dict[str, Any]]:
    path = safe_project_path(root, supplied, "C# semantic fact pack")
    facts = read_json(path, "C# semantic fact pack")
    if (
        facts.get("schema_version") != FACT_SCHEMA
        or facts.get("language") != "csharp"
        or facts.get("status") != "complete"
        or facts.get("read_only") is not True
        or facts.get("project_root") != str(root)
        or not valid_hashed_object(facts, "fact_pack_sha256")
    ):
        raise EvidenceError("partial", "fact_pack_invalid", "complete content-addressed C# facts are required")
    manifest_path = safe_project_path(root, facts.get("manifest_path", ""), "C# project manifest")
    manifest = read_json(manifest_path, "C# project manifest")
    if (
        file_hash(manifest_path) != facts.get("manifest_sha256")
        or canonical_hash(manifest) != facts.get("project_contract_sha256")
        or manifest != facts.get("manifest")
    ):
        raise EvidenceError("partial", "project_contract_stale", "C# project manifest changed")
    inventory = facts.get("source_inventory")
    if not isinstance(inventory, list) or not inventory or canonical_hash(inventory) != facts.get("source_manifest_sha256"):
        raise EvidenceError("partial", "fact_pack_invalid", "source inventory does not verify")
    seen: set[str] = set()
    for row in inventory:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "role", "sha256"}
            or row.get("role") not in {"source", "test", "generated", "vendor"}
            or row.get("path") in seen
        ):
            raise EvidenceError("failed", "fact_pack_invalid", "source inventory row is invalid")
        source = _safe_manifest_relative(root, row.get("path"), "source inventory")
        if file_hash(source) != row.get("sha256"):
            raise EvidenceError("partial", "evidence_stale", f"source changed: {row.get('path')}")
        seen.add(row["path"])
    authority = facts.get("semantic_authority")
    provider = Path(__file__).with_name("csharp_semantic_facts.py")
    helper = Path(__file__).with_name("CSharpSemanticFacts.cs")
    if (
        not isinstance(authority, dict)
        or authority.get("kind") != "sdk-bundled-roslyn-after-direct-csc-native-gates"
        or authority.get("sdk_version") != SDK_VERSION
        or authority.get("runtime_version") != RUNTIME_VERSION
        or not provider.is_file()
        or not helper.is_file()
        or authority.get("provider_sha256") != file_hash(provider)
        or authority.get("helper_sha256") != file_hash(helper)
    ):
        raise EvidenceError("partial", "semantic_authority_stale", "provider/helper authority changed")
    _validate_tools(facts)
    _validate_native_evidence(facts)
    return path, facts


def _artifact(
    root: Path,
    supplied: str | Path,
    facts: dict[str, Any],
    *,
    schema: str,
    collection: str,
) -> tuple[Path, dict[str, Any]]:
    path = safe_project_path(root, supplied, "accepted C# producer artifact")
    artifact = read_json(path, "accepted C# producer artifact")
    if (
        artifact.get("schema_version") != schema
        or artifact.get("language") != "csharp"
        or artifact.get("status") != "complete"
        or artifact.get("read_only") is not True
        or artifact.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or artifact.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
        or artifact.get("candidate_sha256") != canonical_hash(artifact.get(collection, []))
    ):
        raise EvidenceError("partial", "producer_artifact_invalid", "accepted producer artifact does not verify")
    return path, artifact


def validate_state_acceptance(
    root: Path,
    *,
    facts_path: str | Path,
    findings_path: str | Path,
    acceptance_path: str | Path,
) -> dict[str, Any]:
    fact_path, facts = validate_fact_pack(root, facts_path)
    finding_path, findings = _artifact(
        root,
        findings_path,
        facts,
        schema="csharp-roslyn-state-v1",
        collection="candidates",
    )
    accepted_path = safe_project_path(root, acceptance_path, "C# state acceptance")
    acceptance = read_json(accepted_path, "C# state acceptance")
    if (
        acceptance.get("schema_version") != "csharp-state-acceptance-v1"
        or acceptance.get("language") != "csharp"
        or acceptance.get("status") != "accepted"
        or acceptance.get("producer") != "find-implicit-state"
        or acceptance.get("decision") != "accept-enum"
        or acceptance.get("artifact") != finding_path.relative_to(root).as_posix()
        or acceptance.get("artifact_sha256") != file_hash(finding_path)
        or acceptance.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or acceptance.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
        or acceptance.get("candidate_sha256") != findings.get("candidate_sha256")
        or acceptance.get("boundary_verdicts") != STATE_GATES
        or not isinstance(acceptance.get("reviewer"), str)
        or not acceptance["reviewer"].strip()
        or not isinstance(acceptance.get("notes"), str)
        or not acceptance["notes"].strip()
        or not valid_hashed_object(acceptance, "acceptance_sha256")
    ):
        raise EvidenceError("partial", "acceptance_invalid", "fresh exact C# state acceptance is required")
    selected = [
        row
        for row in findings.get("candidates", [])
        if row.get("symbol_id") == acceptance.get("selection_symbol_id")
    ]
    enum = acceptance.get("enum")
    if len(selected) != 1 or not _valid_enum(enum, selected[0].get("literals")):
        raise EvidenceError("partial", "selection_invalid", "one exact accepted String-state domain is required")
    return {
        "facts_path": fact_path,
        "facts": facts,
        "findings_path": finding_path,
        "findings": findings,
        "acceptance_path": accepted_path,
        "acceptance": acceptance,
        "candidate": selected[0],
    }


def _valid_enum(value: Any, literals: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"namespace", "type_name", "members"}:
        return False
    if value.get("namespace") != "CSharpSemantic" or value.get("type_name") != "JobStatus":
        return False
    members = value.get("members")
    if not isinstance(members, list) or len(members) != len(literals or []):
        return False
    return (
        all(
            isinstance(row, dict)
            and set(row) == {"name", "wire_value"}
            and isinstance(row.get("name"), str)
            and row["name"]
            and isinstance(row.get("wire_value"), str)
            for row in members
        )
        and [row["wire_value"] for row in members] == literals
        and len({row["name"] for row in members}) == len(members)
    )


def validate_duplication_acceptance(
    root: Path,
    *,
    facts_path: str | Path,
    analysis_path: str | Path,
    acceptance_path: str | Path,
) -> dict[str, Any]:
    fact_path, facts = validate_fact_pack(root, facts_path)
    analysis_file, analysis = _artifact(
        root,
        analysis_path,
        facts,
        schema="csharp-roslyn-duplication-v1",
        collection="leads",
    )
    accepted_path = safe_project_path(root, acceptance_path, "C# duplication acceptance")
    acceptance = read_json(accepted_path, "C# duplication acceptance")
    if (
        acceptance.get("schema_version") != "csharp-duplication-acceptance-v1"
        or acceptance.get("language") != "csharp"
        or acceptance.get("status") != "accepted"
        or acceptance.get("producer") != "find-semantic-duplication"
        or acceptance.get("decision") not in CONSOLIDATION_SHAPES
        or acceptance.get("artifact") != analysis_file.relative_to(root).as_posix()
        or acceptance.get("artifact_sha256") != file_hash(analysis_file)
        or acceptance.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or acceptance.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
        or acceptance.get("candidate_sha256") != analysis.get("candidate_sha256")
        or acceptance.get("boundary_verdicts") != DUPLICATION_GATES
        or not isinstance(acceptance.get("reviewer"), str)
        or not acceptance["reviewer"].strip()
        or not isinstance(acceptance.get("notes"), str)
        or not acceptance["notes"].strip()
        or not valid_hashed_object(acceptance, "acceptance_sha256")
    ):
        raise EvidenceError("partial", "acceptance_invalid", "fresh exact C# duplication acceptance is required")
    selected = [
        row for row in analysis.get("leads", []) if row.get("id") == acceptance.get("selection_id")
    ]
    if len(selected) != 1:
        raise EvidenceError("partial", "selection_invalid", "one exact accepted C# duplication pair is required")
    return {
        "facts_path": fact_path,
        "facts": facts,
        "analysis_path": analysis_file,
        "analysis": analysis,
        "acceptance_path": accepted_path,
        "acceptance": acceptance,
        "lead": selected[0],
    }


def run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
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


def replace_bundle(output: Path, files: dict[str, str | dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output.name}.staged-", dir=output.parent))
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    try:
        for relative, content in files.items():
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict):
                atomic_json(destination, content)
            else:
                destination.write_text(content, encoding="utf-8")
        if output.exists():
            output.replace(backup)
        staged.replace(output)
        shutil.rmtree(backup, ignore_errors=True)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise


def refusal(skill: str, error: EvidenceError) -> tuple[dict[str, Any], str]:
    payload = {
        "schema_version": "csharp-accepted-evidence-refusal-v1",
        "language": "csharp",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "detail": error.detail,
        "source_mutations": 0,
        "human_authority": "required",
    }
    report = (
        f"# {skill} — C# refusal\n\nStatus: `{error.status}`.\n\n"
        f"Refused `{error.failure_kind}`: {error.detail}\n\nNo C# source was changed.\n"
    )
    return payload, report
