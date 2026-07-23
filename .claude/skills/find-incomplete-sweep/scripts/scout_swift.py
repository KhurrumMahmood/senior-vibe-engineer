#!/usr/bin/env python3
"""Build content-hashed Swift incomplete-sweep scout packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _safe(root: Path, supplied: Path) -> Path:
    scan = supplied if supplied.is_absolute() else root / supplied
    scan = Path(os.path.abspath(scan))
    allowed = root / "reports/find-incomplete-sweep"
    try:
        scan.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("scan-dir must stay beneath reports/find-incomplete-sweep/") from exc
    current = root
    for part in scan.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("scan-dir must not traverse a symbolic link")
    return scan


def _window(root: Path, file: str, line: int, context: int = 4) -> dict[str, Any]:
    source = root / file
    if not source.is_file() or source.is_symlink():
        return {"file": file, "line": line, "available": False, "text": ""}
    lines = source.read_text(encoding="utf-8").splitlines()
    if not 1 <= line <= len(lines):
        return {"file": file, "line": line, "available": False, "text": ""}
    low, high = max(1, line - context), min(len(lines), line + context)
    return {
        "file": file,
        "line": line,
        "available": True,
        "start": low,
        "end": high,
        "text": "\n".join(
            f"{'>>' if number == line else '  '} {number:>5}│ {lines[number - 1]}"
            for number in range(low, high + 1)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--scan-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    try:
        scan = _safe(root, args.scan_dir)
        manifest = json.loads((scan / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if manifest.get("language") != "swift" or manifest.get("status") != "complete":
        parser.error("a complete Swift compiler manifest is required")
    packets: list[dict[str, Any]] = []
    for index, finding in enumerate(
        [row for row in manifest.get("findings", []) if row.get("gated_in")], 1
    ):
        straggler = finding["straggler_site"]
        packet = {
            "id": f"swift-sweep-{index:04d}",
            "callee": finding["callee"],
            "callee_semantic_id": finding["callee_semantic_id"],
            "kwarg": finding["kwarg"],
            "value": finding["value"],
            "default_value": finding["default_value"],
            "trajectory": finding["trajectory"],
            "fact_pack_sha256": manifest.get("fact_pack_sha256"),
            "straggler": {
                "ref": finding["straggler"],
                "window": _window(root, straggler["file"], straggler["line"]),
            },
            "present": [
                {
                    "ref": f"{row['file']}:{row['line']}",
                    "window": _window(root, row["file"], row["line"]),
                }
                for row in finding.get("present_sites", [])[:2]
            ],
            "human_verdict": "required",
        }
        packet["packet_sha256"] = _hash(packet)
        packets.append(packet)
    payload = {
        "schema_version": "swift-sweep-packets-v1",
        "language": "swift",
        "project_root": str(root),
        "scan_dir": str(scan),
        "packet_count": len(packets),
        "packets": packets,
    }
    (scan / "scout_packets.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote Swift sweep scout packets: {len(packets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
