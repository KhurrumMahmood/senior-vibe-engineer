#!/usr/bin/env python3
"""Validate one content-addressed, human-accepted Dart evidence envelope.

This module owns only acceptance, provenance, and freshness checks. Consumers
retain all proposal, rewrite, compatibility, and guard policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA_VERSION = "dart-accepted-evidence-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AcceptedEvidenceError(ValueError):
    """A typed terminal refusal from the accepted-evidence boundary."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _partial(kind: str, detail: str) -> AcceptedEvidenceError:
    return AcceptedEvidenceError("partial", kind, detail)


def _failed(kind: str, detail: str) -> AcceptedEvidenceError:
    return AcceptedEvidenceError("failed", kind, detail)


def canonical_hash(value: Any) -> str:
    """Return the contract's canonical JSON SHA-256."""

    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _root(path: str | Path) -> Path:
    supplied = Path(path)
    if supplied.is_symlink():
        raise _failed("invalid_accepted_evidence", "project root must not be a symbolic link")
    try:
        resolved = Path(os.path.realpath(supplied.resolve(strict=True)))
    except OSError as exc:
        raise _partial("evidence_unavailable", f"project root is unavailable: {exc}") from exc
    if not resolved.is_dir():
        raise _partial("evidence_unavailable", "project root is not a directory")
    return resolved


