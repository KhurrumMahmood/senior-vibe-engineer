"""Tests for the ecosystem skill-health gate
(.claude/skills/_common/scripts/run_skill_smokes.py).

Black-box via subprocess against a synthetic skills tree (using --skills-dir),
exercising the two-layer contract: explicit smokes, the import-floor for
script-bearing skills without a smoke, prose-only skills as n/a, --require-all
promotion, fixtures-subtree exclusion, and timeout-as-failure.

Includes a regression guard for the import-floor's sys.modules registration:
a module-level @dataclass must import cleanly (the dataclass machinery looks
its module up by __module__ during class creation).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / ".claude" / "skills" / "_common" / "scripts" / "run_skill_smokes.py"

PASS_SMOKE = "print('ok')\n"
FAIL_SMOKE = "import sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n"

CLEAN_SCRIPT = "VALUE = 1\n"
BROKEN_IMPORT_SCRIPT = "import totally_missing_module_xyz_123  # noqa\n"
DATACLASS_SCRIPT = "from dataclasses import dataclass\n\n\n@dataclass\nclass Thing:\n    x: int = 0\n"
MAIN_RAISES_SCRIPT = (
    "def main():\n"
    "    raise SystemExit('boom-main')\n\n\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)


def make_skill(skills_dir: Path, name: str, *, smoke: str | None = None,
               scripts: dict[str, str] | None = None) -> None:
    skill = skills_dir / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    if smoke is not None or scripts:
        sdir = skill / "scripts"
        sdir.mkdir()
        if smoke is not None:
            (sdir / "smoke.py").write_text(smoke, encoding="utf-8")
        for fname, body in (scripts or {}).items():
            (sdir / fname).write_text(body, encoding="utf-8")


def run_gate(skills_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--skills-dir", str(skills_dir), *extra],
        capture_output=True,
        text=True,
    )


def test_explicit_smokes_pass(tmp_path):
    make_skill(tmp_path, "alpha", smoke=PASS_SMOKE)
    make_skill(tmp_path, "beta", smoke=PASS_SMOKE)
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "explicit smokes 2" in res.stdout


def test_failing_smoke_fails_gate_and_surfaces_output(tmp_path):
    make_skill(tmp_path, "alpha", smoke=PASS_SMOKE)
    make_skill(tmp_path, "beta", smoke=FAIL_SMOKE)
    res = run_gate(tmp_path)
    assert res.returncode == 1
    assert "FAIL  beta  (smoke" in res.stdout
    assert "boom" in res.stdout  # captured smoke output surfaced, not swallowed


def test_prose_only_skill_is_na_and_passes(tmp_path):
    make_skill(tmp_path, "alpha", smoke=PASS_SMOKE)
    make_skill(tmp_path, "guide")  # no scripts at all
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "prose-only" in res.stdout
    assert "+1 prose-only" in res.stdout


def test_import_floor_passes_for_clean_script(tmp_path):
    make_skill(tmp_path, "alpha", scripts={"tool.py": CLEAN_SCRIPT})
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "import-floor 1 (1 ok" in res.stdout


def test_import_floor_catches_broken_import(tmp_path):
    make_skill(tmp_path, "needy", scripts={"tool.py": BROKEN_IMPORT_SCRIPT})
    res = run_gate(tmp_path)
    assert res.returncode == 1
    assert "FAIL  needy  (import-floor)" in res.stdout
    assert "tool.py" in res.stdout


def test_import_floor_does_not_run_main(tmp_path):
    # Importing the module must not execute its __main__ block.
    make_skill(tmp_path, "guarded", scripts={"tool.py": MAIN_RAISES_SCRIPT})
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "boom-main" not in (res.stdout + res.stderr)


def test_import_floor_handles_module_level_dataclass(tmp_path):
    # Regression guard: a @dataclass at module scope must import cleanly. This
    # only passes if the probe registers the module in sys.modules before exec.
    make_skill(tmp_path, "dc", scripts={"tool.py": DATACLASS_SCRIPT})
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "import-floor 1 (1 ok" in res.stdout


def test_require_all_fails_on_floor_only_skill(tmp_path):
    make_skill(tmp_path, "alpha", smoke=PASS_SMOKE)
    make_skill(tmp_path, "needy", scripts={"tool.py": CLEAN_SCRIPT})
    res = run_gate(tmp_path, "--require-all")
    assert res.returncode == 1
    assert "no explicit smoke" in res.stderr
    assert "needy" in res.stderr


def test_no_skills_is_invocation_error(tmp_path):
    res = run_gate(tmp_path)  # empty dir — no */SKILL.md
    assert res.returncode == 2


def test_fixtures_subtree_is_not_treated_as_a_skill(tmp_path):
    make_skill(tmp_path, "alpha", smoke=PASS_SMOKE)
    nested = tmp_path / "alpha" / "fixtures" / "bad" / ".claude" / "skills" / "find-bad"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("# find-bad\n", encoding="utf-8")
    res = run_gate(tmp_path)
    assert res.returncode == 0, res.stderr
    assert "1 eligible" in res.stdout  # only alpha, not the nested fixture skill


def test_smoke_timeout_counts_as_failure(tmp_path):
    make_skill(tmp_path, "slow", smoke="import time\ntime.sleep(30)\n")
    res = run_gate(tmp_path, "--timeout", "1")
    assert res.returncode == 1
    assert "TIMEOUT" in res.stdout
