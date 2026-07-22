#!/usr/bin/env python3
"""Render one accepted Java static lead as a read-only human proposal."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
REQUIRED_MATRIX_ROWS = {
    "Static record return type",
    "Returned record components",
    "Resolved direct call relationship",
    "Resolved direct callers",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProposalError(ValueError):
    """Invalid or unsupported structured Java handoff."""


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
    allowed = root / "reports/unify-shadows"
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
    if payload.get("language") != "java":
        raise ProposalError(f"Java proposal requires language=java, got {payload.get('language')!r}")
    if payload.get("status") != "complete":
        raise ProposalError(
            f"Java semantic evidence is {payload.get('status')!r}; refresh complete evidence before synthesis"
        )
    fingerprint = payload.get("source_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
        raise ProposalError("Java semantic evidence requires its source_fingerprint")
    confirmed = payload.get("confirmed")
    if not isinstance(confirmed, list):
        raise ProposalError("findings payload requires a confirmed array")
    matches = [
        item for item in confirmed
        if isinstance(item, dict) and finding_id in {item.get("finding_id"), item.get("id")}
    ]
    if not matches:
        for bucket in (payload.get("uncertain"), payload.get("rejected")):
            if isinstance(bucket, list) and any(
                isinstance(item, dict) and finding_id in {item.get("finding_id"), item.get("id")}
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
        raise ProposalError("Java payload requires the accepted findings array")
    public_matches = [
        item for item in public
        if isinstance(item, dict) and finding_id in {item.get("finding_id"), item.get("id")}
    ]
    if len(public_matches) != 1:
        raise ProposalError(f"{finding_id} must occur exactly once in findings")
    if public_matches[0].get("consolidation_shape") != finding.get("consolidation_shape"):
        raise ProposalError(f"{finding_id} has inconsistent consolidation_shape")
    return finding


def _positive_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProposalError(f"{label} must be a positive integer")
    return value


def _source_manifest(payload: dict[str, Any]) -> dict[str, str]:
    manifest = payload.get("source_manifest")
    if not isinstance(manifest, dict) or manifest.get("algorithm") != "sha256":
        raise ProposalError("Java semantic evidence requires a sha256 source manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(path, str)
        and isinstance(digest, str)
        and SHA256_RE.fullmatch(digest)
        for path, digest in files.items()
    ):
        raise ProposalError("Java semantic source manifest is malformed")
    return files


def _validate_source_hash(
    source: Path,
    relative: str,
    manifest: dict[str, str],
    label: str,
) -> None:
    expected = manifest.get(relative)
    if expected is None:
        raise ProposalError(f"{label} is absent from the upstream source manifest")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ProposalError(f"{label} evidence is stale; refresh Java semantic evidence")


def _members(
    root: Path, finding: dict[str, Any], manifest: dict[str, str]
) -> list[dict[str, Any]]:
    raw_members = finding.get("members")
    if not isinstance(raw_members, list) or len(raw_members) < 2:
        raise ProposalError("confirmed Java finding requires at least two members")
    members: list[dict[str, Any]] = []
    for index, raw_member in enumerate(raw_members, 1):
        member = _object(raw_member, f"member {index}")
        file = _text(member.get("file"), f"member {index}.file")
        if Path(file).is_absolute() or Path(file).suffix.casefold() != ".java":
            raise ProposalError(f"member {index} must cite project-relative Java source")
        source = _project_file(root, file, f"member {index} source")
        name = _text(member.get("qualified_name"), f"member {index}.qualified_name")
        line = _positive_integer(member.get("line"), f"member {index}.line")
        end_line = _positive_integer(member.get("end_line"), f"member {index}.end_line")
        if end_line < line:
            raise ProposalError(f"member {index}.end_line must be at or after line")
        source_lines = source.read_text(encoding="utf-8").splitlines()
        if end_line > len(source_lines):
            raise ProposalError(f"member {index} source span exceeds {file}")
        if name.split(".")[-1] not in "\n".join(source_lines[line - 1 : end_line]):
            raise ProposalError(f"member {index} source span does not contain {name}")
        _validate_source_hash(source, file, manifest, f"member {index}")
        caller_count = member.get("caller_count")
        raw_callers = member.get("direct_callers")
        if not isinstance(caller_count, int) or isinstance(caller_count, bool) or caller_count < 1:
            raise ProposalError(f"member {index}.caller_count must be positive")
        if not isinstance(raw_callers, list) or len(raw_callers) != caller_count:
            raise ProposalError(f"member {index} direct_callers must match caller_count")
        callers: list[dict[str, Any]] = []
        for caller_index, raw_caller in enumerate(raw_callers, 1):
            caller = _object(raw_caller, f"member {index} caller {caller_index}")
            caller_file = _text(caller.get("file"), f"member {index} caller {caller_index}.file")
            if Path(caller_file).is_absolute() or Path(caller_file).suffix.casefold() != ".java":
                raise ProposalError(f"member {index} caller {caller_index} must cite Java source")
            caller_source = _project_file(root, caller_file, f"member {index} caller {caller_index} source")
            caller_line = _positive_integer(caller.get("line"), f"member {index} caller {caller_index}.line")
            lines = caller_source.read_text(encoding="utf-8").splitlines()
            if caller_line > len(lines) or not lines[caller_line - 1].strip():
                raise ProposalError(f"member {index} caller {caller_index} citation is stale")
            _validate_source_hash(
                caller_source,
                caller_file,
                manifest,
                f"member {index} caller {caller_index}",
            )
            callers.append({
                "file": caller_file,
                "line": caller_line,
                "symbol": _text(caller.get("symbol"), f"member {index} caller {caller_index}.symbol"),
                "citation": f"{caller_file}:{caller_line}",
            })
        members.append({
            "file": file, "name": name, "line": line, "end_line": end_line,
            "caller_count": caller_count, "direct_callers": callers,
            "citation": f"{file}:{line}-{end_line}",
        })
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
        raise ProposalError(f"capability matrix is missing required Java evidence rows: {', '.join(missing)}")
    rel = candidate.relative_to(root).as_posix()
    citations = [
        f"{rel}:{line}" for line, text in enumerate(content.splitlines(), 1)
        if any(row in text for row in REQUIRED_MATRIX_ROWS)
    ]
    return candidate, citations


def _action(shape: str, members: list[dict[str, Any]]) -> str:
    names = ", ".join(f"`{member['name']}`" for member in members)
    if shape == "keep_separate_document_why":
        return (
            "Template: `keep_separate_document_why`. Preserve both implementations and document "
            f"why {names} remain separate. Keep every current caller and public contract unchanged."
        )
    if shape == "share_utilities":
        return (
            "Template: `share_utilities`. After full behavioral characterization, identify only a deep shared "
            f"utility seam; keep {names} as explicit entry points and preserve every caller contract."
        )
    if shape == "complete_migration":
        return (
            "Template: `complete_migration`. Choose a survivor only after human review, move every confirmed and "
            "newly inventoried caller under focused tests, and remove the retired entry point only when references are zero."
        )
    return (
        "Template: `merge_at_workflow`. Static record-return evidence cannot identify workflow authority. Obtain "
        "current workflow and runtime evidence first, then propose one authority with explicit compatibility boundaries."
    )


def _render(
    finding_id: str,
    finding: dict[str, Any],
    members: list[dict[str, Any]],
    matrix_citations: list[str],
) -> str:
    shape = str(finding["consolidation_shape"])
    member_lines = [
        f"- `{member['citation']}` — `{member['name']}` ({member['caller_count']} resolved eligible-source callers)"
        for member in members
    ]
    caller_lines = [
        f"- `{member['name']}` → `{caller['citation']}` in `{caller['symbol']}`"
        for member in members for caller in member["direct_callers"]
    ]
    matrix_lines = [f"- `{citation}`" for citation in matrix_citations]
    return "\n".join([
        f"# Java shadow proposal — {finding_id}", "",
        "This is a read-only proposal from an accepted static lead. Matching record construction is not behavioral equivalence.", "",
        "## Shape", "", f"`{shape}`", "",
        "## Members and source impact", "", *member_lines, "",
        "Only cited members and human-confirmed callers may enter a later implementation scope.", "",
        "## Accepted upstream evidence", "",
        *[f"- `{member['citation']}`" for member in members], *matrix_lines, "",
        "The matrix proves only compiler-resolved record type, returned components, and direct eligible-source callers.", "",
        "## Proposed action", "", _action(shape, members), "",
        "## Caller impact", "", *caller_lines, "",
        "Run a full project reference inventory before approval; these compiler-resolved callers are evidence, not a complete runtime graph.", "",
        "## Native Java test matrix", "",
        "- Baseline and post-change: run the host's existing Java 17 compile and test commands.",
        "- Add focused tests that distinguish each method's inputs, exceptions, side effects, ordering, and output values.",
        "- Re-run a compiler or language-server reference search for every member before deleting or moving a caller.", "",
        "## Stop condition", "",
        "- [ ] Every source, caller, and capability-matrix citation still matches the working tree.",
        "- [ ] A human has reviewed full bodies, all references, exceptions, side effects, ordering, and framework/runtime contracts.",
        "- [ ] The selected shape remains justified after behavioral characterization.",
        "- [ ] Baseline native tests pass and the implementation plan names focused regression coverage.", "",
        "## Authorization and handoff", "",
        f"Human approval is required before `/fix-workflow semantic:{finding_id}`. This skill made no source edits.", "",
    ])


def _consumer_fingerprint() -> str:
    return f"sha256:{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}"


def _replace(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--finding-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    staged: Path | None = None
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
        if proposal.name != "proposal.md" or evidence.name != "evidence.json":
            raise ProposalError("Java proposal outputs must be proposal.md and evidence.json")
        payload = _load(findings, "findings payload")
        finding = _select(payload, finding_id)
        source_manifest = _source_manifest(payload)
        members = _members(root, finding, source_manifest)
        matrix_path, matrix_citations = _matrix(root, findings, finding)
        rendered = _render(finding_id, finding, members, matrix_citations)
        source_evidence = [member["citation"] for member in members]
        caller_evidence = [caller["citation"] for member in members for caller in member["direct_callers"]]
        evidence_payload = {
            "status": "proposal_ready_for_human_review", "skill": "unify-shadows",
            "language": "java", "finding_id": finding_id,
            "shape": finding["consolidation_shape"],
            "findings": findings.relative_to(root).as_posix(),
            "capability_matrix": matrix_path.relative_to(root).as_posix(),
            "source_evidence": source_evidence, "caller_evidence": caller_evidence,
            "upstream_source_fingerprint": payload["source_fingerprint"],
            "upstream_source_manifest": payload["source_manifest"],
            "consumer_source_fingerprint": _consumer_fingerprint(), "source_mutations": 0,
        }
        scope_payload = {
            "version": 1,
            "paths": sorted({
                *(member["file"] for member in members),
                *(caller["file"] for member in members for caller in member["direct_callers"]),
            }),
            "written_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        proposal.parent.parent.mkdir(parents=True, exist_ok=True)
        staged = proposal.parent.with_name(f".{proposal.parent.name}.staged-{uuid.uuid4().hex}")
        staged.mkdir()
        (staged / "proposal.md").write_text(rendered, encoding="utf-8")
        (staged / "evidence.json").write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
        (staged / "scope.json").write_text(json.dumps(scope_payload, indent=2) + "\n", encoding="utf-8")
        _replace(staged, proposal.parent)
        staged = None
    except (ProposalError, OSError, KeyError, TypeError) as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[propose_java] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[propose_java] wrote {proposal}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
