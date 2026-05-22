"""Tests for the ecosystem skill-smoke gate
(.claude/skills/_common/scripts/run_skill_smokes.py).

Black-box via subprocess against a synthetic skills tree (using --skills-dir),
exercising the real CLI contract: blocking on a failing smoke, reporting (not
failing) on a missing smoke by default, --require-all promotion, the
fixtures-subtree exclusion, and timeout-as-failure.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / ".claude" / "skills" / "_common" / "scripts" / "run_skill_smokes.py"

PASS_SMOKE = "print('ok')\n"
FAIL_SMOKE = "import sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n"


def make_skill(skills_dir: Path, name: str, smoke_body: str | None) -> None:
    skill = skills_dir / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    if smoke_body is not None:
        scripts = skill / "scripts"
        scripts.mkdir()
        (scripts / "smoke.py").write_text(smoke_body, encoding="utf-8")


def run_gate(skills_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--skills-dir", str(skills_dir), *extra],
        capture_output=True,
        text=True,
    )


def test_all_smokes_pass(tmp_path):
    make_skill(tmp_path, "alpha", PASS_SMOKE)
    make_skill(tmp_path, "beta", PASS_SMOKE)
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "2 passed" in res.stdout


def test_failing_smoke_fails_gate_and_surfaces_output(tmp_path):
    make_skill(tmp_path, "alpha", PASS_SMOKE)
    make_skill(tmp_path, "beta", FAIL_SMOKE)
    res = run_gate(tmp_path)
    assert res.returncode == 1
    assert "FAIL  beta" in res.stdout
    assert "boom" in res.stdout  # captured smoke output is surfaced, not swallowed


def test_missing_smoke_reports_but_passes_by_default(tmp_path):
    make_skill(tmp_path, "alpha", PASS_SMOKE)
    make_skill(tmp_path, "needy", None)
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "1 missing" in res.stdout


def test_require_all_promotes_missing_to_failure(tmp_path):
    make_skill(tmp_path, "alpha", PASS_SMOKE)
    make_skill(tmp_path, "needy", None)
    res = run_gate(tmp_path, "--require-all")
    assert res.returncode == 1
    assert "no scripts/smoke.py" in res.stderr


def test_no_skills_is_invocation_error(tmp_path):
    res = run_gate(tmp_path)  # empty dir — no */SKILL.md
    assert res.returncode == 2


def test_fixtures_subtree_is_not_treated_as_a_skill(tmp_path):
    # A SKILL.md nested under a skill's fixtures/ tree must not be enumerated.
    make_skill(tmp_path, "alpha", PASS_SMOKE)
    nested = tmp_path / "alpha" / "fixtures" / "bad" / ".claude" / "skills" / "find-bad"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("# find-bad\n", encoding="utf-8")
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "1 skills" in res.stdout  # only alpha, not the nested fixture skill


def test_timeout_counts_as_failure(tmp_path):
    make_skill(tmp_path, "slow", "import time\ntime.sleep(30)\n")
    res = run_gate(tmp_path, "--timeout", "1")
    assert res.returncode == 1
    assert "TIMEOUT" in res.stdout
