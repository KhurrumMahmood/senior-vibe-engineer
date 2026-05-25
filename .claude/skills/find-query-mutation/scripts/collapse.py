#!/usr/bin/env python3
"""Group query-mutation detector output into per-function candidates.

Reads the ``hits.jsonl`` produced by ``detect.py`` and emits a
``candidates.jsonl`` where each record corresponds to one ``(file,
symbol)`` bucket — i.e. one finding per read-named function. If a
function contains multiple mutation calls, they roll up into one
finding with an evidence list.

Confidence tier is assigned by mutation shape:

- ``high`` — the function calls ``save`` / ``delete`` / ``create`` /
  ``bulk_create`` / ``bulk_update`` (Django persistence shapes; strong
  signal the read-named function mutates a persisted row).
- ``medium`` — the function calls ``update`` / ``update_or_create`` /
  ``get_or_create``. ``update`` especially is ambiguous: it's also
  ``dict.update`` and ``set.update`` on non-queryset receivers —
  scouts disambiguate by reading the function body.

Output shape (one JSON record per line at ``--output``):

    {
      "candidate_id": "query-mutation-0001",
      "file": "core/models/settings.py",
      "symbol": "get_settings",
      "func_lineno": 181,
      "confidence": "medium",
      "mutation_methods": ["get_or_create"],
      "hit_count": 1,
      "hits": [ { ... detector record ... }, ... ]
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HIGH_CONF_METHODS = frozenset({
    "save", "delete", "create", "bulk_create", "bulk_update",
})
MEDIUM_CONF_METHODS = frozenset({
    "update", "update_or_create", "get_or_create",
})


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _confidence(methods: set[str]) -> str:
    if methods & HIGH_CONF_METHODS:
        return "high"
    if methods & MEDIUM_CONF_METHODS:
        return "medium"
    return "low"


def _collapse(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for hit in hits:
        file = hit.get("file", "")
        symbol = hit.get("symbol", "")
        func_lineno = int(hit.get("func_lineno", 0))
        if not file or not symbol:
            continue
        by_group[(file, symbol, func_lineno)].append(hit)

    candidates: list[dict[str, Any]] = []
    # Deterministic ordering: high confidence first, then file asc.
    ordered_keys = sorted(by_group.keys(), key=lambda k: (k[0], k[2], k[1]))
    for i, key in enumerate(ordered_keys, start=1):
        file, symbol, func_lineno = key
        bucket = by_group[key]
        methods = {h["method"] for h in bucket if "method" in h}
        candidates.append({
            "candidate_id": f"query-mutation-{i:04d}",
            "file": file,
            "symbol": symbol,
            "func_lineno": func_lineno,
            "confidence": _confidence(methods),
            "mutation_methods": sorted(methods),
            "hit_count": len(bucket),
            "hits": bucket,
        })

    # Re-sort so high confidence lands first — scouts budget from the top.
    conf_rank = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(
        key=lambda c: (conf_rank.get(c["confidence"], 99), c["file"], c["func_lineno"]),
    )
    # Re-number so candidate_id reflects priority order.
    for i, c in enumerate(candidates, start=1):
        c["candidate_id"] = f"query-mutation-{i:04d}"
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

    by_conf: dict[str, int] = defaultdict(int)
    for c in candidates:
        by_conf[c["confidence"]] += 1
    print(
        f"[collapse_query_mutation] hits={len(hits)} "
        f"candidates={len(candidates)} "
        f"by_confidence={dict(by_conf)}",
        file=sys.stderr,
    )
    print(
        f"[collapse_query_mutation] wrote {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
