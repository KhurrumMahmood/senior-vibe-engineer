#!/usr/bin/env python3
"""Carry Rust omnibus syntax candidates through required scout grading."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any


ARTIFACTS = ("omnibus.jsonl", "candidates.jsonl", "scan.json", "findings.json", "report.md")
GENERIC = frozenset({
    "load", "save", "validate", "authorize", "render", "write", "rotate",
    "find", "get", "set", "create", "update", "delete", "process", "handle",
})
BUCKETS = {"confirmed_omnibus", "borderline", "coordination_omnibus", "facets_not_domains"}


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _producer() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_rust-syntax/scripts/rust_syntax_facts.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("rust_syntax_facts", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rust_syntax_facts"] = module
    spec.loader.exec_module(module)
    return module


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    producer = _producer()
    if producer is None:
        return {
            "status": "partial", "failure_kind": "rust_fact_producer_missing",
            "analyzer": "rust-syntax-facts-v1", "files": [], "inventory": [],
            "ambiguities": [], "native": {}, "source_manifest": {"preserved": True},
        }, 0
    return producer.produce(
        args.project_root, args.target,
        cargo=args.cargo, rustc=args.rustc, rustfmt=args.rustfmt, clippy=args.clippy,
    )


def _cluster(name: str) -> str:
    words = [word for word in re.split(r"_+|(?<=[a-z])(?=[A-Z])", name) if word]
    specific = [word.casefold() for word in words if word.casefold() not in GENERIC]
    return specific[-1] if specific else words[-1].casefold()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scout-dir", required=True, type=Path)
    parser.add_argument("--cargo")
    parser.add_argument("--rustc")
    parser.add_argument("--rustfmt")
    parser.add_argument("--clippy")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    detections: list[dict[str, Any]] = []
    for file in facts.get("files", []):
        clusters: dict[str, list[str]] = defaultdict(list)
        for function in file["functions"]:
            clusters[_cluster(function["name"])].append(function["name"])
        confirmed = {name: names for name, names in clusters.items() if len(names) >= 2}
        if len(confirmed) >= 4:
            detections.append({
                "file": file["file"], "language": "rust", "analyzer": facts["analyzer"],
                "cluster_count": len(confirmed), "and_count": len(confirmed) - 1,
                "clusters": confirmed,
                "srp_sentence": "This file handles " + " and ".join(sorted(confirmed)) + ".",
            })
    detections.sort(key=lambda row: (-row["cluster_count"], row["file"]))
    candidates = [{**row, "candidate_id": f"candidate-{index:03d}"} for index, row in enumerate(detections, 1)]
    findings: list[dict[str, Any]] = []
    missing_scouts: list[str] = []
    for candidate in candidates:
        scout_path = args.scout_dir / f"{candidate['candidate_id']}.json"
        try:
            scout = json.loads(scout_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            missing_scouts.append(candidate["candidate_id"])
            continue
        if scout.get("candidate_id") != candidate["candidate_id"] or scout.get("bucket") not in BUCKETS:
            missing_scouts.append(candidate["candidate_id"])
            continue
        bucket = scout["bucket"]
        recommendation = {
            "confirmed_omnibus": "/refactor-subsystem <spec-id>",
            "coordination_omnibus": "/map-product-workflow",
            "borderline": "measure responsibility change before decomposition",
            "facets_not_domains": "keep cohesive module",
        }[bucket]
        findings.append({**candidate, **scout, "recommendation": recommendation})
    status = facts["status"]
    failure = facts["failure_kind"]
    if missing_scouts and status != "failed":
        status = "partial"
        failure = "rust_scout_evidence_missing"
        code = 0
    payload = {
        "status": status,
        "failure_kind": failure,
        "analysis": {"rust": facts},
        "summary": dict(sorted(Counter(row["bucket"] for row in findings).items())),
        "missing_scouts": missing_scouts,
        "findings": findings,
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "omnibus.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in detections))
    _atomic(output / "candidates.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates))
    _atomic(output / "scan.json", json.dumps({"status": status, "failure_kind": failure, "rust": facts}, indent=2, sort_keys=True) + "\n")
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = ["# Omnibus audit", "", f"Status: `{status}`", f"Analyzer: `{facts['analyzer']}`", ""]
    lines.extend(
        f"- `{row['file']}` — `{row['bucket']}`; {row['recommendation']}"
        for row in findings
    )
    if missing_scouts:
        lines.append("- Missing scout evidence: " + ", ".join(missing_scouts))
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    print(f"[detect_omnibus] wrote {output / 'omnibus.jsonl'} ({len(detections)} candidates)")
    print(f"[collapse] wrote {output / 'candidates.jsonl'} ({len(candidates)} candidates)")
    print(f"[report] wrote {output / 'report.md'} ({len(findings)} scout-graded findings)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
