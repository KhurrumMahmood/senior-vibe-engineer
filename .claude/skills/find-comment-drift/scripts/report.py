#!/usr/bin/env python3
"""Render a find-comment-drift JSONL scan."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from product_topology import read_jsonl, render_simple_report, write_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render comment-drift findings.")
    parser.add_argument("detections", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", default="/sites surface")
    args = parser.parse_args(argv)

    records = read_jsonl(args.detections)
    markdown, findings = render_simple_report("Comment-drift audit", records, args.target)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    write_json(findings, args.output.with_name("findings.json"))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
