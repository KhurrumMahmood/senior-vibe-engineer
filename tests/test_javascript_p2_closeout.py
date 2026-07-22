"""Serial acceptance contract for completing JavaScript P2 coverage."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COVERAGE = REPO_ROOT / ".claude" / "tasks" / "javascript-language-coverage.json"
MATRIX = REPO_ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
ROUTER = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"


def _route(task: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(ROUTER),
            task,
            "--project-root",
            str(REPO_ROOT),
            "--library-root",
            str(REPO_ROOT),
            "--language",
            "javascript",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_all_language_level_skills_have_final_javascript_evidence() -> None:
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]

    assert len(rows) == 22
    dispositions = Counter(row["disposition"] for row in rows)
    assert not dispositions["pending-validation"]
    assert set(dispositions) <= {"javascript-supported", "javascript-limited"}
    assert sum(dispositions.values()) == 22
    for row in rows:
        assert row["evidence_modes"] != ["pending"], row
        assert (REPO_ROOT / row["evidence_path"]).is_file(), row
        assert row["native_check"], row
        assert row["reviewed_revision"], row

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    language_rows = [
        row
        for row in matrix["skills"]
        if row["expansion_disposition"] == "language-level"
    ]
    assert len(language_rows) == 22
    assert {row["javascript_disposition"] for row in language_rows} <= {
        "javascript-supported",
        "javascript-limited",
    }


def test_router_projects_proposal_mutation_and_guard_capabilities() -> None:
    cases = {
        "propose a module boundary for src/legacy.js with caller impact and a compatibility plan": "propose-boundary",
        "move src/legacy.js to src/core/legacy.js and update references safely": "move-path",
        "turn this recurring JavaScript import invariant into a permanent guardrail": "prevent-regression",
    }

    for task, expected in cases.items():
        payload = _route(task)
        assert payload["recommendation"] == expected, payload
        handoff = payload["handoff"]
        assert handoff["available"] is True
        assert handoff["default_execution"] == "fresh_non_context_subagent"
        assert handoff["skills"][0] == expected
        capability = handoff["capabilities"]["skills"][0]
        assert capability["skill"] == expected
        assert capability["javascript_disposition"] == "javascript-supported"
        assert Path(handoff["guides"][0]["guide"]).is_file()
