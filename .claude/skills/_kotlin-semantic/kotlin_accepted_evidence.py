#!/usr/bin/env python3
"""Validate accepted Kotlin state evidence without performing detection."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


STATE_GATES = {
    "closed_domain": "accepted",
    "serialization": "accepted_wire_values",
    "java_callers": "none",
    "framework_registration": "none",
    "external_callers": "none",
    "jvm_abi": "accepted_change",
    "reflection": "none",
    "delegated_property": "none",
    "generated_kapt_ksp": "none",
    "gradle_variants": "none",
    "overload_ambiguity": "none",
}


class EvidenceError(ValueError):
    """A classified refusal at the accepted-evidence boundary."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def canonical_hash(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(rendered.encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def safe_project_path(root: Path, supplied: str | Path, label: str) -> Path:
    candidate = Path(supplied)
    candidate = candidate if candidate.is_absolute() else root / candidate
    path = Path(os.path.abspath(candidate))
    if not _inside(root, path):
        raise EvidenceError("failed", "unsafe_path", f"{label} must stay inside project root")
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
        raise EvidenceError(
            "failed", "unsafe_path", f"output must stay beneath reports/{family}/"
        )
    return output


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceError("partial", "evidence_unavailable", f"{label} is unavailable") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("failed", "evidence_invalid", f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("failed", "evidence_invalid", f"{label} must be an object")
    return payload


def valid_hashed_object(payload: dict[str, Any], field: str) -> bool:
    claimed = payload.get(field)
    unhashed = dict(payload)
    unhashed.pop(field, None)
    return isinstance(claimed, str) and claimed == canonical_hash(unhashed)


def _relative_source(raw: Any) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise EvidenceError("failed", "evidence_invalid", "source path must be POSIX relative")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".kt":
        raise EvidenceError("failed", "evidence_invalid", f"unsafe Kotlin source path: {raw}")
    return raw


def validate_source_rows(root: Path, rows: Any) -> None:
    if not isinstance(rows, list) or not rows:
        raise EvidenceError("partial", "evidence_incomplete", "source inventory is empty")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "role", "sha256"}:
            raise EvidenceError("failed", "evidence_invalid", "source inventory row is malformed")
        relative = _relative_source(row["path"])
        if relative in seen or row["role"] not in {"source", "test"}:
            raise EvidenceError("failed", "evidence_invalid", "source inventory is ambiguous")
        seen.add(relative)
        path = safe_project_path(root, relative, "Kotlin source")
        if not path.is_file() or path.is_symlink() or file_hash(path) != row["sha256"]:
            raise EvidenceError("partial", "evidence_stale", f"Kotlin source changed: {relative}")


def validate_fact_pack(root: Path, supplied: str | Path) -> tuple[Path, dict[str, Any]]:
    path = safe_project_path(root, supplied, "Kotlin semantic fact pack")
    payload = read_json(path, "Kotlin semantic fact pack")
    if (
        payload.get("schema_version") != "kotlin-jvm-semantic-facts-v1"
        or payload.get("language") != "kotlin"
        or payload.get("status") != "complete"
        or payload.get("read_only") is not True
        or payload.get("project_root") != str(root)
        or not valid_hashed_object(payload, "fact_pack_sha256")
    ):
        raise EvidenceError(
            "partial", "fact_pack_invalid", "complete content-addressed Kotlin facts are required"
        )
    validate_source_rows(root, payload.get("source_inventory"))
    if payload.get("source_manifest_sha256") != canonical_hash(payload["source_inventory"]):
        raise EvidenceError("failed", "fact_pack_invalid", "source manifest hash does not verify")
    if payload.get("diagnostics") != []:
        raise EvidenceError("partial", "fact_pack_diagnostics", "semantic facts contain diagnostics")
    return path, payload


def validate_state_acceptance(
    root: Path,
    *,
    facts_path: str | Path,
    findings_path: str | Path,
    acceptance_path: str | Path,
) -> dict[str, Any]:
    fact_file, facts = validate_fact_pack(root, facts_path)
    finding_file = safe_project_path(root, findings_path, "implicit-state findings")
    findings = read_json(finding_file, "implicit-state findings")
    if (
        findings.get("schema_version") != "kotlin-jvm-state-v1"
        or findings.get("language") != "kotlin"
        or findings.get("status") != "complete"
        or findings.get("read_only") is not True
        or findings.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or findings.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
        or findings.get("candidate_sha256")
        != canonical_hash(findings.get("candidates", []))
    ):
        raise EvidenceError("partial", "producer_artifact_invalid", "accepted state findings do not verify")
    acceptance_file = safe_project_path(root, acceptance_path, "state acceptance")
    acceptance = read_json(acceptance_file, "state acceptance")
    if (
        acceptance.get("schema_version") != "kotlin-state-acceptance-v1"
        or acceptance.get("language") != "kotlin"
        or acceptance.get("status") != "accepted"
        or acceptance.get("producer") != "find-implicit-state"
        or acceptance.get("decision") != "accept-enum"
        or acceptance.get("artifact") != finding_file.relative_to(root).as_posix()
        or acceptance.get("artifact_sha256") != file_hash(finding_file)
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
        raise EvidenceError("partial", "acceptance_invalid", "fresh exact Kotlin state acceptance is required")
    selection = acceptance.get("selection_fq_name")
    candidates = [
        row for row in findings.get("candidates", []) if row.get("fq_name") == selection
    ]
    if len(candidates) != 1:
        raise EvidenceError("partial", "selection_invalid", "acceptance must select one exact state candidate")
    return {
        "facts_path": fact_file,
        "facts": facts,
        "findings_path": finding_file,
        "findings": findings,
        "acceptance_path": acceptance_file,
        "acceptance": acceptance,
        "candidate": candidates[0],
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
        "schema_version": "kotlin-state-consumer-refusal-v1",
        "language": "kotlin",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "detail": error.detail,
        "source_mutations": 0,
        "human_authority": "required",
    }
    report = (
        f"# {skill} — Kotlin refusal\n\nStatus: `{error.status}`.\n\n"
        f"Refused `{error.failure_kind}`: {error.detail}\n\nNo Kotlin source was changed.\n"
    )
    return payload, report
