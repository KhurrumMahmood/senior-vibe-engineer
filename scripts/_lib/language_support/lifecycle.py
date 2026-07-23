"""Atomic text output used by the shared source inventory."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class LifecycleError(ValueError):
    """An atomic output request targets an unsafe destination."""


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


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
