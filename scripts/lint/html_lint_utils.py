"""Shared helpers for HTML class-chain lints.

The ``no_inline_*`` lint family (alert, modal, pill, th_col) all flag
hand-rolled markup whose Tailwind class chain duplicates a cotton
primitive. They share the same skip rules:

- Skip matches inside ``<script>...</script>`` blocks (cotton renders at
  Django template time, not in browser-runtime template literals).
- Skip matches inside HTML comments (``<!-- ... -->``) and Django
  comments (``{# ... #}``) on the same line.
- Skip lines carrying a per-lint ``noqa: <name>: <reason>`` marker.

This module owns the byte-offset and line-substring primitives those
skip rules need, so each lint stays focused on its own chain matcher.
Stdlib-only by the same rule that keeps ``path_utils`` stdlib-only — the
HTML lints run from pre-commit before the virtualenv is ready.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Pattern

from path_utils import should_skip_dir

SCRIPT_BLOCK_RE = re.compile(
    r"<script\b(?![^>]*\bsrc=)[^>]*>(?P<body>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)


def expand_html_paths(paths: Iterable[str]) -> list[str]:
    """Expand files/directories to a stable list of HTML files.

    Mirrors ``path_utils.expand_python_paths`` for ``.html`` suffixes.
    Missing explicit paths are preserved so callers' "cannot read"
    handling still surfaces a typo as an invocation error.
    """
    suffixes = (".html",)
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
                    if candidate.suffix in suffixes:
                        add(candidate)
            continue

        if path.exists() and path.suffix not in suffixes:
            continue
        add(raw_path)

    return expanded


def line_col(src: str, offset: int) -> tuple[int, int]:
    """Return 1-indexed line number and 0-indexed column for ``offset``."""
    line = src.count("\n", 0, offset) + 1
    line_start = src.rfind("\n", 0, offset) + 1
    return line, offset - line_start


def line_text(src: str, offset: int) -> str:
    """Return the full text of the line containing ``offset``."""
    line_start = src.rfind("\n", 0, offset) + 1
    line_end = src.find("\n", offset)
    if line_end == -1:
        line_end = len(src)
    return src[line_start:line_end]


def is_in_html_comment(line: str, col: int) -> bool:
    """True when ``col`` falls inside an unclosed ``<!-- ... -->`` on this line."""
    open_idx = line.rfind("<!--", 0, col)
    if open_idx == -1:
        return False
    close_idx = line.find("-->", open_idx)
    return close_idx == -1 or close_idx >= col


def is_in_django_comment(line: str, col: int) -> bool:
    """True when ``col`` falls inside an unclosed ``{# ... #}`` on this line."""
    open_idx = line.rfind("{#", 0, col)
    if open_idx == -1:
        return False
    close_idx = line.find("#}", open_idx)
    return close_idx == -1 or close_idx >= col


def line_has_noqa(line: str, noqa_re: Pattern[str]) -> bool:
    """True when ``line`` carries the lint's ``noqa`` allow-list marker."""
    return bool(noqa_re.search(line))


def script_block_ranges(src: str) -> list[tuple[int, int]]:
    """Byte-offset ranges of every inline ``<script>...</script>`` body.

    ``<script src="...">`` tags are excluded because they cannot carry
    inline template-literal markup. Ranges cover the body only (not the
    open/close tags) so a chain on the open tag itself would still flag.
    """
    return [(m.start("body"), m.end("body")) for m in SCRIPT_BLOCK_RE.finditer(src)]


def offset_in_ranges(offset: int, ranges: list[tuple[int, int]]) -> bool:
    """True when ``offset`` falls inside any of the precomputed ranges."""
    for start, end in ranges:
        if start <= offset < end:
            return True
    return False
