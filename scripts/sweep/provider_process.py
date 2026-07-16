#!/usr/bin/env python3
"""Standalone child-process entry point for parser-backed sweep providers."""
from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sweep.ecosystem import provider_process_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(provider_process_main())
