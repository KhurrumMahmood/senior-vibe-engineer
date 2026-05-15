"""Manual compaction script for .claude/skill-use/log.jsonl.

Reads the active log, writes a markdown lessons digest, gzips the log
into archive/, and truncates the active log to a sentinel header
pointing at the latest digest.

Stdlib only. No-op on empty log (emits notice, leaves files untouched).

Usage: python3 .claude/skill-use/compact.py [--log <path>] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_USE_DIR = REPO_ROOT / ".claude" / "skill-use"
DEFAULT_LOG = SKILL_USE_DIR / "log.jsonl"
ARCHIVE_DIR = SKILL_USE_DIR / "archive"


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
        if isinstance(event, dict) and "skill" in event:
            events.append(event)
    return events


def _stem(text: str) -> str:
    return re.split(r"[:\-—]", text, maxsplit=1)[0].strip().lower()


def _composition_pairs(events: list[dict]) -> Counter[tuple[str, str]]:
    pairs: Counter[tuple[str, str]] = Counter()
    for event in events:
        follow = event.get("follow_up_skill")
        if follow:
            pairs[(event["skill"], follow)] += 1
    return pairs


def _render_digest(events: list[dict], window_start: str, window_end: str) -> str:
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_skill[event["skill"]].append(event)

    lines: list[str] = []
    lines.append(f"# Skill-use lessons — {window_start} → {window_end}\n")
    lines.append(f"Events in window: {len(events)}\n")

    lines.append("## Per-skill useful rate\n")
    lines.append("| Skill | n | useful% | overridden% |")
    lines.append("|---|---:|---:|---:|")
    for skill in sorted(by_skill):
        skill_events = by_skill[skill]
        n = len(skill_events)
        useful = sum(
            1 for e in skill_events if e.get("outcome") == "useful"
        )
        overridden = sum(
            1 for e in skill_events if e.get("outcome") == "overridden"
        )
        lines.append(
            f"| `{skill}` | {n} | {useful * 100 // n if n else 0}% | "
            f"{overridden * 100 // n if n else 0}% |"
        )

    lines.append("\n## Recurring override themes\n")
    themed = False
    for skill in sorted(by_skill):
        stems = Counter(
            _stem(e["human_override"])
            for e in by_skill[skill]
            if isinstance(e.get("human_override"), str)
            and e["human_override"].strip()
        )
        stems.pop("", None)
        if not stems:
            continue
        themed = True
        lines.append(f"\n### `{skill}`")
        for stem, count in stems.most_common():
            lines.append(f"- `{stem}` × {count}")
    if not themed:
        lines.append("(no override themes in this window)")

    lines.append("\n## Composition patterns (skill → follow-up)\n")
    pairs = _composition_pairs(events)
    if not pairs:
        lines.append("(no follow-up handoffs captured)")
    else:
        for (a, b), count in pairs.most_common():
            lines.append(f"- `{a}` → `{b}` × {count}")

    lines.append("\n## Calibration triggers\n")
    triggers: list[str] = []
    for skill, skill_events in by_skill.items():
        n = len(skill_events)
        if n < 5:
            continue
        overridden_rate = sum(
            1 for e in skill_events if e.get("outcome") == "overridden"
        ) / n
        if overridden_rate >= 0.4:
            triggers.append(
                f"- `{skill}`: overridden rate {overridden_rate:.0%} "
                f"across n={n} — boundary-split candidate "
                f"(invoke `/propose-boundary .claude/skills/{skill}/`)."
            )
    if triggers:
        lines.extend(triggers)
    else:
        lines.append("(no triggers fired in this window)")

    lines.append("")
    return "\n".join(lines)


def _sentinel(digest_name: str, archive_name: str) -> str:
    return (
        f"# Sentinel — active log truncated by compact.py. "
        f"Latest digest: {digest_name}. Archive: archive/{archive_name}.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    events = _load_events(args.log)
    if not events:
        print("no events in log; nothing to compact")
        return 0

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    window_start = events[0].get("ts", "?")
    window_end = events[-1].get("ts", "?")
    digest_name = f"lessons-{ts}.md"
    archive_name = f"log-{ts}.jsonl.gz"

    digest_path = SKILL_USE_DIR / digest_name
    archive_path = ARCHIVE_DIR / archive_name

    digest = _render_digest(events, window_start, window_end)

    if args.dry_run:
        print(f"[dry-run] would write {digest_path}")
        print(f"[dry-run] would archive {args.log} → {archive_path}")
        print(f"[dry-run] would truncate {args.log} to sentinel")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(digest)

    with args.log.open("rb") as src, gzip.open(archive_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    args.log.write_text(_sentinel(digest_name, archive_name))

    print(f"wrote digest: {digest_path}")
    print(f"archived raw log: {archive_path}")
    print(f"truncated active log: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
