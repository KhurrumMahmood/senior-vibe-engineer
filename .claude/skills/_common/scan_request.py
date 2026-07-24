#!/usr/bin/env python3
"""Resolve one bounded scan request, including new-side Git hunk ranges.

The request separates *what the caller selected* from *how a detector uses that
selection*. It supplies current paths, file-level change facts, and changed-line
ranges without deciding whether a semantic/project detector may be clipped.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VALID_MODES = {"auto", "diff-lines", "changed-files", "paths", "project"}
VALID_SELECTORS = {
    "working-tree",
    "staged",
    "changed-from",
    "commit",
    "range",
    "paths",
    "project",
}
DIFF_SELECTORS = {"working-tree", "staged", "changed-from", "commit", "range"}
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class ScanRequestError(Exception):
    """A scan request could not be resolved safely or truthfully."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LineRange:
    """Inclusive one-based new-side line range."""

    start: int
    end: int


@dataclass(frozen=True)
class PathChange:
    """One path-level change plus any current-tree line attribution facts."""

    path: str
    change_type: str
    old_path: str | None
    current_exists: bool
    binary: bool
    line_ranges: tuple[LineRange, ...]


@dataclass(frozen=True)
class ScanRequest:
    """Serializable request shared by cleanup routing and detector adapters."""

    project_root: str
    requested_mode: str
    selector: dict[str, Any]
    content_basis: str
    line_filter_safe: bool | None
    changes: tuple[PathChange, ...]
    warnings: tuple[dict[str, str], ...] = ()
    schema_version: int = 1

    @property
    def resolved_paths(self) -> tuple[str, ...]:
        return tuple(sorted(change.path for change in self.changes if change.current_exists))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["resolved_paths"] = list(self.resolved_paths)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def _run_git(root: Path, args: list[str], *, code: str = "git_scope_unresolvable") -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise ScanRequestError("git_unavailable", "Git is unavailable") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ScanRequestError(code, detail or f"Git could not resolve: {' '.join(args)}")
    return result.stdout


