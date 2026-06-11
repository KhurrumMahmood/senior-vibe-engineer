#!/usr/bin/env python3
"""Candidate emitter for /extract-existing-ideas.

Wraps ideas_lib.extract_candidates: walks the named root for prose
surfaces (BACKLOG.md, lessons.md), produces candidate intake dicts,
classifies each as NEW or COLLIDE against the existing ledger, and
emits a report + a candidates JSON file the user can hand to
brainstorm.py.

Usage:
    extract.py [<root>] [--source backlog|lessons|both]
               [--out <path>] [--json] [--include-collisions]

Exit codes:
    0 success (at least one candidate emitted)
    1 no candidates found
    2 usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude" / "skills" / "_common"))

import ideas_lib as L  # noqa: E402

LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"
DEFAULT_OUT = REPO_ROOT / ".claude" / "ideas" / "extract-candidates.json"


def classify(candidates: list[dict], existing_slugs: set[str]) -> tuple[list[dict], list[dict]]:
    new: list[dict] = []
    collide: list[dict] = []
    for c in candidates:
        if c["slug"] in existing_slugs:
            collide.append(c)
        else:
            new.append(c)
    return new, collide


def filter_by_source(candidates: list[dict], source: str) -> list[dict]:
    if source == "both":
        return candidates
    if source == "backlog":
        return [c for c in candidates if c.get("source_kind") == "backlog"]
    if source == "lessons":
        return [c for c in candidates if c.get("source_kind") == "lesson"]
    return candidates


def render_markdown(root: Path, new: list[dict], collide: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# Extract candidates (root: {root})")
    lines.append("")
    lines.append(f"Found {len(new)} NEW, {len(collide)} WOULD-COLLIDE.")
    by_source: dict[str, list[dict]] = {}
    for c in new:
        by_source.setdefault(c.get("source_kind", "?"), []).append(c)
    for kind in sorted(by_source):
        lines.append("")
        lines.append(f"## NEW from {kind}")
        for c in by_source[kind]:
            tags = ",".join(c.get("tags") or [])
            lines.append(f"- `{c['slug']}` — {c['title']}  [{c['subsystem_kind']}]  ({tags})")
    if collide:
        lines.append("")
        lines.append("## WOULD-COLLIDE (existing slugs)")
        for c in collide:
            lines.append(f"- `{c['slug']}` — {c['title']}  (use /track-idea event instead)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Candidate emitter")
    p.add_argument("root", nargs="?", default=".")
    p.add_argument("--source", choices=("backlog", "lessons", "both"), default="both")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-collisions", action="store_true",
                   help="Include colliding candidates in the JSON output file")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    raw = L.extract_candidates(root)
    candidates = filter_by_source(raw, args.source)

    records = L.load_ledger(LEDGER)
    existing_slugs = {r["id"] for r in records if r.get("record_kind") == "intake"}

    new, collide = classify(candidates, existing_slugs)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = list(new) if not args.include_collisions else list(new) + list(collide)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    try:
        out_display = str(args.out.relative_to(REPO_ROOT))
    except ValueError:
        out_display = str(args.out)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "out": str(args.out),
            "new": new,
            "collide": collide,
            "counts": {"new": len(new), "collide": len(collide)},
        }, indent=2, sort_keys=True))
    else:
        print(render_markdown(root, new, collide))
        print()
        print(f"Wrote {len(payload)} candidate(s) to {out_display}")
        if new:
            print("Hand off to brainstorm.py to write:")
            print(f"  .venv/bin/python .claude/skills/brainstorm-ideas/scripts/brainstorm.py {out_display}")
    return 0 if (new or collide) else 1


if __name__ == "__main__":
    raise SystemExit(main())
