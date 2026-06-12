#!/usr/bin/env python3
"""Bulk intake writer for the idea ledger.

Takes a JSON file containing a list of candidate intake dicts, dedupes
against the existing ledger by slug, validates the survivors, and
writes them as new intake records with state=proposed (unless
overridden).

Usage:
    brainstorm.py <batch.json> [--dry-run] [--json]

Batch shape:
    [
      {"slug": "...", "title": "...", "subsystem_kind": "...",
       "summary": "...", "origin": "AI-suggestion",
       "hypothesis": "...", "quality_markers": ["underdeveloped"],
       "tags": ["..."], "composes_with": [], ...},
      ...
    ]

Required per candidate: slug, title, subsystem_kind, summary, origin.
Optional: hypothesis, quality_markers, tags, composes_with, feeds_into,
lineage_parents, state (default proposed).

Exit codes:
    0 success (writes may be 0 if all duplicates)
    1 validation failure on at least one candidate
    2 usage error (file missing, malformed JSON, not a list)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# KIT_ROOT anchors kit-relative imports ONLY. The ledger is a target-project
# surface and anchors on --project-root instead — the kit may live in a
# different repo than the target project (de-baking convention, ADR 0024).
KIT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(KIT_ROOT / ".claude" / "skills" / "_common"))

import ideas_lib as L  # noqa: E402
from diff_resolution import resolve_project_root  # noqa: E402

REQUIRED_FIELDS = ("slug", "title", "subsystem_kind", "summary", "origin")


def build_intake(candidate: dict) -> dict:
    now = L.utc_now_iso()
    rec: dict = {
        "record_kind": "intake",
        "id": candidate["slug"],
        "title": candidate["title"],
        "created_at": now,
        "origin": candidate["origin"],
        "subsystem_kind": candidate["subsystem_kind"],
        "state": candidate.get("state", "proposed"),
        "outcome": None,
        "quality_markers": list(candidate.get("quality_markers") or []),
        "feeds_into": list(candidate.get("feeds_into") or []),
        "composes_with": list(candidate.get("composes_with") or []),
        "lineage_parents": list(candidate.get("lineage_parents") or []),
        "lineage_children": [],
        "superseded_by": None,
        "adoption_count": 0,
        "generalizability": None,
        "last_event_at": now,
        "tags": list(candidate.get("tags") or []),
        "summary": candidate["summary"],
    }
    if candidate.get("hypothesis"):
        rec["hypothesis"] = candidate["hypothesis"]
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bulk intake writer")
    p.add_argument("batch_file", type=Path)
    p.add_argument("--dry-run", action="store_true",
                   help="Validate and dedupe without writing")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON summary instead of human-readable text")
    p.add_argument("--project-root", type=Path, default=None,
                   help="Target project root owning .claude/ideas/log.jsonl "
                        "(default: git toplevel of cwd, else cwd)")
    args = p.parse_args(argv)

    ledger = resolve_project_root(args.project_root) / ".claude" / "ideas" / "log.jsonl"

    if not args.batch_file.exists():
        print(f"error: batch file not found: {args.batch_file}", file=sys.stderr)
        return 2

    try:
        batch = json.loads(args.batch_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: batch file is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(batch, list):
        print("error: batch file must be a JSON list", file=sys.stderr)
        return 2

    for i, c in enumerate(batch):
        if not isinstance(c, dict):
            print(f"error: candidate {i} is not a JSON object", file=sys.stderr)
            return 2
        missing = [f for f in REQUIRED_FIELDS if not c.get(f)]
        if missing:
            print(
                f"error: candidate {i} ({c.get('slug', '<no-slug>')!r}) "
                f"missing required fields: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

    records = L.load_ledger(ledger)
    existing_slugs = {r["id"] for r in records if r.get("record_kind") == "intake"}

    written: list[str] = []
    skipped_duplicate: list[str] = []
    validation_failures: list[tuple[str, list[str]]] = []

    for c in batch:
        slug = c["slug"]
        if slug in existing_slugs:
            skipped_duplicate.append(slug)
            continue
        rec = build_intake(c)
        errors = L.validate_record(rec)
        if errors:
            validation_failures.append((slug, errors))
            continue
        if not args.dry_run:
            L.append_record(ledger, rec)
        written.append(slug)

    if args.json:
        print(json.dumps({
            "written": written,
            "skipped_duplicate": skipped_duplicate,
            "validation_failures": [
                {"slug": s, "errors": errs} for s, errs in validation_failures
            ],
            "dry_run": args.dry_run,
        }, indent=2, sort_keys=True))
    else:
        verb = "would write" if args.dry_run else "wrote"
        print(f"{verb} {len(written)} intake(s):")
        for s in written:
            print(f"  - {s}")
        if skipped_duplicate:
            print(f"skipped {len(skipped_duplicate)} duplicate slug(s):")
            for s in skipped_duplicate:
                print(f"  - {s}")
        if validation_failures:
            print(f"validation failed on {len(validation_failures)}:")
            for s, errs in validation_failures:
                print(f"  - {s}: {'; '.join(errs)}")
    return 1 if validation_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
