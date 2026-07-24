from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MATCHER = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"
CATALOG_BUILDER = REPO_ROOT / "scripts" / "build_router_catalog.py"


def _run_match(prompt: str, *extra: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json", *extra],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode, json.loads(result.stdout)


def _match(prompt: str) -> dict:
    returncode, payload = _run_match(prompt)
    assert returncode == 0, payload
    return payload


def test_diagnose_prompt_routes_to_diagnose():
    payload = _match("diagnose failing export job regression with no reproduction yet")

    assert payload["recommendation"] == "diagnose"
    assert payload["inferred_tier"] == "maintenance"
    assert payload["inferred_job"] == "diagnose"
    assert "reproduction_loop" in payload["task_packet"]["produces"]


def test_natural_spaced_skill_name_routes_to_gut_check():
    payload = _match(
        "review the supplied architecture plan for strong engineering smells "
        "and give a bounded gut check"
    )

    assert payload["recommendation"] == "gut-check"
    assert payload["candidates"][0]["rationale"][0] == "natural skill name: check gut"


def test_bundled_catalog_matches_source_frontmatter():
    result = subprocess.run(
        [sys.executable, str(CATALOG_BUILDER), "--check"],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "76 skills" in result.stdout

    catalog = json.loads(
        (REPO_ROOT / ".claude" / "skills" / "which-skill" / "catalog.json").read_text(
            encoding="utf-8"
        )
    )
    omnibus = next(skill for skill in catalog["skills"] if skill["name"] == "find-omnibus")
    assert omnibus["language"] == "any"
    assert omnibus["framework"] == "any"
    assert omnibus["scans"] == [
        "python",
        "javascript",
        "typescript",
        "go",
        "java",
        "kotlin",
        "php",
        "ruby",
        "rust",
        "dart",
        "swift",
        "c",
        "cpp",
    ]


def test_new_skill_prompt_routes_to_plan_skill():
    payload = _match("create a new skill for constructive UI forms")

    assert payload["recommendation"] == "plan-skill"
    assert payload["inferred_tier"] == "cross-cutting"
    assert payload["inferred_job"] == "plan"
    assert "adversarial_review" in payload["task_packet"]["evidence_required"]


def test_tiny_skill_wording_prompt_proceeds_directly():
    returncode, payload = _run_match("tiny wording fix in an existing skill doc")

    assert returncode == 1
    assert payload["recommendation"] == "proceed_directly"
    assert payload["inferred_tier"] == "quick"


def test_one_line_debug_prompt_does_not_trigger_diagnose():
    returncode, payload = _run_match("debug a one-line typo in a status label")

    assert returncode == 1
    assert payload["recommendation"] == "proceed_directly"
    assert payload["inferred_tier"] == "quick"


def test_glossary_backed_typescript_rename_is_not_short_circuited_as_quick():
    returncode, payload = _run_match(
        "assess a TypeScript glossary concept rename lifecycle and completeness gate",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "rename-concept"
    assert payload["handoff"]["skills"][0] == "rename-concept"


def test_checked_javascript_file_move_routes_to_move_path_not_concept_rename():
    returncode, payload = _run_match(
        "Move src/old.js to lib/new.js, update every safe affected JavaScript "
        "import and the checked-project configuration, and verify the project "
        "still works. Keep unrelated TypeScript source unchanged.",
        "--language",
        "javascript",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["recommendation"] == "move-path"
    assert payload["handoff"]["skills"][0] == "move-path"


def test_generic_upgrade_plans_do_not_route_to_boundary_proposal():
    for task in (
        "propose a database migration plan for the users table",
        "write a compatibility plan for upgrading the API",
    ):
        _returncode, payload = _run_match(task, "--top", "10")

        assert payload["recommendation"] != "propose-boundary"


def test_explicit_mixed_javascript_boundary_still_routes_to_propose_boundary():
    returncode, payload = _run_match(
        "This inherited mixed JavaScript/TypeScript project has several concerns "
        "under src/boundary. Propose a maintainable module boundary for that target, "
        "including public API, caller impact, compatibility plan, and verification plan. "
        "Do not modify source.",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["recommendation"] == "propose-boundary"


def test_exact_typescript_marker_routes_to_earned_state_skill():
    returncode, payload = _run_match(
        "find repeated bare status literals in a TypeScript source file",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"] == {
        "language": "typescript",
        "languages": ["typescript"],
        "language_source": "task_marker",
        "task_language_markers": ["typescript"],
        "framework": None,
        "frameworks": [],
        "framework_source": None,
        "filtering_applied": True,
    }
    assert payload["recommendation"] == "find-implicit-state"
    assert payload["handoff"]["skills"][0] == "find-implicit-state"


def test_typescript_direct_export_explanation_routes_to_explain_code():
    returncode, payload = _run_match(
        "produce an annotated behavior doc for the direct public exports "
        "in this TypeScript module",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "explain-code"
    assert payload["handoff"]["skills"][0] == "explain-code"


def test_typescript_omnibus_routes_to_earned_skill():
    returncode, payload = _run_match(
        "find an omnibus TypeScript module with too many unrelated responsibilities",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "find-omnibus"
    assert payload["handoff"]["skills"][0] == "find-omnibus"


def test_typescript_lexical_clones_route_to_duplication():
    returncode, payload = _run_match(
        "audit TypeScript lexical clone clusters with reliable source spans "
        "and enclosing symbols",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "find-duplication"
    assert payload["handoff"]["skills"][0] == "find-duplication"


def test_go_exact_function_clones_route_to_duplication():
    returncode, payload = _run_match(
        "audit exact normalized duplicate Golang function bodies without claiming "
        "that consolidation is safe",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "go"
    assert payload["recommendation"] == "find-duplication"
    assert payload["handoff"]["skills"][0] == "find-duplication"


def test_go_package_map_routes_to_map_subsystem():
    returncode, payload = _run_match(
        "map this Golang package exported surface and first-party import edges",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "go"
    assert payload["recommendation"] == "map-subsystem"
    assert payload["handoff"]["skills"][0] == "map-subsystem"


def test_go_zero_use_review_routes_to_find_dormant():
    returncode, payload = _run_match(
        "review unexported Golang package functions with zero static uses for "
        "dormant code",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "go"
    assert payload["recommendation"] == "find-dormant"
    assert payload["handoff"]["skills"][0] == "find-dormant"


def test_typescript_function_complexity_routes_to_complexity_hotspots():
    returncode, payload = _run_match(
        "audit syntactic branch complexity in TypeScript functions and methods",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "find-complexity-hotspots"
    assert payload["handoff"]["skills"][0] == "find-complexity-hotspots"


def test_java_method_complexity_routes_to_complexity_hotspots():
    returncode, payload = _run_match(
        "audit syntactic branch complexity in Java methods and constructors",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "java"
    assert payload["recommendation"] == "find-complexity-hotspots"
    assert payload["handoff"]["skills"][0] == "find-complexity-hotspots"


def test_kotlin_host_onboarding_routes_to_adapt_project():
    returncode, payload = _run_match(
        "onboard a Kotlin/JVM repository by discovering objective stack, test, "
        "and source-root facts",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "kotlin"
    assert payload["recommendation"] == "adapt-project"
    assert payload["handoff"]["skills"][0] == "adapt-project"


def test_typescript_flat_prefix_routes_to_folder_topology():
    returncode, payload = _run_match(
        "audit a TypeScript source root for a flat prefix filename cluster "
        "among direct siblings",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "find-folder-topology-drift"
    assert payload["handoff"]["skills"][0] == "find-folder-topology-drift"


def test_typescript_host_onboarding_routes_to_adapt_project():
    returncode, payload = _run_match(
        "onboard a TypeScript repository by discovering objective stack CI "
        "test and source-root facts",
        "--top",
        "10",
    )

    assert returncode == 0
    assert payload["routing_context"]["language"] == "typescript"
    assert payload["recommendation"] == "adapt-project"
    assert payload["handoff"]["skills"][0] == "adapt-project"


def test_explicit_language_is_authoritative_and_repeatable(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "skills": [
                    {
                        "name": "ts-audit",
                        "description": "audit modules",
                        "best_for": "audit modules",
                        "not_for": "none",
                        "tier": "maintenance",
                        "job": "suspect",
                        "language": "any",
                        "framework": "any",
                        "scans": ["typescript", "javascript"],
                    },
                    {
                        "name": "django-audit",
                        "description": "audit modules",
                        "best_for": "audit modules",
                        "not_for": "none",
                        "tier": "maintenance",
                        "job": "suspect",
                        "language": "any",
                        "framework": "django",
                        "scans": ["typescript", "javascript"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    returncode, payload = _run_match(
        "audit Python modules",
        "--catalog",
        str(catalog),
        "--language",
        "ts",
        "--language",
        "javascript",
    )

    assert returncode == 0
    assert payload["recommendation"] == "ts-audit"
    assert payload["routing_context"]["languages"] == ["typescript", "javascript"]
    assert payload["routing_context"]["language_source"] == "explicit"
    assert {item["name"] for item in payload["excluded_ineligible"]} == {
        "django-audit"
    }


def test_mixed_exact_markers_do_not_guess_a_language():
    returncode, payload = _run_match(
        "compare Python app.py behavior with TypeScript app.ts behavior"
    )

    assert returncode in {0, 1}
    assert payload["routing_context"]["languages"] == []
    assert payload["routing_context"]["language_source"] is None
    assert payload["routing_context"]["task_language_markers"] == ["typescript", "python"]
    assert payload["routing_context"]["filtering_applied"] is False


@pytest.mark.parametrize("suffix", ["mjs", "cjs"])
def test_javascript_module_suffixes_are_detected(suffix):
    returncode, payload = _run_match(
        f"find complexity hotspots in src/config.{suffix}"
    )

    assert returncode in {0, 1}
    assert payload["routing_context"]["languages"] == ["javascript"]
    assert payload["routing_context"]["language_source"] == "task_marker"


# --- activation enforcement -------------------------------------------------

FRONTEND_DUP_PROMPT = (
    "find duplicated frontend cotton components and tailwind class chains across templates"
)


def _run_match_against(prompt: str, project_root: Path) -> tuple[int, dict]:
    """Run the bundled catalog against a chosen activation root."""
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json",
         "--project-root", str(project_root),
         "--top", "10"],
        cwd=REPO_ROOT, check=False, text=True, capture_output=True,
    )
    return result.returncode, json.loads(result.stdout)


def test_recommendation_prefers_on_demand_handoff_and_keeps_install_optional(tmp_path):
    returncode, payload = _run_match(
        "diagnose failing export job regression with no reproduction yet",
        "--project-root",
        str(tmp_path),
    )
    assert returncode == 0, payload
    library_root = tmp_path.parent / ".engineering-skills" / tmp_path.name

    assert "install" not in payload
    assert payload["handoff"] == {
        "mode": "on_demand_library",
        "available": False,
        "default_execution": "fresh_non_context_subagent",
        "library_root": str(library_root),
        "skills": ["diagnose"],
        "guides": [
            {
                "skill": "diagnose",
                "skill_root": str(library_root / ".claude" / "skills" / "diagnose"),
                "guide": str(library_root / ".claude" / "skills" / "diagnose" / "SKILL.md"),
                "bundled_tooling": None,
            }
        ],
        "shared_tooling": None,
        "source_inventory_tool": None,
        "common_guidance": None,
        "shared_guidance": None,
        "runtime": {
            "available": False,
            "python": str(library_root / ".venv" / "bin" / "python"),
        },
        "capabilities": {
            "available": False,
            "manifest": str(
                library_root
                / ".claude"
                / "tasks"
                / "multilanguage-skill-matrix.json"
            ),
            "skills": [],
            "reason": "manifest_missing",
        },
        "instruction": (
            "For non-trivial work, give a fresh non-context sub-agent the task, project root, "
            "task packet, selected skill roots, library runtime Python, and shared guidance/tool "
            "paths. For small work, read from the same bounded roots directly. Do not install "
            "the skills unless the user explicitly asks."
        ),
    }
    assert payload["optional_install"] == {
        "skill": "diagnose",
        "skills": ["diagnose"],
        "source": "https://github.com/KhurrumMahmood/senior-vibe-engineer",  # host-ref-allow: public distribution repository
        "skills_cli_version": "1.5.19",
        "agent": "codex",
        "available": False,
        "reason": "manifest_missing",
        "evidence": [],
    }


def _seed_manifest(root: Path, payload: dict) -> None:
    eng = root / ".engineering"
    eng.mkdir(parents=True, exist_ok=True)
    (eng / "manifest.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_skill_recommendable_when_no_manifest(tmp_path):
    # tmp_path has no .engineering/manifest.json => every skill applies, so the
    # frontend-dup prompt surfaces find-frontend-duplication as a candidate.
    _returncode, payload = _run_match_against(FRONTEND_DUP_PROMPT, tmp_path)
    names = [c["name"] for c in payload.get("candidates", [])]
    assert "find-frontend-duplication" in names
    assert payload.get("excluded_inactive") == []


def test_inactive_skill_excluded_from_recommendation(tmp_path):
    # Deactivate the would-be top scorer; it must drop out of candidates and the
    # recommendation, and surface in excluded_inactive with its recorded reason.
    _seed_manifest(tmp_path, {
        "version": 1,
        "skills": {"default": "active",
                   "inactive": {"find-frontend-duplication": "no frontend here"}},
    })
    _returncode, payload = _run_match_against(FRONTEND_DUP_PROMPT, tmp_path)
    names = [c["name"] for c in payload.get("candidates", [])]
    assert "find-frontend-duplication" not in names
    assert payload["recommendation"] != "find-frontend-duplication"
    excluded = {e["name"]: e["reason"] for e in payload.get("excluded_inactive", [])}
    assert excluded.get("find-frontend-duplication") == "no frontend here"
