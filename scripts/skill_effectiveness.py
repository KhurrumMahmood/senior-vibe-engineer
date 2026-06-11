#!/usr/bin/env python3
"""Aggregate reports/_meta/effectiveness.jsonl into a markdown dashboard.

Reads one JSON object per line from `reports/_meta/effectiveness.jsonl` and
writes `reports/_meta/dashboard.md` — counts by skill, per-month trend,
most-hit targets, plus the five most-recent runs verbatim.

Schema (one line per skill run, appended by each skill's final stage):

    {
      "skill": "find-dormant",
      "scan_id": "scan-20260419-062049",
      "ts": "2026-04-19T06:20:49Z",
      "target": "src/services/",
      "findings_total": 27,
      "buckets": {"certain_delete": 4, "orphan_endpoint": 0,
                  "quasi_dead_broken": 4, "false_positive": 17,
                  "unverified_budget": 2},
      "notes": "optional free-text"
    }

Stdlib-only (runs under `python3`, no venv needed). Invalid lines are
skipped with a warning rather than aborting; the log is append-only and
a malformed entry from one skill run must not block the dashboard.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def load_entries(jsonl_path: Path) -> list[dict]:
    if not jsonl_path.exists():
        return []
    entries: list[dict] = []
    for lineno, raw in enumerate(jsonl_path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(
                f"warn: {jsonl_path}:{lineno} skipped (invalid JSON: {exc})",
                file=sys.stderr,
            )
    return entries


def month_key(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m")
    except (ValueError, AttributeError):
        return "unknown"


def render(entries: list[dict]) -> str:
    if not entries:
        return (
            "# Skill effectiveness dashboard\n\n"
            "_No runs recorded yet._ Skills append one line per run to\n"
            "`reports/_meta/effectiveness.jsonl`. Re-run this script after\n"
            "the first scan lands.\n"
        )

    runs_by_skill = Counter(e.get("skill", "unknown") for e in entries)
    findings_by_skill: Counter[str] = Counter()
    for e in entries:
        findings_by_skill[e.get("skill", "unknown")] += int(e.get("findings_total", 0) or 0)

    per_month: dict[str, Counter[str]] = defaultdict(Counter)
    for e in entries:
        per_month[month_key(e.get("ts", ""))][e.get("skill", "unknown")] += 1

    target_hits: Counter[str] = Counter(e.get("target", "unknown") for e in entries)

    lines: list[str] = [
        "# Skill effectiveness dashboard",
        "",
        f"_Aggregated from `reports/_meta/effectiveness.jsonl` — {len(entries)} run(s)._",
        "",
        "## Runs by skill",
        "",
        "| Skill | Runs | Total findings |",
        "|---|---:|---:|",
    ]
    for skill in sorted(runs_by_skill):
        lines.append(f"| {skill} | {runs_by_skill[skill]} | {findings_by_skill[skill]} |")

    lines += [
        "",
        "## Trend by month",
        "",
        "| Month | " + " | ".join(sorted(runs_by_skill)) + " |",
        "|---|" + "|".join("---:" for _ in runs_by_skill) + "|",
    ]
    for month in sorted(per_month):
        row = [month] + [str(per_month[month][s]) for s in sorted(runs_by_skill)]
        lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## Most-scanned targets",
        "",
        "| Target | Runs |",
        "|---|---:|",
    ]
    for target, count in target_hits.most_common(10):
        lines.append(f"| `{target}` | {count} |")

    lines += ["", "## Five most recent runs", ""]
    recent = sorted(entries, key=lambda e: e.get("ts", ""), reverse=True)[:5]
    for entry in recent:
        lines.append(f"- **{entry.get('ts', '?')}** `{entry.get('skill', '?')}`"
                     f" scan `{entry.get('scan_id', '?')}` — target "
                     f"`{entry.get('target', '?')}`, "
                     f"{entry.get('findings_total', 0)} findings"
                     + (f", buckets: {entry['buckets']}" if entry.get("buckets") else "")
                     + (f". {entry['notes']}" if entry.get("notes") else ""))

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/_meta/effectiveness.jsonl"),
        help="Path to effectiveness log (default: reports/_meta/effectiveness.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/_meta/dashboard.md"),
        help="Path to write dashboard (default: reports/_meta/dashboard.md)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print dashboard to stdout instead of writing to --output",
    )
    args = parser.parse_args()

    entries = load_entries(args.input)
    rendered = render(entries)

    if args.stdout:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
        print(f"wrote {args.output} ({len(entries)} run(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
