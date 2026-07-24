#!/usr/bin/env python3
"""Accepted-evidence boundary for Swift semantic proposal consumers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


STATE_GATES = {
    "closed_domain": "accepted",
    "existing_enum_authority": "accepted_exact_type",
    "raw_values": "accepted_exact_strings",
    "serialization_codable": "none_selected",
    "reflection_objc_dynamic_selectors": "none_selected",
    "protocol_existential_dispatch": "none_selected",
    "external_callers": "none_selected",
    "framework_xcode_registration": "none_selected",
    "generated_macro_plugin_sources": "none_selected",
    "conditional_build_variants": "none",
    "source_binary_compatibility": "accepted_change_for_proposal_only",
}
ARTIFACT_DIRS = frozenset({".agents", ".build", ".git", ".swiftpm", "reports"})
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EvidenceError(ValueError):
    """A classified accepted-evidence refusal."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_hashed_object(payload: dict[str, Any], field: str) -> bool:
    claimed = payload.get(field)
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return isinstance(claimed, str) and claimed == canonical_hash(unsigned)


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_project_path(root: Path, supplied: str | Path, label: str) -> Path:
    candidate = Path(supplied)
    path = Path(os.path.abspath(candidate if candidate.is_absolute() else root / candidate))
    if not _inside(root, path):
        raise EvidenceError("failed", "unsafe_path", f"{label} must stay inside the project")
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise EvidenceError("failed", "unsafe_path", f"{label} must not traverse a symlink")
    return path


