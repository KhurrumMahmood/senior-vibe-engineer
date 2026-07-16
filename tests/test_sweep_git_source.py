from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from sweep.git_source import capture_git_source


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    ).stdout


def _repository(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@example.test")
    _git(root, "config", "user.name", "Fixture")
    tracked = root / "src" / "sample.py"
    tracked.parent.mkdir()
    tracked.write_text("before\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    revision = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    return root, tracked, revision


def test_capture_git_source_binds_clean_head_and_exact_tracked_diff(
    tmp_path: Path,
) -> None:
    root, tracked, revision = _repository(tmp_path)

    assert capture_git_source(root) == {
        "revision": revision,
        "dirty": False,
        "dirty_state_hash": EMPTY_SHA256,
    }

    tracked.write_text("after\n", encoding="utf-8")
    diff = _git(root, "diff", "--binary", "HEAD", "--")
    assert capture_git_source(root) == {
        "revision": revision,
        "dirty": True,
        "dirty_state_hash": hashlib.sha256(diff).hexdigest(),
    }

    _git(root, "add", "src/sample.py")
    staged_diff = _git(root, "diff", "--binary", "HEAD", "--")
    assert capture_git_source(root)["dirty_state_hash"] == hashlib.sha256(
        staged_diff
    ).hexdigest()


def test_capture_git_source_binds_untracked_paths_and_raw_bytes(tmp_path: Path) -> None:
    root, _tracked, _revision = _repository(tmp_path)
    untracked = root / "src" / "new.py"
    untracked.write_bytes(b"first\x00payload")

    first = capture_git_source(root)
    assert first["dirty"] is True
    assert first["dirty_state_hash"] != EMPTY_SHA256

    untracked.write_bytes(b"second\x00payload")
    second = capture_git_source(root)
    assert second["dirty_state_hash"] != first["dirty_state_hash"]

    renamed = root / "src" / "renamed.py"
    untracked.rename(renamed)
    third = capture_git_source(root)
    assert third["dirty_state_hash"] != second["dirty_state_hash"]


def test_capture_git_source_supports_a_nested_scan_root(tmp_path: Path) -> None:
    root, tracked, revision = _repository(tmp_path)
    tracked.write_text("nested change\n", encoding="utf-8")
    nested = root / "src"
    diff = _git(nested, "diff", "--binary", "HEAD", "--")

    assert capture_git_source(nested) == {
        "revision": revision,
        "dirty": True,
        "dirty_state_hash": hashlib.sha256(diff).hexdigest(),
    }


def test_capture_git_source_rejects_a_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot inspect Git source"):
        capture_git_source(tmp_path)
