#!/usr/bin/env python3
"""Prepare and verify pinned real repositories in a disposable local cache."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / ".claude" / "tasks" / "real-repository-corpus.json"
DEFAULT_CACHE_ROOT = REPO_ROOT / ".engineering" / "local" / "real-repo-corpus"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
HTTPS_GITHUB_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+(?:\.git)?$")


class CorpusError(ValueError):
    """The corpus declaration or prepared checkout is unsafe or inconsistent."""


@dataclass(frozen=True)
class CorpusEntry:
    """One pinned external repository used as validation input."""

    name: str
    source: str
    revision: str
    language: str
    license: str
    slice: int

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        allow_local_source: bool = False,
    ) -> "CorpusEntry":
        if not isinstance(payload, dict):
            raise CorpusError("repository entry must be an object")
        expected = {"name", "source", "revision", "language", "license", "slice"}
        unknown = sorted(set(payload) - expected)
        missing = sorted(expected - set(payload))
        if unknown or missing:
            raise CorpusError(
                f"repository entry fields mismatch: missing={missing}, unknown={unknown}"
            )
        values = {key: payload[key] for key in expected}
        if not all(isinstance(values[key], str) for key in expected - {"slice"}):
            raise CorpusError("repository string fields must be strings")
        if isinstance(values["slice"], bool) or not isinstance(values["slice"], int):
            raise CorpusError("repository slice must be an integer")
        entry = cls(**values)  # type: ignore[arg-type]
        entry.validate(allow_local_source=allow_local_source)
        return entry

    def validate(self, *, allow_local_source: bool = False) -> None:
        if not NAME_RE.fullmatch(self.name):
            raise CorpusError(f"unsafe repository name: {self.name!r}")
        if not REVISION_RE.fullmatch(self.revision):
            raise CorpusError(f"revision must be 40 lowercase hex characters: {self.name}")
        if not self.language or self.language != self.language.lower():
            raise CorpusError(f"language must be a lowercase label: {self.name}")
        if not self.license.strip():
            raise CorpusError(f"license expectation is empty: {self.name}")
        if self.slice < 1:
            raise CorpusError(f"slice must be positive: {self.name}")
        if not allow_local_source and not HTTPS_GITHUB_RE.fullmatch(self.source):
            raise CorpusError(f"source must be an HTTPS GitHub repository: {self.name}")

    def to_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "license": self.license,
            "name": self.name,
            "revision": self.revision,
            "slice": self.slice,
            "source": self.source,
        }


def load_manifest(
    path: Path,
    *,
    allow_local_source: bool = False,
) -> tuple[CorpusEntry, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusError(f"cannot read corpus manifest: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CorpusError("corpus manifest must be a schema-version-1 object")
    if set(payload) != {"schema_version", "repositories"}:
        raise CorpusError("corpus manifest has unknown or missing top-level fields")
    rows = payload.get("repositories")
    if not isinstance(rows, list) or not rows:
        raise CorpusError("corpus manifest repositories must be a non-empty list")
    entries = tuple(
        CorpusEntry.from_payload(row, allow_local_source=allow_local_source)
        for row in rows
    )
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise CorpusError("corpus repository names must be unique")
    return entries


def _selected(
    entries: Iterable[CorpusEntry],
    *,
    names: set[str],
    slice_number: int | None,
) -> tuple[CorpusEntry, ...]:
    available = {entry.name for entry in entries}
    missing = sorted(names - available)
    if missing:
        raise CorpusError(f"unknown corpus repositories: {', '.join(missing)}")
    selected = tuple(
        entry
        for entry in entries
        if (not names or entry.name in names)
        and (slice_number is None or entry.slice == slice_number)
    )
    if not selected:
        raise CorpusError("selection matched no corpus repositories")
    return selected


def _safe_cache_root(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        resolved = expanded.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise CorpusError(f"cache root cannot be resolved: {path}") from exc
    forbidden = {Path("/").resolve(), Path.home().resolve(), REPO_ROOT.resolve()}
    if resolved in forbidden or resolved in REPO_ROOT.resolve().parents:
        raise CorpusError(f"unsafe cache root: {resolved}")
    current = resolved
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink():
        raise CorpusError(f"cache root ancestor is a symlink: {current}")
    if resolved.exists() and (resolved.is_symlink() or not resolved.is_dir()):
        raise CorpusError(f"cache root must be a real directory: {resolved}")
    return resolved


def _git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120.0,
) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CorpusError(f"git command failed to run: git {' '.join(args)}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise CorpusError(f"git {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed.stdout.strip()


def _license_files(destination: Path) -> list[str]:
    prefixes = ("license", "licence", "copying")
    return sorted(
        candidate.relative_to(destination).as_posix()
        for candidate in destination.iterdir()
        if candidate.is_file()
        and not candidate.is_symlink()
        and candidate.name.lower().startswith(prefixes)
    )


def verify_entry(entry: CorpusEntry, cache_root: Path) -> dict[str, object]:
    destination = cache_root / entry.name
    if destination.is_symlink() or not destination.is_dir():
        raise CorpusError(f"prepared repository is missing or unsafe: {entry.name}")
    if not (destination / ".git").is_dir():
        raise CorpusError(f"prepared repository is not a Git checkout: {entry.name}")
    head = _git(["rev-parse", "HEAD"], cwd=destination)
    if head != entry.revision:
        raise CorpusError(
            f"prepared revision mismatch for {entry.name}: expected {entry.revision}, got {head}"
        )
    source = _git(["remote", "get-url", "origin"], cwd=destination)
    if source != entry.source:
        raise CorpusError(
            f"prepared source mismatch for {entry.name}: expected {entry.source}, got {source}"
        )
    status = _git(["status", "--porcelain", "--untracked-files=all"], cwd=destination)
    if status:
        raise CorpusError(f"prepared repository is dirty: {entry.name}: {status.splitlines()[0]}")
    licenses = _license_files(destination)
    if not licenses:
        raise CorpusError(f"prepared repository has no root license file: {entry.name}")
    return {
        **entry.to_dict(),
        "destination": str(destination),
        "license_files": licenses,
        "status": "verified",
    }


def prepare_entry(
    entry: CorpusEntry,
    cache_root: Path,
    *,
    allow_local_source: bool = False,
) -> dict[str, object]:
    entry.validate(allow_local_source=allow_local_source)
    destination = cache_root / entry.name
    if destination.exists() or destination.is_symlink():
        result = verify_entry(entry, cache_root)
        result["status"] = "reused"
        return result
    cache_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{entry.name}.", dir=cache_root))
    try:
        _git(["init", "--quiet"], cwd=temporary)
        _git(["remote", "add", "origin", entry.source], cwd=temporary)
        _git(["fetch", "--quiet", "--depth", "1", "origin", entry.revision], cwd=temporary)
        _git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=temporary)
        head = _git(["rev-parse", "HEAD"], cwd=temporary)
        if head != entry.revision:
            raise CorpusError(
                f"fetched revision mismatch for {entry.name}: expected {entry.revision}, got {head}"
            )
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    result = verify_entry(entry, cache_root)
    result["status"] = "prepared"
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "prepare", "verify"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--name", action="append", default=[])
    parser.add_argument("--slice", type=int, dest="slice_number")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        entries = load_manifest(args.manifest.resolve())
        selected = _selected(
            entries,
            names=set(args.name),
            slice_number=args.slice_number,
        )
        if args.command == "list":
            payload: dict[str, Any] = {
                "repositories": [entry.to_dict() for entry in selected],
                "schema_version": 1,
            }
        else:
            cache_root = _safe_cache_root(args.cache_root)
            operation = prepare_entry if args.command == "prepare" else verify_entry
            payload = {
                "cache_root": str(cache_root),
                "repositories": [operation(entry, cache_root) for entry in selected],
                "schema_version": 1,
            }
    except CorpusError as exc:
        print(f"real-repo-corpus: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
