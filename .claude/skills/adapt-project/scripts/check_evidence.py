#!/usr/bin/env python3
"""Verify the final artifact closure emitted by the installed adapt-project skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def declared_file(scan_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    declared = Path(value)
    if declared.is_absolute() or ".." in declared.parts:
        return None
    try:
        resolved = (scan_dir / declared).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not is_within(resolved, scan_dir) or not resolved.is_file():
        return None
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check adapt-project scan evidence")
    parser.add_argument("--scan-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    scan_dir = args.scan_dir.resolve()
    manifest_path = declared_file(scan_dir, "evidence.json")
    if manifest_path is None:
        print("error: missing or escaped evidence.json", file=sys.stderr)
        return 1
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
    missing = [name for name in ("adapter", "report") if declared_file(scan_dir, evidence.get(name)) is None]
    if missing:
        print(f"error: missing required evidence: {', '.join(missing)}", file=sys.stderr)
        return 1
    if declared_file(scan_dir, "adapter.json") is None:
        print("error: missing or escaped adapter.json", file=sys.stderr)
        return 1
    print("adapt-project evidence OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
