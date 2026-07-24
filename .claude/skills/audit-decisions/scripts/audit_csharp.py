#!/usr/bin/env python3
"""Audit decision references in C# source comments."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_csharp"))
from csharp_consumers import audit_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(audit_main(None, Path(__file__).with_name("audit.py")))
