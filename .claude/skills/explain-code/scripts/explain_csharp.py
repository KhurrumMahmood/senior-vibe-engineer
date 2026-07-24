#!/usr/bin/env python3
"""Explain bounded C# declaration spelling."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_csharp"))
from csharp_consumers import explain_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(explain_main())
