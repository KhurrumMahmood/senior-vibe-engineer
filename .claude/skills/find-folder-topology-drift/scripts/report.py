#!/usr/bin/env python3
"""Render folder-topology-drift findings."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from support import read_jsonl, render_simple_report, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--language",
        choices=("python", "typescript", "mixed"),
        default=None,
        help="Language label for the final artifact; infer from detections when omitted.",
    )
    args = parser.parse_args()

    records = read_jsonl(args.detections)
    record_languages = {str(record.get("language", "python")) for record in records}
    language = args.language or (next(iter(record_languages)) if len(record_languages) == 1 else "mixed")
    markdown, findings = render_simple_report(
        "Folder-topology drift audit", records, args.target, language
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown, encoding="utf-8")
    write_json(findings, args.output_json)

    print(f"wrote {args.output_md}")
    print(f"wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
