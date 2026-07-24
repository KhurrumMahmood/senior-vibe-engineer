"""Release sentinels joining public claims to accepted language evidence."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TASKS = ROOT / ".claude" / "tasks"
MATRIX = TASKS / "multilanguage-skill-matrix.json"
ROUTER = ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"


def _coverage(language: str) -> tuple[int, set[str]]:
    payload = json.loads(
        (TASKS / f"{language}-language-coverage.json").read_text(encoding="utf-8")
    )
    rows = payload["skills"]
    return len(rows), {
        row["skill"] for row in rows if row["disposition"] == f"{language}-supported"
    }


def _route(language: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(ROUTER),
            f"use find-omnibus to inspect a large {language} source file",
            "--project-root",
            str(ROOT),
            "--library-root",
            str(ROOT),
            "--language",
            language,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_public_language_counts_match_coverage_matrix_and_router() -> None:
    readme = " ".join(README.read_text(encoding="utf-8").split())
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))["skills"]

    for display_name, language in (
        ("Go", "go"),
        ("Java", "java"),
        ("Swift", "swift"),
    ):
        row_count, supported = _coverage(language)
        assert row_count == 22
        assert len(supported) == 22

        claims = {
            int(value)
            for value in re.findall(rf"{re.escape(display_name)}[^.]*?(\d+)/22", readme)
        }
        assert claims == {22}, f"README {display_name} claims disagree: {sorted(claims)}"

        projected = {
            row["skill"]
            for row in matrix
            if row[f"{language}_disposition"] == f"{language}-supported"
        }
        assert projected == supported

        routed = _route(language)
        assert routed["recommendation"] == "find-omnibus"
        capability = routed["handoff"]["capabilities"]["skills"][0]
        assert capability[f"{language}_disposition"] == f"{language}-supported"
