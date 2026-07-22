#!/usr/bin/env python3
"""Scan eligible Rust source for glossary-backed concept divergence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

COMMON = Path(__file__).resolve().parents[2] / "_rust"
sys.path.insert(0, str(COMMON))

from rust_lexical_facts import (  # noqa: E402
    add_tool_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    hash_bytes,
    public_snapshot,
    sources_preserved,
    span,
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


def _pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.I)


def _hits(row: dict[str, Any], term: str) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    text = source.decode("utf-8")
    results = []
    for match in _pattern(term).finditer(text):
        start = len(text[: match.start()].encode("utf-8"))
        end = start + len(match.group(0).encode("utf-8"))
        results.append(
            {
                "term": term,
                "match": match.group(0),
                "line": text.count("\n", 0, match.start()) + 1,
                "span": span(source, start, end),
                "spelling_sha256": hash_bytes(source[start:end]),
            }
        )
    return results


def _scan(glossary: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    concepts = [item for item in glossary.get("concepts", []) if isinstance(item, dict)]
    by_name = {item.get("name"): item for item in concepts if item.get("name")}
    for concept in concepts:
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
                            "language": "rust",
                            "source_sha256": row["source_sha256"],
                            **hit,
                        }
                    )
        replacement = concept.get("superseded_by")
        if replacement and replacement in by_name and not concept.get("coverage_lint"):
            old = [concept.get("name"), *(concept.get("aliases") or [])]
            new_concept = by_name[replacement]
            new = [new_concept.get("name"), *(new_concept.get("aliases") or [])]
            for row in rows:
                if not any(_hits(row, term) for term in old if isinstance(term, str)):
                    continue
                if not any(_hits(row, term) for term in new if isinstance(term, str)):
                    continue
                for term in old:
                    if not isinstance(term, str):
                        continue
                    for hit in _hits(row, term):
                        findings.append(
                            {
                                "band": "superseded_co_occurrence",
                                "concept": concept.get("name"),
                                "superseded_by": replacement,
                                "side": "old",
                                "file": row["file"],
                                "language": "rust",
                                "source_sha256": row["source_sha256"],
                                **hit,
                            }
                        )
    for ambiguity in glossary.get("flagged_ambiguities") or []:
        if not isinstance(ambiguity, dict):
            continue
        terms = [term for term in ambiguity.get("competing_terms") or [] if isinstance(term, str)]
        for row in rows:
            found = {term: _hits(row, term) for term in terms}
            found = {term: hits for term, hits in found.items() if hits}
            if len(found) < 2:
                continue
            for term_hits in found.values():
                for hit in term_hits:
                    findings.append(
                        {
                            "band": "competing_term_coexistence",
                            "ambiguity_id": ambiguity.get("id", "?"),
                            "competing_terms": list(found),
                            "file": row["file"],
                            "language": "rust",
                            "source_sha256": row["source_sha256"],
                            **hit,
                        }
                    )
    findings.sort(key=lambda item: (item["file"], item["line"], item["band"], item["term"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--glossary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("targets", nargs="*", default=["."])
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    report = args.report.resolve()
    final_json = output.with_name("findings.json")
    scan_json = output.with_name("scan.json")
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        args.targets or ["."],
        rustc=args.rustc,
        cargo=args.cargo,
        rustfmt=args.rustfmt,
    )
    try:
        glossary = _load(args.glossary)
    except (OSError, UnicodeError, ValueError) as exc:
        snapshot.update(status="failed", failure_kind="glossary-invalid", errors=[str(exc)])
        glossary = {"concepts": []}
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    rows = [row for row in snapshot["inventory"] if row["role"] == "eligible"]
    findings = _scan(glossary, rows) if snapshot["status"] != "failed" else []
    jsonl = "".join(json.dumps(item, sort_keys=True) + "\n" for item in findings)
    atomic_text(output, jsonl)
    analysis = public_snapshot(snapshot)
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "drift-found"
        if findings
        else "clean-within-complete"
    )
    payload = {
        "schema_version": 1,
        "status": snapshot["status"],
        "outcome": outcome,
        "analysis": {"rust": analysis},
        "detections_sha256": hash_bytes(jsonl.encode()),
        "findings": findings,
    }
    atomic_json(final_json, payload)
    atomic_json(scan_json, analysis)
    lines = [
        "# Concept-divergence scan — Rust",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        "",
    ]
    if findings:
        lines.append(f"Total findings: **{len(findings)}**.")
        lines.extend(
            f"- `{item['file']}:{item['line']}` — `{item['term']}` — `{item['band']}`"
            for item in findings
        )
    elif snapshot["status"] == "complete":
        lines.append("No drift detected against the current glossary.")
    else:
        lines.append("Analysis is incomplete; no absence-of-drift conclusion is available.")
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
