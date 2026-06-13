#!/usr/bin/env python3
"""Smoke-test find-test-obligation-drift fixtures."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = Path(__file__).resolve().parents[1]


def _run(project: Path) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        project_copy = Path(tmp) / project.name
        shutil.copytree(project, project_copy)
        descriptor = project_copy / ".engineering" / "docs" / "product-workflows.md"
        descriptor.parent.mkdir(parents=True, exist_ok=True)
        descriptor.write_text(
            "\n".join(
                [
                    "# Product workflow — find-test-obligation-drift fixture",
                    "",
                    "## Targets",
                    "- app/pages/sites",
                    "- static/js/site-config-*.js",
                    "",
                    "## UI template globs",
                    "- app/pages/sites/templates/**/*.html",
                    "",
                    "## UI script globs",
                    "- static/js/site-config-*.js",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        output = Path(tmp) / "detections.jsonl"
        subprocess.run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "detect.py"),
                "--project-root",
                str(project_copy),
                "--output",
                str(output),
                ".",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
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
        "missing_backend_test_obligation",
        "missing_ui_test_obligation",
        "missing_skill_smoke_obligation",
        "missing_quality_tool_test_obligation",
    }
    missing = expected - patterns
    if missing:
        print(f"missing expected patterns: {sorted(missing)}", file=sys.stderr)
        return 1
    print("find-test-obligation-drift smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
