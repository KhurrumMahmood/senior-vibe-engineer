#!/usr/bin/env python3
"""Fixture smoke test for find-complexity-hotspots."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DETECT = SCRIPT_DIR / "detect.py"
FIXTURES = SKILL_DIR / "fixtures"

EXPECTED_BAD = {
    "django-query-in-loop",
    "membership-scan-in-loop",
    "nested-loop",
    "sort-in-loop",
    "repeated-scan-in-loop",
    "high-branch-function",
}


def run_detect(*paths: Path) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "detections.jsonl"
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(DETECT),
                "--output",
                str(output),
                "--max-findings",
                "200",
                *(str(path) for path in paths),
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        try:
            text = output.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        return [
            json.loads(line)
            for line in text.splitlines()
            if line.strip()
        ]


def main() -> int:
    good = run_detect(FIXTURES / "good")
    if good:
        print("good fixture produced unexpected findings:", file=sys.stderr)
        for record in good:
            print(json.dumps(record, sort_keys=True), file=sys.stderr)
        return 1

    bad = run_detect(FIXTURES / "bad")
    patterns = {str(record["pattern"]) for record in bad}
    missing = EXPECTED_BAD - patterns
    if missing:
        print(f"missing expected patterns: {sorted(missing)}", file=sys.stderr)
        print(f"got patterns: {sorted(patterns)}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "detections.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(DETECT),
                "--output",
                str(output),
                "--max-findings",
                "0",
                str(FIXTURES / "bad"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode == 0 or "must be >= 1" not in result.stderr:
        print("--max-findings 0 should fail with a clear validation error", file=sys.stderr)
        return 1

    print(f"OK - {len(bad)} bad fixture findings, good fixture clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
