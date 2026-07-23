#!/usr/bin/env python3
"""Produce Dart direct-sibling filename-cluster findings and final artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_dart"
sys.path.insert(0, str(COMMON))

from dart_project_snapshot import (  # noqa: E402
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    eligible_rows,
    hash_bytes,
    public_snapshot,
    terminal_return_code,
    validate_artifact_paths,
)


def _detect(snapshot: dict, minimum: int, allowed: set[str]) -> list[dict]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in eligible_rows(snapshot):
        path = Path(row["file"])
        directory = path.parent.as_posix()
        if directory in allowed or path.stem == path.parent.name:
            continue
        if "_" not in path.stem:
            continue
        prefix = path.stem.split("_", 1)[0]
        if len(prefix) < 2:
            continue
        groups[(directory, prefix)].append(row["file"])
    findings: list[dict] = []
    for (directory, prefix), files in sorted(groups.items()):
        if len(files) < minimum:
            continue
        files.sort()
        findings.append(
            {
                "pattern": "flat_prefix_cluster",
                "language": "dart",
                "file": directory,
                "lineno": 1,
                "prefix": prefix,
                "count": len(files),
                "files": files,
                "evidence_sha256": hash_bytes("\n".join(files).encode()),
                "summary": (
                    f"Dart directory `{directory}` has {len(files)} direct authored siblings "
                    f"sharing the first underscore token `{prefix}`."
                ),
                "recommendation": "Human triage only; no library ownership, import-safe move, or Flutter convention is implied.",
            }
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dart-root", action="append", required=True)
    parser.add_argument("--min-cluster-size", type=int, default=3)
    parser.add_argument("--allow-folder", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    raw = [
        args.output,
        args.output.with_name("report.md"),
        args.output.with_name("findings.json"),
        args.output.with_name("scan.json"),
    ]
    try:
        output, report, final_json, scan_json = validate_artifact_paths(root, raw)
    except ValueError as exc:
        print(f"detect-dart: status=failed: {exc}", file=sys.stderr)
        return 2
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        args.dart_root,
        dart=args.dart,
        direct_test=args.direct_test,
        smoke_entrypoint=args.smoke_entrypoint,
        expected_smoke=args.expected_smoke,
    )
    allowed = {Path(value).as_posix().rstrip("/") for value in args.allow_folder}
    findings = (
        _detect(snapshot, args.min_cluster_size, allowed)
        if snapshot["status"] == "complete"
        else []
    )
    analysis = public_snapshot(snapshot)
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "drift-found"
        if findings
        else "clean"
    )
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    atomic_text(output, jsonl)
    atomic_json(scan_json, analysis)
    atomic_json(
        final_json,
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "scan_meta": {
                "language": "dart",
                "target": args.dart_root,
                "patterns": sorted({row["pattern"] for row in findings}),
            },
            "analysis": {"dart": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "findings": findings,
            "limitation": "Filename topology is advisory; it proves no library ownership, import impact, move safety, or Flutter convention.",
        },
    )
    lines = [
        "# Folder-topology drift audit — Dart",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        f"**Target:** `{', '.join(args.dart_root)}`",
        "",
    ]
    if findings:
        lines.extend(
            f"- `{row['file']}` prefix `{row['prefix']}` — {row['count']} files"
            for row in findings
        )
        lines.append("\nFindings are lexical naming evidence only; do not move files automatically.")
    elif snapshot["status"] == "complete":
        lines.append("No Dart direct-sibling prefix cluster met the policy threshold.")
    else:
        lines.append("Analysis is incomplete; no clean topology conclusion is available.")
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
