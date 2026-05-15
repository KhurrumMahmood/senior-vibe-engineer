#!/usr/bin/env python3
"""Group implicit-state detector output into per-file candidates.

Reads the ``hits.jsonl`` produced by ``detect.py`` and emits a
``candidates.jsonl`` where each record corresponds to one ``(file,
pattern)`` bucket. Confidence tier is assigned based on the hit pattern
and density:

- ``tuple_identity``: always ``high`` — this shape is rare and
  distinctive; every hit is worth a scout.
- ``stringly_compare``: ``high`` when >=3 hits in a single file on the
  same field; else ``medium``.
- ``stringly_field``: always ``medium`` — every hit is worth reviewing,
  but the lint rule is the primary guard.
- ``possible_state_literal``: ``low`` unless the same file also has a
  ``stringly_compare`` hit — then upgraded to ``medium``.

Scouts should prioritize high > medium > low.

Output shape (one JSON record per line at ``--output``):

    {
      "candidate_id": "implicit-state-0001",
      "file": "core/views/crawling.py",
      "pattern": "stringly_compare",
      "confidence": "high",
      "hit_count": 5,
      "hits": [ { ... detector record ... }, ... ],
      "fields_touched": ["status"],
      "symbols": ["bulk_crawl_collection_task"],
      "recommendation_hint": "extract_enum_candidate"
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# Pattern → default recommendation-hint mapping. These are hints only —
# the scout reads the full context to decide. Mapping matches the
# bucket names the scout uses when writing its assessment.
PATTERN_TO_HINT: dict[str, str] = {
    "tuple_identity": "introduce_fk_candidate",
    "stringly_compare": "extract_enum_candidate",
    "stringly_field": "extract_enum_candidate",
    "possible_state_literal": "extract_enum_candidate",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _confidence(
    pattern: str,
    hits: list[dict[str, Any]],
    file_has_compare: bool,
) -> str:
    if pattern == "tuple_identity":
        return "high"
    if pattern == "stringly_compare":
        by_field: dict[str, int] = defaultdict(int)
        for h in hits:
            f = h.get("field", "?")
            by_field[f] += 1
        if any(count >= 3 for count in by_field.values()):
            return "high"
        return "medium"
    if pattern == "stringly_field":
        return "medium"
    if pattern == "possible_state_literal":
        return "medium" if file_has_compare else "low"
    return "low"


def _fields_touched(hits: list[dict[str, Any]]) -> list[str]:
    out: set[str] = set()
    for h in hits:
        f = h.get("field")
        if isinstance(f, str):
            out.add(f)
    return sorted(out)


def _symbols_touched(hits: list[dict[str, Any]]) -> list[str]:
    out: set[str] = set()
    for h in hits:
        s = h.get("symbol")
        if isinstance(s, str):
            out.add(s)
    return sorted(out)


def _collapse(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Bucket by (file, pattern). Preserve detector-hit order inside each
    # bucket so evidence lines stay in source order.
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    files_with_compare: set[str] = set()
    for hit in hits:
        file = hit.get("file", "")
        pattern = hit.get("pattern", "")
        if not file or not pattern:
            continue
        by_group[(file, pattern)].append(hit)
        if pattern == "stringly_compare":
            files_with_compare.add(file)

    candidates: list[dict[str, Any]] = []
    # Deterministic ordering: file asc, pattern asc (tuple first).
    pattern_priority = {
        "tuple_identity": 0,
        "stringly_compare": 1,
        "stringly_field": 2,
        "possible_state_literal": 3,
    }
    ordered_keys = sorted(
        by_group.keys(),
        key=lambda k: (pattern_priority.get(k[1], 99), k[0]),
    )
    for i, (file, pattern) in enumerate(ordered_keys, start=1):
        bucket = by_group[(file, pattern)]
        confidence = _confidence(
            pattern, bucket, file in files_with_compare,
        )
        candidates.append({
            "candidate_id": f"implicit-state-{i:04d}",
            "file": file,
            "pattern": pattern,
            "confidence": confidence,
            "hit_count": len(bucket),
            "hits": bucket,
            "fields_touched": _fields_touched(bucket),
            "symbols": _symbols_touched(bucket),
            "recommendation_hint": PATTERN_TO_HINT.get(pattern, "review"),
        })
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hits", required=True, type=Path,
                        help="Input hits.jsonl from detect.py")
    parser.add_argument("--output", required=True, type=Path,
                        help="Output candidates.jsonl")
    args = parser.parse_args(argv)

    hits = _read_jsonl(args.hits)
    candidates = _collapse(hits)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for c in candidates:
            fh.write(json.dumps(c, sort_keys=True) + "\n")

    # Summary to stderr for orchestrator.
    by_conf: dict[str, int] = defaultdict(int)
    by_pattern: dict[str, int] = defaultdict(int)
    for c in candidates:
        by_conf[c["confidence"]] += 1
        by_pattern[c["pattern"]] += 1
    print(
        f"[collapse_implicit_state] hits={len(hits)} "
        f"candidates={len(candidates)} "
        f"by_confidence={dict(by_conf)} "
        f"by_pattern={dict(by_pattern)}",
        file=sys.stderr,
    )
    print(
        f"[collapse_implicit_state] wrote {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
