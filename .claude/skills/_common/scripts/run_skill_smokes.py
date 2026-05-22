#!/usr/bin/env python3
"""Aggregating skill-ecosystem health gate — the single entry point CI calls to
prove the ecosystem's own skills still run.

Why this exists
---------------
The ecosystem ships 60+ guard/maintenance skills that detect drift in *host*
projects, yet almost none of that machinery was exercised automatically: a
skill could break (an import error, a moved `_common` path, a frontmatter↔
script drift) and rot silently until someone next invoked it by hand. That is
the exact "a contract checker that runs nowhere protects nothing" trap these
skills are built to catch — turned inward on the ecosystem itself.

Two-layer model
---------------
Each skill is evaluated by the strongest check it can support:

* **Explicit smoke** — if the skill has ``scripts/smoke.py`` it is run (exit 0
  required). These verify *behaviour* (e.g. a detector fires on a bad fixture
  and stays clean on a good one). This is the coverage target.
* **Import-floor** — a skill with scripts but no smoke gets every
  ``scripts/*.py`` imported (without running its ``__main__`` block). This is a
  cheap, uniform safety net: it catches syntax errors, ImportError, and moved
  ``_common``/sibling paths — the dominant silent-rot — without verifying
  detection correctness.
* **Prose-only** — a skill with no scripts has nothing to execute; it is
  reported ``n/a`` and excluded from the coverage denominator. Its health is a
  job for the coherence lane (frontmatter↔reality), not this gate.

Blocking vs reporting (mirrors a quality gate's split):

* **Blocking** — any explicit smoke OR import-floor that fails fails the gate
  (exit 1). Every eligible skill is guarded the moment this runs.
* **Reporting** — the coverage ratio (explicit smokes / eligible skills) is
  printed but not enforced by default; coverage climbs over time. Pass
  ``--require-all`` to demand an explicit smoke for every eligible skill once
  coverage is high enough to warrant it.

Usage::

    run_skill_smokes.py [--require-all] [--timeout SECONDS] [--quiet]
                        [--skills-dir DIR]

Exit codes::

    0  every smoke and import-floor passed (and, with --require-all, every
       eligible skill has an explicit smoke)
    1  a smoke or import-floor failed (or an eligible skill lacks an explicit
       smoke under --require-all)
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

# Import a script module WITHOUT running its __main__ block: the spec name
# "_smoke_probe" is not "__main__", so `if __name__ == "__main__"` guards stay
# closed. The script's own dir goes on sys.path first so its sibling imports
# (e.g. `import collapse`) resolve exactly as they do under
# `python scripts/detect.py`.
_IMPORT_PROBE = (
    "import sys, importlib.util as u\n"
    "path, script_dir = sys.argv[1], sys.argv[2]\n"
    "sys.path.insert(0, script_dir)\n"
    "spec = u.spec_from_file_location('_smoke_probe', path)\n"
    "mod = u.module_from_spec(spec)\n"
    # Register before exec: @dataclass/typing look the module up by __module__
    # in sys.modules during class creation; without this they hit None.__dict__.
    "sys.modules['_smoke_probe'] = mod\n"
    "spec.loader.exec_module(mod)\n"
)


@dataclass
class SkillResult:
    skill: str
    kind: str  # "smoke" | "floor" | "prose"
    status: str  # "passed" | "failed" | "n/a"
    returncode: int | None = None
    output: str = ""


def discover_skills(skills_dir: Path) -> list[Path]:
    """Return skill dirs — the parent of each ``<skills_dir>/<name>/SKILL.md``.

    The single-level glob deliberately skips ``SKILL.md`` files nested under a
    skill's ``fixtures/`` tree (those are test data for the test-obligation
    detector, not real skills).
    """
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md"))


def _scripts(skill_dir: Path) -> list[Path]:
    """Smoke-eligible scripts: every ``scripts/*.py`` except smoke.py itself."""
    sdir = skill_dir / "scripts"
    if not sdir.is_dir():
        return []
    return sorted(p for p in sdir.glob("*.py") if p.name != "smoke.py")


def _run(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)


def run_smoke_file(smoke: Path, *, timeout: int) -> tuple[str, int | None, str]:
    try:
        proc = _run([sys.executable, "-B", str(smoke)], timeout=timeout)
    except subprocess.TimeoutExpired:
        return "failed", None, f"TIMEOUT after {timeout}s"
    status = "passed" if proc.returncode == 0 else "failed"
    return status, proc.returncode, (proc.stdout + proc.stderr).strip()


def run_import_floor(scripts: list[Path], *, timeout: int) -> tuple[str, str]:
    failures: list[str] = []
    for script in scripts:
        try:
            proc = _run(
                [sys.executable, "-c", _IMPORT_PROBE, str(script), str(script.parent)],
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{script.name}: TIMEOUT after {timeout}s")
            continue
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            failures.append(f"{script.name}: {detail[-1] if detail else 'import failed'}")
    return ("failed" if failures else "passed", "\n".join(failures))


def evaluate_skill(skill_dir: Path, *, timeout: int) -> SkillResult:
    name = skill_dir.name
    smoke = skill_dir / "scripts" / "smoke.py"
    if smoke.is_file():
        status, rc, out = run_smoke_file(smoke, timeout=timeout)
        return SkillResult(name, "smoke", status, rc, out)
    scripts = _scripts(skill_dir)
    if scripts:
        status, out = run_import_floor(scripts, timeout=timeout)
        return SkillResult(name, "floor", status, None, out)
    return SkillResult(name, "prose", "n/a")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every skill's smoke (or an import-floor) through one aggregating ecosystem gate."
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Require an explicit scripts/smoke.py for every eligible skill (import-floor alone fails the gate).",
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="Per-check timeout in seconds (default: 120)."
    )
    parser.add_argument(
        "--skills-dir",
        default=str(SKILLS_DIR),
        help="Override the skills directory (default: the ecosystem's own).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-skill PASS/prose lines; show failures + summary only.",
    )
    args = parser.parse_args(argv)

    skills_dir = Path(args.skills_dir).resolve()
    skills = discover_skills(skills_dir)
    if not skills:
        print(f"run_skill_smokes: no skills found under {skills_dir}", file=sys.stderr)
        return 2

    results = [evaluate_skill(d, timeout=args.timeout) for d in skills]
    smokes = [r for r in results if r.kind == "smoke"]
    floors = [r for r in results if r.kind == "floor"]
    prose = [r for r in results if r.kind == "prose"]
    failed = [r for r in results if r.status == "failed"]

    for r in failed:
        label = "smoke" if r.kind == "smoke" else "import-floor"
        rc = f", rc={r.returncode}" if r.returncode is not None else ""
        print(f"FAIL  {r.skill}  ({label}{rc})")
        for line in r.output.splitlines():
            print(f"      | {line}")
    if not args.quiet:
        for r in smokes:
            if r.status == "passed":
                print(f"SMOKE {r.skill}")
        for r in floors:
            if r.status == "passed":
                print(f"floor {r.skill}")
        for r in prose:
            print(f"----  {r.skill}  (prose-only, no scripts)")

    eligible = len(smokes) + len(floors)
    smoke_ok = sum(1 for r in smokes if r.status == "passed")
    smoke_fail = len(smokes) - smoke_ok
    floor_ok = sum(1 for r in floors if r.status == "passed")
    floor_fail = len(floors) - floor_ok
    cov = 100 * len(smokes) // eligible if eligible else 0
    print(
        f"\nskill-smokes: {eligible} eligible (+{len(prose)} prose-only) | "
        f"explicit smokes {len(smokes)} ({smoke_ok} ok, {smoke_fail} fail) | "
        f"import-floor {len(floors)} ({floor_ok} ok, {floor_fail} fail) | "
        f"explicit coverage {len(smokes)}/{eligible} = {cov}%"
    )

    if failed:
        print(f"GATE FAILED: {len(failed)} skill check(s) failing.", file=sys.stderr)
        return 1
    if args.require_all and floors:
        names = ", ".join(r.skill for r in floors)
        print(
            f"GATE FAILED (--require-all): {len(floors)} eligible skill(s) have only the "
            f"import-floor, no explicit smoke: {names}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
