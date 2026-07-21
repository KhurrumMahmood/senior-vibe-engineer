#!/usr/bin/env python3
"""Render the fixed find-incomplete-sweep verdict contract into triaged.md.

The detector and scout deliberately stop before judgment.  This writer is the
single final-output oracle: every packet must receive one explicit fixed-vocab
verdict before a forgotten-first triage can exist.  It is language-neutral so
the Python, compiler-backed TypeScript, and checked-JavaScript paths share the
same human handoff without sharing detection logic.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


VALID_VERDICTS = ("forgotten", "deliberate", "optional", "not-applicable")


class TriageError(ValueError):
    """An incomplete or malformed human-verdict artifact."""


def _load_json(path: Path) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TriageError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise TriageError(f"{path.name} must contain an object")
    return loaded


def validate_verdicts(packets: dict, verdicts: dict) -> list[dict]:
    """Return verdicts in packet order after proving the Step B accounting."""
    packet_rows = packets.get("packets", [])
    verdict_rows = verdicts.get("verdicts", [])
    if not isinstance(packet_rows, list) or not isinstance(verdict_rows, list):
        raise TriageError("packets and verdicts must both be lists")
    packet_ids = [row.get("id") for row in packet_rows if isinstance(row, dict)]
    if len(packet_ids) != len(packet_rows) or any(not isinstance(item, str) or not item for item in packet_ids):
        raise TriageError("every scout packet must have a non-empty id")
    if len(set(packet_ids)) != len(packet_ids):
        raise TriageError("scout packet ids must be unique")

    by_id: dict[str, dict] = {}
    for row in verdict_rows:
        if not isinstance(row, dict):
            raise TriageError("each verdict must be an object")
        verdict_id = row.get("id")
        verdict = row.get("verdict")
        rationale = row.get("rationale")
        if not isinstance(verdict_id, str) or not verdict_id:
            raise TriageError("every verdict must name a packet id")
        if verdict_id in by_id:
            raise TriageError(f"duplicate verdict for packet {verdict_id}")
        if verdict not in VALID_VERDICTS:
            raise TriageError(f"packet {verdict_id} has invalid verdict {verdict!r}")
        if not isinstance(rationale, str) or not rationale.strip() or "\n" in rationale:
            raise TriageError(f"packet {verdict_id} needs a one-line rationale")
        completion = row.get("completion")
        if verdict == "forgotten":
            if not isinstance(completion, str) or not completion.strip() or "\n" in completion:
                raise TriageError(f"forgotten packet {verdict_id} needs a one-line completion")
        elif completion not in (None, ""):
            raise TriageError(f"non-forgotten packet {verdict_id} must not carry a completion")
        by_id[verdict_id] = row

    unexpected = sorted(set(by_id) - set(packet_ids))
    missing = [packet_id for packet_id in packet_ids if packet_id not in by_id]
    if unexpected:
        raise TriageError(f"verdicts reference unknown packets: {', '.join(unexpected)}")
    if missing:
        raise TriageError(f"verdicts missing packets: {', '.join(missing)}")
    return [by_id[packet_id] for packet_id in packet_ids]


def ensure_compiler_manifest_output_containment(scan_dir: Path, packets: dict) -> None:
    """Keep every compiler-manifest final writer inside its detector-owned report root.

    Python's legacy `--out` supports broader caller-selected output locations.
    The compiler runners deliberately promise stricter report containment, so
    Step C preserves that boundary instead of reopening a symlink path after the
    detector and scout have completed.
    """
    language = packets.get("language")
    if language not in {"typescript", "javascript", "go"}:
        return
    language_label = {
        "typescript": "TypeScript",
        "javascript": "checked JavaScript",
        "go": "Go",
    }[language]
    root_value = packets.get("project_root")
    if not isinstance(root_value, str) or not root_value:
        raise TriageError(f"{language_label} packets must record their project root")
    project_root = Path(root_value).resolve()
    allowed_root = project_root / "reports" / "find-incomplete-sweep"
    if ".." in scan_dir.parts:
        raise TriageError(f"{language_label} triage path must not contain parent traversal")
    try:
        scan_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise TriageError(f"{language_label} triage must stay beneath reports/find-incomplete-sweep/") from exc
    current = project_root
    try:
        parts = scan_dir.relative_to(project_root).parts
    except ValueError as exc:
        raise TriageError(f"{language_label} triage must stay inside its project root") from exc
    try:
        scan_dir.resolve().relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise TriageError(f"{language_label} triage must stay beneath reports/find-incomplete-sweep/") from exc
    for part in parts:
        current /= part
        if current.is_symlink():
            raise TriageError(f"{language_label} triage must not traverse a symbolic link")
    output = scan_dir / "triaged.md"
    if output.is_symlink():
        raise TriageError(f"{language_label} triage output must not be a symbolic link")


def render_triage(packets: dict, ordered_verdicts: list[dict]) -> str:
    """Render the immutable forgotten-first human handoff report."""
    packet_by_id = {packet["id"]: packet for packet in packets.get("packets", [])}
    grouped = {verdict: [] for verdict in VALID_VERDICTS}
    for row in ordered_verdicts:
        grouped[row["verdict"]].append(row)

    counts = Counter(row["verdict"] for row in ordered_verdicts)
    lines = [
        "# find-incomplete-sweep — triage",
        "",
        "This is a human-verdict handoff, not an automatic code change.",
        "",
        "## Verdict accounting",
        "",
        f"- Scout packets: {len(ordered_verdicts)}",
        *[f"- {verdict}: {counts[verdict]}" for verdict in VALID_VERDICTS],
    ]
    headings = {
        "forgotten": "Forgotten",
        "deliberate": "Deliberate",
        "optional": "Optional",
        "not-applicable": "Not applicable",
    }
    for verdict in VALID_VERDICTS:
        rows = grouped[verdict]
        lines.extend(["", f"## {headings[verdict]} ({len(rows)})", ""])
        if not rows:
            lines.append("None.")
            continue
        for row in rows:
            packet = packet_by_id[row["id"]]
            straggler = packet.get("straggler", {})
            ref = straggler.get("ref", "unknown location") if isinstance(straggler, dict) else "unknown location"
            callee = packet.get("callee", "unknown callee")
            kwarg = packet.get("kwarg", "unknown option")
            lines.extend([
                f"### {row['id']} — `{callee}` missing `{kwarg}`",
                f"- straggler: `{ref}`",
                f"- rationale: {row['rationale'].strip()}",
            ])
            if verdict == "forgotten":
                lines.extend([
                    f"- suggested completion: {row['completion'].strip()}",
                    f"- handoff: `/fix-workflow cluster:{row['id']}`",
                ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="write find-incomplete-sweep triaged.md")
    parser.add_argument("--scan-dir", type=Path, required=True)
    args = parser.parse_args()
    raw_scan_dir = args.scan_dir if args.scan_dir.is_absolute() else Path.cwd() / args.scan_dir
    scan_dir = raw_scan_dir.resolve()
    packets = _load_json(scan_dir / "scout_packets.json")
    verdicts = _load_json(scan_dir / "scout_verdicts.json")
    ensure_compiler_manifest_output_containment(raw_scan_dir, packets)
    ordered = validate_verdicts(packets, verdicts)
    output = scan_dir / "triaged.md"
    output.write_text(render_triage(packets, ordered), encoding="utf-8")
    print(f"wrote {output}  ({len(ordered)} explicit verdicts)")


if __name__ == "__main__":
    try:
        main()
    except TriageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
