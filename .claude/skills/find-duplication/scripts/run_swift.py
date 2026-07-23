#!/usr/bin/env python3
"""Produce exact Swift function-body duplication evidence and triage."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_swift-project-lexical"
sys.path.insert(0, str(COMMON))

from swift_project_facts import (  # noqa: E402
    add_tool_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    function_facts,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
    validate_artifacts,
)


def _findings(snapshot: dict) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in snapshot["inventory"]:
        if row["role"] != "eligible":
            continue
        for fact in function_facts(row):
            if fact["line_count"] >= 5:
                groups[fact["normalized_body_sha256"]].append(fact)
    findings: list[dict] = []
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
            }
            for fact in facts
        ]
        multiplicity = len(sites)
        priority = round(multiplicity * 1.5, 2)
        findings.append(
            {
                "finding_id": f"SWIFT-DUP-{digest[:12].upper()}",
                "detector": "swift-exact-normalized-function-body",
                "shape_hint": "cross-file-clone",
                "multiplicity": multiplicity,
                "shared_lines_min": min(fact["line_count"] for fact in facts),
                "shared_lines_max": max(fact["line_count"] for fact in facts),
                "normalized_body_sha256": digest,
                "semantic_identity_claimed": False,
                "sites": sites,
                "rank_meta": {
                    "priority": priority,
                    "priority_tier": "P1" if priority >= 5 else "P2",
                    "effective_multiplicity": multiplicity,
                    "effort_hint": "medium" if len({site["file"] for site in sites}) > 1 else "low",
                },
            }
        )
    findings.sort(key=lambda row: (-row["rank_meta"]["priority"], row["finding_id"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    artifacts = {
        "collapsed": output / "collapsed.json",
        "ranked": output / "ranked.json",
        "triage": output / "triage.md",
        "findings": output / "findings.json",
        "scan": output / "scan.json",
    }
    try:
        validate_artifacts(root, artifacts.values())
    except ValueError as exc:
        parser.error(str(exc))
    clear_artifacts(artifacts.values())
    snapshot = collect_snapshot(
        root,
        [args.target],
        swift=args.swift,
        swiftc=args.swiftc,
        swift_format=args.swift_format,
        check_product=args.check_product,
        expected_check=args.expected_check,
        smoke_product=args.smoke_product,
        expected_smoke=args.expected_smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    snapshot["host_state_preserved"] = snapshot["source_preserved"]
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    findings = _findings(snapshot) if snapshot["status"] == "complete" else []
    analysis = public_snapshot(snapshot)
    tier_counts = {
        tier: sum(item["rank_meta"]["priority_tier"] == tier for item in findings)
        for tier in ("P0", "P1", "P2")
    }
    scan_meta = {
        "language": "swift",
        "target": args.target,
        "project_root": str(root),
        "status": snapshot["status"],
        "analyzer": "swift-exact-normalized-function-body",
        "analysis": analysis,
        "ast_finding_count": len(findings),
        "rank_summary": {key.casefold(): value for key, value in tier_counts.items()},
    }
    collapsed = {"schema_version": 1, "scan_meta": scan_meta, "findings": findings}
    atomic_json(artifacts["collapsed"], collapsed)
    atomic_json(artifacts["ranked"], collapsed)
    atomic_json(
        artifacts["findings"],
        {"scan_meta": scan_meta, "findings": findings, "dormant_candidates": []},
    )
    atomic_json(artifacts["scan"], analysis)
    lines = [
        "# Duplication triage — Swift",
        "",
        f"**Target:** `{args.target}`",
        f"**Scan status:** `{snapshot['status']}`",
        "",
        "Exact normalized body equality is lexical clone evidence only. "
        "It does not prove semantic identity or authorize consolidation.",
        "",
    ]
    for finding in findings:
        lines.append(f"## `{finding['finding_id']}`")
        lines.extend(
            f"- `{site['file']}::{site['symbol']}` ({site['start_line']}-{site['end_line']})"
            for site in finding["sites"]
        )
        lines.append("")
    if not findings:
        lines.append(
            "No exact clone evidence found within the complete snapshot."
            if snapshot["status"] == "complete"
            else "Analysis is incomplete; no clean conclusion is available."
        )
    atomic_text(artifacts["triage"], "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
