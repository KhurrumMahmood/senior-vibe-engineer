#!/usr/bin/env python3
"""Append one line to reports/_meta/effectiveness.jsonl.

Each `/find-*`, `/refactor-subsystem`, and `/fix-workflow` run calls this
at its final stage so the skill-effectiveness dashboard can track trends.

Usage (from a skill's final stage):

    python3 scripts/log_effectiveness.py \
      --skill find-dormant \
      --scan-id scan-20260419-062049 \
      --target core/services/ \
      --findings-total 27 \
      --buckets '{"certain_delete": 4, "orphan_endpoint": 0, \
                  "quasi_dead_broken": 4, "false_positive": 17, \
                  "unverified_budget": 2}' \
      --notes "optional"

Schema is documented in `.claude/skills/_common/skill-conventions.md`.

Stdlib-only — runs under `python3`, no venv required. The log is append-
only; partial writes are guarded by opening with mode='a' (atomic on
POSIX for writes under PIPE_BUF, which 1 JSONL line easily satisfies).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".claude" / "skills" / "_common"))

from skill_use import log_event  # noqa: E402


DEFAULT_LOG = Path("reports/_meta/effectiveness.jsonl")


def main() -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="Skill name, e.g. find-dormant")
    parser.add_argument("--scan-id", required=True, help="Scan directory name, e.g. scan-20260419-062049")
    parser.add_argument("--target", required=True, help="Target path of the scan")
    parser.add_argument(
        "--findings-total",
        type=int,
        required=True,
        help="Total findings (or candidates, or items) surfaced by this run",
    )
    parser.add_argument(
        "--buckets",
        default="{}",
        help="JSON dict of bucket name → count (skill-specific)",
    )
    parser.add_argument("--notes", default="", help="Optional free-text notes")
    parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG,
        help=f"Path to effectiveness log (default: {DEFAULT_LOG})",
    )
    parser.add_argument(
        "--ts",
        default=None,
        help="ISO-8601 timestamp (default: now in UTC). Override for backfills.",
    )
    args = parser.parse_args()

    try:
        buckets = json.loads(args.buckets)
        if not isinstance(buckets, dict):
            raise TypeError("buckets must be a JSON object")
    except (json.JSONDecodeError, TypeError) as exc:
        print(f"error: --buckets must be a JSON dict: {exc}", file=sys.stderr)
        return 1

    entry = {
        "skill": args.skill,
        "scan_id": args.scan_id,
        "ts": args.ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target": args.target,
        "findings_total": args.findings_total,
        "buckets": buckets,
    }
    if args.notes:
        entry["notes"] = args.notes

    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"logged to {args.log}: {entry['skill']} / {entry['scan_id']}")
    if args.skill == "refactor-subsystem":
        log_event(
            skill="refactor-subsystem",
            target=args.target,
            artifact=str(args.log),
            elapsed_s=time.monotonic() - start,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
