from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER = REPO_ROOT / ".claude" / "skills" / "which-cleanup" / "scripts" / "route.py"


def _run_router(
    project_root: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(ROUTER),
            *args,
            "--project-root",
            str(project_root),
            "--json",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "--quiet")


def test_dart_closeout_keeps_external_library_only_companion_honest(tmp_path):
    project_root = tmp_path / "host"
    _init_repo(project_root)
    result = _run_router(
        project_root,
        "lib/invoice.dart",
        "--library-root",
        str(REPO_ROOT),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    comment = next(
        row for row in payload["recommendations"] if row["skill"] == "find-comment-drift"
    )
    assert comment["handoff"]["available"] is True
    assert comment["optional_install"]["available"] is False
    assert comment["optional_install"]["reason"] == (
        "selected_language_requires_external_library"
    )
    assert "command" not in comment["optional_install"]


@pytest.mark.parametrize(
    ("file_count", "expected_band", "expected_skills"),
    [
        (0, "trivial", []),
        (
            1,
            "trivial",
            ["find-test-obligation-drift", "find-comment-drift", "prevent-regression"],
        ),
        (
            5,
            "small",
            ["find-test-obligation-drift", "find-comment-drift", "prevent-regression"],
        ),
        (
            6,
            "medium",
            [
                "find-test-obligation-drift",
                "find-comment-drift",
                "prevent-regression",
                "find-duplication",
                "find-omnibus",
            ],
        ),
        (
            20,
            "medium",
            [
                "find-test-obligation-drift",
                "find-comment-drift",
                "prevent-regression",
                "find-duplication",
                "find-omnibus",
            ],
        ),
        (
            21,
            "large",
            [
                "find-test-obligation-drift",
                "find-comment-drift",
                "prevent-regression",
                "find-duplication",
                "find-omnibus",
                "find-incomplete-sweep",
            ],
        ),
    ],
)
def test_file_count_boundaries_preserve_bands_and_rosters(
    tmp_path, file_count, expected_band, expected_skills
):
    project_root = tmp_path / "host"
    _init_repo(project_root)
    paths = [f"src/file_{index}.py" for index in range(file_count)]

    result = _run_router(project_root, *paths)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resolved_paths"] == sorted(paths)
    assert payload["scope_band"] == expected_band
    assert [item["skill"] for item in payload["recommendations"]] == expected_skills


def test_explicit_paths_are_project_relative_and_deduplicated_after_normalization(tmp_path):
    project_root = tmp_path / "host"
    project_root.mkdir()
    canonical = project_root / "src" / "deleted.py"

    result = _run_router(
        project_root,
        "src/deleted.py",
        "./src/../src/deleted.py",
        str(canonical),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resolved_paths"] == ["src/deleted.py"]
    assert payload["scope_band"] == "trivial"


@pytest.mark.parametrize("requested", ["", "   "])
def test_empty_explicit_paths_are_rejected(tmp_path, requested):
    project_root = tmp_path / "host"
    project_root.mkdir()

    result = _run_router(project_root, requested)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["resolution"]["target"] == "explicit paths"
    assert payload["resolution"]["code"] == "empty_explicit_path"


@pytest.mark.parametrize("path", ["../outside.py", "ABSOLUTE"])
def test_explicit_paths_outside_project_root_are_rejected(tmp_path, path):
    project_root = tmp_path / "host"
    project_root.mkdir()
    requested = str(tmp_path / "outside.py") if path == "ABSOLUTE" else path

    result = _run_router(project_root, requested)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "resolution_failed"
    assert payload["resolution"]["status"] == "failed"
    assert payload["resolution"]["target"] == "explicit paths"
    assert payload["resolution"]["code"] == "path_outside_project"


@pytest.mark.parametrize(
    ("scope_args", "target"),
    [
        (("--changed-from", "missing-ref"), "changes from missing-ref"),
        (("--commit", "missing-ref"), "commit missing-ref"),
        (("--range", "missing-ref..other-missing-ref"), "range missing-ref..other-missing-ref"),
    ],
)
def test_unresolvable_git_scopes_are_structured_failures(tmp_path, scope_args, target):
    project_root = tmp_path / "host"
    _init_repo(project_root)

    result = _run_router(project_root, *scope_args)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "resolution_failed",
        "resolution": {
            "status": "failed",
            "target": target,
            "code": "git_scope_unresolvable",
            "detail": f"Git could not resolve {target}.",
        },
    }


@pytest.mark.parametrize(
    ("scope_flag", "target"),
    [
        ("--changed-from", "changes from <empty>"),
        ("--commit", "commit <empty>"),
        ("--range", "range <empty>"),
    ],
)
def test_empty_git_scopes_do_not_fall_back_to_the_working_tree(
    tmp_path, scope_flag, target
):
    project_root = tmp_path / "host"
    _init_repo(project_root)
    (project_root / "unrelated.py").write_text("dirty\n", encoding="utf-8")

    result = _run_router(project_root, scope_flag, "")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["resolution"]["target"] == target
    assert payload["resolution"]["code"] == "empty_git_scope"


def test_non_git_working_tree_scope_is_a_structured_failure(tmp_path):
    project_root = tmp_path / "host"
    project_root.mkdir()

    result = _run_router(project_root)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "resolution_failed"
    assert payload["resolution"]["target"] == "working tree"
    assert payload["resolution"]["code"] == "not_git_repository"


def test_git_unavailable_is_a_structured_failure(tmp_path):
    project_root = tmp_path / "host"
    project_root.mkdir()
    env = os.environ.copy()
    env["PATH"] = ""

    result = _run_router(project_root, env=env)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "resolution_failed"
    assert payload["resolution"]["target"] == "working tree"
    assert payload["resolution"]["code"] == "git_unavailable"


def test_root_commit_scope_includes_files_added_by_initial_commit(tmp_path):
    project_root = tmp_path / "host"
    _init_repo(project_root)
    (project_root / "src").mkdir()
    (project_root / "README.md").write_text("root\n", encoding="utf-8")
    (project_root / "src" / "app.py").write_text("pass\n", encoding="utf-8")
    _git(project_root, "add", "README.md", "src/app.py")
    _git(
        project_root,
        "-c",
        "user.name=Router Test",
        "-c",
        "user.email=router@example.com",
        "commit",
        "--quiet",
        "-m",
        "initial",
    )
    root_commit = _git(project_root, "rev-parse", "HEAD")

    result = _run_router(project_root, "--commit", root_commit)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resolved_paths"] == ["README.md", "src/app.py"]
    assert payload["scope_band"] == "small"


def test_local_library_guide_is_returned_in_handoff(tmp_path):
    project_root = tmp_path / "host"
    project_root.mkdir()
    library_root = tmp_path / "library"
    guide = (
        library_root
        / ".claude"
        / "skills"
        / "find-test-obligation-drift"
        / "SKILL.md"
    )
    guide.parent.mkdir(parents=True)
    guide.write_text("---\nname: find-test-obligation-drift\n---\n", encoding="utf-8")

    result = _run_router(
        project_root,
        "src/app.py",
        "--library-root",
        str(library_root),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    handoff = payload["recommendations"][0]["handoff"]
    assert handoff["available"] is True
    assert handoff["guides"][0]["guide"] == str(guide)
    assert handoff["default_execution"] == "fresh_non_context_subagent"
