#!/usr/bin/env python3
"""Render one accepted Swift semantic-shadow disposition without redetection."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


GATES = {
    "resolved_members_and_callers": "accepted_exact_selected_target",
    "static_capability_overlap": "accepted_not_equivalence",
    "behavioral_runtime_equivalence": "not_established_no_mutation_authority",
    "overload_default_argument_selection": "accepted_exact",
    "protocol_existential_override_dispatch": "none_selected",
    "closures_dynamic_reflection_objc": "none_selected",
    "actor_global_actor_concurrency": "none_selected",
    "conditional_macros_plugins_generated": "no_selected_dependency",
    "external_callers_package_variants": "none_after_human_review",
    "errors_side_effects_resources_frameworks": "not_established",
    "abi_binary_compatibility": "separate_approval_required",
}
CONSOLIDATION_SHAPES = {
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}
NATIVE_IDS = [
    "swiftpm-dump-package",
    "swiftpm-describe",
    "swiftpm-build",
    "compiler-parse",
    "swift-format-lint",
    "direct-check",
    "executable-smoke",
    "compiler-ast",
]
EXPECTED_CAPABILITIES = {
    "declaration_identity": True,
    "default_arguments": True,
    "direct_calls": True,
    "direct_references": True,
    "literal_property_writes": True,
    "overload_selection": True,
    "static_function_bodies": True,
}


class ProposalError(RuntimeError):
    """A classified terminal refusal."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _provider() -> Any:
    candidates = [
        parent / "_swift-semantic-readonly" / "swift_semantic_facts.py"
        for parent in Path(__file__).resolve().parents
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Swift semantic provider is missing")
    spec = importlib.util.spec_from_file_location("swift_unify_semantic_facts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Swift semantic provider cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROVIDER = _provider()


def _canonical(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(rendered.encode()).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProposalError("evidence_unavailable", f"{label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("evidence_invalid", f"{label} must be a JSON object")
    return payload


def _safe_file(root: Path, supplied: Path, label: str) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ProposalError("unsafe_path", f"{label} must stay inside project root") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ProposalError("unsafe_path", f"{label} cannot traverse a symbolic link")
    if not candidate.is_file():
        raise ProposalError("evidence_unavailable", f"{label} is unavailable")
    return candidate


def _safe_output(root: Path, supplied: Path) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(candidate))
    allowed = root / "reports/unify-shadows/swift"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ProposalError(
            "unsafe_output", "output must stay beneath reports/unify-shadows/swift"
        ) from exc
    if not relative.parts:
        raise ProposalError("unsafe_output", "output must name one bounded job")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ProposalError("unsafe_output", "output cannot traverse a symbolic link")
    return output


def _atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace(output: Path, files: dict[str, str | dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output.name}.staged-", dir=output.parent))
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    try:
        for name, value in files.items():
            text = (
                json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
                if isinstance(value, dict)
                else value
            )
            _atomic(staged / name, text)
        if output.exists():
            output.replace(backup)
        staged.replace(output)
        shutil.rmtree(backup, ignore_errors=True)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise


def _validate_acceptance(
    root: Path,
    path: Path,
    facts_path: Path,
    analysis_path: Path,
) -> dict[str, Any]:
    accepted = _json(path, "Swift unify acceptance")
    unsigned = dict(accepted)
    supplied = unsigned.pop("acceptance_sha256", None)
    if (
        accepted.get("schema_version") != "swift-unify-shadows-acceptance-v1"
        or accepted.get("language") != "swift"
        or accepted.get("status") != "accepted"
        or accepted.get("consumer") != "unify-shadows"
        or supplied != _canonical(unsigned)
        or not isinstance(accepted.get("reviewer"), str)
        or not accepted["reviewer"].strip()
        or not isinstance(accepted.get("notes"), str)
        or not accepted["notes"].strip()
    ):
        raise ProposalError("acceptance_invalid", "fresh hash-bound acceptance is required")
    if accepted.get("boundary_verdicts") != GATES:
        raise ProposalError("acceptance_invalid", "every Swift boundary verdict is required")
    if (
        accepted.get("facts") != facts_path.relative_to(root).as_posix()
        or accepted.get("facts_sha256") != _file_hash(facts_path)
        or accepted.get("analysis") != analysis_path.relative_to(root).as_posix()
        or accepted.get("analysis_sha256") != _file_hash(analysis_path)
    ):
        raise ProposalError("artifact_hash_mismatch", "accepted facts or analysis changed")
    provider_path = Path(PROVIDER.__file__).resolve()
    authority = accepted.get("authority")
    if authority != {
        "provider_sha256": _file_hash(provider_path),
        "proposer_sha256": _file_hash(Path(__file__).resolve()),
    }:
        raise ProposalError("authority_stale", "accepted provider or proposer changed")
    return accepted


def _finding(analysis: dict[str, Any], accepted: dict[str, Any]) -> dict[str, Any]:
    if (
        analysis.get("schema_version") != "swift-semantic-duplication-v1"
        or analysis.get("language") != "swift"
        or analysis.get("status") != "complete"
        or analysis.get("failure_kind") is not None
        or analysis.get("read_only") is not True
    ):
        raise ProposalError("analysis_incomplete", "complete accepted duplication analysis is required")
    matches = [
        row
        for row in analysis.get("findings", [])
        if isinstance(row, dict)
        and row.get("candidate_id") == accepted.get("candidate_id")
        and row.get("candidate_sha256") == accepted.get("candidate_sha256")
    ]
    if len(matches) != 1:
        raise ProposalError("selection_invalid", "acceptance must select one exact finding")
    finding = matches[0]
    if finding.get("human_verdict") != "accepted" or finding.get("verdict") != accepted.get(
        "upstream_verdict"
    ):
        raise ProposalError("selection_invalid", "upstream human verdict changed")
    reconstructed = dict(finding)
    claimed = reconstructed.pop("candidate_sha256", None)
    reconstructed.pop("verdict", None)
    reconstructed.pop("review_notes", None)
    reconstructed["human_verdict"] = "required"
    if claimed != _canonical(reconstructed):
        raise ProposalError("candidate_hash_mismatch", "reviewed candidate hash does not verify")
    return finding


def _compatible(upstream: str, decision: str) -> str:
    if upstream == "consolidate_candidate" and decision in {
        *CONSOLIDATION_SHAPES,
        "keep_separate_document_why",
    }:
        return decision
    if upstream == "keep_separate_document_why" and decision == upstream:
        return decision
    if upstream == "not_equivalent" and decision == "not_equivalent_documented":
        return decision
    raise ProposalError(
        "verdict_incompatible", "downstream disposition cannot strengthen the upstream verdict"
    )


def _validate_facts(
    root: Path,
    facts_path: Path,
    accepted: dict[str, Any],
    finding: dict[str, Any],
) -> dict[str, Any]:
    functions = finding.get("functions")
    if not isinstance(functions, list) or len(functions) != 2:
        raise ProposalError("selection_invalid", "one exact two-function lead is required")
    queries = {
        value
        for function in functions
        for value in [
            function.get("name"),
            function.get("return_type"),
            *function.get("resolved_callees", []),
            *(row.get("name") for row in function.get("production_callers", [])),
        ]
        if isinstance(value, str) and value
    }
    try:
        facts = PROVIDER.load_fact_pack(
            facts_path, root, accepted.get("target_name", ""), sorted(queries)
        )
    except PROVIDER.SwiftFactError as exc:
        raise ProposalError(exc.kind, str(exc)) from exc
    native = facts.get("native_checks")
    if (
        facts.get("status") != "complete"
        or facts.get("failure_kind") is not None
        or facts.get("read_only") is not True
        or facts.get("source_preserved") is not True
        or facts.get("semantic", {}).get("state") != "complete"
        or facts.get("semantic", {}).get("capabilities") != EXPECTED_CAPABILITIES
        or facts.get("compiler", {}).get("fresh_scratch") is not True
        or facts.get("compiler", {}).get("selected_sources_compiled") is not True
        or not isinstance(native, list)
        or [row.get("id") for row in native] != NATIVE_IDS
        or any(row.get("returncode") != 0 for row in native)
    ):
        raise ProposalError("native_evidence_invalid", "complete A3 native evidence is required")
    if (
        facts.get("fact_pack_sha256") != accepted.get("fact_pack_sha256")
        or facts.get("source_manifest_sha256") != accepted.get("source_manifest_sha256")
    ):
        raise ProposalError("artifact_hash_mismatch", "accepted fact identity changed")
    return facts


def _one(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ProposalError("semantic_join_ambiguous", f"{label} must resolve exactly once")
    return rows[0]


def _scope(facts: dict[str, Any], finding: dict[str, Any], decision: str) -> dict[str, Any]:
    symbols = facts.get("symbols", [])
    occurrences = facts.get("definition_occurrences", [])
    roles = {row.get("path"): row.get("role") for row in facts.get("source_inventory", [])}
    bodies = facts.get("compiler_details", {}).get("function_bodies", [])
    members: list[dict[str, Any]] = []
    caller_sets: list[set[str]] = []
    body_rows: list[dict[str, Any]] = []
    for member in finding["functions"]:
        definition = _one(
            [
                row
                for row in symbols
                if row.get("semantic_id") == member.get("semantic_id")
                and row.get("name") == member.get("name")
                and row.get("file") == member.get("file")
                and row.get("line") == member.get("line")
                and row.get("end_line") == member.get("end_line")
                and row.get("top_level") is True
                and row.get("role") == "selected-production"
            ],
            f'definition {member.get("name")}',
        )
        body = _one(
            [row for row in bodies if row.get("semantic_id") == definition["semantic_id"]],
            f'body facts {member.get("name")}',
        )
        producer_callers = member.get("production_callers")
        if not isinstance(producer_callers, list) or not producer_callers:
            raise ProposalError("caller_evidence_ambiguous", "each member needs production callers")
        resolved_callers: list[dict[str, Any]] = []
        for expected in producer_callers:
            caller = _one(
                [
                    row
                    for row in symbols
                    if row.get("semantic_id") == expected.get("semantic_id")
                    and row.get("name") == expected.get("name")
                    and row.get("file") == expected.get("path")
                    and row.get("line") == expected.get("line")
                    and row.get("top_level") is True
                    and row.get("role") == "selected-production"
                ],
                f'caller {expected.get("name")}',
            )
            callsites = [
                row
                for row in occurrences
                if definition["semantic_id"] in row.get("definition_semantic_ids", [])
                and row.get("source") == caller["file"]
                and caller["line"] < row.get("line", 0) <= caller["end_line"]
                and roles.get(row.get("source")) == "selected-production"
            ]
            if not callsites:
                raise ProposalError("caller_evidence_mismatch", "resolved caller has no fact callsite")
            resolved_callers.append({"caller": caller, "occurrences": callsites})
        expected_ids = {row.get("semantic_id") for row in producer_callers}
        actual_ids = {row["caller"]["semantic_id"] for row in resolved_callers}
        if expected_ids != actual_ids:
            raise ProposalError("caller_evidence_mismatch", "producer and fact callers diverged")
        caller_sets.append(actual_ids)
        body_rows.append(body)
        members.append({"definition": definition, "resolved_callers": resolved_callers})
    if caller_sets[0] & caller_sets[1]:
        raise ProposalError("caller_evidence_ambiguous", "selected caller sets must be distinct")
    callee_ids = [set(row.get("direct_call_target_ids", [])) for row in body_rows]
    if not callee_ids[0] or callee_ids[0] != callee_ids[1]:
        raise ProposalError("static_shape_mismatch", "selected resolved callee sets changed")
    callee_names = sorted(
        {
            row["name"]
            for row in symbols
            if row.get("semantic_id") in callee_ids[0]
        }
    )
    expected_callees = [sorted(row.get("resolved_callees", [])) for row in finding["functions"]]
    if expected_callees != [callee_names, callee_names]:
        raise ProposalError("static_shape_mismatch", "accepted resolved callee names changed")
    overloads = [
        row
        for body in body_rows
        for row in body.get("selected_overloads", [])
    ]
    selected = {
        _canonical(
            {
                "declaration": row.get("selected_declaration"),
                "interface_type": row.get("selected_interface_type"),
            }
        ): {
            **row.get("selected_declaration", {}),
            "interface_type": row.get("selected_interface_type"),
        }
        for row in overloads
    }
    if len(selected) != 1 or len(overloads) != 2:
        raise ProposalError("overload_evidence_mismatch", "one shared selected overload is required")
    return_shape = finding.get("return_shape")
    if (
        return_shape != {"type": "Statement", "fields": ["label", "total"]}
        or len(finding.get("resolved_constructor_ids", [])) != 1
    ):
        raise ProposalError("static_shape_mismatch", "accepted constructor or return shape changed")
    static_shape = {
        "return_shape": return_shape,
        "resolved_constructor_ids": finding["resolved_constructor_ids"],
        "shared_resolved_callee_ids": sorted(callee_ids[0]),
        "shared_resolved_callees": callee_names,
        "selected_initializer_overload": next(iter(selected.values())),
    }
    return {
        "schema_version": "swift-unify-shadows-scope-v1",
        "language": "swift",
        "status": "complete",
        "read_only": True,
        "mutation_authorized": False,
        "source_mutations": 0,
        "finding_id": finding["candidate_id"],
        "upstream_verdict": finding["verdict"],
        "selected_shape": decision,
        "members": members,
        "caller_impact": [row for member in members for row in member["resolved_callers"]],
        "static_shape": static_shape,
        "boundary_verdicts": GATES,
        "human_approval_required": True,
    }


def _outcome(decision: str) -> str:
    if decision == "keep_separate_document_why":
        return "keep_separate_documented"
    if decision == "not_equivalent_documented":
        return decision
    return "proposal_ready"


def _markdown(evidence: dict[str, Any], scope: dict[str, Any]) -> str:
    lines = [
        "# Swift semantic-shadow disposition",
        "",
        f"Outcome: `{evidence['outcome']}`; selected shape: `{scope['selected_shape']}`.",
        "",
        "## Exact definitions and selected-target callers",
        "",
    ]
    for member in scope["members"]:
        definition = member["definition"]
        lines.append(
            f"- `{definition['name']}` / `{definition['interface_type']}` at "
            f"`{definition['file']}:{definition['line']}`"
        )
        for caller in member["resolved_callers"]:
            symbol = caller["caller"]
            sites = ", ".join(
                f"{row['source']}:{row['line']}:{row['column']}"
                for row in caller["occurrences"]
            )
            lines.append(f"  - `{symbol['name']}` at `{sites}`")
    lines.extend(["", "## Disposition", ""])
    if evidence["outcome"] == "proposal_ready":
        lines.append(
            "Investigate only the accepted shape after characterization and separate source-"
            "mutation approval; migrate callers before deleting either definition."
        )
    elif evidence["outcome"] == "keep_separate_documented":
        lines.append("Keep both definitions and caller paths separate; no consolidation is authorized.")
    else:
        lines.append("Document the reviewed non-equivalence; no consolidation is authorized.")
    lines.extend(
        [
            "",
            "## Stop conditions and non-claims",
            "",
            "- Static return, constructor, callee, overload, and caller facts are not behavioral equivalence.",
            "- External callers, dynamic/Objective-C/protocol dispatch, concurrency, generated variants, resources, side effects, and ABI remain human-owned.",
            "- The native check and smoke are the accepted current baseline, not after-tree proof.",
            "- This artifact is read-only and grants no source mutation authority.",
            "",
        ]
    )
    return "\n".join(lines)


def _refusal(error: ProposalError) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = {
        "schema_version": "swift-unify-shadows-evidence-v1",
        "language": "swift",
        "status": "refused",
        "outcome": "refused",
        "failure_kind": error.kind,
        "detail": error.detail,
        "read_only": True,
        "source_mutations": 0,
    }
    scope = {
        "schema_version": "swift-unify-shadows-scope-v1",
        "language": "swift",
        "status": "refused",
        "outcome": "refused",
        "failure_kind": error.kind,
        "read_only": True,
        "mutation_authorized": False,
        "source_mutations": 0,
        "members": [],
        "caller_impact": [],
        "static_shape": {},
    }
    report = (
        "# Swift semantic-shadow disposition refused\n\n"
        f"Failure: `{error.kind}` — {error.detail}\n\nNo Swift source was changed.\n"
    )
    return evidence, scope, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    output: Path | None = None
    try:
        output = _safe_output(root, args.output_dir)
        facts_path = _safe_file(root, args.facts, "Swift fact pack")
        analysis_path = _safe_file(root, args.analysis, "Swift duplication analysis")
        acceptance_path = _safe_file(root, args.acceptance, "Swift unify acceptance")
        accepted = _validate_acceptance(
            root, acceptance_path, facts_path, analysis_path
        )
        analysis = _json(analysis_path, "Swift duplication analysis")
        finding = _finding(analysis, accepted)
        decision = _compatible(finding["verdict"], accepted.get("decision", ""))
        facts = _validate_facts(root, facts_path, accepted, finding)
        if (
            analysis.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
            or analysis.get("source_hashes") != facts.get("source_hashes")
        ):
            raise ProposalError("artifact_hash_mismatch", "analysis and fact pack diverged")
        scope = _scope(facts, finding, decision)
        scope["artifact_sha256"] = _canonical(scope)
        evidence = {
            "schema_version": "swift-unify-shadows-evidence-v1",
            "language": "swift",
            "status": "complete",
            "outcome": _outcome(decision),
            "failure_kind": None,
            "read_only": True,
            "source_mutations": 0,
            "consolidation_shape": decision,
            "fact_pack_sha256": facts["fact_pack_sha256"],
            "source_manifest_sha256": facts["source_manifest_sha256"],
            "native_checks": facts["native_checks"],
            "upstream": {
                "facts": accepted["facts"],
                "facts_sha256": accepted["facts_sha256"],
                "analysis": accepted["analysis"],
                "analysis_sha256": accepted["analysis_sha256"],
                "acceptance": acceptance_path.relative_to(root).as_posix(),
                "acceptance_sha256": _file_hash(acceptance_path),
            },
            "human_authority": accepted,
            "scope_sha256": _canonical(scope),
            "nonclaims": [
                "static capability overlap is not behavioral or runtime equivalence",
                "external callers, variants, side effects, and ABI are not established",
                "the disposition grants no source mutation authority",
            ],
        }
        evidence["artifact_sha256"] = _canonical(evidence)
        _replace(
            output,
            {
                "proposal.md": _markdown(evidence, scope),
                "evidence.json": evidence,
                "scope.json": scope,
            },
        )
        return 0
    except (OSError, RuntimeError, ProposalError) as exc:
        error = exc if isinstance(exc, ProposalError) else ProposalError("consumer_failed", str(exc))
        if output is not None:
            evidence, scope, report = _refusal(error)
            _replace(
                output,
                {"proposal.md": report, "evidence.json": evidence, "scope.json": scope},
            )
        print(f"propose_swift.py: {error.kind}: {error.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
