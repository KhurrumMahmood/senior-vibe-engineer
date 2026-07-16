#!/usr/bin/env python3
"""Validate evidence-backed completion-floor claims against the registry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from _lib.capability_registry import load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path, help="YAML or JSON completion-claims document")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path.cwd(),
        help="Root for fixture commands and attested paths (default: cwd)",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Validate structure/hashes only; cannot be used as promotion evidence",
    )
    args = parser.parse_args(argv)
    try:
        payload = yaml.safe_load(args.claims.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("error: claims document must be a mapping", file=sys.stderr)
        return 2
    errors = load_registry().validate_completion_claims(
        payload,
        evidence_root=args.evidence_root,
        execute_evidence=not args.no_execute,
    )
    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, indent=2))
        return 1
    if args.no_execute:
        print(
            json.dumps(
                {
                    "status": "structural-only",
                    "errors": [],
                    "promotable": False,
                },
                indent=2,
            )
        )
        return 3
    print(json.dumps({"status": "pass", "errors": []}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
