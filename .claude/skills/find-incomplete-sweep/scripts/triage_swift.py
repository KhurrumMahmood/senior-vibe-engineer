#!/usr/bin/env python3
"""Render hash-bound Swift incomplete-sweep human verdicts."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


VALID = ("forgotten", "deliberate", "optional", "not-applicable")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--scan-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    try:
        scan = _safe(root, args.scan_dir)
        rendered = scan / "triaged.md"
        if rendered.is_symlink() or rendered.is_file():
            rendered.unlink()
        elif rendered.exists():
            raise ValueError("triaged.md must not be a directory")
        packets = json.loads((scan / "scout_packets.json").read_text(encoding="utf-8"))
        verdicts = json.loads((scan / "scout_verdicts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if packets.get("schema_version") != "swift-sweep-packets-v1":
        parser.error("packet schema is incompatible")
    if verdicts.get("schema_version") != "swift-sweep-verdicts-v1":
        parser.error("verdict schema is incompatible")
    by_id = {row["id"]: row for row in packets.get("packets", [])}
    selected: dict[str, dict] = {}
    for row in verdicts.get("verdicts", []):
        identifier = row.get("id")
        if identifier not in by_id or identifier in selected:
            parser.error("verdict ids must match packets exactly once")
        if row.get("packet_sha256") != by_id[identifier].get("packet_sha256"):
            parser.error(f"verdict hash does not match {identifier}")
        if row.get("verdict") not in VALID:
            parser.error(f"verdict vocabulary is invalid for {identifier}")
        if not isinstance(row.get("rationale"), str) or not row["rationale"].strip():
            parser.error(f"rationale is required for {identifier}")
        if row["verdict"] == "forgotten" and not str(row.get("completion", "")).strip():
            parser.error(f"completion is required for forgotten packet {identifier}")
        selected[identifier] = row
    if set(selected) != set(by_id):
        parser.error("every scout packet requires one verdict")
    ordered = [selected[row["id"]] for row in packets["packets"]]
    counts = Counter(row["verdict"] for row in ordered)
    lines = [
        "# find-incomplete-sweep — Swift triage",
        "",
        "This is a hash-bound human-verdict handoff, not an automatic source change.",
        "",
        "## Verdict accounting",
        "",
        f"- Scout packets: {len(ordered)}",
        *[f"- {verdict}: {counts[verdict]}" for verdict in VALID],
    ]
    for row in ordered:
        packet = by_id[row["id"]]
        lines.extend(
            [
                "",
                f"## {row['id']} — {row['verdict']}",
                "",
                f"- straggler: `{packet['straggler']['ref']}`",
                f"- callee/argument: `{packet['callee']}` / `{packet['kwarg']}`",
                f"- rationale: {row['rationale'].strip()}",
            ]
        )
        if row["verdict"] == "forgotten":
            lines.append(f"- suggested completion: {row['completion'].strip()}")
    temporary = rendered.with_name(f".{rendered.name}.tmp-{os.getpid()}")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, rendered)
    print(f"wrote Swift sweep triage: {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
