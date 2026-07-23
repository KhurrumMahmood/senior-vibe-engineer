#!/usr/bin/env python3
"""Render one Ruby folder proposal from accepted lexical topology evidence."""

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
    spec = importlib.util.spec_from_file_location("ruby_folder_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Ruby proposal-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _moves(finding: dict[str, Any]) -> list[dict[str, str]]:
    parent = Path(finding["file"])
    prefix = finding["prefix"]
    rows = []
    for source in finding["files"]:
        path = Path(source)
        stem = path.stem
        suffix = stem[len(prefix) :].lstrip("_-")
        rows.append({"source": source, "destination": (parent / prefix / f"{suffix}{path.suffix}").as_posix()})
    return rows


def _markdown(payload: dict[str, Any]) -> str:
    if payload["outcome"] == "safely_deferred":
        return "# Ruby folder proposal\n\nHuman review chose to keep this cluster flat. No move is proposed.\n"
    lines = [
        "# Ruby folder reorganization proposal",
        "",
        "Status: `review_required`; this artifact moves no files.",
        "",
        "## Current → proposed",
        "",
    ]
    lines.extend(f"- `{row['source']}` → `{row['destination']}`" for row in payload["moves"])
    lines.extend(
        [
            "",
            "## Required impact inventory and stop conditions",
            "",
            "- Inventory every `require`, `require_relative`, autoload, constant, test, and executable reference before moving anything.",
            "- Preserve constant ownership; filenames alone are not constant or load-path authority.",
            "- Stop for Rails engines/concerns, Zeitwerk/autoload naming, dynamic require/load, `$LOAD_PATH`, reopening, refinements, or metaprogramming.",
            "- Add characterization coverage first; then run Ruby syntax, frozen Bundler, native test, and exact smoke before/after.",
            "- Human approval is required before `/refactor-subsystem` performs the move.",
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
        output = EVIDENCE.safe_output(root, args.output_dir, "propose-folder-reorganization")
        validated = EVIDENCE.validate(
            project_root=root,
            producer="find-folder-topology-drift",
            evidence_path=args.evidence,
            acceptance_path=args.acceptance,
            allowed_decisions={"split-folder", "keep-flat"},
        )
        selection = validated["acceptance"].get("selection_sha256")
        matches = [row for row in validated["artifact"].get("findings", []) if row.get("evidence_sha256") == selection]
        if len(matches) != 1:
            raise EVIDENCE.EvidenceError("invalid_accepted_evidence", "acceptance must select exactly one topology finding")
        finding = matches[0]
        if finding.get("pattern") != "flat_prefix_cluster" or finding.get("count", 0) < 3:
            raise EVIDENCE.EvidenceError("unaccepted_evidence", "selected Ruby cluster does not meet the three-sibling threshold")
        decision = validated["acceptance"]["decision"]
        payload = {
            "schema_version": "ruby-folder-proposal-v1",
            "language": "ruby",
            "status": "complete",
            "outcome": "proposal_ready" if decision == "split-folder" else "safely_deferred",
            "read_only": True,
            "source_mutations": 0,
            "finding": finding,
            "moves": _moves(finding) if decision == "split-folder" else [],
            "upstream_artifact_sha256": validated["artifact_sha256"],
            "acceptance_sha256": validated["acceptance_sha256"],
            "human_authority": validated["acceptance"],
            "dynamic_boundaries": [
                "Lexical filename evidence does not resolve require/load or constants.",
                "Rails/Zeitwerk/autoload and metaprogramming require a separate runtime-aware review.",
            ],
        }
        EVIDENCE.replace_artifacts(output, {"inspection.json": payload, "proposal.md": _markdown(payload)})
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "propose-folder-reorganization")
            payload, report = EVIDENCE.refusal("propose-folder-reorganization", exc)
            EVIDENCE.replace_artifacts(output, {"inspection.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"propose-folder-reorganization: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
