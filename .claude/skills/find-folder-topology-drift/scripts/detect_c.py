#!/usr/bin/env python3
"""Produce direct-sibling C filename cluster evidence and final artifacts."""

from __future__ import annotations

import argparse
import json
import re
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
    hash_bytes,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def _detect(snapshot: dict, minimum: int) -> list[dict]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in snapshot["inventory"]:
        if row["role"] != "eligible" or not row["selected"]:
            continue
        path = Path(row["file"])
        if path.suffix.casefold() not in {".c", ".i"}:
            continue
        prefix = re.split(r"[_-]", path.stem, maxsplit=1)[0]
        if len(prefix) < 2 or prefix == path.stem:
            continue
        groups[(path.parent.as_posix(), prefix)].append(row["file"])
    findings = []
    for (directory, prefix), files in sorted(groups.items()):
        if len(files) < minimum:
            continue
        files.sort()
        findings.append(
            {
                "pattern": "flat_prefix_cluster",
                "language": "c",
                "file": directory,
                "prefix": prefix,
                "count": len(files),
                "files": files,
                "evidence_sha256": hash_bytes("\n".join(files).encode()),
                "recommendation": (
                    "Human triage only; compiler ownership, include/build impact, framework layout, and move safety are unresolved."
                ),
            }
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--c-root", required=True)
    parser.add_argument("--min-cluster-size", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root, output = args.project_root.resolve(), args.output.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output must be inside --project-root")
    report, final_json, scan_json = (
        output.with_name("report.md"),
        output.with_name("findings.json"),
        output.with_name("scan.json"),
    )
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        [args.c_root],
        clang=args.clang,
        make=args.make,
        test_target=args.test_target,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    findings = _detect(snapshot, args.min_cluster_size) if snapshot["status"] != "failed" else []
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "drift-found"
        if findings
        else "clean"
    )
    jsonl = "".join(json.dumps(item, sort_keys=True) + "\n" for item in findings)
    atomic_text(output, jsonl)
    analysis = public_snapshot(snapshot)
    atomic_json(scan_json, analysis)
    atomic_json(
        final_json,
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "scan_meta": {
                "language": "c",
                "target": args.c_root,
                "patterns": sorted({item["pattern"] for item in findings}),
            },
            "analysis": {"c": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "findings": findings,
        },
    )
    lines = [
        "# Folder-topology drift audit — C17",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        "",
    ]
    if findings:
        lines.extend(
            f"- `{item['file']}` prefix `{item['prefix']}` — {item['count']} files"
            for item in findings
        )
        lines.append("\nFilename evidence does not endorse a framework/layout or authorize moves.")
    elif snapshot["status"] == "complete":
        lines.append("No direct-sibling C filename cluster met the threshold.")
    else:
        lines.append("Analysis is incomplete; no clean topology conclusion is available.")
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
