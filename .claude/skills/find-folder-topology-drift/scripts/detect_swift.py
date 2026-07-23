#!/usr/bin/env python3
"""Produce Swift flat-prefix folder-topology findings and final artifacts."""

from __future__ import annotations

import argparse
import json
import re
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
    hash_bytes,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
    validate_artifacts,
)


def _prefix(stem: str) -> str | None:
    snake = re.split(r"[_-]", stem, maxsplit=1)
    if len(snake) > 1 and len(snake[0]) >= 2:
        return snake[0]
    camel = re.match(r"([A-Z][a-z0-9]+)(?=[A-Z])", stem)
    return camel.group(1) if camel else None


def _detect(snapshot: dict, minimum: int, allowed: set[str]) -> list[dict]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in snapshot["inventory"]:
        if row["role"] != "eligible":
            continue
        path = Path(row["file"])
        if path.name == "main.swift" or path.parent.as_posix() in allowed:
            continue
        prefix = _prefix(path.stem)
        if prefix:
            groups[(path.parent.as_posix(), prefix)].append(row["file"])
    findings = []
    for (directory, prefix), files in sorted(groups.items()):
        if len(files) < minimum:
            continue
        files.sort()
        findings.append(
            {
                "pattern": "flat_prefix_cluster",
                "language": "swift",
                "file": directory,
                "prefix": prefix,
                "count": len(files),
                "files": files,
                "evidence_sha256": hash_bytes("\n".join(files).encode()),
                "recommendation": "Human triage only; no SwiftPM-safe move is implied.",
            }
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--swift-root", required=True)
    parser.add_argument("--min-cluster-size", type=int, default=3)
    parser.add_argument("--allow-folder", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    report = output.with_name("report.md")
    final_json = output.with_name("findings.json")
    scan_json = output.with_name("scan.json")
    try:
        validate_artifacts(root, [output, report, final_json, scan_json])
    except ValueError as exc:
        parser.error(str(exc))
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        [args.swift_root],
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
    findings = (
        _detect(snapshot, args.min_cluster_size, set(args.allow_folder))
        if snapshot["status"] == "complete"
        else []
    )
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
    analysis = public_snapshot(snapshot)
    atomic_text(output, jsonl)
    atomic_json(scan_json, analysis)
    atomic_json(
        final_json,
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "scan_meta": {
                "language": "swift",
                "target": args.swift_root,
                "patterns": sorted({item["pattern"] for item in findings}),
            },
            "analysis": {"swift": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "findings": findings,
        },
    )
    lines = [
        "# Folder-topology drift audit — Swift",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        f"**Target:** `{args.swift_root}`",
        "",
    ]
    lines.extend(
        f"- `{item['file']}` prefix `{item['prefix']}` — {item['count']} files"
        for item in findings
    )
    if findings:
        lines.append("\nFilename clustering is lexical evidence only; no move is implied.")
    elif snapshot["status"] == "complete":
        lines.append("No Swift filename-prefix cluster met the threshold.")
    else:
        lines.append("Analysis is incomplete; no clean topology conclusion is available.")
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
