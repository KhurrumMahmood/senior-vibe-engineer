#!/usr/bin/env python3
"""Report bounded Kotlin source branch hotspots."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_kotlin"))
from kotlin_consumers import complexity_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(complexity_main())
