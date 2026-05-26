#!/usr/bin/env python3
"""Synthesize .claude/contracts/skills/_duplication-watchlist.yaml from the
duplication_risk[] blocks in every skill contract.

Canonicalizes each (skill, with) into a sorted pair so A->B and B->A merge;
if both directions exist with DIFFERENT relations, that disagreement is flagged
(a real signal — the two skills disagree on how they relate). Groups by relation:
genuine-overlap + shared-doc-coupling are actionable (review/promote to findings);
sibling-different-layer + sequential are expected/healthy.

Run from the es2 repo root.
"""
from __future__ import annotations
from pathlib import Path
import yaml

CONTRACTS = Path(".claude/contracts/skills")
RELATIONS = ("genuine-overlap", "shared-doc-coupling", "sibling-different-layer", "sequential")


def main() -> None:
    pairs: dict[tuple[str, str], dict] = {}
    for f in sorted(CONTRACTS.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        d = yaml.safe_load(f.read_text()) or {}
        src = d.get("skill", f.stem)
        for dr in d.get("duplication_risk") or []:
            other = dr.get("with")
            rel = dr.get("relation")
            note = dr.get("disambiguator", "")
            if not other or not rel:
                continue
            key = tuple(sorted((src, other)))
            slot = pairs.setdefault(key, {"relations": {}, "notes": []})
            slot["relations"].setdefault(rel, []).append(src)
            if note:
                slot["notes"].append(f"[{src}->{other}] {note}")

    counts = {r: 0 for r in RELATIONS}
    conflicts = []
    rel_buckets: dict[str, list] = {r: [] for r in RELATIONS}
    for (a, b), slot in sorted(pairs.items()):
        rels = slot["relations"]
        # effective relation: the most "severe" one declared (genuine-overlap worst)
        eff = next((r for r in RELATIONS if r in rels), None)
        counts[eff] += 1
        entry = {"pair": [a, b], "note": " | ".join(slot["notes"][:2])}
        if len(rels) > 1:
            entry["relation_disagreement"] = {r: sorted(set(v)) for r, v in rels.items()}
            conflicts.append((a, b, list(rels)))
        rel_buckets[eff].append(entry)

    out = {
        "_note": (
            "Synthesized from the duplication_risk[] blocks in every skill contract "
            "(regenerate: .venv/bin/python .claude/contracts/skills/_synth_watchlist.py). "
            "Raw, pre-review duplication candidates; "
            "promote confirmed items to .claude/quality/findings.jsonl. genuine-overlap + "
            "shared-doc-coupling are actionable; sibling-different-layer + sequential are "
            "expected/healthy (distinct surfaces / pipelines, disambiguated by each skill's not_for). "
            "relation_disagreement = the two skills' contracts classify the pair differently — reconcile."
        ),
        "counts": counts,
        "unique_pairs": len(pairs),
        "relation_disagreements": len(conflicts),
        "actionable": {
            "genuine-overlap": rel_buckets["genuine-overlap"],
            "shared-doc-coupling": rel_buckets["shared-doc-coupling"],
        },
        "informational": {
            "sibling-different-layer": rel_buckets["sibling-different-layer"],
            "sequential": rel_buckets["sequential"],
        },
    }
    dest = CONTRACTS / "_duplication-watchlist.yaml"
    dest.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100))
    print(f"unique_pairs={len(pairs)} counts={counts} disagreements={len(conflicts)}")
    for a, b, rels in conflicts:
        print(f"  DISAGREEMENT {a} <-> {b}: {rels}")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
