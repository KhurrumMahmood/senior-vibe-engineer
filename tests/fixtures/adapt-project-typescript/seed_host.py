#!/usr/bin/env python3
"""Materialize the locked TypeScript-only adapt-project fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


FIXTURE = Path(__file__).with_name("fixture.json")
PACKAGE_LOCK = Path(__file__).with_name("package-lock.json")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the adapt-project TypeScript fixture")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-files", type=int, default=201)
    parser.add_argument("--excluded-files", type=int, default=0)
    args = parser.parse_args(argv)
    if args.source_files < 0 or args.excluded_files < 0:
        parser.error("file counts must be non-negative")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    root = args.destination
    write(root / "package.json", json.dumps(fixture["package_json"], indent=2) + "\n")
    write(root / "package-lock.json", PACKAGE_LOCK.read_text(encoding="utf-8"))
    write(root / "tsconfig.json", json.dumps(fixture["tsconfig"], indent=2) + "\n")
    write(root / "tests" / "adapter.test.mjs", "import test from 'node:test';\ntest('fixture', () => {});\n")
    for index in range(args.source_files):
        extension = ".tsx" if index % 2 else ".ts"
        write(root / "src" / "features" / f"source_{index:03d}{extension}", fixture["source_seed"][extension[1:]])
    for tree in fixture["excluded_trees"]:
        for index in range(args.excluded_files):
            write(root / tree / f"ignored_{index:03d}.tsx", fixture["source_seed"]["tsx"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
