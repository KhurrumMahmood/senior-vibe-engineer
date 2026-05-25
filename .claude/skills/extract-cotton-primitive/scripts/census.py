#!/usr/bin/env python
"""
Stage 1.5 of /extract-cotton-primitive: census the candidate's full
callsite population so the propose scout can reconcile primitive
defaults against the dominant variant.

Reads the same candidate the profiler reads, then buckets every
occurrence by its canonical token chain. Output is a histogram —
"how many callsites use shape A vs shape B vs the long tail".

The proposal scout uses this to decide whether the proposed (or
existing) primitive's defaults match the dominant variant, or whether
the doctrine call is "change the primitive defaults *first*, then
sweep" (the `<c-alert>` lesson — primitive shipped with `px-4 py-3`
while 104 callsites used `p-4`; default was changed before sweep to
keep the dominant variant lint-clean).

Reads:
  --candidates reports/frontend-duplication/latest/candidates.json
  Either:
    --from-finding <id>
    --category <name>
  --project-root <path>
  --output     <census.json>

Writes:
  census.json with shape:
    {
      "target_slug": ...,
      "category": ...,
      "candidate_id": ...,
      "scan_count": <occurrence_count from candidate evidence>,
      "scan_file_count": <file_count from candidate evidence>,
      "occurrences_in_sample": <count of occurrences this script saw>,
      "sample_only": <bool — true if scan_count > occurrences_in_sample>,
      "variant_histogram": [
        {
          "variant": "<canonical token chain>",
          "count": N,
          "share": 0.62,
          "sample_files": ["templates/...", ...],
          "samples": [{"file":..., "line":..., "raw":...}, ...]
        },
        ...  # sorted by count desc
      ],
      "dominant_variant": "<canonical token chain>",
      "dominant_share": 0.62,
      "tail_count": <count outside dominant>,
      "high_variance": <bool — true if dominant_share < 0.6>,
      "existing_primitive": <passthrough from candidate>,
      "primitive_bypass": <passthrough from candidate>
    }

  When sample_only is true, the candidate's per-occurrence sample is
  smaller than the full scan count — the histogram represents only the
  sampled subset. The propose scout should treat dominance and variance
  as lower-bound estimates and consider re-grepping the chain across
  the full template tree before committing to a doctrine call.

Stdlib only.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


HIGH_VARIANCE_THRESHOLD = 0.6

# Tone-family Tailwind utilities the doctrine collapses under `{tone}`.
# bg-yellow-50, text-red-800, border-blue-200 → bg-{tone}-50 etc.
_TONE_PREFIXES = (
    "bg", "text", "border", "ring", "from", "to", "via",
    "divide", "placeholder", "decoration", "outline", "shadow",
)
_TONE_FAMILIES = (
    "gray", "slate", "zinc", "neutral", "stone",
    "red", "orange", "amber", "yellow", "lime",
    "green", "emerald", "teal", "cyan", "sky",
    "blue", "indigo", "violet", "purple", "fuchsia",
    "pink", "rose",
)
_TONE_RE = re.compile(
    rf"^({'|'.join(_TONE_PREFIXES)})-({'|'.join(_TONE_FAMILIES)})-(\d+)$"
)


def find_candidate(candidates, finding_id=None, category=None):
    if finding_id:
        return next((c for c in candidates if c["id"] == finding_id), None)
    if category:
        return next((c for c in candidates if c.get("category") == category), None)
    return None


def canonical_variant(tokens):
    """Sort + dedup tokens; collapse tone-family suffixes to `{tone}`.

    `bg-yellow-50 text-yellow-800 p-4` → `bg-{tone}-50 p-4 text-{tone}-800`.
    The collapse is so two callsites that differ only by tone (yellow vs
    red alert) share a canonical variant — tone is a prop, not a shape
    axis.
    """
    norm = []
    for t in sorted(set(tokens)):
        m = _TONE_RE.match(t)
        if m:
            prefix, _, shade = m.groups()
            norm.append(f"{prefix}-{{tone}}-{shade}")
        else:
            norm.append(t)
    return " ".join(norm)


def bucket_occurrences(occurrences):
    buckets = defaultdict(lambda: {"count": 0, "files": set(), "samples": []})
    for occ in occurrences:
        tokens = occ.get("tokens", [])
        if not tokens:
            continue
        key = canonical_variant(tokens)
        b = buckets[key]
        b["count"] += 1
        if occ.get("file"):
            b["files"].add(occ["file"])
        if len(b["samples"]) < 3:
            b["samples"].append({
                "file": occ.get("file"),
                "line": occ.get("line"),
                "raw": occ.get("raw"),
            })
    return buckets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--from-finding", default=None)
    ap.add_argument("--category", default=None)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    if not args.from_finding and not args.category:
        print("error: pass --from-finding or --category", file=sys.stderr)
        sys.exit(2)

    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        print(f"error: candidates file missing: {candidates_path}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(candidates_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read candidates file: {exc}", file=sys.stderr)
        sys.exit(1)
    candidates = raw.get("candidates", raw) if isinstance(raw, dict) else raw

    candidate = find_candidate(
        candidates,
        finding_id=args.from_finding,
        category=args.category,
    )
    if candidate is None:
        ident = args.from_finding or args.category
        print(f"error: candidate not found: {ident}", file=sys.stderr)
        sys.exit(1)

    evidence = candidate.get("evidence") or {}
    occurrences = evidence.get("occurrences") or []

    buckets = bucket_occurrences(occurrences)
    total = sum(b["count"] for b in buckets.values())

    histogram = []
    for variant, b in buckets.items():
        histogram.append({
            "variant": variant,
            "count": b["count"],
            "share": round(b["count"] / total, 3) if total else 0.0,
            "sample_files": sorted(b["files"])[:5],
            "samples": b["samples"],
        })
    histogram.sort(key=lambda h: h["count"], reverse=True)

    dominant = histogram[0] if histogram else {
        "variant": "", "count": 0, "share": 0.0,
    }
    high_variance = dominant["share"] < HIGH_VARIANCE_THRESHOLD
    tail_count = total - dominant["count"]

    scan_count = evidence.get("occurrence_count", total)
    sample_only = total < scan_count

    output = {
        "target_slug": args.from_finding or args.category,
        "category": candidate.get("category"),
        "candidate_id": candidate.get("id"),
        "candidate_title": candidate.get("title"),
        "scan_count": scan_count,
        "scan_file_count": evidence.get("file_count"),
        "occurrences_in_sample": total,
        "sample_only": sample_only,
        "variant_histogram": histogram,
        "dominant_variant": dominant["variant"],
        "dominant_share": dominant["share"],
        "tail_count": tail_count,
        "high_variance": high_variance,
        "existing_primitive": candidate.get("existing_primitive"),
        "primitive_bypass": candidate.get("primitive_bypass"),
    }

    Path(args.output).write_text(json.dumps(output, indent=2))

    label = "HIGH-VARIANCE" if high_variance else "tight"
    sample_note = (
        f" [sample-only: {total}/{scan_count}]" if sample_only else ""
    )
    summary = (
        f"{candidate.get('category')} — {total} occurrences in "
        f"{len(histogram)} variant(s); dominant {dominant['share']:.0%} "
        f"({label}){sample_note}"
    )
    print(summary, file=sys.stderr)


if __name__ == "__main__":
    main()
