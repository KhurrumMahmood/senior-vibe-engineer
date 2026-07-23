#!/usr/bin/env python3
"""Validate accepted Ruby evidence for the five A4 proposal/guard consumers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


ACCEPTANCE_SCHEMA = "ruby-a4-human-acceptance-v1"
SUPPORTED = {
    "find-implicit-state": "ruby-rbs-implicit-state-v1",
    "find-semantic-duplication": "ruby-rbs-semantic-duplication-v1",
    "find-omnibus": None,
    "find-folder-topology-drift": 1,
}


class EvidenceError(RuntimeError):
    """A fail-closed Ruby evidence boundary."""

    def __init__(self, failure_kind: str, detail: str, *, status: str = "partial") -> None:
        super().__init__(detail)
        self.failure_kind = failure_kind
        self.detail = detail
        self.status = status


def canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("evidence_unavailable", f"{label} is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("invalid_accepted_evidence", f"{label} must be a JSON object")
    return payload


def safe_project_path(root: Path, supplied: Path, label: str) -> Path:
    path = supplied if supplied.is_absolute() else root / supplied
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise EvidenceError("invalid_accepted_evidence", f"{label} escapes the project root") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise EvidenceError("invalid_accepted_evidence", f"{label} traverses a symbolic link")
    return path


def safe_output(root: Path, supplied: Path, skill: str) -> Path:
    path = safe_project_path(root, supplied, "output directory")
    allowed = root / "reports" / skill / "ruby"
    try:
        path.relative_to(allowed)
    except ValueError as exc:
        raise EvidenceError(
            "invalid_output_path", f"output directory must stay beneath {allowed.relative_to(root)}"
        ) from exc
    return path


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(raw, path)
    finally:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def replace_artifacts(output: Path, artifacts: dict[str, str | dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    expected = set(artifacts)
    for path in output.iterdir():
        if path.is_file() and path.name not in expected:
            path.unlink()
    for name, value in artifacts.items():
        if isinstance(value, dict):
            atomic_json(output / name, value)
        else:
            atomic_text(output / name, value)


def _hash_rows(artifact: dict[str, Any], producer: str) -> list[tuple[str, str]]:
    if producer in {"find-implicit-state", "find-semantic-duplication"}:
        raise EvidenceError(
            "incomplete_evidence", "RBS-backed consumers require the accepted semantic fact pack"
        )
    analysis = artifact.get("analysis", {}).get("ruby", {})
    inventory = analysis.get("inventory", [])
    rows = []
    for row in inventory:
        if not isinstance(row, dict):
            continue
        path = row.get("file") or row.get("path")
        digest = row.get("source_sha256") or row.get("sha256")
        if isinstance(path, str) and isinstance(digest, str):
            rows.append((path, digest))
    if not rows:
        raise EvidenceError("incomplete_evidence", "accepted Ruby evidence lacks source hashes")
    return rows


def _validate_rows(root: Path, rows: Iterable[tuple[str, str]]) -> None:
    for relative, expected in rows:
        path = safe_project_path(root, Path(relative), "cited source")
        if not path.is_file() or file_hash(path) != expected:
            raise EvidenceError("stale_accepted_evidence", f"cited source is stale: {relative}")


def validate_source_rows(root: Path, rows: Any) -> None:
    """Validate source rows retained by a downstream Ruby proposal."""
    parsed = [
        (row["path"], row["sha256"])
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and isinstance(row.get("sha256"), str)
    ] if isinstance(rows, list) else []
    if not parsed:
        raise EvidenceError("incomplete_evidence", "accepted Ruby proposal lacks source hashes")
    _validate_rows(root.resolve(), parsed)


def _validate_fact_pack(root: Path, facts_path: Path, expected_hash: str) -> dict[str, Any]:
    facts = read_json(safe_project_path(root, facts_path, "semantic fact pack"), "semantic fact pack")
    if facts.get("status") != "complete" or facts.get("semantic_authority", {}).get("kind") != "project_owned_rbs":
        raise EvidenceError("incomplete_evidence", "project-owned RBS semantic evidence is incomplete")
    claimed = facts.get("fact_pack_sha256")
    unsigned = dict(facts)
    unsigned.pop("fact_pack_sha256", None)
    if not isinstance(claimed, str) or canonical_hash(unsigned) != claimed or claimed != expected_hash:
        raise EvidenceError("invalid_accepted_evidence", "semantic fact-pack hash does not verify")
    rows = [
        (row["path"], row["sha256"])
        for row in facts.get("source_hashes", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str)
    ]
    if not rows:
        raise EvidenceError("incomplete_evidence", "semantic fact pack lacks source hashes")
    _validate_rows(root, rows)
    return facts


def validate(
    *,
    project_root: Path,
    producer: str,
    evidence_path: Path,
    acceptance_path: Path,
    allowed_decisions: set[str],
    facts_path: Path | None = None,
) -> dict[str, Any]:
    """Return hash- and source-validated evidence; never run a detector."""
    root = project_root.resolve()
    if producer not in SUPPORTED:
        raise EvidenceError("unexpected_evidence", f"unsupported Ruby producer: {producer}")
    evidence_file = safe_project_path(root, evidence_path, "evidence artifact")
    acceptance_file = safe_project_path(root, acceptance_path, "acceptance artifact")
    artifact = read_json(evidence_file, "evidence artifact")
    acceptance = read_json(acceptance_file, "acceptance artifact")
    if artifact.get("status") != "complete":
        raise EvidenceError("incomplete_evidence", "upstream Ruby evidence is not complete")
    expected_schema = SUPPORTED[producer]
    if producer == "find-omnibus":
        if artifact.get("analysis", {}).get("ruby", {}).get("analyzer") != "ruby-syntax-prism-v1":
            raise EvidenceError("unexpected_evidence", "omnibus evidence is not the accepted Ruby syntax lane")
    elif artifact.get("schema_version") != expected_schema:
        raise EvidenceError("unexpected_evidence", "Ruby evidence schema does not match the producer")
    if acceptance.get("schema_version") != ACCEPTANCE_SCHEMA or acceptance.get("producer") != producer:
        raise EvidenceError("invalid_accepted_evidence", "human acceptance authority is malformed")
    expected_artifact = evidence_file.relative_to(root).as_posix()
    if acceptance.get("artifact") != expected_artifact or acceptance.get("artifact_sha256") != file_hash(evidence_file):
        raise EvidenceError("invalid_accepted_evidence", "human acceptance is not bound to this artifact")
    reviewer = acceptance.get("reviewer")
    boundaries = acceptance.get("reviewed_boundaries")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(boundaries, list) or not boundaries:
        raise EvidenceError("invalid_accepted_evidence", "human reviewer and reviewed boundaries are required")
    decision = acceptance.get("decision")
    if decision not in allowed_decisions:
        raise EvidenceError("unaccepted_evidence", f"human decision is not accepted here: {decision!r}")
    candidate_hash = artifact.get("candidate_sha256")
    if candidate_hash is not None and acceptance.get("candidate_sha256") != candidate_hash:
        raise EvidenceError("invalid_accepted_evidence", "acceptance candidate hash does not verify")
    if producer in {"find-implicit-state", "find-semantic-duplication"}:
        if facts_path is None:
            raise EvidenceError("incomplete_evidence", "RBS-backed evidence requires --facts")
        facts = _validate_fact_pack(root, facts_path, artifact.get("fact_pack_sha256", ""))
    else:
        _validate_rows(root, _hash_rows(artifact, producer))
        facts = None
    return {
        "root": root,
        "artifact": artifact,
        "artifact_path": evidence_file,
        "artifact_sha256": file_hash(evidence_file),
        "acceptance": acceptance,
        "acceptance_sha256": file_hash(acceptance_file),
        "facts": facts,
    }


def refusal(skill: str, error: EvidenceError) -> tuple[dict[str, Any], str]:
    payload = {
        "schema_version": "ruby-a4-refusal-v1",
        "language": "ruby",
        "skill": skill,
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.failure_kind,
        "detail": error.detail,
        "source_mutations": 0,
        "human_authority": "required",
    }
    report = (
        f"# {skill} — Ruby refusal\n\nStatus: `{error.status}`\n\n"
        f"Refused: `{error.failure_kind}` — {error.detail}\n\nNo source was changed.\n"
    )
    return payload, report
