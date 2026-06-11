#!/usr/bin/env python3
"""Run find-complexity-hotspots and write the standard report directory."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.dont_write_bytecode = True

from detect import detect  # noqa: E402
from product_health import write_scan_outputs  # noqa: E402


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files, directories, or globs to scan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--max-findings", type=_positive_int, default=80)
    parser.add_argument("--skip-effectiveness-log", action="store_true")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    target = " ".join(args.paths)
    records = detect(
        project_root,
        args.paths,
        include_tests=args.include_tests,
        max_findings=args.max_findings,
    )
    report_dir = write_scan_outputs(
        "find-complexity-hotspots",
        "Complexity hotspot audit",
        records,
        target,
        project_root,
        skip_effectiveness_log=args.skip_effectiveness_log,
    )
    print(f"wrote {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
