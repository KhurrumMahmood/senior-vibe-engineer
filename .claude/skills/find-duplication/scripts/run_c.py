#!/usr/bin/env python3
"""Produce exact C17 function-body spelling duplication evidence and triage."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

PROVIDER = Path(__file__).resolve().parents[2] / "_c"
sys.path.insert(0, str(PROVIDER))

from c_lexical_facts import (  # noqa: E402
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    function_facts,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def _findings(snapshot: dict) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in snapshot["inventory"]:
        if row["role"] != "eligible" or not row["selected"]:
            continue
        for fact in function_facts(row):
            if fact["line_count"] >= 5:
                groups[fact["normalized_body_sha256"]].append(fact)
    findings = []
    for digest, facts in sorted(groups.items()):
        if len(facts) < 2:
            continue
        sites = [
            {
                "file": fact["file"],
                "symbol": fact["symbol"],
                "start_line": fact["span"]["start"]["line"],
                "end_line": fact["span"]["end"]["line"],
                "span": fact["span"],
                "source_sha256": fact["source_sha256"],
                "spelling_sha256": fact["spelling_sha256"],
                "linkage": fact["linkage"],
            }
            for fact in facts
        ]
        multiplicity = len(sites)
        findings.append(
            {
                "finding_id": f"C-DUP-{digest[:12].upper()}",
                "detector": "c17-exact-normalized-function-body-spelling",
                "shape_hint": "cross_file_clone",
                "multiplicity": multiplicity,
                "shared_lines_min": min(fact["line_count"] for fact in facts),
                "shared_lines_max": max(fact["line_count"] for fact in facts),
                "normalized_body_sha256": digest,
                "sites": sites,
                "rank_meta": {
                    "priority": round(multiplicity * 1.5, 2),
                    "priority_tier": "P1" if multiplicity >= 4 else "P2",
                    "divergence_risk": 1.0,
                    "bug_blast_radius": 1.5,
                    "effective_multiplicity": multiplicity,
                    "effort_hint": "medium" if len({site["file"] for site in sites}) > 1 else "low",
                },
            }
        )
    return sorted(findings, key=lambda item: (-item["rank_meta"]["priority"], item["finding_id"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root, output = args.project_root.resolve(), args.output_dir.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output-dir must be inside --project-root")
    artifacts = {
        "collapsed": output / "collapsed.json",
        "ranked": output / "ranked.json",
        "triage": output / "triage.md",
        "findings": output / "findings.json",
        "scan": output / "scan.json",
    }
    clear_artifacts(artifacts.values())
    snapshot = collect_snapshot(
        root,
        [args.target],
        clang=args.clang,
        make=args.make,
        test_target=args.test_target,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    findings = _findings(snapshot) if snapshot["status"] != "failed" else []
    analysis = public_snapshot(snapshot)
    scan_meta = {
        "language": "c",
        "target": args.target,
        "project_root": str(root),
        "status": snapshot["status"],
        "analyzer": "c17-exact-normalized-function-body-spelling",
        "analysis": analysis,
        "lexical_finding_count": len(findings),
    }
    collapsed = {"schema_version": 1, "scan_meta": scan_meta, "findings": findings}
    atomic_json(artifacts["collapsed"], collapsed)
    atomic_json(artifacts["ranked"], dict(collapsed))
    atomic_json(artifacts["findings"], {**collapsed, "dormant_candidates": []})
    atomic_json(artifacts["scan"], analysis)
    lines = [
        "# Duplication triage — C17",
        "",
        f"**Scan status:** `{snapshot['status']}`",
        "",
        "> Exact direct function-body spelling is a review lead only; it is not semantic or behavioral equivalence.",
        "",
    ]
    for finding in findings:
        lines.append(f"### `{finding['finding_id']}`")
        lines.extend(f"- `{site['file']}::{site['symbol']}`" for site in finding["sites"])
        lines.append("")
    if not findings:
        lines.append(
            "No exact clone evidence found within the complete snapshot."
            if snapshot["status"] == "complete"
            else "Analysis incomplete; no clean conclusion is available."
        )
    atomic_text(artifacts["triage"], "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
