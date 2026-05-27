#!/usr/bin/env python3
"""Per-skill scan/ignore scope — the "gitignore per skill" mechanism (ADR 0021).

A skill's scope answers "which files does THIS skill apply to in THIS repo?"
It is **host-authored data, not baked-in code**: each skill reads an optional
`.engineering/docs/<skill>-scope.md` descriptor from the cross-agent state home
(`engineering_home.docs_path`). Adopters tune a skill's reach without editing
toolkit code, and the toolkit ships with zero assumptions about any one host's
folder layout.

The contract is **ignore-first** (the user's stated principle, twice): the
default universe is the whole repo minus a small set of never-useful
directories minus the host's `## Ignore` globs. Declaring explicit `## Roots`
is an *optional narrowing*, not the primary knob — a host says what to leave
out, not what to let in.

Descriptor format (loose markdown, stdlib-parseable — no PyYAML):

    ## Ignore
    - `**/migrations/**` — generated, never analyzed
    - `app/legacy/`      — frozen subtree

    ## Roots          (optional; omit for whole-repo-minus-ignores)
    - app/
    - scripts/

`## Scan` is an accepted alias for `## Roots`. Each bullet's pattern is the
backtick-delimited token if present, else the text before a ` — ` rationale.
Patterns are fnmatch globs over the **repo-relative POSIX path** (consistent
with the `todo-tuning.md` `## Path skip` precedent this generalizes), with a
gitignore-style subtree rule: a pattern naming a directory also matches
everything beneath it.

Stdlib-only. Read-only against the project.
"""
from __future__ import annotations

import fnmatch
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# engineering_home is this module's sibling in _common; make it importable
# regardless of who imported us (a skill script, a test, or python -c).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engineering_home as _home  # noqa: E402

# Directories never worth scanning, pruned during the walk regardless of host
# config — VCS, virtualenvs, dependency trees, build artifacts, tool caches,
# and generated DB migrations. Kept to "common noise across the ecosystems the
# toolkit supports"; the host's `## Ignore` is the real, project-specific knob.
BUILTIN_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "node_modules", "__pycache__", "site-packages",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", ".next", ".cache",
    "migrations",
})

# Repo-relative POSIX *prefixes* pruned during the walk. Unlike the bare-name
# dirs above these are anchored multi-segment subtrees. `.claude/worktrees`
# holds live agent git worktrees (a whole second checkout) — never the host's
# own source.
BUILTIN_SKIP_PREFIXES = (
    ".claude/worktrees",
)


@dataclass
class Scope:
    """A resolved per-skill scan scope.

    - ``roots``: optional narrowing. ``None`` (or empty) means the universe is
      the whole repo (minus builtin skips minus ``ignore``). When set, only
      paths under one of these repo-relative roots are in scope.
    - ``ignore``: glob patterns removed from the universe — the ignore-first
      primary knob.
    - ``source``: the descriptor path actually read, or ``None`` when no file
      existed (ignore-first fallback in effect). Diagnostic only.
    """
    roots: list[str] | None = None
    ignore: list[str] = field(default_factory=list)
    source: Path | None = None


# Headings (normalized to lowercase) that select each section.
_IGNORE_HEADINGS = {"ignore", "ignores", "skip", "path skip", "paths to skip"}
_ROOTS_HEADINGS = {"roots", "root", "scan", "scan roots", "include"}


def _bullet_token(line: str) -> str | None:
    """Pattern from a markdown bullet: the backtick-delimited token if present,
    else the text before a ` — ` rationale separator. ``None`` if blank.
    """
    body = line[1:].strip()  # drop the leading -, *, or +
    if "`" in body:
        start = body.index("`")
        end = body.find("`", start + 1)
        if end > start:
            token = body[start + 1:end].strip()
            return token or None
    token = body.split(" — ", 1)[0].strip()
    return token or None


