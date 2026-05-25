#!/usr/bin/env python3
"""Fixture smoke test for find-comment-drift."""
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
    "detached_section_banner",
    "obvious_narration_comment",
    "missing_public_class_docstring",
    "thin_public_class_docstring",
    "stale_comment_term",
    "jsdoc_candidate",
    "thin_jsdoc_comment",
    "noisy_html_comment",
    "malformed_doc_reference",
}


def run_detect(*paths: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "detections.jsonl"
        subprocess.run(
            [sys.executable, str(DETECT), "--output", str(output), *(str(path) for path in paths)],
            check=True,
            text=True,
            capture_output=True,
        )
        try:
            text = output.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> int:
    bad = run_detect(FIXTURES / "bad")
    bad_patterns = {record["pattern"] for record in bad}
    missing = EXPECTED_BAD_PATTERNS - bad_patterns
    if missing:
        print(f"missing expected bad fixture patterns: {sorted(missing)}", file=sys.stderr)
        return 1

    good = run_detect(FIXTURES / "good")
    if good:
        print("good fixtures produced unexpected findings:", file=sys.stderr)
        for record in good:
            print(json.dumps(record, sort_keys=True), file=sys.stderr)
        return 1

    print(f"OK - {len(bad)} bad fixture findings, good fixtures clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
