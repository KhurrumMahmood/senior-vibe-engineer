#!/usr/bin/env python3
"""Render one accepted Go semantic-duplication finding as a read-only proposal."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
REQUIRED_MATRIX_ROWS = {
    "Static result type",
    "Returned fields",
    "Resolved direct call relationship",
    "Panic / defer / goroutine policy",
}


class ProposalError(ValueError):
    """Invalid or unsupported structured handoff."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlinks(root: Path, candidate: Path, label: str) -> None:
    current = root
    for part in candidate.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ProposalError(f"{label} must not traverse a symbolic link: {candidate}")


def _project_file(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    if not _inside(root, candidate):
        raise ProposalError(f"{label} must stay inside project root: {supplied}")
    _reject_symlinks(root, candidate, label)
    resolved = candidate.resolve()
    if not _inside(root, resolved) or not resolved.is_file():
        raise ProposalError(f"{label} not found: {supplied}")
    return resolved


def _artifact_path(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    allowed = root / "reports" / "unify-shadows"
    if candidate == allowed or not _inside(allowed, candidate):
        raise ProposalError(f"{label} must stay beneath reports/unify-shadows/: {supplied}")
    _reject_symlinks(root, candidate, label)
    return candidate


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProposalError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n\0"):
        raise ProposalError(f"{label} must be non-empty single-line text")
    return value


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, json.JSONDecodeError) as error:
        raise ProposalError(f"{label} is not valid JSON: {error}") from error


def _select(payload: dict[str, Any], finding_id: str) -> dict[str, Any]:
    if payload.get("skill") != "find-semantic-duplication":
        raise ProposalError("wrong finding kind: expected skill=find-semantic-duplication")
    if payload.get("language") != "go":
        raise ProposalError(f"Go proposal requires language=go, got {payload.get('language')!r}")
    if payload.get("status") != "complete":
        raise ProposalError(
            f"Go semantic evidence is {payload.get('status')!r}; refresh complete evidence before synthesis"
        )
    confirmed = payload.get("confirmed")
    if not isinstance(confirmed, list):
        raise ProposalError("findings payload requires a confirmed array")
    matches = [
        item
        for item in confirmed
        if isinstance(item, dict) and finding_id in {item.get("finding_id"), item.get("id")}
    ]
    if not matches:
        for bucket in (payload.get("uncertain"), payload.get("rejected")):
            if isinstance(bucket, list) and any(
                isinstance(item, dict)
                and finding_id in {item.get("finding_id"), item.get("id")}
                for item in bucket
            ):
                raise ProposalError(f"{finding_id} is not confirmed")
        raise ProposalError(f"{finding_id} is missing from confirmed findings")
    if len(matches) != 1:
        raise ProposalError(f"{finding_id} must identify exactly one confirmed finding")
    finding = _object(matches[0], f"confirmed finding {finding_id}")
    if finding.get("investigation_status") != "confirmed":
        raise ProposalError(f"{finding_id} must have investigation_status=confirmed")
    if finding.get("level") != "function":
        raise ProposalError(f"{finding_id} requires a function-level finding")
    if finding.get("consolidation_shape") not in SHAPES:
        raise ProposalError(
            f"{finding_id} has unsupported consolidation_shape={finding.get('consolidation_shape')!r}"
        )
    public = payload.get("findings")
    if not isinstance(public, list):
        raise ProposalError("Go payload requires the accepted findings array")
    public_matches = [
        item
        for item in public
        if isinstance(item, dict) and finding_id in {item.get("finding_id"), item.get("id")}
    ]
    if len(public_matches) != 1:
        raise ProposalError(f"{finding_id} must occur exactly once in findings")
    if public_matches[0].get("consolidation_shape") != finding.get("consolidation_shape"):
        raise ProposalError(f"{finding_id} has inconsistent consolidation_shape")
    return finding


def _members(root: Path, finding: dict[str, Any]) -> list[dict[str, Any]]:
    raw_members = finding.get("members")
    if not isinstance(raw_members, list) or len(raw_members) < 2:
        raise ProposalError("confirmed Go finding requires at least two members")
    members: list[dict[str, Any]] = []
    for index, raw_member in enumerate(raw_members, 1):
        member = _object(raw_member, f"member {index}")
        file = _text(member.get("file"), f"member {index}.file")
        if Path(file).is_absolute() or Path(file).suffix.lower() != ".go":
            raise ProposalError(f"member {index} must cite a project-relative Go source file")
        source = _project_file(root, file, f"member {index} source")
        name = _text(member.get("qualified_name"), f"member {index}.qualified_name")
        line = member.get("line")
        end_line = member.get("end_line")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise ProposalError(f"member {index}.line must be a positive integer")
        if not isinstance(end_line, int) or isinstance(end_line, bool) or end_line < line:
            raise ProposalError(f"member {index}.end_line must be at or after line")
        source_lines = source.read_text(encoding="utf-8").splitlines()
        if end_line > len(source_lines):
            raise ProposalError(f"member {index} source span exceeds {file}")
        if name.split(".")[-1] not in "\n".join(source_lines[line - 1 : end_line]):
            raise ProposalError(f"member {index} source span does not contain {name}")
        callers = member.get("caller_count")
        if callers not in (None, -1) and (
            not isinstance(callers, int) or isinstance(callers, bool) or callers < 0
        ):
            raise ProposalError(f"member {index}.caller_count must be non-negative or unknown")
        members.append(
            {
                "file": file,
                "name": name,
                "line": line,
                "end_line": end_line,
                "caller_count": callers,
                "citation": f"{file}:{line}-{end_line}",
            }
        )
    return members


def _matrix(root: Path, findings: Path, finding: dict[str, Any]) -> tuple[Path, list[str]]:
    relative = _text(finding.get("matrix_path"), "matrix_path")
    candidate = Path(os.path.abspath(findings.parent / relative))
    if not _inside(root, candidate):
        raise ProposalError("capability matrix must stay inside project root")
    _reject_symlinks(root, candidate, "capability matrix")
    candidate = candidate.resolve()
    if not _inside(root, candidate) or not candidate.is_file():
        raise ProposalError(f"capability matrix not found: {relative}")
    content = candidate.read_text(encoding="utf-8")
    missing = sorted(row for row in REQUIRED_MATRIX_ROWS if row not in content)
    if missing:
        raise ProposalError(f"capability matrix is missing required Go evidence rows: {', '.join(missing)}")
    rel = candidate.relative_to(root).as_posix()
    citations = [f"{rel}:{line}" for line, text in enumerate(content.splitlines(), 1) if any(row in text for row in REQUIRED_MATRIX_ROWS)]
    return candidate, citations


def _action(shape: str, members: list[dict[str, Any]]) -> str:
    names = ", ".join(f"`{member['name']}`" for member in members)
    if shape == "keep_separate_document_why":
        return (
            "Template: `keep_separate_document_why`. Preserve both implementations and document "
            f"the load-bearing reason {names} remain separate. Do not move callers or introduce a shared implementation."
        )
    if shape == "share_utilities":
        return (
            "Template: `share_utilities`. After behavioral review, identify the smallest shared utility seam; "
            f"keep {names} as explicit entry points until native tests prove their contracts remain distinct and intact."
        )
    if shape == "complete_migration":
        return (
            "Template: `complete_migration`. Choose the surviving implementation only after caller review, move each "
            "confirmed caller with native tests, and remove the retired member only when no live reference remains."
        )
    return (
        "Template: `merge_at_workflow`. Static function evidence cannot establish workflow authority; first obtain "
        "runtime/workflow evidence, then propose one authority and preserve compatibility at every confirmed caller."
    )


def _render(
    finding_id: str,
    finding: dict[str, Any],
    members: list[dict[str, Any]],
    matrix_citations: list[str],
) -> str:
    shape = str(finding["consolidation_shape"])
    member_lines = [
        f"- `{member['citation']}` — `{member['name']}` ({member['caller_count'] if member['caller_count'] not in (None, -1) else 'unknown'} eligible static callers)"
        for member in members
    ]
    source_citations = [f"- `{member['citation']}`" for member in members]
    matrix_lines = [f"- `{citation}`" for citation in matrix_citations]
    caller_lines = [
        f"- `{member['name']}`: detector observed {member['caller_count'] if member['caller_count'] not in (None, -1) else 'unknown'} resolved incoming calls in eligible production Go source; run a full reference review before edits."
        for member in members
    ]
    return "\n".join(
        [
            f"# Go shadow proposal — {finding_id}",
            "",
            "This is a read-only proposal from a static review lead. It is not proof of behavioral equivalence.",
            "",
            "## Shape",
            "",
            f"`{shape}`",
            "",
            "## Members and source impact",
            "",
            *member_lines,
            "",
            "Only these cited members and human-confirmed project callers are in scope.",
            "",
            "## Evidence",
            "",
            *source_citations,
            *matrix_lines,
            "",
            "The matrix proves matching static result/field facts and visible policy markers only; runtime and framework behavior remain unavailable.",
            "",
            "## Proposed action",
            "",
            _action(shape, members),
            "",
            "## Caller impact",
            "",
            *caller_lines,
            "",
            "## Native Go test matrix",
            "",
            "- Baseline and post-change: `go test ./...`",
            "- Static follow-up where the host already uses it: `go vet ./...`",
            "- Add focused tests that distinguish each member's error, panic, side-effect, and ordering contract before sharing behavior.",
            "",
            "## Stop condition",
            "",
            "- [ ] Every source span and capability-matrix citation still matches the working tree.",
            "- [ ] A human has reviewed full bodies, resolved callers, side effects, error behavior, ordering, and concurrency semantics.",
            "- [ ] The selected shape remains justified after that review.",
            "- [ ] Baseline native tests pass and the implementation plan names focused regression coverage.",
            "",
            "## Authorization and handoff",
            "",
            f"Human approval is required before `/fix-workflow semantic:{finding_id}`. This skill made no source edits.",
            "",
        ]
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--finding-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    try:
        logical_root = Path(os.path.abspath(args.project_root))
        if not logical_root.is_dir() or logical_root.is_symlink():
            raise ProposalError(f"project root is not a directory: {args.project_root}")
        root = logical_root.resolve()
        finding_id = _text(args.finding_id, "finding id")
        findings = _project_file(root, args.findings, "findings file")
        proposal = _artifact_path(root, args.proposal, "proposal")
        evidence = _artifact_path(root, args.evidence, "evidence")
        if proposal.parent != evidence.parent:
            raise ProposalError("proposal and evidence must share one finding directory")
        payload = _load(findings, "findings payload")
        finding = _select(payload, finding_id)
        members = _members(root, finding)
        matrix_path, matrix_citations = _matrix(root, findings, finding)
        rendered = _render(finding_id, finding, members, matrix_citations)
        source_evidence = [member["citation"] for member in members]
        evidence_payload = {
            "status": "proposal_ready_for_human_review",
            "skill": "unify-shadows",
            "language": "go",
            "finding_id": finding_id,
            "shape": finding["consolidation_shape"],
            "findings": findings.relative_to(root).as_posix(),
            "capability_matrix": matrix_path.relative_to(root).as_posix(),
            "source_evidence": source_evidence,
            "source_mutations": 0,
        }
        scope_payload = {
            "version": 1,
            "paths": sorted({member["file"] for member in members}),
            "written_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        _atomic_write(proposal, rendered)
        _atomic_write(evidence, json.dumps(evidence_payload, indent=2) + "\n")
        _atomic_write(proposal.parent / "scope.json", json.dumps(scope_payload, indent=2) + "\n")
    except (ProposalError, OSError) as error:
        print(f"[propose_go] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[propose_go] wrote {proposal}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
