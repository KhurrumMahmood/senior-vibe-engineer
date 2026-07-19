#!/usr/bin/env python3
"""Check project-interview's fixed three-artifact evidence manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SKILL = "project-interview"
REQUIRED = ("profile", "profile_summary", "open_questions")


def _rows(scan_dir: Path, evidence: dict[str, Any]) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    for token in REQUIRED:
        declared = evidence.get(token)
        if not isinstance(declared, str) or not declared.strip():
            rows.append({"token": token, "status": "missing_token", "path": None})
            continue
        relative = Path(declared)
        if relative.is_absolute() or ".." in relative.parts:
            rows.append({"token": token, "status": "unsafe_path", "path": declared})
            continue
        candidate = (scan_dir / relative).resolve()
        try:
            candidate.relative_to(scan_dir.resolve())
        except ValueError:
            rows.append({"token": token, "status": "unsafe_path", "path": declared})
            continue
        status = "ok" if candidate.is_file() else "missing_file"
        rows.append({"token": token, "status": status, "path": declared})
    return rows


def _render(scan_dir: Path, rows: list[dict[str, str | None]]) -> str:
    lines = [f"Evidence gate for /{SKILL} on {scan_dir}:"]
    for row in rows:
        marker = "[ok]" if row["status"] == "ok" else "[FAIL]"
        if row["status"] == "ok":
            lines.append(f"  {marker} {row['token']} -> {row['path']}")
        elif row["status"] == "missing_token":
            lines.append(f"  {marker} {row['token']} -> MISSING (no path declared in manifest)")
        elif row["status"] == "unsafe_path":
            lines.append(f"  {marker} {row['token']} -> UNSAFE path {row['path']}")
        else:
            lines.append(f"  {marker} {row['token']} -> DECLARED but file not found at {row['path']}")
    ok_total = sum(row["status"] == "ok" for row in rows)
    status = "OK" if ok_total == len(REQUIRED) else "FAIL"
    lines.extend(["", f"{status}: {ok_total}/{len(REQUIRED)} required evidence shapes present."])
    return "\n".join(lines)


def check(scan_dir: Path) -> int:
    scan_dir = scan_dir.resolve()
    if not scan_dir.is_dir():
        print(f"error: scan-dir not found: {scan_dir}", file=sys.stderr)
        return 2
    manifest_path = scan_dir / "evidence.json"
    if not manifest_path.is_file():
        print(f"Evidence gate for /{SKILL} on {scan_dir}:")
        print(f"  [FAIL] no manifest found at {manifest_path}")
        print(f"  Required tokens: {', '.join(REQUIRED)}")
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: malformed manifest at {manifest_path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print(f"error: manifest at {manifest_path} must be a JSON object", file=sys.stderr)
        return 2
    if manifest.get("skill") != SKILL:
        print(f"error: evidence manifest skill must be {SKILL}", file=sys.stderr)
        return 2
    evidence = manifest.get("evidence")
    rows = _rows(scan_dir, evidence if isinstance(evidence, dict) else {})
    print(_render(scan_dir, rows))
    return 0 if all(row["status"] == "ok" for row in rows) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--skill", choices=[SKILL], default=SKILL)
    check_parser.add_argument("--scan-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return check(args.scan_dir)


if __name__ == "__main__":
    raise SystemExit(main())
