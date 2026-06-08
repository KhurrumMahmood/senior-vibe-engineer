#!/usr/bin/env python3
"""Turn a query_planner registry report into a tiered closeout roster.

Each touched subsystem contributes its `related_skills` plus the `/find-*`
scanners implied by its `adjacency` smell tokens; a small universal floor is
added regardless of subsystem. Every candidate skill is bucketed into a
point-in-time band by reading its own `job:` frontmatter (the registry is the
single source of truth — ADR 0024 — so we tier by job, not by a parallel
table). The canonical smell -> skill chains live in
`.claude/docs/architectural-smells.md`; this is the lookup, not a restatement.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LIB = _REPO_ROOT / "scripts" / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import yaml_frontmatter

SKILLS_DIR = _REPO_ROOT / ".claude" / "skills"

# adjacency smell token -> SUSPECT scanner skill(s). Lint-only tokens
# (missing-auth, safe-dispatch, sidecar-boundary, silent-catch,
# stale-model-field-ref) have no dedicated /find-* scanner — diff-scoped lints
# cover them at commit time — so they are intentionally absent here.
ADJACENCY_SCANNERS: dict[str, list[str]] = {
    "copy-paste-variation": ["find-duplication"],
    "dormant": ["find-dormant"],
    "duplication": ["find-duplication"],
    "fat-view": ["find-layer-violation"],
    "foreign-key-as-tuple": ["find-implicit-state"],
    "layer-violation": ["find-layer-violation"],
    "omnibus": ["find-omnibus"],
    "query-mutation": ["find-query-mutation"],
    "stringly-status": ["find-implicit-state"],
}

# `job:` frontmatter -> closeout point-in-time band. Skills whose job maps to no
# band (decide / meta / plan / teach / triage / diagnose) are not closeout
# scans and are dropped from the roster (surfaced under `dropped` for transparency).
JOB_BAND: dict[str, str] = {
    "map": "pre_baseline",
    "suspect": "post_sweep",
    "explain": "post_sweep",
    "refactor": "post_sweep",
    "guard": "guard_tail",
}

# Always-relevant skills regardless of subsystem (the "universal floor").
UNIVERSAL_FLOOR = ["find-comment-drift", "find-test-obligation-drift", "prevent-regression"]
DOC_SHAPE_FLOOR: list[str] = []                    # find-doc-link-rot not in this repo's skill set
RENAME_SHAPE_FLOOR = ["find-concept-divergence"]   # added on large (rename-prone) shapes

_JOB_CACHE: dict[str, str | None] = {}


def job_for(skill: str) -> str | None:
    """Read a skill's `job:` frontmatter (cached). None if the skill/file is absent."""
    if skill in _JOB_CACHE:
        return _JOB_CACHE[skill]
    md = SKILLS_DIR / skill / "SKILL.md"
    job: str | None = None
    if md.is_file():
        try:
            value = yaml_frontmatter.read(md).metadata.get("job")
            job = value if isinstance(value, str) else None
        except (OSError, ValueError):
            job = None
    _JOB_CACHE[skill] = job
    return job


def select(report: dict[str, Any], *, band: str, has_doc_change: bool = False) -> dict[str, Any]:
    """Build the tiered roster from a `query_planner.report_for_files` report.

    Returns `{"buckets": {pre_baseline, post_sweep, guard_tail}, "dropped": [...]}`,
    each item `{skill, job, why}`. `why` records every provenance reason.
    """
    candidates: dict[str, list[str]] = {}

    def add(skill: str, reason: str) -> None:
        reasons = candidates.setdefault(skill, [])
        if reason not in reasons:
            reasons.append(reason)

    for entry in report.get("subsystems", []):
        sub = entry["name"]
        for skill in entry.get("related_skills", []):
            add(skill, f"{sub}: related skill")
        for token in entry.get("adjacency", []):
            for skill in ADJACENCY_SCANNERS.get(token, []):
                add(skill, f"{sub}: adjacency '{token}'")

    for skill in UNIVERSAL_FLOOR:
        add(skill, "universal closeout floor")
    if has_doc_change:
        for skill in DOC_SHAPE_FLOOR:
            add(skill, "docs/.md changed")
    if band == "large":
        for skill in RENAME_SHAPE_FLOOR:
            add(skill, "large / cross-subsystem shape (rename-prone)")

    buckets: dict[str, list[dict[str, Any]]] = {"pre_baseline": [], "post_sweep": [], "guard_tail": []}
    dropped: list[dict[str, Any]] = []
    for skill in sorted(candidates):
        job = job_for(skill)
        item = {"skill": skill, "job": job, "why": "; ".join(candidates[skill])}
        target = JOB_BAND.get(job) if job else None
        (buckets[target] if target else dropped).append(item)
    return {"buckets": buckets, "dropped": dropped}
