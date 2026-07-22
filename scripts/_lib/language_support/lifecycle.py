"""Narrow lifecycle mechanics shared by proven language-support consumers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path


class LifecycleError(ValueError):
    """A lifecycle request would escape its declared boundary or lose evidence."""


class TerminalOutcome(StrEnum):
    """Cross-skill terminal outcomes; domain-level clean results remain local."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    TOOL_MISSING = "tool-missing"
    SYNTAX_ERROR = "syntax-error"
    NATIVE_CHECK_FAILURE = "native-check-failure"
    UNEXPECTED_SOURCE_MUTATION = "unexpected-source-mutation"


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_text_atomic(path: Path, content: str) -> None:
    """Replace one text artifact atomically without leaving a partial output."""
    if not isinstance(content, str):
        raise TypeError("atomic text content must be a string")
    target = _absolute(path)
    if target.exists() and target.is_dir():
        raise LifecycleError(f"atomic output must be a file path: {path}")
    if target.is_symlink():
        raise LifecycleError(f"atomic output may not be a symbolic link: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json_atomic(
    path: Path,
    payload: Mapping[str, object] | Sequence[object],
) -> None:
    """Write deterministic UTF-8 JSON through the atomic text boundary."""
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    write_text_atomic(path, rendered)


def clear_artifacts(boundary: Path, artifacts: Iterable[Path]) -> None:
    """Remove explicit stale artifacts without following a boundary escape."""
    root = _absolute(boundary)
    if root.is_symlink():
        raise LifecycleError(f"artifact boundary may not be a symbolic link: {boundary}")
    if root.exists() and not root.is_dir():
        raise LifecycleError(f"artifact boundary must be a directory: {boundary}")
    resolved_root = root.resolve(strict=False)
    for raw in artifacts:
        candidate = _absolute(raw)
        if candidate == root:
            raise LifecycleError("refusing to remove the artifact boundary itself")
        if not _within(candidate, root):
            raise LifecycleError(f"artifact must stay within artifact boundary: {raw}")
        if candidate.is_symlink():
            candidate.unlink()
            continue
        resolved = candidate.resolve(strict=False)
        if not _within(resolved, resolved_root):
            raise LifecycleError(f"artifact must stay within artifact boundary: {raw}")
        if not candidate.exists():
            continue
        if candidate.is_dir():
            shutil.rmtree(candidate)
        else:
            candidate.unlink()


def source_manifest(root: Path, source_files: Iterable[Path]) -> dict[str, str]:
    """Hash explicit regular source files as sorted project-relative paths."""
    source_root = _absolute(root)
    if source_root.is_symlink() or not source_root.is_dir():
        raise LifecycleError(f"source root must be a regular directory: {root}")
    resolved_root = source_root.resolve()
    manifest: dict[str, str] = {}
    for raw in source_files:
        lexical = _absolute(raw)
        if lexical.is_symlink():
            raise LifecycleError(f"source file may not be a symbolic link: {raw}")
        resolved = lexical.resolve(strict=False)
        if not _within(resolved, resolved_root):
            raise LifecycleError(f"source file must stay within source root: {raw}")
        if not resolved.is_file():
            raise LifecycleError(f"source file must be a regular file: {raw}")
        relative = resolved.relative_to(resolved_root).as_posix()
        if relative in manifest:
            raise LifecycleError(f"duplicate source file: {relative}")
        manifest[relative] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return dict(sorted(manifest.items()))
