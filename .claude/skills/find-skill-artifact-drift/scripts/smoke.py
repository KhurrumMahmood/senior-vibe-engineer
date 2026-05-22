#!/usr/bin/env python3
"""Fixture smoke test for find-skill-artifact-drift.

Asserts three contracts against the good/bad fixture skills:
1. every detector band fires on the bad fixture,
2. the good fixture stays clean, and
3. ``--gate`` (the Band-A pre-commit subset) exits non-zero on the bad
   fixture and zero on the good one.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
FIXTURES = SKILL_DIR / "fixtures"
DETECT = SCRIPT_DIR / "detect.py"

EXPECTED_BAD_PATTERNS = {
    "missing_script_ref",
    "missing_documented_flag",
    "bash_tool_undeclared",
    "orphan_script",
    "evidence_contract_unbacked",
    "not_for_tooltell_conflict",
}
BAND_A = {"missing_script_ref", "missing_documented_flag", "bash_tool_undeclared"}


def run_detect(skills_dir: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "detections.jsonl"
        subprocess.run(
            [sys.executable, str(DETECT), "--skills-dir", str(skills_dir), "--output", str(output)],
            check=True,
            text=True,
            capture_output=True,
        )
        return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]


def gate_returncode(skills_dir: Path) -> int:
    return subprocess.run(
        [sys.executable, str(DETECT), "--skills-dir", str(skills_dir), "--gate"],
        text=True,
        capture_output=True,
    ).returncode


def main() -> int:
    bad = run_detect(FIXTURES / "bad")
    bad_patterns = {record["pattern"] for record in bad}
    missing = EXPECTED_BAD_PATTERNS - bad_patterns
    if missing:
        print(f"missing expected bad fixture patterns: {sorted(missing)}", file=sys.stderr)
        return 1
    for record in bad:
        expected_band = "A" if record["pattern"] in BAND_A else "B"
        if record["band"] != expected_band:
            print(f"band mismatch for {record['pattern']}: {record['band']} != {expected_band}", file=sys.stderr)
            return 1

    good = run_detect(FIXTURES / "good")
    if good:
        print("good fixtures produced unexpected findings:", file=sys.stderr)
        for record in good:
            print(json.dumps(record, sort_keys=True), file=sys.stderr)
        return 1

    if gate_returncode(FIXTURES / "bad") != 1:
        print("--gate should exit 1 on the bad fixture", file=sys.stderr)
        return 1
    if gate_returncode(FIXTURES / "good") != 0:
        print("--gate should exit 0 on the good fixture", file=sys.stderr)
        return 1

    print(f"OK - {len(bad)} bad fixture findings across {len(EXPECTED_BAD_PATTERNS)} bands, good clean, gate honored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
