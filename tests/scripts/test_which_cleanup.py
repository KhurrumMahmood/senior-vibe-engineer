"""Tests for the /which-cleanup engine.

Pure logic (classify / select / closeout) is imported directly; the run.py and
coverage.py CLIs are exercised via subprocess (the latter also dodges the stdlib
`coverage` name collision). Asserts the advisory invariant: a run writes only
where told, never into the repo working tree."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WC_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "which-cleanup" / "scripts"
for _p in (
    WC_SCRIPTS,
    REPO_ROOT / ".claude" / "skills" / "_common",
    REPO_ROOT / "scripts",
    REPO_ROOT / "scripts" / "_lib",
):
    sys.path.insert(0, str(_p))

import importlib.util

import classify
import closeout as closeout_mod
import select_scanners

RUN = WC_SCRIPTS / "run.py"
COVERAGE = WC_SCRIPTS / "coverage.py"


def _load_module(name: str, path: Path):
    """Load a module under a unique name (dodges the stdlib `coverage` collision)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wc_coverage = _load_module("wc_coverage", COVERAGE)


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _changed_project(tmp_path: Path, *, file_count: int) -> Path:
    """Create a deterministic Git diff instead of depending on this repo's HEAD."""
    project = tmp_path / "project"
    project.mkdir()
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "which-cleanup@example.invalid"],
        ["git", "config", "user.name", "Which Cleanup Test"],
    ):
        subprocess.run(command, cwd=project, check=True)
    for index in range(file_count):
        (project / f"module_{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=project, check=True)
    for index in range(file_count):
        (project / f"module_{index}.py").write_text("VALUE = 2\n", encoding="utf-8")
    return project


# --- classify (OR-logic across axes) --------------------------------------- #


@pytest.mark.parametrize(
    "files,subs,loc,expected",
    [
        (1, 1, 10, "trivial"),
        (3, 1, 50, "small"),
        (8, 1, 100, "medium"),
        (25, 1, 100, "large"),  # file axis
        (2, 3, 20, "large"),  # subsystem axis dominates despite tiny file/loc
        (2, 1, 1600, "large"),  # diff-loc axis dominates
        (2, 1, None, "small"),  # loc axis drops out when no ref
    ],
)
def test_classify_bands(files, subs, loc, expected):
    assert classify.classify(classify.ScopeInputs(files, subs, loc)) == expected


# --- select (registry adjacency + job-frontmatter tiering) ----------------- #


def test_select_buckets_by_job():
    report = {
        "subsystems": [
            {
                "name": "field_extraction",
                "related_skills": ["map-product-workflow"],
                "adjacency": ["stringly-status", "query-mutation"],
            },
        ],
        "unmatched": [],
    }
    roster = select_scanners.select(report, band="small")
    post = {i["skill"] for i in roster["buckets"]["post_sweep"]}
    pre = {i["skill"] for i in roster["buckets"]["pre_baseline"]}
    guard = {i["skill"] for i in roster["buckets"]["guard_tail"]}
    assert "find-implicit-state" in post  # stringly-status adjacency -> SUSPECT
    assert "find-query-mutation" in post  # query-mutation adjacency -> SUSPECT
    assert "map-product-workflow" in pre  # job: map -> pre_baseline
    assert "prevent-regression" in guard  # universal floor guard -> guard_tail
    assert "find-test-obligation-drift" in post  # universal floor suspect


def test_select_large_adds_rename_floor():
    report = {
        "subsystems": [{"name": "tooling", "related_skills": [], "adjacency": []}],
        "unmatched": [],
    }
    roster = select_scanners.select(report, band="large", has_doc_change=True)
    post = {i["skill"] for i in roster["buckets"]["post_sweep"]}
    assert "find-concept-divergence" in post  # large-shape rename floor (present in ES2)
    # find-doc-link-rot is not in this repo's skill set, so the doc-shape floor is empty here.


def test_closeout_build_shape():
    report = {
        "subsystems": [
            {"name": "field_extraction", "related_skills": [], "adjacency": ["stringly-status"]}
        ],
        "unmatched": ["x/y.py"],
    }
    roster = select_scanners.select(report, band="small")
    c = closeout_mod.build(
        target="t",
        scope_band="small",
        axis_breakdown={"files": "small", "subsystems": "trivial", "diff_loc": "small"},
        resolved_paths=["app/services/extraction/field_chat.py"],
        report=report,
        roster=roster,
        max_scouts=5,
    )
    assert set(c["checklist"]) == {"pre_baseline", "post_sweep", "guard_tail"}
    assert c["unmatched"] == ["x/y.py"]
    # post-sweep find-* command is scoped to the changed file
    impl = next(i for i in c["checklist"]["post_sweep"] if i["skill"] == "find-implicit-state")
    assert "field_chat.py" in impl["command"]


# --- run.py integration ---------------------------------------------------- #


def test_run_changed_from_head(tmp_path):
    project = _changed_project(tmp_path, file_count=3)
    r = _run(
        RUN,
        "--project-root",
        str(project),
        "--changed-from",
        "HEAD",
        "--json",
        "--skip-effectiveness-log",
        "--now",
        "testrun",
        "--reports-dir",
        str(tmp_path / "reports"),
        "--specs-dir",
        str(tmp_path / "specs"),
    )
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert c["scope_band"] == "small"
    assert set(c["checklist"]) == {"pre_baseline", "post_sweep", "guard_tail"}
    # Advisory invariant: it wrote only where told (under tmp), not into the repo.
    assert str(tmp_path) in c["report_dir"] or c["report_dir"].startswith(str(tmp_path))


def test_run_area_without_registry_exits_2(tmp_path):
    # ES2 ships no .claude/subsystems.yaml, so --area has nothing to resolve against.
    r = _run(RUN, "--area", "anything", "--reports-dir", str(tmp_path))
    assert r.returncode == 2
    assert "unknown subsystem/area" in r.stderr


def test_run_unknown_area_exits_2(tmp_path):
    r = _run(RUN, "--area", "does-not-exist", "--reports-dir", str(tmp_path))
    assert r.returncode == 2
    assert "unknown subsystem/area" in r.stderr


# --- coverage.py integration ----------------------------------------------- #


def test_coverage_check_passes():
    r = _run(COVERAGE, "check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_coverage_audit_structure_and_unmappable():
    r = _run(COVERAGE, "audit", "--last", "30", "--json")
    assert r.returncode == 0, r.stderr
    a = json.loads(r.stdout)
    for key in (
        "gaps",
        "guard_gaps",
        "unmappable_targets",
        "subsystems_touched",
        "implied_skill_count",
    ):
        assert key in a
    assert isinstance(a["unmappable_targets"], list)  # surfaced, never dropped
    assert isinstance(a["gaps"], list)


def test_join_subsystem_trailing_slash_retry():
    """A bare directory target still matches a registry dir-prefix (synthetic registry)."""
    reg = {"si": {"paths": ["app/services/site_intelligence/"]}}
    # bare dir (no trailing slash) -> matched via the trailing-slash retry
    assert wc_coverage._join_subsystem("app/services/site_intelligence", reg) == "si"
    # a file target (has extension) matches the prefix directly
    assert wc_coverage._join_subsystem("app/services/site_intelligence/x.py", reg) == "si"
    # unmatched stays None
    assert wc_coverage._join_subsystem("other/path", reg) is None


def test_emit_plan_gates_spec_stub(tmp_path):
    """Review fix: the large-band spec stub is written only with --emit-plan."""
    project = _changed_project(tmp_path, file_count=25)
    common = [
        "--project-root",
        str(project),
        "--changed-from",
        "HEAD",
        "--json",
        "--skip-effectiveness-log",
        "--now",
        "ep",
    ]
    r1 = _run(
        RUN, *common, "--reports-dir", str(tmp_path / "r1"), "--specs-dir", str(tmp_path / "s1")
    )
    c1 = json.loads(r1.stdout)
    assert c1["scope_band"] == "large"
    assert "spec_stub" not in c1
    assert not list((tmp_path / "s1").glob("*.md")) if (tmp_path / "s1").exists() else True
    r2 = _run(
        RUN,
        *common,
        "--emit-plan",
        "--reports-dir",
        str(tmp_path / "r2"),
        "--specs-dir",
        str(tmp_path / "s2"),
    )
    c2 = json.loads(r2.stdout)
    assert "spec_stub" in c2
    assert list((tmp_path / "s2").glob("*.md"))
