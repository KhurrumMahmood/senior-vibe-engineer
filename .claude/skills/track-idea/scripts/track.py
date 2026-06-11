#!/usr/bin/env python3
"""Writer for the Tier 1 idea ledger.

Usage:
    track.py intake  <slug>  --title T --origin O --subsystem-kind K --summary S
                              [--state S] [--quality-markers a,b]
                              [--feeds-into a,b] [--composes-with a,b]
                              [--lineage-parents a,b] [--tags a,b]
                              [--hypothesis H]
    track.py event   <slug>  --kind {transition|marker|edge|adoption|dev-note|note}
                              [--from-state ...] [--to-state ...] [--outcome ...]
                              [--markers-added a,b] [--markers-removed a,b]
                              [--edges-added '{"feeds_into":["x"],...}']
                              [--adoption-evidence path]
                              [--summary ...]
    track.py lesson  <slug>  --title T --body B [--generalizes-to a,b]
    track.py list           [--state ...] [--marker ...] [--subsystem ...]
    track.py show    <id>   [--quiet-on-list-fields]

Exit codes:
    0 success
    1 validation / domain error (idea exists / missing intake / bad input)
    2 usage error

The ledger is .claude/ideas/log.jsonl. All timestamps are current UTC.
Schema lives at .claude/docs/idea-ledger.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude" / "skills" / "_common"))

import ideas_lib as L  # noqa: E402
from skill_use import log_event  # noqa: E402

LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"


def _csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [t.strip() for t in s.split(",") if t.strip()]


def _load() -> list[dict]:
    return L.load_ledger(LEDGER)


def _intake_for(records: list[dict], idea_id: str) -> dict | None:
    return next(
        (r for r in records if r.get("record_kind") == "intake" and r.get("id") == idea_id),
        None,
    )


def cmd_intake(args: argparse.Namespace) -> int:
    records = _load()
    if _intake_for(records, args.slug):
        print(f"error: intake already exists for {args.slug!r}; use 'event' or 'show'", file=sys.stderr)
        return 1
    now = L.utc_now_iso()
    rec: dict = {
        "record_kind": "intake",
        "id": args.slug,
        "title": args.title,
        "created_at": now,
        "origin": args.origin,
        "subsystem_kind": args.subsystem_kind,
        "state": args.state,
        "outcome": None,
        "quality_markers": _csv(args.quality_markers),
        "feeds_into": _csv(args.feeds_into),
        "composes_with": _csv(args.composes_with),
        "lineage_parents": _csv(args.lineage_parents),
        "lineage_children": [],
        "superseded_by": None,
        "adoption_count": 0,
        "generalizability": None,
        "last_event_at": now,
        "tags": _csv(args.tags),
        "summary": args.summary,
    }
    if args.hypothesis:
        rec["hypothesis"] = args.hypothesis
    errors = L.validate_record(rec)
    if errors:
        print(f"validation failed: {'; '.join(errors)}", file=sys.stderr)
        return 1
    L.append_record(LEDGER, rec)
    print(f"appended intake: {args.slug}")
    return 0


def cmd_event(args: argparse.Namespace) -> int:
    # --adoption-evidence is only meaningful on an 'adoption' event; on any other
    # kind it was silently dropped, so 'transition --to-state done --outcome adopted
    # --adoption-evidence ...' never recorded the adoption (adoption_count stayed 0
    # and the idea never graduated). Reject it loudly and point at the separate
    # event — track-idea keeps one record per event. Checked before any ledger read.
    if args.adoption_evidence and args.kind != "adoption":
        print(
            f"error: --adoption-evidence is only recorded on '--kind adoption' events, "
            f"not '--kind {args.kind}'. Record this {args.kind} first, then append a "
            f"separate adoption event: "
            f"event {args.slug} --kind adoption --adoption-evidence ...",
            file=sys.stderr,
        )
        return 2
    records = _load()
    intake = _intake_for(records, args.slug)
    if not intake:
        print(f"error: no intake for {args.slug!r}; create one with 'intake' first", file=sys.stderr)
        return 1
    proj = L.project(records, args.slug)
    if proj is None:
        print(f"error: projection failed for {args.slug!r}", file=sys.stderr)
        return 1

    now = L.utc_now_iso()
    rec: dict = {
        "record_kind": "event",
        "id": args.slug,
        "event_at": now,
        "event_kind": args.kind,
    }

    if args.kind == "transition":
        if not args.to_state:
            print("error: transition requires --to-state", file=sys.stderr)
            return 2
        rec["from_state"] = args.from_state or proj["state"]
        rec["to_state"] = args.to_state
        if args.to_state == "done":
            if not args.outcome:
                print(
                    "error: transition to done requires --outcome "
                    "(adopted|rejected|deferred|harvested|superseded)",
                    file=sys.stderr,
                )
                return 2
            rec["outcome"] = args.outcome
        elif args.outcome:
            rec["outcome"] = args.outcome
    elif args.kind == "marker":
        added = _csv(args.markers_added)
        removed = _csv(args.markers_removed)
        if not added and not removed:
            print("error: marker event requires --markers-added or --markers-removed", file=sys.stderr)
            return 2
        rec["markers_added"] = added
        rec["markers_removed"] = removed
    elif args.kind == "edge":
        if not args.edges_added:
            print("error: edge event requires --edges-added (JSON dict)", file=sys.stderr)
            return 2
        try:
            edges = json.loads(args.edges_added)
        except json.JSONDecodeError as exc:
            print(f"error: --edges-added is not valid JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(edges, dict):
            print("error: --edges-added must be a JSON object", file=sys.stderr)
            return 2
        rec["edges_added"] = edges
    elif args.kind == "adoption":
        if not args.adoption_evidence:
            print("error: adoption event requires --adoption-evidence", file=sys.stderr)
            return 2
        rec["adoption_evidence"] = args.adoption_evidence
        if args.summary:
            rec["summary"] = args.summary
    elif args.kind in ("dev-note", "note"):
        if not args.summary:
            print(f"error: {args.kind} event requires --summary", file=sys.stderr)
            return 2
        rec["summary"] = args.summary

    if args.summary and "summary" not in rec:
        rec["summary"] = args.summary

    errors = L.validate_record(rec)
    if errors:
        print(f"validation failed: {'; '.join(errors)}", file=sys.stderr)
        return 1
    L.append_record(LEDGER, rec)
    print(f"appended {args.kind} event for {args.slug}")
    return 0


def cmd_lesson(args: argparse.Namespace) -> int:
    records = _load()
    if not _intake_for(records, args.slug):
        print(f"error: no intake for {args.slug!r}; create one with 'intake' first", file=sys.stderr)
        return 1
    now = L.utc_now_iso()
    rec: dict = {
        "record_kind": "lesson",
        "id": args.slug,
        "lesson_at": now,
        "lesson_title": args.title,
        "lesson_body": args.body,
    }
    gen = _csv(args.generalizes_to)
    if gen:
        rec["generalizes_to"] = gen
    errors = L.validate_record(rec)
    if errors:
        print(f"validation failed: {'; '.join(errors)}", file=sys.stderr)
        return 1
    L.append_record(LEDGER, rec)
    print(f"appended lesson on {args.slug}: {args.title}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    records = _load()
    projs = L.project_all(records)
    if not projs:
        print("(no ideas captured yet)")
        return 0
    rows: list[tuple[str, str, str, str]] = []
    for idea_id in sorted(projs):
        proj = projs[idea_id]
        if args.state and proj["state"] != args.state:
            continue
        if args.marker and args.marker not in proj["quality_markers"]:
            continue
        if args.subsystem and proj["subsystem_kind"] != args.subsystem:
            continue
        markers = ",".join(proj["quality_markers"]) or "-"
        rows.append((idea_id, proj["state"], markers, proj["title"]))
    if not rows:
        print("(no ideas match the filter)")
        return 0
    width_id = max(len(r[0]) for r in rows)
    width_state = max(len(r[1]) for r in rows)
    width_markers = max(len(r[2]) for r in rows)
    for r in rows:
        print(f"{r[0]:<{width_id}}  {r[1]:<{width_state}}  {r[2]:<{width_markers}}  {r[3]}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    records = _load()
    proj = L.project(records, args.idea_id)
    if proj is None:
        print(f"error: no intake for {args.idea_id!r}", file=sys.stderr)
        return 1
    out: dict = {
        "id": proj["id"],
        "title": proj["title"],
        "state": proj["state"],
        "outcome": proj["outcome"],
        "subsystem_kind": proj["subsystem_kind"],
        "quality_markers": proj["quality_markers"],
        "adoption_count": proj["adoption_count"],
        "adoption_evidence": proj["adoption_evidence"],
        "feeds_into": proj["feeds_into"],
        "composes_with": proj["composes_with"],
        "lineage_parents": proj["lineage_parents"],
        "lineage_children": proj["lineage_children"],
        "superseded_by": proj["superseded_by"],
        "tags": proj["tags"],
        "created_at": proj["created_at"],
        "last_event_at": proj["last_event_at"],
        "summary": proj["summary"],
        "hypothesis": proj.get("hypothesis"),
        "lesson_count": len(proj["lessons"]),
    }
    if args.quiet_on_list_fields:
        out = {k: v for k, v in out.items() if not (isinstance(v, list) and not v)}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Idea ledger writer")
    sub = p.add_subparsers(dest="form", required=True)

    pi = sub.add_parser("intake", help="Append a new intake record")
    pi.add_argument("slug")
    pi.add_argument("--title", required=True)
    pi.add_argument("--origin", required=True)
    pi.add_argument("--subsystem-kind", required=True)
    pi.add_argument("--summary", required=True)
    pi.add_argument("--state", default="proposed", choices=sorted(L.VALID_STATES))
    pi.add_argument("--quality-markers")
    pi.add_argument("--feeds-into")
    pi.add_argument("--composes-with")
    pi.add_argument("--lineage-parents")
    pi.add_argument("--tags")
    pi.add_argument("--hypothesis")
    pi.set_defaults(func=cmd_intake)

    pe = sub.add_parser("event", help="Append an event record")
    pe.add_argument("slug")
    pe.add_argument("--kind", required=True, choices=sorted(L.VALID_EVENT_KINDS))
    pe.add_argument("--from-state", choices=sorted(L.VALID_STATES))
    pe.add_argument("--to-state", choices=sorted(L.VALID_STATES))
    pe.add_argument("--outcome", choices=sorted(L.VALID_OUTCOMES))
    pe.add_argument("--markers-added")
    pe.add_argument("--markers-removed")
    pe.add_argument("--edges-added")
    pe.add_argument("--adoption-evidence")
    pe.add_argument("--summary")
    pe.set_defaults(func=cmd_event)

    pl = sub.add_parser("lesson", help="Append a lesson record")
    pl.add_argument("slug")
    pl.add_argument("--title", required=True)
    pl.add_argument("--body", required=True)
    pl.add_argument("--generalizes-to")
    pl.set_defaults(func=cmd_lesson)

    pli = sub.add_parser("list", help="List ideas with optional filters")
    pli.add_argument("--state", choices=sorted(L.VALID_STATES))
    pli.add_argument("--marker", choices=sorted(L.VALID_MARKERS))
    pli.add_argument("--subsystem")
    pli.set_defaults(func=cmd_list)

    ps = sub.add_parser("show", help="Show one idea's projection")
    ps.add_argument("idea_id")
    ps.add_argument("--quiet-on-list-fields", action="store_true")
    ps.set_defaults(func=cmd_show)

    return p


def main(argv: list[str] | None = None) -> int:
    start = time.monotonic()
    args = build_parser().parse_args(argv)
    rc = args.func(args)
    target = (
        getattr(args, "slug", None)
        or getattr(args, "idea_id", None)
        or getattr(args, "form", "list")
    )
    log_event(
        skill="track-idea",
        target=str(target),
        artifact=str(LEDGER),
        elapsed_s=time.monotonic() - start,
    )
    return rc


def self_test() -> None:
    """Lock the loud guard: --adoption-evidence on a non-adoption event is
    rejected (exit 2), never silently dropped. Hermetic — the guard returns
    before any ledger read, so no fixture ledger is needed."""
    def _ns(**kw):
        base = dict(
            slug="selftest", kind=None, from_state=None, to_state=None,
            outcome=None, markers_added=None, markers_removed=None,
            edges_added=None, adoption_evidence=None, summary=None,
        )
        base.update(kw)
        return argparse.Namespace(**base)

    for kind in ("transition", "marker", "edge", "dev-note", "note"):
        ns = _ns(kind=kind, to_state="done", outcome="adopted",
                 adoption_evidence="app/x.py")
        assert cmd_event(ns) == 2, f"--adoption-evidence on {kind!r} must be rejected (got pass)"
    print("track self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        self_test()
        raise SystemExit(0)
    raise SystemExit(main())
