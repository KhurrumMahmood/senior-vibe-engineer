#!/usr/bin/env python3
"""Group transaction-overreach detector output into per-atomic-block
candidates.

Reads the ``hits.jsonl`` produced by ``detect.py`` and emits a
``candidates.jsonl`` where each record corresponds to one atomic block
(``with transaction.atomic():`` or a ``@transaction.atomic`` function).
If a block contains multiple slow-op calls, they roll up into one
candidate with the per-call evidence preserved in ``hits``.

Confidence tier per candidate is the highest tier across its hits:

- ``high`` — at least one hit in ``http`` / ``ai`` / ``cloud`` /
  ``subprocess`` / ``sleep`` (each is a guaranteed-slow operation).
- ``medium`` — only ``celery`` hits (dispatch can be safe under
  ``transaction.on_commit``; the scout disambiguates).
- ``low`` — only ``network_helper`` hits (ambiguous wrapper-named
  helpers; the scout reads the helper to decide).

Output shape (one JSON record per line at ``--output``):

    {
      "candidate_id": "transaction-overreach-0001",
      "file": "core/views/foo.py",
      "block_kind": "with",
      "block_lineno": 222,
      "block_endline": 285,
      "enclosing_symbol": "scrape_test_view",
      "confidence": "high",
      "categories": ["http", "celery"],
      "hit_count": 3,
      "hits": [ { ...detector record... }, ... ]
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HIGH_CATEGORIES = frozenset({"http", "ai", "cloud", "subprocess", "sleep"})
MEDIUM_CATEGORIES = frozenset({"celery"})
LOW_CATEGORIES = frozenset({"network_helper"})


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


def _confidence(categories: set[str]) -> str:
    if categories & HIGH_CATEGORIES:
        return "high"
    if categories & MEDIUM_CATEGORIES:
        return "medium"
    if categories & LOW_CATEGORIES:
        return "low"
    return "low"


def _collapse(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_block: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for hit in hits:
        file = hit.get("file", "")
        block_lineno = int(hit.get("block_lineno", 0))
        kind = str(hit.get("block_kind", "with"))
        if not file or not block_lineno:
            continue
        by_block[(file, block_lineno, kind)].append(hit)

    candidates: list[dict[str, Any]] = []
    keys = sorted(by_block.keys(), key=lambda k: (k[0], k[1], k[2]))
    for key in keys:
        file, block_lineno, kind = key
        bucket = by_block[key]
        cats = {str(h.get("category", "")) for h in bucket if h.get("category")}
        candidates.append({
            "candidate_id": "transaction-overreach-0000",  # rewritten below
            "file": file,
            "block_kind": kind,
            "block_lineno": block_lineno,
            "block_endline": int(bucket[0].get("block_endline", block_lineno)),
            "enclosing_symbol": str(
                bucket[0].get("enclosing_symbol", "<module>"),
            ),
            "confidence": _confidence(cats),
            "categories": sorted(cats),
            "hit_count": len(bucket),
            "hits": bucket,
        })

    conf_rank = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(
        key=lambda c: (
            conf_rank.get(c["confidence"], 99),
            c["file"],
            c["block_lineno"],
        ),
    )
    for i, c in enumerate(candidates, start=1):
        c["candidate_id"] = f"transaction-overreach-{i:04d}"
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
        f"[collapse_transaction_overreach] hits={len(hits)} "
        f"candidates={len(candidates)} "
        f"by_confidence={dict(by_conf)}",
        file=sys.stderr,
    )
    print(
        f"[collapse_transaction_overreach] wrote {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
