#!/usr/bin/env python3
"""Render one read-only C# shadow disposition from accepted Roslyn evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    sys.dont_write_bytecode = True
    candidates = [Path(__file__).with_name("csharp_accepted_evidence.py")]
    candidates.extend(
        parent / "_csharp-semantic" / "csharp_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied C# accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("csharp_unify_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C# accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", value if isinstance(value, str) else "").strip()


def _exact_lead(validated: dict[str, Any]) -> dict[str, Any]:
    facts, lead = validated["facts"], validated["lead"]
    if (
        lead.get("classification")
        != "review_required_resolved_contract_and_body_shape_lead"
        or lead.get("human_verdict") != "required"
        or len(lead.get("functions", [])) != 2
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "lead_invalid", "selected lead must be one exact two-method review pair"
        )
    members: list[dict[str, Any]] = []
    caller_ids: list[set[str]] = []
    for member in lead["functions"]:
        declarations = [
            row
            for row in facts.get("declarations", [])
            if row.get("role") == "source"
            and row.get("kind") == "method"
            and row.get("symbol_id") == member.get("symbol_id")
            and row.get("signature") == member.get("signature")
            and row.get("path") == member.get("path")
            and row.get("line") == member.get("line")
        ]
        if len(declarations) != 1:
            raise EVIDENCE.EvidenceError(
                "partial", "definition_ambiguous", "each accepted method must resolve once"
            )
        declaration = declarations[0]
        if declaration.get("override") or declaration.get("partial"):
            raise EVIDENCE.EvidenceError(
                "partial", "definition_unsupported", "override or partial methods cannot be proposed"
            )
        if hashlib.sha256(_normalized(declaration.get("body_source")).encode()).hexdigest() != lead.get(
            "body_sha256"
        ):
            raise EVIDENCE.EvidenceError(
                "partial", "body_shape_mismatch", "accepted normalized body hash changed"
            )
        calls = [
            {
                "path": row["path"],
                "line": row["line"],
                "source": row.get("source"),
                "caller": row.get("caller"),
                "target_symbol_id": row.get("target_symbol_id"),
                "target_signature": row.get("target_signature"),
            }
            for row in facts.get("calls", [])
            if row.get("role") == "source"
            and row.get("resolved") is True
            and row.get("target_symbol_id") == declaration["symbol_id"]
        ]
        projected = [
            {"path": row["path"], "line": row["line"], "caller": row["caller"]}
            for row in calls
        ]
        if not calls or projected != member.get("direct_caller_contexts"):
            raise EVIDENCE.EvidenceError(
                "partial", "caller_evidence_mismatch", "accepted resolved callers changed"
            )
        ids = {
            row["caller"]["symbol_id"]
            for row in calls
            if isinstance(row.get("caller"), dict) and row["caller"].get("symbol_id")
        }
        if not ids:
            raise EVIDENCE.EvidenceError(
                "partial", "caller_evidence_ambiguous", "each method requires a resolved caller"
            )
        caller_ids.append(ids)
        members.append({"definition": declaration, "resolved_callers": calls})
    if (
        members[0]["definition"]["symbol_id"] == members[1]["definition"]["symbol_id"]
        or caller_ids[0] & caller_ids[1]
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "pair_ambiguous", "distinct definitions and resolved caller sets are required"
        )
    return {"id": lead["id"], "body_sha256": lead["body_sha256"], "members": members}


def _markdown(payload: dict[str, Any]) -> str:
    shape = payload["consolidation_shape"]
    lines = [
        "# C# semantic-shadow disposition",
        "",
        f"Outcome: `{payload['outcome']}`; reviewer-selected shape: `{shape}`.",
        "",
        "## Exact definitions and resolved callers",
        "",
    ]
    for member in payload["scope"]["members"]:
        definition = member["definition"]
        lines.append(
            f"- `{definition['symbol_id']}` / `{definition['signature']}` at "
            f"`{definition['path']}:{definition['line']}`"
        )
        lines.extend(
            f"  - `{call['caller']['symbol_id']}` / `{call['caller']['signature']}` "
            f"at `{call['path']}:{call['line']}`"
            for call in member["resolved_callers"]
        )
    lines.extend(["", "## Reviewer disposition", ""])
    if shape == "keep_separate_document_why":
        lines.append(
            "Keep the two definitions and caller paths separate and document their independent "
            "ownership. No consolidation or caller migration is authorized."
        )
    else:
        lines.append(
            f"Investigate only the accepted `{shape}` shape after characterization and separate "
            "source-mutation approval; migrate resolved callers before deleting any definition."
        )
    lines.extend(
        [
            "",
            "## Stop conditions and non-claims",
            "",
            "- Matching Roslyn signatures and normalized bodies are not behavioral or runtime equivalence.",
            "- Stop on overload, dispatch/interface, delegate/dynamic/reflection, partial, generated/vendor, external-caller, or binary-compatibility changes.",
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
        scope = {
            "schema_version": "csharp-unify-shadows-scope-v1",
            "language": "csharp",
            "status": "complete",
            "read_only": True,
            "source_mutations": 0,
            "finding_id": exact["id"],
            "selected_shape": shape,
            "body_sha256": exact["body_sha256"],
            "members": exact["members"],
            "boundary_verdicts": validated["acceptance"]["boundary_verdicts"],
            "human_approval_required": True,
        }
        scope["artifact_sha256"] = EVIDENCE.canonical_hash(scope)
        evidence = {
            "schema_version": "csharp-unify-shadows-evidence-v1",
            "language": "csharp",
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
                "matching selected static contracts and bodies are not behavioral equivalence",
                "runtime reachability and external/binary compatibility are not established",
                "the disposition grants no source mutation authority",
            ],
        }
        evidence["scope_sha256"] = EVIDENCE.canonical_hash(scope)
        evidence["artifact_sha256"] = EVIDENCE.canonical_hash(evidence)
        proposal_payload = {**evidence, "scope": scope}
        EVIDENCE.replace_bundle(
            output,
            {
                "proposal.md": _markdown(proposal_payload),
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
        print(f"propose_csharp.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
