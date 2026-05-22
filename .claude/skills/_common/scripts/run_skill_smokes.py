#!/usr/bin/env python3
"""Aggregating skill-ecosystem smoke gate — the single entry point CI calls to
prove the ecosystem's own skills still run.

Why this exists
---------------
The ecosystem ships 60+ guard/maintenance skills that detect drift in *host*
projects, yet almost none of that machinery was exercised automatically: a
skill could break (an import error, a moved `_common` path, a frontmatter↔
script drift) and rot silently until someone next invoked it by hand. That is
the exact "a contract checker that runs nowhere protects nothing" trap these
skills are built to catch — turned inward on the ecosystem itself.

This gate closes that gap. It mirrors a quality gate's blocking/reporter split:

* **Blocking**  — every skill that *has* a `scripts/smoke.py` must exit 0. A
  failing smoke fails the gate (exit 1). This keeps the smokes that exist green
  instead of letting them silently rot.
* **Reporter**  — skills with no smoke are listed and counted but do NOT fail
  the gate by default. Hard-failing on dozens of missing smokes would be
  unmergeable noise; coverage is meant to climb over time. Pass ``--require-all``
  to promote "missing smoke" to a hard failure once coverage is high enough.

Usage::

    run_skill_smokes.py [--require-all] [--timeout SECONDS] [--quiet]
                        [--skills-dir DIR]

Exit codes::

    0  every existing smoke passed (and, with --require-all, none missing)
    1  a smoke failed (or a skill is missing one under --require-all)
    2  invocation error (no skills found under the skills dir)

Stdlib-only; safe under bare ``python3``.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPTS_DIR.parents[1]  # .claude/skills/
REPO_ROOT = SCRIPTS_DIR.parents[3]  # repo root


@dataclass
class SmokeResult:
    skill: str
    status: str  # "passed" | "failed" | "missing"
    returncode: int | None = None
    output: str = ""


def discover_skills(skills_dir: Path) -> list[Path]:
    """Return skill dirs — the parent of each ``<skills_dir>/<name>/SKILL.md``.

    The single-level glob deliberately skips ``SKILL.md`` files nested under a
    skill's ``fixtures/`` tree (those are test data for the test-obligation
    detector, not real skills).
    """
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md"))


def run_smoke(skill_dir: Path, *, timeout: int) -> SmokeResult:
    name = skill_dir.name
    smoke = skill_dir / "scripts" / "smoke.py"
    if not smoke.is_file():
        return SmokeResult(skill=name, status="missing")
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(smoke)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SmokeResult(
            skill=name, status="failed", returncode=None, output=f"TIMEOUT after {timeout}s"
        )
    status = "passed" if proc.returncode == 0 else "failed"
    return SmokeResult(
        skill=name,
        status=status,
        returncode=proc.returncode,
        output=(proc.stdout + proc.stderr).strip(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every skill's scripts/smoke.py through one aggregating ecosystem gate."
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Treat a skill with no scripts/smoke.py as a failure (default: report only).",
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="Per-smoke timeout in seconds (default: 120)."
    )
    parser.add_argument(
        "--skills-dir",
        default=str(SKILLS_DIR),
        help="Override the skills directory (default: the ecosystem's own).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-skill PASS/missing lines; show failures + summary only.",
    )
    args = parser.parse_args(argv)

    skills_dir = Path(args.skills_dir).resolve()
    skills = discover_skills(skills_dir)
    if not skills:
        print(f"run_skill_smokes: no skills found under {skills_dir}", file=sys.stderr)
        return 2

    results = [run_smoke(d, timeout=args.timeout) for d in skills]
    passed = [r for r in results if r.status == "passed"]
    failed = [r for r in results if r.status == "failed"]
    missing = [r for r in results if r.status == "missing"]

    for r in failed:
        print(f"FAIL  {r.skill}  (rc={r.returncode})")
        for line in r.output.splitlines():
            print(f"      | {line}")
    if not args.quiet:
        for r in passed:
            print(f"PASS  {r.skill}")
        for r in missing:
            print(f"----  {r.skill}  (no scripts/smoke.py)")

    total = len(results)
    have = len(passed) + len(failed)
    pct = 100 * have // total if total else 0
    print(
        f"\nskill-smokes: {total} skills | {have} with a smoke "
        f"({len(passed)} passed, {len(failed)} failed) | {len(missing)} missing "
        f"| coverage {have}/{total} = {pct}%"
    )

    if failed:
        print(f"GATE FAILED: {len(failed)} smoke(s) failing.", file=sys.stderr)
        return 1
    if args.require_all and missing:
        print(
            f"GATE FAILED (--require-all): {len(missing)} skill(s) have no scripts/smoke.py.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
