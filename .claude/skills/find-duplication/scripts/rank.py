#!/usr/bin/env python3
"""Rank collapsed findings by multiplicity x divergence x blast-radius.

Reads the findings JSON produced by collapse.py, attaches a rank_meta object
to each finding (priority, tier, heuristic inputs), and sorts the findings
list in descending priority order.

Usage:
  python rank.py --input collapsed.json --output ranked.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# Filename keywords that bump divergence risk (money / auth / proxy code).
HIGH_RISK_KEYWORDS: set[str] = {
    "auth", "price", "pricing", "cost", "billing", "payment",
    "proxy", "credentials", "token",
}

# shape_hint -> bug blast radius multiplier.
SHAPE_BLAST: dict[str, float] = {
    "pure_duplication": 2.0,
    "three_way_plus": 2.5,
    "shadow_helper": 3.0,
    "canonical_pattern_violation": 2.0,
    "cross_file_clone": 1.5,
    "protocol_name_collision": 0.25,
}


def _keyword_bump(path: str) -> float:
    low = path.lower()
    bump = sum(0.5 for kw in HIGH_RISK_KEYWORDS if kw in low)
    return min(bump, 2.0)


def divergence_risk(sites: list[dict[str, Any]]) -> float:
    """Divergence risk for a finding's sites: a neutral 1.0 base plus a
    filename-keyword bump (money / auth / proxy). Path location does not affect
    the score — the toolkit assumes no host folder layout."""
    if not sites:
        return 1.0
    return max(1.0 + _keyword_bump(s.get("file", "") or "") for s in sites)


def bug_blast_radius(shape_hint: str) -> float:
    return SHAPE_BLAST.get(shape_hint, 1.0)


def effort_hint(sites: list[dict[str, Any]], multiplicity: int) -> str:
    files = {s.get("file") for s in sites}
    if len(files) == 1:
        return "low"
    if multiplicity <= 3:
        return "medium"
    return "high"


def tier_for(priority: float) -> str:
    if priority >= 10:
        return "P0"
    if priority >= 5:
        return "P1"
    return "P2"


MULT_CAP = 10.0  # keep one sprawl pattern from dwarfing everything else


def rank_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for f in findings:
        mult = float(f.get("multiplicity") or 1)
        effective_mult = min(mult, MULT_CAP)
        div = divergence_risk(f.get("sites", []) or [])
        blast = bug_blast_radius(f.get("shape_hint", ""))
        priority = effective_mult * div * blast
        new_f = dict(f)
        new_f["rank_meta"] = {
            "priority": round(priority, 2),
            "priority_tier": tier_for(priority),
            "divergence_risk": round(div, 2),
            "bug_blast_radius": blast,
            "effective_multiplicity": effective_mult,
            "effort_hint": effort_hint(f.get("sites", []) or [], int(mult)),
        }
        out.append(new_f)

    def _key(f: dict[str, Any]) -> tuple[float, float, float]:
        return (
            -f["rank_meta"]["priority"],
            -float(f.get("multiplicity") or 0),
            -float(f.get("shared_lines_max") or 0),
        )

    out.sort(key=_key)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank collapsed findings by priority heuristic."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    ranked = rank_findings(data.get("findings", []) or [])
    data["findings"] = ranked

    tier_counts = Counter(f["rank_meta"]["priority_tier"] for f in ranked)
    data.setdefault("scan_meta", {})
    data["scan_meta"]["rank_summary"] = {
        "p0": tier_counts.get("P0", 0),
        "p1": tier_counts.get("P1", 0),
        "p2": tier_counts.get("P2", 0),
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

    print(
        f"[rank] {len(ranked)} findings: "
        f"P0={tier_counts.get('P0', 0)} "
        f"P1={tier_counts.get('P1', 0)} "
        f"P2={tier_counts.get('P2', 0)}",
        file=sys.stderr,
    )
    print(f"[rank] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
