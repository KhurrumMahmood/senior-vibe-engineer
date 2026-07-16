"""Mandatory profile-derived perimeter audit boundary for host adaptation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


# spec:portable-host-profile-routing::IM-4
def run_perimeter_audit(
    project_root: Path,
    host_profile_path: Path,
    scan_dir: Path,
) -> dict[str, Any]:
    """Run the mandatory profile-derived perimeter audit and return its payload."""
    perimeter_json = scan_dir / "perimeter.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / ".claude" / "skills" / "find-perimeter-gaps" / "scripts" / "scan.py"),
            "--project-root",
            str(project_root),
            "--skills-root",
            str(REPO_ROOT / ".claude" / "skills"),
            "--host-profile",
            str(host_profile_path),
            "--output",
            str(perimeter_json),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    (scan_dir / "perimeter.md").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            "mandatory perimeter audit failed: "
            f"exit={completed.returncode} stderr={completed.stderr.strip()}"
        )
    if not perimeter_json.is_file() or not (scan_dir / "perimeter.md").is_file():
        raise RuntimeError("mandatory perimeter audit did not produce required artifacts")
    try:
        payload = json.loads(perimeter_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"mandatory perimeter audit produced invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("gaps"), list):
        raise RuntimeError("mandatory perimeter audit produced an invalid result shape")
    return payload


def validate_perimeter_artifacts(
    scan_dir: Path,
    host_profile: dict[str, Any],
    returned: object,
) -> dict[str, Any]:
    """Revalidate mandatory audit artifacts at the adaptation success boundary."""
    perimeter_json = scan_dir / "perimeter.json"
    perimeter_report = scan_dir / "perimeter.md"
    if not perimeter_json.is_file() or not perimeter_report.is_file():
        raise RuntimeError("mandatory perimeter audit did not produce required artifacts")
    try:
        payload = json.loads(perimeter_json.read_text(encoding="utf-8"))
        report_text = perimeter_report.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"mandatory perimeter audit produced invalid artifacts: {exc}") from exc
    if not report_text.strip():
        raise RuntimeError("mandatory perimeter audit produced an empty human report")
    if not isinstance(returned, dict) or returned != payload:
        raise RuntimeError("mandatory perimeter audit return does not match its JSON artifact")
    required_lists = ("profile_exclusions", "accepted_exclusions", "detectors", "cells", "gaps")
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 2
        or payload.get("coverage_mode") != "executable-evidence"
        or any(not isinstance(payload.get(field), list) for field in required_lists)
    ):
        raise RuntimeError("mandatory perimeter audit produced an invalid result shape")
    if payload.get("host_profile_sha256") != host_profile.get("profile_sha256"):
        raise RuntimeError("mandatory perimeter audit is not bound to this host profile")
    if payload.get("profile_exclusions") != host_profile.get("exclusions"):
        raise RuntimeError("mandatory perimeter audit changed the host profile exclusions")
    if any(not isinstance(item, dict) for field in required_lists for item in payload[field]):
        raise RuntimeError("mandatory perimeter audit result rows must be mappings")
    if any(
        not isinstance(item.get("root"), str)
        or not isinstance(item.get("language"), str)
        or not isinstance(item.get("reason"), str)
        or not item["reason"].strip()
        for item in payload["accepted_exclusions"]
    ):
        raise RuntimeError("mandatory perimeter audit accepted exclusions require reasons")
    return payload
