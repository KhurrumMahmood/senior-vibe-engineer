"""Acceptance contract for full Java language-level coverage."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".claude/tasks/java-language-coverage.json"
MATRIX = ROOT / ".claude/tasks/multilanguage-skill-matrix.json"
ROUTER = ROOT / ".claude/skills/which-skill/scripts/match.py"


def _route(task: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(ROUTER),
            task,
            "--project-root",
            str(ROOT),
            "--library-root",
            str(ROOT),
            "--language",
            "java",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_java_coverage_is_bounded_traceable_and_projected() -> None:
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert len(rows) == 22
    assert Counter(row["disposition"] for row in rows) == {
        "java-supported": 22,
    }
    supported = {row["skill"] for row in rows if row["disposition"] == "java-supported"}
    assert supported == {row["skill"] for row in rows}
    for row in rows:
        assert (ROOT / row["evidence_path"]).is_file()
        assert row["native_check"]
        assert row["reviewed_revision"]

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    projected = {
        row["skill"]
        for row in matrix["skills"]
        if row["java_disposition"] == "java-supported"
    }
    assert projected == supported


def test_java_router_selects_representative_supported_families() -> None:
    cases = {
        "audit syntactic branch complexity in Java methods and constructors": "find-complexity-hotspots",
        "propose a Java package boundary with resolved caller impact": "propose-boundary",
        "move a Java package directory and update imports safely": "move-path",
        "use find-dormant to review unused private Java methods": "find-dormant",
    }
    for task, expected in cases.items():
        payload = _route(task)
        assert payload["recommendation"] == expected, payload
        capability = payload["handoff"]["capabilities"]["skills"][0]
        assert capability["skill"] == expected
        assert capability["java_disposition"] == "java-supported"
        assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"
