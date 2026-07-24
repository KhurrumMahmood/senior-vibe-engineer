#!/usr/bin/env python3
"""Scan eligible C17 source for strict glossary-backed text divergence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROVIDER = Path(__file__).resolve().parents[2] / "_c"
sys.path.insert(0, str(PROVIDER))

from c_lexical_facts import (  # noqa: E402
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    hash_bytes,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("["):
        return json.loads(value.replace("'", '"'))
    if value.startswith(('"', "'")) and value.endswith(value[0]):
        return value[1:-1]
    return value


def _yaml_profile(text: str) -> dict[str, Any]:
    data: dict[str, list[dict[str, Any]]] = {"concepts": [], "flagged_ambiguities": []}
    collection: str | None = None
    current: dict[str, Any] | None = None
    list_key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line in {"concepts:", "flagged_ambiguities:"}:
            if current is not None and collection:
                data[collection].append(current)
            collection, current, list_key = line[:-1], None, None
            continue
        if collection is None:
            continue
        if indent == 2 and line.startswith("- "):
            if current is not None:
                data[collection].append(current)
            current, list_key = {}, None
            line = line[2:]
            if ":" in line:
                key, value = line.split(":", 1)
                current[key.strip()] = _scalar(value)
            continue
        if current is None:
            continue
        if indent == 4 and ":" in line:
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            current[key] = [] if not value else _scalar(value)
            list_key = key if not value else None
            continue
        if indent >= 6 and list_key and line.startswith("- "):
            current[list_key].append(_scalar(line[2:]))
    if current is not None and collection:
        data[collection].append(current)
    return data


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _yaml_profile(text)
    if not isinstance(data, dict) or not isinstance(data.get("concepts"), list):
        raise ValueError("glossary missing top-level concepts list")
    return data


def _span(source: bytes, start: int, end: int) -> dict[str, Any]:
    start_before, end_before = source[:start], source[:end]
    return {
        "start_byte": start,
        "end_byte": end,
        "start": {
            "line": start_before.count(b"\n") + 1,
            "column": start - start_before.rfind(b"\n"),
        },
        "end": {
            "line": end_before.count(b"\n") + 1,
            "column": end - end_before.rfind(b"\n"),
        },
    }


def _hits(row: dict[str, Any], term: str) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    pattern = re.compile(rb"(?<![A-Za-z0-9_])" + re.escape(term.encode()) + rb"(?![A-Za-z0-9_])", re.I)
    return [
        {
            "term": term,
            "match": match.group().decode("utf-8", errors="replace"),
            "line": _span(source, *match.span())["start"]["line"],
            "span": _span(source, *match.span()),
            "spelling_sha256": hash_bytes(match.group()),
        }
        for match in pattern.finditer(source)
    ]


def _scan(glossary: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for concept in glossary.get("concepts", []):
        if not isinstance(concept, dict):
            continue
        sources = set(concept.get("source_files") or concept.get("sources") or [])
        for entry in concept.get("avoid") or []:
            if not isinstance(entry, str):
                continue
            term = entry.split("(", 1)[0].strip().strip("\"'").rstrip(",.;:")
            for row in rows:
                if row["file"] in sources:
                    continue
                for hit in _hits(row, term):
                    findings.append(
                        {
                            "band": "avoid_term_hit",
                            "concept": concept.get("name", "?"),
                            "file": row["file"],
                            "language": "c",
                            "source_sha256": row["source_sha256"],
                            "claim": "strict-text-evidence-not-symbol-identity",
                            **hit,
                        }
                    )
    findings.sort(key=lambda item: (item["file"], item["line"], item["term"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--glossary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("targets", nargs="*", default=["."])
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output, report = args.output.resolve(), args.report.resolve()
    try:
        output.relative_to(root)
        report.relative_to(root)
    except ValueError:
        parser.error("--output and --report must be inside --project-root")
    final_json, scan_json = output.with_name("findings.json"), output.with_name("scan.json")
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        args.targets or ["."],
        clang=args.clang,
        make=args.make,
        test_target=args.test_target,
        smoke=args.smoke,
    )
    try:
        glossary = _load(args.glossary)
    except (OSError, UnicodeError, ValueError) as exc:
        snapshot.update(status="failed", failure_kind="glossary-invalid", errors=[str(exc)])
        glossary = {"concepts": []}
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    rows = [row for row in snapshot["inventory"] if row["role"] == "eligible" and row["selected"]]
    findings = _scan(glossary, rows) if snapshot["status"] != "failed" else []
    jsonl = "".join(json.dumps(item, sort_keys=True) + "\n" for item in findings)
    atomic_text(output, jsonl)
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "drift-found"
        if findings
        else "clean-within-complete"
    )
    analysis = public_snapshot(snapshot)
    atomic_json(
        final_json,
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "analysis": {"c": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "findings": findings,
        },
    )
    atomic_json(scan_json, analysis)
    lines = [
        "# Concept-divergence scan — C17",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        "",
    ]
    if findings:
        lines.extend(f"- `{item['file']}:{item['line']}` — `{item['term']}`" for item in findings)
    elif snapshot["status"] == "complete":
        lines.append("No strict glossary drift detected in the complete selected snapshot.")
    else:
        lines.append("Analysis is incomplete; no absence-of-drift conclusion is available.")
    lines.extend(["", "Strict C text evidence is not preprocessed symbol or conceptual identity."])
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
