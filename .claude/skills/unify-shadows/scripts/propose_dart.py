#!/usr/bin/env python3
"""Render one accepted Dart static lead as a read-only human proposal."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "dart-unify-shadows-proposal-v1"
SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
LIMITS = [
    "the accepted D5 record is a conservative static review lead, not behavioral equivalence",
    "the proposal does not choose a canonical implementation or grant source-mutation authority",
    "runtime behavior, side effects, error ordering, external callers, reflection, dynamic dispatch, isolates, native/JS interop, generated code, conditional configurations, and Flutter behavior remain unresolved",
    "a full current reference inventory and behavioral characterization remain human approval gates",
]


class ProposalError(RuntimeError):
    """A typed proposal refusal."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _validator() -> Any:
    candidates = [Path(__file__).with_name("dart_accepted_evidence.py")]
    candidates.extend(
        parent / "_dart" / "dart_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Dart accepted-evidence validator is missing")
    spec = importlib.util.spec_from_file_location("dart_unify_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Dart accepted-evidence validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ACCEPTED = _validator()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contained(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_output(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(raw))
    allowed = root / "reports" / "unify-shadows"
    if not _contained(allowed, output) or output == allowed:
        raise ProposalError(
            "failed",
            "unsafe_output_path",
            "output-dir must stay beneath reports/unify-shadows/ and name one finding",
        )
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ProposalError(
                "failed", "unsafe_output_path", "output-dir traverses a symbolic link"
            )
    return output


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative.as_posix()] = _sha256(path)
    return result


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is not an object")
    return payload


def _relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is missing")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is unsafe")
    return value


