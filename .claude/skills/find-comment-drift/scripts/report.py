#!/usr/bin/env python3
"""Render a find-comment-drift JSONL scan."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from support import read_jsonl, render_simple_report, write_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render comment-drift findings.")
    parser.add_argument("detections", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="JSON report path (default: findings.json beside the Markdown report).",
    )
    parser.add_argument("--target", default="legacy default surface")
    args = parser.parse_args(argv)

    records = read_jsonl(args.detections)
    scan_path = args.detections.with_name("scan.json")
    scan = None
    if scan_path.is_file():
        import json

        scan = json.loads(scan_path.read_text(encoding="utf-8"))
    markdown, findings = render_simple_report(
        "Comment-drift audit", records, args.target, scan
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    if scan and "outcome" in scan:
        findings["outcome"] = scan["outcome"]
    write_json(findings, args.output_json or args.output.with_name("findings.json"))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
