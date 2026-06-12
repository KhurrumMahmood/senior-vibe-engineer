#!/usr/bin/env python3
"""Staged-work queue — stage, list, and surface packet-compatible work items.

The queue is the first executable implementation of ADR 0036's packet
concept (ADR 0037 §4). Items are plain agent-neutral JSON files, one per
staged work item, under `.engineering/local/queue/`. Any agent (or a
human) can read them; nothing here is Claude-specific except the `hook`
subcommand's output convention.

Contract (full prose: .claude/docs/queue-contract.md):
  packet fields (ADR 0036): scope (file list), recipe, verification
  (command), expected_delta, token_budget
  queue metadata: staged_at (UTC ISO), status (staged|picked|done),
  origin (chain/proposal/plan ref)

Manual-pickup floor for any agent:
  python3 scripts/queue_status.py list

Claude Code session-start hook (optional wiring, settings.json):
  {"hooks": {"SessionStart": [{"hooks": [{"type": "command",
    "command": "python3 scripts/queue_status.py hook"}]}]}}

Source decision: `core:status-projection-schema` (ADR 0037).
"""
# spec:status-projection-and-presentation::IM-8
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

QUEUE_STATUSES = ("staged", "picked", "done")


def queue_dir(root: Path) -> Path:
    return root / ".engineering" / "local" / "queue"


def read_items(root: Path) -> list[dict]:
    qdir = queue_dir(root)
    if not qdir.is_dir():
        return []
    items = []
    for path in sorted(qdir.glob("*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            item = {"status": "unreadable"}
        item["id"] = path.stem
        items.append(item)
    return items


def stage_item(
    root: Path,
    item_id: str,
    *,
    recipe: str,
    scope: list[str],
    verification: str | None = None,
    expected_delta: str | None = None,
    token_budget: int | None = None,
    origin: str | None = None,
) -> Path:
    qdir = queue_dir(root)
    qdir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-")
    if not safe_id:
        raise ValueError(f"item id {item_id!r} reduces to an empty slug")
    payload = {
        "recipe": recipe,
        "scope": sorted(scope),
        "verification": verification,
        "expected_delta": expected_delta,
        "token_budget": token_budget,
        "origin": origin,
        "status": "staged",
        "staged_at": datetime.now(timezone.utc).isoformat(),
    }
    path = qdir / f"{safe_id}.json"
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def cmd_list(root: Path) -> int:
    items = read_items(root)
    if not items:
        print("queue empty")
        return 0
    for item in items:
        scope_n = len(item.get("scope") or [])
        print(
            f"{item['id']}  [{item.get('status', '?')}]  "
            f"{item.get('recipe', '(no recipe)')}  "
            f"({scope_n} file(s); staged {item.get('staged_at', '?')})"
        )
    pending = [i for i in items if i.get("status") == "staged"]
    print(f"\n{len(pending)} staged of {len(items)} total. "
          f"Pick up: read .engineering/local/queue/<id>.json, do the recipe over "
          f"its scope, run its verification, then set its status to done.")
    return 0


# Stale-plan surfacing (consistency-session-execution W-G): the same
# session-start hook also flags non-terminal plans gone silent, so a plan
# can't quietly evaporate between sessions. This is the cheap surfacer —
# /find-orphaned-ideas --stale-plans stays the authoritative detector.
PLAN_NON_TERMINAL = ("draft", "proposed", "scoped", "impacted", "architected")
_PLAN_STATUS_RE = re.compile(r"^status:\s*([a-z-]+)\s*$", re.MULTILINE)
STALE_PLAN_DAYS = 14


def stale_plans(root: Path, days: int = STALE_PLAN_DAYS) -> list[tuple[str, str]]:
    plans_dir = root / "ai-docs" / "plans"
    if not plans_dir.is_dir():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    out = []
    for path in sorted(plans_dir.glob("*.md")):
        if path.name == "README.md" or path.stat().st_mtime > cutoff:
            continue
        try:
            head = path.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            continue  # noqa: silent-catch: unreadable plan is find-orphaned-ideas' problem, not the hook's
        m = _PLAN_STATUS_RE.search(head)
        if m and m.group(1) in PLAN_NON_TERMINAL:
            out.append((path.stem, m.group(1)))
    return out


def cmd_hook(root: Path) -> int:
    """Session-start hook: one line per concern when there is one, else silence."""
    pending = [i for i in read_items(root) if i.get("status") == "staged"]
    if pending:
        ids = ", ".join(i["id"] for i in pending[:5])
        more = f" (+{len(pending) - 5} more)" if len(pending) > 5 else ""
        print(
            f"[queue] {len(pending)} staged work item(s) pending: {ids}{more} — "
            f"run `python3 scripts/queue_status.py list` to pick up."
        )
    silent = stale_plans(root)
    if silent:
        listed = ", ".join(f"{name} ({status})" for name, status in silent[:5])
        more = f" (+{len(silent) - 5} more)" if len(silent) > 5 else ""
        print(
            f"[plans] {len(silent)} non-terminal plan(s) silent >{STALE_PLAN_DAYS}d: "
            f"{listed}{more} — run `/find-orphaned-ideas --stale-plans`."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List queue items (the manual-pickup floor).")
    sub.add_parser("hook", help="Session-start hook: report pending count.")
    stage = sub.add_parser("stage", help="Stage a packet-compatible work item.")
    stage.add_argument("item_id")
    stage.add_argument("--recipe", required=True)
    stage.add_argument("--scope", action="append", default=[], metavar="PATH")
    stage.add_argument("--verification", default=None)
    stage.add_argument("--expected-delta", default=None)
    stage.add_argument("--token-budget", type=int, default=None)
    stage.add_argument("--origin", default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.cmd == "list":
        return cmd_list(root)
    if args.cmd == "hook":
        return cmd_hook(root)
    try:
        path = stage_item(
            root, args.item_id, recipe=args.recipe, scope=args.scope,
            verification=args.verification, expected_delta=args.expected_delta,
            token_budget=args.token_budget, origin=args.origin,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"staged: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
