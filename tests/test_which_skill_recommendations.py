from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATCHER = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"


def _run_match(prompt: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json"],
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


# --- activation enforcement -------------------------------------------------

SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
FRONTEND_DUP_PROMPT = (
    "find duplicated frontend cotton components and tailwind class chains across templates"
)


def _run_match_against(prompt: str, project_root: Path) -> tuple[int, dict]:
    """Run the matcher against the real skills dir but a chosen activation root."""
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json",
         "--skills-dir", str(SKILLS_DIR),
         "--project-root", str(project_root),
         "--top", "10"],
        cwd=REPO_ROOT, check=False, text=True, capture_output=True,
    )
    return result.returncode, json.loads(result.stdout)


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
