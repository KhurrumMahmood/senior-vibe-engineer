"""Shared YAML frontmatter parser for scripts/.

Replaces the four hand-rolled `parse_frontmatter` implementations that
diverged across decisions.py, plans.py, skill_meta.py, and specs.py.
Backed by PyYAML so multiline block scalars, lists, nested maps, and
quoted strings work uniformly.

Two PyYAML defaults bite callers and need explicit handling at the call
site — the parser does not paper over them, since silent coercion would
hide registry bugs:

* YAML 1.1 octal: SafeLoader parses unquoted leading-zero integers as
  octal (``id: 0010`` → int 8). ADR ids must be quoted in frontmatter,
  and ``decisions.py`` derives the canonical id from the filename
  (warning when the frontmatter id disagrees).
* Date auto-coercion: ``YYYY-MM-DD`` becomes ``datetime.date``, which
  ``json.dump`` cannot serialize. ``specs.py`` normalizes
  ``last_audited`` / ``last_synced`` at the load boundary via
  ``_coerce_date_str`` so JSON output paths stay date-safe.

Public surface:

    from _lib.yaml_frontmatter import parse, read, FrontmatterDoc, FrontmatterError

    doc = parse(text)
    doc.metadata     # dict, {} when no frontmatter
    doc.body         # str, everything after the closing ---
    doc.has_frontmatter
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\n(?P<body>.*?)^---[ \t]*(?:\n+|\Z)",
    re.DOTALL | re.MULTILINE,
)


class FrontmatterError(ValueError):
    """Raised when frontmatter is present but malformed (invalid YAML, non-mapping top level)."""

    def __init__(self, message: str, *, path: str | Path | None = None, line: int | None = None):
        self.path = str(path) if path is not None else None
        self.line = line
        prefix = ""
        if self.path:
            prefix = f"{self.path}"
            if line is not None:
                prefix += f":{line}"
            prefix += ": "
        super().__init__(f"{prefix}{message}")


@dataclass(frozen=True)
class FrontmatterDoc:
    metadata: dict[str, Any]
    body: str
    has_frontmatter: bool
    raw_frontmatter: str | None


def parse(text: str, *, path: str | Path | None = None) -> FrontmatterDoc:
    # Strip leading UTF-8 BOM so editors that prepend one don't defeat the
    # \A---  anchor. Normalize CRLF to LF so files committed with Windows
    # line endings parse the same as LF — matters for `parse()` callers
    # that bypass Path.read_text() (which already universal-newlines).
    if text.startswith("﻿"):
        text = text[1:]
    if "\r\n" in text:
        text = text.replace("\r\n", "\n")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return FrontmatterDoc(metadata={}, body=text, has_frontmatter=False, raw_frontmatter=None)
    raw = match.group("body")
    body = text[match.end():]
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        line = (line + 2) if line is not None else None  # +1 for 1-based, +1 for opening ---
        raise FrontmatterError(f"invalid YAML in frontmatter: {exc}", path=path, line=line) from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError(
            f"frontmatter must be a mapping at the top level, got {type(data).__name__}",
            path=path,
        )
    return FrontmatterDoc(metadata=data, body=body, has_frontmatter=True, raw_frontmatter=raw)


def read(path: str | Path) -> FrontmatterDoc:
    p = Path(path)
    return parse(p.read_text(encoding="utf-8"), path=p)
