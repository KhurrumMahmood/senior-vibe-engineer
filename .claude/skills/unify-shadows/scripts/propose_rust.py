#!/usr/bin/env python3
"""Render one accepted Rust static lead as a read-only human proposal."""

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
NON_CLAIMS = [
    "traits and blanket implementations are outside this function-level evidence",
    "generics and monomorphized behavior are unresolved",
    "macro expansion and procedural-macro output are unresolved",
    "unselected cfg, feature, and target variants are unresolved",
    "unsafe or FFI behavior is unresolved",
    "runtime behavior, reachability, side effects, ordering, and concurrency are unresolved",
    "external API ownership and compatibility are unresolved",
    "semver compatibility is unresolved",
]
EXCLUDED_SNAPSHOT_PARTS = {".git", ".agents", ".claude", "reports"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProposalError(ValueError):
    """Invalid, stale, or unsupported structured Rust handoff."""


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


def _positive_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProposalError(f"{label} must be a positive integer")
    return value


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProposalError(f"{label} is not valid UTF-8 JSON: {error}") from error


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _snapshot(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(root)
        retained = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_SNAPSHOT_PARTS
            and not (relative_directory / name).parts[0].startswith("cargo-target-")
        )
        directory_names[:] = []
        for name in retained:
            child = directory_path / name
            if child.is_symlink():
                rows.append(
                    {
                        "path": child.relative_to(root).as_posix(),
                        "sha256": _sha256_text(f"symlink:{os.readlink(child)}"),
                        "kind": "symlink",
                    }
                )
            else:
                directory_names.append(name)
        for name in sorted(file_names):
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                digest = _sha256_text(f"symlink:{os.readlink(path)}")
                kind = "symlink"
            elif path.is_file():
                digest = _sha256_bytes(path.read_bytes())
                kind = "file"
            else:
                continue
            rows.append({"path": relative, "sha256": digest, "kind": kind})
    return rows


def _verify_facts(root: Path, payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "rust-semantic-facts-v1":
        raise ProposalError("incompatible Rust semantic fact pack")
    supplied_hash = payload.get("fact_pack_sha256")
    without_hash = dict(payload)
    without_hash.pop("fact_pack_sha256", None)
    canonical = json.dumps(without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if supplied_hash != _sha256_text(canonical):
        raise ProposalError("Rust semantic fact-pack hash does not verify")
    if payload.get("status") != "complete":
        raise ProposalError(
            f"Rust proposal requires complete semantic facts, got {payload.get('status')!r}"
        )
    if payload.get("read_only") is not True:
        raise ProposalError("Rust semantic facts must be read-only")
    if payload.get("compiler", {}).get("state") != "clean":
        raise ProposalError("Rust semantic facts require a clean locked compiler check")
    semantic = payload.get("semantic_analysis", {})
    selected = semantic.get("selected_definitions", {})
    if (
        semantic.get("state") != "complete"
        or semantic.get("protocol") != "LSP"
        or selected.get("protocol") != "LSP"
        or selected.get("unstable_cli_used") is not False
    ):
        raise ProposalError("Rust semantic facts require complete stable-LSP definition evidence")
    editions = {
        row.get("edition") for row in payload.get("cargo_targets", []) if isinstance(row, dict)
    }
    if not editions or editions != {"2024"}:
        raise ProposalError("Rust proposal v1 requires a bounded Cargo 2024 target set")
    if payload.get("source_snapshot") != _snapshot(root):
        raise ProposalError(
            "Rust semantic facts are stale for the current source/configuration snapshot"
        )
    hashes = payload.get("source_hashes")
    if not isinstance(hashes, list) or not hashes:
        raise ProposalError("Rust semantic facts require source hashes")
    for index, raw in enumerate(hashes, 1):
        row = _object(raw, f"source hash {index}")
        relative = _text(row.get("path"), f"source hash {index}.path")
        digest = row.get("sha256")
        if (
            Path(relative).is_absolute()
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise ProposalError(f"source hash {index} is malformed")
        source = _project_file(root, relative, f"source hash {index}")
        if source.is_symlink() or _sha256_bytes(source.read_bytes()) != digest:
            raise ProposalError(f"Rust semantic facts are stale for {relative}")
    limits = payload.get("limits")
    rendered_limits = "\n".join(limits) if isinstance(limits, list) else ""
    for required in (
        "runtime reachability",
        "macro_rules and procedural-macro",
        "unselected cfg",
        "traits, generics, unsafe, FFI",
        "external API behavior",
    ):
        if required not in rendered_limits:
            raise ProposalError(f"Rust semantic facts omit required non-claim: {required}")


def _select(analysis: dict[str, Any], facts: dict[str, Any], finding_id: str) -> dict[str, Any]:
    if analysis.get("schema_version") != "rust-semantic-duplication-v1":
        raise ProposalError("wrong finding kind: expected Rust semantic-duplication analysis")
    if analysis.get("language") != "rust":
        raise ProposalError(
            f"Rust proposal requires language=rust, got {analysis.get('language')!r}"
        )
    if analysis.get("status") != "complete":
        raise ProposalError(
            f"Rust proposal requires complete Rust semantic evidence, got {analysis.get('status')!r}"
        )
    if analysis.get("read_only") is not True:
        raise ProposalError("Rust semantic-duplication analysis must be read-only")
    if analysis.get("target") != facts.get("target"):
        raise ProposalError("Rust analysis target does not match the accepted fact pack")
    if analysis.get("fact_pack_sha256") != facts.get("fact_pack_sha256"):
        raise ProposalError("Rust analysis does not cite the accepted fact pack")
    if analysis.get("source_hashes") != facts.get("source_hashes"):
        raise ProposalError("Rust analysis source hashes do not match the accepted fact pack")
    if analysis.get("limits") != facts.get("limits"):
        raise ProposalError("Rust analysis limits do not match the accepted fact pack")
    confirmed = analysis.get("confirmed")
    if not isinstance(confirmed, list):
        raise ProposalError("Rust analysis requires a confirmed array")
    matches = [
        item for item in confirmed if isinstance(item, dict) and item.get("id") == finding_id
    ]
    if not matches:
        for bucket in (analysis.get("uncertain"), analysis.get("rejected")):
            if isinstance(bucket, list) and any(
                isinstance(item, dict) and item.get("id") == finding_id for item in bucket
            ):
                raise ProposalError(f"{finding_id} is not a confirmed Rust lead")
        raise ProposalError(f"{finding_id} is missing from confirmed Rust leads")
    if len(matches) != 1:
        raise ProposalError(f"{finding_id} must identify exactly one confirmed Rust lead")
    lead = matches[0]
    if lead.get("classification") != "review_required_semantic_lead":
        raise ProposalError(f"{finding_id} is not a review-required semantic lead")
    if lead.get("human_verdict") != "required":
        raise ProposalError(f"{finding_id} must retain human_verdict=required")
    boundary = lead.get("boundary")
    if (
        not isinstance(boundary, str)
        or "not behavioral equivalence" not in boundary
        or "safe-refactor" not in boundary
    ):
        raise ProposalError(f"{finding_id} omits the static-evidence boundary")
    return lead


def _hash_index(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["path"]: row
        for row in facts["source_hashes"]
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }


def _role_index(facts: dict[str, Any]) -> dict[str, str]:
    return {
        row["path"]: row["role"]
        for row in facts.get("source_inventory", [])
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and isinstance(row.get("role"), str)
    }


def _inside_span(rows: Any, source: str, line: int) -> bool:
    if not isinstance(rows, list):
        return False
    return any(
        isinstance(row, dict)
        and row.get("source") == source
        and isinstance(row.get("start_line"), int)
        and isinstance(row.get("end_line"), int)
        and row["start_line"] <= line <= row["end_line"]
        for row in rows
    )


def _members(root: Path, lead: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    raw_members = lead.get("functions")
    if not isinstance(raw_members, list) or len(raw_members) < 2:
        raise ProposalError("confirmed Rust lead requires at least two functions")
    return_shape = _object(lead.get("return_shape"), "return_shape")
    return_type = _text(return_shape.get("type"), "return_shape.type")
    return_fields = return_shape.get("fields")
    if (
        not isinstance(return_fields, list)
        or not return_fields
        or not all(isinstance(field, str) and field for field in return_fields)
    ):
        raise ProposalError("return_shape.fields must be a non-empty string array")
    hashes = _hash_index(facts)
    roles = _role_index(facts)
    members: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_members, 1):
        member = _object(raw, f"function {index}")
        name = _text(member.get("name"), f"function {index}.name")
        relative = _text(member.get("file"), f"function {index}.file")
        line = _positive_integer(member.get("line"), f"function {index}.line")
        if Path(relative).is_absolute() or Path(relative).suffix.casefold() != ".rs":
            raise ProposalError(f"function {index} must cite project-relative Rust source")
        if member.get("scope") != "top_level":
            raise ProposalError("Rust proposals accept only top-level free functions")
        if member.get("attribute_boundary") is not False:
            raise ProposalError(f"{name} crosses a cfg, procedural, or unknown attribute boundary")
        if member.get("return_type") != return_type or member.get("return_fields") != return_fields:
            raise ProposalError(f"{name} does not match the accepted return-shape lead")
        if roles.get(relative) != "production-module" or relative not in hashes:
            raise ProposalError(f"{name} is not accepted production-module evidence")
        source = _project_file(root, relative, f"function {index} source")
        lines = source.read_text(encoding="utf-8").splitlines()
        if line > len(lines):
            raise ProposalError(f"{name} citation is stale")
        header = lines[line - 1]
        if re.search(rf"\bfn\s+{re.escape(name)}\s*\(", header) is None:
            raise ProposalError(f"{name} citation is stale")
        if re.search(rf"\bfn\s+{re.escape(name)}\s*<", header):
            raise ProposalError(f"{name} is generic and outside the Rust proposal boundary")
        if re.search(r"\b(?:unsafe|extern)\b", header):
            raise ProposalError(f"{name} crosses an unsafe or FFI boundary")
        if _inside_span(facts.get("unsafe_ffi_boundaries"), relative, line):
            raise ProposalError(f"{name} crosses an unsafe or FFI boundary")
        if _inside_span(facts.get("macro_regions"), relative, line):
            raise ProposalError(f"{name} crosses a macro expansion boundary")
        members.append(
            {
                "name": name,
                "file": relative,
                "line": line,
                "citation": f"{relative}:{line}",
            }
        )
    if len({member["name"] for member in members}) != len(members):
        raise ProposalError("confirmed Rust lead contains duplicate function names")
    return members


def _callers(
    root: Path,
    lead: dict[str, Any],
    members: list[dict[str, Any]],
    facts: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    raw_callers = _object(lead.get("production_callers"), "production_callers")
    hashes = _hash_index(facts)
    roles = _role_index(facts)
    if set(raw_callers) != {member["name"] for member in members}:
        raise ProposalError("production_callers must name every accepted function exactly once")
    callers: dict[str, list[dict[str, Any]]] = {}
    file_sets: list[set[str]] = []
    for member in members:
        name = member["name"]
        raw_rows = raw_callers.get(name)
        if not isinstance(raw_rows, list) or not raw_rows:
            raise ProposalError(f"{name} requires at least one resolved production caller")
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_rows, 1):
            row = _object(raw, f"{name} caller {index}")
            relative = _text(row.get("file"), f"{name} caller {index}.file")
            line = _positive_integer(row.get("line"), f"{name} caller {index}.line")
            if Path(relative).is_absolute() or Path(relative).suffix.casefold() != ".rs":
                raise ProposalError(f"{name} caller {index} must cite project-relative Rust source")
            if (
                roles.get(relative) not in {"production-module", "workspace-consumer"}
                or relative not in hashes
            ):
                raise ProposalError(f"{name} caller {index} is not accepted production evidence")
            source = _project_file(root, relative, f"{name} caller {index} source")
            lines = source.read_text(encoding="utf-8").splitlines()
            if line > len(lines) or name not in lines[line - 1]:
                raise ProposalError(f"{name} caller {index} citation is stale")
            rows.append({"file": relative, "line": line, "citation": f"{relative}:{line}"})
        callers[name] = rows
        file_sets.append({row["file"] for row in rows})
    if len({tuple(sorted(paths)) for paths in file_sets}) != len(file_sets):
        raise ProposalError("Rust lead lacks distinct resolved production-caller surfaces")
    return callers


def _matrix(
    root: Path,
    analysis_path: Path,
    finding_id: str,
    lead: dict[str, Any],
    members: list[dict[str, Any]],
    callers: dict[str, list[dict[str, Any]]],
) -> tuple[Path, list[str]]:
    candidate = analysis_path.parent / f"capability-matrix-{finding_id.casefold()}.md"
    _reject_symlinks(root, candidate, "capability matrix")
    if not candidate.is_file() or not _inside(root, candidate.resolve()):
        raise ProposalError(f"capability matrix not found for {finding_id}")
    lines = candidate.read_text(encoding="utf-8").splitlines()
    required = [
        f"# Capability matrix — {finding_id}",
        "| Function | Return fields | Resolved production callers |",
        "This matrix does not establish behavioral equivalence.",
    ]
    citations: list[str] = []
    relative = candidate.relative_to(root).as_posix()
    for text in required:
        matches = [index for index, line in enumerate(lines, 1) if line == text]
        if len(matches) != 1:
            raise ProposalError(f"capability matrix is inconsistent for {finding_id}")
        citations.append(f"{relative}:{matches[0]}")
    fields = ", ".join(lead["return_shape"]["fields"])
    for member in members:
        expected = f"| `{member['name']}` | `{fields}` | {len(callers[member['name']])} |"
        matches = [index for index, line in enumerate(lines, 1) if line == expected]
        if len(matches) != 1:
            raise ProposalError(f"capability matrix row is stale for {member['name']}")
        citations.append(f"{relative}:{matches[0]}")
    return candidate, citations


def _action(shape: str, members: list[dict[str, Any]]) -> str:
    names = ", ".join(f"`{member['name']}`" for member in members)
    if shape == "keep_separate_document_why":
        return (
            "Template: `keep_separate_document_why`. Preserve both implementations and document "
            f"why {names} remain separate. Keep current entry points and callers unchanged. This draft is not authorization."
        )
    if shape == "share_utilities":
        return (
            "Template: `share_utilities`. Operator selection permits only a planning draft, not authorization. "
            f"After human behavioral characterization, assess whether {names} share a deep utility seam; keep both entry points and every caller contract."
        )
    if shape == "complete_migration":
        return (
            "Template: `complete_migration`. Operator selection permits only a planning draft, not authorization. "
            "Static evidence cannot choose a survivor: a human must establish canonical ownership, inventory every reference, and approve a tested retirement plan first."
        )
    return (
        "Template: `merge_at_workflow`. Operator selection permits only a planning draft, not authorization. "
        "Static function facts cannot identify workflow authority; a human must supply current workflow, runtime, compatibility, and caller evidence first."
    )


def _render(
    finding_id: str,
    shape: str,
    members: list[dict[str, Any]],
    callers: dict[str, list[dict[str, Any]]],
    matrix_citations: list[str],
) -> str:
    member_lines = [f"- `{member['citation']}` — `{member['name']}`" for member in members]
    caller_lines = [
        f"- `{member['name']}` → `{caller['citation']}`"
        for member in members
        for caller in callers[member["name"]]
    ]
    return "\n".join(
        [
            f"# Rust shadow proposal — {finding_id}",
            "",
            "This is a read-only human-review draft from an accepted static lead. It is not behavioral equivalence, a safe-refactor claim, or source-change approval.",
            "",
            "The selected shape is explicit operator input for proposal structure only; static evidence did not choose it.",
            "",
            "## Shape",
            "",
            f"`{shape}`",
            "",
            "## Members and bounded impact",
            "",
            *member_lines,
            "",
            "Only these cited functions and their cited resolved production callers enter this draft's static scope.",
            "",
            "## Accepted static evidence",
            "",
            *[f"- `{member['citation']}`" for member in members],
            *[f"- `{citation}`" for citation in matrix_citations],
            "",
            "The accepted evidence establishes current top-level source locations, matching constructed return fields, and bounded resolved caller citations only.",
            "",
            "## Proposed action",
            "",
            _action(shape, members),
            "",
            "## Caller impact",
            "",
            *caller_lines,
            "",
            "These language-server-resolved references are bounded static evidence, not a complete runtime, dynamic-dispatch, external-consumer, or public-API graph.",
            "",
            "## Native Rust test matrix",
            "",
            "Run from the Cargo workspace before and after any separately approved implementation:",
            "",
            "- `cargo metadata --format-version 1 --locked --offline --no-deps`",
            "- `cargo check --locked --offline --workspace --all-targets --all-features`",
            "- `cargo test --locked --offline --workspace --all-targets --all-features`",
            "- `cargo clippy --locked --offline --workspace --all-targets --all-features -- -D warnings`",
            "- `cargo fmt --all -- --check`",
            "- Run the host's locked/offline executable smoke and assert its exact output.",
            "",
            "Add focused characterization for inputs, return values, errors/panics, side effects, ordering, ownership, concurrency, feature/cfg variants, and public compatibility before approval.",
            "",
            "## Explicit non-claims",
            "",
            *[f"- {claim}." for claim in NON_CLAIMS],
            "- The accepted static lead does not authorize shared behavior, caller movement, retirement, or source consolidation.",
            "",
            "## Stop condition",
            "",
            "- [ ] The accepted analysis, fact-pack hash, full source/configuration snapshot, source hashes, member/caller citations, and capability matrix still verify.",
            "- [ ] A human has reviewed complete bodies and all project/public references, including traits, blanket implementations, generics, macros, cfg variants, unsafe/FFI, and external consumers.",
            "- [ ] Runtime characterization distinguishes behavior, side effects, ordering, errors/panics, concurrency, ownership, and compatibility.",
            "- [ ] Baseline locked/offline native checks pass and the separately approved plan names focused regression coverage.",
            "- [ ] The human either approves this shape for `/fix-workflow` or records why both implementations remain separate.",
            "",
            "## Authorization and handoff",
            "",
            f"Human approval is required before `/fix-workflow semantic:{finding_id}`. This proposal is not approval and this skill made no source edits.",
            "",
        ]
    )


def _consumer_fingerprint() -> str:
    return f"sha256:{_sha256_bytes(Path(__file__).read_bytes())}"


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
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--finding-id", required=True)
    parser.add_argument("--shape", required=True, choices=sorted(SHAPES))
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
        analysis_path = _project_file(root, args.analysis, "analysis file")
        facts_path = _project_file(root, args.facts, "fact-pack file")
        proposal = _artifact_path(root, args.proposal, "proposal")
        evidence = _artifact_path(root, args.evidence, "evidence")
        if proposal.parent != evidence.parent:
            raise ProposalError("proposal and evidence must share one finding directory")
        if proposal.name != "proposal.md" or evidence.name != "evidence.json":
            raise ProposalError("Rust proposal outputs must be proposal.md and evidence.json")
        if proposal.parent.exists() and not proposal.parent.is_dir():
            raise ProposalError("Rust proposal destination must be a directory")
        facts = _load(facts_path, "Rust semantic fact pack")
        _verify_facts(root, facts)
        analysis = _load(analysis_path, "Rust semantic-duplication analysis")
        lead = _select(analysis, facts, finding_id)
        members = _members(root, lead, facts)
        callers = _callers(root, lead, members, facts)
        matrix_path, matrix_citations = _matrix(
            root, analysis_path, finding_id, lead, members, callers
        )
        rendered = _render(finding_id, args.shape, members, callers, matrix_citations)
        evidence_payload = {
            "status": "proposal_ready_for_human_review",
            "skill": "unify-shadows",
            "language": "rust",
            "finding_id": finding_id,
            "shape": args.shape,
            "shape_source": "explicit_operator_input_for_read_only_draft",
            "authorization": "human_review_required",
            "analysis": analysis_path.relative_to(root).as_posix(),
            "analysis_sha256": f"sha256:{_sha256_bytes(analysis_path.read_bytes())}",
            "facts": facts_path.relative_to(root).as_posix(),
            "fact_pack_sha256": facts["fact_pack_sha256"],
            "capability_matrix": matrix_path.relative_to(root).as_posix(),
            "source_evidence": [member["citation"] for member in members],
            "caller_evidence": [
                caller["citation"] for member in members for caller in callers[member["name"]]
            ],
            "non_claims": NON_CLAIMS,
            "consumer_source_fingerprint": _consumer_fingerprint(),
            "source_mutations": 0,
        }
        scope_payload = {
            "version": 1,
            "paths": sorted(
                {
                    *(member["file"] for member in members),
                    *(caller["file"] for member in members for caller in callers[member["name"]]),
                }
            ),
            "written_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        proposal.parent.parent.mkdir(parents=True, exist_ok=True)
        staged = proposal.parent.with_name(f".{proposal.parent.name}.staged-{uuid.uuid4().hex}")
        staged.mkdir()
        (staged / "proposal.md").write_text(rendered, encoding="utf-8")
        (staged / "evidence.json").write_text(
            json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (staged / "scope.json").write_text(
            json.dumps(scope_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _replace(staged, proposal.parent)
        staged = None
    except (ProposalError, OSError, KeyError, TypeError) as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[propose_rust] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[propose_rust] wrote {proposal}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
