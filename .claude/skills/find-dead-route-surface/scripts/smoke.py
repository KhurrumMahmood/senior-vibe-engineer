#!/usr/bin/env python3
"""Smoke-test find-dead-route-surface fixtures."""
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
            capture_output=True,
            text=True,
            check=True,
        )
        return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    good = _run(SKILL_ROOT / "fixtures" / "good")
    bad = _run(SKILL_ROOT / "fixtures" / "bad")
    if good:
        print(f"expected clean good fixtures, got {len(good)} findings", file=sys.stderr)
        return 1
    patterns = {record["pattern"] for record in bad}
    expected = {
        "legacy_prototype_route",
        "route_template_missing",
        "unreferenced_template_surface",
        "missing_static_js",
        "unloaded_site_static_js",
    }
    missing = expected - patterns
    if missing:
        print(f"missing expected patterns: {sorted(missing)}", file=sys.stderr)
        return 1
    print("find-dead-route-surface smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