def parse_scope(text: str) -> tuple[list[str] | None, list[str]]:
    """Parse a scope descriptor body into ``(roots, ignore)``.

    Pure function over text — unit-testable without disk. ``roots`` is ``None``
    when no Roots/Scan section is present *or* the section is empty (an empty
    narrowing is no narrowing); ``ignore`` is the accumulated glob list.
    """
    roots: list[str] = []
    ignore: list[str] = []
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if heading in _IGNORE_HEADINGS:
                section = "ignore"
            elif heading in _ROOTS_HEADINGS:
                section = "roots"
            else:
                section = None
            continue
        if not line.startswith(("-", "*", "+")):
            continue
        token = _bullet_token(line)
        if not token:
            continue
        if section == "ignore":
            ignore.append(token)
        elif section == "roots":
            roots.append(token.rstrip("/"))
    return (roots or None), ignore


def load_scope(repo_root: Path | str, skill_name: str) -> Scope:
    """Read `.engineering/docs/<skill_name>-scope.md`; empty Scope if absent.

    An absent (or unreadable) descriptor yields the ignore-first whole-repo
    scope (``roots=None``, ``ignore=[]``) — a skill works with no config.
    """
    repo_root = Path(repo_root)
    path, _used_legacy = _home.docs_path(repo_root, f"{skill_name}-scope.md")
    if not path.is_file():
        return Scope(roots=None, ignore=[], source=None)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Scope(roots=None, ignore=[], source=None)
    roots, ignore = parse_scope(text)
    return Scope(roots=roots, ignore=ignore, source=path)


def _path_matches(rel_posix: str, pattern: str) -> bool:
    """fnmatch over the repo-relative POSIX path, with a gitignore-style subtree
    rule: a pattern naming a directory also matches everything beneath it.
    """
    p = pattern.rstrip("/")
    return (
        rel_posix == p
        or rel_posix.startswith(p + "/")
        or fnmatch.fnmatch(rel_posix, p)
        or fnmatch.fnmatch(rel_posix, p + "/*")
    )


def _matches_any(rel_posix: str, patterns: list[str]) -> bool:
    return any(_path_matches(rel_posix, p) for p in patterns)


def iter_paths(
    repo_root: Path | str,
    scope: Scope,
    *,
    extensions: frozenset[str] | None = None,
) -> list[Path]:
    """Return absolute paths of repo files in ``scope``, ignore-first.

    Universe = every file under ``repo_root``, pruning ``BUILTIN_SKIP_DIRS``
    directories and ``BUILTIN_SKIP_PREFIXES`` subtrees, minus ``scope.ignore``
    globs, narrowed to ``scope.roots`` when those are set. Optional
    ``extensions`` (e.g. ``{".py"}``) filters by suffix; ``None`` = all files.
    Sorted for deterministic output.
    """
    repo_root = Path(repo_root)
    roots = scope.roots or None
    ignore = scope.ignore
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = Path(dirpath).relative_to(repo_root).as_posix()
        kept: list[str] = []
        for d in dirnames:
            if d in BUILTIN_SKIP_DIRS:
                continue
            child_rel = d if rel_dir == "." else f"{rel_dir}/{d}"
            if any(child_rel == pre or child_rel.startswith(pre + "/")
                   for pre in BUILTIN_SKIP_PREFIXES):
                continue
            kept.append(d)
        dirnames[:] = kept

        for fname in filenames:
            abs_path = Path(dirpath) / fname
            if extensions is not None and abs_path.suffix not in extensions:
                continue
            rel_posix = abs_path.relative_to(repo_root).as_posix()
            if roots and not _matches_any(rel_posix, roots):
                continue
            if _matches_any(rel_posix, ignore):
                continue
            out.append(abs_path)
    out.sort()
    return out


def scan(
    repo_root: Path | str,
    skill_name: str,
    *,
    extensions: frozenset[str] | None = None,
) -> list[Path]:
    """Convenience: ``iter_paths(repo_root, load_scope(repo_root, skill_name))``.

    The ergonomic entry point for a detector — load the skill's host-authored
    scope and return the in-scope files in one call.
    """
    return iter_paths(repo_root, load_scope(repo_root, skill_name), extensions=extensions)
