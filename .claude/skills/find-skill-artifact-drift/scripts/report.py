#!/usr/bin/env python3
"""Render a find-skill-artifact-drift JSONL scan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"cannot read detections JSONL {path}: {exc}") from None
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def render_simple_report(title: str, records: list[dict[str, Any]], target: str) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        key = str(record.get("pattern") or "finding")
        buckets[key] = buckets.get(key, 0) + 1
    lines = [f"# {title}", "", f"**Target:** `{target}`", f"**Findings:** {len(records)}", ""]
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        lines.extend(f"| `{bucket}` | {count} |" for bucket, count in sorted(buckets.items()))
        lines.append("")
    if records:
        lines.extend(["## Findings", ""])
        for index, record in enumerate(records, 1):
            lines.extend([
                f"### {index}. `{record.get('pattern', 'finding')}`",
                "",
                f"- **Location:** `{record.get('file', '?')}:{record.get('lineno', '?')}`",
            ])
            if summary := record.get("summary"):
                lines.append(f"- **Evidence:** {summary}")
            if recommendation := record.get("recommendation"):
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")
    return "\n".join(lines), {"summary": {"findings_total": len(records), "buckets": buckets}, "findings": records}


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render skill-artifact-drift findings.")
    parser.add_argument("detections", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", default="all skills")
    args = parser.parse_args(argv)

    records = read_jsonl(args.detections)
    markdown, findings = render_simple_report("Skill-artifact-drift audit", records, args.target)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    write_json(findings, args.output.with_name("findings.json"))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