def safe_output(root: Path, supplied: str | Path, family: str) -> Path:
    output = safe_project_path(root, supplied, "output")
    allowed = root / "reports" / family
    if output == allowed or not _inside(allowed, output):
        raise EvidenceError("failed", "unsafe_path", f"output must stay beneath reports/{family}/")
    return output


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(
            "partial", "evidence_unavailable", f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise EvidenceError("failed", "evidence_invalid", f"{label} must be a JSON object")
    return payload


def _provider() -> Any:
    path = Path(__file__).with_name("swift_semantic_facts.py")
    if not path.is_file():
        raise EvidenceError(
            "partial", "semantic_provider_missing", "copied Swift semantic validator is missing"
        )
    spec = importlib.util.spec_from_file_location("swift_accepted_semantic_facts", path)
    if spec is None or spec.loader is None:
        raise EvidenceError("failed", "semantic_provider_invalid", "cannot load Swift validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_hashes(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
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
            relative = relative_parent / name
            if any(part in ARTIFACT_DIRS for part in relative.parts):
                continue
            if not path.is_symlink() and path.is_file():
                rows.append({"path": relative.as_posix(), "sha256": file_hash(path)})
    return sorted(rows, key=lambda row: row["path"])


def _enum(candidate: dict[str, Any], acceptance: dict[str, Any], root: Path) -> dict[str, Any]:
    enum = acceptance.get("enum")
    if not isinstance(enum, dict):
        raise EvidenceError(
            "partial", "acceptance_invalid", "exact existing enum authority is required"
        )
    cases = enum.get("cases")
    if (
        enum.get("action") != "reuse_existing"
        or enum.get("raw_type") != "String"
        or not isinstance(enum.get("module"), str)
        or not IDENTIFIER.fullmatch(str(enum.get("type_name", "")))
        or not isinstance(cases, list)
        or len(cases) < 2
    ):
        raise EvidenceError(
            "partial", "acceptance_invalid", "existing String enum shape is invalid"
        )
    normalized: list[dict[str, str]] = []
    for row in cases:
        if (
            not isinstance(row, dict)
            or set(row) != {"name", "raw_value"}
            or not IDENTIFIER.fullmatch(str(row.get("name", "")))
            or not isinstance(row.get("raw_value"), str)
            or not row["raw_value"]
        ):
            raise EvidenceError("partial", "acceptance_invalid", "enum case mapping is invalid")
        normalized.append(row)
    if len({row["name"] for row in normalized}) != len(normalized) or sorted(
        row["raw_value"] for row in normalized
    ) != candidate.get("literals"):
        raise EvidenceError(
            "partial",
            "acceptance_invalid",
            "enum cases must preserve every accepted literal exactly",
        )
    source_path = enum.get("source")
    if not isinstance(source_path, str) or not source_path:
        raise EvidenceError("partial", "acceptance_invalid", "existing enum source is required")
    source = safe_project_path(root, source_path, "existing enum source")
    if (
        not isinstance(enum.get("source_sha256"), str)
        or not source.is_file()
        or file_hash(source) != enum["source_sha256"]
    ):
        raise EvidenceError("partial", "acceptance_stale", "existing enum authority is stale")
    return enum


def validate_state_acceptance(
    root: Path,
    *,
    target_name: str,
    facts_path: str | Path,
    findings_path: str | Path,
    acceptance_path: str | Path,
) -> dict[str, Any]:
    fact_file = safe_project_path(root, facts_path, "Swift semantic fact pack")
    finding_file = safe_project_path(root, findings_path, "Swift implicit-state findings")
    acceptance_file = safe_project_path(root, acceptance_path, "Swift state acceptance")
    provider = _provider()
    try:
        facts = provider.load_fact_pack(fact_file, root, target_name, ["state"])
    except provider.SwiftFactError as exc:
        raise EvidenceError("partial", exc.kind, str(exc)) from exc
    findings = read_json(finding_file, "Swift implicit-state findings")
    accepted = findings.get("findings")
    if (
        findings.get("schema_version") != "swift-implicit-state-v1"
        or findings.get("language") != "swift"
        or findings.get("status") != "complete"
        or findings.get("read_only") is not True
        or findings.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or findings.get("source_hashes") != facts.get("source_hashes")
        or not isinstance(accepted, list)
        or len(accepted) != 1
        or findings.get("summary", {}).get("accepted") != 1
        or findings.get("summary", {}).get("pending_review") != 0
    ):
        raise EvidenceError(
            "partial",
            "producer_artifact_invalid",
            "one complete accepted Swift state finding is required",
        )
    candidate = accepted[0]
    acceptance = read_json(acceptance_file, "Swift state acceptance")
    if (
        acceptance.get("schema_version") != "swift-state-acceptance-v1"
        or acceptance.get("language") != "swift"
        or acceptance.get("status") != "accepted"
        or acceptance.get("producer") != "find-implicit-state"
        or acceptance.get("decision") != "accept-enum"
        or acceptance.get("artifact") != finding_file.relative_to(root).as_posix()
        or acceptance.get("artifact_sha256") != file_hash(finding_file)
        or acceptance.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or acceptance.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
        or acceptance.get("candidate_sha256") != candidate.get("candidate_sha256")
        or acceptance.get("selection_semantic_id") != candidate.get("semantic_id")
        or acceptance.get("boundary_verdicts") != STATE_GATES
        or not isinstance(acceptance.get("reviewer"), str)
        or not acceptance["reviewer"].strip()
        or not isinstance(acceptance.get("notes"), str)
        or not acceptance["notes"].strip()
        or not valid_hashed_object(acceptance, "acceptance_sha256")
    ):
        raise EvidenceError(
            "partial", "acceptance_invalid", "fresh exact Swift state acceptance is required"
        )
    if (
        candidate.get("human_verdict") != "accepted"
        or candidate.get("bucket") != "extract_enum_candidate"
        or candidate.get("type") != "String"
        or candidate.get("owner") != "Job"
        or candidate.get("field") != "state"
        or not isinstance(candidate.get("semantic_id"), str)
        or not isinstance(candidate.get("operations"), list)
        or len(candidate["operations"]) < 3
        or candidate.get("literals") != ["done", "queued", "running"]
    ):
        raise EvidenceError(
            "partial", "selection_invalid", "accepted authority is not exact Job.state"
        )
    enum = _enum(candidate, acceptance, root)
    if enum.get("module") != target_name:
        raise EvidenceError(
            "partial", "acceptance_invalid", "enum module must match the selected target"
        )
    native = acceptance.get("native")
    expected_native = {
        "configuration",
        "check_product",
        "expected_check",
        "smoke_product",
        "expected_smoke",
    }
    if (
        not isinstance(native, dict)
        or set(native) != expected_native
        or native.get("configuration") not in {"debug", "release"}
        or not all(isinstance(native.get(key), str) and native[key] for key in expected_native)
    ):
        raise EvidenceError(
            "partial", "acceptance_invalid", "exact native check contract is required"
        )
    return {
        "facts": facts,
        "facts_path": fact_file,
        "findings": findings,
        "findings_path": finding_file,
        "candidate": candidate,
        "acceptance": acceptance,
        "acceptance_path": acceptance_file,
        "enum": enum,
    }


def replace_bundle(output: Path, files: dict[str, str | dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output.name}.staged-", dir=output.parent))
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    try:
        for relative, content in files.items():
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            text = (
                json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
                if isinstance(content, dict)
                else content
            )
            destination.write_text(text, encoding="utf-8")
        if output.exists():
            output.replace(backup)
        staged.replace(output)
        shutil.rmtree(backup, ignore_errors=True)
    except OSError:
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def refusal(skill: str, error: EvidenceError) -> tuple[dict[str, Any], str]:
    payload = {
        "schema_version": "swift-a4-refusal-v1",
        "language": "swift",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "detail": error.detail,
        "source_mutations": 0,
    }
    report = (
        f"# {skill} — Swift refusal\n\nStatus: `{error.status}`\n\n"
        f"Refused: `{error.failure_kind}` — {error.detail}\n\nNo source was changed.\n"
    )
    return payload, report
