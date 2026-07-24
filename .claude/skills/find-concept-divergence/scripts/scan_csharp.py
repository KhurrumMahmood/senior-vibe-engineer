#!/usr/bin/env python3
"""Scan C# identifier tokens for bounded concept divergence."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_csharp"))
from csharp_consumers import concept_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(concept_main())