def _is_git_repo(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ScanRequestError("git_unavailable", "Git is unavailable") from exc
    return result.returncode == 0 and result.stdout.strip() == "true"


def _has_head(root: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _normalize_path(root: Path, raw: str) -> str:
    if not raw.strip():
        raise ScanRequestError("empty_explicit_path", "Explicit paths cannot be empty")
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ScanRequestError(
            "path_outside_project", f"Path resolves outside the project root: {raw}"
        ) from exc


def _decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")


def _parse_name_status(data: bytes) -> list[dict[str, str | None]]:
    tokens = data.rstrip(b"\0").split(b"\0") if data else []
    changes: list[dict[str, str | None]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if b"\t" in token:
            status_raw, first_path = token.split(b"\t", 1)
        else:
            status_raw = token
            if index >= len(tokens):
                raise ScanRequestError("git_output_invalid", "name-status row has no path")
            first_path = tokens[index]
            index += 1
        status = _decode_path(status_raw)
        kind = status[:1]
        if kind in {"R", "C"}:
            if index >= len(tokens):
                raise ScanRequestError("git_output_invalid", "rename/copy row has no new path")
            second_path = tokens[index]
            index += 1
            changes.append(
                {
                    "path": _decode_path(second_path),
                    "old_path": _decode_path(first_path),
                    "change_type": "renamed" if kind == "R" else "copied",
                }
            )
            continue
        change_type = {
            "A": "added",
            "D": "deleted",
            "M": "modified",
            "T": "type-changed",
            "U": "unmerged",
        }.get(kind, "unknown")
        changes.append(
            {"path": _decode_path(first_path), "old_path": None, "change_type": change_type}
        )
    return changes


def _coalesce(ranges: list[LineRange]) -> tuple[LineRange, ...]:
    if not ranges:
        return ()
    ordered = sorted(ranges, key=lambda item: (item.start, item.end))
    merged = [ordered[0]]
    for item in ordered[1:]:
        previous = merged[-1]
        if item.start <= previous.end + 1:
            merged[-1] = LineRange(previous.start, max(previous.end, item.end))
        else:
            merged.append(item)
    return tuple(merged)


def _apply_patch_facts(raw_patch: bytes, changes: list[dict[str, Any]]) -> None:
    section = -1
    current: dict[str, Any] | None = None
    for raw_line in raw_patch.decode("utf-8", errors="surrogateescape").splitlines():
        if raw_line.startswith("diff --git "):
            section += 1
            current = changes[section] if section < len(changes) else None
            continue
        if current is None:
            continue
        if raw_line.startswith("Binary files ") or raw_line == "GIT binary patch":
            current["binary"] = True
            continue
        match = _HUNK_RE.match(raw_line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) is not None else 1
        if count > 0:
            current["line_ranges"].append(LineRange(start, start + count - 1))
    for change in changes:
        change["line_ranges"] = _coalesce(change["line_ranges"])
    section_count = section + 1
    if section_count != len(changes):
        raise ScanRequestError(
            "git_output_invalid",
            "Git patch sections do not align with the name-status change set",
        )


def _full_file_range(path: Path) -> tuple[LineRange, ...]:
    if not path.is_file():
        return ()
    line_count = 0
    last_byte = b""
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            line_count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if not last_byte:
        return ()
    line_count += 0 if last_byte == b"\n" else 1
    return (LineRange(1, line_count),)


def _is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(8192)
    except OSError:
        return False


def _exact_revision(root: Path, revision: str) -> str:
    return _run_git(root, ["rev-parse", "--verify", revision]).decode().strip()


def _worktree_matches_revision(root: Path, revision: str, path: str) -> bool:
    worktree = subprocess.run(
        ["git", "hash-object", "--", path],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    expected = subprocess.run(
        ["git", "rev-parse", f"{revision}:{path}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return (
        worktree.returncode == 0
        and expected.returncode == 0
        and worktree.stdout.strip() == expected.stdout.strip()
    )


def _staged_matches_worktree(root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", path],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _untracked_paths(root: Path) -> list[str]:
    raw = _run_git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    return sorted(_decode_path(token) for token in raw.rstrip(b"\0").split(b"\0") if token)


def _diff_commands(
    root: Path, selector_kind: str, selector_value: str | None
) -> tuple[list[str], list[str], str, str | None]:
    """Return name-status args, patch args, content basis, and comparison revision."""
    common = ["--find-renames"]
    if selector_kind == "working-tree":
        if not _has_head(root):
            return [], [], "working-tree", None
        return (
            ["diff", "--name-status", "-z", *common, "HEAD", "--"],
            ["diff", "--unified=0", "--no-color", "--no-ext-diff", *common, "HEAD", "--"],
            "working-tree",
            None,
        )
    if selector_kind == "staged":
        return (
            ["diff", "--cached", "--name-status", "-z", *common, "--"],
            ["diff", "--cached", "--unified=0", "--no-color", "--no-ext-diff", *common, "--"],
            "index",
            None,
        )
    if not selector_value or not selector_value.strip():
        raise ScanRequestError("empty_git_scope", f"{selector_kind} requires a value")
    if selector_kind == "changed-from":
        _exact_revision(root, selector_value)
        return (
            ["diff", "--name-status", "-z", *common, selector_value, "--"],
            ["diff", "--unified=0", "--no-color", "--no-ext-diff", *common, selector_value, "--"],
            "working-tree",
            None,
        )
    if selector_kind == "commit":
        revision = _exact_revision(root, selector_value)
        return (
            ["diff-tree", "--root", "--no-commit-id", "-r", "--name-status", "-z", *common, revision, "--"],
            ["show", "--format=", "--unified=0", "--no-color", "--no-ext-diff", *common, revision, "--"],
            revision,
            revision,
        )
    if selector_kind == "range":
        if ".." not in selector_value:
            raise ScanRequestError("git_scope_unresolvable", "range must use A..B")
        left, right = selector_value.rsplit("..", 1)
        if not left or not right:
            raise ScanRequestError("git_scope_unresolvable", "range must use A..B")
        _exact_revision(root, left)
        revision = _exact_revision(root, right)
        return (
            ["diff", "--name-status", "-z", *common, selector_value, "--"],
            ["diff", "--unified=0", "--no-color", "--no-ext-diff", *common, selector_value, "--"],
            revision,
            revision,
        )
    raise ScanRequestError("selector_invalid", f"Unsupported diff selector: {selector_kind}")


def _build_path_request(
    root: Path, requested_mode: str, selector_kind: str, explicit_paths: list[str] | None
) -> ScanRequest:
    if selector_kind == "project":
        if explicit_paths:
            raise ScanRequestError("selector_conflict", "project mode does not accept paths")
        return ScanRequest(
            project_root=str(root),
            requested_mode=requested_mode,
            selector={"kind": "project"},
            content_basis="working-tree",
            line_filter_safe=None,
            changes=(),
        )
    if not explicit_paths:
        raise ScanRequestError("paths_required", "paths mode requires at least one path")
    paths = sorted({_normalize_path(root, raw) for raw in explicit_paths})
    changes = tuple(
        PathChange(
            path=path,
            change_type="explicit",
            old_path=None,
            current_exists=(root / path).exists(),
            binary=_is_binary_file(root / path),
            line_ranges=(),
        )
        for path in paths
    )
    return ScanRequest(
        project_root=str(root),
        requested_mode=requested_mode,
        selector={"kind": "paths", "paths": paths},
        content_basis="working-tree",
        line_filter_safe=None,
        changes=changes,
    )


def build_scan_request(
    project_root: Path | str,
    *,
    requested_mode: str,
    selector_kind: str,
    selector_value: str | None = None,
    explicit_paths: list[str] | None = None,
) -> ScanRequest:
    """Build one normalized request without applying detector-specific semantics."""
    root = Path(project_root).resolve()
    if requested_mode not in VALID_MODES:
        raise ScanRequestError("scope_mode_invalid", f"Unknown mode: {requested_mode}")
    if selector_kind not in VALID_SELECTORS:
        raise ScanRequestError("selector_invalid", f"Unknown selector: {selector_kind}")
    if selector_kind in {"paths", "project"}:
        if requested_mode == "diff-lines":
            raise ScanRequestError("mode_requires_diff", "diff-lines requires a Git diff selector")
        return _build_path_request(root, requested_mode, selector_kind, explicit_paths)
    if explicit_paths:
        raise ScanRequestError("selector_conflict", "Git selectors do not accept explicit paths")
    if not _is_git_repo(root):
        raise ScanRequestError("not_git_repository", "Git selector requires a Git repository")

    name_args, patch_args, basis, comparison_revision = _diff_commands(
        root, selector_kind, selector_value
    )
    raw_changes: list[dict[str, Any]]
    if name_args:
        raw_changes = _parse_name_status(_run_git(root, name_args))
        for change in raw_changes:
            change.update(binary=False, line_ranges=[])
        _apply_patch_facts(_run_git(root, patch_args), raw_changes)
    else:
        raw_changes = []
        staged_or_untracked = _run_git(
            root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        for token in staged_or_untracked.rstrip(b"\0").split(b"\0"):
            if not token:
                continue
            path = _decode_path(token)
            binary = _is_binary_file(root / path)
            raw_changes.append(
                {
                    "path": path,
                    "old_path": None,
                    "change_type": "added",
                    "binary": binary,
                    "line_ranges": () if binary else _full_file_range(root / path),
                }
            )

    if selector_kind == "working-tree" and _has_head(root):
        known = {str(change["path"]) for change in raw_changes}
        for path in _untracked_paths(root):
            if path in known:
                continue
            binary = _is_binary_file(root / path)
            raw_changes.append(
                {
                    "path": path,
                    "old_path": None,
                    "change_type": "untracked",
                    "binary": binary,
                    "line_ranges": () if binary else _full_file_range(root / path),
                }
            )

    raw_changes.sort(key=lambda item: str(item["path"]))
    warnings: list[dict[str, str]] = []
    line_filter_safe = True
    for change in raw_changes:
        path = str(change["path"])
        current_exists = (root / path).exists()
        change["current_exists"] = current_exists
        if not change["line_ranges"]:
            continue
        if not current_exists:
            line_filter_safe = False
            warnings.append(
                {
                    "code": "content_basis_mismatch",
                    "path": path,
                    "detail": "The selected new-side file is absent from the current working tree.",
                }
            )
            continue
        matches = True
        if selector_kind == "staged":
            matches = _staged_matches_worktree(root, path)
        elif comparison_revision:
            matches = _worktree_matches_revision(root, comparison_revision, path)
        if not matches:
            line_filter_safe = False
            warnings.append(
                {
                    "code": "content_basis_mismatch",
                    "path": path,
                    "detail": "Current working-tree bytes differ from the selected new-side content basis.",
                }
            )

    changes = tuple(
        PathChange(
            path=str(change["path"]),
            change_type=str(change["change_type"]),
            old_path=str(change["old_path"]) if change["old_path"] is not None else None,
            current_exists=bool(change["current_exists"]),
            binary=bool(change["binary"]),
            line_ranges=tuple(change["line_ranges"]),
        )
        for change in raw_changes
    )
    selector: dict[str, Any] = {"kind": selector_kind}
    if selector_value is not None:
        selector["value"] = selector_value
    return ScanRequest(
        project_root=str(root),
        requested_mode=requested_mode,
        selector=selector,
        content_basis=basis,
        line_filter_safe=line_filter_safe,
        changes=changes,
        warnings=tuple(warnings),
    )
