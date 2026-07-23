"""Atomic output used by the shared language source inventory."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts._lib.language_support.lifecycle import (
    LifecycleError,
    write_text_atomic,
)


def test_atomic_text_replaces_existing_output(tmp_path: Path) -> None:
    text_path = tmp_path / "reports" / "result.txt"

    write_text_atomic(text_path, "first")
    write_text_atomic(text_path, "second\n")

    assert text_path.read_text(encoding="utf-8") == "second\n"
    assert not list((tmp_path / "reports").glob(".*.tmp"))


def test_atomic_text_rejects_symlink_and_directory_destinations(tmp_path: Path) -> None:
    outside = tmp_path / "source.py"
    outside.write_text("preserve\n", encoding="utf-8")
    link = tmp_path / "result.json"
    link.symlink_to(outside)

    with pytest.raises(LifecycleError, match="symbolic link"):
        write_text_atomic(link, "replace\n")
    with pytest.raises(LifecycleError, match="file path"):
        write_text_atomic(tmp_path, "replace\n")

    assert outside.read_text(encoding="utf-8") == "preserve\n"