def _artifact_paths(evidence: Path, envelope: dict[str, Any]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for row in envelope["artifacts"]:
        relative = _relative(row.get("path"), "artifact path")
        path = evidence / relative
        if not path.is_file() or path.is_symlink():
            raise ProposalError(
                "partial", "evidence_unavailable", f"accepted artifact is unavailable: {relative}"
            )
        result[relative] = path
    return result


def _finding_hash(finding: dict[str, Any]) -> str:
    unhashed = dict(finding)
    supplied = unhashed.pop("finding_sha256", None)
    if not isinstance(supplied, str) or supplied != _canonical_hash(unhashed):
        raise ProposalError(
            "failed", "invalid_selected_finding", "selected finding hash does not verify"
        )
    return supplied


def _span_key(span: dict[str, Any]) -> tuple[Any, ...]:
    return (
        span.get("path"),
        span.get("start_line"),
        span.get("start_column"),
        span.get("end_line"),
        span.get("end_column"),
        span.get("sha256"),
    )


def _validate_citations(envelope: dict[str, Any], finding: dict[str, Any]) -> list[str]:
    accepted = {_span_key(row) for row in envelope["cited_spans"]}
    citations: list[str] = []
    caller_sets: list[set[str]] = []
    members = finding.get("members")
    if not isinstance(members, list) or len(members) != 2:
        raise ProposalError("failed", "invalid_selected_finding", "exactly two members are required")
    for member in members:
        if not isinstance(member, dict) or member.get("fact_status") != "complete":
            raise ProposalError(
                "partial", "incomplete_selected_finding", "member call facts are not complete"
            )
        span = member.get("source_span")
        if not isinstance(span, dict) or _span_key(span) not in accepted:
            raise ProposalError(
                "failed", "uncited_selected_finding", "member source span is not accepted"
            )
        citations.append(
            f"{span['path']}:{span['start_line']}:{span['start_column']}"
        )
        callers = member.get("direct_callers")
        if not isinstance(callers, list) or not callers:
            raise ProposalError(
                "partial", "incomplete_selected_finding", "resolved production callers are required"
            )
        caller_ids: set[str] = set()
        for caller in callers:
            caller_span = caller.get("source_span") if isinstance(caller, dict) else None
            if not isinstance(caller_span, dict) or _span_key(caller_span) not in accepted:
                raise ProposalError(
                    "failed", "uncited_selected_finding", "caller source span is not accepted"
                )
            symbol_id = caller.get("symbol_id")
            if not isinstance(symbol_id, str) or not symbol_id:
                raise ProposalError(
                    "failed", "invalid_selected_finding", "caller identity is missing"
                )
            caller_ids.add(symbol_id)
            citations.append(
                f"{caller_span['path']}:{caller_span['start_line']}:{caller_span['start_column']}"
            )
        caller_sets.append(caller_ids)
    if caller_sets[0] == caller_sets[1]:
        raise ProposalError(
            "partial",
            "incomplete_selected_finding",
            "distinct first-party caller surfaces are not established",
        )
    return sorted(set(citations))


def _validate_upstream(
    evidence: Path,
    envelope: dict[str, Any],
    finding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    paths = _artifact_paths(evidence, envelope)
    producer_relative = envelope["producer"]["artifact"]
    findings_path = paths.get(producer_relative)
    if findings_path is None:
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "producer findings artifact is not bound"
        )
    findings = _read_json(findings_path, "D5 findings")
    if (
        findings.get("schema_version") != "dart-semantic-duplication-v1"
        or findings.get("skill") != "find-semantic-duplication"
        or findings.get("language") != "dart"
        or findings.get("status") != "complete"
    ):
        raise ProposalError(
            "partial", "upstream_not_complete", "D5 findings are not complete Dart evidence"
        )
    finding_sha = _finding_hash(finding)
    matches = [
        row
        for row in findings.get("findings", [])
        if isinstance(row, dict) and row.get("finding_sha256") == finding_sha
    ]
    if len(matches) != 1 or matches[0] != finding:
        raise ProposalError(
            "failed", "invalid_selected_finding", "selected finding is not unique in D5 findings"
        )
    shape = finding.get("consolidation_shape")
    review = finding.get("review")
    if (
        finding.get("investigation_status") != "accepted_static_lead"
        or finding.get("human_verdict") != "accepted"
        or finding.get("machine_consolidation_shape") is not None
        or shape not in SHAPES
        or not isinstance(review, dict)
        or review.get("candidate_sha256") != finding.get("candidate_sha256")
    ):
        raise ProposalError(
            "partial",
            "human_acceptance_required",
            "selected static lead lacks a hash-bound accepted human shape",
        )
    boundaries = envelope["reviewed_boundaries"]
    if (
        boundaries.get("consolidation_shape") != shape
        or boundaries.get("static_lead_only") is not True
        or boundaries.get("source_mutation_authorized") is not False
    ):
        raise ProposalError(
            "failed", "invalid_selected_shape", "accepted boundaries do not bind the selected shape"
        )
    review_relative = f"scout/{finding['candidate_id']}.json"
    review_path = paths.get(review_relative)
    if (
        review_path is None
        or _sha256(review_path) != review.get("review_artifact_sha256")
    ):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "hash-bound D5 human review does not verify"
        )

    matrix_relative = _relative(
        finding.get("capability_matrix_path"), "capability matrix path"
    )
    matrix_path = paths.get(matrix_relative)
    if matrix_path is None:
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "capability matrix is not hash-bound"
        )
    matrix_sha = _sha256(matrix_path)
    if matrix_sha != finding.get("capability_matrix_sha256"):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "capability matrix hash does not verify"
        )
    matrix = _read_json(matrix_path, "D5 capability matrix")
    if (
        matrix.get("schema_version") != "dart-semantic-capability-matrix-v1"
        or matrix.get("candidate_id") != finding.get("candidate_id")
        or matrix.get("machine_consolidation_shape") is not None
        or matrix.get("members") != finding.get("members")
        or matrix.get("return_shape") != finding.get("return_shape")
        or matrix.get("constructor_target") != finding.get("constructor_target")
        or matrix.get("first_party_nonconstructor_callees")
        != finding.get("first_party_nonconstructor_callees")
    ):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "capability matrix does not match finding"
        )

    scan_path = paths.get("scan.json")
    if scan_path is None:
        raise ProposalError("failed", "invalid_upstream_artifact", "D5 scan is not hash-bound")
    scan = _read_json(scan_path, "D5 scan")
    if (
        scan.get("status") != "complete"
        or scan.get("findings_sha256") != _sha256(findings_path)
        or scan.get("capability_matrix_hashes", {}).get(matrix_relative) != matrix_sha
        or scan.get("fact_pack_sha256") != finding.get("fact_pack_sha256")
        or scan.get("query_plan_sha256") != finding.get("query_plan_sha256")
        or scan.get("source_hashes_sha256") != _canonical_hash(findings.get("source_hashes"))
        or scan.get("configuration_hashes_sha256")
        != _canonical_hash(findings.get("configuration_hashes"))
    ):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "D5 scan lineage does not verify"
        )
    if (
        findings.get("source_hashes") != envelope.get("source_hashes")
        or findings.get("configuration_hashes") != envelope.get("configuration_hashes")
    ):
        raise ProposalError(
            "failed", "invalid_upstream_artifact", "accepted source/config hashes diverge from D5"
        )
    citations = _validate_citations(envelope, finding)
    return findings, matrix, scan, citations


