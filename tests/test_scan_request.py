"""Behavioral tests for the shared scan-request and Git hunk resolver."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".claude" / "skills" / "_common" / "scan_request.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_request", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    _git(repo, "config", "user.name", "Scope Fixture")
    _git(repo, "config", "user.email", "scope@example.invalid")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _change(request, path: str):
    return next(item for item in request.changes if item.path == path)


def test_explicit_paths_work_without_git_and_reject_boundary_escape(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "plain"
    _write(host / "src" / "a.py", "value = 1\n")

    request = scan_request.build_scan_request(
        host,
        requested_mode="paths",
        selector_kind="paths",
        explicit_paths=["src/a.py"],
    )

    assert request.resolved_paths == ("src/a.py",)
    assert request.content_basis == "working-tree"
    assert request.line_filter_safe is None
    assert _change(request, "src/a.py").line_ranges == ()
    assert json.loads(request.to_json())["selector"] == {
        "kind": "paths",
        "paths": ["src/a.py"],
    }

    with pytest.raises(scan_request.ScanRequestError) as exc:
        scan_request.build_scan_request(
            host,
            requested_mode="paths",
            selector_kind="paths",
            explicit_paths=["../outside.py"],
        )
    assert exc.value.code == "path_outside_project"


def test_working_tree_resolves_multiple_hunks_and_untracked_files(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "src" / "app.py", "\n".join(f"line {i}" for i in range(1, 11)) + "\n")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")

    lines = (host / "src" / "app.py").read_text(encoding="utf-8").splitlines()
    lines[1] = "changed 2"
    lines[7] = "changed 8"
    _write(host / "src" / "app.py", "\n".join(lines) + "\n")
    _write(host / "src" / "new file.py", "first\nsecond\n")

    request = scan_request.build_scan_request(
        host, requested_mode="diff-lines", selector_kind="working-tree"
    )

    assert request.content_basis == "working-tree"
    assert request.line_filter_safe is True
    assert request.resolved_paths == ("src/app.py", "src/new file.py")
    assert [(item.start, item.end) for item in _change(request, "src/app.py").line_ranges] == [
        (2, 2),
        (8, 8),
    ]
    untracked = _change(request, "src/new file.py")
    assert untracked.change_type == "untracked"
    assert [(item.start, item.end) for item in untracked.line_ranges] == [(1, 2)]


def test_resolved_request_is_eager_and_serializes_without_more_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "app.py", "before\n")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    _write(host / "app.py", "after\n")

    request = scan_request.build_scan_request(
        host, requested_mode="diff-lines", selector_kind="working-tree"
    )

    def unexpected_git(*_args, **_kwargs):
        raise AssertionError("resolved request performed a lazy Git query")

    monkeypatch.setattr(scan_request.subprocess, "run", unexpected_git)
    assert request.resolved_paths == ("app.py",)
    assert json.loads(request.to_json())["resolved_paths"] == ["app.py"]


def test_working_tree_without_head_treats_current_files_as_added(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "staged.py", "one\ntwo\n")
    _git(host, "add", "staged.py")
    _write(host / "untracked.py", "only\n")

    request = scan_request.build_scan_request(
        host, requested_mode="diff-lines", selector_kind="working-tree"
    )

    assert request.line_filter_safe is True
    assert request.resolved_paths == ("staged.py", "untracked.py")
    assert [(item.start, item.end) for item in _change(request, "staged.py").line_ranges] == [
        (1, 2)
    ]
    assert [(item.start, item.end) for item in _change(request, "untracked.py").line_ranges] == [
        (1, 1)
    ]


def test_staged_request_marks_line_filter_unsafe_when_worktree_drifted(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "app.py", "one\ntwo\nthree\n")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    _write(host / "app.py", "one\nstaged two\nthree\n")
    _git(host, "add", "app.py")
    _write(host / "app.py", "unstaged prefix\none\nstaged two\nthree\n")

    request = scan_request.build_scan_request(
        host, requested_mode="diff-lines", selector_kind="staged"
    )

    assert request.content_basis == "index"
    assert request.line_filter_safe is False
    assert [(item.start, item.end) for item in _change(request, "app.py").line_ranges] == [
        (2, 2)
    ]
    assert any(warning["code"] == "content_basis_mismatch" for warning in request.warnings)


def test_root_commit_ranges_are_safe_only_while_worktree_matches(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "root.py", "one\ntwo\n")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "root", "--quiet")
    root_sha = _git(host, "rev-parse", "HEAD")

    request = scan_request.build_scan_request(
        host,
        requested_mode="diff-lines",
        selector_kind="commit",
        selector_value=root_sha,
    )
    assert request.content_basis == root_sha
    assert request.line_filter_safe is True
    assert [(item.start, item.end) for item in _change(request, "root.py").line_ranges] == [
        (1, 2)
    ]

    _write(host / "root.py", "prefix\none\ntwo\n")
    drifted = scan_request.build_scan_request(
        host,
        requested_mode="diff-lines",
        selector_kind="commit",
        selector_value=root_sha,
    )
    assert drifted.line_filter_safe is False


def test_changed_from_uses_current_content_and_project_has_no_fake_ranges(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "app.py", "one\ntwo\n")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    base = _git(host, "rev-parse", "HEAD")
    _write(host / "app.py", "one\nchanged\n")

    changed = scan_request.build_scan_request(
        host,
        requested_mode="diff-lines",
        selector_kind="changed-from",
        selector_value=base,
    )
    assert changed.content_basis == "working-tree"
    assert changed.line_filter_safe is True
    assert [(item.start, item.end) for item in _change(changed, "app.py").line_ranges] == [
        (2, 2)
    ]

    project = scan_request.build_scan_request(
        host, requested_mode="project", selector_kind="project"
    )
    assert project.resolved_paths == ()
    assert project.changes == ()
    assert project.line_filter_safe is None


def test_range_preserves_rename_deletion_binary_and_space_paths(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)
    _write(host / "old name.py", "value = 1\n")
    _write(host / "delete.py", "gone = True\n")
    (host / "blob.bin").write_bytes(b"before\x00bytes")
    _git(host, "add", ".")
    _git(host, "commit", "-m", "base", "--quiet")
    before = _git(host, "rev-parse", "HEAD")

    _git(host, "mv", "old name.py", "new name.py")
    (host / "delete.py").unlink()
    (host / "blob.bin").write_bytes(b"after\x00bytes")
    _git(host, "add", "-A")
    _git(host, "commit", "-m", "shape", "--quiet")
    after = _git(host, "rev-parse", "HEAD")

    request = scan_request.build_scan_request(
        host,
        requested_mode="diff-lines",
        selector_kind="range",
        selector_value=f"{before}..{after}",
    )

    renamed = _change(request, "new name.py")
    assert renamed.change_type == "renamed"
    assert renamed.old_path == "old name.py"
    assert renamed.current_exists is True
    deleted = _change(request, "delete.py")
    assert deleted.change_type == "deleted"
    assert deleted.current_exists is False
    assert deleted.line_ranges == ()
    binary = _change(request, "blob.bin")
    assert binary.binary is True
    assert binary.line_ranges == ()
    assert request.line_filter_safe is True


def test_invalid_ref_is_a_structured_failure(tmp_path: Path) -> None:
    scan_request = _load_module()
    host = tmp_path / "repo"
    _init_repo(host)

    with pytest.raises(scan_request.ScanRequestError) as exc:
        scan_request.build_scan_request(
            host,
            requested_mode="changed-files",
            selector_kind="changed-from",
            selector_value="missing-ref",
        )

    assert exc.value.code == "git_scope_unresolvable"


def test_patch_facts_refuse_misaligned_change_sets() -> None:
    scan_request = _load_module()
    changes = [
        {
            "path": "one.py",
            "old_path": None,
            "change_type": "modified",
            "binary": False,
            "line_ranges": [],
        },
        {
            "path": "two.py",
            "old_path": None,
            "change_type": "modified",
            "binary": False,
            "line_ranges": [],
        },
    ]

    with pytest.raises(scan_request.ScanRequestError) as exc:
        scan_request._apply_patch_facts(  # noqa: SLF001 - contract-level parser test
            b"diff --git a/one.py b/one.py\n@@ -1 +1 @@\n-old\n+new\n",
            changes,
        )

    assert exc.value.code == "git_output_invalid"
