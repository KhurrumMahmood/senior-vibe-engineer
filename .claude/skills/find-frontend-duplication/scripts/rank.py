#!/usr/bin/env python
"""
Stage 3 of /find-frontend-duplication: rank candidates into P0/P1/P2.

Reads:
  --input  candidates.json
Writes:
  --output ranked.json — same candidates, with rank_meta block:
                        {priority: P0|P1|P2|skip, score: float,
                         reason: str}, sorted highest priority first.

Scoring rubric (additive):
  + occurrence_count
  + 2 × file_count
  + 10 if primitive_bypass (we already have a c-* primitive — adoption
    gap, not extraction work)
  + 5 if category in {csrf-fetch, helper-fork} (cross-file blast radius)
  − 100 if category == layout-utility (downgrade to skip)

Bucketing:
  score >= 30 -> P0
  score >= 15 -> P1
  score >= 6  -> P2
  else        -> skip
"""

import argparse
import json
import sys
from pathlib import Path


def score(candidate):
    occ = candidate["evidence"]["occurrence_count"]
    files = candidate["evidence"]["file_count"]
    s = occ + 2 * files
    if candidate.get("primitive_bypass"):
        s += 10
    if candidate.get("category") in {"csrf-fetch", "helper-fork",
                                      "implicit-cross-file-dependency"}:
        s += 5
    if candidate.get("category") == "layout-utility":
        s -= 100
    return s


def bucket(score_value):
    if score_value < 0:
        return "skip"
    if score_value >= 30:
        return "P0"
    if score_value >= 15:
        return "P1"
    if score_value >= 6:
        return "P2"
    return "skip"


def reason_for(candidate, score_value, priority):
    parts = [
        f"{candidate['evidence']['occurrence_count']} occurrences",
        f"{candidate['evidence']['file_count']} files",
    ]
    if candidate.get("primitive_bypass"):
        parts.append(f"<c-{candidate['existing_primitive']['name']}/> exists but is bypassed")
    if candidate.get("category") == "layout-utility":
        parts.append("layout-utility (skip — Tailwind atoms, not extractable)")
    return f"{priority} ({score_value}): " + ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.input.read_text())
    for c in data["candidates"]:
        s = score(c)
        p = bucket(s)
        c["rank_meta"] = {
            "priority": p,
            "score": s,
            "reason": reason_for(c, s, p),
        }

    data["candidates"].sort(
        key=lambda c: (
            {"P0": 0, "P1": 1, "P2": 2, "skip": 3}[c["rank_meta"]["priority"]],
            -c["rank_meta"]["score"],
        )
    )

    counts = {"P0": 0, "P1": 0, "P2": 0, "skip": 0}
    for c in data["candidates"]:
        counts[c["rank_meta"]["priority"]] += 1
    data["priority_counts"] = counts

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} (P0={counts['P0']}, P1={counts['P1']}, "
          f"P2={counts['P2']}, skip={counts['skip']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
