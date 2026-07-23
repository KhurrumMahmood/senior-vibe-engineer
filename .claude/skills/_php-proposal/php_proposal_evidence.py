#!/usr/bin/env python3
"""Accepted PHP evidence, native preflight, and terminal artifact mechanics.

This module validates evidence produced elsewhere.  It never detects a state
candidate, boundary, folder cluster, or semantic shadow.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MINIMUM_PHP = (8, 1, 0)
MINIMUM_COMPOSER = (2, 2, 0)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(ValueError):
    """A bounded accepted-evidence or native-preflight refusal."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def safe_path(root: Path, supplied: str | Path, label: str, *, exists: bool = True) -> Path:
    root = root.resolve()
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    normalized = Path(os.path.abspath(candidate))
    if not _inside(root, normalized):
        raise EvidenceError("unsafe_path", f"{label} must stay inside the project root")
    cursor = root
    for part in normalized.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise EvidenceError("symlink_path", f"{label} must not traverse a symbolic link")
        if not cursor.exists():
            break
    if exists and not normalized.exists():
        raise EvidenceError("evidence_missing", f"{label} is missing: {supplied}")
    return normalized


def output_dir(root: Path, supplied: str | Path, consumer: str) -> Path:
    path = safe_path(root, supplied, "output directory", exists=False)
    allowed = root.resolve() / "reports" / consumer
    if path == allowed or not _inside(allowed, path):
        raise EvidenceError(
            "unsafe_output", f"output directory must stay beneath reports/{consumer}/"
        )
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError("evidence_malformed", f"cannot read {label}: {error}") from error
    if not isinstance(payload, dict):
        raise EvidenceError("evidence_malformed", f"{label} must be a JSON object")
    return payload


def _version(text: str) -> tuple[int, int, int]:
    match = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b", text)
    return (0, 0, 0) if match is None else tuple(int(item or 0) for item in match.groups())


def _tool(supplied: str | Path, label: str, minimum: tuple[int, int, int]) -> dict[str, str]:
    raw = str(supplied)
    path = str(Path(raw).resolve()) if Path(raw).is_file() else shutil.which(raw)
    if not path:
        raise EvidenceError(f"{label}_missing", f"{label} executable is missing")
    try:
        command = [path, "--version"] if label == "php" else [path, "--version"]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceError(f"{label}_probe_failed", str(error)) from error
    rendered = (result.stdout + result.stderr).strip()
    if result.returncode:
        raise EvidenceError(f"{label}_probe_failed", rendered or f"{label} probe failed")
    if _version(rendered) < minimum:
        required = ".".join(str(item) for item in minimum)
        raise EvidenceError(f"{label}_too_old", f"{label} >= {required} is required")
    return {"path": path, "version": rendered.splitlines()[0] if rendered else "unknown"}


def _run(command: list[str], root: Path, kind: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceError(kind, str(error)) from error
    record = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }
    if result.returncode:
        raise EvidenceError(kind, result.stderr.strip() or result.stdout.strip() or kind)
    return record


