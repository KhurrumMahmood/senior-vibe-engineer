#!/usr/bin/env python3
"""Scope-band classification for /which-cleanup.

Sizes a change into one of four bands from three independent axes — file
count, distinct-subsystem count, and diff magnitude (lines, when a git ref is
available). The HIGHEST band any axis triggers wins (OR-logic): a 2-file change
that crosses 3 subsystems is `large`, not `small`. Thresholds are tunable knobs
seeded from the 50-commit study behind ADR 0024; recalibrate against
reports/_meta/effectiveness.jsonl once real runs accumulate.
"""
from __future__ import annotations

from dataclasses import dataclass

TRIVIAL, SMALL, MEDIUM, LARGE = "trivial", "small", "medium", "large"
_ORDER = {TRIVIAL: 0, SMALL: 1, MEDIUM: 2, LARGE: 3}

# --- tunable thresholds ---
SMALL_MAX_FILES = 5
MEDIUM_MAX_FILES = 20
MEDIUM_MIN_SUBSYSTEMS = 2
LARGE_MIN_SUBSYSTEMS = 3
TRIVIAL_MAX_LOC = 30   # < this -> trivial
SMALL_MAX_LOC = 200    # < this -> small
MEDIUM_MAX_LOC = 1500  # < this -> medium; >= -> large


@dataclass(frozen=True)
class ScopeInputs:
    file_count: int
    subsystem_count: int
    diff_loc: int | None = None  # None when no git ref is available (path/area/since input)


def _file_band(n: int) -> str:
    if n <= 1:
        return TRIVIAL
    if n <= SMALL_MAX_FILES:
        return SMALL
    if n <= MEDIUM_MAX_FILES:
        return MEDIUM
    return LARGE


def _subsystem_band(n: int) -> str:
    # 0-1 subsystems: this axis contributes nothing (let file/loc decide).
    if n >= LARGE_MIN_SUBSYSTEMS:
        return LARGE
    if n >= MEDIUM_MIN_SUBSYSTEMS:
        return MEDIUM
    return TRIVIAL


def _loc_band(loc: int | None) -> str:
    if loc is None:  # axis drops out for non-diff inputs
        return TRIVIAL
    if loc < TRIVIAL_MAX_LOC:
        return TRIVIAL
    if loc < SMALL_MAX_LOC:
        return SMALL
    if loc < MEDIUM_MAX_LOC:
        return MEDIUM
    return LARGE


def classify(inputs: ScopeInputs) -> str:
    """Return the highest band any axis triggers."""
    bands = (
        _file_band(inputs.file_count),
        _subsystem_band(inputs.subsystem_count),
        _loc_band(inputs.diff_loc),
    )
    return max(bands, key=lambda b: _ORDER[b])


def axis_breakdown(inputs: ScopeInputs) -> dict[str, str]:
    """Per-axis bands, for transparency in the report (which axis drove the verdict)."""
    return {
        "files": _file_band(inputs.file_count),
        "subsystems": _subsystem_band(inputs.subsystem_count),
        "diff_loc": _loc_band(inputs.diff_loc),
    }
