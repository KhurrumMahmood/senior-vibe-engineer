"""scope.json sidecar helper — what paths an expensive artifact covered.

A skill that produces an expensive report writes a `scope.json` sidecar
into its artifact directory declaring the repo-relative paths the
artifact's conclusions depend on. The status projection then computes
input-drift staleness: commits touching a scoped path after the sidecar
was written mark the artifact stale. Cheap detector reports are exempt —
they re-run instead of being tracked (ADR 0036 tier rule).

Strictly additive: nothing about the artifact's own format changes.
Named `artifact_scope` (not `scope`) — `.claude/skills/_common/scope.py`
already owns the per-skill scan-scope loader and the two are unrelated.

Source decision: `core:status-projection-schema` (ADR 0037).
"""
# spec:status-projection-and-presentation::IM-4
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIDECAR_NAME = "scope.json"
SIDECAR_VERSION = 1


def write_scope(artifact_dir: Path, paths: list[str], note: str | None = None) -> Path:
    """Write the sidecar next to an artifact; returns the sidecar path.

    `paths` are repo-relative POSIX paths (files or directory prefixes).
    """
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": SIDECAR_VERSION,
        "paths": sorted({str(p) for p in paths}),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        payload["note"] = note
    sidecar = artifact_dir / SIDECAR_NAME
    sidecar.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return sidecar


def read_scope(artifact_dir: Path) -> dict[str, Any] | None:
    """Read a sidecar; None when absent or unreadable (absent is normal)."""
    sidecar = Path(artifact_dir) / SIDECAR_NAME
    if not sidecar.is_file():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None  # noqa: silent-catch: unreadable sidecar = untracked artifact, not an error path
    if not isinstance(payload, dict) or not isinstance(payload.get("paths"), list):
        return None
    return payload
