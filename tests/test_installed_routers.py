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
STACK_BOUND_SKILLS = (
    "extract-cotton-primitive",
    "extract-state-type",
    "extract-workflow-registry",
    "find-async-lifecycle-drift",
    "find-contract-drift",
    "find-dead-route-surface",
    "find-doc-route-drift",
    "find-frontend-contract-drift",
    "find-frontend-duplication",
    "find-layer-violation",
    "find-query-mutation",
    "find-route-sprawl",
    "find-test-obligation-drift",
    "find-transaction-overreach",
    "find-workflow-duplication",
    "find-workflow-state-gaps",
    "fix-workflow",
    "impact-feature",
    "introduce-fk",
    "map-product-workflow",
    "plan-feature",
    "refactor-subsystem",
)


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


def test_default_routers_materialize_an_on_demand_library_outside_discovery(tmp_path):
    host = tmp_path / "host"
    installed = {
        name: _install_router(host, name)
        for name in DEFAULT_ROUTERS
    }

    bootstrap = _run_isolated(
        installed["which-skill"] / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        cwd=host,
    )

    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr
    library_root = host.parent / ".engineering-skills" / host.name
    assert (library_root / ".claude" / "skills" / "diagnose" / "SKILL.md").is_file()
    assert (library_root / "scripts").is_dir()
    assert {
        path.name
        for path in (host / ".agents" / "skills").iterdir()
        if path.is_dir()
    } == set(DEFAULT_ROUTERS)

    repeated = _run_isolated(
        installed["which-skill"] / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        cwd=host,
    )
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert "already available" in repeated.stdout

    routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "diagnose failing export job regression with no reproduction yet",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    payload = _json_output(routed)
    assert "install" not in payload
    assert payload["handoff"]["mode"] == "on_demand_library"
    assert payload["handoff"]["available"] is True
    assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"
    assert payload["handoff"]["guides"] == [
        {
            "skill": "diagnose",
            "skill_root": str(library_root / ".claude" / "skills" / "diagnose"),
            "guide": str(library_root / ".claude" / "skills" / "diagnose" / "SKILL.md"),
            "bundled_tooling": str(
                library_root / ".claude" / "skills" / "diagnose" / "scripts"
            ),
        }
    ]
    assert payload["handoff"]["shared_tooling"] == str(library_root / "scripts")
    assert payload["handoff"]["common_guidance"] == str(
        library_root / ".claude" / "skills" / "_common"
    )
    assert payload["handoff"]["shared_guidance"] == str(library_root / ".claude" / "docs")
    assert "--skill diagnose" in payload["optional_install"]["command"]

    resource_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use plan-feature to plan this Django workflow",
        "--project-root",
        str(host),
        "--language",
        "python",
        "--framework",
        "django",
        "--json",
        cwd=host,
    )
    resource_payload = _json_output(resource_routed)
    assert resource_payload["recommendation"] == "plan-feature"
    selected_root = Path(resource_payload["handoff"]["guides"][0]["skill_root"])
    assert (selected_root / "agents" / "impact-scout.md").is_file()
    assert (selected_root / "knowledge").is_dir()


def test_library_bootstrap_refuses_to_overwrite_an_existing_incomplete_destination(tmp_path):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")
    library_root = host.parent / ".engineering-skills" / host.name
    library_root.mkdir(parents=True)
    sentinel = library_root / "KEEP.txt"
    sentinel.write_text("owned by host\n", encoding="utf-8")

    result = _run_isolated(
        router / "scripts" / "bootstrap_library.py",
        "--project-root",
        str(host),
        "--source",
        str(REPO_ROOT),
        cwd=host,
    )

    assert result.returncode == 2
    assert "existing library is incomplete" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "owned by host\n"


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
        assert payload["handoff"]["skills"] == ["adapt-project"]
        assert payload["optional_install"]["skill"] == "adapt-project"
        assert "--skill adapt-project" in payload["optional_install"]["command"]
    else:
        assert "handoff" not in payload
        assert "optional_install" not in payload


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
    assert payload["handoff"]["skills"] == [expected_skill]
    assert f"--skill {expected_skill}" in payload["optional_install"]["command"]


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
    assert payload["handoff"]["skills"] == ["find-implicit-state"]


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
    assert payload["handoff"]["skills"] == ["explain-code"]


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
        (
            "propose a TypeScript boundary from resolved symbol import and call evidence",
            "propose-boundary",
        ),
        (
            "propose reorganizing a TypeScript flat prefix folder cluster with resolved "
            "import impact",
            "propose-folder-reorganization",
        ),
        (
            "audit TypeScript private implementations for statically unreferenced "
            "dormant code",
            "find-dormant",
        ),
        (
            "audit TypeScript call sites for an incomplete option property sweep",
            "find-incomplete-sweep",
        ),
        (
            "audit TypeScript functions for semantic duplication with the same "
            "typed outcome and different code",
            "find-semantic-duplication",
        ),
        (
            "turn a confirmed TypeScript semantic finding into an implementation-ready "
            "proposal with caller impact and a stop condition",
            "unify-shadows",
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
    assert payload["handoff"]["skills"][0] == expected_skill


def test_default_router_set_is_exactly_three():
    assert DEFAULT_ROUTERS == ("which-shape", "which-skill", "which-cleanup")


@pytest.mark.parametrize(
    ("task", "excluded_skill"),
    [
        ("plan a TypeScript feature across one workflow", "plan-feature"),
        (
            "use impact-feature to map TypeScript touched subsystem blast radius",
            "impact-feature",
        ),
    ],
)
def test_installed_which_skill_excludes_stack_bound_planning_claims(
    tmp_path, task, excluded_skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        task,
        "--project-root",
        str(host),
        "--top",
        "20",
        "--json",
        cwd=host,
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "unsupported"
    assert payload["unsupported"]["name"] == excluded_skill
    excluded = {item["name"] for item in payload["excluded_unsupported"]}
    assert excluded_skill in excluded


@pytest.mark.parametrize("skill", STACK_BOUND_SKILLS)
def test_installed_which_skill_never_substitutes_for_named_stack_bound_skill(
    tmp_path, skill
):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")

    result = _run_isolated(
        router / "scripts" / "match.py",
        f"use {skill} on this TypeScript project",
        "--project-root",
        str(host),
        "--top",
        "20",
        "--json",
        cwd=host,
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"] == "unsupported"
    assert payload["unsupported"]["name"] == skill


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
    handoff = recommendations["find-test-obligation-drift"]["handoff"]
    assert handoff["skills"] == ["find-test-obligation-drift"]
    optional_install = recommendations["find-test-obligation-drift"]["optional_install"]
    assert optional_install["source"] == "/tmp/engineering-skills-source"
    assert "--skill find-test-obligation-drift" in optional_install["command"]
