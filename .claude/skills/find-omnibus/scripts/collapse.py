#!/usr/bin/env python3
"""Collapse detector output into the top-N candidate list for scout fan-out.

Reads ``omnibus.jsonl`` from detect.py (already score-sorted). Assigns a
``candidate_id`` (``omnibus-0001`` …) and truncates to ``--top``
records. Writes ``candidates.jsonl`` for the scout phase.

Nothing merges here — detect.py emits one record per file, so this
stage is pure capping + id assignment. Kept as a separate script to
mirror find-dormant's pipeline (detect → collapse → verify → report)
and to keep the per-file detector minimal.
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
    try:
        text = path.read_text()
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--detections", required=True, type=Path,
                   help="Path to omnibus.jsonl from detect.py")
    p.add_argument("--output", required=True, type=Path,
                   help="Output candidates.jsonl")
    p.add_argument("--top", type=int, default=30,
                   help="Maximum candidates to keep (default: 30)")
    args = p.parse_args(argv)

    records = _read_jsonl(args.detections)
    records.sort(key=lambda r: (-int(r.get("score", 0)), str(r.get("file", ""))))
    capped = records[: max(0, args.top)]

    for i, entry in enumerate(capped, start=1):
        entry["candidate_id"] = f"omnibus-{i:04d}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in capped:
            fh.write(json.dumps(r) + "\n")

    print(
        f"[collapse] detections={len(records)} "
        f"→ candidates={len(capped)} (top={args.top})",
        file=sys.stderr,
    )
    print(f"[collapse] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
