#!/usr/bin/env python3
"""Produce pinned Kotlin/JVM resolved signature/body-shape review leads."""

from __future__ import annotations
import importlib.util
import sys
from pathlib import Path


def _main() -> int:
    path = next(
        (
            parent / "_kotlin-semantic" / "consume_kotlin_facts.py"
            for parent in Path(__file__).resolve().parents
            if (parent / "_kotlin-semantic" / "consume_kotlin_facts.py").is_file()
        ),
        None,
    )
    if path is None:
        raise RuntimeError("assembled Kotlin semantic consumer is missing")
    spec = importlib.util.spec_from_file_location("kotlin_duplication_consumer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Kotlin semantic consumer cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main("duplication")


if __name__ == "__main__":
    raise SystemExit(_main())
