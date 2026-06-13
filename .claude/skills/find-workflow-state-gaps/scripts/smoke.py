#!/usr/bin/env python3
"""Smoke-test find-workflow-state-gaps fixtures."""
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
                ".",
                "--no-workflow-duplication",
                "--output",
                str(output),
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


def _fixture_project(root: Path, body: str) -> Path:
    project = root / "project"
    templates = project / "templates"
    templates.mkdir(parents=True)
    (templates / "workflow.html").write_text(body, encoding="utf-8")
    return project


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        good_project = _fixture_project(
            tmp_root / "good",
            """
            <div class="loading spinner">Loading export</div>
            <div class="empty">No results</div>
            <div class="error">Failed job</div>
            <button disabled>Retry</button>
            <div class="mobile responsive grid-cols">Status</div>
            <script>fetch('/workflow/export')</script>
            """,
        )
        bad_project = _fixture_project(
            tmp_root / "bad",
            """
            <button>Run export</button>
            <div>Job status</div>
            <script>fetch('/workflow/export')</script>
            """,
        )
        good = _run(good_project)
        bad = _run(bad_project)
    if good:
        print(f"expected clean good fixtures, got {len(good)} findings", file=sys.stderr)
        return 1
    patterns = {record["pattern"] for record in bad}
    expected = {
        "missing_loading_state",
        "missing_empty_state",
        "missing_failure_state",
        "missing_recovery_state",
        "missing_disabled_state",
        "missing_mobile_state",
    }
    missing = expected - patterns
    if missing:
        print(f"missing expected patterns: {sorted(missing)}", file=sys.stderr)
        return 1
    print("find-workflow-state-gaps smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