def _action(shape: str, members: list[dict[str, Any]]) -> str:
    names = " and ".join(f"`{row['name']}`" for row in members)
    if shape == "keep_separate_document_why":
        return (
            f"Document the load-bearing reason {names} remain separate at both cited declarations. "
            "Leave both entry points and every cited caller unchanged; this proposal contains no shared implementation or caller-move plan."
        )
    if shape == "share_utilities":
        return (
            f"After focused behavioral characterization, review whether {names} can share one deep utility while preserving both entry points and caller contracts. "
            "The accepted static evidence does not identify that utility."
        )
    if shape == "complete_migration":
        return (
            f"Before changing {names}, a human must name the surviving authority, inventory all callers, and define compatibility and rollback. "
            "No survivor or edit plan is selected by this artifact."
        )
    return (
        f"Before coordinating {names} at a workflow boundary, identify the runtime workflow authority and characterize ordering, failures, and side effects. "
        "Static function facts cannot choose that authority."
    )


def _build(
    root: Path,
    evidence: Path,
    acceptance: Path,
    before: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validated = ACCEPTED.validate_accepted_evidence(
        root,
        evidence,
        acceptance,
        expected_producer="find-semantic-duplication",
        expected_kind="dart_semantic_duplication_finding",
    )
    envelope = validated["envelope"]
    finding = validated["selected_evidence"]
    if not isinstance(finding, dict):
        raise ProposalError("failed", "invalid_selected_finding", "selection is not an object")
    findings, matrix, scan, citations = _validate_upstream(evidence, envelope, finding)
    if _snapshot(root) != before:
        raise ProposalError(
            "failed", "source_mutation_detected", "accepted-evidence validation changed the host"
        )
    shape = finding["consolidation_shape"]
    members = finding["members"]
    evidence_payload = {
        "schema_version": SCHEMA_VERSION,
        "skill": "unify-shadows",
        "language": "dart",
        "read_only": True,
        "status": "ready_for_human_review",
        "failure_kind": None,
        "finding_id": finding["candidate_id"],
        "shape": shape,
        "acceptance_hash": envelope["acceptance_hash"],
        "finding_sha256": finding["finding_sha256"],
        "candidate_sha256": finding["candidate_sha256"],
        "capability_matrix_sha256": finding["capability_matrix_sha256"],
        "scan_sha256": _sha256(evidence / "scan.json"),
        "fact_pack_sha256": findings["fact_pack_sha256"],
        "query_plan_sha256": findings["query_plan_sha256"],
        "citations": citations,
        "accepted_native_obligations": envelope["native_obligations"],
        "source_preservation": {"verified": True, "snapshot": before},
        "human_review_required": True,
        "mutation_authorized": False,
        "limits": LIMITS,
    }
    scope = {
        "schema_version": "dart-unify-shadows-scope-v1",
        "status": "ready_for_human_review",
        "finding_id": finding["candidate_id"],
        "shape": shape,
        "members": members,
        "return_shape": matrix["return_shape"],
        "constructor_target": matrix["constructor_target"],
        "first_party_nonconstructor_callees": matrix[
            "first_party_nonconstructor_callees"
        ],
        "source_paths": sorted(
            {
                row["path"]
                for member in members
                for row in [member, *member["direct_callers"]]
            }
        ),
        "proposed_action": _action(shape, members),
        "stop_conditions": [
            "all accepted hashes and citations still verify",
            "a human reviews full bodies, callers, side effects, error behavior, ordering, and compatibility",
            "the host-native analyze, format, direct-test, and exact-smoke obligations remain green",
            "separate source-mutation approval is recorded before any implementation",
        ],
        "mutation_authorized": False,
        "limits": LIMITS,
    }
    return evidence_payload, scope


def _terminal(status: str, failure_kind: str, detail: str) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "skill": "unify-shadows",
        "language": "dart",
        "read_only": True,
        "status": status,
        "failure_kind": failure_kind,
        "message": detail,
        "finding_id": None,
        "shape": None,
        "citations": [],
        "human_review_required": True,
        "mutation_authorized": False,
        "limits": LIMITS,
    }
    scope = {
        "schema_version": "dart-unify-shadows-scope-v1",
        "status": status,
        "failure_kind": failure_kind,
        "finding_id": None,
        "shape": None,
        "members": [],
        "source_paths": [],
        "proposed_action": None,
        "mutation_authorized": False,
        "limits": LIMITS,
    }
    return evidence, scope


