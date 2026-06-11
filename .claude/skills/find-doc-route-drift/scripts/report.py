#!/usr/bin/env python3
"""Render docs-route-drift findings."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import read_jsonl, render_simple_report, write_json  # noqa: E402


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
    markdown, findings = render_simple_report("Docs-route drift audit", records, args.target)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    write_json(findings, args.output_json)

    if not args.skip_effectiveness_log:
        subprocess.run(
            [
                "python3",
                "scripts/log_effectiveness.py",
                "--skill",
                "find-doc-route-drift",
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
