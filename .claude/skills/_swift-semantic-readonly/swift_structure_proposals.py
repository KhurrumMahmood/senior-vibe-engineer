#!/usr/bin/env python3
"""Consume accepted Swift structure evidence and prove read-only proposals."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "swift-structure-proposal-v1"
ACCEPTANCE_SCHEMA = "swift-structure-acceptance-v1"
CANDIDATE_VERDICT_SCHEMA = "swift-structure-candidate-verdict-v1"
PROPOSAL_VERDICT_SCHEMA = "swift-structure-proposal-verdict-v1"
BOUNDARY_GATES = {
    "abi": "not_claimed_separate_release_approval",
    "compatibility": "three_original_public_static_signatures_retained_as_shims",
    "dynamic_reflection": "none_selected",
    "external_callers": "none",
    "macro_conditional_compilation": "none_selected",
    "module_identity": "SwiftA3Core_unchanged",
    "new_boundary": "internal_ExportOperations",
    "protocol_actor_dispatch": "none_selected",
    "resolved_callers": "accepted_exact_and_unchanged",
    "runtime_behavior": "native_check_and_smoke_only",
    "xcode_mixed_language": "none",
}
FOLDER_GATES = {
    "abi": "not_claimed_separate_release_approval",
    "api_identity": "unchanged",
    "dynamic_reflection": "none_selected",
    "external_callers": "none",
    "macro_conditional_compilation": "none_selected",
    "module_identity": "SwiftA3Core_unchanged",
    "package_manifest": "unchanged",
    "project_convention": "swiftpm_recursive_target_subfolders",
    "protocol_actor_dispatch": "none_selected",
    "resolved_callers_references": "accepted_exact_logical_edges_unchanged",
    "runtime_behavior": "native_check_and_smoke_only",
    "target_identity": "name_type_path_dependencies_unchanged",
    "type_identity": "module_qualified_names_unchanged",
    "xcode_mixed_language": "none",
}
NONCLAIMS = [
    "Swift compiler facts are pinned to the supplied complete schema-v2 fact pack and Apple Swift 6.3.3",
    "compiler-resolved calls and references do not establish dynamic dispatch, reflection, macro expansion, generated code, or external callers",
    "Xcode projects, mixed-language targets, protocols, actors, dynamic or Objective-C dispatch, macro or conditional compilation, and ABI-sensitive declarations are excluded",
    "native current/after checks prove only the exact accepted SwiftPM package, configuration, products, outputs, and selected target",
    "proposal.md, evidence.json, and scope.json are read-only and grant no mutation, ABI, release, or deployment authority",
]
UNSUPPORTED_PATTERNS = {
    "protocol": re.compile(r"\bprotocol\s+[A-Za-z_]"),
    "actor": re.compile(r"\bactor\s+[A-Za-z_]"),
    "dynamic_or_objc": re.compile(
        r"@objc\b|\bdynamic\b|\bSelector\s*\(|\bNSClassFromString\s*\(|\bperform\s*\("
    ),
    "macro_or_conditional": re.compile(
        r"#if\b|#elseif\b|#externalMacro\b|@attached\b|@freestanding\b|\bmacro\s+[A-Za-z_]"
    ),
    "abi_sensitive": re.compile(
        r"@frozen\b|@inlinable\b|@usableFromInline\b|@_cdecl\b|@_silgen_name\b"
    ),
}


class ProposalError(RuntimeError):
    """A typed refusal that may still replace the terminal artifact bundle."""

    def __init__(self, status: str, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.kind = kind
        self.detail = detail


def _provider() -> Any:
    path = Path(__file__).with_name("swift_semantic_facts.py")
    spec = importlib.util.spec_from_file_location("swift_structure_native_provider", path)
    if spec is None or spec.loader is None:
        raise ProposalError("failed", "semantic_provider_unavailable", "Swift provider cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ProposalError("failed", "invalid_selection", f"{label} is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ProposalError("failed", "invalid_selection", f"{label} is unsafe")
    return value


def _input(root: Path, supplied: Path, label: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    try:
        path = raw.resolve(strict=True)
        path.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not path.is_file() or path.is_symlink():
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is unavailable")
    return path


def _output(root: Path, supplied: Path, consumer: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    path = Path(os.path.abspath(raw))
    allowed = root / "reports" / consumer / "swift"
    try:
        relative = path.relative_to(allowed)
    except ValueError as exc:
        raise ProposalError(
            "failed",
            "unsafe_output_path",
            f"output must stay below reports/{consumer}/swift",
        ) from exc
    if not relative.parts:
        raise ProposalError("failed", "unsafe_output_path", "output must name a run")
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProposalError("failed", "unsafe_output_path", "output traverses a symlink")
    return path


def _read(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("failed", "invalid_upstream_artifact", f"{label} is not an object")
    return payload


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _scope(payload: dict[str, Any], consumer: str) -> dict[str, Any]:
    fields = (
        "status",
        "outcome",
        "failure_kind",
        "message",
        "target",
        "domain",
        "parent",
        "prefix",
        "declarations",
        "caller_impact",
        "reference_impact",
        "api_impact",
        "module_impact",
        "package_impact",
        "target_identity_impact",
        "type_identity_impact",
        "exact_edits",
        "create_files",
        "exact_moves",
        "target_sources_after",
        "test_surface",
        "candidate_verdict_sha256",
        "proposal_verdict_sha256",
        "nonclaims",
    )
    return {
        "schema_version": SCHEMA,
        "skill": consumer,
        "language": "swift",
        "read_only": True,
        "mutation_authorized": False,
        "source_mutations": 0,
        **{field: payload[field] for field in fields if field in payload},
    }


def _replace(output: Path, payload: dict[str, Any], proposal: str, consumer: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.parent / f".{output.name}.stage-{uuid.uuid4().hex}"
    backup = output.parent / f".{output.name}.old-{uuid.uuid4().hex}"
    staged.mkdir()
    try:
        _atomic(staged / "evidence.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _atomic(
            staged / "scope.json",
            json.dumps(_scope(payload, consumer), indent=2, sort_keys=True) + "\n",
        )
        _atomic(staged / "proposal.md", proposal)
        if output.exists():
            if output.is_symlink() or not output.is_dir():
                raise ProposalError("failed", "unsafe_output_path", "output is not a safe directory")
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


def _hash_object(payload: dict[str, Any], field: str, kind: str) -> None:
    supplied = payload.get(field)
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if supplied != _canonical(unsigned):
        raise ProposalError("failed", kind, f"{field} does not verify")


def _artifact_hashes(
    root: Path, acceptance: dict[str, Any], supplied: dict[str, Path]
) -> dict[str, str]:
    rows = acceptance.get("artifacts")
    if not isinstance(rows, list) or len(rows) != len(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "artifact binding is incomplete")
    accepted = {
        row.get("kind"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if set(accepted) != set(supplied):
        raise ProposalError("failed", "invalid_accepted_evidence", "accepted artifact set changed")
    hashes: dict[str, str] = {}
    for kind, path in supplied.items():
        row = accepted[kind]
        expected = root / _relative(row.get("path"), f"{kind} path")
        if expected.resolve() != path.resolve():
            raise ProposalError("failed", "invalid_accepted_evidence", f"{kind} path changed")
        digest = _sha256(path)
        if row.get("sha256") != digest:
            raise ProposalError("failed", "artifact_hash_mismatch", f"{kind} hash changed")
        hashes[kind] = digest
    return hashes


def _target(facts: dict[str, Any], target_name: str) -> dict[str, Any]:
    rows = [row for row in facts.get("target_graph", []) if row.get("name") == target_name]
    if len(rows) != 1:
        raise ProposalError("partial", "fact_closure_incomplete", "selected target is ambiguous")
    target = rows[0]
    if (
        target.get("type") != "library"
        or target.get("path") != f"Sources/{target_name}"
        or target.get("target_dependencies") != []
    ):
        raise ProposalError(
            "partial", "unsupported_swift_condition", "only one dependency-free SwiftPM library target is supported"
        )
    return target


def _tool_path(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProposalError("failed", "native_verification_failed", f"{label}: {exc}") from exc
    if not resolved.is_file():
        raise ProposalError("failed", "native_verification_failed", f"{label} is not executable")
    return resolved


def _authority(
    acceptance: dict[str, Any],
    *,
    selected_skill: Path,
    provider_path: Path,
    helper_path: Path,
    swift: Path,
    swiftc: Path,
    swift_format: Path,
    facts: dict[str, Any],
) -> None:
    expected = {
        "selected_skill_sha256": _sha256(selected_skill),
        "semantic_provider_sha256": _sha256(provider_path),
        "structure_helper_sha256": _sha256(helper_path),
        "swift_format_sha256": _sha256(swift_format),
        "swift_sha256": _sha256(swift),
        "swiftc_sha256": _sha256(swiftc),
        "toolchain_sha256": facts.get("identity", {}).get("toolchain_sha256"),
    }
    if acceptance.get("authority") != expected:
        raise ProposalError("failed", "authority_hash_mismatch", "accepted Swift authority changed")
    if expected["toolchain_sha256"] != _canonical(facts.get("tools")):
        raise ProposalError("failed", "fact_pack_invalid", "fact-pack toolchain identity changed")


def _verdicts(
    consumer: str,
    acceptance: dict[str, Any],
    producer_candidate: dict[str, Any],
    facts: dict[str, Any],
    selection: dict[str, Any],
) -> tuple[str, str]:
    candidate = acceptance.get("candidate_verdict")
    proposal = acceptance.get("proposal_verdict")
    if not isinstance(candidate, dict) or not isinstance(proposal, dict):
        raise ProposalError("failed", "human_acceptance_required", "separate verdicts are missing")
    _hash_object(candidate, "candidate_verdict_sha256", "candidate_verdict_hash_mismatch")
    _hash_object(proposal, "proposal_verdict_sha256", "proposal_verdict_hash_mismatch")
    candidate_hash = candidate["candidate_verdict_sha256"]
    proposal_hash = proposal["proposal_verdict_sha256"]
    material = {
        "consumer": consumer,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "producer_candidate": producer_candidate,
    }
    if (
        candidate.get("schema_version") != CANDIDATE_VERDICT_SCHEMA
        or candidate.get("status") != "accepted"
        or not isinstance(candidate.get("reviewer"), str)
        or not candidate["reviewer"].strip()
        or not isinstance(candidate.get("notes"), str)
        or not candidate["notes"].strip()
        or candidate.get("candidate_sha256") != _canonical(material)
    ):
        raise ProposalError("failed", "candidate_acceptance_required", "candidate verdict is stale or incomplete")
    gates = BOUNDARY_GATES if consumer == "propose-boundary" else FOLDER_GATES
    if proposal.get("boundary_verdicts") != gates:
        kind = "swift_boundary_unresolved" if consumer == "propose-boundary" else "swift_folder_boundary_unresolved"
        raise ProposalError("failed", kind, "accepted Swift uncertainty gates are unresolved")
    if (
        proposal.get("schema_version") != PROPOSAL_VERDICT_SCHEMA
        or proposal.get("status") != "accepted"
        or not isinstance(proposal.get("reviewer"), str)
        or not proposal["reviewer"].strip()
        or not isinstance(proposal.get("notes"), str)
        or not proposal["notes"].strip()
        or proposal.get("candidate_verdict_sha256") != candidate_hash
        or proposal.get("proposal_sha256") != _canonical(selection)
    ):
        raise ProposalError("failed", "proposal_acceptance_required", "proposal verdict is stale or incomplete")
    return candidate_hash, proposal_hash


def _same(left: Any, right: Any) -> bool:
    return _canonical(left) == _canonical(right)


def _selected_file(root: Path, value: Any, selected_sources: set[str], label: str) -> Path:
    relative = _relative(value, label)
    path = root / relative
    if relative not in selected_sources or not path.is_file() or path.is_symlink():
        raise ProposalError("partial", "fact_closure_incomplete", f"{label} lacks current compiler coverage")
    return path


def _boundary_plan(
    root: Path,
    selection: dict[str, Any],
    producer: dict[str, Any],
    facts: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if producer.get("status") != "complete" or producer.get("outcome") != "findings-within-complete":
        raise ProposalError("partial", "upstream_not_complete", "omnibus evidence is not complete")
    findings = producer.get("findings")
    matches = [
        row
        for row in findings or []
        if isinstance(row, dict)
        and isinstance(row.get("candidate"), dict)
        and row["candidate"].get("candidate_id") == selection.get("candidate_id")
    ]
    if len(matches) != 1:
        raise ProposalError("failed", "invalid_selection", "accepted omnibus candidate changed")
    finding = matches[0]
    candidate = finding["candidate"]
    scout = finding.get("scout")
    analysis = producer.get("analysis", {}).get("swift", {})
    if (
        candidate.get("language") != "swift"
        or analysis.get("status") != "complete"
        or analysis.get("analyzer") != "swiftc-typecheck-dump-ast"
        or not isinstance(scout, dict)
        or scout.get("bucket") != "confirmed_omnibus"
        or scout.get("candidate_id") != candidate.get("candidate_id")
        or scout.get("file") != candidate.get("file")
    ):
        raise ProposalError("partial", "upstream_not_complete", "Swift omnibus closure is incomplete")
    clusters = [row for row in candidate.get("clusters", []) if row.get("name") == "exports"]
    if len(clusters) != 1:
        raise ProposalError("failed", "invalid_selection", "exact exports cluster is missing")
    names = {str(name).split(".")[-1] for name in clusters[0].get("symbols", [])}
    if names != {"loadExports", "saveExports", "renderExports"}:
        raise ProposalError("failed", "invalid_selection", "exports cluster is not the exact three-method boundary")
    target = _relative(candidate.get("file"), "boundary target")
    selected_sources = set(facts["compiler_details"]["selected_sources"])
    source = _selected_file(root, target, selected_sources, "boundary target")
    declarations = [
        row
        for row in facts["compiler_details"]["all_declarations"]
        if row.get("file") == target
        and row.get("parent") == "DomainOperations"
        and row.get("name") in names
    ]
    if (
        len(declarations) != 3
        or {row.get("name") for row in declarations} != names
        or any(row.get("interface_type") != "(DomainOperations.Type) -> () -> Int" for row in declarations)
    ):
        raise ProposalError("partial", "fact_closure_incomplete", "exact export declarations are ambiguous")
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks: list[dict[str, Any]] = []
    bodies: list[str] = []
    edits: list[dict[str, Any]] = []
    for row in declarations:
        line = row.get("line")
        if not isinstance(line, int) or line < 1 or line > len(lines):
            raise ProposalError("failed", "invalid_selection", "declaration line is invalid")
        text = lines[line - 1]
        match = re.fullmatch(
            rf"  public static func {re.escape(row['name'])}\(\) -> Int \{{ (?P<body>.+) \}}\n?",
            text,
        )
        if match is None:
            raise ProposalError("partial", "unsupported_swift_condition", "export method is not a one-line static value method")
        blocks.append({"line": line, "path": target, "text": text})
        bodies.append(match.group("body"))
        edits.append(
            {
                "after": f"  public static func {row['name']}() -> Int {{ ExportOperations.{row['name']}() }}\n",
                "before": text,
                "expected_occurrences": 1,
                "path": target,
            }
        )
    new_path = f"{PurePosixPath(target).parent.as_posix()}/ExportOperations.swift"
    if (root / new_path).exists():
        raise ProposalError("failed", "invalid_selection", "new internal boundary path already exists")
    contents = "internal enum ExportOperations {\n" + "".join(
        f"  internal static func {row['name']}() -> Int {{ {body} }}\n"
        for row, body in zip(declarations, bodies, strict=True)
    ) + "}\n"
    declaration_ids = {row["semantic_id"] for row in declarations}
    callers = [
        row
        for row in facts["compiler_details"]["resolved_calls"]
        if row.get("target_semantic_id") in declaration_ids
    ]
    if len(callers) != 3 or {row.get("target_semantic_id") for row in callers} != declaration_ids:
        raise ProposalError("partial", "fact_closure_incomplete", "exact resolved caller closure is incomplete")
    target_row = _target(facts, facts["identity"]["target_name"])
    expected = {
        "api_impact": {
            "compatibility_shims": True,
            "existing_public_signatures_changed": False,
            "new_type": f"{facts['identity']['target_name']}.ExportOperations",
            "new_type_access": "internal",
        },
        "caller_impact": callers,
        "candidate_id": candidate["candidate_id"],
        "create_files": [{"contents": contents, "path": new_path}],
        "declarations": declarations,
        "domain": "exports",
        "exact_edits": edits,
        "exact_moves": [],
        "module_impact": {
            "after": facts["identity"]["target_name"],
            "before": facts["identity"]["target_name"],
            "changed": False,
        },
        "package_impact": {
            "manifest_changed": False,
            "package_sha256": _sha256(root / "Package.swift"),
        },
        "source_blocks": blocks,
        "target": target,
        "target_sources_after": sorted([*target_row["sources"], PurePosixPath(new_path).relative_to(target_row["path"]).as_posix()]),
        "test_surface": ["Sources/SwiftA3Check/main.swift", "Sources/SwiftA3Smoke/main.swift"],
    }
    if not _same(selection, expected):
        raise ProposalError("failed", "invalid_selection", "accepted boundary proposal no longer derives exactly")
    plan = dict(expected)
    plan["reference_impact"] = []
    return plan, finding


def _logical(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": row["display_name"],
        "interface_type": row["interface_type"],
        "kind": row["kind"],
        "name": row["name"],
        "parent": row["parent"],
        "top_level": row["top_level"],
    }


def _folder_plan(
    root: Path,
    selection: dict[str, Any],
    producer: dict[str, Any],
    facts: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if producer.get("schema_version") != 1 or producer.get("status") != "complete" or producer.get("outcome") != "drift-found":
        raise ProposalError("partial", "upstream_not_complete", "topology evidence is not complete")
    analysis = producer.get("analysis", {}).get("swift", {})
    if analysis.get("status") != "complete" or analysis.get("source_preserved") is not True:
        raise ProposalError("partial", "upstream_not_complete", "Swift topology closure is incomplete")
    matches = [
        row
        for row in producer.get("findings", [])
        if isinstance(row, dict) and row.get("evidence_sha256") == selection.get("finding_evidence_sha256")
    ]
    if len(matches) != 1:
        raise ProposalError("failed", "invalid_selection", "accepted topology finding changed")
    finding = matches[0]
    target_name = facts["identity"]["target_name"]
    target_root = f"Sources/{target_name}"
    files = finding.get("files")
    if (
        finding.get("pattern") != "flat_prefix_cluster"
        or finding.get("language") != "swift"
        or finding.get("file") != target_root
        or finding.get("prefix") != "Billing"
        or finding.get("count") != 4
        or not isinstance(files, list)
        or len(files) != 4
        or files != sorted(files)
        or any(PurePosixPath(path).parent.as_posix() != target_root for path in files)
        or {PurePosixPath(path).name for path in files}
        != {"BillingModel.swift", "BillingParser.swift", "BillingTypes.swift", "BillingValidator.swift"}
    ):
        raise ProposalError("failed", "invalid_selection", "topology candidate is not the exact Billing cluster")
    selected_sources = set(facts["compiler_details"]["selected_sources"])
    for path in files:
        _selected_file(root, path, selected_sources, "Billing source")
    declarations = [
        row for row in facts["compiler_details"]["all_declarations"] if row.get("file") in set(files)
    ]
    if not declarations or {row["file"] for row in declarations} != set(files):
        raise ProposalError("partial", "fact_closure_incomplete", "Billing declaration closure is incomplete")
    ids = {row["semantic_id"] for row in declarations}
    callers = [
        row for row in facts["compiler_details"]["resolved_calls"] if row.get("target_semantic_id") in ids
    ]
    references = [
        row for row in facts["compiler_details"]["resolved_references"] if row.get("target_semantic_id") in ids
    ]
    replacements = {path: f"{target_root}/Billing/{PurePosixPath(path).name}" for path in files}
    target_row = _target(facts, target_name)
    target_sources_after = sorted(
        f"Billing/{PurePosixPath(path).name}" if f"{target_root}/{path}" in replacements else path
        for path in target_row["sources"]
    )
    expected = {
        "api_impact": {
            "logical_declarations": sorted((_logical(row) for row in declarations), key=_canonical),
            "public_signatures_changed": False,
            "source_location_only": True,
        },
        "caller_impact": callers,
        "create_files": [],
        "declarations": declarations,
        "exact_edits": [],
        "exact_moves": [{"from": source, "to": destination} for source, destination in replacements.items()],
        "files": files,
        "finding_evidence_sha256": finding["evidence_sha256"],
        "module_impact": {"after": target_name, "before": target_name, "changed": False},
        "package_impact": {
            "manifest_changed": False,
            "package_sha256": _sha256(root / "Package.swift"),
        },
        "parent": finding["file"],
        "prefix": "Billing",
        "project_convention": "swiftpm-recursive-target-subfolders",
        "reference_impact": references,
        "target_identity_impact": {
            "dependencies": target_row["target_dependencies"],
            "name": target_name,
            "path": target_root,
            "type": "library",
            "changed": False,
        },
        "target_sources_after": target_sources_after,
        "test_surface": ["Sources/SwiftA3Check/main.swift", "Sources/SwiftA3Smoke/main.swift"],
        "type_identity_impact": {
            "module": target_name,
            "qualified_types": sorted(row["name"] for row in declarations if row["kind"] in {5, 10, 11, 23}),
            "changed": False,
        },
    }
    if not _same(selection, expected):
        raise ProposalError("failed", "invalid_selection", "accepted folder proposal no longer derives exactly")
    plan = dict(expected)
    plan["target"] = finding["file"]
    return plan, finding


def _validate_acceptance(
    root: Path,
    consumer: str,
    acceptance: dict[str, Any],
    producer_path: Path,
    facts_path: Path,
    producer: dict[str, Any],
    facts: dict[str, Any],
    *,
    selected_skill: Path,
    provider_path: Path,
    helper_path: Path,
    swift: Path,
    swiftc: Path,
    swift_format: Path,
    provider: Any,
) -> tuple[dict[str, Any], dict[str, str], str, str]:
    _hash_object(acceptance, "acceptance_sha256", "acceptance_hash_mismatch")
    if (
        acceptance.get("schema_version") != ACCEPTANCE_SCHEMA
        or acceptance.get("consumer") != consumer
        or acceptance.get("language") != "swift"
        or acceptance.get("target_name") != facts.get("identity", {}).get("target_name")
        or acceptance.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
        or acceptance.get("source_manifest_sha256") != facts.get("source_manifest_sha256")
    ):
        raise ProposalError("failed", "invalid_accepted_evidence", "acceptance identity changed")
    producer_kind = "confirmed-omnibus" if consumer == "propose-boundary" else "lexical-topology"
    artifact_hashes = _artifact_hashes(
        root,
        acceptance,
        {producer_kind: producer_path, "swift-semantic-facts-v2": facts_path},
    )
    _authority(
        acceptance,
        selected_skill=selected_skill,
        provider_path=provider_path,
        helper_path=helper_path,
        swift=swift,
        swiftc=swiftc,
        swift_format=swift_format,
        facts=facts,
    )
    try:
        provider.load_fact_pack(facts_path, root, facts["identity"]["target_name"], [])
    except (OSError, RuntimeError, ValueError) as exc:
        kind = getattr(exc, "kind", "fact_pack_invalid")
        raise ProposalError("partial", kind, str(exc)) from exc
    if (
        facts.get("schema_version") != "swift-semantic-facts-v2"
        or facts.get("status") != "complete"
        or facts.get("source_preserved") is not True
        or facts.get("semantic", {}).get("state") != "complete"
        or facts.get("compiler", {}).get("selected_sources_compiled") is not True
        or facts.get("identity", {}).get("configuration") not in {"debug", "release"}
    ):
        raise ProposalError("partial", "fact_closure_incomplete", "current Swift fact pack is incomplete")
    _target(facts, facts["identity"]["target_name"])
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise ProposalError("failed", "invalid_selection", "accepted proposal selection is missing")
    plan, producer_candidate = (
        _boundary_plan(root, selection, producer, facts)
        if consumer == "propose-boundary"
        else _folder_plan(root, selection, producer, facts)
    )
    candidate_hash, proposal_hash = _verdicts(
        consumer, acceptance, producer_candidate, facts, selection
    )
    plan["candidate_verdict_sha256"] = candidate_hash
    plan["proposal_verdict_sha256"] = proposal_hash
    return plan, artifact_hashes, candidate_hash, proposal_hash


def _unsupported(root: Path, plan: dict[str, Any], target_name: str) -> None:
    for path in root.rglob("*"):
        if path.name.endswith((".xcodeproj", ".xcworkspace")) or path.name == "project.pbxproj":
            raise ProposalError("partial", "unsupported_swift_condition", "Xcode project/workspace is outside this proposal contract")
    target_root = root / f"Sources/{target_name}"
    mixed = {
        path.suffix.lower()
        for path in target_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp", ".m", ".mm"}
    }
    if mixed:
        raise ProposalError("partial", "unsupported_swift_condition", "mixed-language target is outside this proposal contract")
    impacted = {row["file"] for row in plan["declarations"]}
    impacted.update(row.get("source") for row in plan.get("caller_impact", []))
    impacted.update(row.get("source") for row in plan.get("reference_impact", []))
    impacted.update(plan.get("test_surface", []))
    for relative in sorted(path for path in impacted if isinstance(path, str)):
        path = root / _relative(relative, "impacted Swift source")
        if not path.is_file() or path.is_symlink():
            raise ProposalError("partial", "fact_closure_incomplete", f"impacted source is unavailable: {relative}")
        text = path.read_text(encoding="utf-8")
        matched = next((name for name, pattern in UNSUPPORTED_PATTERNS.items() if pattern.search(text)), None)
        conformance = re.search(r"\b(?:struct|class|enum|actor)\s+[A-Za-z_][^\n{]*:\s*[^\n{]+", text)
        if matched or conformance:
            condition = matched or "protocol_conformance"
            raise ProposalError(
                "partial",
                "unsupported_swift_condition",
                f"{condition} appears in impacted source: {relative}",
            )


def _copy_host(root: Path, destination: Path) -> None:
    shutil.copytree(
        root,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", ".build", ".swiftpm", ".agents", ".engineering", "reports"
        ),
    )


def _apply(root: Path, plan: dict[str, Any]) -> None:
    for row in plan["exact_moves"]:
        source = root / _relative(row.get("from"), "move source")
        destination = root / _relative(row.get("to"), "move destination")
        if not source.is_file() or source.is_symlink() or destination.exists():
            raise ProposalError("failed", "disposable_plan_mismatch", f"move changed: {row.get('from')}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for row in plan["exact_edits"]:
        path = root / _relative(row.get("path"), "edit path")
        before = row.get("before")
        after = row.get("after")
        expected = row.get("expected_occurrences")
        if not path.is_file() or not isinstance(before, str) or not isinstance(after, str) or expected != 1:
            raise ProposalError("failed", "disposable_plan_mismatch", "edit is malformed")
        text = path.read_text(encoding="utf-8")
        if text.count(before) != expected:
            raise ProposalError("failed", "disposable_plan_mismatch", f"edit changed: {row.get('path')}")
        path.write_text(text.replace(before, after), encoding="utf-8")
    for row in plan["create_files"]:
        path = root / _relative(row.get("path"), "created path")
        contents = row.get("contents")
        if path.exists() or not isinstance(contents, str):
            raise ProposalError("failed", "disposable_plan_mismatch", "created file is malformed")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def _collect(
    provider: Any,
    root: Path,
    facts: dict[str, Any],
    *,
    configuration: str,
    swift: Path,
    swiftc: Path,
    swift_format: Path,
    check_product: str,
    expected_check: str,
    smoke_product: str,
    expected_smoke: str,
) -> dict[str, Any]:
    try:
        payload = provider.collect(
            root,
            facts["identity"]["target_name"],
            facts["query_names"],
            configuration=configuration,
            swift=swift,
            swiftc=swiftc,
            swift_format=swift_format,
            check_product=check_product,
            expected_check=expected_check,
            smoke_product=smoke_product,
            expected_smoke=expected_smoke,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProposalError("failed", "native_verification_failed", str(exc)) from exc
    if (
        payload.get("status") != "complete"
        or payload.get("source_preserved") is not True
        or payload.get("semantic", {}).get("state") != "complete"
    ):
        detail = payload.get("failure_detail") or payload.get("failure_kind") or "incomplete provider result"
        raise ProposalError("failed", "native_verification_failed", str(detail))
    return payload


def _native_output(payload: dict[str, Any], identifier: str) -> str:
    rows = [row for row in payload.get("native_checks", []) if row.get("id") == identifier]
    if len(rows) != 1 or rows[0].get("returncode") != 0:
        raise ProposalError("failed", "native_verification_failed", f"{identifier} is incomplete")
    return str(rows[0].get("stdout", "")).strip()


def _current_matches(facts: dict[str, Any], replay: dict[str, Any]) -> None:
    stable = (
        "query_names",
        "source_inventory",
        "source_hashes",
        "source_manifest_sha256",
        "identity",
        "target_graph",
        "semantic",
        "symbols",
        "definition_occurrences",
        "compiler_details",
    )
    changed = [key for key in stable if not _same(facts.get(key), replay.get(key))]
    if changed:
        raise ProposalError(
            "failed",
            "native_verification_failed",
            "disposable current tree does not replay supplied facts: " + ", ".join(changed),
        )


def _target_graph_after(facts: dict[str, Any], after: dict[str, Any], expected_sources: list[str]) -> None:
    expected = json.loads(json.dumps(facts["target_graph"]))
    target_name = facts["identity"]["target_name"]
    next(row for row in expected if row["name"] == target_name)["sources"] = expected_sources
    if not _same(expected, after.get("target_graph")):
        raise ProposalError("failed", "native_verification_failed", "SwiftPM target graph changed")
    identity = after.get("identity", {})
    original = facts["identity"]
    for key in ("package_name", "package_sha256", "tools_version", "target_name", "target_type", "target_path", "configuration"):
        if identity.get(key) != original.get(key):
            raise ProposalError("failed", "native_verification_failed", f"target identity changed: {key}")
    if identity.get("target_sources") != expected_sources:
        raise ProposalError("failed", "native_verification_failed", "selected target sources changed")


def _declaration_key(row: dict[str, Any], path_map: dict[str, str]) -> dict[str, Any]:
    return {
        **_logical(row),
        "file": path_map.get(row["file"], row["file"]),
        "line": row["line"],
        "column": row["column"],
    }


def _edge_key(
    row: dict[str, Any],
    declarations: dict[str, dict[str, Any]],
    path_map: dict[str, str],
) -> dict[str, Any]:
    target = declarations[row["target_semantic_id"]]
    key: dict[str, Any] = {
        "source": path_map.get(row["source"], row["source"]),
        "line": row["line"],
        "column": row["column"],
        "evidence": row["evidence"],
        "target": _declaration_key(target, path_map),
    }
    caller = row.get("containing_caller")
    if isinstance(caller, dict):
        caller_row = declarations[caller["semantic_id"]]
        key["caller"] = _declaration_key(caller_row, path_map)
    return key


def _verify_boundary(plan: dict[str, Any], facts: dict[str, Any], after: dict[str, Any]) -> None:
    original = plan["declarations"]
    names = {row["name"] for row in original}
    replay = [
        row
        for row in after["compiler_details"]["all_declarations"]
        if row.get("file") == plan["target"]
        and row.get("parent") == "DomainOperations"
        and row.get("name") in names
    ]
    if len(replay) != 3:
        raise ProposalError("failed", "native_verification_failed", "compatibility shims are incomplete")
    stable_fields = (
        "semantic_id", "name", "kind", "file", "line", "column", "interface_type", "display_name", "parent", "top_level"
    )
    if {
        tuple(row.get(field) for field in stable_fields) for row in replay
    } != {
        tuple(row.get(field) for field in stable_fields) for row in original
    }:
        raise ProposalError("failed", "native_verification_failed", "original public signatures changed")
    ids = {row["semantic_id"] for row in original}
    callers = [
        row for row in after["compiler_details"]["resolved_calls"] if row.get("target_semantic_id") in ids
    ]
    if not _same(callers, plan["caller_impact"]):
        raise ProposalError("failed", "native_verification_failed", "accepted resolved callers changed")
    new_path = plan["create_files"][0]["path"]
    created = [
        row
        for row in after["compiler_details"]["all_declarations"]
        if row.get("file") == new_path and row.get("parent") == "ExportOperations"
    ]
    if {row.get("name") for row in created} != names:
        raise ProposalError("failed", "native_verification_failed", "internal ExportOperations is incomplete")


def _verify_folder(plan: dict[str, Any], facts: dict[str, Any], after: dict[str, Any]) -> None:
    path_map = {row["from"]: row["to"] for row in plan["exact_moves"]}
    before_declarations = {row["semantic_id"]: row for row in facts["compiler_details"]["all_declarations"]}
    after_declarations = {row["semantic_id"]: row for row in after["compiler_details"]["all_declarations"]}
    expected_declarations = sorted(
        (_declaration_key(row, path_map) for row in plan["declarations"]), key=_canonical
    )
    destinations = set(path_map.values())
    actual_rows = [row for row in after_declarations.values() if row.get("file") in destinations]
    actual_declarations = sorted((_declaration_key(row, {}) for row in actual_rows), key=_canonical)
    if not _same(expected_declarations, actual_declarations):
        raise ProposalError("failed", "native_verification_failed", "moved logical declarations changed")
    expected_ids = {row["semantic_id"] for row in plan["declarations"]}
    after_ids = {row["semantic_id"] for row in actual_rows}
    before_calls = [
        row for row in facts["compiler_details"]["resolved_calls"] if row.get("target_semantic_id") in expected_ids
    ]
    after_calls = [
        row for row in after["compiler_details"]["resolved_calls"] if row.get("target_semantic_id") in after_ids
    ]
    before_refs = [
        row for row in facts["compiler_details"]["resolved_references"] if row.get("target_semantic_id") in expected_ids
    ]
    after_refs = [
        row for row in after["compiler_details"]["resolved_references"] if row.get("target_semantic_id") in after_ids
    ]
    try:
        normalized = (
            sorted((_edge_key(row, before_declarations, path_map) for row in before_calls), key=_canonical),
            sorted((_edge_key(row, after_declarations, {}) for row in after_calls), key=_canonical),
            sorted((_edge_key(row, before_declarations, path_map) for row in before_refs), key=_canonical),
            sorted((_edge_key(row, after_declarations, {}) for row in after_refs), key=_canonical),
        )
    except KeyError as exc:
        raise ProposalError("failed", "native_verification_failed", "logical edge closure changed") from exc
    if not _same(normalized[0], normalized[1]) or not _same(normalized[2], normalized[3]):
        raise ProposalError("failed", "native_verification_failed", "resolved caller/reference edges changed")
    type_names = sorted(row["name"] for row in actual_rows if row["kind"] in {5, 10, 11, 23})
    if type_names != plan["type_identity_impact"]["qualified_types"]:
        raise ProposalError("failed", "native_verification_failed", "module-qualified type identity changed")


def _native(
    root: Path,
    plan: dict[str, Any],
    facts: dict[str, Any],
    provider: Any,
    consumer: str,
    *,
    configuration: str,
    swift: Path,
    swiftc: Path,
    swift_format: Path,
    check_product: str,
    expected_check: str,
    smoke_product: str,
    expected_smoke: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="swift-structure-native-") as temporary:
        base = Path(temporary)
        current_root = base / "current"
        after_root = base / "after"
        _copy_host(root, current_root)
        _copy_host(root, after_root)
        current = _collect(
            provider,
            current_root,
            facts,
            configuration=configuration,
            swift=swift,
            swiftc=swiftc,
            swift_format=swift_format,
            check_product=check_product,
            expected_check=expected_check,
            smoke_product=smoke_product,
            expected_smoke=expected_smoke,
        )
        _current_matches(facts, current)
        _apply(after_root, plan)
        after = _collect(
            provider,
            after_root,
            facts,
            configuration=configuration,
            swift=swift,
            swiftc=swiftc,
            swift_format=swift_format,
            check_product=check_product,
            expected_check=expected_check,
            smoke_product=smoke_product,
            expected_smoke=expected_smoke,
        )
        _target_graph_after(facts, after, plan["target_sources_after"])
        if consumer == "propose-boundary":
            _verify_boundary(plan, facts, after)
        else:
            _verify_folder(plan, facts, after)
        current_check = _native_output(current, "direct-check")
        current_smoke = _native_output(current, "executable-smoke")
        after_check = _native_output(after, "direct-check")
        after_smoke = _native_output(after, "executable-smoke")
        if (current_check, after_check) != (expected_check, expected_check) or (
            current_smoke,
            after_smoke,
        ) != (expected_smoke, expected_smoke):
            raise ProposalError("failed", "native_verification_failed", "native output changed")
        return {
            "current_tree": {
                "status": "complete",
                "disposable": True,
                "semantic_state": current["semantic"]["state"],
                "target_graph_sha256": current["identity"]["target_graph_sha256"],
                "direct_check_stdout": current_check,
                "smoke_stdout": current_smoke,
            },
            "disposable_after_tree": {
                "status": "complete",
                "disposable": True,
                "semantic_state": after["semantic"]["state"],
                "target_graph_sha256": after["identity"]["target_graph_sha256"],
                "direct_check_stdout": after_check,
                "smoke_stdout": after_smoke,
            },
        }


def _source_state(root: Path, facts: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for row in facts.get("source_hashes", []):
        relative = _relative(row.get("path"), "fact source")
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ProposalError("failed", "unexpected_source_mutation", f"fact source changed: {relative}")
        rows[relative] = _sha256(path)
    return rows


def _proposal(payload: dict[str, Any], consumer: str) -> str:
    title = "Swift boundary proposal" if consumer == "propose-boundary" else "Swift folder reorganization proposal"
    lines = [
        "---",
        "language: swift",
        "status: ready_for_human_review",
        "read_only: true",
        "---",
        "",
        f"# {title}",
        "",
        f"Target: `{payload['target']}`",
        "",
        "## Exact accepted scope",
        "",
        f"- Compiler declarations: **{len(payload['declarations'])}**",
        f"- Resolved callers: **{len(payload['caller_impact'])}**",
        f"- Resolved references: **{len(payload['reference_impact'])}**",
        f"- Exact moves: **{len(payload['exact_moves'])}**",
        f"- Exact edits: **{len(payload['exact_edits'])}**",
        f"- Created files: **{len(payload['create_files'])}**",
        "",
        "## Interface depth and compatibility",
        "",
        "- The proposed boundary is internal; existing same-module public signatures remain compatibility shims.",
        "- The folder proposal changes source location only; SwiftPM target, module, type, and API identity remain unchanged.",
        "- Apply only scope.json after separate human mutation approval.",
        "",
        "## Native stop condition",
        "",
        "- Revalidate the exact accepted producer, schema-v2 fact pack, candidate verdict, and proposal verdict.",
        "- Re-run the pinned provider on disposable current and exact after trees.",
        "- Stop on any declaration, caller, reference, target graph, package, tool, check, smoke, or source-preservation mismatch.",
        "",
        "## Nonclaims",
        "",
        *[f"- {item}" for item in NONCLAIMS],
        "",
        "Human approval is still required before any host mutation.",
        "",
    ]
    return "\n".join(lines)


def _failure(consumer: str, error: ProposalError) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "skill": consumer,
        "language": "swift",
        "status": error.status,
        "outcome": "refused",
        "failure_kind": error.kind,
        "message": error.detail,
        "read_only": True,
        "mutation_authorized": False,
        "source_mutations": 0,
        "declarations": [],
        "caller_impact": [],
        "reference_impact": [],
        "exact_moves": [],
        "exact_edits": [],
        "create_files": [],
        "nonclaims": NONCLAIMS,
    }


def main(consumer: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    producer_flag = "--omnibus" if consumer == "propose-boundary" else "--topology"
    parser.add_argument(producer_flag, required=True, type=Path, dest="producer")
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--acceptance", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--configuration", choices=("debug", "release"), default="debug")
    parser.add_argument("--swift", required=True, type=Path)
    parser.add_argument("--swiftc", required=True, type=Path)
    parser.add_argument("--swift-format", required=True, type=Path)
    parser.add_argument("--check-product", required=True)
    parser.add_argument("--expected-check", required=True)
    parser.add_argument("--smoke-product", required=True)
    parser.add_argument("--expected-smoke", required=True)
    args = parser.parse_args(argv)
    if consumer not in {"propose-boundary", "propose-folder-reorganization"}:
        parser.error("unsupported Swift structure consumer")
    try:
        root = args.project_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise ProposalError("failed", "invalid_project_root", "project root is unsafe")
        output = _output(root, args.output_dir, consumer)
    except (OSError, RuntimeError, ProposalError) as exc:
        parser.error(str(exc))
    try:
        producer_path = _input(root, args.producer, "producer")
        facts_path = _input(root, args.facts, "Swift fact pack")
        acceptance_path = _input(root, args.acceptance, "acceptance")
        swift = _tool_path(args.swift, "swift")
        swiftc = _tool_path(args.swiftc, "swiftc")
        swift_format = _tool_path(args.swift_format, "swift-format")
        provider = _provider()
        provider_path = Path(provider.__file__).resolve(strict=True)
        helper_path = Path(__file__).resolve(strict=True)
        selected_skill = Path(sys.argv[0]).resolve(strict=True)
        producer = _read(producer_path, "producer")
        facts = _read(facts_path, "Swift fact pack")
        acceptance = _read(acceptance_path, "acceptance")
        if facts.get("identity", {}).get("target_name") != args.target_name:
            raise ProposalError("failed", "fact_pack_scope_mismatch", "target argument changed")
        plan, artifact_hashes, candidate_hash, proposal_hash = _validate_acceptance(
            root,
            consumer,
            acceptance,
            producer_path,
            facts_path,
            producer,
            facts,
            selected_skill=selected_skill,
            provider_path=provider_path,
            helper_path=helper_path,
            swift=swift,
            swiftc=swiftc,
            swift_format=swift_format,
            provider=provider,
        )
        _unsupported(root, plan, args.target_name)
        before = _source_state(root, facts)
        native = _native(
            root,
            plan,
            facts,
            provider,
            consumer,
            configuration=args.configuration,
            swift=swift,
            swiftc=swiftc,
            swift_format=swift_format,
            check_product=args.check_product,
            expected_check=args.expected_check,
            smoke_product=args.smoke_product,
            expected_smoke=args.expected_smoke,
        )
        after = _source_state(root, facts)
        if before != after:
            raise ProposalError("failed", "unexpected_source_mutation", "host source changed")
        payload = {
            "schema_version": SCHEMA,
            "skill": consumer,
            "language": "swift",
            "status": "ready_for_human_review",
            "outcome": "proposal_ready",
            "failure_kind": "none",
            "read_only": True,
            "mutation_authorized": False,
            "source_mutations": 0,
            **plan,
            "evidence_binding": {
                "acceptance_sha256": acceptance["acceptance_sha256"],
                "artifact_sha256": artifact_hashes,
                "fact_pack_sha256": facts["fact_pack_sha256"],
                "source_manifest_sha256": facts["source_manifest_sha256"],
                "candidate_verdict_sha256": candidate_hash,
                "proposal_verdict_sha256": proposal_hash,
            },
            "native_verification": native,
            "source_preservation": {"verified": True},
            "boundary_verdicts": BOUNDARY_GATES if consumer == "propose-boundary" else FOLDER_GATES,
            "semantic_authority": {
                "schema_version": facts["schema_version"],
                "toolchain_sha256": facts["identity"]["toolchain_sha256"],
                "provider_sha256": _sha256(provider_path),
                "role": "native_verifier_on_disposable_current_and_after_trees",
            },
            "nonclaims": NONCLAIMS,
        }
        unsigned = dict(payload)
        payload["artifact_sha256"] = _canonical(unsigned)
        _replace(output, payload, _proposal(payload, consumer), consumer)
        return 0
    except (OSError, RuntimeError, UnicodeDecodeError, ValueError, ProposalError) as exc:
        error = exc if isinstance(exc, ProposalError) else ProposalError("failed", "consumer_failed", str(exc))
        payload = _failure(consumer, error)
        proposal = (
            "# Swift structure proposal refused\n\n"
            f"Status: `{error.status}`\n\nFailure: `{error.kind}` — {error.detail}\n"
        )
        _replace(output, payload, proposal, consumer)
        return 2


if __name__ == "__main__":
    raise SystemExit("invoke this helper through a selected Swift proposal skill")
