from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
    assert omnibus["language"] == "python"
    assert omnibus["framework"] == "any"
    assert omnibus["scans"] == ["python"]


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
    assert payload["install"]["skill"] == "find-implicit-state"


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
    assert payload["install"]["skill"] == "explain-code"


def test_unearned_omnibus_typescript_claim_returns_unsupported():
    returncode, payload = _run_match(
        "find an omnibus TypeScript module with too many unrelated responsibilities",
        "--top",
        "10",
    )

    assert returncode == 1
    assert payload["recommendation"] == "unsupported"
    excluded = {item["name"]: item["reason"] for item in payload["excluded_unsupported"]}
    assert excluded["find-omnibus"] == "declares language=python"


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
    assert {item["name"] for item in payload["excluded_unsupported"]} == {"django-audit"}


def test_mixed_exact_markers_do_not_guess_a_language():
    returncode, payload = _run_match(
        "compare Python app.py behavior with TypeScript app.ts behavior"
    )

    assert returncode in {0, 1}
    assert payload["routing_context"]["languages"] == []
    assert payload["routing_context"]["language_source"] is None
    assert payload["routing_context"]["task_language_markers"] == ["typescript", "python"]
    assert payload["routing_context"]["filtering_applied"] is False


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


def test_recommendation_includes_pinned_selected_skill_install():
    payload = _match("diagnose failing export job regression with no reproduction yet")

    assert payload["install"] == {
        "skill": "diagnose",
        "source": "https://github.com/KhurrumMahmood/senior-vibe-engineer",  # host-ref-allow: public distribution repository
        "skills_cli_version": "1.5.19",
        "agent": "codex",
        "command": (
            "DO_NOT_TRACK=1 npx --yes skills@1.5.19 add "
            "https://github.com/KhurrumMahmood/senior-vibe-engineer "  # host-ref-allow: public distribution repository
            "--skill diagnose --agent codex --copy -y"
        ),
        "locations": {
            "definition": (
                "https://github.com/KhurrumMahmood/senior-vibe-engineer::.claude/skills/diagnose/SKILL.md"  # host-ref-allow: public distribution repository
            ),
            "bundled_tooling": (
                "https://github.com/KhurrumMahmood/senior-vibe-engineer::.claude/skills/diagnose/scripts/"  # host-ref-allow: public distribution repository
            ),
            "shared_tooling": (
                "https://github.com/KhurrumMahmood/senior-vibe-engineer::scripts/"  # host-ref-allow: public distribution repository
            ),
        },
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
