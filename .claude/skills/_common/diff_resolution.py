#!/usr/bin/env python3
"""Shared diff / target resolution for skill scripts.

Normalizes the many ways a caller can name "what changed" into a file set:
explicit paths/globs, the working-tree or staged diff, a single commit, a
commit range (``A..B``), a subsystem area, or a ``--since`` time spec.

Lifted out of ``find-test-obligation-drift/scripts/detect.py`` so that skill
and ``/which-cleanup`` share one implementation rather than two diverging
copies (ADR 0024 — no parallel writers of the same shape).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_COMMON_DIR = Path(__file__).resolve().parent
if str(_COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMON_DIR))

from product_health import expand_paths

DEFAULT_SUFFIXES = (".py", ".js", ".html", ".md", ".yaml", ".yml", ".toml")


def resolve_project_root(explicit: Path | None = None) -> Path:
    """Resolve the target-project root for de-baked skill scripts.

    An explicit ``--project-root`` always wins. Otherwise prefer the git
    toplevel of the current working directory (so a run from a subdirectory
    of the target repo still anchors at its root), falling back to the cwd
    itself outside any git repo. Never anchors on the kit's own location —
    the skill kit may live in a different repo than the target project.
    """
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True, capture_output=True, check=True,
        )
        toplevel = result.stdout.strip()
        if toplevel:
            return Path(toplevel).resolve()
    except (OSError, subprocess.CalledProcessError):
        pass
    return cwd.resolve()


def run_git_name_only(project_root: Path, cmd: list[str]) -> list[str]:
    """Run a git command, returning non-empty stripped stdout lines (``[]`` on failure)."""
    try:
        result = subprocess.run(cmd, cwd=project_root, text=True, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def diff_loc(project_root: Path, git_args: list[str]) -> int:
    """Sum of added + deleted lines for ``git diff --numstat <git_args>`` (0 on failure).

    ``git_args`` is the ref selector, e.g. ``["--cached"]``, ``["HEAD~1"]``, or
    ``["A..B"]``. Binary files (``-``/``-`` in numstat) contribute 0.
    """
    total = 0
    for line in run_git_name_only(project_root, ["git", "diff", "--numstat", *git_args]):
        parts = line.split("\t")
        if len(parts) >= 2:
            added, deleted = parts[0], parts[1]
            total += (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
    return total


def git_files(project_root: Path, *, staged: bool = False, changed_from: str | None = None) -> list[str]:
    """Repo-relative paths from a working-tree, staged, or ``changed_from`` ref diff."""
    if changed_from:
        return run_git_name_only(project_root, ["git", "diff", "--name-only", changed_from])
    if staged:
        return run_git_name_only(project_root, ["git", "diff", "--cached", "--name-only"])
    tracked = run_git_name_only(project_root, ["git", "diff", "--name-only"])
    untracked = run_git_name_only(project_root, ["git", "ls-files", "--others", "--exclude-standard"])
    return sorted(set(tracked + untracked))


def changed_paths(
    project_root: Path,
    paths: list[str] | None,
    *,
    staged: bool = False,
    changed_from: str | None = None,
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES,
) -> list[Path]:
    """Resolve explicit paths (globs/dirs expanded) or a git diff to absolute ``Path``s."""
    if paths:
        return expand_paths(project_root, paths, suffixes)
    return [project_root / f for f in git_files(project_root, staged=staged, changed_from=changed_from)]


def resolve_commit(project_root: Path, sha: str) -> list[str]:
    """Repo-relative paths changed by a single commit.

    ``--root`` makes a parentless (root/initial) commit report its added files
    instead of an empty diff.
    """
    return run_git_name_only(
        project_root,
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha],
    )


def resolve_range(project_root: Path, rev_range: str) -> list[str]:
    """Repo-relative paths changed across a commit range, e.g. ``A..B``."""
    return run_git_name_only(project_root, ["git", "diff", "--name-only", rev_range])


def resolve_since(project_root: Path, since_spec: str) -> list[str]:
    """Unique repo-relative paths touched by commits since a time spec.

    ``since_spec`` is any ``git log --since=`` value (``3.days.ago``,
    ``2026-06-01``, ``"2 weeks ago"``).
    """
    out = run_git_name_only(
        project_root,
        ["git", "log", f"--since={since_spec}", "--name-only", "--pretty=format:"],
    )
    return sorted(set(out))


def resolve_area(
    project_root: Path,
    area: str,
    registry: dict,
    *,
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES,
) -> list[Path]:
    """Expand a subsystem's registry path prefixes to the on-disk file set.

    ``registry`` is the mapping returned by ``subsystems.load_registry``.
    Raises ``KeyError`` if ``area`` is not a registered subsystem.
    """
    body = registry.get(area)
    if body is None:
        raise KeyError(area)
    prefixes = [p for p in (body.get("paths") or []) if isinstance(p, str)]
    if not prefixes:
        return []
    return expand_paths(project_root, prefixes, suffixes)
