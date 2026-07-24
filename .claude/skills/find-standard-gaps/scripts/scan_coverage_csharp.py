#!/usr/bin/env python3
"""Measure C# unresolved call-spelling/if syntax coverage."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_csharp"))
from csharp_consumers import standards_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(standards_main())
