#!/usr/bin/env python3
"""Collapse signal-hits into per-symbol candidates for scout fan-out.

Reads ``layer_violations.jsonl`` from detect.py (one record per signal-hit).
Groups by ``(file, symbol)`` — a single view method commonly emits 2–4
signals (e.g. ``fat`` + ``dispatch_bypass`` + ``multi_model_write``).
Assigns a confidence tier based on how many distinct signals fired and
emits a single ``candidates.jsonl`` record per symbol.

Output record:

    {
      "candidate_id": "layer-0001",
      "file": "core/views/external_source.py",
      "symbol": "ExternalSourceExtractView.post",
      "kind": "view_method",
      "loc": 142,
      "lineno": 412,
      "end_lineno": 553,
      "signals": ["fat", "multi_model_write"],
      "signal_count": 2,
      "evidence": {
        "fat": "body LOC=142 (budget 120)",
        "multi_model_write": "writes to 3 models in one function: ProductCrawlJob, ProductCrawlResult, IndividualCrawlResult"
      },
      "confidence": "high | medium | low",
      "score": 2142
    }

Ranking: ``signal_count`` then ``loc``. ``confidence`` is
``high`` for 3+ signals, ``medium`` for 2, ``low`` for 1. The scout
phase decides bucket placement — this stage only sets up the fan-out.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _confidence(signal_count: int) -> str:
    if signal_count >= 3:
        return "high"
    if signal_count == 2:
        return "medium"
    return "low"


def _collapse(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[tuple[str, str], dict[str, Any]] = {}
    for h in hits:
        key = (h.get("file", ""), h.get("symbol", ""))
        entry = by_symbol.setdefault(key, {
            "file": h.get("file", ""),
            "symbol": h.get("symbol", ""),
            "kind": h.get("kind", ""),
            "loc": int(h.get("loc", 0) or 0),
            "lineno": int(h.get("lineno", 0) or 0),
            "end_lineno": int(h.get("end_lineno", 0) or 0),
            "signals": [],
            "evidence": {},
        })
        signal = h.get("signal", "")
        if signal and signal not in entry["signals"]:
            entry["signals"].append(signal)
        # Keep the longest evidence string per signal (best description when
        # multiple hits of the same kind fired in one function).
        prev = entry["evidence"].get(signal, "")
        new_evidence = str(h.get("evidence", ""))
        if len(new_evidence) > len(prev):
            entry["evidence"][signal] = new_evidence
        # Track the largest LOC across hits (the `fat` signal has the LOC
        # budget, other hits carry the enclosing body size as a fallback).
        loc = int(h.get("loc", 0) or 0)
        if loc > entry["loc"]:
            entry["loc"] = loc
        lineno = int(h.get("lineno", 0) or 0)
        if entry["lineno"] == 0 and lineno:
            entry["lineno"] = lineno
        end_lineno = int(h.get("end_lineno", 0) or 0)
        if end_lineno > entry["end_lineno"]:
            entry["end_lineno"] = end_lineno

    # Assemble + rank.
    out: list[dict[str, Any]] = []
    for entry in by_symbol.values():
        signals = sorted(entry["signals"])
        count = len(signals)
        out.append({
            **entry,
            "signals": signals,
            "signal_count": count,
            "confidence": _confidence(count),
            # signal_count weighs much more than LOC: a 1-signal 2000-LOC
            # function is still just one smell; a 3-signal 100-LOC function
            # is three smells stacked up.
            "score": count * 1000 + int(entry["loc"]),
        })

    out.sort(
        key=lambda e: (
            -int(e["score"]),
            -int(e["signal_count"]),
            -int(e["loc"]),
            str(e["file"]),
            str(e["symbol"]),
        ),
    )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--detections", required=True, type=Path,
                   help="Path to layer_violations.jsonl from detect.py")
    p.add_argument("--output", required=True, type=Path,
                   help="Output candidates.jsonl")
    p.add_argument("--top", type=int, default=30,
                   help="Maximum candidates to keep (default: 30)")
    args = p.parse_args(argv)

    hits = _read_jsonl(args.detections)
    candidates = _collapse(hits)
    capped = candidates[: max(0, args.top)]

    for i, entry in enumerate(capped, start=1):
        entry["candidate_id"] = f"layer-{i:04d}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in capped:
            fh.write(json.dumps(r) + "\n")

    print(
        f"[collapse] hits={len(hits)} "
        f"→ symbols={len(candidates)} "
        f"→ candidates={len(capped)} (top={args.top})",
        file=sys.stderr,
    )
    print(f"[collapse] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
