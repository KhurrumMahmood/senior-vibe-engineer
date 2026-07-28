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
REAL_REPO_STATUS = TASKS / "real-repository-validation-status.json"
REAL_REPO_CORPUS = TASKS / "real-repository-corpus.json"
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


def test_public_validation_claims_are_separate_pinned_and_traceable() -> None:
    readme_lines = README.read_text(encoding="utf-8").splitlines()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    status = json.loads(REAL_REPO_STATUS.read_text(encoding="utf-8"))
    corpus = json.loads(REAL_REPO_CORPUS.read_text(encoding="utf-8"))
    projected = {row["language"]: row for row in matrix["language_validation"]}
    declared = {row["language"]: row for row in status["languages"]}
    pinned = {row["language"]: row for row in corpus["repositories"]}

    assert matrix["language_validation"] == sorted(
        status["languages"], key=lambda row: row["language"]
    )
    assert set(projected) == set(declared) == set(pinned) | {"python"}
    for language, row in projected.items():
        assert row["validation_level"] == "journey-validated"
        assert (ROOT / row["evidence_path"]).is_file()
        assert len(row["revision"]) == 40
        if language in pinned:
            assert row["repository"] == pinned[language]["name"]
            assert row["revision"] == pinned[language]["revision"]

    display_names = {
        "python": "Python", "typescript": "TypeScript", "javascript": "JavaScript",
        "go": "Go", "java": "Java", "php": "PHP", "ruby": "Ruby",
        "swift": "Swift", "rust": "Rust", "dart": "Dart", "c": "C",
        "cpp": "C++", "kotlin": "Kotlin", "csharp": "C#",
    }
    for language, display in display_names.items():
        matches = [line for line in readme_lines if line.startswith(f"| {display} |")]
        assert len(matches) == 1
        assert "journey-validated" in matches[0]
        expected_coverage = "Original host contract" if language == "python" else "22/22"
        assert expected_coverage in matches[0]
