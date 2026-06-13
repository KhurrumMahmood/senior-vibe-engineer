#!/usr/bin/env python3
"""Filter an extracted idea-candidate batch to the approved survivor set.

The /extract-existing-ideas orchestrator uses this after user review so the
writer stage receives exactly the approved candidates, not the original noisy
extraction batch.

Usage:
    filter_candidates.py --candidates reports/.../extract-candidates.json \\
      --keep-slugs slug-a,slug-b \\
      --out reports/.../approved-candidates.json

Exit codes:
    0 approved batch written
    1 no approved candidates remain
    2 malformed input or usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_slugs(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument(
        "--keep-slugs",
        required=True,
        help="Comma-separated candidate slugs approved for the writer stage",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    keep = _parse_slugs(args.keep_slugs)
    if not keep:
        print("error: --keep-slugs resolved to an empty set", file=sys.stderr)
        return 1

    if not args.candidates.exists():
        print(f"error: candidates file not found: {args.candidates}", file=sys.stderr)
        return 2

    try:
        payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read candidates JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, list):
        print("error: candidates JSON must be a list", file=sys.stderr)
        return 2

    survivors: list[dict] = []
    seen: set[str] = set()
    for index, candidate in enumerate(payload):
        if not isinstance(candidate, dict):
            print(f"error: candidate {index} is not an object", file=sys.stderr)
            return 2
        slug = candidate.get("slug")
        if not isinstance(slug, str) or not slug:
            print(f"error: candidate {index} has no slug", file=sys.stderr)
            return 2
        if slug in keep:
            survivors.append(candidate)
            seen.add(slug)

    missing = sorted(keep - seen)
    if missing:
        print(
            "error: approved slug(s) not present in candidates: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    if not survivors:
        print("error: no approved candidates remain", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(survivors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(survivors)} approved candidate(s) to {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
