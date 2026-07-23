#!/usr/bin/env python3
"""Write frozen Dart direct-body branch scores and final hotspot artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

sys.dont_write_bytecode = True


BRANCH_THRESHOLD = 18
ELIGIBLE_KINDS = frozenset({"top_level_function", "method", "operator"})
ARTIFACTS = ("detections.jsonl", "findings.json", "report.md", "scan.json")


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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
            consumer="find-complexity-hotspots",
            required_fact_groups=("named_bodies", "direct_body_branches"),
        )
    except support.SnapshotError as exc:
        return support.terminal(exc.status, exc.failure_kind, str(exc))


def _safe_output(root: Path, requested: Path) -> Path:
    configured = root / "reports/find-complexity-hotspots"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError(
            "output must be a run directory below reports/find-complexity-hotspots"
        ) from exc
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
    findings: list[dict[str, Any]] = []
    for file in snapshot["provider"]["files"]:
        if not _selected(file["file"], root, target):
            continue
        source = (root / file["file"]).read_bytes()
        events: dict[int, list[dict[str, Any]]] = {}
        for row in file["direct_body_branches"]:
            event = {
                "kind": row["kind"],
                "offset": row["offset"],
                "end": row["end"],
                "line": row["line"],
                "column": row["column"],
                "spelling_sha256": _hash(source[row["offset"] : row["end"]]),
            }
            events.setdefault(row["declaration_offset"], []).append(event)
        for body in file["named_bodies"]:
            if body["kind"] not in ELIGIBLE_KINDS:
                continue
            branch_events = events.get(body["declaration_offset"], [])
            score = len(branch_events)
            if score < BRANCH_THRESHOLD:
                continue
            declaration = source[body["declaration_offset"] : body["declaration_end"]]
            body_source = source[body["body_offset"] : body["body_end"]]
            findings.append(
                {
                    "pattern": "high-branch-function",
                    "language": "dart",
                    "analyzer": snapshot["provider"]["analyzer"],
                    "file": file["file"],
                    "function": body["name"],
                    "kind": body["kind"],
                    "container": body["container"],
                    "lineno": body["body_line"],
                    "end_lineno": body["body_end_line"],
                    "loc": body["body_end_line"] - body["body_line"] + 1,
                    "branch_score": score,
                    "threshold": BRANCH_THRESHOLD,
                    "declaration_span": {
                        "offset": body["declaration_offset"],
                        "end": body["declaration_end"],
                    },
                    "body_span": {"offset": body["body_offset"], "end": body["body_end"]},
                    "source_sha256": file["source_sha256"],
                    "spelling_sha256": _hash(declaration),
                    "body_sha256": _hash(body_source),
                    "branch_events": branch_events,
                    "summary": (
                        "frozen direct-body syntax score; nested closures/local functions "
                        "are excluded and runtime cost remains unmeasured"
                    ),
                }
            )
    findings.sort(key=lambda row: (-row["branch_score"], row["file"], row["lineno"]))
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
    latest = output.parent / "latest"
    latest.unlink(missing_ok=True)
    for name in ARTIFACTS:
        (output / name).unlink(missing_ok=True)

    snapshot = _load(args)
    findings = _findings(snapshot, root, args.target)
    outcome = (
        "measure-first"
        if snapshot["status"] == "complete" and findings
        else "no-hotspots"
        if snapshot["status"] == "complete"
        else "incomplete"
    )
    payload = {
        "schema_version": 1,
        "skill": "find-complexity-hotspots",
        "language": "dart",
        "target": args.target,
        "status": snapshot["status"],
        "failure_kind": snapshot["failure_kind"],
        "outcome": outcome,
        "threshold": BRANCH_THRESHOLD,
        "summary": {"findings_total": len(findings), "high-branch-function": len(findings)},
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "findings": findings,
        "limitation": (
            "Advisory direct-body syntax score only; no patterns, scheduling, dispatch, "
            "runtime frequency/cost, framework, or Flutter behavior."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    _atomic(output / "detections.jsonl", jsonl)
    _atomic(output / "findings.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(output / "scan.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Dart complexity hotspot audit",
        "",
        f"Status: `{snapshot['status']}`",
        f"Failure: `{snapshot['failure_kind']}`",
        f"Frozen branch threshold: {BRANCH_THRESHOLD}",
        f"Findings: {len(findings)}",
        "",
    ]
    lines.extend(
        f"- `{row['file']}:{row['lineno']}` `{row['function']}` — direct branch score {row['branch_score']}"
        for row in findings
    )
    if snapshot["status"] != "complete":
        lines.append("- Incomplete evidence; no clean conclusion is available.")
    _atomic(output / "report.md", "\n".join(lines) + "\n")
    if snapshot["status"] == "complete":
        try:
            latest.symlink_to(output.name)
        except OSError:
            pass
    print(output / "report.md")
    return 0 if snapshot["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
