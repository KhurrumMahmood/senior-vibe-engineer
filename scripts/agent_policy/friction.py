#!/usr/bin/env python3
"""Friction telemetry for local agent policy hooks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO_ROOT / "logs" / "agent_policy" / "friction.jsonl"
GRANT_DECISIONS = ("grant_issued", "grant_consumed", "grant_expired", "grant_revoked")


def append_event(
    *,
    rule_id: str,
    decision: str,
    reason: str,
    summary: str = "",
    tool: str = "",
    event: str = "",
    source: str = "automatic",
    log_path: Path | None = None,
    now: datetime | None = None,
) -> None:
    path = log_path or DEFAULT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "tool": sanitize_text(tool, 80),
        "event": sanitize_text(event, 80),
        "rule_id": sanitize_text(rule_id, 120),
        "decision": sanitize_text(decision, 40),
        "reason": sanitize_text(reason, 280),
        "summary": sanitize_text(summary, 240),
        "source": sanitize_text(source, 80),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def sanitize_text(value: object, limit: int = 240) -> str:
    text = str(value or "")
    if "*** Begin Patch" in text or "diff --git" in text:
        return "<patch redacted>"
    text = text.replace("\n", " ")
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=\S+", r"\1=<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", text)
    text = re.sub(r"\b[A-Za-z0-9_/-]{48,}\b", "<redacted-token>", text)
    return text[:limit]


def summarize(
    *,
    log_path: Path | None = None,
    grants_path: Path | None = None,
    since: str = "14d",
    now: datetime | None = None,
) -> str:
    path = log_path or DEFAULT_LOG
    if not path.exists():
        return f"No friction events found at {path}."

    cutoff = (now or datetime.now(timezone.utc)) - parse_duration(since)
    events = [event for event in _read_events(path) if _event_time(event) >= cutoff]
    if not events:
        return f"No friction events since {since}."

    grant_events = [
        event for event in events if event.get("decision") in GRANT_DECISIONS
    ]
    policy_events = [
        event for event in events if event.get("decision") not in GRANT_DECISIONS
    ]

    by_rule = Counter(event.get("rule_id", "unknown") for event in policy_events)
    by_decision = Counter(event.get("decision", "unknown") for event in policy_events)
    explicit = [event for event in policy_events if event.get("source") == "explicit"]
    examples: dict[str, list[str]] = defaultdict(list)
    for event in policy_events:
        rule = event.get("rule_id", "unknown")
        summary_text = event.get("summary") or event.get("reason") or ""
        if summary_text and len(examples[rule]) < 3:
            examples[rule].append(summary_text)

    lines = [
        f"Policy events since {since}: {len(policy_events)}",
        "Decisions: "
        + ", ".join(f"{key}={value}" for key, value in sorted(by_decision.items())),
        "Most common rules:",
    ]
    for rule, count in by_rule.most_common(10):
        lines.append(f"- {rule}: {count}")
        for example in examples.get(rule, []):
            lines.append(f"  example: {example}")
    if explicit:
        lines.append("Explicit feedback:")
        for event in explicit[-10:]:
            lines.append(f"- {event.get('rule_id')}: {event.get('reason')}")

    lines.extend(_grants_section(grant_events, grants_path))
    return "\n".join(lines)


def _grants_section(grant_events: list[dict], grants_path: Path | None) -> list[str]:
    active_count = _count_active_grants(grants_path)
    if not grant_events and active_count == 0:
        return []

    consumed_by_rule = Counter(
        event.get("rule_id", "unknown")
        for event in grant_events
        if event.get("decision") == "grant_consumed"
    )
    lifecycle_counts = Counter(event.get("decision", "") for event in grant_events)

    lines = ["", f"Grants: {active_count} active"]
    lifecycle = ", ".join(
        f"{name}={lifecycle_counts.get(name, 0)}" for name in GRANT_DECISIONS
    )
    lines.append(f"  Lifecycle: {lifecycle}")
    if consumed_by_rule:
        lines.append("  Consumed (top 5):")
        for rule, count in consumed_by_rule.most_common(5):
            lines.append(f"    - {rule}: {count}")
    return lines


def _count_active_grants(grants_path: Path | None) -> int:
    # Local import keeps friction.py importable even if grants.py is absent
    # (grants was added later; some operational scripts predate it).
    try:
        from scripts.agent_policy.grants import load_grants, prune_expired
    except ImportError:
        return 0
    kept, _ = prune_expired(load_grants(grants_path))
    return len(kept)


def parse_duration(value: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([dhm])", value.strip())
    if not match:
        raise ValueError("duration must look like 14d, 12h, or 30m")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "h":
        return timedelta(hours=amount)
    return timedelta(minutes=amount)


def _read_events(path: Path) -> Iterable[dict]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            yield data


def _event_time(event: dict) -> datetime:
    try:
        return datetime.fromisoformat(event.get("timestamp", ""))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Record or summarize local agent-policy friction")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report")
    report.add_argument("--rule", required=True)
    report.add_argument("--message", required=True)
    report.add_argument("--tool", default="")
    report.add_argument("--event", default="")

    summary = subparsers.add_parser("summarize")
    summary.add_argument("--since", default="14d")
    summary.add_argument(
        "--grants-path",
        type=Path,
        default=None,
        help="Override grants file path (default: .claude/agent_policy_grants.json).",
    )

    args = parser.parse_args(argv)
    if args.command == "report":
        append_event(
            rule_id=args.rule,
            decision="feedback",
            reason=args.message,
            summary="explicit friction report",
            tool=args.tool,
            event=args.event,
            source="explicit",
            log_path=args.log_path,
        )
        print(f"Recorded friction feedback for {args.rule}.")
        return 0
    if args.command == "summarize":
        print(
            summarize(
                log_path=args.log_path,
                grants_path=args.grants_path,
                since=args.since,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
