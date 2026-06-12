"""Root-resolution tests for /which-cleanup (de-baking convention, ADR 0024).

The kit root (`KIT_ROOT`, parents[4] of run.py) anchors sys.path imports ONLY;
every target-project operation (registry, reports, specs, git scope) anchors on
--project-root, which defaults to the git toplevel of the cwd. Regression
coverage for the bug where run.py/coverage.py hard-anchored REPO_ROOT to the
kit's own repo and resolved the wrong project when invoked elsewhere.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WC_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "which-cleanup" / "scripts"
COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
for _p in (str(COMMON),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import diff_resolution as dr

RUN = WC_SCRIPTS / "run.py"
COVERAGE = WC_SCRIPTS / "coverage.py"

GIT_ENV_ARGS = ["-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]


@pytest.fixture
def foreign_repo(tmp_path: Path) -> Path:
    """A throwaway git repo standing in for a target project that is NOT the kit repo."""
    repo = tmp_path / "target"
    (repo / "sub").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "sub" / "helper.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", *GIT_ENV_ARGS, "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          cwd=cwd, capture_output=True, text=True, check=False)


# --- resolve_project_root (the shared helper) ------------------------------- #

def test_resolve_project_root_explicit_wins(foreign_repo, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    assert dr.resolve_project_root(foreign_repo) == foreign_repo.resolve()


def test_resolve_project_root_defaults_to_git_toplevel_from_subdir(foreign_repo, monkeypatch):
    monkeypatch.chdir(foreign_repo / "sub")
    assert dr.resolve_project_root(None) == foreign_repo.resolve()


def test_resolve_project_root_falls_back_to_cwd_outside_git(tmp_path, monkeypatch):
    bare = tmp_path / "no-git"
    bare.mkdir()
    monkeypatch.chdir(bare)
    assert dr.resolve_project_root(None) == bare.resolve()


# --- run.py: kit imports + target anchoring with project_root != kit root --- #

def test_run_from_foreign_repo_anchors_there(foreign_repo):
    """Invoked with cwd in a foreign repo: kit imports still work (no shim), and
    the scope, report paths, and missing-registry degradation all resolve there."""
    r = _run(RUN, "--commit", "HEAD", "--json", "--skip-effectiveness-log",
             "--now", "t1", cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert sorted(c["resolved_paths"]) == ["app.py", "sub/helper.py"]  # foreign git history
    assert c["subsystems"] == []  # no .claude/subsystems.yaml -> graceful universal floor
    assert (foreign_repo / "reports" / "which-cleanup" / "scan-t1" / "closeout.json").is_file()
    assert not (REPO_ROOT / "reports" / "which-cleanup" / "scan-t1").exists()  # no kit-repo leak


def test_run_default_root_resolves_toplevel_from_subdir(foreign_repo):
    r = _run(RUN, "--commit", "HEAD", "--json", "--skip-effectiveness-log",
             "--now", "t2", cwd=foreign_repo / "sub")
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert "app.py" in c["resolved_paths"]
    assert (foreign_repo / "reports" / "which-cleanup" / "scan-t2" / "closeout.json").is_file()


def test_run_explicit_project_root_wins_over_cwd(foreign_repo):
    r = _run(RUN, "--project-root", str(foreign_repo), "--commit", "HEAD", "--json",
             "--skip-effectiveness-log", "--now", "t3", cwd=REPO_ROOT)
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert "app.py" in c["resolved_paths"]
    assert (foreign_repo / "reports" / "which-cleanup" / "scan-t3" / "closeout.json").is_file()
    assert not (REPO_ROOT / "reports" / "which-cleanup" / "scan-t3").exists()


# --- coverage.py: same anchoring contract ----------------------------------- #

def test_coverage_audit_from_foreign_repo(foreign_repo):
    r = _run(COVERAGE, "audit", "--last", "5", "--json", cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    a = json.loads(r.stdout)
    assert a["subsystems_touched"] == []  # foreign history, no registry -> graceful
    assert isinstance(a["gaps"], list)


def test_coverage_check_uses_kit_skill_catalogue_from_foreign_repo(foreign_repo):
    """check() must keep resolving recommendable skills against the KIT's
    .claude/skills/ even when run from a repo that ships none."""
    r = _run(COVERAGE, "check", cwd=foreign_repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout
