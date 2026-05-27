#!/usr/bin/env python3
"""Shared helpers for advisory product-health skills."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

# _common siblings; product_topology's import side-effect also adds _common to
# the path, but inserting here makes this module self-sufficient. The scan
# targets / template roots are host-authored data (see workflows.py), not baked
# in — a repo with no descriptor scans nothing rather than another host's flow.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from product_topology import render_simple_report, relpath, utc_scan_id, write_json, write_jsonl  # noqa: E402
from workflows import workflow_targets  # noqa: E402


SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "migrations",
}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def expand_paths(
    project_root: Path,
    raw_paths: Sequence[str | Path] | None,
    suffixes: tuple[str, ...],
    default_targets: Sequence[str] | None = None,
) -> list[Path]:
    # Explicit caller paths win; else the caller's declared default_targets;
    # else the host's workflow scan targets (empty when no descriptor exists).
    if raw_paths:
        targets: Sequence[str | Path] = raw_paths
    elif default_targets is not None:
        targets = default_targets
    else:
        targets = workflow_targets(project_root)
    found: list[Path] = []
    for raw in targets:
        raw_text = str(raw)
        candidates: Iterable[Path]
        if any(char in raw_text for char in "*?[]"):
            candidates = project_root.glob(raw_text)
        else:
            path = Path(raw_text)
            candidates = [path if path.is_absolute() else project_root / path]
        for candidate in candidates:
            if any(part in SKIP_DIRS for part in candidate.parts):
                continue
            if candidate.is_dir():
                for child in candidate.rglob("*"):
                    if any(part in SKIP_DIRS for part in child.parts):
                        continue
                    if child.is_file() and child.suffix in suffixes:
                        found.append(child)
            elif candidate.is_file() and candidate.suffix in suffixes:
                found.append(candidate)
    return sorted(dict.fromkeys(path.resolve() for path in found))


def infer_surface(file: str) -> str:
    if file.startswith("app/pages/sites") or file.startswith("templates/core/site_config"):
        return "sites_template_or_view"
    if file.startswith("app/site_management") or file.startswith("app/api/"):
        return "sites_backend"
    if file.startswith("app/services/sites"):
        return "sites_service"
    if file.startswith("static/js/"):
        return "sites_frontend"
    if file.startswith(".claude/skills"):
        return "skill"
    if file.startswith(".claude/docs") or file.startswith("docs/"):
        return "docs"
    if file.startswith("tests/") or file.startswith("testing/"):
        return "tests"
    return "sites_surface"


def finding(
    pattern: str,
    path: Path | str,
    lineno: int,
    summary: str,
    recommendation: str,
    project_root: Path,
    *,
    confidence: str = "medium",
    surface: str | None = None,
    next_skill: str = "triage-debt",
    guard_candidate: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    file = relpath(path, project_root) if isinstance(path, Path) else path
    record: dict[str, Any] = {
        "pattern": pattern,
        "file": file,
        "lineno": lineno,
        "summary": summary.strip(),
        "recommendation": recommendation.strip(),
        "confidence": confidence,
        "surface": surface or infer_surface(file),
        "next_skill": next_skill,
        "guard_candidate": guard_candidate,
    }
    record.update(extra)
    return record


def normalize_record(
    record: dict[str, Any],
    project_root: Path,
    *,
    default_confidence: str = "medium",
    next_skill: str = "triage-debt",
    guard_candidate: bool = False,
) -> dict[str, Any]:
    file = str(record.get("file", ""))
    return {
        **record,
        "lineno": int(record.get("lineno") or 1),
        "summary": str(record.get("summary") or record.get("evidence") or "").strip(),
        "recommendation": str(record.get("recommendation") or "Review this advisory finding.").strip(),
        "confidence": str(record.get("confidence") or default_confidence),
        "surface": str(record.get("surface") or infer_surface(file)),
        "next_skill": str(record.get("next_skill") or next_skill),
        "guard_candidate": bool(record.get("guard_candidate", guard_candidate)),
    }


def render_report_file(title: str, detections: Path, output: Path, target: str) -> None:
    records: list[dict[str, Any]] = []
    if detections.exists():
        for line in detections.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    markdown, findings = render_simple_report(title, records, target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown + "\n", encoding="utf-8")
    write_json(findings, output.with_name("findings.json"))


def write_scan_outputs(
    skill_name: str,
    title: str,
    records: list[dict[str, Any]],
    target: str,
    project_root: Path,
    *,
    skip_effectiveness_log: bool = False,
) -> Path:
    scan_id = utc_scan_id("scan")
    report_dir = project_root / "reports" / skill_name / scan_id
    detections = report_dir / "detections.jsonl"
    report = report_dir / "report.md"
    findings_json = report_dir / "findings.json"

    write_jsonl(records, detections)
    markdown, findings = render_simple_report(title, records, target)
    findings["skill"] = skill_name
    findings["scan_id"] = scan_id
    findings["target"] = target
    report.write_text(markdown + "\n", encoding="utf-8")
    write_json(findings, findings_json)

    latest = report_dir.parent / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(scan_id)

    if not skip_effectiveness_log:
        buckets = Counter(str(record.get("pattern", "finding")) for record in records)
        subprocess.run(
            [
                sys.executable,
                "scripts/log_effectiveness.py",
                "--skill",
                skill_name,
                "--scan-id",
                scan_id,
                "--target",
                target,
                "--findings-total",
                str(len(records)),
                "--buckets",
                json.dumps(dict(sorted(buckets.items()))),
            ],
            cwd=project_root,
            check=False,
        )
    return report_dir
