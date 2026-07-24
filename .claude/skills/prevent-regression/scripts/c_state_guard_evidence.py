"""Small accepted-evidence and artifact helper for the C exact-field guard."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


class EvidenceError(ValueError):
    """One stable refusal kind for accepted C guard evidence."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def safe_path(root: Path, supplied: str | Path, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    absolute = Path(os.path.abspath(candidate))
    if not inside(root, absolute):
        raise EvidenceError("unsafe_path", f"{label} must stay inside project root")
    current = root
    for part in absolute.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise EvidenceError("unsafe_path", f"{label} must not traverse a symbolic link")
    return absolute


def artifact(root: Path, supplied: str | Path, label: str, family: str) -> Path:
    path = safe_path(root, supplied, label)
    allowed = root / "reports" / family
    if path == allowed or not inside(allowed, path):
        raise EvidenceError("unsafe_path", f"{label} must stay beneath reports/{family}/")
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError("evidence_invalid", f"cannot read {label}: {error}") from error
    if not isinstance(payload, dict):
        raise EvidenceError("evidence_invalid", f"{label} must be a JSON object")
    return payload


def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def replace_bundle(destination: Path, files: dict[str, str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for relative, text in files.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        shutil.rmtree(destination, ignore_errors=True)
        temporary.replace(destination)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_sources(root: Path, rows: Any, *, kind: str) -> dict[str, str]:
    if not isinstance(rows, list) or not rows:
        raise EvidenceError("migration_invalid", "accepted migrated source hashes are missing")
    output: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceError("migration_invalid", "accepted migrated source hashes are malformed")
        relative, digest = row.get("path"), row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or len(digest) != 64
            or relative in output
        ):
            raise EvidenceError("migration_invalid", "accepted migrated source hashes are malformed")
        path = safe_path(root, relative, "accepted migrated source")
        if not path.is_file() or path.is_symlink() or sha256(path) != digest:
            raise EvidenceError(kind, f"accepted migrated source is stale: {relative}")
        output[relative] = digest
    return output


def source_snapshot(root: Path) -> dict[str, str]:
    excluded = {".git", ".native-build", "reports"}
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if excluded & set(relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = sha256(path)
    return rows
