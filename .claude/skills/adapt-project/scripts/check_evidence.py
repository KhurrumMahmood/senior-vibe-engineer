#!/usr/bin/env python3
"""Verify the final artifact closure emitted by the installed adapt-project skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check adapt-project scan evidence")
    parser.add_argument("--scan-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest_path = args.scan_dir / "evidence.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: cannot read evidence manifest: {exc}", file=sys.stderr)
        return 2
    if manifest.get("skill") != "adapt-project":
        print("error: evidence manifest is not for adapt-project", file=sys.stderr)
        return 1
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        print("error: evidence manifest has no evidence mapping", file=sys.stderr)
        return 1
    missing = [name for name in ("adapter", "report") if not isinstance(evidence.get(name), str) or not (args.scan_dir / evidence[name]).is_file()]
    if missing:
        print(f"error: missing required evidence: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not (args.scan_dir / "adapter.json").is_file():
        print("error: missing adapter.json", file=sys.stderr)
        return 1
    print("adapt-project evidence OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
