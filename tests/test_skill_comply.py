"""End-to-end wrapper for the skill-comply conformance harness.

Black-box via subprocess, matching the suite's convention for script-backed
gates (see test_run_skill_smokes.py): invoke scripts/skill_comply/validate.py,
which seeds a throwaway mini-host git repo per fixture, installs each of the
five proposal fixtures (conformant / defective / over-broad / poisoned-good /
wrong-name), scores by side-effect, and asserts every expected verdict.

Marked slow: each fixture run is a fresh `git init` + several subprocess
invocations (~3s total). Deselect with `-m 'not slow'`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PROJECT_ROOT / "scripts" / "skill_comply" / "validate.py"


@pytest.mark.slow
def test_validate_all_five_fixtures_pass():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"validate.py exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "OVERALL: PASS" in proc.stdout
