#!/usr/bin/env python3
"""Carry PHP syntax nominees through mandatory human omnibus scout grading."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
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


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    provider = Path(__file__).resolve().parents[2] / "_php-syntax/php_syntax_facts.php"
    if not provider.is_file():
        return {
            "status": "partial", "failure_kind": "php_syntax_provider_missing",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "source_manifest": {"preserved": True},
        }, 2
    runner = args.php_runner or shutil.which("php") or "php"
    command = [
        runner, str(provider), "--project-root", str(args.project_root), "--target", str(args.target),
        "--php", args.php, "--composer", args.composer,
        "--minimum-php", args.minimum_php, "--minimum-composer", args.minimum_composer,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return json.loads(result.stdout), result.returncode
    except (OSError, json.JSONDecodeError) as error:
        return {
            "status": "failed", "failure_kind": "php_syntax_provider_execution_failed",
            "analyzer": "php-token-syntax-facts-v1", "files": [], "inventory": [],
            "provider_error": str(error), "source_manifest": {"preserved": True},
        }, 1


def _cluster(name: str) -> str:
    words = [word for word in re.split(r"_+|(?<=[a-z])(?=[A-Z])", name) if word]
    specific = [word.casefold() for word in words if word.casefold() not in GENERIC]
    return specific[-1] if specific else words[-1].casefold()


def _candidate_sha256(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scout-dir", required=True, type=Path)
    parser.add_argument("--php", default="php")
    parser.add_argument("--composer", default="composer")
    parser.add_argument("--php-runner")
    parser.add_argument("--minimum-php", default="8.1.0")
    parser.add_argument("--minimum-composer", default="2.2.0")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    facts, code = _facts(args)
    detections: list[dict[str, Any]] = []
    if facts["status"] == "complete":
        for file in facts["files"]:
            clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for function in file["functions"]:
                clusters[_cluster(function["name"])].append(function)
            paired = {name: rows for name, rows in clusters.items() if len(rows) >= 2}
            if len(paired) >= 4:
                detections.append({
                    "file": file["file"], "language": "php", "analyzer": facts["analyzer"],
                    "cluster_count": len(paired), "and_count": len(paired) - 1,
                    "clusters": {name: [row["qualified_name"] for row in rows] for name, rows in paired.items()},
                    "declarations": [
                        {"name": row["qualified_name"], "line": row["line"], "spelling_sha256": row["spelling_sha256"]}
                        for rows in paired.values() for row in rows
                    ],
                    "srp_sentence": "This file handles " + " and ".join(sorted(paired)) + ".",
                })
    detections.sort(key=lambda row: (-row["cluster_count"], row["file"]))
    candidates = []
    for index, row in enumerate(detections, 1):
        base = {**row, "candidate_id": f"candidate-{index:03d}"}
        candidates.append({**base, "candidate_sha256": _candidate_sha256(base)})
    findings: list[dict[str, Any]] = []
    missing_scouts: list[str] = []
    if facts["status"] == "complete":
        for candidate in candidates:
            scout_path = args.scout_dir / f"{candidate['candidate_id']}.json"
            try:
                scout = json.loads(scout_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                missing_scouts.append(candidate["candidate_id"])
                continue
            if (
                scout.get("candidate_id") != candidate["candidate_id"]
                or scout.get("candidate_sha256") != candidate["candidate_sha256"]
                or scout.get("bucket") not in BUCKETS
                or scout.get("human_verdict") != "accepted"
            ):
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
    if missing_scouts and status == "complete":
        status = "partial"
        failure = "php_scout_evidence_missing"
        code = 2
    payload = {
        "status": status, "failure_kind": failure, "analysis": {"php": facts},
        "summary": dict(sorted(Counter(row["bucket"] for row in findings).items())),
        "human_scout_accounting": {
            "candidates_total": len(candidates), "graded": len(findings), "ungraded": len(missing_scouts),
        },
        "missing_scouts": missing_scouts, "findings": findings,
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "omnibus.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in detections))
    _atomic(output / "candidates.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates))
    _atomic(output / "scan.json", json.dumps({"status": status, "failure_kind": failure, "php": facts}, indent=2, sort_keys=True) + "\n")
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = ["# Omnibus audit", "", f"Status: `{status}`", f"Analyzer: `{facts['analyzer']}`", ""]
    lines.extend(f"- `{row['file']}` — `{row['bucket']}`; {row['recommendation']}" for row in findings)
    if missing_scouts:
        lines.append("- Missing or stale scout evidence: " + ", ".join(missing_scouts))
    lines.append("- PHP name clusters are syntax leads; human judgment owns domain and decomposition decisions.")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    print(f"[detect_omnibus] wrote {output / 'omnibus.jsonl'} ({len(detections)} candidates)")
    print(f"[collapse] wrote {output / 'candidates.jsonl'} ({len(candidates)} candidates)")
    print(f"[report] wrote {output / 'report.md'} ({len(findings)} scout-graded findings)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
