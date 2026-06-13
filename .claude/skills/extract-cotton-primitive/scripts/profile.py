#!/usr/bin/env python
"""
Stage 1 of /extract-cotton-primitive: bundle representative callsites
for the propose-primitive scout.

Reads:
  --findings   reports/frontend-duplication/latest/findings.json (or arg)
  --candidates reports/frontend-duplication/latest/candidates.json (or arg)
  Either:
    --from-finding <id>  — pull candidate by id
    --category <name>    — pull the highest-priority candidate of category

  --project-root <path>
  --output     <profile.json>

Writes:
  profile.json with shape:
    {
      "target_slug": "<id-or-category>",
      "category": "<category>",
      "candidate": <full candidate>,
      "callsites": [
        {
          "file": "templates/...",
          "line": <int>,
          "context_before": "<10 lines>",
          "highlight": "<line at the cited line>",
          "context_after": "<20 lines>"
        }
      ]
    }

Stdlib only.
"""

import argparse
import json
import sys
from pathlib import Path


CONTEXT_BEFORE = 10
CONTEXT_AFTER = 20
MAX_CALLSITES = 6


def find_candidate(candidates, finding_id=None, category=None):
    if finding_id:
        for c in candidates:
            if c["id"] == finding_id:
                return c
        return None
    if category:
        # Highest-priority match (already sorted by rank)
        for c in candidates:
            if c.get("category") == category:
                return c
        return None
    return None


def load_callsite(project_root, file_rel, line_no):
    abs_path = project_root / file_rel
    if not abs_path.exists():
        return None
    try:
        lines = abs_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    if not lines or line_no < 1:
        return None
    idx = min(max(0, line_no - 1), len(lines) - 1)
    before_start = max(0, idx - CONTEXT_BEFORE)
    after_end = min(len(lines), idx + CONTEXT_AFTER + 1)
    return {
        "file": file_rel,
        "line": line_no,
        "context_before": "\n".join(lines[before_start:idx]),
        "highlight": lines[idx],
        "context_after": "\n".join(lines[idx + 1:after_end]),
    }


def gather_callsites(candidate, project_root, max_callsites=MAX_CALLSITES):
    occurrences = candidate.get("evidence", {}).get("occurrences", [])
    seen_files = set()
    callsites = []
    for occ in occurrences:
        f = occ.get("file")
        line = occ.get("line", 1)
        if not f:
            continue
        loaded = load_callsite(project_root, f, line)
        if not loaded:
            continue
        callsites.append(loaded)
        seen_files.add(f)
        if len(callsites) >= max_callsites:
            break
    return callsites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", type=Path)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--from-finding", type=str)
    parser.add_argument("--category", type=str)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.from_finding and not args.category:
        print("ERROR: must pass --from-finding or --category", file=sys.stderr)
        return 2

    candidates_source = args.candidates
    if not candidates_source and args.findings:
        # findings.json is the slim view; candidates.json is the rich view.
        # Prefer candidates.json for occurrences; fall back to findings.
        findings_dir = args.findings.parent
        cand = findings_dir / "candidates.json"
        if cand.exists():
            candidates_source = cand

    if not candidates_source or not candidates_source.exists():
        print(f"ERROR: candidates file not found: {candidates_source}",
              file=sys.stderr)
        return 1

    try:
        payload = json.loads(candidates_source.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read candidates file: {exc}", file=sys.stderr)
        return 1
    candidates = payload.get("candidates", [])

    candidate = find_candidate(candidates,
                                finding_id=args.from_finding,
                                category=args.category)
    if not candidate:
        print(f"ERROR: candidate not found "
              f"(finding={args.from_finding}, category={args.category})",
              file=sys.stderr)
        return 1

    callsites = gather_callsites(candidate, args.project_root.resolve())

    profile = {
        "target_slug": args.from_finding or args.category,
        "category": candidate.get("category"),
        "candidate": candidate,
        "callsite_count": len(callsites),
        "callsites": callsites,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2) + "\n",
                            encoding="utf-8")

    print(f"Profiled {candidate.get('category')} — {len(callsites)} "
          f"representative callsites loaded "
          f"(of {candidate.get('evidence', {}).get('occurrence_count', 0)} total)",
          file=sys.stderr)
    print(f"Wrote {args.output}")
    if not callsites:
        print(
            "ERROR: zero representative callsites loaded; "
            "profile artifact was written for inspection, aborting before scout",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
