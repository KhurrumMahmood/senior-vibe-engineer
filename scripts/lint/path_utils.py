"""Shared path handling for project lint scripts.

The custom AST rules are intentionally stdlib-only so they can run from
pre-commit, CI, or a fresh checkout before the virtualenv is ready.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

PYTHON_SUFFIXES = (".py",)

SKIP_DIR_NAMES = {
    "migrations",
    ".venv",
    "node_modules",
    "__pycache__",
    "staticfiles",
}


def should_skip_dir(dirname: str) -> bool:
    """Return True when a recursive lint scan should not descend."""
    return dirname.startswith(".") or dirname in SKIP_DIR_NAMES


def expand_python_paths(paths: Iterable[str]) -> list[str]:
    """Expand files/directories to a stable list of Python files.

    Missing explicit paths are preserved so the caller's existing
    "cannot read" handling still returns an invocation error instead of
    silently dropping a typo.
    """
    expanded: list[str] = []
    seen: set[str] = set()

    def add(path: Path | str) -> None:
        display = os.fspath(path)
        key = str(Path(display).resolve()) if Path(display).exists() else display
        if key in seen:
            return
        seen.add(key)
        expanded.append(display)

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = [d for d in sorted(dirnames) if not should_skip_dir(d)]
                for filename in sorted(filenames):
                    candidate = Path(dirpath) / filename
                    if candidate.suffix in PYTHON_SUFFIXES:
                        add(candidate)
            continue

        if path.exists() and path.suffix not in PYTHON_SUFFIXES:
            continue
        add(raw_path)

    return expanded
