#!/usr/bin/env python3
"""Self-contained filesystem and report helpers for find-comment-drift."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "migrations",
    "node_modules",
    "staticfiles",
    "venv",
}


def resolve_project_root(explicit: Path | None = None) -> Path:
    """Use the explicit host root, git toplevel, or current directory."""
    if explicit is not None:
        return explicit.resolve()
    cwd = Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return cwd.resolve()
    root = result.stdout.strip()
    return Path(root).resolve() if root else cwd.resolve()


def iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Return supported files below ``root`` while skipping generated trees."""
    if not root.exists():
        return []

    root = root.resolve()

    def is_eligible(path: Path) -> bool:
        relative = path.relative_to(root)
        parent_parts = relative.parts[:-1]
        return (
            path.is_file()
            and path.suffix.lower() in suffixes
            and not any(
                part in SKIP_DIRS or part.startswith(".") for part in parent_parts
            )
        )

    return sorted(
        path
        for path in root.rglob("*")
        if is_eligible(path)
    )


def relpath(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"cannot read required detections file {path}: {exc}") from None
    try:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSONL in required detections file {path}: {exc}") from None


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_simple_report(
    title: str, records: list[dict[str, Any]], target: str
) -> tuple[str, dict[str, Any]]:
    buckets: dict[str, int] = {}
    for record in records:
        key = str(record.get("pattern") or record.get("bucket") or "finding")
        buckets[key] = buckets.get(key, 0) + 1

    lines = [f"# {title}", "", f"**Target:** `{target}`", f"**Findings:** {len(records)}", ""]
    if buckets:
        lines.extend(["## Buckets", "", "| Bucket | Count |", "|---|---|"])
        for bucket, count in sorted(buckets.items()):
            lines.append(f"| `{bucket}` | {count} |")
        lines.append("")
    if records:
        lines.extend(["## Findings", ""])
        for index, record in enumerate(records, start=1):
            file = record.get("file", "?")
            line = record.get("lineno", "?")
            pattern = record.get("pattern", record.get("bucket", "finding"))
            summary = record.get("summary") or record.get("message") or record.get("evidence") or ""
            lines.extend([f"### {index}. `{pattern}`", "", f"- **Location:** `{file}:{line}`"])
            if summary:
                lines.append(f"- **Evidence:** {summary}")
            recommendation = record.get("recommendation")
            if recommendation:
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")

    return "\n".join(lines), {
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }
