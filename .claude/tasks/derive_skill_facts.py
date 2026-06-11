#!/usr/bin/env python3
"""Derive deterministic git + on-disk reports facts for every ES2 skill.

Feeds the intent-contract fan-out so agents don't each re-run git archaeology
(and don't trip the `git log --diff-filter=A` merge-birth artifact). True birth
= earliest commit (full history) touching SKILL.md whose parents all lack it.

Writes .claude/tasks/es2_skill_facts.yaml. Run from the es2 repo root.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
import yaml

SKILLS = Path(".claude/skills")
REPORTS = Path("reports")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def exists_in(commit: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"],
                          capture_output=True).returncode == 0


def true_birth(path: str):
    """(short_sha, date) of the earliest commit adding `path`, verified by parent-absence."""
    revs = git("rev-list", "--full-history", "--reverse", "HEAD", "--", path).split()
    for c in revs:
        parents = git("show", "-s", "--format=%P", c).split()
        if all(not exists_in(p, path) for p in parents):  # absent in every parent (or no parents)
            short = git("rev-parse", "--short", c)
            date = git("show", "-s", "--format=%ad", "--date=short", c)
            return short, date
    return None, None


def run_dirs(d: Path):
    """Immediate subdirs of a reports dir that look like runs; (count, first, latest) by name."""
    if not d.is_dir():
        return 0, None, None
    subs = sorted(p.name for p in d.iterdir() if p.is_dir())
    if not subs:
        # flat report dir (files only) still counts as one run-equivalent
        files = [p for p in d.iterdir() if p.is_file()]
        return (1 if files else 0), None, None
    return len(subs), subs[0], subs[-1]


def main() -> None:
    skills = sorted(p.name for p in SKILLS.iterdir()
                    if p.is_dir() and p.name != "_common" and (p / "SKILL.md").exists())

    # first pass: births (to compute sibling cohorts)
    births: dict[str, tuple] = {}
    for s in skills:
        births[s] = true_birth(f".claude/skills/{s}/SKILL.md")

    by_commit: dict[str, list] = {}
    for s, (sha, _date) in births.items():
        by_commit.setdefault(sha, []).append(s)

    report_subdirs = sorted(p.name for p in REPORTS.iterdir() if p.is_dir()) if REPORTS.is_dir() else []
    matched = set()

    out = {}
    for s in skills:
        sha, date = births[s]
        siblings = sorted(x for x in by_commit.get(sha, []) if x != s) if sha else []
        rdir = REPORTS / s
        has = rdir.is_dir()
        if has:
            matched.add(s)
        cnt, first, latest = run_dirs(rdir)
        out[s] = {
            "born": {"commit": sha or "pending-initial-commit",
                     "date": date or "UNCOMMITTED",
                     "sibling_births_count": len(siblings),
                     "sibling_births": siblings},
            "reports_dir": f"reports/{s}" if has else None,
            "run_evidence": {"count": cnt, "first": first, "latest": latest},
        }

    summary = {
        "_skill_count": len(skills),
        "_birth_cohorts": {sha: sorted(names) for sha, names in sorted(by_commit.items(),
                            key=lambda kv: -len(kv[1])) if len(names) > 1},
        "_unmatched_report_dirs": [d for d in report_subdirs if d not in matched and not d.startswith("_")],
        "skills": out,
    }
    Path(".claude/tasks/es2_skill_facts.yaml").write_text(
        yaml.safe_dump(summary, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"skills={len(skills)}")
    print("biggest birth cohorts:")
    for sha, names in sorted(by_commit.items(), key=lambda kv: -len(kv[1]))[:4]:
        print(f"  {sha} ({births_date(births, names)}): {len(names)} skills")
    print(f"skills WITH on-disk reports/: {len(matched)}")
    print(f"unmatched report dirs (aliases to map): {summary['_unmatched_report_dirs']}")


def births_date(births, names):
    for n in names:
        return births[n][1]
    return "?"


if __name__ == "__main__":
    main()
