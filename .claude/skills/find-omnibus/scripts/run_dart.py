#!/usr/bin/env python3
"""Carry Dart syntax nominees through mandatory human omnibus scout grading."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

sys.dont_write_bytecode = True


ARTIFACTS = ("omnibus.jsonl", "candidates.jsonl", "findings.json", "report.md", "scan.json")
GENERIC = frozenset(
    {
        "load",
        "save",
        "read",
        "write",
        "validate",
        "authorize",
        "render",
        "rotate",
        "find",
        "get",
        "set",
        "create",
        "update",
        "delete",
        "process",
        "handle",
    }
)
BUCKETS = frozenset(
    {"confirmed_omnibus", "borderline", "coordination_omnibus", "facets_not_domains"}
)


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
            consumer="find-omnibus",
            required_fact_groups=("declarations",),
        )
    except support.SnapshotError as exc:
        return support.terminal(exc.status, exc.failure_kind, str(exc))


def _safe_output(root: Path, requested: Path) -> Path:
    configured = root / "reports/omnibus"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError("output must be a run directory below reports/omnibus") from exc
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


def _cluster(name: str) -> str:
    words = [word for word in re.split(r"_+|(?<=[a-z])(?=[A-Z])", name) if word]
    specific = [word.casefold() for word in words if word.casefold() not in GENERIC]
    return specific[-1] if specific else words[-1].casefold()


def _candidates(snapshot: dict[str, Any], root: Path, target: str) -> list[dict[str, Any]]:
    if snapshot["status"] != "complete":
        return []
    candidates: list[dict[str, Any]] = []
    for file in snapshot["provider"]["files"]:
        if not _selected(file["file"], root, target):
            continue
        source = (root / file["file"]).read_bytes()
        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for declaration in file["declarations"]:
            if not (
                declaration["top_level"]
                and declaration["kind"] == "top_level_function"
                and not declaration["private"]
                and declaration["supported"]
                and declaration["name"]
            ):
                continue
            offset, end = declaration["offset"], declaration["end"]
            clusters[_cluster(declaration["name"])].append(
                {
                    "name": declaration["name"],
                    "kind": declaration["kind"],
                    "span": {
                        "offset": offset,
                        "end": end,
                        "line": declaration["line"],
                        "end_line": declaration["end_line"],
                    },
                    "spelling_sha256": _hash(source[offset:end]),
                }
            )
        paired = {
            cluster: sorted(rows, key=lambda row: (row["span"]["offset"], row["name"]))
            for cluster, rows in sorted(clusters.items())
            if len(rows) >= 2
        }
        if len(paired) < 4:
            continue
        declarations = [row for rows in paired.values() for row in rows]
        material = {
            "file": file["file"],
            "source_sha256": file["source_sha256"],
            "clusters": {name: [row["name"] for row in rows] for name, rows in paired.items()},
            "declarations": declarations,
        }
        digest = _canonical_hash(material)
        candidates.append(
            {
                "candidate_id": f"DART-OMN-{digest[:12].upper()}",
                "candidate_sha256": digest,
                "language": "dart",
                "analyzer": snapshot["provider"]["analyzer"],
                **material,
                "cluster_count": len(paired),
                "and_count": len(paired) - 1,
                "srp_sentence": "This file handles " + " and ".join(sorted(paired)) + ".",
                "nomination_only": True,
            }
        )
    candidates.sort(key=lambda row: (-row["cluster_count"], row["file"]))
    return candidates


def _grade(
    candidates: list[dict[str, Any]], scout_dir: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    graded: list[dict[str, Any]] = []
    ungraded: list[str] = []
    for candidate in candidates:
        scout_path = scout_dir / f"{candidate['candidate_id']}.json"
        try:
            scout = json.loads(scout_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ungraded.append(candidate["candidate_id"])
            continue
        if (
            scout.get("schema_version") != "dart-omnibus-scout-v1"
            or scout.get("candidate_id") != candidate["candidate_id"]
            or scout.get("candidate_sha256") != candidate["candidate_sha256"]
            or scout.get("bucket") not in BUCKETS
            or scout.get("human_verdict") != "accepted"
            or not isinstance(scout.get("rationale"), str)
            or not scout["rationale"].strip()
        ):
            ungraded.append(candidate["candidate_id"])
            continue
        recommendation = {
            "confirmed_omnibus": "/refactor-subsystem <spec-id>",
            "coordination_omnibus": "/map-product-workflow",
            "borderline": "measure responsibility-change evidence before decomposition",
            "facets_not_domains": "keep cohesive library",
        }[scout["bucket"]]
        graded.append({**candidate, **scout, "recommendation": recommendation})
    graded.sort(key=lambda row: row["file"])
    return graded, ungraded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scout-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        output = _safe_output(root, args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)
    if args.scout_dir.resolve() != (output / "scout").resolve():
        shutil.rmtree(output / "scout", ignore_errors=True)

    snapshot = _load(args)
    candidates = _candidates(snapshot, root, args.target)
    graded, ungraded = _grade(candidates, args.scout_dir)
    status, failure_kind = snapshot["status"], snapshot["failure_kind"]
    if status == "complete" and ungraded:
        status, failure_kind = "partial", "human_scout_required"
    confirmed = [row for row in graded if row["bucket"] == "confirmed_omnibus"]
    accounting = {
        "candidates_total": len(candidates),
        "graded": len(graded),
        "ungraded": len(ungraded),
    }
    final = {
        "schema_version": 1,
        "language": "dart",
        "target": args.target,
        "status": status,
        "failure_kind": failure_kind,
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "human_scout_accounting": accounting,
        "ungraded_candidate_ids": ungraded,
        "scout_verdicts": graded,
        "findings": confirmed,
        "limitation": (
            "Syntax nominates only; explicit human domain judgment is mandatory and no "
            "safe split, runtime responsibility, framework, or Flutter behavior is proven."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _atomic(
        output / "candidates.jsonl",
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
    )
    _atomic(
        output / "omnibus.jsonl",
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in confirmed),
    )
    _atomic(output / "findings.json", json.dumps(final, indent=2, sort_keys=True) + "\n")
    _atomic(output / "scan.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    for row in graded:
        scout = {
            key: row[key]
            for key in (
                "schema_version",
                "candidate_id",
                "candidate_sha256",
                "human_verdict",
                "bucket",
                "rationale",
            )
        }
        _atomic(
            output / "scout" / f"{row['candidate_id']}.json",
            json.dumps(scout, indent=2, sort_keys=True) + "\n",
        )
    lines = [
        "# Dart omnibus audit",
        "",
        f"Status: `{status}`",
        f"Failure: `{failure_kind}`",
        f"Candidates: {len(candidates)}; human graded: {len(graded)}; ungraded: {len(ungraded)}",
        "",
    ]
    lines.extend(
        f"- `{row['file']}` — `{row['bucket']}`; {row['recommendation']}" for row in graded
    )
    if ungraded:
        lines.append("- Ungraded candidates are not findings: " + ", ".join(ungraded))
    if snapshot["status"] != "complete":
        lines.append("- Provider evidence is incomplete; no clean conclusion is available.")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    print(output / "report.md")
    return 0 if status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
