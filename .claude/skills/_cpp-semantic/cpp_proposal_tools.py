#!/usr/bin/env python3
"""Shared content-addressed evidence helpers for bounded C++ proposals."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


class ProposalError(ValueError):
    """A stable proposal refusal."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


def _provider():
    candidates = [Path(__file__).with_name("cpp_semantic_facts.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_semantic_facts.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ semantic fact provider is missing")
    spec = importlib.util.spec_from_file_location("cpp_proposal_semantic_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROVIDER = _provider()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def safe_path(root: Path, supplied: str | Path, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    absolute = Path(os.path.abspath(candidate))
    if not inside(root, absolute):
        raise ProposalError("unsafe_path", f"{label} must stay inside project root")
    current = root
    for part in absolute.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ProposalError("unsafe_path", f"{label} must not traverse a symbolic link")
    return absolute


def output_dir(root: Path, supplied: str | Path, family: str) -> Path:
    path = safe_path(root, supplied, "output")
    allowed = root / "reports" / family
    if path == allowed or not inside(allowed, path):
        raise ProposalError("unsafe_path", f"output must stay beneath reports/{family}/")
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProposalError("evidence_invalid", f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProposalError("evidence_invalid", f"{label} must be an object")
    return payload


def fact_pack(root: Path, supplied: str | Path) -> tuple[Path, dict[str, Any]]:
    path = safe_path(root, supplied, "C++ fact pack")
    payload = load_json(path, "C++ fact pack")
    claimed = payload.get("fact_pack_sha256")
    unhashed = dict(payload)
    unhashed.pop("fact_pack_sha256", None)
    database = root / "compile_commands.json"
    current_manifest, rows = PROVIDER.source_manifest(root)
    if (
        payload.get("schema_version") != PROVIDER.SCHEMA
        or payload.get("language") != "cpp"
        or payload.get("status") != "complete"
        or payload.get("read_only") is not True
        or claimed != canonical_hash(unhashed)
    ):
        raise ProposalError("evidence_invalid", "complete content-addressed C++ facts required")
    if (
        payload.get("source_manifest_sha256") != current_manifest
        or payload.get("source_files") != rows
        or not database.is_file()
        or sha256(database) != payload.get("compile_database", {}).get("sha256")
        or payload.get("compile_database", {}).get("state") != "valid-current-complete-c++20"
    ):
        raise ProposalError("evidence_stale", "C++ fact pack source or compile database changed")
    return path, payload


def audited_sources(root: Path) -> list[dict[str, str]]:
    _digest, rows = PROVIDER.source_manifest(root)
    return rows


def validate_source_rows(root: Path, rows: Any) -> None:
    if rows != audited_sources(root):
        raise ProposalError("evidence_stale", "accepted C++ source census changed")


def run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"command": argv, "returncode": 124, "stdout": "", "stderr": str(exc)}
    return {
        "command": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-6000:],
    }


def native_proof(root: Path, clangxx: str, make: str) -> dict[str, Any]:
    tested = run([make, "clean", "compile-db", "test", f"CXX={clangxx}"], root)
    smoke_path = root / ".native-build/cpp-semantic-smoke"
    smoke = run([str(smoke_path)], root) if tested["returncode"] == 0 else {
        "command": [str(smoke_path)], "returncode": 125, "stdout": "", "stderr": "build failed"
    }
    return {"test": tested, "smoke": smoke, "passed": tested["returncode"] == 0 and smoke["returncode"] == 0}


def project_copy(root: Path, destination: Path) -> Path:
    shutil.copytree(
        root,
        destination,
        ignore=shutil.ignore_patterns(".git", ".native-build", "reports", "compile_commands.json"),
    )
    return destination


def apply_replacements(root: Path, replacements: list[dict[str, str]]) -> None:
    by_path: dict[str, list[dict[str, str]]] = {}
    for row in replacements:
        relative = row.get("path")
        before, after = row.get("before"), row.get("after")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(before, str)
            or not before
            or not isinstance(after, str)
            or before == after
        ):
            raise ProposalError("mutation_plan_invalid", "replacement row is malformed")
        by_path.setdefault(relative, []).append(row)
    for relative, rows in by_path.items():
        path = safe_path(root, relative, "replacement path")
        text = path.read_text(encoding="utf-8")
        for row in rows:
            if text.count(row["before"]) != 1:
                raise ProposalError("mutation_plan_stale", f"replacement anchor changed: {relative}")
            text = text.replace(row["before"], row["after"], 1)
        path.write_text(text, encoding="utf-8")


def _atomic_text(path: Path, text: str) -> None:
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def replace_bundle(output: Path, files: dict[str, str]) -> dict[str, str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    staged.mkdir()
    hashes = {}
    try:
        for name, content in files.items():
            _atomic_text(staged / name, content)
            hashes[name] = sha256(staged / name)
        if output.exists():
            output.replace(backup)
        try:
            staged.replace(output)
        except OSError:
            if backup.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return hashes


def json_text(payload: dict[str, Any], hash_field: str = "artifact_sha256") -> str:
    value = dict(payload)
    value[hash_field] = canonical_hash(value)
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
