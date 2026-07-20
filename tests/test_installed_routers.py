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
    assert payload["handoff"]["source_inventory_tool"] == str(
        library_root / "scripts" / "source_inventory.py"
    )
    assert payload["handoff"]["capabilities"]["available"] is True
    assert payload["handoff"]["capabilities"]["manifest"] == str(
        library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    )
    assert payload["handoff"]["capabilities"]["skills"] == [
        {
            "skill": "diagnose",
            "expansion_disposition": "validated-neutral",
            "typescript_disposition": "validated-neutral",
            "javascript_disposition": "validated-neutral",
            "go_disposition": "validated-neutral",
            "fact_level": "neutral",
            "outcome_class": "not-applicable",
            "framework_family": None,
            "closure_skills": ["diagnose"],
            "optional_install_status": "passed",
        }
    ]
    assert payload["optional_install"]["available"] is True
    assert payload["optional_install"]["evidence"] == [
        {"skill": "diagnose", "status": "passed"}
    ]
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
    assert resource_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "plan-feature",
        "expansion_disposition": "framework-bound",
        "typescript_disposition": "stack-bound",
        "javascript_disposition": "stack-bound",
        "go_disposition": "stack-bound",
        "fact_level": "framework",
        "outcome_class": "framework-specific",
        "framework_family": "architecture-planning",
        "closure_skills": ["plan-feature"],
        "optional_install_status": "deferred-named-stack",
    }
    assert resource_payload["optional_install"]["available"] is False
    assert (
        resource_payload["optional_install"]["reason"]
        == "selected_skill_install_not_validated"
    )
    assert "command" not in resource_payload["optional_install"]

    typescript_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "find repeated bare status literals in src/job.ts",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    typescript_payload = _json_output(typescript_routed)
    assert typescript_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "find-implicit-state",
        "expansion_disposition": "language-level",
        "typescript_disposition": "typescript-supported",
        "javascript_disposition": "javascript-supported",
        "go_disposition": "pending-validation",
        "fact_level": "semantic-project",
        "outcome_class": "read-only-report",
        "framework_family": None,
        "closure_skills": ["find-implicit-state"],
        "optional_install_status": "passed",
    }

    for skill, task in (
        ("find-complexity-hotspots", "use find-complexity-hotspots on Go source"),
        ("propose-boundary", "use propose-boundary for a Go package boundary"),
        ("move-path", "use move-path to move a Go package directory"),
    ):
        go_routed = _run_isolated(
            installed["which-skill"] / "scripts" / "match.py",
            task,
            "--project-root",
            str(host),
            "--json",
            cwd=host,
        )
        go_payload = _json_output(go_routed)
        assert go_payload["recommendation"] == skill
        assert go_payload["handoff"]["available"] is True
        assert go_payload["handoff"]["capabilities"]["skills"][0][
            "go_disposition"
        ] == "go-pilot-supported"
        assert Path(go_payload["handoff"]["guides"][0]["guide"]).is_file()

    shape_routed = _run_isolated(
        installed["which-shape"] / "scripts" / "route.py",
        "onboard an unknown inherited repo and figure out what loop to run",
        "--project-root",
        str(host),
        "--json",
        "--skip-log",
        cwd=host,
    )
    shape_payload = _json_output(shape_routed)
    assert shape_payload["handoff"]["capabilities"]["skills"][0] == {
        "skill": "adapt-project",
        "expansion_disposition": "language-level",
        "typescript_disposition": "typescript-supported",
        "javascript_disposition": "javascript-supported",
        "go_disposition": "pending-validation",
        "fact_level": "lexical-filesystem",
        "outcome_class": "configuration-output",
        "framework_family": None,
        "closure_skills": ["adapt-project"],
        "optional_install_status": "passed",
    }

    cleanup_routed = _run_isolated(
        installed["which-cleanup"] / "scripts" / "route.py",
        "src/app.py",
        "tests/test_app.py",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    cleanup_payload = _json_output(cleanup_routed)
    cleanup_recommendations = {
        item["skill"]: item for item in cleanup_payload["recommendations"]
    }
    assert cleanup_recommendations["find-test-obligation-drift"]["handoff"][
        "capabilities"
    ]["skills"][0] == {
        "skill": "find-test-obligation-drift",
        "expansion_disposition": "framework-bound",
        "typescript_disposition": "stack-bound",
        "javascript_disposition": "stack-bound",
        "go_disposition": "stack-bound",
        "fact_level": "framework",
        "outcome_class": "framework-specific",
        "framework_family": "framework-quality",
        "closure_skills": ["find-test-obligation-drift"],
        "optional_install_status": "deferred-named-stack",
    }
    cleanup_install = cleanup_recommendations["find-test-obligation-drift"][
        "optional_install"
    ]
    assert cleanup_install["available"] is False
    assert cleanup_install["reason"] == "selected_skill_install_not_validated"
    assert "command" not in cleanup_install

    rename_routed = _run_isolated(
        installed["which-skill"] / "scripts" / "match.py",
        "use rename-concept to rename the TypeScript domain term",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )
    rename_payload = _json_output(rename_routed)
    rename_capabilities = rename_payload["handoff"]["capabilities"]
    assert rename_payload["handoff"]["skills"] == [
        "rename-concept",
        "find-concept-divergence",
    ]
    assert rename_capabilities["available"] is True
    assert rename_capabilities["skills"][0]["closure_skills"] == [
        "rename-concept",
        "find-concept-divergence",
    ]
    assert [row["optional_install_status"] for row in rename_capabilities["skills"]] == [
        "passed",
        "passed",
    ]
    assert rename_payload["optional_install"]["available"] is True
    assert "--skill rename-concept" in rename_payload["optional_install"]["command"]
    assert "--skill find-concept-divergence" in rename_payload["optional_install"][
        "command"
    ]


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
    "corruption",
    ["wrong-root", "schema", "duplicate", "missing-selected", "closure-mismatch"],
)
def test_installed_router_reports_invalid_capability_manifest(tmp_path, corruption):
    host = tmp_path / "host"
    router = _install_router(host, "which-skill")
    library_root = host.parent / ".engineering-skills" / host.name
    guide = library_root / ".claude" / "skills" / "diagnose" / "SKILL.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# diagnose\n", encoding="utf-8")
    manifest = library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    manifest.parent.mkdir(parents=True)
    payload = json.loads(
        (REPO_ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    diagnose = next(row for row in payload["skills"] if row["skill"] == "diagnose")
    if corruption == "wrong-root":
        payload = []
    elif corruption == "schema":
        payload["schema_version"] = 999
    elif corruption == "duplicate":
        payload["skills"].append(dict(diagnose))
    elif corruption == "missing-selected":
        payload["skills"] = [row for row in payload["skills"] if row["skill"] != "diagnose"]
    else:
        diagnose["on_demand_closure"]["closure_skills"] = [
            "diagnose",
            "find-duplication",
        ]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_isolated(
        router / "scripts" / "match.py",
        "diagnose failing export job regression with no reproduction yet",
        "--project-root",
        str(host),
        "--json",
        cwd=host,
    )

    routed = _json_output(result)
    assert routed["recommendation"] == "diagnose"
    assert routed["handoff"]["capabilities"] == {
        "available": False,
        "manifest": str(manifest),
        "skills": [],
        "reason": "manifest_invalid_or_incomplete",
    }


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
        assert payload["optional_install"]["available"] is False
        assert payload["optional_install"]["reason"] == "manifest_missing"
        assert "command" not in payload["optional_install"]
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
    assert payload["optional_install"]["available"] is False
    assert payload["optional_install"]["reason"] == "manifest_missing"
    assert "command" not in payload["optional_install"]


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
    assert payload["handoff"]["capabilities"]["available"] is False
    assert payload["handoff"]["capabilities"]["reason"] == "manifest_missing"


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
    assert handoff["capabilities"]["available"] is False
    assert handoff["capabilities"]["reason"] == "manifest_missing"
    optional_install = recommendations["find-test-obligation-drift"]["optional_install"]
    assert optional_install["source"] == "/tmp/engineering-skills-source"
    assert optional_install["available"] is False
    assert optional_install["reason"] == "manifest_missing"
    assert "command" not in optional_install
