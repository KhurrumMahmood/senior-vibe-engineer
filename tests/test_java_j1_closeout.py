"""Serial acceptance contract for the bounded three-family Java pilot."""
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
        "java-supported": 3,
        "pending-validation": 19,
    }
    supported = {row["skill"] for row in rows if row["disposition"] == "java-supported"}
    assert supported == {"find-complexity-hotspots", "propose-boundary", "move-path"}
    for row in rows:
        if row["disposition"] == "java-supported":
            assert (ROOT / row["evidence_path"]).is_file()
            assert row["native_check"]
            assert row["reviewed_revision"]
        else:
            assert row["evidence_path"] is None
            assert row["native_check"] is None
            assert row["reviewed_revision"] is None

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    projected = {
        row["skill"]
        for row in matrix["skills"]
        if row["java_disposition"] == "java-supported"
    }
    assert projected == supported


def test_java_router_selects_supported_families_and_refuses_pending_family() -> None:
    cases = {
        "audit syntactic branch complexity in Java methods and constructors": "find-complexity-hotspots",
        "propose a Java package boundary with resolved caller impact": "propose-boundary",
        "move a Java package directory and update imports safely": "move-path",
    }
    for task, expected in cases.items():
        payload = _route(task)
        assert payload["recommendation"] == expected, payload
        capability = payload["handoff"]["capabilities"]["skills"][0]
        assert capability["skill"] == expected
        assert capability["java_disposition"] == "java-supported"
        assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"

    unsupported = _route("use find-dormant to remove unused Java methods")
    assert unsupported["recommendation"] == "unsupported"
    assert unsupported["unsupported"]["reason"] in {
        "scanner does not declare scans=java",
        "/find-dormant declares java_disposition=pending-validation",
    }
