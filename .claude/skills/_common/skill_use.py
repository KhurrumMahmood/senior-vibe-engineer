"""Opt-in skill-use telemetry per .claude/skill-use/README.md.

One function: log_event(). Called at a skill's terminal stage to append
one JSON line to .claude/skill-use/log.jsonl. The helper locates the
repo root via .claude/ walk-up, so callers don't track parents[N]
depth themselves. Failures swallowed by design — telemetry must never
block the skill from terminating.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any


def log_event(
    *,
    skill: str,
    target: str,
    artifact: str | None,
    elapsed_s: float,
    outcome: str = "useful",
    follow_up_skill: str | None = None,
    human_override: str | None = None,
    event_kind: str = "skill_run",
    log_path: Path | None = None,
    **extra: Any,
) -> None:
    try:
        if log_path is None:
            repo_root = _find_repo_root(Path(__file__))
            if repo_root is None:
                return
            log_path = repo_root / ".claude" / "skill-use" / "log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "skill": skill,
            "event_kind": event_kind,
            "target": target,
            "artifact": artifact,
            "outcome": outcome,
            "human_override": human_override,
            "duration_s": round(elapsed_s, 3),
            "follow_up_skill": follow_up_skill,
        }
        event.update(extra)
        with log_path.open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def _find_repo_root(start: Path) -> Path | None:
    for parent in start.resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    return None
