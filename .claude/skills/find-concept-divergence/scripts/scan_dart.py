#!/usr/bin/env python3
"""Scan authored Dart library source for strict glossary-backed term drift."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

COMMON = Path(__file__).resolve().parents[2] / "_dart"
sys.path.insert(0, str(COMMON))

from dart_project_snapshot import (  # noqa: E402
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    eligible_rows,
    hash_bytes,
    public_snapshot,
    span,
    terminal_return_code,
    validate_artifact_paths,
)


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("["):
        try:
            return json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            if not value.endswith("]"):
                raise ValueError("unterminated glossary flow list") from None
            return [
                item.strip().strip("\"'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
    if value.startswith(("\"", "'")) and value.endswith(value[0]):
        return value[1:-1]
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
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


def _load_glossary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = _yaml_profile(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("concepts"), list):
        raise ValueError("glossary missing top-level concepts list")
    if not payload["concepts"]:
        raise ValueError("glossary concepts list must not be empty")
    return payload


def _pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.I)


def _hits(row: dict[str, Any], term: str) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    text = source.decode("utf-8")
    results: list[dict[str, Any]] = []
    for match in _pattern(term).finditer(text):
        start = len(text[: match.start()].encode("utf-8"))
        spelling = match.group(0).encode("utf-8")
        results.append(
            {
                "term": term,
                "match": match.group(0),
                "line": text.count("\n", 0, match.start()) + 1,
                "span": span(source, start, start + len(spelling)),
                "spelling_sha256": hash_bytes(spelling),
            }
        )
    return results


def _scan(glossary: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    concepts = [row for row in glossary.get("concepts", []) if isinstance(row, dict)]
    by_name = {row.get("name"): row for row in concepts if row.get("name")}
    for concept in concepts:
        sources = set(concept.get("source_files") or concept.get("sources") or [])
        if isinstance(concept.get("source"), str):
            sources.add(concept["source"])
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
                            "language": "dart",
                            "source_sha256": row["sha256"],
                            **hit,
                        }
                    )
        replacement = concept.get("superseded_by")
        if replacement and replacement in by_name and not concept.get("coverage_lint"):
            old_terms = [concept.get("name"), *(concept.get("aliases") or [])]
            new = by_name[replacement]
            new_terms = [new.get("name"), *(new.get("aliases") or [])]
            for row in rows:
                if not any(_hits(row, term) for term in old_terms if isinstance(term, str)):
                    continue
                if not any(_hits(row, term) for term in new_terms if isinstance(term, str)):
                    continue
                for term in old_terms:
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
                                "language": "dart",
                                "source_sha256": row["sha256"],
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
                            "language": "dart",
                            "source_sha256": row["sha256"],
                            **hit,
                        }
                    )
    return sorted(findings, key=lambda row: (row["file"], row["line"], row["band"], row["term"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--glossary", type=Path, required=True)
    parser.add_argument("--dart-root", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    raw = [args.output, args.report, args.output.with_name("findings.json"), args.output.with_name("scan.json")]
    try:
        output, report, final_json, scan_json = validate_artifact_paths(root, raw)
    except ValueError as exc:
        print(f"scan-dart: status=failed: {exc}", file=sys.stderr)
        return 2
    clear_artifacts([output, report, final_json, scan_json])
    snapshot = collect_snapshot(
        root,
        args.dart_root,
        dart=args.dart,
        direct_test=args.direct_test,
        smoke_entrypoint=args.smoke_entrypoint,
        expected_smoke=args.expected_smoke,
    )
    try:
        glossary = _load_glossary(args.glossary)
        glossary_bytes = args.glossary.read_bytes()
        snapshot["consumer_configuration"] = {
            "glossary": str(args.glossary),
            "sha256": hash_bytes(glossary_bytes),
            "bytes": len(glossary_bytes),
        }
    except (OSError, UnicodeError, ValueError) as exc:
        snapshot.update(status="failed", failure_kind="glossary-invalid", errors=[str(exc)])
        glossary = {"concepts": []}
    findings = _scan(glossary, eligible_rows(snapshot)) if snapshot["status"] == "complete" else []
    analysis = public_snapshot(snapshot)
    outcome = (
        "failed"
        if snapshot["status"] == "failed"
        else "incomplete"
        if snapshot["status"] == "partial"
        else "drift-found"
        if findings
        else "clean"
    )
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    atomic_text(output, jsonl)
    atomic_json(scan_json, analysis)
    atomic_json(
        final_json,
        {
            "schema_version": 1,
            "status": snapshot["status"],
            "outcome": outcome,
            "analysis": {"dart": analysis},
            "detections_sha256": hash_bytes(jsonl.encode()),
            "glossary_sha256": analysis.get("consumer_configuration", {}).get("sha256"),
            "findings": findings,
            "limitation": "Strict glossary text only; no symbol identity, conceptual equivalence, or rename-completeness claim.",
        },
    )
    lines = [
        "# Concept-divergence scan — Dart",
        "",
        f"**Status:** `{snapshot['status']}`",
        f"**Outcome:** `{outcome}`",
        "",
    ]
    if findings:
        lines.extend(
            f"- `{row['file']}:{row['line']}` — `{row['term']}` — `{row['band']}`"
            for row in findings
        )
    elif snapshot["status"] == "complete":
        lines.append("No drift detected against the current glossary.")
    else:
        lines.append("Analysis is incomplete; no absence-of-drift conclusion is available.")
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
