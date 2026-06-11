#!/usr/bin/env python3
"""Render workflow-duplication findings."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import read_jsonl, write_json  # noqa: E402


def _bucket_counts(records: list[dict[str, object]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for record in records:
        key = str(record.get("pattern") or record.get("bucket") or "finding")
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


def _format_file_list(files: object) -> str:
    if not isinstance(files, list) or not files:
        return "`(none)`"
    return ", ".join(f"`{file}`" for file in files)


def render_workflow_report(records: list[dict[str, object]], target: str) -> tuple[str, dict[str, object]]:
    buckets = _bucket_counts(records)

    lines = [
        "# Workflow-duplication audit",
        "",
        f"**Target:** `{target}`",
        f"**Findings:** {len(records)}",
        "",
    ]
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        for bucket, count in sorted(buckets.items()):
            lines.append(f"| `{bucket}` | {count} |")
        lines.append("")

    if records:
        lines.extend(["## Findings", ""])
        for idx, record in enumerate(records, start=1):
            file = record.get("file", "?")
            line = record.get("lineno", "?")
            pattern = record.get("pattern", record.get("bucket", "finding"))
            summary = record.get("summary") or record.get("message") or record.get("evidence") or ""
            surface_counts = record.get("surface_counts") or {}

            lines.append(f"### {idx}. `{pattern}`")
            lines.append("")
            lines.append(f"- **Location:** `{file}:{line}`")
            if summary:
                lines.append(f"- **Evidence:** {summary}")
            if surface_counts:
                lines.append(f"- **Surfaces:** `{surface_counts}`")
            lines.append(f"- **Active owners:** `{record.get('active_owners', [])}`")
            lines.append(f"- **Active files:** {_format_file_list(record.get('active_files'))}")
            lines.append(f"- **Deferred/context files:** {_format_file_list(record.get('deferred_files'))}")
            recommendation = record.get("recommendation")
            if recommendation:
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")

    findings = {
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
    return "\n".join(lines), findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--scan-id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-effectiveness-log", action="store_true")
    args = parser.parse_args()

    records = read_jsonl(args.detections)
    markdown, findings = render_workflow_report(records, args.target)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    write_json(findings, args.output_json)

    if not args.skip_effectiveness_log:
        subprocess.run(
            [
                "python3",
                "scripts/log_effectiveness.py",
                "--skill",
                "find-workflow-duplication",
                "--scan-id",
                args.scan_id,
                "--target",
                args.target,
                "--findings-total",
                str(findings["summary"]["findings_total"]),
                "--buckets",
                json.dumps(findings["summary"]["buckets"], sort_keys=True),
            ],
            cwd=args.project_root,
            check=False,
        )
    print(f"wrote {args.output_md}")
    print(f"wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