def _render(evidence: dict[str, Any], scope: dict[str, Any]) -> str:
    if evidence["status"] != "ready_for_human_review":
        return "\n".join(
            [
                "# Dart unify-shadows proposal — refusal",
                "",
                f"Status: `{evidence['status']}`",
                f"Failure kind: `{evidence['failure_kind']}`",
                "",
                "## Refusal",
                "",
                evidence.get("message", "Accepted D5 evidence did not verify."),
                "",
                "No unification proposal or source-change authority was emitted.",
                "",
            ]
        )
    members = scope["members"]
    lines = [
        f"# Dart unify-shadows proposal — {scope['finding_id']}",
        "",
        "Status: `ready_for_human_review`",
        f"Shape: `{scope['shape']}` (selected by the accepted human D5 review)",
        "",
        "This is a read-only proposal from a conservative static lead. It is not behavioral equivalence or refactor approval.",
        "",
        "## Members",
        "",
    ]
    for member in members:
        span = member["source_span"]
        lines.append(
            f"- `{member['path']}:{span['start_line']}:{span['start_column']}` — `{member['name']}`"
        )
    lines.extend(
        [
            "",
            "## Proposed action",
            "",
            scope["proposed_action"],
            "",
            "## Caller evidence",
            "",
        ]
    )
    for member in members:
        for caller in member["direct_callers"]:
            span = caller["source_span"]
            lines.append(
                f"- `{member['name']}` ← `{caller['path']}:{span['start_line']}:{span['start_column']}` (`{caller['name']}`)"
            )
    lines.extend(["", "## Stop conditions", ""])
    lines.extend(f"- [ ] {item}" for item in scope["stop_conditions"])
    lines.extend(["", "## Explicit limitations", ""])
    lines.extend(f"- {item}" for item in LIMITS)
    lines.extend(["", "Human approval is required before any downstream source change.", ""])
    return "\n".join(lines)


def _write(output: Path, evidence: dict[str, Any], scope: dict[str, Any]) -> None:
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged.mkdir()
    try:
        _atomic(staged / "proposal.md", _render(evidence, scope))
        _atomic(staged / "evidence.json", json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        _atomic(staged / "scope.json", json.dumps(scope, indent=2, sort_keys=True) + "\n")
        if output.exists():
            output.replace(backup)
        try:
            staged.replace(output)
        except OSError:
            if backup.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    try:
        output = _safe_output(root, args.output_dir)
    except ProposalError as exc:
        parser.error(exc.detail)
    before = _snapshot(root)
    raw_evidence = args.evidence_dir if args.evidence_dir.is_absolute() else root / args.evidence_dir
    evidence_dir = Path(os.path.realpath(raw_evidence.resolve(strict=False)))
    raw_acceptance = args.acceptance
    acceptance = raw_acceptance if raw_acceptance.is_absolute() else evidence_dir / raw_acceptance
    try:
        evidence, scope = _build(root, evidence_dir, acceptance, before)
        exit_code = 0
    except ACCEPTED.AcceptedEvidenceError as exc:
        evidence, scope = _terminal(exc.status, exc.failure_kind, exc.detail)
        exit_code = 2
    except ProposalError as exc:
        evidence, scope = _terminal(exc.status, exc.failure_kind, exc.detail)
        exit_code = 2
    except (KeyError, TypeError, ValueError) as exc:
        evidence, scope = _terminal(
            "failed", "invalid_upstream_artifact", f"malformed accepted D5 evidence: {exc}"
        )
        exit_code = 2
    if _snapshot(root) != before:
        evidence, scope = _terminal(
            "failed", "source_mutation_detected", "proposal synthesis changed the audited host"
        )
        exit_code = 2
    _write(output, evidence, scope)
    print(f"wrote Dart unify-shadows proposal artifacts: {output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
