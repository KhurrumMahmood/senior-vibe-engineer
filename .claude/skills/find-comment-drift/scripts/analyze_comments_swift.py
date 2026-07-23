#!/usr/bin/env python3
"""Find one bounded adjacent percentage contradiction in Swift source."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_swift-project-lexical"
sys.path.insert(0, str(COMMON))

from swift_project_facts import (  # noqa: E402
    add_tool_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    function_facts,
    hash_bytes,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
    validate_artifacts,
)

PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:percent|%)\b", re.I)
MULTIPLIER_RE = re.compile(r"\*\s*(0?\.\d+)(?![\d.])")


def _findings(snapshot: dict) -> list[dict]:
    findings: list[dict] = []
    for row in snapshot["inventory"]:
        if row["role"] != "eligible":
            continue
        source: bytes = row["_source"]
        functions = function_facts(row)
        for comment in row["comments"]:
            percentage = PERCENT_RE.search(comment["text"])
            if percentage is None:
                continue
            end = comment["span"]["end_byte"]
            adjacent = [
                fact
                for fact in functions
                if fact["span"]["start_byte"] >= end
                and not source[end : fact["span"]["start_byte"]].strip()
            ]
            if not adjacent:
                continue
            fact = min(adjacent, key=lambda item: item["span"]["start_byte"])
            multiplier = MULTIPLIER_RE.search(fact["normalized_body"])
            if multiplier is None:
                continue
            documented = float(percentage.group(1))
            fixed = float(multiplier.group(1))
            if abs(documented / 100 - fixed) < 1e-9:
                continue
            findings.append(
                {
                    "band": "adjacent_percentage_mismatch",
                    "language": "swift",
                    "file": row["file"],
                    "symbol": fact["symbol"],
                    "documented_percent": int(documented) if documented.is_integer() else documented,
                    "fixed_multiplier": fixed,
                    "comment_span": comment["span"],
                    "function_span": fact["span"],
                    "source_sha256": row["source_sha256"],
                    "comment_spelling_sha256": comment["spelling_sha256"],
                    "function_spelling_sha256": fact["spelling_sha256"],
                    "claim_boundary": "bounded adjacent lexical contradiction; no semantic identity is claimed",
                }
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    artifacts = {
        "detections": output / "detections.jsonl",
        "scan": output / "scan.json",
        "findings": output / "findings.json",
        "report": output / "report.md",
    }
    try:
        validate_artifacts(root, artifacts.values())
    except ValueError as exc:
        parser.error(str(exc))
    clear_artifacts(artifacts.values())
    snapshot = collect_snapshot(
        root,
        [args.target],
        swift=args.swift,
        swiftc=args.swiftc,
        swift_format=args.swift_format,
        check_product=args.check_product,
        expected_check=args.expected_check,
        smoke_product=args.smoke_product,
        expected_smoke=args.expected_smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    snapshot["host_state_preserved"] = snapshot["source_preserved"]
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    findings = _findings(snapshot) if snapshot["status"] == "complete" else []
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "advisory-findings"
        if findings
        else "clean-within-complete"
    )
    jsonl = "".join(json.dumps(item, sort_keys=True) + "\n" for item in findings)
    analysis = public_snapshot(snapshot)
    atomic_text(artifacts["detections"], jsonl)
    atomic_json(artifacts["scan"], analysis)
    atomic_json(
        artifacts["findings"],
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "analysis": {"swift": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "findings": findings,
        },
    )
    lines = [
        "# Comment-drift audit — Swift",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        "",
        "This rule reports only an adjacent fixed percentage contradiction. "
        "It does not infer comment-to-symbol semantic identity.",
        "",
    ]
    lines.extend(
        f"- `{row['file']}::{row['symbol']}` — {row['documented_percent']}% vs "
        f"multiplier {row['fixed_multiplier']}"
        for row in findings
    )
    if not findings:
        lines.append(
            "No bounded contradiction found."
            if snapshot["status"] == "complete"
            else "Analysis is incomplete; no clean conclusion is available."
        )
    atomic_text(artifacts["report"], "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
