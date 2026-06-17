#!/usr/bin/env python3
"""Render frontend-contract-drift findings."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import read_jsonl, render_simple_report, write_json  # noqa: E402


TARGET_SCOPE_BY_NAME = {
    "sites": "sites_workflow",
    "site_config": "sites_workflow",
}


def _target_scope(target: str) -> str | None:
    normalized = target.lower().replace("\\", "/")
    if TARGET_SCOPE_BY_NAME.get(normalized):
        return TARGET_SCOPE_BY_NAME[normalized]
    if (
        "site_config" in normalized
        or "templates/core/site_config" in normalized
        or "static/js/site-config" in normalized
    ):
        return "sites_workflow"
    if "external_source" in normalized:
        return "other_product_surface"
    return None


def _with_scope_summary(markdown: str, records: list[dict[str, object]], target: str) -> str:
    scope_counts: dict[str, int] = {}
    for record in records:
        scope = str(record.get("workflow_scope") or "unknown")
        scope_counts[scope] = scope_counts.get(scope, 0) + 1

    target_scope = _target_scope(target)
    lines = ["## Scope Summary", ""]
    if target_scope:
        target_count = scope_counts.get(target_scope, 0)
        status = "target clean" if target_count == 0 else f"{target_count} target finding(s)"
        lines.append(f"- **Target status:** {status} for `{target_scope}`")
    if scope_counts:
        lines.append("- **Scope buckets:** " + ", ".join(
            f"`{scope}`={count}" for scope, count in sorted(scope_counts.items())
        ))
    else:
        lines.append("- **Scope buckets:** none")
    lines.append("")

    marker = "## Buckets\n"
    if marker in markdown:
        return markdown.replace(marker, "\n".join(lines) + "\n" + marker, 1)
    return markdown + "\n\n" + "\n".join(lines)


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
    markdown, findings = render_simple_report("Frontend-contract drift audit", records, args.target)
    markdown = _with_scope_summary(markdown, records, args.target)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    write_json(findings, args.output_json)

    if not args.skip_effectiveness_log:
        subprocess.run(
            [
                "python3",
                "scripts/log_effectiveness.py",
                "--skill",
                "find-frontend-contract-drift",
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
