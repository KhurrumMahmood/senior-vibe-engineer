#!/usr/bin/env python3
"""Cross-agent `.engineering/` state home resolver (ADR 0021).

`.engineering/` is the toolkit's agent-neutral, per-project **state home** —
the *state* analog of the cross-tool instruction mirror (`CLAUDE.md` /
`AGENTS.md` / `.augment/`). All agents read and write it; shared state must
not live under any one agent's folder (`.claude/` is Claude-specific — putting
shared state there is the category error ADR 0021 calls out).

Two zones, split by commit policy:

  - **Committed zone** — the top level of `.engineering/` (tracked in git):
    durable team knowledge that should travel with the repo. Machine state
    (`project-state.json`, `manifest.json`) sits here; human-readable
    convention / capability descriptors live under `.engineering/docs/`.
  - **Gitignored zone** — `.engineering/local/`: per-run scratch that must not
    be committed. The toolkit ships the ignore rule (a `.gitignore` inside
    `.engineering/` that ignores `local/` and nothing else), so adoption is
    automatic.

This module is the single resolver every reader goes through, so the folder
layout and the transitional legacy-location fallbacks live in exactly one
place. Stdlib-only — the whole skill toolchain stays dependency-free.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ENGINEERING_DIRNAME = ".engineering"
MANIFEST_FILENAME = "manifest.json"
DOCS_SUBDIR = "docs"
LOCAL_SUBDIR = "local"  # the only gitignored path inside .engineering/

# Schema version of the .engineering/ layout. Readers check it; a mismatch is
# the signal to run a documented migration, never a crash (ADR 0021).
MANIFEST_VERSION = 1

# One-time legacy-fallback warnings, keyed by the canonical path we *wanted*.
_warned: set[str] = set()


def engineering_dir(root: Path | str) -> Path:
    """`<root>/.engineering`."""
    return Path(root) / ENGINEERING_DIRNAME


def manifest_path(root: Path | str) -> Path:
    """`<root>/.engineering/manifest.json`."""
    return engineering_dir(root) / MANIFEST_FILENAME


def read_manifest(root: Path | str) -> dict | None:
    """Parsed manifest dict, or None when absent/unreadable/not-an-object."""
    path = manifest_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def check_version(root: Path | str) -> tuple[bool, int | None]:
    """Return (ok, found_version).

    `ok` is True when the manifest is absent (un-migrated clone — fine) or its
    version equals MANIFEST_VERSION. A present-but-mismatched version returns
    (False, found) so the caller can trigger a documented migration rather than
    silently mis-reading a future layout.
    """
    manifest = read_manifest(root)
    if manifest is None:
        return True, None
    found = manifest.get("version")
    return (found == MANIFEST_VERSION), found


# --- Skill activation (which skills apply to this project) ------------------
# Activation answers "does this skill apply to THIS repo at all?" — pure
# applicability, declared per project in the manifest's `skills` block. The
# normal case is "most skills apply": `default: active` with a short opt-out
# list (`inactive`), each entry carrying a human reason ("no frontend", "no
# route surface", ...). This is orthogonal to ADR 0020 maturity x stakes
# rung-gating (project-state.json), which selects which *standards* inside
# find-standard-gaps fire — not whether a whole skill runs. An absent manifest
# or absent `skills` block means the un-adapted default: every skill applies.


def skill_activation(root: Path | str) -> dict:
    """Normalized `skills` activation block.

    Always returns ``{"default": "active"|"inactive",
    "inactive": {name: reason}, "active": {name: reason}}``. Tolerates a missing
    manifest, a missing/non-dict `skills` block, and list-or-dict opt-out
    values (a bare list is read as names with no recorded reason).
    """
    block = (read_manifest(root) or {}).get("skills")
    if not isinstance(block, dict):
        block = {}
    default = block.get("default")
    if default not in ("active", "inactive"):
        default = "active"

    def _reasons(value: object) -> dict:
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        if isinstance(value, list):
            return {str(item): "" for item in value}
        return {}

    return {
        "default": default,
        "inactive": _reasons(block.get("inactive")),
        "active": _reasons(block.get("active")),
    }


def is_skill_active(root: Path | str, skill_name: str) -> bool:
    """Whether ``skill_name`` applies to the project at ``root``.

    Default-active model (normal case): active unless listed in
    ``skills.inactive``. Flipped allowlist (``skills.default == "inactive"``):
    active only when listed in ``skills.active``. An absent manifest => active.
    """
    activation = skill_activation(root)
    if activation["default"] == "inactive":
        return skill_name in activation["active"]
    return skill_name not in activation["inactive"]


def inactive_reason(root: Path | str, skill_name: str) -> str | None:
    """Recorded reason ``skill_name`` is inactive, or None.

    None when the skill is active, or inactive without a recorded reason.
    """
    if is_skill_active(root, skill_name):
        return None
    return skill_activation(root)["inactive"].get(skill_name) or None


def _warn_once(message: str, key: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(f"WARNING: {message}", file=sys.stderr)


def resolve(
    root: Path | str, *relparts: str, legacy: Path | str | None = None
) -> tuple[Path, bool]:
    """Resolve a committed-zone path under `.engineering/`.

    Returns ``(path, used_legacy)``. Prefers ``.engineering/<relparts>``. If
    that does not exist and ``legacy`` is given and does exist, returns the
    legacy path and warns once (ADR 0021's transitional fallback). Otherwise
    returns the canonical `.engineering/` path even when absent, so callers get
    one consistent location to test or create.
    """
    canonical = engineering_dir(root).joinpath(*relparts)
    if canonical.exists():
        return canonical, False
    if legacy is not None:
        legacy_path = Path(legacy)
        if legacy_path.exists():
            _warn_once(
                f"reading {legacy_path.name} from its legacy location "
                f"{legacy_path}; move it to {canonical} (ADR 0021).",
                key=str(canonical),
            )
            return legacy_path, True
    return canonical, False


def docs_path(
    root: Path | str, name: str, *, legacy_claude_docs: bool = False
) -> tuple[Path, bool]:
    """Resolve a human-readable descriptor under `.engineering/docs/<name>`.

    With ``legacy_claude_docs=True``, falls back to the pre-migration
    ``.claude/docs/<name>`` (warning once) so an un-migrated host still works.
    """
    legacy = (Path(root) / ".claude" / "docs" / name) if legacy_claude_docs else None
    return resolve(root, DOCS_SUBDIR, name, legacy=legacy)
