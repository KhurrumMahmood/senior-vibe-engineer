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


def _split_events(events: list[dict]) -> tuple[list[dict], list[dict]]:
    run_events: list[dict] = []
    recommendation_events: list[dict] = []
    for event in events:
        if event.get("event_kind") == "recommendation":
            recommendation_events.append(event)
        else:
            run_events.append(event)
    return run_events, recommendation_events


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


def _project_shapes(events: list[dict]) -> dict[str, dict]:
    by_shape: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        shape = event.get("shape")
        if isinstance(shape, str) and shape:
            by_shape[shape].append(event)

    summary: dict[str, dict] = {}
    for shape, shape_events in by_shape.items():
        overrides = [
            event["human_override"]
            for event in shape_events
            if event.get("human_override")
        ]
        first_skills = Counter(
            event.get("recommended_first_skill")
            for event in shape_events
            if event.get("recommended_first_skill")
        )
        confidences = Counter(
            event.get("confidence", "unknown")
            for event in shape_events
        )
        summary[shape] = {
            "n": len(shape_events),
            "confidences": dict(confidences),
            "top_first_skill": first_skills.most_common(1),
            "override_themes": _cluster_overrides(overrides),
        }
    return summary


def _render(
    summary: dict[str, dict],
    shape_summary: dict[str, dict],
    event_count: int,
    run_event_count: int | None = None,
    recommendation_event_count: int | None = None,
) -> str:
    run_count = event_count if run_event_count is None else run_event_count
    rec_count = 0 if recommendation_event_count is None else recommendation_event_count
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []
    lines.append(f"# Skill-use projection — {ts}\n")
    lines.append(f"Events scanned: {event_count}\n")
    lines.append(f"Skill runs: {run_count}; shape recommendations: {rec_count}\n")
    if not summary and not shape_summary:
        lines.append("No skill-use events recorded yet.\n")
        return "\n".join(lines)

    if summary:
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
    else:
        lines.append("## Per-skill summary\n")
        lines.append("(no skill-run events captured)\n")

    lines.append("\n## Shape recommendations\n")
    if shape_summary:
        lines.append("| Shape | n | confidence mix | top first step | top override theme |")
        lines.append("|---|---:|---|---|---|")
        for shape in sorted(shape_summary):
            s = shape_summary[shape]
            confidence_mix = ", ".join(
                f"{name}:{count}" for name, count in sorted(s["confidences"].items())
            )
            top_first = s["top_first_skill"][0][0] if s["top_first_skill"] else "—"
            top_override = s["override_themes"][0][0] if s["override_themes"] else "—"
            lines.append(
                f"| `{shape}` | {s['n']} | {confidence_mix or '—'} | "
                f"{top_first} | {top_override} |"
            )
    else:
        lines.append("(no shape recommendation events captured)")

    lines.append("\n## Override themes (clustered by leading stem)\n")
    any_overrides = False
    for label, items in (("skill", summary), ("shape", shape_summary)):
        for name in sorted(items):
            themes = items[name]["override_themes"]
            if not themes:
                continue
            any_overrides = True
            lines.append(f"\n### `{label}:{name}`\n")
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
    lines.append(
        "- Shape recommendation events are excluded from per-skill useful "
        "rates so routing advice does not masquerade as completed work."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    events = _load_events(args.log)
    run_events, recommendation_events = _split_events(events)
    summary = _project(run_events)
    shape_summary = _project_shapes(recommendation_events)

    if args.output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output = DEFAULT_OUTPUT_DIR / f"projection-{ts}.md"
    else:
        output = args.output
        output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        _render(
            summary,
            shape_summary,
            len(events),
            len(run_events),
            len(recommendation_events),
        )
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
