#!/usr/bin/env python3
"""Find direct-sibling C++ filename clusters without authorizing moves."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_cpp"))
from cpp_consumers import folder_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(folder_main())
