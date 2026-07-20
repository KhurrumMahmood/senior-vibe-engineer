#!/usr/bin/env python3
"""Run find-complexity-hotspots and write the standard report directory."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.dont_write_bytecode = True

from detect import TypeScriptExtractionError, detect  # noqa: E402


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def _utc_scan_id(prefix: str = "scan") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def _write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def _write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_simple_report(
    title: str,
    records: list[dict[str, Any]],
    target: str,
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
            lines.append(f"### {index}. `{pattern}`")
            lines.append("")
            lines.append(f"- **Location:** `{file}:{line}`")
            if summary:
                lines.append(f"- **Evidence:** {summary}")
            language = record.get("language")
            analyzer = record.get("analyzer")
            if language and analyzer:
                lines.append(f"- **Analyzer:** `{language}` via `{analyzer}`")
            recommendation = record.get("recommendation")
            if recommendation:
                lines.append(f"- **Recommendation:** {recommendation}")
            lines.append("")

    return "\n".join(lines), {
        "summary": {"findings_total": len(records), "buckets": buckets},
        "findings": records,
    }


def _write_scan_outputs(
    records: list[dict[str, Any]],
    target: str,
    project_root: Path,
) -> Path:
    scan_id = _utc_scan_id("scan")
    report_dir = project_root / "reports" / "find-complexity-hotspots" / scan_id
    _write_jsonl(records, report_dir / "detections.jsonl")
    markdown, findings = _render_simple_report("Complexity hotspot audit", records, target)
    findings["skill"] = "find-complexity-hotspots"
    findings["scan_id"] = scan_id
    findings["target"] = target
    (report_dir / "report.md").write_text(markdown + "\n", encoding="utf-8")
    _write_json(findings, report_dir / "findings.json")

    latest = report_dir.parent / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(scan_id)
    return report_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files, directories, or globs to scan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--max-findings", type=_positive_int, default=80)
    parser.add_argument("--skip-effectiveness-log", action="store_true")
    parser.add_argument(
        "--language",
        action="append",
        choices=("javascript", "python", "typescript"),
        default=[],
        help="Restrict scanning to one or more supported languages.",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    target = " ".join(args.paths)
    try:
        records = detect(
            project_root,
            args.paths,
            include_tests=args.include_tests,
            max_findings=args.max_findings,
            languages=set(args.language) or None,
        )
    except TypeScriptExtractionError as exc:
        print(f"[find-complexity-hotspots] ERROR: {exc}", file=sys.stderr)
        return 2
    report_dir = _write_scan_outputs(records, target, project_root)
    print(f"wrote {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
