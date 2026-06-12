#!/usr/bin/env python3
"""Research-event writer for the idea ledger.

Append a research note (and optionally clear markers) on one or more
existing ledger entries.

Usage:
    mature.py <slug> --summary S [--sources url1,url2,path]
                                 [--clear-needs-research]
                                 [--clear-underdeveloped]

    mature.py --batch <batch.json>

Batch shape:
    [
      {"slug": "...", "summary": "research: ...",
       "sources": ["...", "..."],
       "clear_needs_research": true,
       "clear_underdeveloped": false},
      ...
    ]

The `summary` is appended verbatim to the note event (with a "Sources: ..."
line appended if sources is non-empty). The `clear_*` flags emit a
marker event removing the marker if it is currently set.

Exit codes:
    0 success
    1 idea slug not found, or marker clearance requested for a marker
      that isn't present
    2 usage error
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


def _format_summary(summary: str, sources: list[str]) -> str:
    if not summary.lower().startswith("research:"):
        summary = "research: " + summary
    if sources:
        summary = summary.rstrip() + "\nSources: " + ", ".join(sources)
    return summary


def _append_note(ledger: Path, slug: str, summary: str) -> None:
    rec = {
        "record_kind": "event",
        "id": slug,
        "event_at": L.utc_now_iso(),
        "event_kind": "note",
        "summary": summary,
    }
    L.append_record(ledger, rec)


def _append_marker_removal(ledger: Path, slug: str, marker: str) -> None:
    rec = {
        "record_kind": "event",
        "id": slug,
        "event_at": L.utc_now_iso(),
        "event_kind": "marker",
        "markers_added": [],
        "markers_removed": [marker],
        "summary": f"research complete: removing {marker}",
    }
    L.append_record(ledger, rec)


def mature_one(
    ledger: Path,
    slug: str,
    summary: str,
    sources: list[str],
    clear_needs_research: bool,
    clear_underdeveloped: bool,
) -> dict:
    records = L.load_ledger(ledger)
    proj = L.project(records, slug)
    if proj is None:
        raise ValueError(f"no intake for {slug!r}")
    formatted = _format_summary(summary, sources)
    _append_note(ledger, slug, formatted)
    actions: list[str] = ["note_appended"]
    if clear_needs_research:
        if "needs-research" not in proj["quality_markers"]:
            actions.append("needs_research_not_set")
        else:
            _append_marker_removal(ledger, slug, "needs-research")
            actions.append("needs_research_cleared")
    if clear_underdeveloped:
        if "underdeveloped" not in proj["quality_markers"]:
            actions.append("underdeveloped_not_set")
        else:
            _append_marker_removal(ledger, slug, "underdeveloped")
            actions.append("underdeveloped_cleared")
    return {"slug": slug, "actions": actions}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Research-event writer")
    p.add_argument("slug", nargs="?")
    p.add_argument("--summary")
    p.add_argument("--sources", default="")
    p.add_argument("--clear-needs-research", action="store_true")
    p.add_argument("--clear-underdeveloped", action="store_true")
    p.add_argument("--batch", type=Path)
    p.add_argument("--json", action="store_true")
    p.add_argument("--project-root", type=Path, default=None,
                   help="Target project root owning .claude/ideas/log.jsonl "
                        "(default: git toplevel of cwd, else cwd)")
    args = p.parse_args(argv)

    ledger = resolve_project_root(args.project_root) / ".claude" / "ideas" / "log.jsonl"

    work: list[dict] = []

    if args.batch:
        if not args.batch.exists():
            print(f"error: batch file not found: {args.batch}", file=sys.stderr)
            return 2
        try:
            data = json.loads(args.batch.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"error: batch file is not valid JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(data, list):
            print("error: batch must be a JSON list", file=sys.stderr)
            return 2
        for entry in data:
            if not isinstance(entry, dict) or not entry.get("slug") or not entry.get("summary"):
                print("error: each batch entry needs slug + summary", file=sys.stderr)
                return 2
            work.append({
                "slug": entry["slug"],
                "summary": entry["summary"],
                "sources": list(entry.get("sources") or []),
                "clear_needs_research": bool(entry.get("clear_needs_research")),
                "clear_underdeveloped": bool(entry.get("clear_underdeveloped")),
            })
    else:
        if not args.slug or not args.summary:
            print(
                "usage: mature.py <slug> --summary S [--sources ...] "
                "[--clear-needs-research] [--clear-underdeveloped]",
                file=sys.stderr,
            )
            return 2
        work.append({
            "slug": args.slug,
            "summary": args.summary,
            "sources": [s.strip() for s in args.sources.split(",") if s.strip()],
            "clear_needs_research": args.clear_needs_research,
            "clear_underdeveloped": args.clear_underdeveloped,
        })

    results: list[dict] = []
    fatal = False
    for entry in work:
        try:
            result = mature_one(ledger, **entry)
            results.append(result)
        except ValueError as exc:
            results.append({"slug": entry["slug"], "error": str(exc)})
            fatal = True

    if args.json:
        print(json.dumps({"results": results}, indent=2, sort_keys=True))
    else:
        for r in results:
            if "error" in r:
                print(f"FAILED {r['slug']}: {r['error']}")
            else:
                print(f"{r['slug']}: {', '.join(r['actions'])}")
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
