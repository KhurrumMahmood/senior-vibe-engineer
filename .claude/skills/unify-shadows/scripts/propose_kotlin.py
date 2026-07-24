#!/usr/bin/env python3
"""Render one read-only Kotlin shadow proposal from accepted semantic facts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("kotlin_accepted_evidence.py")]
    candidates.extend(
        parent / "_kotlin-semantic" / "kotlin_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("kotlin_unify_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _normalized_body(source: Any) -> str:
    return re.sub(r"\s+", " ", source if isinstance(source, str) else "").strip()


def _exact_lead(validated: dict[str, Any]) -> dict[str, Any]:
    facts, lead = validated["facts"], validated["lead"]
    if (
        lead.get("classification")
        != "review_required_resolved_contract_and_body_shape_lead"
        or lead.get("human_verdict") != "required"
        or len(lead.get("functions", [])) != 2
    ):
        raise EVIDENCE.EvidenceError(
            "partial",
            "lead_invalid",
            "selected lead must contain exactly two review-required Kotlin functions",
        )
    definitions: list[dict[str, Any]] = []
    caller_sets: list[list[dict[str, Any]]] = []
    for member in lead["functions"]:
        matches = [
            row
            for row in facts.get("declarations", [])
            if row.get("role") == "source"
            and row.get("kind") == "function"
            and row.get("fq_name") == member.get("fq_name")
            and row.get("signature") == member.get("signature")
            and row.get("path") == member.get("path")
            and row.get("line") == member.get("line")
        ]
        if len(matches) != 1:
            raise EVIDENCE.EvidenceError(
                "partial",
                "definition_ambiguous",
                "each accepted member must resolve to one exact production definition",
            )
        definition = matches[0]
        if (
            definition.get("override")
            or definition.get("extension_receiver") is not None
            or not definition.get("body")
        ):
            raise EVIDENCE.EvidenceError(
                "partial",
                "definition_unsupported",
                "override, extension, or bodyless definitions cannot be proposed",
            )
        body = _normalized_body(definition["body"])
        if hashlib.sha256(body.encode()).hexdigest() != lead.get("body_sha256"):
            raise EVIDENCE.EvidenceError(
                "partial", "body_shape_mismatch", "accepted normalized body hash changed"
            )
        calls = [
            {
                "path": row["path"],
                "line": row["line"],
                "source": row.get("source"),
                "caller": row.get("caller"),
                "target_signature": row.get("target_signature"),
            }
            for row in facts.get("calls", [])
            if row.get("role") == "source"
            and row.get("resolved")
            and row.get("target_signature") == definition["signature"]
        ]
        producer_calls = member.get("direct_caller_contexts")
        projected = [
            {"path": row["path"], "line": row["line"], "caller": row["caller"]}
            for row in calls
        ]
        if not calls or projected != producer_calls:
            raise EVIDENCE.EvidenceError(
                "partial",
                "caller_evidence_mismatch",
                "accepted caller contexts must match exact resolved production calls",
            )
        definitions.append(definition)
        caller_sets.append(calls)
    if definitions[0]["signature"] == definitions[1]["signature"]:
        raise EVIDENCE.EvidenceError(
            "partial", "definition_ambiguous", "two distinct function signatures are required"
        )
    caller_names = [
        {
            row["caller"]["fq_name"]
            for row in calls
            if isinstance(row.get("caller"), dict) and row["caller"].get("fq_name")
        }
        for calls in caller_sets
    ]
    if any(not names for names in caller_names) or caller_names[0] & caller_names[1]:
        raise EVIDENCE.EvidenceError(
            "partial",
            "caller_evidence_ambiguous",
            "accepted definitions require distinct resolved production callers",
        )
    return {
        "id": lead["id"],
        "body_sha256": lead["body_sha256"],
        "definitions": definitions,
        "callers": caller_sets,
    }


def _proposal(payload: dict[str, Any]) -> str:
    shape = payload["consolidation_shape"]
    lines = [
        "# Kotlin semantic-shadow proposal",
        "",
        f"Outcome: `{payload['outcome']}`; human-selected shape: `{shape}`.",
        "",
        "## Exact definitions and resolved callers",
        "",
    ]
    for member in payload["scope"]["members"]:
        definition = member["definition"]
        lines.append(
            f"- `{definition['fq_name']}` / `{definition['signature']}` at "
            f"`{definition['path']}:{definition['line']}`"
        )
        lines.extend(
            f"  - `{call['caller']['fq_name']}` at `{call['path']}:{call['line']}`"
            for call in member["resolved_callers"]
        )
    lines.extend(["", "## Human-selected disposition", ""])
    if shape == "keep_separate_document_why":
        lines.append(
            "Keep both definitions and caller paths separate; document their independent "
            "ownership. No consolidation or caller-move plan is authorized."
        )
    else:
        lines.append(
            f"Investigate only the accepted `{shape}` shape after characterization tests and "
            "separate source-mutation approval. Sequence characterization, the smallest shared "
            "seam or survivor, caller migration, and deletion only after native parity."
        )
    lines.extend(
        [
            "",
            "## Stop conditions and non-claims",
            "",
            "- Static signature and body shape are not runtime or behavioral equivalence.",
            "- Stop on overload ambiguity, callable references, reflection, delegates, generated "
            "or KAPT/KSP code, Gradle variants, Java/external callers, or JVM ABI change.",
            "- The accepted native test/smoke baseline is evidence to preserve, not proof that "
            "consolidation is safe.",
            "- This artifact is read-only and grants no mutation authority.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "unify-shadows")
        validated = EVIDENCE.validate_duplication_acceptance(
            root,
            facts_path=args.facts,
            analysis_path=args.analysis,
            acceptance_path=args.acceptance,
        )
        exact = _exact_lead(validated)
        shape = validated["acceptance"]["decision"]
        members = [
            {"definition": definition, "resolved_callers": callers}
            for definition, callers in zip(
                exact["definitions"], exact["callers"], strict=True
            )
        ]
        scope = {
            "schema_version": "kotlin-unify-shadows-scope-v1",
            "language": "kotlin",
            "status": "complete",
            "read_only": True,
            "source_mutations": 0,
            "finding_id": exact["id"],
            "selected_shape": shape,
            "body_sha256": exact["body_sha256"],
            "members": members,
            "boundary_verdicts": validated["acceptance"]["boundary_verdicts"],
            "human_approval_required": True,
        }
        evidence = {
            "schema_version": "kotlin-unify-shadows-evidence-v1",
            "language": "kotlin",
            "status": "complete",
            "outcome": (
                "keep_separate_documented"
                if shape == "keep_separate_document_why"
                else "proposal_ready"
            ),
            "read_only": True,
            "source_mutations": 0,
            "consolidation_shape": shape,
            "fact_pack_sha256": validated["facts"]["fact_pack_sha256"],
            "source_manifest_sha256": validated["facts"]["source_manifest_sha256"],
            "source_inventory": validated["facts"]["source_inventory"],
            "upstream": {
                "facts_path": validated["facts_path"].relative_to(root).as_posix(),
                "facts_sha256": EVIDENCE.file_hash(validated["facts_path"]),
                "analysis_path": validated["analysis_path"].relative_to(root).as_posix(),
                "analysis_sha256": EVIDENCE.file_hash(validated["analysis_path"]),
                "acceptance_path": validated["acceptance_path"].relative_to(root).as_posix(),
                "acceptance_sha256": EVIDENCE.file_hash(validated["acceptance_path"]),
            },
            "native_checks": {
                name: validated["facts"]["commands"][name]
                for name in ("compile", "compile_tests", "test", "smoke")
            },
            "human_authority": validated["acceptance"],
            "nonclaims": [
                "matching static signature/body shapes are not behavioral equivalence",
                "runtime reachability, JVM ABI, and external compatibility are not established",
                "the proposal grants no source mutation authority",
            ],
            "scope_sha256": EVIDENCE.canonical_hash(scope),
        }
        proposal_payload = {**evidence, "scope": scope}
        EVIDENCE.replace_bundle(
            output,
            {
                "proposal.md": _proposal(proposal_payload),
                "evidence.json": evidence,
                "scope.json": scope,
            },
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "unify-shadows")
            payload, report = EVIDENCE.refusal("unify-shadows", exc)
            EVIDENCE.replace_bundle(
                output, {"proposal.md": report, "evidence.json": payload, "scope.json": payload}
            )
        except EVIDENCE.EvidenceError:
            pass
        print(f"propose_kotlin.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
