"""Minimal `.engineering/` state-home resolver bundled for this skill.

The scanner only needs the canonical project-state location plus its legacy
fallback. Keep that boundary local so a stock installed skill has no sibling
runtime dependency.
"""
from __future__ import annotations

import sys
from pathlib import Path


ENGINEERING_DIRNAME = ".engineering"
_warned: set[str] = set()


def engineering_dir(root: Path | str) -> Path:
    """Return the project-local `.engineering` state directory."""
    return Path(root) / ENGINEERING_DIRNAME


def resolve(
    root: Path | str, *relparts: str, legacy: Path | str | None = None
) -> tuple[Path, bool]:
    """Prefer `.engineering/<relparts>`, with a warned legacy fallback."""
    canonical = engineering_dir(root).joinpath(*relparts)
    if canonical.exists():
        return canonical, False
    if legacy is not None:
        legacy_path = Path(legacy)
        if legacy_path.exists():
            key = str(canonical)
            if key not in _warned:
                _warned.add(key)
                print(
                    f"WARNING: reading {legacy_path.name} from its legacy location "
                    f"{legacy_path}; move it to {canonical} (ADR 0021).",
                    file=sys.stderr,
                )
            return legacy_path, True
    return canonical, False
