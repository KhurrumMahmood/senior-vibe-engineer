#!/usr/bin/env python3
"""Render one Ruby shadow proposal from accepted RBS-backed duplication evidence."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


SHAPES = {"keep_separate_document_why", "share_utilities", "complete_migration", "merge_at_workflow"}


def _helper() -> Any:
    candidates = [Path(__file__).with_name("ruby_proposal_evidence.py")]
    candidates.extend(parent / "_ruby-semantic" / "ruby_proposal_evidence.py" for parent in Path(__file__).resolve().parents)
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("copied Ruby proposal-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("ruby_unify_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Ruby proposal-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _markdown(payload: dict[str, Any]) -> str:
    lead, shape = payload["lead"], payload["consolidation_shape"]
    lines = [
        "# Ruby semantic-shadow proposal",
        "",
        f"Outcome: `{payload['outcome']}`; shape: `{shape}`; source remains unchanged.",
        "",
        "## Evidence-cited members and callers",
        "",
    ]
    for member in lead["functions"]:
        lines.append(f"- `{member['owner']}#{member['name']}` at `{member['source']['path']}:{member['source']['line']}`; RBS `{member['rbs']['path']}:{member['rbs']['line']}`")
        lines.extend(f"  - direct lexical caller context `{row['path']}:{row['line']}`" for row in member["direct_caller_contexts"])
    lines.extend(["", "## Proposed action", ""])
    if shape == "keep_separate_document_why":
        lines.append("Keep the implementations separate and document their distinct ownership/runtime contracts. No consolidation or caller-move plan is authorized.")
    else:
        lines.append(f"Use the human-selected `{shape}` shape only after a full runtime/caller inventory and characterization tests establish a safe survivor boundary.")
        lines.append("Sequence characterization, smallest shared seam/survivor change, caller migration, then deletion only after native parity.")
    lines.extend(
        [
            "",
            "## Non-claims and stop conditions",
            "",
            "- Matching RBS type shape and direct body spelling do not prove behavioral equivalence.",
            "- Stop for Rails callbacks/concerns, Zeitwerk/autoload, send/public_send, method_missing, reopening, refinements, eval/define_method, external consumers, or generated/native code.",
            "- Run Ruby syntax, frozen Bundler, RBS validation, native test, and exact smoke after any approved implementation.",
            "- A human must approve source mutation separately; this proposal is read-only.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "unify-shadows")
        validated = EVIDENCE.validate(
            project_root=root,
            producer="find-semantic-duplication",
            evidence_path=args.evidence,
            facts_path=args.facts,
            acceptance_path=args.acceptance,
            allowed_decisions=SHAPES,
        )
        selection = validated["acceptance"].get("selection_id")
        matches = [row for row in validated["artifact"].get("leads", []) if row.get("id") == selection]
        if len(matches) != 1:
            raise EVIDENCE.EvidenceError("invalid_accepted_evidence", "acceptance must select exactly one Ruby duplication lead")
        lead = matches[0]
        if lead.get("classification") != "review_required_rbs_contract_shape_lead":
            raise EVIDENCE.EvidenceError("unexpected_evidence", "selected evidence is not a bounded RBS duplication lead")
        shape = validated["acceptance"]["decision"]
        payload = {
            "schema_version": "ruby-unify-shadows-proposal-v1",
            "language": "ruby",
            "status": "complete",
            "outcome": "keep_separate_documented" if shape == "keep_separate_document_why" else "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "consolidation_shape": shape,
            "lead": lead,
            "upstream_artifact_sha256": validated["artifact_sha256"],
            "acceptance_sha256": validated["acceptance_sha256"],
            "human_authority": validated["acceptance"],
            "dynamic_boundaries": validated["facts"].get("source", {}).get("dynamic", []),
            "limits": validated["facts"].get("limits", []),
            "native_checks": validated["facts"].get("tools", {}).get("native", {}),
        }
        scope = {
            "schema_version": "ruby-unify-shadows-scope-v1",
            "finding_id": lead["id"],
            "members": [row["source"] for row in lead["functions"]],
            "caller_contexts": [caller for row in lead["functions"] for caller in row["direct_caller_contexts"]],
            "excluded_runtime_boundaries": payload["limits"],
            "human_approval_required": True,
        }
        EVIDENCE.replace_artifacts(output, {"evidence.json": payload, "scope.json": scope, "proposal.md": _markdown(payload)})
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "unify-shadows")
            payload, report = EVIDENCE.refusal("unify-shadows", exc)
            EVIDENCE.replace_artifacts(output, {"evidence.json": payload, "scope.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"unify-shadows: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
