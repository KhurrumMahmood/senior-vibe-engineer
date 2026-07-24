#!/usr/bin/env python3
"""Produce a bounded C# 14 / .NET 10 host adapter from copied facts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_csharp"))
from csharp_consumers import adapt_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(adapt_main())
