#!/usr/bin/env python3
"""Smoke-test find-contract-drift fixtures."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[1]


def _run(project: Path) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "detections.jsonl"
        subprocess.run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "detect.py"),
                "--project-root",
                str(project),
                "--output",
                str(output),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        try:
            text = output.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> int:
    good = _run(SKILL_ROOT / "fixtures" / "good")
    bad = _run(SKILL_ROOT / "fixtures" / "bad")
    if good:
        print(f"expected clean good fixtures, got {len(good)} findings", file=sys.stderr)
        return 1
    patterns = {record["pattern"] for record in bad}
    expected = {
        "implicit_template_global",
        "missing_js_export",
        "missing_endpoint_key",
        "missing_dom_id",
        "missing_data_selector",
    }
    missing = expected - patterns
    if missing:
        print(f"missing expected patterns: {sorted(missing)}", file=sys.stderr)
        return 1
    print("find-contract-drift smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