def _bounded_path(
    boundary: Path,
    supplied: str | Path,
    label: str,
    *,
    must_exist: bool = True,
) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else boundary / raw
    if candidate.is_symlink():
        raise _failed("invalid_accepted_evidence", f"{label} must not be a symbolic link")
    resolved = Path(os.path.realpath(candidate.resolve(strict=False)))
    if not _inside(boundary, resolved):
        raise _failed("invalid_accepted_evidence", f"{label} escapes its declared boundary")
    current = boundary
    try:
        relative = candidate.absolute().relative_to(boundary)
    except ValueError as exc:
        raise _failed("invalid_accepted_evidence", f"{label} escapes its declared boundary") from exc
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise _failed("invalid_accepted_evidence", f"{label} traverses a symbolic link")
    if must_exist and not resolved.is_file():
        raise _partial("evidence_unavailable", f"{label} is unavailable")
    return resolved


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _failed("invalid_accepted_evidence", f"{label} must be a relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise _failed("invalid_accepted_evidence", f"{label} must be a normalized relative path")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise _failed("invalid_accepted_evidence", f"{label} must be a lowercase SHA-256")
    return value


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise _partial("evidence_unavailable", f"{label} is unavailable") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _failed("invalid_accepted_evidence", f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise _failed("invalid_accepted_evidence", f"{label} must contain a JSON object")
    return payload


def _pointer(payload: Any, pointer: Any) -> Any:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise _failed("invalid_accepted_evidence", "selection json_pointer is invalid")
    current = payload
    for raw in pointer.split("/")[1:] if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                if not token.isdigit() or (token != "0" and token.startswith("0")):
                    raise KeyError(token)
                current = current[int(token)]
            elif isinstance(current, dict):
                current = current[token]
            else:
                raise KeyError(token)
        except (KeyError, IndexError) as exc:
            raise _failed(
                "invalid_accepted_evidence", "selection json_pointer does not resolve"
            ) from exc
    return current


def _artifact_map(evidence: Path, rows: Any) -> dict[str, Path]:
    if not isinstance(rows, list) or not rows:
        raise _failed("invalid_accepted_evidence", "accepted evidence artifacts are missing")
    paths: dict[str, Path] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise _failed("invalid_accepted_evidence", "accepted evidence artifacts are malformed")
        relative = _relative_path(row.get("path"), "artifact path")
        expected = _digest(row.get("sha256"), f"artifact hash for {relative}")
        if relative in paths:
            raise _failed("invalid_accepted_evidence", f"duplicate artifact path: {relative}")
        path = _bounded_path(evidence, relative, f"artifact {relative}")
        try:
            actual = _sha256(path)
        except OSError as exc:
            raise _partial("evidence_unavailable", f"artifact {relative} is unavailable") from exc
        if actual != expected:
            raise _failed("invalid_accepted_evidence", f"artifact hash does not verify: {relative}")
        paths[relative] = path
    return paths


def _snapshot_rows(rows: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise _failed("invalid_accepted_evidence", f"{label} hashes are malformed")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise _failed("invalid_accepted_evidence", f"{label} hashes are malformed")
        relative = _relative_path(row.get("path"), f"{label} path")
        digest = _digest(row.get("sha256"), f"{label} hash for {relative}")
        if relative in seen:
            raise _failed("invalid_accepted_evidence", f"duplicate {label} path: {relative}")
        seen.add(relative)
        normalized = {"path": relative, "sha256": digest}
        for key, value in row.items():
            if key not in normalized:
                normalized[key] = value
        result.append(normalized)
    return result


def _verify_snapshot(root: Path, rows: list[dict[str, Any]], label: str) -> None:
    for row in rows:
        path = _bounded_path(
            root, row["path"], f"{label} {row['path']}", must_exist=False
        )
        if not path.is_file():
            raise _failed("stale_accepted_evidence", f"{label} is missing: {row['path']}")
        try:
            actual = _sha256(path)
        except OSError as exc:
            raise _failed(
                "stale_accepted_evidence", f"{label} is unreadable: {row['path']}"
            ) from exc
        if actual != row["sha256"]:
            raise _failed("stale_accepted_evidence", f"{label} is stale: {row['path']}")


def _offset(lines: list[str], line: Any, column: Any, label: str) -> int:
    if not isinstance(line, int) or not isinstance(column, int) or line < 1 or column < 1:
        raise _failed("invalid_accepted_evidence", f"{label} coordinates are invalid")
    if line > len(lines):
        raise _failed("stale_accepted_evidence", f"{label} line is stale")
    content = lines[line - 1]
    line_without_break = content.rstrip("\r\n")
    if column > len(line_without_break) + 1:
        raise _failed("stale_accepted_evidence", f"{label} column is stale")
    return sum(len(item) for item in lines[: line - 1]) + column - 1


def _verify_spans(
    root: Path,
    rows: Any,
    source_paths: set[str],
    *,
    verify_current_sources: bool,
) -> None:
    if not isinstance(rows, list) or not rows:
        raise _failed("invalid_accepted_evidence", "accepted evidence cited spans are missing")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise _failed("invalid_accepted_evidence", "accepted evidence cited spans are malformed")
        relative = _relative_path(row.get("path"), f"cited span {index} path")
        if relative not in source_paths:
            raise _failed(
                "invalid_accepted_evidence", f"cited span lacks a source hash: {relative}"
            )
        expected = _digest(row.get("sha256"), f"cited span {index} hash")
        for key in ("start_line", "start_column", "end_line", "end_column"):
            if not isinstance(row.get(key), int) or row[key] < 1:
                raise _failed(
                    "invalid_accepted_evidence", f"cited span {index} coordinates are invalid"
                )
        if not verify_current_sources:
            continue
        path = _bounded_path(root, relative, f"cited span source {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise _failed("stale_accepted_evidence", f"cited span source is stale: {relative}") from exc
        lines = text.splitlines(keepends=True)
        start = _offset(lines, row.get("start_line"), row.get("start_column"), "span start")
        end = _offset(lines, row.get("end_line"), row.get("end_column"), "span end")
        if end <= start or hashlib.sha256(text[start:end].encode()).hexdigest() != expected:
            raise _failed("stale_accepted_evidence", f"cited span is stale: {relative}")


def _native_obligations(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise _failed("invalid_accepted_evidence", "native obligations are missing")
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise _failed("invalid_accepted_evidence", "native obligations are malformed")
        name, argv = row.get("name"), row.get("argv")
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
            or not isinstance(row.get("expected_returncode"), int)
        ):
            raise _failed("invalid_accepted_evidence", "native obligations are malformed")
        names.add(name)
    return rows


def validate_accepted_evidence(
    project_root: str | Path,
    evidence_dir: str | Path,
    acceptance_path: str | Path,
    *,
    expected_producer: str,
    expected_kind: str | None = None,
    verify_current_sources: bool = True,
) -> dict[str, Any]:
    """Validate one accepted envelope without invoking a Dart analysis tool."""

    root = _root(project_root)
    raw_evidence = Path(evidence_dir)
    evidence_candidate = raw_evidence if raw_evidence.is_absolute() else root / raw_evidence
    if evidence_candidate.is_symlink():
        raise _failed("invalid_accepted_evidence", "evidence directory must not be a symlink")
    evidence = Path(os.path.realpath(evidence_candidate.resolve(strict=False)))
    if not _inside(root, evidence):
        raise _failed("invalid_accepted_evidence", "evidence directory escapes project root")
    if not evidence.is_dir():
        raise _partial("evidence_unavailable", "evidence directory is unavailable")
    acceptance = _bounded_path(evidence, acceptance_path, "acceptance artifact")
    envelope = _json(acceptance, "acceptance artifact")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise _failed("invalid_accepted_evidence", "acceptance schema is incompatible")
    supplied_hash = _digest(envelope.get("acceptance_hash"), "acceptance hash")
    hashed = dict(envelope)
    hashed.pop("acceptance_hash", None)
    if supplied_hash != canonical_hash(hashed):
        raise _failed("invalid_accepted_evidence", "acceptance hash does not verify")

    producer = envelope.get("producer")
    if not isinstance(producer, dict):
        raise _failed("invalid_accepted_evidence", "producer authority is missing")
    if producer.get("skill") != expected_producer:
        raise _failed("unexpected_evidence", "accepted evidence names an unexpected producer")
    if producer.get("terminal_status") != "complete":
        raise _partial("upstream_not_complete", "accepted producer evidence is not complete")
    if any(
        not isinstance(producer.get(key), str) or not producer[key]
        for key in ("version", "schema_version", "artifact")
    ):
        raise _failed("invalid_accepted_evidence", "producer authority is malformed")

    verdict = envelope.get("human_verdict")
    if not isinstance(verdict, dict) or verdict.get("status") != "accepted":
        raise _partial("human_acceptance_required", "human acceptance is absent")
    if any(not isinstance(verdict.get(key), str) or not verdict[key].strip() for key in ("reviewer", "notes")):
        raise _failed("invalid_accepted_evidence", "human acceptance authority is malformed")
    boundaries = envelope.get("reviewed_boundaries")
    if not isinstance(boundaries, dict) or not boundaries:
        raise _failed("invalid_accepted_evidence", "reviewed boundaries are missing")

    artifacts = _artifact_map(evidence, envelope.get("artifacts"))
    producer_artifact = _relative_path(producer["artifact"], "producer artifact")
    if producer_artifact not in artifacts:
        raise _failed("invalid_accepted_evidence", "producer artifact is not hash-bound")
    producer_payload = _json(artifacts[producer_artifact], "producer artifact")
    if (
        producer_payload.get("schema_version") != producer["schema_version"]
        or producer_payload.get("language") != "dart"
        or producer_payload.get("status") != producer["terminal_status"]
    ):
        raise _failed("invalid_accepted_evidence", "producer artifact authority does not verify")

    selection = envelope.get("selection")
    if not isinstance(selection, dict):
        raise _failed("invalid_accepted_evidence", "accepted selection is missing")
    if expected_kind is not None and selection.get("kind") != expected_kind:
        raise _failed("unexpected_evidence", "accepted evidence names an unexpected selection kind")
    if any(not isinstance(selection.get(key), str) or not selection[key] for key in ("kind", "id", "artifact")):
        raise _failed("invalid_accepted_evidence", "accepted selection is malformed")
    selection_artifact = _relative_path(selection["artifact"], "selection artifact")
    if selection_artifact not in artifacts:
        raise _failed("invalid_accepted_evidence", "selection artifact is not hash-bound")
    selected_payload = _json(artifacts[selection_artifact], "selection artifact")
    selected = _pointer(selected_payload, selection.get("json_pointer"))
    expected_selection_hash = _digest(selection.get("sha256"), "selection hash")
    if canonical_hash(selected) != expected_selection_hash:
        raise _failed("invalid_accepted_evidence", "selected evidence hash does not verify")

    source_rows = _snapshot_rows(envelope.get("source_hashes"), "source")
    configuration_rows = _snapshot_rows(envelope.get("configuration_hashes"), "configuration")
    _native_obligations(envelope.get("native_obligations"))
    if verify_current_sources:
        _verify_snapshot(root, source_rows, "source")
        _verify_snapshot(root, configuration_rows, "configuration")
    _verify_spans(
        root,
        envelope.get("cited_spans"),
        {row["path"] for row in source_rows},
        verify_current_sources=verify_current_sources,
    )

    return {
        "envelope": envelope,
        "selected_evidence": selected,
        "current_snapshot_verified": verify_current_sources,
        "verified_artifacts": sorted(artifacts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--acceptance", required=True)
    parser.add_argument("--expected-producer", required=True)
    parser.add_argument("--expected-kind")
    parser.add_argument("--skip-current-source-check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_accepted_evidence(
            args.project_root,
            args.evidence_dir,
            args.acceptance,
            expected_producer=args.expected_producer,
            expected_kind=args.expected_kind,
            verify_current_sources=not args.skip_current_source_check,
        )
    except AcceptedEvidenceError as exc:
        print(
            json.dumps(
                {"status": exc.status, "failure_kind": exc.failure_kind, "detail": exc.detail},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "schema_version": "dart-accepted-evidence-validation-v1",
                "status": "complete",
                "acceptance_hash": result["envelope"]["acceptance_hash"],
                "producer": result["envelope"]["producer"],
                "selection": result["envelope"]["selection"],
                "current_snapshot_verified": result["current_snapshot_verified"],
                "verified_artifacts": result["verified_artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
