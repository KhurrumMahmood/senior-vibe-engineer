#!/usr/bin/env python3
"""Optional scheduled review entrypoint for agent-policy friction."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.agent_policy.friction import DEFAULT_LOG, summarize
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.agent_policy.friction import DEFAULT_LOG, summarize

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NOTE = REPO_ROOT / ".claude" / "tasks" / "agent-policy-friction-review.md"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Summarize local agent-policy friction")
    parser.add_argument("--since", default="14d")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--write-note", action="store_true")
    parser.add_argument("--note-path", type=Path, default=DEFAULT_NOTE)
    args = parser.parse_args(argv)

    report = summarize(log_path=args.log_path, since=args.since)
    if args.write_note:
        args.note_path.parent.mkdir(parents=True, exist_ok=True)
        args.note_path.write_text(
            "# Agent Policy Friction Review\n\n"
            f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"```text\n{report}\n```\n",
            encoding="utf-8",
        )
        print(f"Wrote {args.note_path}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
