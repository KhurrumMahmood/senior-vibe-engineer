"""Natural-language regressions for bounded /which-skill recommendations."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
MATCHER = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"


def _run_match(prompt: str, *extra: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json", "--top", "10", *extra],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode, json.loads(result.stdout)


@pytest.mark.parametrize(
    "prompt",
    [
        "Propose a database migration plan for the users table.",
        "Draft a database migration plan for the accounts table.",
    ],
)
def test_generic_database_migration_plans_proceed_directly(prompt):
    returncode, payload = _run_match(prompt)

    assert returncode == 1, payload
    assert payload["recommendation"] == "proceed_directly"


def test_generic_api_upgrade_plan_never_routes_to_project_organization():
    returncode, payload = _run_match("Write a compatibility plan for upgrading the API.")

    assert returncode in {0, 1}, payload
    assert payload["recommendation"] in {"decide", "proceed_directly"}
    assert payload["recommendation"] != "organize-project-structure"


def test_completed_diagnosis_with_a_narrow_fix_proceeds_directly():
    returncode, payload = _run_match(
        "Do not diagnose this again: the parser failure is already reproduced and the root "
        "cause is known; make the narrow fix and verify it."
    )

    assert returncode == 1, payload
    assert payload["recommendation"] == "proceed_directly"


def test_explicit_ordered_maintenance_loop_routes_to_which_shape():
    returncode, payload = _run_match(
        "Map this inherited subsystem, find duplication, then refactor the approved clusters "
        "and add a regression guard."
    )

    assert returncode == 0, payload
    assert payload["recommendation"] == "which-shape"


def test_natural_rust_marker_returns_pending_without_a_handoff():
    returncode, payload = _run_match(
        "Find an omnibus Rust module with too many unrelated responsibilities."
    )

    assert returncode == 1, payload
    assert payload["routing_context"]["languages"] == ["rust"]
    assert payload["routing_context"]["language_source"] == "task_marker"
    assert payload["recommendation"] == "pending-implementation"
    assert payload["unavailable"]["name"] == "find-omnibus"
    assert "handoff" not in payload


def test_rs_alias_preserves_explicit_language_portability_filtering():
    returncode, payload = _run_match(
        "Find an omnibus module with too many unrelated responsibilities.",
        "--language",
        "rs",
    )

    assert returncode == 1, payload
    assert payload["routing_context"]["languages"] == ["rust"]
    assert payload["routing_context"]["language_source"] == "explicit"
    assert payload["recommendation"] == "pending-implementation"
    assert payload["unavailable"]["name"] == "find-omnibus"


def test_supported_go_skill_has_executable_handoff(tmp_path):
    returncode, payload = _run_match(
        "Use propose-boundary for a Go package boundary.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0
    assert payload["routing_context"]["languages"] == ["go"]
    assert payload["recommendation"] == "propose-boundary"
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["capabilities"]["skills"][0]["go_disposition"] == (
        "go-supported"
    )


def test_newly_supported_go_skill_has_executable_handoff(tmp_path):
    returncode, payload = _run_match(
        "Use adapt-project to onboard this Go repository.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0
    assert payload["routing_context"]["languages"] == ["go"]
    assert payload["recommendation"] == "adapt-project"
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["capabilities"]["skills"][0]["go_disposition"] == (
        "go-supported"
    )


@pytest.mark.parametrize(
    "skill",
    [
        "audit-decisions",
        "explain-code",
        "find-comment-drift",
        "find-concept-divergence",
        "find-folder-topology-drift",
        "find-omnibus",
        "find-standard-gaps",
        "find-implicit-state",
        "extract-enum",
        "prevent-regression",
    ],
)
def test_each_new_go_capability_reaches_its_declared_handoff(tmp_path, skill):
    returncode, payload = _run_match(
        f"Use {skill} on this Go module.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0
    assert payload["recommendation"] == skill
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["capabilities"]["skills"][0]["go_disposition"] == (
        "go-supported"
    )


def test_promoted_go_folder_proposal_reaches_declared_handoff(tmp_path):
    returncode, payload = _run_match(
        "Use propose-folder-reorganization on this Go module.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0
    assert payload["routing_context"]["languages"] == ["go"]
    assert payload["recommendation"] == "propose-folder-reorganization"
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["capabilities"]["skills"][0]["go_disposition"] == (
        "go-supported"
    )


def test_go_state_guard_handoff_includes_detector_companion(tmp_path):
    returncode, payload = _run_match(
        "Use prevent-regression on this Go module.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0
    assert payload["recommendation"] == "prevent-regression"
    assert payload["handoff"]["skills"] == [
        "prevent-regression",
        "find-implicit-state",
    ]
    assert payload["optional_install"]["skills"] == [
        "prevent-regression",
        "find-implicit-state",
    ]
