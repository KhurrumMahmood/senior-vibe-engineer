#!/usr/bin/env python3
"""comment-drift lint rule for the live /sites surface.

This is the commit-time companion to the advisory
``.claude/skills/find-comment-drift`` SUSPECT skill. It imports the same
detector, but fails only on comment shapes that are bad enough to block a
diff: stale terminology, detached banners, obvious narration, noisy HTML
section comments, and brittle doc references. Advisory gaps such as
``jsdoc_candidate``, ``thin_jsdoc_comment``, and thin class docstrings stay in
the skill report.

Allow-list (reason required):

    # noqa: comment-drift: <reason>       (Python)
    // noqa: comment-drift: <reason>      (JavaScript)
    <!-- noqa: comment-drift: <reason> --> / {# noqa: comment-drift: <reason> #}

Usage:

    scripts/lint/no_comment_drift.py <file-or-dir> [...]

Exit status:

    0  clean
    1  one or more violations found
    2  invocation error
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Iterable

from path_utils import should_skip_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
DETECTOR_PATH = REPO_ROOT / ".claude" / "skills" / "find-comment-drift" / "scripts" / "detect.py"
SUFFIXES = (".py", ".js", ".html")
BLOCKING_PATTERNS = {
    "detached_section_banner",
    "malformed_doc_reference",
    "noisy_html_comment",
    "obvious_narration_comment",
    "stale_comment_term",
}
NOQA_RE = re.compile(r"noqa:\s*comment-drift:\s*\S")


def _load_detector():
    spec = importlib.util.spec_from_file_location("_find_comment_drift_detect", DETECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load detector from {DETECTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expand_paths(paths: Iterable[str]) -> list[str]:
    """Expand files/directories to a stable list of in-scope files."""
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
                    if candidate.suffix in SUFFIXES:
                        add(candidate)
            continue

        if path.exists() and path.suffix not in SUFFIXES:
            continue
        add(raw_path)

    return expanded


def _line_has_noqa(path: Path, lineno: int) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    if lineno < 1 or lineno > len(lines):
        return False
    return bool(NOQA_RE.search(lines[lineno - 1]))


def _check_path(detector, path: str) -> tuple[int, bool]:
    file_path = Path(path)
    try:
        # The detector skips files it cannot decode (uniform with the other
        # SUSPECT detectors), so probe the read here to preserve this blocking
        # lint's "cannot read -> exit 2" contract instead of letting an
        # unreadable file pass silently as clean.
        file_path.read_text(encoding="utf-8")
        findings = detector.scan_files([file_path], REPO_ROOT)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{path}: comment-drift: cannot read - {exc}", file=sys.stderr)
        return 0, True
    except SyntaxError as exc:
        print(f"{path}: comment-drift: cannot parse - {exc}", file=sys.stderr)
        return 0, True

    hits = 0
    for finding in findings:
        if finding.pattern not in BLOCKING_PATTERNS:
            continue
        resolved = REPO_ROOT / finding.file
        if _line_has_noqa(resolved, finding.lineno):
            continue
        hits += 1
        print(
            f"{finding.file}:{finding.lineno}:1: comment-drift: "
            f"{finding.pattern}: {finding.summary} "
            f"(or mark with `noqa: comment-drift: <reason>`)"
        )
    return hits, False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: no_comment_drift.py <file-or-dir> [...]", file=sys.stderr)
        return 2

    detector = _load_detector()
    total_hits = 0
    had_io_error = False
    for path in expand_paths(argv):
        count, io_err = _check_path(detector, path)
        total_hits += count
        had_io_error = had_io_error or io_err
    if had_io_error:
        return 2
    return 1 if total_hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
