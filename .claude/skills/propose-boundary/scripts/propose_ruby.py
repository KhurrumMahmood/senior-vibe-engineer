#!/usr/bin/env python3
"""Render a Ruby boundary proposal from one accepted omnibus finding."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("ruby_proposal_evidence.py")]
    candidates.extend(parent / "_ruby-semantic" / "ruby_proposal_evidence.py" for parent in Path(__file__).resolve().parents)
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("copied Ruby proposal-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("ruby_boundary_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Ruby proposal-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _markdown(payload: dict[str, Any]) -> str:
    if payload["outcome"] == "safely_deferred":
        return "# Ruby boundary proposal\n\nThe accepted human judgment keeps this module cohesive. No decomposition is proposed.\n"
    finding = payload["finding"]
    lines = [
        "# Ruby boundary proposal",
        "",
        "Status: `review_required`; this is a read-only decomposition plan.",
        "",
        "## Proposed boundaries",
        "",
    ]
    for domain, methods in sorted(finding.get("clusters", {}).items()):
        lines.append(f"- `{domain}` boundary owns: {', '.join(f'`{name}`' for name in methods)}")
    lines.extend(
        [
            "",
            "## Migration and stop conditions",
            "",
            f"- Current source: `{finding.get('file')}`; preserve public require paths and constants until callers are inventoried.",
            "- Characterize each public method and the native smoke path before moving code.",
            "- Stop for Rails callbacks/concerns, Zeitwerk/autoload naming, dynamic require/load, send/public_send, reopening, refinements, or metaprogramming.",
            "- Ruby syntax, frozen Bundler, the recorded native test, and smoke must pass before and after an approved refactor.",
            "- Human approval is required before `/refactor-subsystem` mutates source.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "propose-boundary")
        validated = EVIDENCE.validate(
            project_root=root,
            producer="find-omnibus",
            evidence_path=args.evidence,
            acceptance_path=args.acceptance,
            allowed_decisions={"split-boundary", "keep-cohesive"},
        )
        selection = validated["acceptance"].get("selection_id")
        matches = [row for row in validated["artifact"].get("findings", []) if row.get("candidate_id") == selection]
        if len(matches) != 1:
            raise EVIDENCE.EvidenceError("invalid_accepted_evidence", "acceptance must select exactly one omnibus finding")
        finding = matches[0]
        if finding.get("bucket") != "confirmed_omnibus":
            raise EVIDENCE.EvidenceError("unaccepted_evidence", "selected Ruby finding is not a confirmed omnibus")
        decision = validated["acceptance"]["decision"]
        payload = {
            "schema_version": "ruby-boundary-proposal-v1",
            "language": "ruby",
            "status": "complete",
            "outcome": "proposal_ready" if decision == "split-boundary" else "safely_deferred",
            "read_only": True,
            "source_mutations": 0,
            "finding": finding,
            "upstream_artifact_sha256": validated["artifact_sha256"],
            "acceptance_sha256": validated["acceptance_sha256"],
            "human_authority": validated["acceptance"],
            "dynamic_boundaries": validated["artifact"].get("analysis", {}).get("ruby", {}).get("claim_boundary", []),
            "ambiguities": validated["artifact"].get("analysis", {}).get("ruby", {}).get("ambiguities", []),
        }
        EVIDENCE.replace_artifacts(output, {"inspection.json": payload, "proposal.md": _markdown(payload)})
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "propose-boundary")
            payload, report = EVIDENCE.refusal("propose-boundary", exc)
            EVIDENCE.replace_artifacts(output, {"inspection.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"propose-boundary: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
