#!/usr/bin/env python3
"""Fast self-check for /which-cleanup — no network, no fixtures on disk.

Exercises the deterministic core (classify -> select -> closeout) on a synthetic
registry report and confirms the referential-integrity guard passes. Exits 0 on
success, 1 on the first failed assertion.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
for _p in (str(SCRIPT_DIR), str(REPO_ROOT / ".claude" / "skills" / "_common"), str(REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import classify
import closeout as closeout_mod
import coverage
import select_scanners


def main() -> int:
    # 1. classify — OR-logic: 3 subsystems forces large even with few files.
    assert classify.classify(classify.ScopeInputs(1, 1, 10)) == "trivial"
    assert classify.classify(classify.ScopeInputs(3, 1, 50)) == "small"
    assert classify.classify(classify.ScopeInputs(2, 3, 20)) == "large", "subsystem axis must dominate"
    assert classify.classify(classify.ScopeInputs(8, 1, 100)) == "medium"

    # 2. select — adjacency token routes to its scanner in the right band.
    report = {
        "subsystems": [
            {"name": "field_extraction", "related_skills": ["map-product-workflow"],
             "adjacency": ["stringly-status"]},
        ],
        "unmatched": [],
    }
    roster = select_scanners.select(report, band="small")
    post = {i["skill"] for i in roster["buckets"]["post_sweep"]}
    pre = {i["skill"] for i in roster["buckets"]["pre_baseline"]}
    guard = {i["skill"] for i in roster["buckets"]["guard_tail"]}
    assert "find-implicit-state" in post, "stringly-status -> find-implicit-state (post_sweep)"
    assert "map-product-workflow" in pre, "map skill -> pre_baseline"
    assert "prevent-regression" in guard, "universal-floor guard -> guard_tail"

    # 3. closeout.build — produces the 3 bands + scoped commands.
    c = closeout_mod.build(
        target="smoke", scope_band="small", axis_breakdown={"files": "small", "subsystems": "trivial", "diff_loc": "small"},
        resolved_paths=["app/services/extraction/field_chat.py"], report=report, roster=roster, max_scouts=5,
    )
    assert set(c["checklist"]) == {"pre_baseline", "post_sweep", "guard_tail"}
    assert "/find-implicit-state" in closeout_mod.render_md(c)

    # 4. referential integrity — every recommendable skill resolves. The smoke
    # is a kit self-check, so the kit root is the project root here.
    code, missing = coverage.check(REPO_ROOT)
    assert code == 0, f"missing skills referenced by registry/floor: {missing}"

    print("which-cleanup smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
