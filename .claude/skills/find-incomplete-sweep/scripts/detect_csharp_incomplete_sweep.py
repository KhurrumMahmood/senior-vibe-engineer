#!/usr/bin/env python3
"""Produce exact-Roslyn C# optional-constructor-argument sweep leads."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _main() -> int:
    sys.dont_write_bytecode = True
    path = next(
        (
            parent / "_csharp-semantic" / "consume_csharp_facts.py"
            for parent in Path(__file__).resolve().parents
            if (parent / "_csharp-semantic" / "consume_csharp_facts.py").is_file()
        ),
        None,
    )
    if path is None:
        raise RuntimeError("assembled C# semantic consumer is missing")
    spec = importlib.util.spec_from_file_location("csharp_sweep_consumer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("C# semantic consumer cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main("sweep")


if __name__ == "__main__":
    raise SystemExit(_main())
