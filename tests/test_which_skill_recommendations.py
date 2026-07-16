from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from _lib.host_profile import profile_host

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


def _seed_typescript_profile(root: Path) -> None:
    root.joinpath("package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "19.0.0"},
                "devDependencies": {"typescript": "5.9.3"},
            }
        ),
        encoding="utf-8",
    )
    root.joinpath("tsconfig.json").write_text("{}\n", encoding="utf-8")
    source = root / "src"
    source.mkdir()
    source.joinpath("App.tsx").write_text("export const App = () => <main />;\n", encoding="utf-8")
    profile_path = root / ".engineering" / "project" / "host-profile.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(json.dumps(profile_host(root)), encoding="utf-8")


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


def test_typescript_profile_never_recommends_django_bound_skill(tmp_path):
    _seed_typescript_profile(tmp_path)

    _returncode, payload = _run_match_against(FRONTEND_DUP_PROMPT, tmp_path)

    assert payload["recommendation"] != "find-frontend-duplication"
    assert all(candidate["framework"] != "django" for candidate in payload["candidates"])
    excluded = {
        item["name"]: item for item in payload["excluded_inactive"]
    }
    assert "find-frontend-duplication" in excluded
    assert excluded["find-frontend-duplication"]["activation"]["active"] is False
    assert any(
        "no profile root matches" in reason
        for reason in excluded["find-frontend-duplication"]["reasons"]
    )


def test_matcher_enforces_required_capability_layer_and_binding(tmp_path):
    _seed_typescript_profile(tmp_path)
    skills = tmp_path / "skills"
    for name, capabilities in (
        ("find-symbols", ["analysis.symbols"]),
        ("find-calls", ["analysis.calls"]),
    ):
        skill_dir = skills / name
        skill_dir.mkdir(parents=True)
        metadata = {
            "name": name,
            "description": "Find symbols in TypeScript source.",
            "tier": "maintenance",
            "job": "suspect",
            "best_for": "find symbols",
            "not_for": "",
            "language": "typescript",
            "framework": "react",
            "layer": "framework",
            "binding": "react",
            "bindings": [],
            "capabilities": capabilities,
        }
        skill_dir.joinpath("SKILL.md").write_text(
            f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\n# /{name}\n",
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            sys.executable,
            str(MATCHER),
            "find symbols",
            "--json",
            "--skills-dir",
            str(skills),
            "--project-root",
            str(tmp_path),
            "--require-capability",
            "analysis.symbols",
            "--require-layer",
            "framework",
            "--require-binding",
            "react",
            "--threshold",
            "0",
            "--top",
            "10",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["recommendation"] == "find-symbols"
    assert payload["candidates"][0]["activation"]["active"] is True
    rejected = {item["name"]: item for item in payload["excluded_inactive"]}
    assert "find-calls" in rejected
    assert any("required capabilities" in reason for reason in rejected["find-calls"]["reasons"])
