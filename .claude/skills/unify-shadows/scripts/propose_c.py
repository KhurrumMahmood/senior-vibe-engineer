#!/usr/bin/env python3
"""Render one accepted C static lead as a read-only shadow proposal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
SOURCE_SUFFIXES = {".c", ".i", ".h", ".inc"}
INTERNAL_PARTS = {".agents", ".claude", ".engineering", ".git", "reports"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FINDING_ID = re.compile(r"^C-SD-(\d{4})$")
FACT_SCHEMA = "c-semantic-facts-v1"
ANALYSIS_SCHEMA = "c-semantic-duplication-v1"
ACCEPTANCE_SCHEMA = "c-unify-shadows-acceptance-v1"
EVIDENCE_SCHEMA = "c-unify-shadows-evidence-v1"
SCOPE_SCHEMA = "c-unify-shadows-scope-v1"
REQUIRED_LIMIT = (
    "matching static shapes never establish behavioral equivalence, alias safety, "
    "UB equivalence, or consolidation safety"
)
STOP_CONDITIONS = [
    "all accepted artifact, fact-pack, source, caller, and compile-database hashes still verify",
    "ABI: stop on any public signature, linkage, symbol visibility, calling convention, record layout, or binary-compatibility change",
    "external consumers: stop until callbacks, function pointers, dynamic lookup, every build variant, and out-of-tree callers are inventoried",
    "side effects: stop unless characterization covers output values, errno, globals, I/O, allocation/lifetime, ordering, concurrency, and reentrancy",
    "undefined behavior: stop if either implementation or proposed shared path may depend on aliasing, lifetime, bounds, overflow, alignment, unions, volatile access, or other UB",
    "the accepted Make compile-database/test commands and exact executable smoke remain green before and after an approved implementation",
    "Human approval for source mutation is recorded separately from this read-only proposal choice",
]


class ProposalError(ValueError):
    """A terminal proposal refusal with a stable artifact vocabulary."""

    def __init__(self, status: str, failure_kind: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            raise ProposalError(
                "failed", "unsafe_path", f"{label} must not traverse a symbolic link"
            )


def _input_file(root: Path, supplied: Path, label: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    candidate = Path(os.path.abspath(raw))
    if not _inside(root, candidate):
        raise ProposalError(
            "failed", "unsafe_path", f"{label} must stay inside project root"
        )
    _reject_symlinks(root, candidate, label)
    if not candidate.is_file():
        raise ProposalError(
            "partial", "evidence_unavailable", f"{label} is unavailable: {supplied}"
        )
    return candidate


def _output_dir(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    candidate = Path(os.path.abspath(raw))
    allowed = root / "reports/unify-shadows"
    if candidate == allowed or not _inside(allowed, candidate):
        raise ProposalError(
            "failed",
            "unsafe_path",
            "output must name a directory beneath reports/unify-shadows/",
        )
    _reject_symlinks(root, candidate, "output")
    if candidate.exists() and not candidate.is_dir():
        raise ProposalError("failed", "unsafe_path", "output must be a directory")
    return candidate


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProposalError(
            "failed", "invalid_accepted_evidence", f"{label} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", f"{label} must be an object"
        )
    return value


def _single_line(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(character in value for character in "\r\n\0")
    ):
        raise ProposalError(
            "failed", "invalid_human_acceptance", f"{label} must be single-line text"
        )
    return value


def _source_manifest(root: Path) -> tuple[str, list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in INTERNAL_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES or not (
            path.is_file() or path.is_symlink()
        ):
            continue
        digest = (
            f"symlink:{os.readlink(path)}"
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        rows.append({"path": relative.as_posix(), "sha256": digest})
    rows.sort(key=lambda row: row["path"])
    return _canonical_hash(rows), rows


def _verify_facts(root: Path, facts: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    if facts.get("schema_version") != FACT_SCHEMA or facts.get("language") != "c":
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "incompatible C semantic fact pack"
        )
    supplied_hash = facts.get("fact_pack_sha256")
    unhashed = dict(facts)
    unhashed.pop("fact_pack_sha256", None)
    if not isinstance(supplied_hash, str) or supplied_hash != _canonical_hash(unhashed):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "C semantic fact-pack hash does not verify"
        )
    if facts.get("status") != "complete":
        raise ProposalError(
            "partial", "upstream_not_complete", "complete C semantic facts are required"
        )
    if facts.get("read_only") is not True:
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "C semantic facts must be read-only"
        )
    database = facts.get("compile_database")
    if not isinstance(database, dict) or database.get("state") != "valid-current-complete-c17":
        raise ProposalError(
            "partial", "upstream_not_complete", "a complete current C17 compile database is required"
        )
    database_path = root / "compile_commands.json"
    if (
        not database_path.is_file()
        or not isinstance(database.get("sha256"), str)
        or _sha256(database_path) != database["sha256"]
    ):
        raise ProposalError(
            "failed", "stale_accepted_evidence", "compile_commands.json changed"
        )
    inputs = [root / "Makefile"]
    inputs.extend(root / item for item in database.get("translation_units", []))
    dependency_closure = facts.get("dependency_closure", {})
    if isinstance(dependency_closure, dict):
        for paths in dependency_closure.values():
            if isinstance(paths, list):
                inputs.extend(root / item for item in paths if isinstance(item, str))
    newest_input = max(
        (path.stat().st_mtime_ns for path in inputs if path.is_file()), default=0
    )
    if database_path.stat().st_mtime_ns < newest_input:
        raise ProposalError(
            "failed", "stale_accepted_evidence", "compile_commands.json is stale"
        )
    manifest_sha, manifest = _source_manifest(root)
    if (
        facts.get("source_manifest_sha256") != manifest_sha
        or facts.get("source_files") != manifest
        or facts.get("source_preservation")
        != {"before": manifest_sha, "after": manifest_sha, "unchanged": True}
    ):
        raise ProposalError(
            "failed", "stale_accepted_evidence", "C source or owned headers changed"
        )
    limits = facts.get("limits")
    if not isinstance(limits, list) or not all(isinstance(item, str) for item in limits):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "C semantic limits are malformed"
        )
    return manifest_sha, manifest


def _verify_analysis(
    analysis: dict[str, Any], facts: dict[str, Any]
) -> list[dict[str, Any]]:
    if (
        analysis.get("schema_version") != ANALYSIS_SCHEMA
        or analysis.get("language") != "c"
    ):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "wrong C semantic-duplication artifact"
        )
    if analysis.get("status") != "complete":
        raise ProposalError(
            "partial", "upstream_not_complete", "complete semantic-duplication evidence is required"
        )
    if analysis.get("read_only") is not True:
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "semantic-duplication evidence must be read-only"
        )
    if analysis.get("fact_pack_sha256") != facts.get("fact_pack_sha256"):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "analysis does not cite the supplied fact pack"
        )
    if analysis.get("limits") != [*facts["limits"], REQUIRED_LIMIT]:
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "analysis limits diverge from C facts"
        )
    leads = analysis.get("leads")
    if not isinstance(leads, list) or not all(isinstance(item, dict) for item in leads):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "analysis leads are malformed"
        )
    return leads


def _select_lead(
    leads: list[dict[str, Any]], acceptance: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    raw_id = acceptance.get("finding_id")
    match = FINDING_ID.fullmatch(raw_id) if isinstance(raw_id, str) else None
    if match is None:
        raise ProposalError(
            "failed", "invalid_human_acceptance", "finding_id must use C-SD-NNNN"
        )
    index = int(match.group(1))
    if index < 1 or index > len(leads):
        raise ProposalError(
            "failed", "invalid_human_acceptance", f"{raw_id} is absent from current leads"
        )
    lead = leads[index - 1]
    if acceptance.get("finding_sha256") != _canonical_hash(lead):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "accepted finding hash does not verify"
        )
    return raw_id, lead


def _facts_indexes(
    facts: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    hashes = {
        row["path"]: row["sha256"]
        for row in facts.get("source_files", [])
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and isinstance(row.get("sha256"), str)
    }
    inventory = {
        row["path"]: row
        for row in facts.get("source_inventory", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    return hashes, inventory


def _line_contains(root: Path, relative: str, line: int, symbol: str) -> bool:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    return line <= len(lines) and re.search(rf"\b{re.escape(symbol)}\s*\(", lines[line - 1]) is not None


def _citations(
    root: Path, lead: dict[str, Any], facts: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        lead.get("classification") != "static_review_lead"
        or lead.get("human_verdict") != "required"
        or lead.get("automatic_consolidation") is not False
        or "never behavioral equivalence" not in str(lead.get("boundary"))
    ):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "selected lead lost its static-review boundary"
        )
    members = lead.get("functions")
    shape = lead.get("return_shape")
    if (
        not isinstance(members, list)
        or len(members) < 2
        or not isinstance(shape, dict)
        or not isinstance(shape.get("record"), str)
        or not isinstance(shape.get("designated_fields"), list)
        or not shape["designated_fields"]
    ):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "selected lead members or return shape are malformed"
        )
    hashes, inventory = _facts_indexes(facts)
    declarations = facts.get("declarations", [])
    compounds = facts.get("compound_literals", [])
    references = facts.get("direct_references", [])
    source_rows: list[dict[str, Any]] = []
    caller_rows: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw_member in members:
        if not isinstance(raw_member, dict):
            raise ProposalError(
                "failed", "invalid_accepted_evidence", "selected member is malformed"
            )
        name = raw_member.get("name")
        relative = raw_member.get("file")
        line = raw_member.get("line")
        callers = raw_member.get("direct_callers")
        if (
            not isinstance(name, str)
            or name in names
            or not isinstance(relative, str)
            or Path(relative).is_absolute()
            or Path(relative).suffix.lower() not in {".c", ".i"}
            or not isinstance(line, int)
            or isinstance(line, bool)
            or line < 1
            or not isinstance(callers, list)
            or not callers
            or len(set(callers)) != len(callers)
            or not all(isinstance(item, str) and item for item in callers)
        ):
            raise ProposalError(
                "failed", "invalid_accepted_evidence", "selected member/caller evidence is malformed"
            )
        names.add(name)
        role = inventory.get(relative, {})
        if role.get("role") != "production" or role.get("included") is not True:
            raise ProposalError(
                "failed", "invalid_accepted_evidence", f"{name} is not included production C evidence"
            )
        digest = hashes.get(relative)
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ProposalError(
                "failed", "invalid_accepted_evidence", f"{name} has no accepted source hash"
            )
        declaration_matches = [
            row
            for row in declarations
            if isinstance(row, dict)
            and row.get("kind") == "function"
            and row.get("name") == name
            and row.get("file") == relative
            and row.get("line") == line
            and row.get("definition") is True
            and row.get("linkage") == "external"
            and row.get("macro_expansion") is False
        ]
        shape_matches = [
            row
            for row in compounds
            if isinstance(row, dict)
            and row.get("function") == name
            and row.get("file") == relative
            and row.get("context") == "return"
            and row.get("record") == shape["record"]
            and row.get("fields") == shape["designated_fields"]
            and row.get("macro_expansion") is False
        ]
        if (
            len(declaration_matches) != 1
            or len(shape_matches) != 1
            or not _line_contains(root, relative, line, name)
        ):
            raise ProposalError(
                "failed", "stale_accepted_evidence", f"source citation for {name} is stale"
            )
        source_rows.append(
            {
                "function": name,
                "path": relative,
                "line": line,
                "citation": f"{relative}:{line}",
                "sha256": digest,
            }
        )
        resolved_callers = sorted(
            {
                row.get("function")
                for row in references
                if isinstance(row, dict)
                and row.get("context") == "direct_call"
                and row.get("name") == name
                and row.get("macro_expansion") is False
                and isinstance(row.get("function"), str)
            }
        )
        if callers != resolved_callers:
            raise ProposalError(
                "failed",
                "invalid_accepted_evidence",
                f"accepted direct callers for {name} diverge from the fact pack",
            )
        for caller in callers:
            matches = [
                row
                for row in references
                if isinstance(row, dict)
                and row.get("context") == "direct_call"
                and row.get("name") == name
                and row.get("function") == caller
                and row.get("macro_expansion") is False
            ]
            if not matches:
                raise ProposalError(
                    "failed", "stale_accepted_evidence", f"direct caller evidence for {name} is stale"
                )
            for row in matches:
                caller_path = row.get("file")
                caller_line = row.get("line")
                caller_role = inventory.get(caller_path, {})
                caller_hash = hashes.get(caller_path)
                if (
                    not isinstance(caller_path, str)
                    or not isinstance(caller_line, int)
                    or caller_role.get("role") != "production"
                    or caller_role.get("included") is not True
                    or not isinstance(caller_hash, str)
                    or SHA256.fullmatch(caller_hash) is None
                    or not _line_contains(root, caller_path, caller_line, name)
                ):
                    raise ProposalError(
                        "failed", "stale_accepted_evidence", f"caller citation for {name} is stale"
                    )
                caller_rows.append(
                    {
                        "callee": name,
                        "caller": caller,
                        "path": caller_path,
                        "line": caller_line,
                        "citation": f"{caller_path}:{caller_line}",
                        "sha256": caller_hash,
                    }
                )
    return source_rows, caller_rows


def _accepted_citations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key != "citation"}
        for row in rows
    ]


def _verify_acceptance(
    acceptance: dict[str, Any],
    analysis_path: Path,
    analysis: dict[str, Any],
    facts: dict[str, Any],
    source_rows: list[dict[str, Any]],
    caller_rows: list[dict[str, Any]],
) -> tuple[str, dict[str, str]]:
    supplied_hash = acceptance.get("acceptance_sha256")
    unhashed = dict(acceptance)
    unhashed.pop("acceptance_sha256", None)
    if not isinstance(supplied_hash, str) or supplied_hash != _canonical_hash(unhashed):
        raise ProposalError(
            "failed", "invalid_human_acceptance", "human acceptance hash does not verify"
        )
    if acceptance.get("status") != "accepted":
        raise ProposalError(
            "partial", "human_acceptance_required", "an accepted human proposal choice is required"
        )
    if (
        acceptance.get("schema_version") != ACCEPTANCE_SCHEMA
        or acceptance.get("language") != "c"
        or acceptance.get("producer") != "find-semantic-duplication"
        or acceptance.get("consumer") != "unify-shadows"
    ):
        raise ProposalError(
            "failed", "invalid_human_acceptance", "acceptance authority is for another contract"
        )
    if (
        acceptance.get("analysis_sha256") != _sha256(analysis_path)
        or acceptance.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or acceptance.get("accepted_limits") != analysis.get("limits")
    ):
        raise ProposalError(
            "failed", "invalid_accepted_evidence", "acceptance is not bound to current C evidence"
        )
    shape = acceptance.get("decision")
    if shape not in SHAPES:
        raise ProposalError(
            "failed", "invalid_human_acceptance", "unsupported consolidation choice"
        )
    _single_line(acceptance.get("rationale"), "rationale")
    if (
        acceptance.get("source_citations") != _accepted_citations(source_rows)
        or acceptance.get("caller_citations") != _accepted_citations(caller_rows)
    ):
        raise ProposalError(
            "failed", "invalid_human_acceptance", "accepted source/caller citations do not match current evidence"
        )
    native = acceptance.get("native")
    keys = {"compile_database", "test", "smoke", "smoke_stdout"}
    if not isinstance(native, dict) or set(native) != keys:
        raise ProposalError(
            "failed", "invalid_human_acceptance", "native Make/smoke obligations are incomplete"
        )
    checked_native = {key: _single_line(native[key], f"native.{key}") for key in sorted(keys)}
    return shape, checked_native


def _action(shape: str, members: list[dict[str, Any]]) -> str:
    names = " and ".join(f"`{row['function']}`" for row in members)
    if shape == "keep_separate_document_why":
        return (
            f"Keep {names} separate and document the load-bearing ownership or policy difference at both cited definitions. "
            "No shared implementation or caller move is proposed; every entry point and direct caller remains unchanged."
        )
    if shape == "share_utilities":
        return (
            f"Preserve both {names} entry points and their caller contracts. After characterization, identify at most one deep utility seam whose extraction does not collapse ownership; the accepted static lead does not identify or validate that seam."
        )
    if shape == "complete_migration":
        return (
            f"Treat {names} as migration candidates only. Before implementation, separately approve the survivor and compatibility boundary, characterize both bodies, enumerate all callers, migrate one caller surface at a time, and delete the retired entry point only after native parity."
        )
    return (
        f"Treat {names} as participants in a possible workflow-level merge. First identify the runtime workflow authority and characterize ordering, failures, resource ownership, and side effects; preserve both current entry points until that separate authority and rollout are approved."
    )


def _impacts(
    shape: str,
    members: list[dict[str, Any]],
    callers: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if shape == "keep_separate_document_why":
        source_change = "documentation only; implementation stays separate"
        caller_change = "none; current call remains unchanged"
    elif shape == "share_utilities":
        source_change = "characterize, then assess a deep shared utility while retaining this entry point"
        caller_change = "none planned; retain the current callee contract"
    elif shape == "complete_migration":
        source_change = "characterize; survivor and compatibility plan require separate approval"
        caller_change = "migration candidate only after complete caller and external-consumer inventory"
    else:
        source_change = "characterize workflow role; keep entry point until runtime authority is approved"
        caller_change = "workflow coordination candidate only after ordering and side effects are proven"
    return (
        [
            {"citation": member["citation"], "impact": source_change}
            for member in members
        ],
        [
            {
                "citation": caller["citation"],
                "callee": caller["callee"],
                "impact": caller_change,
            }
            for caller in callers
        ],
    )


def _build(
    root: Path,
    analysis_path: Path,
    facts_path: Path,
    acceptance_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    facts = _load(facts_path, "C semantic facts")
    manifest_sha, manifest = _verify_facts(root, facts)
    analysis = _load(analysis_path, "C semantic-duplication analysis")
    leads = _verify_analysis(analysis, facts)
    acceptance = _load(acceptance_path, "C human acceptance")
    finding_id, lead = _select_lead(leads, acceptance)
    members, callers = _citations(root, lead, facts)
    shape, native = _verify_acceptance(
        acceptance, analysis_path, analysis, facts, members, callers
    )
    source_impact, caller_impact = _impacts(shape, members, callers)
    outcome = (
        "keep_separate_documented"
        if shape == "keep_separate_document_why"
        else "proposal_ready"
    )
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "skill": "unify-shadows",
        "language": "c",
        "status": "complete",
        "failure_kind": None,
        "outcome": outcome,
        "read_only": True,
        "finding_id": finding_id,
        "shape": shape,
        "analysis_sha256": _sha256(analysis_path),
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "finding_sha256": acceptance["finding_sha256"],
        "acceptance_sha256": acceptance["acceptance_sha256"],
        "source_citations": members,
        "caller_citations": callers,
        "source_preservation": {
            "verified": True,
            "source_manifest_sha256": manifest_sha,
            "files": manifest,
        },
        "behavioral_equivalence_claimed": False,
        "mutation_authorized": False,
        "limits": analysis["limits"],
    }
    scope = {
        "schema_version": SCOPE_SCHEMA,
        "status": "complete",
        "finding_id": finding_id,
        "shape": shape,
        "members": members,
        "direct_callers": callers,
        "return_shape": lead["return_shape"],
        "proposed_action": _action(shape, members),
        "source_impact": source_impact,
        "caller_impact": caller_impact,
        "native_test_matrix": native,
        "stop_conditions": STOP_CONDITIONS,
        "human_approval_required": True,
        "mutation_authorized": False,
        "limits": analysis["limits"],
    }
    return evidence, scope


def _terminal(error: ProposalError) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "skill": "unify-shadows",
        "language": "c",
        "status": error.status,
        "failure_kind": error.failure_kind,
        "message": error.detail,
        "outcome": "refused",
        "read_only": True,
        "finding_id": None,
        "shape": None,
        "source_citations": [],
        "caller_citations": [],
        "behavioral_equivalence_claimed": False,
        "mutation_authorized": False,
    }
    scope = {
        "schema_version": SCOPE_SCHEMA,
        "status": error.status,
        "failure_kind": error.failure_kind,
        "finding_id": None,
        "shape": None,
        "members": [],
        "direct_callers": [],
        "proposed_action": None,
        "source_impact": [],
        "caller_impact": [],
        "native_test_matrix": {},
        "stop_conditions": [],
        "human_approval_required": True,
        "mutation_authorized": False,
    }
    return evidence, scope


def _render(evidence: dict[str, Any], scope: dict[str, Any]) -> str:
    if evidence["status"] != "complete":
        return "\n".join(
            [
                "# C shadow-unification proposal — refusal",
                "",
                f"Status: `{evidence['status']}`",
                f"Failure kind: `{evidence['failure_kind']}`",
                "",
                "## Refusal",
                "",
                evidence["message"],
                "",
                "No proposal authority or source-mutation authority was emitted.",
                "",
            ]
        )
    lines = [
        f"# C shadow-unification proposal — {scope['finding_id']}",
        "",
        "Status: `complete` (read-only)",
        f"Shape: `{scope['shape']}` (the exact accepted human consolidation choice)",
        "",
        "Matching C17 return construction and resolved direct calls are a static review lead only. This proposal does not claim behavioral equivalence, alias safety, ABI compatibility, or safe consolidation.",
        "",
        "## Exact source and caller evidence",
        "",
    ]
    for member in scope["members"]:
        lines.append(
            f"- `{member['function']}` — `{member['citation']}` (`sha256:{member['sha256']}`)"
        )
    for caller in scope["direct_callers"]:
        lines.append(
            f"- `{caller['caller']}` → `{caller['callee']}` — `{caller['citation']}` (`sha256:{caller['sha256']}`)"
        )
    lines.extend(["", "## Proposed action", "", scope["proposed_action"]])
    lines.extend(["", "## Source and caller impact", ""])
    for row in scope["source_impact"]:
        lines.append(f"- Source `{row['citation']}` — {row['impact']}.")
    for row in scope["caller_impact"]:
        lines.append(
            f"- Caller `{row['citation']}` → `{row['callee']}` — {row['impact']}."
        )
    native = scope["native_test_matrix"]
    lines.extend(
        [
            "",
            "## Native test matrix",
            "",
            f"- Compile database baseline: `{native['compile_database']}`",
            f"- Warnings-as-errors/native test: `{native['test']}`",
            f"- Executable smoke: `{native['smoke']}`",
            f"- Exact smoke stdout: `{native['smoke_stdout']}`",
            "",
            "## Stop conditions",
            "",
        ]
    )
    lines.extend(f"- [ ] {item}" for item in scope["stop_conditions"])
    lines.extend(["", "## Accepted limitations", ""])
    lines.extend(f"- {item}" for item in scope["limits"])
    lines.extend(
        [
            "",
            "## Authorization",
            "",
            "Human approval for source mutation is still required. The accepted consolidation choice authorizes only this proposal artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_text(path: Path, text: str) -> None:
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


def _replace_bundle(
    output: Path, evidence: dict[str, Any], scope: dict[str, Any]
) -> None:
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staged.mkdir()
    try:
        _atomic_text(staged / "proposal.md", _render(evidence, scope))
        _atomic_text(
            staged / "evidence.json",
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        )
        _atomic_text(
            staged / "scope.json", json.dumps(scope, indent=2, sort_keys=True) + "\n"
        )
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
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        if not root.is_dir() or args.project_root.is_symlink():
            raise ProposalError(
                "failed", "unsafe_path", "project root must be a regular directory"
            )
        output = _output_dir(root, args.output_dir)
    except (OSError, ProposalError) as exc:
        detail = exc.detail if isinstance(exc, ProposalError) else str(exc)
        parser.error(detail)
    before_sha, before_manifest = _source_manifest(root)
    try:
        analysis = _input_file(root, args.analysis, "analysis")
        facts = _input_file(root, args.facts, "facts")
        acceptance = _input_file(root, args.acceptance, "acceptance")
        evidence, scope = _build(root, analysis, facts, acceptance)
        exit_code = 0
    except ProposalError as exc:
        evidence, scope = _terminal(exc)
        exit_code = 2
    except (KeyError, TypeError, ValueError) as exc:
        evidence, scope = _terminal(
            ProposalError(
                "failed",
                "invalid_accepted_evidence",
                f"malformed accepted C evidence: {exc}",
            )
        )
        exit_code = 2
    if _source_manifest(root) != (before_sha, before_manifest):
        evidence, scope = _terminal(
            ProposalError(
                "failed",
                "source_mutation_detected",
                "source changed during read-only C proposal validation",
            )
        )
        exit_code = 2
    _replace_bundle(output, evidence, scope)
    if _source_manifest(root) != (before_sha, before_manifest):
        evidence, scope = _terminal(
            ProposalError(
                "failed",
                "source_mutation_detected",
                "source changed during read-only C proposal synthesis",
            )
        )
        _replace_bundle(output, evidence, scope)
        exit_code = 2
    print(f"wrote C unify-shadows proposal artifacts: {output}")
    if exit_code:
        print(
            f"unify-shadows: {evidence['failure_kind']}: {evidence.get('message', '')}",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
