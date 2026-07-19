#!/usr/bin/env python3
"""Collapse per-domain candidate files from Compare into a single ranked list.

Inputs:
  --prompts-dir   Directory containing one `candidates_<domain>.json` per domain
                  (written by the comparator scouts).
  --output        Path to write the merged candidates JSON.

Behavior:
  1. Load every `*.json` in --prompts-dir.
  2. Re-number IDs globally (SC-1, SC-2, ...) — the per-domain IDs are discarded.
  3. Union-find: merge candidates that share any (file, qualified_name) member.
     This catches three-way+ semantic clusters where the comparator emitted
     (A,B), (A,C), (B,C) as three pairs — same issue as find-duplication jscpd
     pair explosion; same fix.
  4. Tag each merged cluster with `multiplicity` (member count).
  5. Write a single JSON with `findings: [...]` plus a counts summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_domain_files(prompts_dir: Path) -> list[dict[str, Any]]:
    """Load every candidates_<domain>.json produced by the comparator scouts."""
    found: list[dict[str, Any]] = []
    for p in sorted(prompts_dir.glob("candidates_*.json")):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            print(f"[collapse_candidates] WARN skipping {p.name}: {e}",
                  file=sys.stderr)
            continue
        if isinstance(data, dict) and "candidates" in data:
            for c in data.get("candidates") or []:
                if c.get("level", "function") != "function":
                    print(
                        "[collapse_candidates] WARN skipping non-function candidate "
                        f"{c.get('id', '?')}",
                        file=sys.stderr,
                    )
                    continue
                c.setdefault("domain", data.get("domain"))
                found.append(c)
    return found


def _site_key(member: dict[str, Any]) -> tuple[str, str]:
    """Normalize a candidate member to a (file, qualified_name) tuple.

    Keep the full `Class.method` string: stripping the class prefix would
    let `FooView.get` and `BarView.get` in the same file collapse into the
    same union-find bucket (learnings.md R2 — name collision is not
    semantic equivalence).
    """
    f = member.get("file") or ""
    qn = member.get("qualified_name") or member.get("name") or ""
    return (f, qn)


def _members_of(cand: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract member list from either pair shape (a/b) or cluster shape."""
    if "members" in cand and cand["members"]:
        return list(cand["members"])
    members = []
    for slot in ("a", "b"):
        if slot in cand and cand[slot]:
            members.append(cand[slot])
    return members


def _union_find(candidates: list[dict[str, Any]]) -> list[list[int]]:
    """Return groups of candidate indices that share at least one member site."""
    n = len(candidates)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    site_to_idx: dict[tuple[str, str], list[int]] = {}
    for i, c in enumerate(candidates):
        for m in _members_of(c):
            site_to_idx.setdefault(_site_key(m), []).append(i)
    for ids in site_to_idx.values():
        for j in ids[1:]:
            union(ids[0], j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _merge_group(
    candidates: list[dict[str, Any]], indices: list[int], new_id: str
) -> dict[str, Any]:
    """Merge candidates at `indices` into a single cluster finding."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    domains: set[str] = set()
    similarities: list[int] = []
    rationales: list[str] = []
    source_ids: list[str] = []
    for i in indices:
        c = candidates[i]
        for m in _members_of(c):
            seen.setdefault(_site_key(m), m)
        if c.get("domain"):
            domains.add(c["domain"])
        if isinstance(c.get("similarity"), (int, float)):
            similarities.append(int(c["similarity"]))
        if c.get("rationale"):
            rationales.append(str(c["rationale"]))
        if c.get("id"):
            source_ids.append(str(c["id"]))
    members = list(seen.values())
    return {
        "id": new_id,
        "multiplicity": len(members),
        "level": "function",
        "domains": sorted(domains),
        "members": members,
        "similarity_max": max(similarities) if similarities else 0,
        "similarity_avg": (sum(similarities) / len(similarities))
        if similarities else 0.0,
        "rationales": rationales,
        "source_candidate_ids": source_ids,
        "raw_pairs_collapsed": len(indices),
    }


def collapse(prompts_dir: Path, output: Path) -> dict[str, int]:
    candidates = _load_domain_files(prompts_dir)
    groups = _union_find(candidates)
    # Sort groups by max similarity descending, then multiplicity
    groups_sorted = sorted(
        groups,
        key=lambda ids: (
            -max(
                (candidates[i].get("similarity", 0) or 0) for i in ids
            ),
            -len(ids),
        ),
    )
    findings = [
        _merge_group(candidates, ids, f"SC-{n + 1}")
        for n, ids in enumerate(groups_sorted)
    ]
    counts = {
        "raw_candidates": len(candidates),
        "findings": len(findings),
        "multi_way_clusters": sum(1 for f in findings if f["multiplicity"] > 2),
        "cross_domain_findings": sum(
            1 for f in findings if len(f["domains"]) > 1
        ),
    }
    output.write_text(
        json.dumps({"findings": findings, "counts": counts}, indent=2)
    )
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompts-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if not args.prompts_dir.is_dir():
        print(f"[collapse_candidates] ERROR: not a dir: {args.prompts_dir}",
              file=sys.stderr)
        return 2
    counts = collapse(args.prompts_dir, args.output)
    print(
        f"[collapse_candidates] raw={counts['raw_candidates']} "
        f"findings={counts['findings']} "
        f"multi_way={counts['multi_way_clusters']} "
        f"cross_domain={counts['cross_domain_findings']}"
    )
    print(f"[collapse_candidates] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
