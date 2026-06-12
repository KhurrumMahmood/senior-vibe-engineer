#!/usr/bin/env python3
"""Backward coverage audit + referential-integrity check for /which-cleanup.

`audit` runs the forward closeout engine in reverse: over a commit range it
finds the touched subsystems, computes the skills each implies (same selection
as the forward path), then subtracts the skills that actually have a recent
scan in reports/_meta/effectiveness.jsonl — surfacing the gaps, with GUARD-tier
gaps highlighted. The effectiveness `target` field is free-form, so the join is
best-effort: legacy `core/` paths are remapped to `app/` (ADR 0011), and
anything still un-joinable lands in an explicit `unmappable_targets` section —
never silently dropped (ADR 0024).

`check` verifies every skill the registry / selection can recommend resolves to
a real `.claude/skills/<name>/`; wired into scripts/quality_gate.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# KIT_ROOT anchors kit-relative imports and the kit's skill catalogue ONLY.
# Target-project paths (registry, effectiveness log, git history) anchor on
# --project-root instead — the kit may live in a different repo (ADR 0024
# de-baking convention; see which-shape/scripts/route.py).
SCRIPT_DIR = Path(__file__).resolve().parent
KIT_ROOT = Path(__file__).resolve().parents[4]
for _p in (str(SCRIPT_DIR), str(KIT_ROOT / ".claude" / "skills" / "_common"), str(KIT_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import select_scanners
from diff_resolution import resolve_project_root, resolve_since, run_git_name_only
from query_planner import report_for_files
from subsystems import for_path, load_registry

# The recommendable skills ship with the kit (select_scanners reads their
# job: frontmatter from the same place) — kit-anchored, not project-anchored.
SKILLS_DIR = KIT_ROOT / ".claude" / "skills"


def _effectiveness_path(project_root: Path) -> Path:
    return project_root / "reports" / "_meta" / "effectiveness.jsonl"


# --------------------------------------------------------------------------- #
# Target normalization (the namespacing hazard, handled honestly)             #
# --------------------------------------------------------------------------- #

def normalize_target(target: str) -> str:
    """Best-effort path normalization for the effectiveness->subsystem join.

    Generic default just trims; a host project with a package rename can extend
    this (e.g. a ``core/`` -> ``app/`` remap) in its own copy.
    """
    return target.strip()


def _registry(project_root: Path) -> dict[str, Any]:
    """Load the subsystem registry, or {} when none is shipped (generic default)."""
    try:
        return load_registry(project_root / ".claude" / "subsystems.yaml")
    except FileNotFoundError:
        return {}


def _join_subsystem(norm_target: str, registry: dict[str, Any]) -> str | None:
    """for_path with a trailing-slash retry, so a bare directory target (e.g.
    `app/services/site_intelligence`) still matches a registry dir-prefix
    (`app/services/site_intelligence/`) instead of landing as false-unmappable."""
    sub = for_path(norm_target, registry)
    if sub is None and not norm_target.endswith("/") and "." not in norm_target.rsplit("/", 1)[-1]:
        sub = for_path(norm_target + "/", registry)
    return sub


def _is_coverage_skill(skill: str) -> bool:
    """A skill counts as subsystem coverage only if its job is a cleanup-loop job."""
    return select_scanners.job_for(skill) in select_scanners.JOB_BAND


# --------------------------------------------------------------------------- #
# audit                                                                        #
# --------------------------------------------------------------------------- #

def _range_files(last: int | None, since: str | None, project_root: Path) -> list[str]:
    if since:
        return resolve_since(project_root, since)
    n = last or 50
    out = run_git_name_only(
        project_root, ["git", "log", f"-n{n}", "--name-only", "--pretty=format:"]
    )
    return sorted(set(out))


def _recent_coverage(
    window_days: int, now: datetime, project_root: Path
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    """Return ({subsystem -> set(skills recently scanned)}, [unmappable target rows])."""
    cutoff = now - timedelta(days=window_days)
    covered: dict[str, set[str]] = {}
    unmappable: list[dict[str, Any]] = []
    effectiveness = _effectiveness_path(project_root)
    if not effectiveness.is_file():
        return covered, unmappable
    registry = _registry(project_root)
    seen_unmappable: set[str] = set()
    try:
        effectiveness_lines = effectiveness.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return covered, unmappable
    for line in effectiveness_lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        skill, target, ts = e.get("skill", ""), e.get("target", ""), e.get("ts", "")
        if not _is_coverage_skill(skill):
            continue
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if when.tzinfo is None:  # treat naive stamps as UTC (avoid a tz-compare crash)
                when = when.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue
        if when < cutoff:
            continue
        sub = _join_subsystem(normalize_target(target), registry)
        if sub is None:
            if target not in seen_unmappable:
                seen_unmappable.add(target)
                unmappable.append({"target": target, "skill": skill, "ts": ts})
            continue
        covered.setdefault(sub, set()).add(skill)
    return covered, unmappable


def audit(
    *, last: int | None, since: str | None, window_days: int, now: datetime, project_root: Path
) -> dict[str, Any]:
    registry = _registry(project_root)
    files = _range_files(last, since, project_root)
    subsystems = sorted({s for f in files if (s := for_path(f, registry))})
    report = report_for_files(files, registry, include_checklist=False)
    roster = select_scanners.select(report, band="large")  # widest implied set for the audit

    implied: dict[str, list[dict[str, Any]]] = {}
    for band_key, items in roster["buckets"].items():
        for it in items:
            implied.setdefault(it["skill"], []).append(band_key)

    covered, unmappable = _recent_coverage(window_days, now, project_root)
    covered_all: set[str] = set().union(*covered.values()) if covered else set()

    gaps = []
    for skill in sorted(implied):
        bands = implied[skill]
        is_guard = "guard_tail" in bands
        if skill not in covered_all:
            gaps.append({"skill": skill, "bands": bands, "guard_tier": is_guard,
                         "last_scan": None})
    return {
        "range": since or f"last {last or 50} commits",
        "window_days": window_days,
        "subsystems_touched": subsystems,
        "implied_skill_count": len(implied),
        "gaps": gaps,
        "guard_gaps": [g for g in gaps if g["guard_tier"]],
        "unmappable_targets": unmappable,
    }


def render_audit(a: dict[str, Any]) -> str:
    lines = ["# /which-cleanup — coverage audit", "",
             f"**Range:** {a['range']}  ", f"**Coverage window:** {a['window_days']} days  ",
             f"**Subsystems touched:** {', '.join(a['subsystems_touched']) or '(none)'}  ",
             f"**Implied skills:** {a['implied_skill_count']} · **gaps:** {len(a['gaps'])} "
             f"(guard-tier: {len(a['guard_gaps'])})", ""]
    lines.append("## Gaps — implied by recent work, no recent scan")
    if a["gaps"]:
        for g in a["gaps"]:
            mark = " **(GUARD gap — close the loop)**" if g["guard_tier"] else ""
            lines.append(f"  - **/{g['skill']}** ({', '.join(g['bands'])}){mark}")
    else:
        lines.append("  _(none — recent work's implied skills all have a recent scan)_")
    lines.append("")
    lines.append(f"## Unmappable effectiveness targets ({len(a['unmappable_targets'])})")
    if a["unmappable_targets"]:
        lines.append("_Free-form targets that did not resolve to a registry subsystem "
                     "(not counted as coverage; surfaced, not dropped):_")
        for u in a["unmappable_targets"][:30]:
            lines.append(f"  - `{u['target']}` ({u['skill']})")
        if len(a["unmappable_targets"]) > 30:
            lines.append(f"  - … (+{len(a['unmappable_targets']) - 30} more)")
    else:
        lines.append("  _(none)_")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# check (referential integrity — the rot guard)                               #
# --------------------------------------------------------------------------- #

def check(project_root: Path) -> tuple[int, list[str]]:
    """Every skill the registry/selection can recommend must resolve to a real skill dir."""
    registry = _registry(project_root)
    referenced: set[str] = set()
    for body in registry.values():
        referenced.update(body.get("related_skills") or [])
    for skills in select_scanners.ADJACENCY_SCANNERS.values():
        referenced.update(skills)
    # Every `*_FLOOR` roster select_scanners defines, discovered dynamically so a
    # newly-added floor (e.g. SWEEP_SHAPE_FLOOR / RENAME_DRIVER_FLOOR) is covered by
    # this guard automatically rather than being added to the roster but silently
    # escaping the referential check.
    for _name in dir(select_scanners):
        if _name.endswith("_FLOOR"):
            value = getattr(select_scanners, _name)
            if isinstance(value, list):
                referenced.update(value)

    missing = sorted(s for s in referenced if not (SKILLS_DIR / s / "SKILL.md").is_file())
    return (1 if missing else 0), missing


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("audit", help="Backward coverage gap analysis over a commit range")
    grp = pa.add_mutually_exclusive_group()
    grp.add_argument("--since", metavar="DATE", help="git --since spec (e.g. 2026-05-01)")
    grp.add_argument("--last", type=int, metavar="N", help="last N commits (default 50)")
    pa.add_argument("--window-days", type=int, default=90)
    pa.add_argument("--now", default=None, help="Override 'now' (ISO) for the coverage window (tests)")
    pa.add_argument("--project-root", type=Path, default=None,
                    help="Target project root (default: git toplevel of cwd, else cwd)")
    pa.add_argument("--json", action="store_true")

    pc = sub.add_parser("check", help="Referential integrity: every recommendable skill exists")
    pc.add_argument("--project-root", type=Path, default=None,
                    help="Target project root (default: git toplevel of cwd, else cwd)")
    pc.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    project_root = resolve_project_root(args.project_root)

    if args.cmd == "check":
        code, missing = check(project_root)
        if args.json:
            print(json.dumps({"missing_skills": missing}, sort_keys=True))
        elif missing:
            print("which-cleanup check: registry references missing skills:")
            for m in missing:
                print(f"  - {m}")
        else:
            print("which-cleanup check: OK — every recommendable skill resolves.")
        return code

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    a = audit(last=args.last, since=args.since, window_days=args.window_days, now=now,
              project_root=project_root)
    print(json.dumps(a, indent=2, sort_keys=True) if args.json else render_audit(a), end="" if args.json else "")
    if args.json:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
