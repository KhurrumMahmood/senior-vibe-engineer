"""Projection helper for .claude/skill-use/log.jsonl.

Reads the event log and writes a per-skill summary to
reports/skill-use/projection-<TS>.md.

Stdlib only. Safe to run with an empty log (emits "no data" notice).
Malformed lines are skipped with a stderr warning, not raised.

Usage: python3 .claude/skill-use/project.py [--log <path>] [--output <path>]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO_ROOT / ".claude" / "skill-use" / "log.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "skill-use"


def _load_events(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    events: list[dict] = []
    for lineno, line in enumerate(log_path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stderr.write(
                f"skip line {lineno}: malformed JSON ({exc.msg})\n"
            )
            continue
        if not isinstance(event, dict) or "skill" not in event:
            sys.stderr.write(f"skip line {lineno}: not a skill-use event\n")
            continue
        events.append(event)
    return events


def _cluster_overrides(overrides: list[str]) -> list[tuple[str, int]]:
    """Group human_override strings by leading stem (before ':')."""
    if not overrides:
        return []
    stems: Counter[str] = Counter()
    for override in overrides:
        if not isinstance(override, str):
            continue
        stem = re.split(r"[:\-—]", override, maxsplit=1)[0].strip().lower()
        if stem:
            stems[stem] += 1
    return stems.most_common()


def _project(events: list[dict]) -> dict[str, dict]:
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_skill[event["skill"]].append(event)

    summary: dict[str, dict] = {}
    for skill, skill_events in by_skill.items():
        n = len(skill_events)
        outcomes = Counter(e.get("outcome", "unknown") for e in skill_events)
        overrides = [
            e["human_override"]
            for e in skill_events
            if e.get("human_override")
        ]
        durations = [
            e["duration_s"]
            for e in skill_events
            if isinstance(e.get("duration_s"), (int, float))
        ]
        follow_ups = Counter(
            e["follow_up_skill"]
            for e in skill_events
            if e.get("follow_up_skill")
        )
        useful = outcomes.get("useful", 0)
        summary[skill] = {
            "n": n,
            "useful_rate": (useful / n) if n else 0.0,
            "outcomes": dict(outcomes),
            "override_themes": _cluster_overrides(overrides),
            "avg_duration_s": (
                statistics.mean(durations) if durations else None
            ),
            "follow_ups": follow_ups.most_common(3),
        }
    return summary


def _render(summary: dict[str, dict], event_count: int) -> str:
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []
    lines.append(f"# Skill-use projection — {ts}\n")
    lines.append(f"Events scanned: {event_count}\n")
    if not summary:
        lines.append("No skill-use events recorded yet.\n")
        return "\n".join(lines)

    lines.append("## Per-skill summary\n")
    lines.append(
        "| Skill | n | useful% | avg duration (s) | top override theme | top follow-up |"
    )
    lines.append(
        "|---|---:|---:|---:|---|---|"
    )
    for skill in sorted(summary):
        s = summary[skill]
        top_override = s["override_themes"][0][0] if s["override_themes"] else "—"
        top_follow = s["follow_ups"][0][0] if s["follow_ups"] else "—"
        avg_d = (
            f"{s['avg_duration_s']:.1f}"
            if s["avg_duration_s"] is not None
            else "—"
        )
        lines.append(
            f"| `{skill}` | {s['n']} | {s['useful_rate'] * 100:.0f}% | "
            f"{avg_d} | {top_override} | {top_follow} |"
        )

    lines.append("\n## Override themes (clustered by leading stem)\n")
    any_overrides = False
    for skill in sorted(summary):
        themes = summary[skill]["override_themes"]
        if not themes:
            continue
        any_overrides = True
        lines.append(f"\n### `{skill}`\n")
        for stem, count in themes:
            lines.append(f"- `{stem}` × {count}")
    if not any_overrides:
        lines.append("(no override reasons captured yet)")

    lines.append("\n## Notes\n")
    lines.append(
        "- Under-sampled rows (`n` low) are visible on purpose — do not "
        "over-weight their `useful_rate`."
    )
    lines.append(
        "- This projection is evidence, not verdict. Use it to ask "
        "questions about a skill's shape, not to auto-decide splits."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    events = _load_events(args.log)
    summary = _project(events)

    if args.output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output = DEFAULT_OUTPUT_DIR / f"projection-{ts}.md"
    else:
        output = args.output
        output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(_render(summary, len(events)))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
