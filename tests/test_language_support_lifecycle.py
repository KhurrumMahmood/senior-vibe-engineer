"""Narrow lifecycle mechanics shared by language-support consumers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts._lib.language_support.lifecycle import (
    LifecycleError,
    TerminalOutcome,
    clear_artifacts,
    source_manifest,
    write_json_atomic,
    write_text_atomic,
)


def test_terminal_outcome_vocabulary_is_small_and_explicit() -> None:
    assert {outcome.value for outcome in TerminalOutcome} == {
        "complete",
        "partial",
        "unsupported",
        "tool-missing",
        "syntax-error",
        "native-check-failure",
        "unexpected-source-mutation",
    }


def test_atomic_text_and_json_replace_existing_outputs(tmp_path: Path) -> None:
    text_path = tmp_path / "reports" / "result.txt"
    json_path = tmp_path / "reports" / "result.json"

    write_text_atomic(text_path, "first")
    write_text_atomic(text_path, "second\n")
    write_json_atomic(json_path, {"z": 1, "a": 2})

    assert text_path.read_text(encoding="utf-8") == "second\n"
    assert json_path.read_text(encoding="utf-8") == '{\n  "a": 2,\n  "z": 1\n}\n'
    assert not list((tmp_path / "reports").glob(".*.tmp"))


def test_clear_artifacts_is_bounded_and_handles_files_and_directories(tmp_path: Path) -> None:
    boundary = tmp_path / "reports"
    file_path = boundary / "result.json"
    directory = boundary / "scout"
    write_text_atomic(file_path, "{}\n")
    write_text_atomic(directory / "verdict.json", "{}\n")

    clear_artifacts(boundary, [file_path, directory])

    assert not file_path.exists()
    assert not directory.exists()
    with pytest.raises(LifecycleError, match="boundary itself"):
        clear_artifacts(boundary, [boundary])
    with pytest.raises(LifecycleError, match="within artifact boundary"):
        clear_artifacts(boundary, [tmp_path / "outside.json"])


def test_clear_artifacts_unlinks_a_symlink_without_following_it(tmp_path: Path) -> None:
    boundary = tmp_path / "reports"
    outside = tmp_path / "source.py"
    outside.write_text("preserve\n", encoding="utf-8")
    boundary.mkdir()
    link = boundary / "result.json"
    link.symlink_to(outside)

    clear_artifacts(boundary, [link])

    assert not link.exists()
    assert outside.read_text(encoding="utf-8") == "preserve\n"


def test_source_manifest_is_relative_stable_and_rejects_escapes(tmp_path: Path) -> None:
    root = tmp_path / "host"
    first = root / "src" / "a.ts"
    second = root / "src" / "b.ts"
    write_text_atomic(first, "export const a = 1;\n")
    write_text_atomic(second, "export const b = 2;\n")

    manifest = source_manifest(root, [second, first])

    assert list(manifest) == ["src/a.ts", "src/b.ts"]
    assert all(len(digest) == 64 for digest in manifest.values())
    assert json.dumps(manifest, sort_keys=True) == json.dumps(
        source_manifest(root, [first, second]), sort_keys=True
    )
    with pytest.raises(LifecycleError, match="within source root"):
        source_manifest(root, [tmp_path / "outside.ts"])


def test_source_manifest_rejects_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    outside = tmp_path / "outside.ts"
    outside.write_text("export {};\n", encoding="utf-8")
    link = root / "linked.ts"
    link.symlink_to(outside)

    with pytest.raises(LifecycleError, match="symbolic link"):
        source_manifest(root, [link])
