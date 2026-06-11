#!/usr/bin/env python3
"""Rank confirmed semantic-duplication findings by ROI.

Inputs:
  --confirmed     Directory containing one `<finding_id>.json` per scout output
                  (from the confirm stage).
  --callers       Optional path to `callers.jsonl` (produced by
                  `semantic_inventory.py callers`). Missing => caller counts
                  default to -1 and contribute neutrally to ranking.
  --output        Path to write `ranked.json`.

ROI formula:
    ROI = (shared_lines * maintenance_risk * level_multiplier) /
          max(migration_cost, 1)

Where:
    maintenance_risk    from domain tier (HIGH=3.0, MEDIUM=2.0, LOW=1.0);
                        unknown domains default to MEDIUM.
    level_multiplier    workflow=1.5, structural=1.3, function=1.0.
                        Workflow findings are higher-value (Rule R1).
    shared_lines        sum of member sizes; proxy for "how much code can
                        consolidate." Clamped to [10, 500] so single-line
                        helpers don't vanish and 1000-line monsters don't
                        dwarf everything.
    migration_cost      caller-count proxy: min across members, since the
                        cheapest migration direction is what matters.
                        Clamped to [1, 50].

Tier cutoffs: priority >= 30.0 = P0, >= 10.0 = P1, else P2.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MAINTENANCE_RISK = {
    "pricing": 3.0,
    "crawling": 3.0,
    "export": 3.0,
    "interchange": 3.0,
    "extraction": 2.0,
    "discovery": 2.0,
    "brand": 2.0,
    "ptid": 2.0,
    "external_source": 2.0,
    "auth": 2.0,
    "proxy": 2.0,
    "sitemap": 2.0,
    "utility": 1.0,
    "settings": 1.0,
    "email": 1.0,
    "logging": 1.0,
    "visual": 1.0,
    "agent": 1.0,
}
DEFAULT_RISK = 2.0  # medium


LEVEL_MULT = {"workflow": 1.5, "structural": 1.3, "function": 1.0}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _risk_for(domains: list[str]) -> float:
    if not domains:
        return DEFAULT_RISK
    return max(MAINTENANCE_RISK.get(d.lower(), DEFAULT_RISK) for d in domains)


def _shared_lines(finding: dict[str, Any]) -> int:
    sizes = [
        int(m.get("size") or 0)
        for m in finding.get("members") or []
        if m.get("size")
    ]
    return sum(sizes)


def _migration_cost(finding: dict[str, Any]) -> int:
    callers = [
        m.get("caller_count") for m in finding.get("members") or []
        if isinstance(m.get("caller_count"), int) and m.get("caller_count") >= 0
    ]
    if not callers:
        return 5  # neutral default
    return max(1, min(callers))


def _priority(finding: dict[str, Any]) -> dict[str, Any]:
    level = finding.get("level") or "function"
    domains = finding.get("domains") or []
    if isinstance(finding.get("maintenance_risk_domain"), str):
        domains = list(dict.fromkeys(domains + [finding["maintenance_risk_domain"]]))
    # Persist the merged domain list so downstream renderers (report.py) see it.
    finding["domains"] = domains
    risk = _risk_for(domains)
    mult = LEVEL_MULT.get(level, 1.0)
    shared = _clamp(_shared_lines(finding), 10, 500)
    cost = _clamp(_migration_cost(finding), 1, 50)
    score = (shared * risk * mult) / cost
    if score >= 30.0:
        tier = "P0"
    elif score >= 10.0:
        tier = "P1"
    else:
        tier = "P2"
    return {
        "priority": round(score, 2),
        "tier": tier,
        "maintenance_risk": risk,
        "level_multiplier": mult,
        "shared_lines": int(shared),
        "migration_cost": int(cost),
    }


def _load_confirmed(confirmed_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(confirmed_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            print(f"[rank] WARN skipping {p.name}: {e}", file=sys.stderr)
            continue
        out.append(d)
    return out


def _merge_caller_counts(
    confirmed: list[dict[str, Any]], callers_path: Path | None
) -> None:
    """If callers.jsonl exists, patch member.caller_count in-place."""
    if not callers_path or not callers_path.exists():
        return
    caller_map: dict[tuple[str, str], int] = {}
    try:
        text = callers_path.read_text()
    except (OSError, UnicodeDecodeError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Use the full qualified_name so `FooView.get` and `BarView.get` in
        # the same file stay distinct (mirrors collapse_candidates._site_key).
        qn = r.get("qualified_name") or ""
        key = (r.get("file") or "", qn)
        if key[0] and key[1]:
            # `semantic_inventory.py callers` emits `total_refs`; accept
            # `caller_count` as a fallback for alternate producers.
            count = r.get("total_refs")
            if count is None:
                count = r.get("caller_count") or 0
            caller_map[key] = int(count)
    for f in confirmed:
        for m in f.get("members") or []:
            qn = m.get("qualified_name") or m.get("name") or ""
            key = (m.get("file") or "", qn)
            if key in caller_map and m.get("caller_count") in (None, -1):
                m["caller_count"] = caller_map[key]


def rank(
    confirmed_dir: Path, callers_path: Path | None, output: Path
) -> dict[str, int]:
    findings = _load_confirmed(confirmed_dir)
    kept = [
        f for f in findings
        if f.get("investigation_status") in {"confirmed", "migration_in_progress"}
    ]
    rejected = [f for f in findings if f not in kept]
    _merge_caller_counts(kept, callers_path)
    for f in kept:
        f["rank_meta"] = _priority(f)
    kept.sort(key=lambda f: -f["rank_meta"]["priority"])
    by_tier = {"P0": 0, "P1": 0, "P2": 0}
    for f in kept:
        by_tier[f["rank_meta"]["tier"]] += 1
    output.write_text(
        json.dumps(
            {"findings": kept, "rejected": rejected, "tier_counts": by_tier},
            indent=2,
        )
    )
    return {"confirmed": len(kept), "rejected": len(rejected), **by_tier}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--confirmed", required=True, type=Path)
    p.add_argument("--callers", type=Path, default=None)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if not args.confirmed.is_dir():
        print(f"[rank] ERROR: not a dir: {args.confirmed}", file=sys.stderr)
        return 2
    counts = rank(args.confirmed, args.callers, args.output)
    print(
        f"[rank] confirmed={counts['confirmed']} rejected={counts['rejected']} "
        f"P0={counts['P0']} P1={counts['P1']} P2={counts['P2']}"
    )
    print(f"[rank] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
