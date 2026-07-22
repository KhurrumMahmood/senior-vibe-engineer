#!/usr/bin/env python3
"""Produce exact Rust function-body duplication evidence and final triage."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_rust"
sys.path.insert(0, str(COMMON))

from rust_lexical_facts import (  # noqa: E402
    add_tool_arguments,
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
        finding_id = f"RUST-DUP-{digest[:12].upper()}"
        multiplicity = len(sites)
        priority = round(multiplicity * 1.5, 2)
        findings.append(
            {
                "finding_id": finding_id,
                "detector": "rust-exact-normalized-function-body",
                "shape_hint": "cross_file_clone",
                "multiplicity": multiplicity,
                "shared_lines_min": min(fact["line_count"] for fact in facts),
                "shared_lines_max": max(fact["line_count"] for fact in facts),
                "normalized_body_sha256": digest,
                "sites": sites,
                "rank_meta": {
                    "priority": priority,
                    "priority_tier": "P1" if priority >= 5 else "P2",
                    "divergence_risk": 1.0,
                    "bug_blast_radius": 1.5,
                    "effective_multiplicity": multiplicity,
                    "effort_hint": "medium" if len({site["file"] for site in sites}) > 1 else "low",
                },
            }
        )
    findings.sort(key=lambda item: (-item["rank_meta"]["priority"], item["finding_id"]))
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
    clear_artifacts(artifacts.values())
    snapshot = collect_snapshot(
        root,
        [args.target],
        rustc=args.rustc,
        cargo=args.cargo,
        rustfmt=args.rustfmt,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    findings = _findings(snapshot) if snapshot["status"] != "failed" else []
    analysis = public_snapshot(snapshot)
    tier_counts = {
        tier: sum(item["rank_meta"]["priority_tier"] == tier for item in findings)
        for tier in ("P0", "P1", "P2")
    }
    scan_meta = {
        "language": "rust",
        "target": args.target,
        "project_root": str(root),
        "status": snapshot["status"],
        "analyzer": "rust-exact-normalized-function-body",
        "analysis": analysis,
        "ast_finding_count": len(findings),
        "rank_summary": {key.casefold(): value for key, value in tier_counts.items()},
    }
    collapsed = {"schema_version": 1, "scan_meta": scan_meta, "findings": findings}
    ranked = dict(collapsed)
    final = {"scan_meta": scan_meta, "findings": findings, "dormant_candidates": []}
    atomic_json(artifacts["collapsed"], collapsed)
    atomic_json(artifacts["ranked"], ranked)
    atomic_json(artifacts["findings"], final)
    atomic_json(artifacts["scan"], analysis)
    lines = [
        "# Duplication triage — Rust",
        "",
        f"**Target:** `{args.target}`",
        f"**Scan status:** `{snapshot['status']}`",
        "",
        "> **Rust v1 boundary:** This is exact normalized function-body clone evidence. "
        "Do not consolidate automatically; behavior, callers, cfg variants, and ownership "
        "still require human review.",
        "",
        f"## Priority clusters ({len(findings)})",
        "",
    ]
    for finding in findings:
        lines.append(f"### `{finding['finding_id']}`")
        lines.extend(
            f"- `{site['file']}::{site['symbol']}` ({site['start_line']}-{site['end_line']})"
            for site in finding["sites"]
        )
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
