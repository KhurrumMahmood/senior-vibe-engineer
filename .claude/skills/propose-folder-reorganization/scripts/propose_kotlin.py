#!/usr/bin/env python3
"""Render one accepted Kotlin/JVM folder proposal without redetection."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _implementation():
    candidates = [
        parent / "_kotlin-semantic" / "kotlin_structure_proposals.py"
        for parent in Path(__file__).resolve().parents
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Kotlin structure-proposal helper is missing")
    spec = importlib.util.spec_from_file_location("kotlin_folder_proposal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Kotlin structure-proposal helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(_implementation().main("propose-folder-reorganization"))