def source_hashes(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if {".git", "reports", "reviews"} & set(relative.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows[relative.as_posix()] = sha256(path)
    return rows


def _source_records(value: Any) -> dict[str, str]:
    records: dict[str, str] = {}
    if isinstance(value, dict):
        relative, digest = value.get("file"), value.get("source_sha256")
        if isinstance(relative, str) and isinstance(digest, str) and SHA256.fullmatch(digest):
            previous = records.setdefault(relative, digest)
            if previous != digest:
                raise EvidenceError("evidence_tampered", f"conflicting hashes for {relative}")
        for child in value.values():
            for child_path, child_digest in _source_records(child).items():
                previous = records.setdefault(child_path, child_digest)
                if previous != child_digest:
                    raise EvidenceError("evidence_tampered", f"conflicting hashes for {child_path}")
    elif isinstance(value, list):
        for child in value:
            for child_path, child_digest in _source_records(child).items():
                previous = records.setdefault(child_path, child_digest)
                if previous != child_digest:
                    raise EvidenceError("evidence_tampered", f"conflicting hashes for {child_path}")
    return records


def _identity(evidence: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        evidence.get("project_identity"),
        evidence.get("project_resolution", {}).get("composer_identity")
        if isinstance(evidence.get("project_resolution"), dict)
        else None,
        evidence.get("authority", {}).get("project_identity")
        if isinstance(evidence.get("authority"), dict)
        else None,
    ]
    return next((row for row in candidates if isinstance(row, dict)), None)


def _native(
    root: Path,
    evidence: dict[str, Any],
    acceptance: dict[str, Any],
    php: str | Path,
    composer: str | Path,
) -> dict[str, Any]:
    tools = {
        "php": _tool(php, "php", MINIMUM_PHP),
        "composer": _tool(composer, "composer", MINIMUM_COMPOSER),
    }
    checks: dict[str, Any] = {}
    checks["composer_validate"] = _run(
        [
            tools["composer"]["path"], "--no-plugins", "--no-scripts", "validate",
            "--no-check-publish", "--no-interaction",
        ],
        root,
        "composer_validate_failed",
    )
    identity = _identity(evidence)
    composer_json = root / "composer.json"
    if identity is not None:
        expected = identity.get("composer_json_sha256")
        if not isinstance(expected, str) or not composer_json.is_file() or sha256(composer_json) != expected:
            raise EvidenceError("evidence_stale", "Composer identity differs from accepted evidence")
    for relative in sorted(_source_records(evidence)):
        if {".git", "reports", "reviews"} & set(Path(relative).parts):
            continue
        source = safe_path(root, relative, "evidence source")
        if source.suffix == ".php":
            checks[f"lint:{relative}"] = _run(
                [tools["php"]["path"], "-l", str(source)], root, "php_lint_failed"
            )
    native = acceptance.get("native")
    if not isinstance(native, dict):
        raise EvidenceError("acceptance_incomplete", "accepted native obligations are missing")
    lint, smoke, expected = native.get("lint"), native.get("smoke"), native.get("smoke_stdout")
    if not all(isinstance(item, str) and item for item in (lint, smoke, expected)):
        raise EvidenceError("acceptance_incomplete", "native lint/smoke obligations are incomplete")
    try:
        composer_manifest = json.loads(composer_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError("composer_manifest_invalid", str(error)) from error
    declared_scripts = composer_manifest.get("scripts", {})
    if (
        not isinstance(declared_scripts, dict)
        or declared_scripts.get("lint") != f"@php {lint}"
        or declared_scripts.get("test") != f"@php {smoke}"
    ):
        raise EvidenceError(
            "acceptance_incomplete", "native scripts must match Composer-owned lint/test obligations"
        )
    for label, relative in (("project_lint", lint), ("project_smoke", smoke)):
        script = safe_path(root, relative, label)
        if script.suffix != ".php":
            raise EvidenceError("acceptance_incomplete", f"{label} must be a PHP script")
        checks[label] = _run([tools["php"]["path"], str(script)], root, f"{label}_failed")
    if checks["project_smoke"]["stdout"].strip() != expected:
        raise EvidenceError("project_smoke_failed", "project smoke output differs from acceptance")
    return {"tools": tools, "checks": checks}


def _native_disposable(
    root: Path,
    evidence: dict[str, Any],
    acceptance: dict[str, Any],
    php: str | Path,
    composer: str | Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temporary:
        copy = Path(temporary) / "host"
        shutil.copytree(
            root,
            copy,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", "reports", "reviews"),
        )
        return _native(copy, evidence, acceptance, php, composer)


def validate(
    *,
    root: Path,
    consumer: str,
    evidence_arg: str | Path,
    acceptance_arg: str | Path,
    php: str | Path,
    composer: str | Path,
    allowed_evidence_statuses: set[str] | None = None,
    verify_evidence_sources: bool = True,
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    evidence_path = safe_path(root, evidence_arg, "evidence")
    acceptance_path = safe_path(root, acceptance_arg, "acceptance")
    if "reports" not in evidence_path.relative_to(root).parts:
        raise EvidenceError("unsafe_evidence", "evidence must be a retained report artifact")
    evidence = load_json(evidence_path, "evidence")
    acceptance = load_json(acceptance_path, "acceptance")
    if evidence.get("language") != "php":
        raise EvidenceError("evidence_invalid", "evidence must carry PHP language authority")
    allowed = allowed_evidence_statuses or {"complete"}
    if evidence.get("status") not in allowed:
        raise EvidenceError("evidence_incomplete", "complete accepted producer evidence is required")
    inventory = evidence.get("source_inventory")
    provider_read_only = (
        isinstance(inventory, dict) and inventory.get("source_preserved") is True
    )
    if evidence.get("read_only") is not True and not provider_read_only:
        raise EvidenceError("evidence_invalid", "producer evidence must be read-only")
    if (
        acceptance.get("schema_version") != "php-a4-acceptance-v1"
        or acceptance.get("language") != "php"
        or acceptance.get("status") != "accepted"
        or acceptance.get("consumer") != consumer
    ):
        raise EvidenceError("acceptance_unaccepted", "a current accepted PHP A4 decision is required")
    expected = acceptance.get("evidence_sha256")
    if expected != sha256(evidence_path):
        raise EvidenceError("evidence_stale_or_tampered", "acceptance hash does not match evidence")
    limits = evidence.get("limits", evidence.get("nonclaims", []))
    if acceptance.get("accepted_limits") != limits:
        raise EvidenceError("acceptance_incomplete", "acceptance must preserve producer limits")
    if verify_evidence_sources:
        for relative, digest in _source_records(evidence).items():
            source = safe_path(root, relative, "evidence source")
            if not source.is_file() or sha256(source) != digest:
                raise EvidenceError("evidence_stale", f"accepted evidence is stale for {relative}")
    before = source_hashes(root)
    native = _native_disposable(root, evidence, acceptance, php, composer)
    if source_hashes(root) != before:
        raise EvidenceError("source_mutated", "native evidence changed audited project source")
    return evidence_path, evidence, acceptance, native


def replace_bundle(destination: Path, files: dict[str, str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for relative, text in files.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def begin(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)


def refuse(destination: Path, consumer: str, error: Exception) -> None:
    kind = error.kind if isinstance(error, EvidenceError) else "consumer_failed"
    payload = {
        "schema_version": "php-a4-refusal-v1",
        "language": "php",
        "consumer": consumer,
        "status": "refused",
        "failure_kind": kind,
        "message": str(error),
    }
    replace_bundle(destination, {"refusal.json": json.dumps(payload, indent=2, sort_keys=True) + "\n"})


def json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def native_checks(
    root: Path,
    evidence: dict[str, Any],
    native: dict[str, Any],
    php: str | Path,
    composer: str | Path,
) -> dict[str, Any]:
    """Replay only the accepted native matrix for a validated downstream stage."""
    before = source_hashes(root)
    result = _native_disposable(root, evidence, {"native": native}, php, composer)
    if source_hashes(root) != before:
        raise EvidenceError("source_mutated", "native evidence changed audited project source")
    return result


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}."
    ) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)
