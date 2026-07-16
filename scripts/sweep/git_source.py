"""Git-derived source provenance for sweep manifests and verification."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


_UNTRACKED_MARKER = b"\0sweep-untracked-v1\0"


def _git(root: Path, *args: str) -> bytes:
    env = dict(os.environ)
    env.update({"GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise ValueError(f"cannot inspect Git source: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            f"cannot inspect Git source with git {' '.join(args)}"
            + (f": {detail}" if detail else "")
        )
    return completed.stdout


def _framed_untracked(root: Path, raw_paths: bytes) -> bytes:
    paths = sorted(path for path in raw_paths.split(b"\0") if path)
    if not paths:
        return b""
    framed = bytearray(_UNTRACKED_MARKER)
    for raw_path in paths:
        relative = os.fsdecode(raw_path)
        candidate = root / relative
        if candidate.is_symlink():
            kind = b"L"
            payload = os.fsencode(os.readlink(candidate))
        elif candidate.is_file():
            kind = b"F"
            try:
                payload = candidate.read_bytes()
            except OSError as exc:
                raise ValueError(f"cannot read untracked source {relative}: {exc}") from exc
        else:
            raise ValueError(f"untracked source is not a regular file or symlink: {relative}")
        framed.extend(len(raw_path).to_bytes(8, "big"))
        framed.extend(raw_path)
        framed.extend(kind)
        framed.extend(len(payload).to_bytes(8, "big"))
        framed.extend(payload)
    return bytes(framed)


def capture_git_source(root: Path | str) -> dict[str, object]:
    """Derive manifest source identity from one exact Git worktree snapshot.

    For tracked-only changes the dirty digest remains exactly the SHA-256 of
    ``git diff --binary HEAD --``. Untracked, non-ignored files extend that
    byte stream using deterministic path/type/content framing so they cannot be
    consumed by a detector without changing source provenance.
    """
    worktree = Path(root).resolve()
    if not worktree.is_dir():
        raise ValueError(f"scan root is not a directory: {worktree}")

    def snapshot() -> tuple[str, bytes]:
        raw_revision = _git(
            worktree, "rev-parse", "--verify", "HEAD^{commit}"
        ).decode("ascii").strip()
        tracked = _git(worktree, "diff", "--binary", "HEAD", "--")
        untracked_paths = _git(
            worktree, "ls-files", "--others", "--exclude-standard", "-z"
        )
        return raw_revision, tracked + _framed_untracked(worktree, untracked_paths)

    revision, dirty_bytes = snapshot()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("Git HEAD did not resolve to a lowercase 40-character commit id")
    if snapshot() != (revision, dirty_bytes):
        raise ValueError("Git source changed while provenance was being captured")
    return {
        "revision": revision,
        "dirty": bool(dirty_bytes),
        "dirty_state_hash": hashlib.sha256(dirty_bytes).hexdigest(),
    }
