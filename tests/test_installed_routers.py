from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
DEFAULT_ROUTERS = ("which-shape", "which-skill", "which-cleanup")


def _install_router(host: Path, name: str) -> Path:
    destination = host / ".agents" / "skills" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILLS_ROOT / name, destination)
    return destination


def _run_isolated(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )


def _json_output(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("task", "expected_shape"),
    [
        ("fix one-line typo in the status label", "direct-change"),
        ("this inherited repo feels slow and chaotic", "project-intake"),
    ],
)
def test_installed_which_shape_runs_without_repository_runtime(
    tmp_path, task, expected_shape
):
    host = tmp_path / "host"
    router = _install_router(host, "which-shape")

    result = _run_isolated(
        router / "scripts" / "route.py",
        task,
        "--project-root",
        str(host),
        "--json",
        "--skip-log",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["recommendation"]["shape"] == expected_shape
    if expected_shape == "project-intake":
        assert payload["install"]["skill"] == "adapt-project"
        assert "--skill adapt-project" in payload["install"]["command"]
    else:
        assert "install" not in payload


@pytest.mark.parametrize(
    ("task", "expected_skill"),
    [
        ("diagnose failing export job regression with no reproduction yet", "diagnose"),
        ("create a new skill for constructive UI forms", "plan-skill"),
    ],
)
def test_installed_which_skill_runs_with_bundled_catalog(
    tmp_path, task, expected_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["recommendation"] == expected_skill
    assert payload["task_packet"]["produces"]
    assert f"--skill {expected_skill}" in payload["install"]["command"]


def test_installed_which_skill_routes_earned_typescript_state_skill(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "find repeated bare status literals in src/job.ts",
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["routing_context"]["language_source"] == "task_marker"
    assert payload["recommendation"] == "find-implicit-state"
    assert payload["install"]["skill"] == "find-implicit-state"


def test_installed_which_skill_routes_typescript_explanation(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "produce an annotated behavior doc for the direct public exports "
        "in this TypeScript module",
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "explain-code"
    assert payload["install"]["skill"] == "explain-code"


@pytest.mark.parametrize(
    ("task", "expected_skill"),
    [
        (
            "find an omnibus TypeScript module with too many unrelated "
            "responsibilities",
            "find-omnibus",
        ),
        (
            "audit TypeScript lexical clone clusters with reliable source "
            "spans and enclosing symbols",
            "find-duplication",
        ),
        (
            "audit syntactic branch complexity in TypeScript functions and methods",
            "find-complexity-hotspots",
        ),
        (
            "audit a TypeScript source root for a flat prefix filename cluster "
            "among direct siblings",
            "find-folder-topology-drift",
        ),
        (
            "onboard a TypeScript repository by discovering objective stack CI "
            "test and source-root facts",
            "adapt-project",
        ),
        (
            "check coverage gaps where a declared TypeScript standard requires "
            "direct JSON.parse calls to be enclosed by try",
            "find-standard-gaps",
        ),
        (
            "audit decision registry drift and TypeScript decision references",
            "audit-decisions",
        ),
        (
            "map a TypeScript subsystem exported surface and resolved imports",
            "map-subsystem",
        ),
        (
            "assess a TypeScript glossary concept rename lifecycle and completeness gate",
            "rename-concept",
        ),
    ],
)
def test_installed_which_skill_routes_typescript_analysis_skills(
    tmp_path, task, expected_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--top",
        "10",
        "--json",
        cwd=host,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == expected_skill
    assert payload["install"]["skill"] == expected_skill


def test_default_router_set_is_exactly_three():
    assert DEFAULT_ROUTERS == ("which-shape", "which-skill", "which-cleanup")


def test_installed_which_cleanup_routes_without_repository_runtime(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-cleanup")

    result = _run_isolated(
        router / "scripts" / "route.py",
        "src/app.py",
        "tests/test_app.py",
        "--project-root",
        str(host),
        "--source",
        "/tmp/engineering-skills-source",
        "--json",
        cwd=host,
    )

    payload = _json_output(result)
    assert payload["scope_band"] == "small"
    recommendations = {item["skill"]: item for item in payload["recommendations"]}
    assert "find-test-obligation-drift" in recommendations
    handoff = recommendations["find-test-obligation-drift"]["install"]
    assert handoff["source"] == "/tmp/engineering-skills-source"
    assert "--skill find-test-obligation-drift" in handoff["command"]
