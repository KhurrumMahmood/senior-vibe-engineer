#!/usr/bin/env python3
"""Blocking comment-drift subset, bundled for stock-installed use."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect import SUFFIXES, scan_files  # noqa: E402
from support import iter_files, resolve_project_root  # noqa: E402


BLOCKING_PATTERNS = {
    "detached_section_banner",
    "malformed_doc_reference",
    "noisy_html_comment",
    "obvious_narration_comment",
    "stale_comment_term",
}
NOQA_RE = re.compile(r"noqa:\s*comment-drift:\s*\S")


def expand_paths(paths: list[str], project_root: Path) -> list[Path]:
    expanded: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        candidates: list[Path]
        if path.is_dir():
            candidates = iter_files(path, SUFFIXES)
        elif not path.exists() or path.suffix.lower() in SUFFIXES:
            candidates = [path]
        else:
            candidates = []
        for candidate in candidates:
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in seen:
                continue
            seen.add(key)
            expanded.append(candidate)
    return expanded


def _line_has_noqa(path: Path, lineno: int) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    return 1 <= lineno <= len(lines) and bool(NOQA_RE.search(lines[lineno - 1]))


def _check_path(path: Path, project_root: Path) -> tuple[int, bool]:
    try:
        path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{path}: comment-drift: cannot read - {exc}", file=sys.stderr)
        return 0, True

    hits = 0
    for finding in scan_files([path], project_root):
        if finding.pattern not in BLOCKING_PATTERNS or _line_has_noqa(path, finding.lineno):
            continue
        hits += 1
        print(
            f"{finding.file}:{finding.lineno}:1: comment-drift: "
            f"{finding.pattern}: {finding.summary} "
            "(or mark with `noqa: comment-drift: <reason>`)"
        )
    return hits, False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files or directories to check.")
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)

    project_root = resolve_project_root(args.project_root)
    total_hits = 0
    had_io_error = False
    for path in expand_paths(args.paths, project_root):
        count, io_error = _check_path(path, project_root)
        total_hits += count
        had_io_error = had_io_error or io_error
    if had_io_error:
        return 2
    return 1 if total_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
