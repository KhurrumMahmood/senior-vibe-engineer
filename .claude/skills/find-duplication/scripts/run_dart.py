#!/usr/bin/env python3
"""Produce exact token-normalized Dart named-body clone evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

sys.dont_write_bytecode = True


MINIMUM_BODY_LINES = 5
ELIGIBLE_KINDS = frozenset({"top_level_function", "method"})
ARTIFACTS = ("collapsed.json", "ranked.json", "triage.md", "findings.json", "scan.json")


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(payload: Any) -> str:
    return _hash(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


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


def _support() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_dart/scripts/dart_d3_snapshot.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("dart_d3_snapshot", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dart_d3_snapshot"] = module
    spec.loader.exec_module(module)
    return module


def _load(args: argparse.Namespace) -> dict[str, Any]:
    support = _support()
    if support is None:
        return {
            "schema_version": 1,
            "analyzer": "dart-d3-union-syntax-snapshot-v1",
            "status": "partial",
            "failure_kind": "dart_d3_snapshot_companion_missing",
            "provider": {"files": [], "inventory": [], "source_manifest": {"preserved": True}},
        }
    try:
        return support.load_for_consumer(
            args.facts,
            args.project_root,
            Path(args.target),
            consumer="find-duplication",
            required_fact_groups=("named_bodies", "body_tokens"),
        )
    except support.SnapshotError as exc:
        return support.terminal(exc.status, exc.failure_kind, str(exc))


def _safe_output(root: Path, requested: Path) -> Path:
    configured = root / "reports/duplication"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError("output must be a run directory below reports/duplication") from exc
    if not relative.parts:
        raise ValueError("output must name a run directory")
    current = configured
    for path in (root / "reports", configured):
        if path.is_symlink():
            raise ValueError("report ancestors must not be symlinks")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output must not resolve through a symlink")
    return output


def _selected(file: str, root: Path, target: str) -> bool:
    requested = (root / target).resolve()
    source = (root / file).resolve()
    return source == requested or requested in source.parents


def _findings(snapshot: dict[str, Any], root: Path, target: str) -> list[dict[str, Any]]:
    if snapshot["status"] != "complete":
        return []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for file in snapshot["provider"]["files"]:
        if not _selected(file["file"], root, target):
            continue
        source = (root / file["file"]).read_bytes()
        tokens_by_body: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for token in file["body_tokens"]:
            tokens_by_body[token["declaration_offset"]].append(token)
        for body in file["named_bodies"]:
            line_count = body["body_end_line"] - body["body_line"] + 1
            if body["kind"] not in ELIGIBLE_KINDS or line_count < MINIMUM_BODY_LINES:
                continue
            tokens = sorted(
                tokens_by_body[body["declaration_offset"]], key=lambda row: row["index"]
            )
            normalized = [[row["token_kind"], row["lexeme"]] for row in tokens]
            digest = _canonical_hash(normalized)
            groups[digest].append(
                {
                    "file": file["file"],
                    "symbol": body["name"],
                    "kind": body["kind"],
                    "container": body["container"],
                    "start_line": body["body_line"],
                    "end_line": body["body_end_line"],
                    "line_count": line_count,
                    "declaration_span": {
                        "offset": body["declaration_offset"],
                        "end": body["declaration_end"],
                    },
                    "body_span": {"offset": body["body_offset"], "end": body["body_end"]},
                    "source_sha256": file["source_sha256"],
                    "spelling_sha256": _hash(
                        source[body["declaration_offset"] : body["declaration_end"]]
                    ),
                    "body_sha256": _hash(source[body["body_offset"] : body["body_end"]]),
                    "token_count": len(tokens),
                }
            )
    findings: list[dict[str, Any]] = []
    for digest, sites in sorted(groups.items()):
        if len(sites) < 2:
            continue
        sites.sort(key=lambda row: (row["file"], row["declaration_span"]["offset"]))
        multiplicity = len(sites)
        priority = round(multiplicity * 1.5, 2)
        findings.append(
            {
                "finding_id": f"DART-DUP-{digest[:12].upper()}",
                "detector": "dart-exact-public-analyzer-body-tokens",
                "shape_hint": (
                    "three_way_plus"
                    if multiplicity >= 3
                    else "cross_file_clone"
                    if len({row["file"] for row in sites}) > 1
                    else "same_file_clone"
                ),
                "multiplicity": multiplicity,
                "shared_lines_min": min(row["line_count"] for row in sites),
                "shared_lines_max": max(row["line_count"] for row in sites),
                "normalized_body_sha256": digest,
                "normalization": "ordered public-analyzer (token_kind, lexeme); trivia excluded",
                "sites": sites,
                "rank_meta": {
                    "priority": priority,
                    "priority_tier": "P1" if priority >= 5 else "P2",
                    "divergence_risk": 1.0,
                    "bug_blast_radius": 1.5,
                    "effective_multiplicity": multiplicity,
                    "effort_hint": "medium" if len({row["file"] for row in sites}) > 1 else "low",
                },
                "consolidation_safety": "unknown_human_review_required",
            }
        )
    findings.sort(key=lambda row: (-row["rank_meta"]["priority"], row["finding_id"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)

    snapshot = _load(args)
    findings = _findings(snapshot, root, args.target)
    tiers = {
        tier: sum(row["rank_meta"]["priority_tier"] == tier for row in findings)
        for tier in ("P0", "P1", "P2")
    }
    scan_meta = {
        "schema_version": 1,
        "language": "dart",
        "target": args.target,
        "project_root": str(root),
        "status": snapshot["status"],
        "failure_kind": snapshot["failure_kind"],
        "analyzer": "dart-exact-public-analyzer-body-tokens",
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "ast_finding_count": len(findings),
        "rank_summary": {key.casefold(): value for key, value in tiers.items()},
    }
    collapsed = {"schema_version": 1, "scan_meta": scan_meta, "findings": findings}
    ranked = dict(collapsed)
    final = {
        "schema_version": 1,
        "scan_meta": scan_meta,
        "findings": findings,
        "dormant_candidates": [],
        "limitation": (
            "Exact token-normalized syntax clones only; no behavioral equivalence, callers, "
            "ownership, consolidation safety, framework, or Flutter claim."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(output / "collapsed.json", json.dumps(collapsed, indent=2, sort_keys=True) + "\n")
    _atomic(output / "ranked.json", json.dumps(ranked, indent=2, sort_keys=True) + "\n")
    _atomic(output / "findings.json", json.dumps(final, indent=2, sort_keys=True) + "\n")
    _atomic(output / "scan.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Duplication triage — Dart",
        "",
        f"Status: `{snapshot['status']}`",
        f"Failure: `{snapshot['failure_kind']}`",
        "",
        "> Exact public-analyzer token clone evidence. Do not consolidate automatically; "
        "behavior, callers, protocol, and ownership require human review.",
        "",
        f"## Priority clusters ({len(findings)})",
        "",
    ]
    for finding in findings:
        lines.append(f"### `{finding['finding_id']}`")
        lines.extend(
            f"- `{site['file']}::{site['symbol']}` ({site['start_line']}-{site['end_line']})"
            for site in finding["sites"]
        )
        lines.append("")
    if not findings:
        lines.append(
            "No exact clone evidence reached the five-line threshold."
            if snapshot["status"] == "complete"
            else "Incomplete evidence; no clean conclusion is available."
        )
    _atomic(output / "triage.md", "\n".join(lines) + "\n")
    print(output / "triage.md")
    return 0 if snapshot["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
