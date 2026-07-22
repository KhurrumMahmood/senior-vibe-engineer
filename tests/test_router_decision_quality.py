from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "tests" / "fixtures" / "router-decision-quality" / "cases.json"
SHAPE = REPO_ROOT / ".claude" / "skills" / "which-shape" / "scripts" / "route.py"
SKILL = REPO_ROOT / ".claude" / "skills" / "which-skill" / "scripts" / "match.py"
CLEANUP = REPO_ROOT / ".claude" / "skills" / "which-cleanup" / "scripts" / "route.py"


def _corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _run(script: Path, *args: str, cwd: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), *args, "--json"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


@pytest.mark.parametrize("case", _corpus()["which_shape"], ids=lambda case: case["id"])
def test_which_shape_decision_corpus(case, tmp_path):
    code, payload = _run(
        SHAPE,
        case["prompt"],
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--skip-log",
        cwd=REPO_ROOT,
    )

    assert code == 0
    recommendation = payload["recommendation"]
    if "expected" in case:
        assert recommendation["shape"] in case["expected"]
    if "expected_confidence" in case:
        assert recommendation["confidence"] == case["expected_confidence"]
    if case["handoff"] == "none":
        assert "handoff" not in payload
    elif case["handoff"] == "available":
        assert payload["handoff"]["available"] is True
        assert payload["handoff"]["mode"] == "on_demand_library"
    else:
        assert payload["handoff"]["available"] is False
        assert payload["handoff"]["reason"] == "selected_skill_stack_bound_for_language"


@pytest.mark.parametrize("case", _corpus()["which_skill"], ids=lambda case: case["id"])
def test_which_skill_decision_corpus(case, tmp_path):
    code, payload = _run(
        SKILL,
        case["prompt"],
        "--project-root", str(tmp_path),
        "--library-root", str(REPO_ROOT),
        "--top", "10",
        cwd=REPO_ROOT,
    )

    expected_exits = case["exit"] if isinstance(case["exit"], list) else [case["exit"]]
    assert code in expected_exits
    assert payload["recommendation"] in case["expected"]
    if payload["recommendation"] in {"proceed_directly", "unsupported"}:
        assert "handoff" not in payload
    else:
        assert payload["handoff"]["available"] is True
        assert payload["handoff"]["mode"] == "on_demand_library"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.mark.parametrize("case", _corpus()["which_cleanup"], ids=lambda case: case["id"])
def test_which_cleanup_decision_corpus(case, tmp_path):
    project = tmp_path / "host"
    project.mkdir()
    _git(project, "init", "--quiet")
    if case.get("scope") == "known_git_range":
        (project / "base.txt").write_text("base\n", encoding="utf-8")
        _git(project, "add", "base.txt")
        _git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "base")
        (project / "one.py").write_text("one\n", encoding="utf-8")
        (project / "two.py").write_text("two\n", encoding="utf-8")
        _git(project, "add", "one.py", "two.py")
        _git(project, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "two files")
        args = ["--range", "HEAD~1..HEAD"]
    elif "paths" in case:
        args = list(case["paths"])
    else:
        args = [f"src/file_{index}.py" for index in range(case["count"])]

    code, payload = _run(
        CLEANUP,
        *args,
        "--project-root", str(project),
        "--library-root", str(REPO_ROOT),
        cwd=project,
    )

    assert code == 0
    expected_count = case.get("resolved_count", case.get("count"))
    assert len(payload["resolved_paths"]) == expected_count
    assert payload["scope_band"] == case["band"]
    assert len(payload["recommendations"]) == case["recommendation_count"]
