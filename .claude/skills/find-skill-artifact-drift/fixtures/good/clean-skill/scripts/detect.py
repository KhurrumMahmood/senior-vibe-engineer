#!/usr/bin/env python3
"""Fixture detector for clean-skill; defines the flag its SKILL.md documents."""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
