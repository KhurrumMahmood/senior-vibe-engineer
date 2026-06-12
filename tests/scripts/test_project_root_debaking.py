"""Root-resolution tests for the parents[4] de-baking sweep (ADR 0024 convention).

Each skill script's kit root (`KIT_ROOT`, parents[4] of the script) anchors
sys.path imports ONLY; every target-project surface (idea ledger, glossary,
scan targets, report labels) anchors on --project-root, which defaults to the
git toplevel of the cwd. Regression coverage for the bug class where scripts
hard-anchored REPO_ROOT to the kit's own repo and read/wrote the wrong
project when invoked elsewhere. Representative scripts: track-idea (ledger
family) and find-concept-divergence + find-incomplete-sweep (scan family).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

import diff_resolution as dr

TRACK = REPO_ROOT / ".claude" / "skills" / "track-idea" / "scripts" / "track.py"
CDIV = REPO_ROOT / ".claude" / "skills" / "find-concept-divergence" / "scripts" / "scan.py"
SWEEP = REPO_ROOT / ".claude" / "skills" / "find-incomplete-sweep" / "scripts" / "scan.py"

GIT_ENV_ARGS = ["-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]


@pytest.fixture
def foreign_repo(tmp_path: Path) -> Path:
    """A throwaway git repo standing in for a target project that is NOT the kit repo."""
    repo = tmp_path / "target"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "src" / "app.py").write_text(
        "# the flattened data goes here\nx = 1\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", *GIT_ENV_ARGS, "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          cwd=cwd, capture_output=True, text=True, check=False)


# --- resolve_project_root (the shared helper default) ------------------------ #

def test_resolve_project_root_defaults_to_git_toplevel(foreign_repo, monkeypatch):
    monkeypatch.chdir(foreign_repo / "src")
    assert dr.resolve_project_root(None) == foreign_repo.resolve()


# --- track.py (ledger family): ledger anchors on the target project ---------- #

def test_track_list_from_foreign_repo_sees_empty_ledger(foreign_repo):
    """The kit repo's populated ledger must NOT leak into a foreign-repo run."""
    r = _run(TRACK, "list", cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    assert "(no ideas captured yet)" in r.stdout


def test_track_intake_writes_into_foreign_ledger_not_kit(foreign_repo):
    kit_ledger = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"
    kit_before = kit_ledger.read_bytes() if kit_ledger.exists() else b""
    r = _run(TRACK, "intake", "debake-test-idea", "--title", "T",
             "--origin", "AI-suggestion", "--subsystem-kind", "meta",
             "--summary", "S", cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    foreign_ledger = foreign_repo / ".claude" / "ideas" / "log.jsonl"
    assert foreign_ledger.is_file()
    assert "debake-test-idea" in foreign_ledger.read_text(encoding="utf-8")
    kit_after = kit_ledger.read_bytes() if kit_ledger.exists() else b""
    assert kit_after == kit_before  # no kit-repo write


def test_track_explicit_project_root_wins_over_cwd(foreign_repo):
    r = _run(TRACK, "list", "--project-root", str(foreign_repo), cwd=REPO_ROOT)
    assert r.returncode == 0, r.stderr
    assert "(no ideas captured yet)" in r.stdout


# --- find-concept-divergence scan.py (concept family) ------------------------ #

def _write_glossary(repo: Path) -> None:
    contracts = repo / ".claude" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "concepts.yaml").write_text(
        "concepts:\n"
        "  - name: flat-record\n"
        "    avoid:\n"
        "      - flattened data\n",
        encoding="utf-8",
    )


def test_cdiv_scan_anchors_targets_and_labels_on_foreign_repo(foreign_repo, tmp_path):
    _write_glossary(foreign_repo)
    out = tmp_path / "findings.jsonl"
    rep = tmp_path / "report.md"
    r = _run(CDIV, "--output", str(out), "--report", str(rep), "src", cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    findings = [json.loads(ln) for ln in out.read_text().splitlines() if ln.strip()]
    hits = [f for f in findings if f["band"] == "avoid_term_hit"]
    assert hits, "expected the foreign repo's avoid-term hit"
    assert hits[0]["file"] == "src/app.py"  # foreign-root-relative label


def test_cdiv_scan_missing_glossary_names_foreign_path(foreign_repo, tmp_path):
    r = _run(CDIV, "--output", str(tmp_path / "f.jsonl"),
             "--report", str(tmp_path / "r.md"), cwd=foreign_repo)
    assert r.returncode != 0
    assert str(foreign_repo) in (r.stdout + r.stderr)  # complains about ITS glossary
    assert str(REPO_ROOT) not in (r.stdout + r.stderr)  # not the kit's


def test_cdiv_scan_outside_target_does_not_crash(foreign_repo, tmp_path):
    """relative_to() used to raise for files outside the anchored root;
    outside files now degrade to absolute-path labels."""
    _write_glossary(foreign_repo)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "notes.md").write_text("more flattened data prose\n", encoding="utf-8")
    out = tmp_path / "findings.jsonl"
    r = _run(CDIV, "--output", str(out), "--report", str(tmp_path / "r.md"),
             str(outside), cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    findings = [json.loads(ln) for ln in out.read_text().splitlines() if ln.strip()]
    assert any(f["file"] == str(outside / "notes.md") for f in findings)


# --- find-incomplete-sweep scan.py: --paths anchor + manifest root ----------- #

def test_sweep_scan_records_foreign_root_in_manifest(foreign_repo, tmp_path):
    out = tmp_path / "scan-out"
    r = _run(SWEEP, "--paths", "src", "--no-gate", "--out", str(out), cwd=foreign_repo)
    assert r.returncode == 0, r.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert Path(manifest["project_root"]).resolve() == foreign_repo.resolve()
