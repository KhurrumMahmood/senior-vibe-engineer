#!/usr/bin/env python3
"""Repository wrapper for the bundled closed-state guard."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "prevent-regression"
    / "scripts"
    / "stringly_status_guard.py"
)


def _load_guard():
    spec = importlib.util.spec_from_file_location("_stringly_status_guard", GUARD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load stringly-status guard from {GUARD_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    return _load_guard().main(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
