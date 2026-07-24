#!/usr/bin/env python3
"""Preview, apply, and restore toolkit-owned host-state migrations.

This is deliberately not a toolkit updater. Git and the stock agent-skill
installer acquire distributed code; this runner changes only the explicitly
declared host-state paths for the ordered schema migrations below.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))
import engineering_home as eh  # noqa: E402


CURRENT_SCHEMA = eh.MANIFEST_VERSION
OLDEST_READABLE_SCHEMA = 1
SUBSYSTEM_REGISTRY_MIGRATION_ID = "0001-subsystem-registry-home"
SUBSYSTEM_MAPS_MIGRATION_ID = "0002-subsystem-maps-home"

LEGACY_REGISTRY = Path(".claude/subsystems.yaml")
CANONICAL_REGISTRY = Path(".engineering/subsystems.yaml")
LEGACY_SUBSYSTEM_MAPS = Path(".claude/docs/subsystems")
CANONICAL_SUBSYSTEM_MAPS = Path(".engineering/docs/subsystems")
MANIFEST = Path(".engineering/manifest.json")
LOCAL_IGNORE = Path(".engineering/.gitignore")

_DECLARED_MIGRATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": SUBSYSTEM_REGISTRY_MIGRATION_ID,
        "from_schema": 1,
        "to_schema": 2,
        "source": LEGACY_REGISTRY,
        "destination": CANONICAL_REGISTRY,
        "kind": "file",
    },
    {
        "id": SUBSYSTEM_MAPS_MIGRATION_ID,
        "from_schema": 2,
        "to_schema": 3,
        "source": LEGACY_SUBSYSTEM_MAPS,
        "destination": CANONICAL_SUBSYSTEM_MAPS,
        "kind": "directory",
    },
)
MIGRATIONS = tuple(
    row for row in _DECLARED_MIGRATIONS if row["to_schema"] <= CURRENT_SCHEMA
)
MIGRATION_IDS = tuple(row["id"] for row in MIGRATIONS)
MIGRATION_BY_ID = {row["id"]: row for row in MIGRATIONS}
MIGRATION_BY_FROM = {row["from_schema"]: row for row in MIGRATIONS}


def _journal_path(migration_id: str) -> Path:
    return Path(f".engineering/local/migrations/{migration_id}.json")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _b64(raw: bytes | None) -> str | None:
    return base64.b64encode(raw).decode("ascii") if raw is not None else None


def _unb64(value: str | None) -> bytes | None:
    return base64.b64decode(value.encode("ascii")) if value is not None else None


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _write_journal(root: Path, journal: dict[str, Any]) -> None:
    _atomic_write(root / _journal_path(journal["migration_id"]), _json_bytes(journal))


def _read_journal(root: Path, migration_id: str) -> dict[str, Any] | None:
    path = root / _journal_path(migration_id)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_manifest(root: Path) -> tuple[dict[str, Any] | None, bytes | None]:
    path = root / MANIFEST
    if not path.exists():
        return None, None
    if path.is_symlink() or not path.is_file():
        raise ValueError("manifest is not a regular file")
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must contain a JSON object")
    return payload, raw


def _write_manifest(root: Path, manifest: dict[str, Any]) -> bytes:
    raw = _json_bytes(manifest)
    _atomic_write(root / MANIFEST, raw)
    return raw


def _schema(manifest: dict[str, Any] | None) -> int:
    if manifest is None:
        return OLDEST_READABLE_SCHEMA
    version = manifest.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("manifest.version must be an integer")
    return version


def _applied_ids(manifest: dict[str, Any] | None) -> list[str]:
    if manifest is None:
        return []
    value = manifest.get("applied_migrations", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("manifest.applied_migrations must be a list of strings")
    return list(value)


def _path_problem(root: Path, relative: Path, kind: str = "file") -> str | None:
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            return f"parent is a symlink: {current.relative_to(root)}"
        if current.exists() and not current.is_dir():
            return f"parent is not a directory: {current.relative_to(root)}"
    path = root / relative
    if path.is_symlink():
        return f"path is a symlink: {relative}"
    if path.exists() and kind == "file" and not path.is_file():
        return f"path is not a regular file: {relative}"
    if path.exists() and kind == "directory" and not path.is_dir():
        return f"path is not a directory: {relative}"
    if path.is_dir():
        for item in sorted(path.rglob("*")):
            if item.is_symlink():
                return f"directory contains a symlink: {item.relative_to(root)}"
            if not item.is_file() and not item.is_dir():
                return f"directory contains a non-regular entry: {item.relative_to(root)}"
    return None


def _content_digest(path: Path, kind: str) -> str:
    if kind == "file":
        return _sha256(path.read_bytes())
    digest = hashlib.sha256()
    digest.update(b"directory-v1\0")
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix().encode()
        mode = str(stat.S_IMODE(item.stat(follow_symlinks=False).st_mode)).encode()
        if item.is_dir():
            digest.update(b"d\0" + relative + b"\0" + mode + b"\0")
        elif item.is_file():
            digest.update(b"f\0" + relative + b"\0" + mode + b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
        else:  # guarded by _path_problem; keep direct callers fail-closed
            raise ValueError(f"unsupported directory entry: {item}")
    return digest.hexdigest()


def _git_state() -> tuple[str | None, bool | None]:
    try:
        head_result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None, None
    value = head_result.stdout.strip()
    head = value if head_result.returncode == 0 and value else None
    dirty = bool(status_result.stdout) if status_result.returncode == 0 else None
    return head, dirty


def _block(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _base_report(root: Path, current: int) -> dict[str, Any]:
    toolkit_head, toolkit_dirty = _git_state()
    return {
        "project_root": str(root),
        "toolkit_head": toolkit_head,
        "toolkit_dirty": toolkit_dirty,
        "oldest_readable_schema": OLDEST_READABLE_SCHEMA,
        "current_schema": current,
        "target_schema": CURRENT_SCHEMA,
        "available_migrations": list(MIGRATION_IDS),
        "pending_migrations": [],
        "operations": [],
        "blockers": [],
        "recovered": False,
    }


def _validate_local_ignore(root: Path) -> list[dict[str, str]]:
    path = root / LOCAL_IGNORE
    if not path.is_file() or path.is_symlink():
        return [
            _block(
                "missing-local-ignore",
                f"an upgradeable host must provide regular {LOCAL_IGNORE}",
            )
        ]
    rules = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not ({"/local/", "local/"} & rules):
        return [
            _block(
                "local-journal-not-ignored",
                f"{LOCAL_IGNORE} must ignore /local/ before migration",
            )
        ]
    return []


def _journal_shape_errors(
    journal: dict[str, Any], migration: dict[str, Any]
) -> list[dict[str, str]]:
    expected = {
        "migration_id": migration["id"],
        "from_schema": migration["from_schema"],
        "to_schema": migration["to_schema"],
        "source": str(migration["source"]),
        "destination": str(migration["destination"]),
        "content_kind": migration["kind"],
    }
    mismatches = [
        key for key, value in expected.items() if journal.get(key) != value
    ]
    if journal.get("journal_version") != 2:
        mismatches.append("journal_version")
    if not isinstance(journal.get("moved_path"), bool):
        mismatches.append("moved_path")
    if mismatches:
        return [
            _block(
                "inconsistent-journal",
                f"{migration['id']} has mismatched fields: {', '.join(sorted(set(mismatches)))}",
            )
        ]
    return []


def _resume_errors(
    root: Path, migration: dict[str, Any], journal: dict[str, Any]
) -> list[dict[str, str]]:
    errors = _journal_shape_errors(journal, migration)
    if errors:
        return errors
    source = root / migration["source"]
    destination = root / migration["destination"]
    state = journal.get("state")
    moved = journal["moved_path"]
    if state not in {"prepared", "moved"}:
        return [_block("inconsistent-journal", f"unexpected journal state: {state}")]
    if not moved:
        if source.exists() or source.is_symlink() or destination.exists() or destination.is_symlink():
            return [
                _block(
                    "inconsistent-journal",
                    f"{migration['id']} recorded no move but a migration path now exists",
                )
            ]
        return []
    expected = journal.get("content_sha256")
    source_ready = (
        state == "prepared"
        and source.exists()
        and not destination.exists()
        and _content_digest(source, migration["kind"]) == expected
    )
    destination_ready = (
        not source.exists()
        and destination.exists()
        and _content_digest(destination, migration["kind"]) == expected
    )
    if source_ready or destination_ready:
        return []
    return [
        _block(
            "inconsistent-journal",
            f"{migration['id']} paths do not match its prepared/moved digest",
        )
    ]


def _plan_step(root: Path, migration: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    for relative, kind in (
        (migration["source"], migration["kind"]),
        (migration["destination"], migration["kind"]),
        (_journal_path(migration["id"]), "file"),
    ):
        if problem := _path_problem(root, relative, kind):
            blockers.append(_block("unsafe-path-shape", problem))

    journal_path = root / _journal_path(migration["id"])
    journal = _read_journal(root, migration["id"])
    if (journal_path.exists() or journal_path.is_symlink()) and journal is None:
        blockers.append(
            _block("invalid-journal", f"cannot read migration journal {_journal_path(migration['id'])}")
        )
    operations: list[dict[str, Any]] = []
    recovered = False
    if journal is not None and journal.get("state") in {"prepared", "moved"}:
        blockers.extend(_resume_errors(root, migration, journal))
        operations.append(
            {
                "action": "resume",
                "migration_id": migration["id"],
                "from_state": journal.get("state"),
            }
        )
        recovered = True
    elif journal is not None and journal.get("state") not in {"restored"}:
        blockers.append(
            _block(
                "application-record-ahead",
                f"{migration['id']} journal is {journal.get('state')} before schema {migration['to_schema']}",
            )
        )
    else:
        source = root / migration["source"]
        destination = root / migration["destination"]
        if destination.exists() or destination.is_symlink():
            blockers.append(
                _block(
                    "canonical-path-occupied",
                    f"refusing to overwrite pre-existing {migration['destination']}",
                )
            )
        elif source.exists() or source.is_symlink():
            if not blockers:
                operations.append(
                    {
                        "action": "move",
                        "from": str(migration["source"]),
                        "to": str(migration["destination"]),
                        "sha256": _content_digest(source, migration["kind"]),
                    }
                )
    operations.append(
        {
            "action": "update-manifest",
            "path": str(MANIFEST),
            "from_schema": migration["from_schema"],
            "to_schema": migration["to_schema"],
        }
    )
    return {"blockers": blockers, "operations": operations, "recovered": recovered}


def _completed_recovery(
    root: Path, current: int, applied: list[str]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    migration = next((row for row in MIGRATIONS if row["to_schema"] == current), None)
    if migration is None or migration["id"] not in applied:
        return None
    journal = _read_journal(root, migration["id"])
    if journal is None or journal.get("state") not in {"prepared", "moved"}:
        return None
    errors = _resume_errors(root, migration, journal)
    return migration, {"journal": journal, "blockers": errors}


def plan(project_root: Path | str) -> dict[str, Any]:
    """Return the exact no-write plan for upgrading ``project_root``."""
    root = Path(project_root).resolve()
    try:
        manifest, _ = _read_manifest(root)
        current = _schema(manifest)
        applied = _applied_ids(manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        report = _base_report(root, OLDEST_READABLE_SCHEMA)
        report["status"] = "blocked"
        report["blockers"] = [_block("invalid-manifest", str(exc))]
        return report

    report = _base_report(root, current)
    if current > CURRENT_SCHEMA:
        report["status"] = "newer-than-tool"
        report["blockers"] = [
            _block(
                "newer-host-schema",
                f"host schema {current} is newer than toolkit schema {CURRENT_SCHEMA}",
            )
        ]
        return report
    if current < OLDEST_READABLE_SCHEMA:
        report["status"] = "blocked"
        report["blockers"] = [
            _block(
                "unreadable-host-schema",
                f"host schema {current} is older than supported schema {OLDEST_READABLE_SCHEMA}",
            )
        ]
        return report
    if current not in MIGRATION_BY_FROM and current != CURRENT_SCHEMA:
        report["status"] = "blocked"
        report["blockers"] = [
            _block("missing-migration-chain", f"no migration from schema {current}")
        ]
        return report

    if problem := _path_problem(root, MANIFEST):
        report["blockers"].append(_block("unsafe-path-shape", problem))
    if current < CURRENT_SCHEMA:
        report["blockers"].extend(_validate_local_ignore(root))

    required = {row["id"] for row in MIGRATIONS if row["to_schema"] <= current}
    future = {row["id"] for row in MIGRATIONS if row["to_schema"] > current}
    unknown = sorted(set(applied) - set(MIGRATION_IDS))
    for migration_id in unknown:
        report["blockers"].append(
            _block(
                "unknown-application-record",
                f"manifest records unknown migration {migration_id}",
            )
        )
    duplicates = sorted(
        migration_id for migration_id in set(applied) if applied.count(migration_id) > 1
    )
    for migration_id in duplicates:
        report["blockers"].append(
            _block(
                "duplicate-application-record",
                f"manifest records migration {migration_id} more than once",
            )
        )
    for migration_id in sorted(required - set(applied)):
        report["blockers"].append(
            _block(
                "missing-application-record",
                f"schema {current} requires migration record {migration_id}",
            )
        )
    for migration_id in sorted(future & set(applied)):
        report["blockers"].append(
            _block(
                "application-record-ahead",
                f"migration {migration_id} is recorded before its target schema",
            )
        )
    expected_applied = [
        row["id"] for row in MIGRATIONS if row["to_schema"] <= current
    ]
    if (
        not unknown
        and not duplicates
        and set(applied) == set(expected_applied)
        and applied != expected_applied
    ):
        report["blockers"].append(
            _block(
                "out-of-order-application-record",
                "manifest migration records do not match declared order",
            )
        )

    for migration in MIGRATIONS:
        journal_path = root / _journal_path(migration["id"])
        journal = _read_journal(root, migration["id"])
        if (journal_path.exists() or journal_path.is_symlink()) and journal is None:
            report["blockers"].append(
                _block("invalid-journal", f"cannot read migration journal {_journal_path(migration['id'])}")
            )
        if migration["to_schema"] <= current:
            for relative, kind in (
                (migration["source"], migration["kind"]),
                (migration["destination"], migration["kind"]),
            ):
                if problem := _path_problem(root, relative, kind):
                    report["blockers"].append(_block("unsafe-path-shape", problem))
            source = root / migration["source"]
            if source.exists() or source.is_symlink():
                report["blockers"].append(
                    _block("legacy-path-remains", str(migration["source"]))
                )
        elif journal is not None and journal.get("state") == "applied":
            report["blockers"].append(
                _block(
                    "application-record-ahead",
                    f"journal {migration['id']} is applied before schema {migration['to_schema']}",
                )
            )

    recovery = _completed_recovery(root, current, applied)
    if recovery is not None:
        migration, details = recovery
        report["blockers"].extend(details["blockers"])
        report["operations"].append(
            {"action": "finalize-journal", "migration_id": migration["id"]}
        )
        report["recovered"] = True

    for migration in MIGRATIONS:
        if migration["from_schema"] < current:
            continue
        report["pending_migrations"].append(migration["id"])
        step = _plan_step(root, migration)
        report["blockers"].extend(step["blockers"])
        report["operations"].extend(step["operations"])
        report["recovered"] = report["recovered"] or step["recovered"]

    if report["blockers"]:
        report["status"] = "blocked"
    elif report["operations"]:
        report["status"] = "ready"
    else:
        report["status"] = "current"
    return report


def _prepare_journal(
    root: Path,
    migration: dict[str, Any],
    manifest_raw: bytes | None,
    content_sha256: str | None,
    moved: bool,
) -> dict[str, Any]:
    journal = {
        "journal_version": 2,
        "migration_id": migration["id"],
        "state": "prepared",
        "from_schema": migration["from_schema"],
        "to_schema": migration["to_schema"],
        "source": str(migration["source"]),
        "destination": str(migration["destination"]),
        "content_kind": migration["kind"],
        "manifest_existed": manifest_raw is not None,
        "manifest_before_base64": _b64(manifest_raw),
        "content_sha256": content_sha256,
        "moved_path": moved,
    }
    _write_journal(root, journal)
    return journal


def _finish_manifest(
    root: Path,
    manifest: dict[str, Any] | None,
    journal: dict[str, Any],
    migration: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(manifest or {})
    applied = _applied_ids(updated)
    if migration["id"] not in applied:
        applied.append(migration["id"])
    updated["version"] = migration["to_schema"]
    updated["applied_migrations"] = applied
    raw = _write_manifest(root, updated)
    journal["state"] = "applied"
    journal["manifest_after_sha256"] = _sha256(raw)
    _write_journal(root, journal)
    return updated


def _apply_one(root: Path, migration: dict[str, Any]) -> bool:
    manifest, manifest_raw = _read_manifest(root)
    if _schema(manifest) != migration["from_schema"]:
        raise RuntimeError(f"host is not at schema {migration['from_schema']}")
    journal = _read_journal(root, migration["id"])
    recovered = journal is not None and journal.get("state") in {"prepared", "moved"}
    source = root / migration["source"]
    destination = root / migration["destination"]
    if recovered:
        assert journal is not None
        errors = _resume_errors(root, migration, journal)
        if errors:
            raise RuntimeError(errors)
    else:
        moved = source.exists()
        content_sha256 = _content_digest(source, migration["kind"]) if moved else None
        journal = _prepare_journal(
            root, migration, manifest_raw, content_sha256, moved
        )

    assert journal is not None
    if journal["moved_path"] and source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    journal["state"] = "moved"
    _write_journal(root, journal)
    _finish_manifest(root, manifest, journal, migration)

    verified, _ = _read_manifest(root)
    if _schema(verified) != migration["to_schema"] or migration["id"] not in _applied_ids(verified):
        raise RuntimeError(f"migration verification failed for {migration['id']}")
    if source.exists() or source.is_symlink():
        raise RuntimeError(f"legacy path remains after {migration['id']}")
    if journal["moved_path"]:
        if (
            not destination.exists()
            or _content_digest(destination, migration["kind"])
            != journal["content_sha256"]
        ):
            raise RuntimeError(f"destination verification failed for {migration['id']}")
    return recovered


def _finalize_completed(root: Path, migration: dict[str, Any]) -> None:
    manifest, raw = _read_manifest(root)
    journal = _read_journal(root, migration["id"])
    assert manifest is not None and raw is not None and journal is not None
    if _schema(manifest) != migration["to_schema"] or migration["id"] not in _applied_ids(manifest):
        raise RuntimeError(f"cannot finalize {migration['id']} without its manifest record")
    errors = _resume_errors(root, migration, journal)
    if errors:
        raise RuntimeError(errors)
    journal["state"] = "applied"
    journal["manifest_after_sha256"] = _sha256(raw)
    _write_journal(root, journal)


def apply(project_root: Path | str) -> dict[str, Any]:
    """Apply all pending migrations, or return a no-write blocked report."""
    root = Path(project_root).resolve()
    initial = plan(root)
    if initial["status"] != "ready":
        return initial

    recovered = initial["recovered"]
    while True:
        manifest, _ = _read_manifest(root)
        current = _schema(manifest)
        applied = _applied_ids(manifest)
        recovery = _completed_recovery(root, current, applied)
        if recovery is not None:
            migration, details = recovery
            if details["blockers"]:
                raise RuntimeError(details["blockers"])
            _finalize_completed(root, migration)
            recovered = True
            continue
        if current == CURRENT_SCHEMA:
            break
        migration = MIGRATION_BY_FROM.get(current)
        if migration is None:
            raise RuntimeError(f"no migration from schema {current}")
        recovered = _apply_one(root, migration) or recovered

    verified = plan(root)
    if verified["status"] != "current":
        raise RuntimeError(f"migration verification failed: {verified['blockers']}")
    verified["status"] = "applied"
    verified["recovered"] = recovered
    verified["operations"] = initial["operations"]
    return verified


def restore(project_root: Path | str, migration_id: str) -> dict[str, Any]:
    """Restore the exact pre-migration manifest/path state for the last step."""
    root = Path(project_root).resolve()
    report = plan(root)
    migration = MIGRATION_BY_ID.get(migration_id)
    if migration is None:
        report["status"] = "blocked"
        report["blockers"] = [_block("unknown-migration", migration_id)]
        return report
    manifest, _ = _read_manifest(root)
    if _schema(manifest) != migration["to_schema"]:
        report["status"] = "blocked"
        report["blockers"] = [
            _block(
                "not-last-migration",
                f"restore {migration_id} only from schema {migration['to_schema']}",
            )
        ]
        return report
    journal = _read_journal(root, migration_id)
    if journal is None or journal.get("state") != "applied":
        report["status"] = "blocked"
        report["blockers"] = [
            _block("restore-record-missing", f"no applied journal for {migration_id}")
        ]
        return report

    manifest_path = root / MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        report["status"] = "blocked"
        report["blockers"] = [_block("manifest-changed", "current manifest is unavailable")]
        return report
    if _sha256(manifest_path.read_bytes()) != journal.get("manifest_after_sha256"):
        report["status"] = "blocked"
        report["blockers"] = [
            _block("manifest-changed", "manifest changed after migration; refusing restore")
        ]
        return report

    source = root / migration["source"]
    destination = root / migration["destination"]
    if journal.get("moved_path"):
        expected = journal.get("content_sha256")
        if source.exists() or source.is_symlink():
            report["status"] = "blocked"
            report["blockers"] = [_block("legacy-path-occupied", str(migration["source"]))]
            return report
        if (
            not destination.exists()
            or destination.is_symlink()
            or _content_digest(destination, migration["kind"]) != expected
        ):
            report["status"] = "blocked"
            report["blockers"] = [
                _block("canonical-content-changed", str(migration["destination"]))
            ]
            return report
        source.parent.mkdir(parents=True, exist_ok=True)
        os.replace(destination, source)

    manifest_before = _unb64(journal.get("manifest_before_base64"))
    if journal.get("manifest_existed"):
        assert manifest_before is not None
        _atomic_write(manifest_path, manifest_before)
    else:
        manifest_path.unlink()

    journal["state"] = "restored"
    _write_journal(root, journal)
    restored = plan(root)
    if restored["status"] != "ready":
        raise RuntimeError(f"restore verification failed: {restored['blockers']}")
    restored["status"] = "restored"
    restored["operations"] = [{"action": "restore", "migration_id": migration_id}]
    return restored


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Host project whose toolkit-owned state should be inspected",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Read-only code/state compatibility status")
    sub.add_parser("plan", help="Read-only exact migration plan")
    sub.add_parser("apply", help="Apply the pending ordered migration chain")
    restore_parser = sub.add_parser("restore", help="Restore the last migration")
    restore_parser.add_argument("migration_id")
    args = parser.parse_args(argv)

    try:
        if args.command in {"status", "plan"}:
            payload = plan(args.project_root)
        elif args.command == "apply":
            payload = apply(args.project_root)
        else:
            payload = restore(args.project_root, args.migration_id)
    except (
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        payload = {
            "status": "blocked",
            "blockers": [_block("migration-error", str(exc))],
        }
    _emit(payload)
    return 0 if payload["status"] not in {"blocked", "newer-than-tool"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
