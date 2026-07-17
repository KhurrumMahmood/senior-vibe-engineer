"""Transactional host lifecycle for caller-verified skill install images.

Trust verification and image materialization belong to :mod:`skill_bundle`.
This module accepts that verified data, owns host mutation, and fails closed at
every ownership, filesystem, recovery, and native-discovery boundary.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from typing import Any, Protocol
import unicodedata
import uuid

from .distribution_contracts import (
    DistributionContractError,
    canonical_json_bytes,
    canonical_sha256,
    load_canonical_json,
    validate_distribution_contract,
)


MANIFEST_PATH = ".engineering/installed-manifest-v1.json"
STATE_PATH = ".engineering/skill-installer-state-v1.json"
JOURNAL_PATH = ".engineering/skill-installer-recovery-v1.json"
TRANSACTION_PREFIX = ".engineering/.skill-installer-txn-"
PREVIOUS_PREFIX = ".engineering/skill-installer-previous"
_PUBLIC_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_UUID4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_STATE_KEYS = {
    "schema_version",
    "surface_contract",
    "canonical_sources",
    "portfolio",
    "aliases",
    "previous",
}
_JOURNAL_KEYS = {
    "schema_version",
    "state",
    "operation",
    "transaction_id",
    "prior_manifest_sha256",
    "transaction_path",
    "changes",
}
_CHANGE_KEYS = {"path", "existed", "kind", "size", "sha256", "link_target"}


class LifecycleError(RuntimeError):
    """A lifecycle command cannot preserve the transactional contract."""


class NativeDiscoveryAdapter(Protocol):
    """Offline, non-model proof of the toolkit-owned native discovery set."""

    offline_non_model: bool

    def discover(self, project_root: Path, surface_id: str) -> set[str]: ...

    def proves_generated_links(self, surface_id: str) -> bool: ...


@dataclass(frozen=True)
class ValidatedMigrationPlan:
    """A trust-layer validated exact-byte legacy migration plan."""

    entries: tuple[dict[str, Any], ...] = ()
    plan_sha256: str = ""
    _verified: bool = field(default=False, repr=False)

    @classmethod
    def from_verified(
        cls, entries: Sequence[Mapping[str, Any]], *, plan_sha256: str
    ) -> "ValidatedMigrationPlan":
        if _HASH.fullmatch(plan_sha256) is None:
            raise LifecycleError("validated migration plan digest is invalid")
        normalized: list[dict[str, Any]] = []
        paths: set[str] = set()
        for index, candidate in enumerate(entries):
            if set(candidate) != {"action", "path", "size", "sha256"}:
                raise LifecycleError(f"migration entry {index} is not schema-closed")
            path = _relative(candidate["path"], location=f"migration[{index}].path")
            if path in paths:
                raise LifecycleError(f"duplicate migration target: {path}")
            paths.add(path)
            action = candidate["action"]
            if action not in {"adopt", "retire"}:
                raise LifecycleError(f"unsupported migration action: {action!r}")
            size, digest = candidate["size"], candidate["sha256"]
            if type(size) is not int or size < 0 or not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
                raise LifecycleError(f"migration entry {index} has invalid byte identity")
            normalized.append(
                {"action": action, "path": path, "size": size, "sha256": digest}
            )
        return cls(tuple(normalized), plan_sha256, True)

    @classmethod
    def unverified_for_test(cls) -> "ValidatedMigrationPlan":
        """Construct an explicitly untrusted value for a fail-closed test."""
        return cls()


@dataclass(frozen=True)
class LifecycleInput:
    """Caller-verified immutable image plus lifecycle projection metadata."""

    root: Path
    manifest: dict[str, Any]
    surface_contract: dict[str, Any]
    canonical_sources: dict[str, str]
    portfolio: tuple[str, ...]
    aliases: dict[str, str]
    _verified: bool = field(default=False, repr=False)

    @classmethod
    def from_verified(
        cls,
        *,
        root: Path,
        manifest: Mapping[str, Any],
        surface_contract: Mapping[str, Any],
        canonical_sources: Mapping[str, str],
        portfolio: Sequence[str],
        aliases: Mapping[str, str],
    ) -> "LifecycleInput":
        return cls(
            Path(root),
            deepcopy(dict(manifest)),
            deepcopy(dict(surface_contract)),
            {str(name): str(path) for name, path in canonical_sources.items()},
            tuple(str(name) for name in portfolio),
            {str(name): str(target) for name, target in aliases.items()},
            True,
        )

    def with_generated_link(self, path: str, target: str) -> "LifecycleInput":
        """Return verified test/input data with one declared contained link."""
        safe_path = _relative(path, location="generated link path")
        safe_target = _relative(target, location="generated link target")
        target_path = _safe_path(self.root, safe_target, must_exist=True)
        content = target_path.read_bytes()
        link = self.root / safe_path
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(target_path, link.parent)
        link.symlink_to(relative_target)
        manifest = deepcopy(self.manifest)
        manifest["owned_paths"]["generated_links"].append(
            {
                "path": safe_path,
                "link_sha256": _sha(relative_target.encode()),
                "target": safe_target,
                "target_sha256": _sha(content),
            }
        )
        _rehash_manifest(manifest)
        return replace(self, manifest=manifest)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _root_path(value: Path | str, *, label: str, may_create: bool) -> Path:
    path = Path(value)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if not may_create:
            raise LifecycleError(f"{label} is missing: {path}") from None
    else:
        if stat.S_ISLNK(metadata.st_mode):
            raise LifecycleError(f"{label} must not be a symlink: {path}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise LifecycleError(f"{label} must be a directory: {path}")
    return path.resolve()


def _row(path: str, content: bytes) -> dict[str, Any]:
    return {"path": path, "size": len(content), "sha256": _sha(content)}


def _relative(value: object, *, location: str = "path") -> str:
    if not isinstance(value, str) or not value:
        raise LifecycleError(f"{location} must be a non-empty relative path")
    if value != unicodedata.normalize("NFC", value) or value.startswith("/"):
        raise LifecycleError(f"{location} must be NFC relative POSIX")
    if "\\" in value or "\x00" in value:
        raise LifecycleError(f"{location} must be a relative POSIX path")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise LifecycleError(f"{location} traverses or contains a dot segment")
    if len(value.encode()) > 1024:
        raise LifecycleError(f"{location} exceeds 1024 UTF-8 bytes")
    return value


def _safe_path(root: Path, relative: str, *, must_exist: bool) -> Path:
    relative = _relative(relative)
    cursor = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except FileNotFoundError:
            if must_exist:
                raise LifecycleError(f"path is missing: {relative}") from None
            continue
        if stat.S_ISLNK(metadata.st_mode):
            if index != len(parts) - 1:
                raise LifecycleError(f"path traverses a symlink: {relative}")
        elif index != len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise LifecycleError(f"path has a non-directory ancestor: {relative}")
    return cursor


def _atomic_write(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise


def _secure_parents(path: Path, *, anchor: Path) -> None:
    """Create transaction-private ancestors without changing host directories."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    cursor = path
    while cursor != anchor.parent:
        cursor.chmod(0o700)
        if cursor == anchor:
            break
        cursor = cursor.parent


def _rehash_manifest(manifest: dict[str, Any]) -> None:
    manifest["manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )


def _manifest_rows(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    owned = manifest.get("owned_paths")
    if not isinstance(owned, Mapping):
        raise LifecycleError("manifest owned_paths is missing")
    for class_name, rows in owned.items():
        if not isinstance(rows, list):
            raise LifecycleError(f"manifest ownership class {class_name} is not an array")
        for row in rows:
            path = _relative(row.get("path"), location=f"owned_paths.{class_name}.path")
            if path in result:
                raise LifecycleError(f"duplicate owned target: {path}")
            result[path] = dict(row)
    return result


def _verify_regular(root: Path, row: Mapping[str, Any], *, label: str) -> bytes:
    path = _safe_path(root, row["path"], must_exist=True)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise LifecycleError(f"{label} is not a single-link regular file: {row['path']}")
    content = path.read_bytes()
    if len(content) != row["size"] or _sha(content) != row["sha256"]:
        raise LifecycleError(f"modified owned content: {row['path']}")
    return content


def _verify_link(root: Path, row: Mapping[str, Any], *, label: str) -> None:
    link = _safe_path(root, row["path"], must_exist=True)
    if not link.is_symlink():
        raise LifecycleError(f"{label} is not a symlink: {row['path']}")
    target_text = os.readlink(link)
    if _sha(target_text.encode()) != row["link_sha256"]:
        raise LifecycleError(f"modified owned generated link: {row['path']}")
    declared_target = _safe_path(root, row["target"], must_exist=True)
    resolved = (link.parent / target_text).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise LifecycleError(f"generated link escapes project: {row['path']}") from exc
    if resolved != declared_target.resolve() or not resolved.is_file():
        raise LifecycleError(f"generated link target differs: {row['path']}")
    if _sha(resolved.read_bytes()) != row["target_sha256"]:
        raise LifecycleError(f"generated link target hash differs: {row['path']}")


def _validate_input(data: LifecycleInput, adapter: NativeDiscoveryAdapter) -> None:
    if not data._verified:
        raise LifecycleError("lifecycle requires caller-verified input data")
    image_root = _root_path(data.root, label="verified image root", may_create=False)
    if image_root != data.root.resolve():
        raise LifecycleError("verified image root identity changed")
    if not getattr(adapter, "offline_non_model", False):
        raise LifecycleError("native discovery adapter must be an offline non-model check")
    if not callable(getattr(adapter, "discover", None)) or not callable(
        getattr(adapter, "proves_generated_links", None)
    ):
        raise LifecycleError("native discovery adapter is incomplete")
    try:
        validate_distribution_contract("installed-manifest-v1", data.manifest)
    except (DistributionContractError, KeyError, TypeError) as exc:
        raise LifecycleError(f"invalid verified lifecycle manifest: {exc}") from exc
    rows = _manifest_rows(data.manifest)
    if set(data.canonical_sources) != set(data.portfolio):
        raise LifecycleError("canonical source map must exactly equal the selected portfolio")
    for name in data.portfolio:
        if _PUBLIC_NAME.fullmatch(name) is None:
            raise LifecycleError(f"invalid portfolio public name: {name!r}")
        source = _relative(data.canonical_sources[name], location=f"canonical_sources.{name}")
        row = rows.get(source)
        if row is None or source not in {
            candidate["path"] for candidate in data.manifest["owned_paths"]["catalog_store"]
        }:
            raise LifecycleError(f"canonical source is not owned catalog content: {source}")
    for public_name, target in data.aliases.items():
        if _PUBLIC_NAME.fullmatch(public_name) is None or target not in data.canonical_sources:
            raise LifecycleError(f"invalid or stale alias: {public_name!r} -> {target!r}")
        if public_name in data.canonical_sources:
            raise LifecycleError(f"alias collides with canonical procedure: {public_name}")
    surfaces = _surface_records(data.surface_contract)
    selected_surfaces = data.manifest["surface_set"]
    if len(selected_surfaces) != len(set(selected_surfaces)) or not set(selected_surfaces).issubset(
        surfaces
    ):
        raise LifecycleError("verified manifest selects an unknown or duplicate surface")
    for _path, row in rows.items():
        if "link_sha256" in row:
            _verify_link(data.root, row, label="verified image generated link")
        else:
            _verify_regular(data.root, row, label="verified image owned file")
    for surface in data.manifest["surface_set"]:
        if data.manifest["owned_paths"]["generated_links"] and not adapter.proves_generated_links(surface):
            raise LifecycleError(f"generated links are not discovery-proven for {surface}")


def _surface_records(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if set(contract) != {"schema_version", "contract_version", "surfaces"}:
        raise LifecycleError("surface contract is not schema-closed")
    if contract["schema_version"] != 1 or contract["contract_version"] != 1:
        raise LifecycleError("surface contract version is unsupported")
    result: dict[str, dict[str, Any]] = {}
    for row in contract["surfaces"]:
        surface = row["surface_id"]
        if surface in result:
            raise LifecycleError(f"duplicate surface contract: {surface}")
        identity = row["generated_identity"]
        if set(identity) != {"which_shape", "which_skill", "alias_template"}:
            raise LifecycleError(f"surface identity is not closed: {surface}")
        if identity["alias_template"].count("{public-name}") != 1:
            raise LifecycleError(f"surface alias template is invalid: {surface}")
        if row["discovery"].get("offline_non_model") is not True:
            raise LifecycleError(f"surface lacks offline non-model discovery: {surface}")
        result[surface] = deepcopy(row)
    return result


def _clean_journal() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "state": "clean",
        "operation": None,
        "transaction_id": None,
        "prior_manifest_sha256": None,
        "transaction_path": None,
        "changes": [],
    }


def _state_payload(
    data: LifecycleInput, *, previous: dict[str, Any] | None
) -> dict[str, Any]:
    rows = _manifest_rows(data.manifest)
    sources = {
        name: {key: rows[path][key] for key in ("path", "size", "sha256")}
        for name, path in sorted(data.canonical_sources.items())
    }
    return {
        "schema_version": 1,
        "surface_contract": data.surface_contract,
        "canonical_sources": sources,
        "portfolio": list(data.portfolio),
        "aliases": [
            {"public_name": name, "canonical_target": target}
            for name, target in sorted(data.aliases.items())
        ],
        "previous": previous,
    }


def _load_state(root: Path, manifest: Mapping[str, Any]) -> tuple[dict[str, Any], LifecycleInput]:
    state_rows = manifest["owned_paths"]["activation_state"]
    if len(state_rows) != 1 or state_rows[0]["path"] != STATE_PATH:
        raise LifecycleError("installed lifecycle state is absent or ambiguous")
    content = _verify_regular(root, state_rows[0], label="lifecycle state")
    try:
        state = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("lifecycle state is corrupt") from exc
    if set(state) != _STATE_KEYS or state["schema_version"] != 1:
        raise LifecycleError("lifecycle state is not schema-closed v1")
    sources = state["canonical_sources"]
    if not isinstance(sources, dict):
        raise LifecycleError("lifecycle canonical_sources is invalid")
    data = LifecycleInput.from_verified(
        root=root,
        manifest=manifest,
        surface_contract=state["surface_contract"],
        canonical_sources={name: row["path"] for name, row in sources.items()},
        portfolio=state["portfolio"],
        aliases={row["public_name"]: row["canonical_target"] for row in state["aliases"]},
    )
    return state, data


def _copy_object(source_root: Path, target_root: Path, relative: str) -> None:
    source = _safe_path(source_root, relative, must_exist=True)
    target = target_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata = source.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        target.symlink_to(os.readlink(source))
    elif stat.S_ISREG(metadata.st_mode):
        _atomic_write(target, source.read_bytes())
    else:
        raise LifecycleError(f"owned object is not a regular file or link: {relative}")


def _copy_base(data: LifecycleInput, stage: Path) -> dict[str, Any]:
    manifest = deepcopy(data.manifest)
    keep_classes = {"catalog_store", "bootstrap_projections", "generated_links"}
    for class_name, rows in list(manifest["owned_paths"].items()):
        kept = []
        if class_name in keep_classes:
            for row in rows:
                if row["path"].startswith(f"{PREVIOUS_PREFIX}/"):
                    continue
                kept.append(deepcopy(row))
                _copy_object(data.root, stage, row["path"])
        manifest["owned_paths"][class_name] = kept
    manifest["generated_files"] = [
        deepcopy(row) for row in manifest["generated_files"] if row["ownership_class"] == "bootstrap"
    ]
    return manifest


def _projection_path(contract: Mapping[str, Any], surface: str, public_name: str) -> str:
    identity = _surface_records(contract)[surface]["generated_identity"]
    if public_name == "which-shape":
        return _relative(identity["which_shape"])
    if public_name == "which-skill":
        return _relative(identity["which_skill"])
    return _relative(identity["alias_template"].replace("{public-name}", public_name))


def _render_projections(
    stage: Path,
    manifest: dict[str, Any],
    data: LifecycleInput,
    records: list[dict[str, str]],
    mode: str,
) -> None:
    routers = {"which-shape", "which-skill"}
    names: dict[str, str] = {}
    if mode == "full-discovery":
        names.update({name: name for name in data.portfolio})
        names.update(data.aliases)
        ownership = "full-discovery"
        owned_class = "full_discovery_projections"
    else:
        names.update({row["public_name"]: row["canonical_target"] for row in records})
        ownership = "activation"
        owned_class = "activation_projections"
    for public_name, target in sorted(names.items()):
        if public_name in routers:
            continue
        source = stage / data.canonical_sources[target]
        if not source.is_file():
            raise LifecycleError(f"projection source is missing: {target}")
        content = source.read_bytes()
        for surface in manifest["surface_set"]:
            path = _projection_path(data.surface_contract, surface, public_name)
            if any(row["path"] == path for row in manifest["generated_files"]):
                raise LifecycleError(f"projection target collision: {path}")
            _atomic_write(stage / path, content)
            row = _row(path, content)
            manifest["owned_paths"][owned_class].append(row)
            manifest["generated_files"].append(
                {"ownership_class": ownership, "surface_id": surface, **row}
            )


def _snapshot_current(
    current_root: Path, current: Mapping[str, Any], stage: Path
) -> dict[str, Any]:
    digest = current["manifest_sha256"]
    prefix = f"{PREVIOUS_PREFIX}/{digest}"
    files: list[dict[str, Any]] = []
    for path, row in sorted(_manifest_rows(current).items()):
        if path.startswith(f"{PREVIOUS_PREFIX}/"):
            continue
        archive = f"{prefix}/files/{path}"
        source = _safe_path(current_root, path, must_exist=True)
        if source.is_symlink():
            target = os.readlink(source)
            files.append(
                {
                    "path": path,
                    "archive": None,
                    "kind": "link",
                    "size": len(target.encode()),
                    "sha256": _sha(target.encode()),
                    "link_target": target,
                }
            )
        else:
            content = source.read_bytes()
            _atomic_write(stage / archive, content)
            files.append(
                {
                    "path": path,
                    "archive": archive,
                    "kind": "file",
                    "size": row["size"],
                    "sha256": row["sha256"],
                    "link_target": None,
                }
            )
    manifest_content = (current_root / MANIFEST_PATH).read_bytes()
    manifest_archive = f"{prefix}/manifest.json"
    _atomic_write(stage / manifest_archive, manifest_content)
    return {
        "manifest_sha256": digest,
        "manifest_archive": manifest_archive,
        "files": files,
    }


def _add_snapshot_rows(stage: Path, manifest: dict[str, Any], previous: dict[str, Any]) -> None:
    paths = [
        previous["manifest_archive"],
        *[row["archive"] for row in previous["files"] if row["archive"] is not None],
    ]
    for path in paths:
        content = (stage / path).read_bytes()
        manifest["owned_paths"]["catalog_store"].append(_row(path, content))


def _finalize_stage(
    stage: Path,
    manifest: dict[str, Any],
    data: LifecycleInput,
    *,
    generation: int,
    previous_digest: str | None,
    previous: dict[str, Any] | None,
    mode: str,
    activation_records: list[dict[str, str]],
) -> dict[str, Any]:
    if mode not in {"router-only", "full-discovery"}:
        raise LifecycleError("mode must be router-only or full-discovery")
    manifest["manifest_generation"] = generation
    manifest["previous_manifest_sha256"] = previous_digest
    manifest["mode"] = mode
    manifest["activation_records"] = deepcopy(activation_records)
    manifest["cleanup"] = {
        "state": "clean",
        "last_cleaned_generation": generation,
        "failure_code": None,
    }
    if previous is not None:
        _add_snapshot_rows(stage, manifest, previous)

    state_bytes = canonical_json_bytes(_state_payload(data, previous=previous))
    _atomic_write(stage / STATE_PATH, state_bytes)
    manifest["owned_paths"]["activation_state"] = [_row(STATE_PATH, state_bytes)]
    journal_bytes = canonical_json_bytes(_clean_journal())
    _atomic_write(stage / JOURNAL_PATH, journal_bytes)
    manifest["owned_paths"]["recovery_journal"] = [_row(JOURNAL_PATH, journal_bytes)]
    manifest["recovery"] = {
        "state": "clean",
        "journal_path": JOURNAL_PATH,
        "journal_sha256": _sha(journal_bytes),
        "temporary_records": [],
    }
    _render_projections(stage, manifest, data, activation_records, mode)
    _rehash_manifest(manifest)
    try:
        validate_distribution_contract("installed-manifest-v1", manifest)
    except DistributionContractError as exc:
        raise LifecycleError(f"generated lifecycle manifest is invalid: {exc}") from exc
    _atomic_write(stage / MANIFEST_PATH, canonical_json_bytes(manifest))
    _verify_owned(stage, manifest)
    return manifest


def _verify_owned(root: Path, manifest: Mapping[str, Any]) -> None:
    try:
        validate_distribution_contract("installed-manifest-v1", dict(manifest))
    except DistributionContractError as exc:
        raise LifecycleError(f"installed manifest is invalid: {exc}") from exc
    for row in _manifest_rows(manifest).values():
        if "link_sha256" in row:
            _verify_link(root, row, label="owned generated link")
        else:
            _verify_regular(root, row, label="owned file")
    raw = (root / MANIFEST_PATH).read_bytes()
    if raw != canonical_json_bytes(manifest):
        raise LifecycleError("installed manifest bytes are corrupt or noncanonical")


def _expected_discovery(manifest: Mapping[str, Any], contract: Mapping[str, Any], surface: str) -> set[str]:
    identities = _surface_records(contract)[surface]["generated_identity"]
    template = identities["alias_template"]
    prefix, suffix = template.split("{public-name}")
    result: set[str] = set()
    for row in manifest["generated_files"]:
        if row["surface_id"] != surface:
            continue
        path = row["path"]
        if path == identities["which_shape"]:
            result.add("which-shape")
        elif path == identities["which_skill"]:
            result.add("which-skill")
        elif path.startswith(prefix) and path.endswith(suffix):
            name = path[len(prefix) : len(path) - len(suffix) if suffix else None]
            if _PUBLIC_NAME.fullmatch(name):
                result.add(name)
            else:
                raise LifecycleError(f"generated path has invalid public identity: {path}")
        elif row["ownership_class"] == "bootstrap":
            # Bootstrap metadata and declared runtime support files are owned
            # generated bytes, not public skill headers.
            continue
        else:
            raise LifecycleError(f"generated path differs from surface identity: {path}")
    return result


def _prove_discovery(
    root: Path,
    manifest: Mapping[str, Any] | None,
    contract: Mapping[str, Any] | None,
    adapter: NativeDiscoveryAdapter,
) -> None:
    if not getattr(adapter, "offline_non_model", False):
        raise LifecycleError("native discovery adapter must be an offline non-model check")
    if not callable(getattr(adapter, "discover", None)):
        raise LifecycleError("native discovery adapter is incomplete")
    surfaces = list(manifest["surface_set"]) if manifest is not None else []
    for surface in surfaces:
        expected = _expected_discovery(manifest, contract or {}, surface)
        actual = set(adapter.discover(root, surface))
        if actual != expected:
            raise LifecycleError(
                f"native discovery mismatch for {surface}: expected={sorted(expected)}, actual={sorted(actual)}"
            )


def _prove_uninstalled_discovery(
    root: Path,
    prior_manifest: Mapping[str, Any],
    adapter: NativeDiscoveryAdapter,
) -> None:
    if not getattr(adapter, "offline_non_model", False) or not callable(
        getattr(adapter, "discover", None)
    ):
        raise LifecycleError("native discovery adapter must be an offline non-model check")
    for surface in prior_manifest["surface_set"]:
        actual = set(adapter.discover(root, surface))
        if actual:
            raise LifecycleError(
                f"native discovery still exposes toolkit names for {surface}: {sorted(actual)}"
            )


@contextmanager
def _project_lock(project_root: Path):
    project_root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(project_root, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LifecycleError("another project lifecycle command holds the lock") from exc
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _read_manifest(root: Path) -> dict[str, Any] | None:
    path = root / MANIFEST_PATH
    if not path.exists():
        return None
    try:
        value = load_canonical_json(path)
        validate_distribution_contract("installed-manifest-v1", value)
    except (OSError, DistributionContractError) as exc:
        raise LifecycleError(f"installed manifest is corrupt: {exc}") from exc
    return value


def _journal_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = load_canonical_json(path)
    except (OSError, DistributionContractError) as exc:
        raise LifecycleError("recovery journal is corrupt") from exc
    if not isinstance(value, dict) or set(value) != _JOURNAL_KEYS or value["schema_version"] != 1:
        raise LifecycleError("recovery journal is not schema-closed v1")
    if value["state"] not in {"clean", "committing", "restoring", "blocked"}:
        raise LifecycleError("recovery journal has an unknown state")
    if value["state"] == "clean":
        if value != _clean_journal():
            raise LifecycleError("clean recovery journal carries transaction state")
        return value
    if value["operation"] not in {
        "activate",
        "deactivate",
        "install",
        "rollback",
        "set-mode",
        "uninstall",
        "update",
    }:
        raise LifecycleError("recovery journal operation is invalid")
    transaction_id = value["transaction_id"]
    if not isinstance(transaction_id, str) or _UUID4.fullmatch(transaction_id) is None:
        raise LifecycleError("recovery journal transaction id is invalid")
    if value["transaction_path"] != f"{TRANSACTION_PREFIX}{transaction_id}":
        raise LifecycleError("recovery journal transaction path is invalid")
    prior = value["prior_manifest_sha256"]
    if prior is not None and (not isinstance(prior, str) or _HASH.fullmatch(prior) is None):
        raise LifecycleError("recovery journal prior manifest digest is invalid")
    paths: set[str] = set()
    for change in value["changes"]:
        if set(change) != _CHANGE_KEYS:
            raise LifecycleError("recovery journal change is not schema-closed")
        relative = _relative(change["path"], location="recovery journal change path")
        if relative in paths or relative.startswith(f"{TRANSACTION_PREFIX}"):
            raise LifecycleError("recovery journal change path is duplicate or reserved")
        paths.add(relative)
        if type(change["existed"]) is not bool or change["kind"] not in {
            "absent",
            "file",
            "link",
        }:
            raise LifecycleError("recovery journal change kind is invalid")
        if change["existed"] != (change["kind"] != "absent"):
            raise LifecycleError("recovery journal existence and kind disagree")
        if (
            type(change["size"]) is not int
            or change["size"] < 0
            or not isinstance(change["sha256"], str)
            or _HASH.fullmatch(change["sha256"]) is None
        ):
            raise LifecycleError("recovery journal byte identity is invalid")
        link_target = change["link_target"]
        if change["kind"] == "link":
            if not isinstance(link_target, str) or len(link_target.encode()) != change["size"]:
                raise LifecycleError("recovery journal link identity is invalid")
            if _sha(link_target.encode()) != change["sha256"]:
                raise LifecycleError("recovery journal link digest is invalid")
        elif link_target is not None:
            raise LifecycleError("non-link recovery journal row carries link text")
    return value


def _remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and parent.is_dir():
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def _restore_from_journal(project: Path, journal: Mapping[str, Any]) -> None:
    transaction = project / journal["transaction_path"]
    for change in reversed(journal["changes"]):
        target = project / change["path"]
        if target.is_symlink() or target.is_file():
            target.unlink()
        if change["existed"]:
            backup = transaction / "backup" / change["path"]
            if change["kind"] == "link":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(change["link_target"])
            else:
                content = backup.read_bytes()
                if len(content) != change["size"] or _sha(content) != change["sha256"]:
                    raise LifecycleError("recovery backup bytes are missing or corrupt")
                _atomic_write(target, content)
        _remove_empty_parents(target, project)
    shutil.rmtree(transaction, ignore_errors=False)
    _remove_empty_parents(transaction, project)


def _recover(project: Path) -> None:
    journal_path = project / JOURNAL_PATH
    journal = _journal_record(journal_path)
    if journal is None or journal["state"] == "clean":
        for orphan in project.glob(f"{TRANSACTION_PREFIX}*"):
            marker = orphan / "owner-v1"
            if marker.is_file() and marker.read_text(encoding="ascii") == "engineering-skills\n":
                shutil.rmtree(orphan)
        return
    if journal["state"] == "blocked":
        raise LifecycleError("recovery journal is blocked and requires manual restoration")
    try:
        _restore_from_journal(project, journal)
    except (OSError, LifecycleError) as exc:
        blocked = dict(journal)
        blocked["state"] = "blocked"
        _atomic_write(journal_path, canonical_json_bytes(blocked))
        raise LifecycleError(f"startup recovery failed closed: {exc}") from exc


def _current(project: Path) -> tuple[dict[str, Any] | None, LifecycleInput | None]:
    manifest = _read_manifest(project)
    if manifest is None:
        return None, None
    _verify_owned(project, manifest)
    _, data = _load_state(project, manifest)
    return manifest, data


def _migration_entries(plan: ValidatedMigrationPlan | None) -> tuple[dict[str, Any], ...]:
    if plan is None:
        return ()
    if not plan._verified:
        raise LifecycleError("lifecycle requires an injected validated migration plan")
    return plan.entries


def _object_identity(path: Path) -> tuple[str, int, str, str | None]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        target = os.readlink(path)
        return "link", len(target.encode()), _sha(target.encode()), target
    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
        content = path.read_bytes()
        return "file", len(content), _sha(content), None
    raise LifecycleError(f"target is not a single-link regular file: {path}")


def _commit(
    project: Path,
    stage: Path | None,
    desired: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
    *,
    operation: str,
    adapter: NativeDiscoveryAdapter,
    contract: Mapping[str, Any] | None,
    migration_plan: ValidatedMigrationPlan | None,
) -> None:
    current_rows = _manifest_rows(current) if current else {}
    desired_rows = _manifest_rows(desired) if desired else {}
    current_paths = set(current_rows) | ({MANIFEST_PATH} if current else set())
    desired_paths = set(desired_rows) | ({MANIFEST_PATH} if desired else set())
    migrations = _migration_entries(migration_plan)
    migrate_by_path = {row["path"]: row for row in migrations}

    for migration in migrations:
        path = migration["path"]
        if path in current_paths:
            raise LifecycleError(f"migration plan overlaps manifest-owned content: {path}")
        if migration["action"] == "adopt":
            desired_row = desired_rows.get(path)
            if desired_row is None or "link_sha256" in desired_row:
                raise LifecycleError(f"migration adoption is not a desired regular file: {path}")
            if (desired_row["size"], desired_row["sha256"]) != (
                migration["size"],
                migration["sha256"],
            ):
                raise LifecycleError(f"migration adoption differs from desired bytes: {path}")
        elif path in desired_paths:
            raise LifecycleError(f"migration retirement remains in the desired generation: {path}")

    for _path, row in current_rows.items():
        if "link_sha256" in row:
            _verify_link(project, row, label="current owned link")
        else:
            _verify_regular(project, row, label="current owned file")
    for path in desired_paths - current_paths:
        target = _safe_path(project, path, must_exist=False)
        if target.exists() or target.is_symlink():
            migration = migrate_by_path.get(path)
            if migration is None or migration["action"] != "adopt":
                raise LifecycleError(f"host collision at unowned target: {path}")
            kind, size, digest, _ = _object_identity(target)
            if kind != "file" or (size, digest) != (migration["size"], migration["sha256"]):
                raise LifecycleError(f"migration adoption bytes differ: {path}")
    for migration in migrations:
        target = _safe_path(project, migration["path"], must_exist=True)
        kind, size, digest, _ = _object_identity(target)
        if kind != "file" or (size, digest) != (migration["size"], migration["sha256"]):
            raise LifecycleError(f"migration known bytes differ: {migration['path']}")

    changed_paths = sorted(current_paths | desired_paths | {row["path"] for row in migrations})
    transaction_id = str(uuid.uuid4())
    transaction_relative = f"{TRANSACTION_PREFIX}{transaction_id}"
    transaction = project / transaction_relative
    transaction.mkdir(parents=True, mode=0o700)
    _atomic_write(transaction / "owner-v1", b"engineering-skills\n")
    changes: list[dict[str, Any]] = []
    try:
        for relative in changed_paths:
            target = project / relative
            existed = target.is_symlink() or target.is_file()
            if existed:
                kind, size, digest, link_target = _object_identity(target)
                backup = transaction / "backup" / relative
                _secure_parents(backup.parent, anchor=transaction)
                if kind == "link":
                    # The closed journal already carries the bounded link text;
                    # raw transaction staging never needs a symlink.
                    pass
                else:
                    _atomic_write(backup, target.read_bytes())
            else:
                kind, size, digest, link_target = "absent", 0, _sha(b""), None
            changes.append(
                {
                    "path": relative,
                    "existed": existed,
                    "kind": kind,
                    "size": size,
                    "sha256": digest,
                    "link_target": link_target,
                }
            )
        journal = {
            "schema_version": 1,
            "state": "committing",
            "operation": operation,
            "transaction_id": transaction_id,
            "prior_manifest_sha256": current["manifest_sha256"] if current else None,
            "transaction_path": transaction_relative,
            "changes": changes,
        }
        _atomic_write(project / JOURNAL_PATH, canonical_json_bytes(journal))
        retire = (current_paths - desired_paths) | {
            row["path"] for row in migrations if row["action"] == "retire"
        }
        # The committing journal is the durable recovery pointer until native
        # discovery accepts the whole requested surface set.
        retire.discard(JOURNAL_PATH)
        for relative in sorted(retire, reverse=True):
            target = project / relative
            if target.is_symlink() or target.is_file():
                target.unlink()
                _remove_empty_parents(target, project)
        if desired is not None and stage is not None:
            for relative in sorted(desired_paths - {MANIFEST_PATH, JOURNAL_PATH}):
                source = stage / relative
                target = _safe_path(project, relative, must_exist=False)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or target.is_file():
                    target.unlink()
                if source.is_symlink():
                    target.symlink_to(os.readlink(source))
                else:
                    _atomic_write(target, source.read_bytes())
            _atomic_write(project / MANIFEST_PATH, (stage / MANIFEST_PATH).read_bytes())
            _prove_discovery(project, desired, contract, adapter)
            _atomic_write(project / JOURNAL_PATH, canonical_json_bytes(_clean_journal()))
        else:
            if current is None:
                raise LifecycleError("uninstall transaction has no prior manifest")
            _prove_uninstalled_discovery(project, current, adapter)
            (project / JOURNAL_PATH).unlink(missing_ok=True)
        shutil.rmtree(transaction)
    except BaseException as exc:
        try:
            active = _journal_record(project / JOURNAL_PATH)
            if active and active["state"] != "clean":
                _restore_from_journal(project, active)
        except (OSError, LifecycleError) as restore_exc:
            raise LifecycleError(f"transaction failed and restoration failed: {restore_exc}") from exc
        if isinstance(exc, LifecycleError):
            raise
        raise LifecycleError(f"transaction failed: {exc}") from exc


def _prepare(
    data: LifecycleInput,
    *,
    current_root: Path | None,
    current: Mapping[str, Any] | None,
    generation: int,
    mode: str,
    records: list[dict[str, str]],
) -> tuple[Path, dict[str, Any]]:
    temporary = Path(tempfile.mkdtemp(prefix="engineering-skills-lifecycle-"))
    try:
        manifest = _copy_base(data, temporary)
        previous = _snapshot_current(current_root, current, temporary) if current_root and current else None
        finalized = _finalize_stage(
            temporary,
            manifest,
            data,
            generation=generation,
            previous_digest=current["manifest_sha256"] if current else None,
            previous=previous,
            mode=mode,
            activation_records=records,
        )
        return temporary, finalized
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _execute(
    project_root: Path | str,
    operation: str,
    *,
    adapter: NativeDiscoveryAdapter,
    builder: Any,
    migration_plan: ValidatedMigrationPlan | None = None,
) -> dict[str, Any] | None:
    project = _root_path(project_root, label="project root", may_create=True)
    with _project_lock(project):
        _recover(project)
        current, current_data = _current(project)
        stage: Path | None = None
        try:
            stage, desired, contract = builder(project, current, current_data)
            if stage is None and desired is current:
                return desired
            if desired is not None and stage is not None:
                _verify_owned(stage, desired)
            _commit(
                project,
                stage,
                desired,
                current,
                operation=operation,
                adapter=adapter,
                contract=contract,
                migration_plan=migration_plan,
            )
            return desired
        finally:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)


def install(
    project_root: Path | str,
    data: LifecycleInput,
    *,
    adapter: NativeDiscoveryAdapter,
    migration_plan: ValidatedMigrationPlan | None = None,
) -> dict[str, Any]:
    """Install a verified router-only generation or prove it is idempotent."""
    _validate_input(data, adapter)

    def build(project: Path, current: dict[str, Any] | None, current_data: LifecycleInput | None):
        del current_data
        if current is not None:
            if (
                current["release_root_sha256"] == data.manifest["release_root_sha256"]
                and current["surface_set"] == data.manifest["surface_set"]
            ):
                _prove_discovery(project, current, _load_state(project, current)[1].surface_contract, adapter)
                return None, current, data.surface_contract
            raise LifecycleError("a different toolkit generation is already installed; use update")
        stage, desired = _prepare(
            data,
            current_root=None,
            current=None,
            generation=1,
            mode="router-only",
            records=[],
        )
        return stage, desired, data.surface_contract

    result = _execute(
        project_root,
        "install",
        adapter=adapter,
        builder=build,
        migration_plan=migration_plan,
    )
    if result is None:
        raise LifecycleError("install did not produce an installed generation")
    return result


def verify(project_root: Path | str, *, adapter: NativeDiscoveryAdapter) -> dict[str, Any]:
    """Verify every owned byte, link, manifest relation, and discovery set."""
    project = _root_path(project_root, label="project root", may_create=True)
    with _project_lock(project):
        _recover(project)
        manifest, data = _current(project)
        if manifest is None or data is None:
            raise LifecycleError("toolkit is not installed")
        _validate_input(data, adapter)
        _prove_discovery(project, manifest, data.surface_contract, adapter)
        return manifest


def _version_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"[._-]", value))


def update(
    project_root: Path | str,
    data: LifecycleInput,
    *,
    adapter: NativeDiscoveryAdapter,
    allow_downgrade: bool = False,
    migration_plan: ValidatedMigrationPlan | None = None,
) -> dict[str, Any]:
    """Transactionally update or explicitly downgrade a local verified bundle."""
    _validate_input(data, adapter)

    def build(project: Path, current: dict[str, Any] | None, current_data: LifecycleInput | None):
        if current is None or current_data is None:
            raise LifecycleError("toolkit is not installed")
        same_input = (
            current["release_root_sha256"] == data.manifest["release_root_sha256"]
            and current["surface_set"] == data.manifest["surface_set"]
            and current_data.surface_contract == data.surface_contract
            and current_data.canonical_sources == data.canonical_sources
            and current_data.portfolio == data.portfolio
            and current_data.aliases == data.aliases
        )
        if same_input:
            return None, current, current_data.surface_contract
        if _version_key(data.manifest["bundle_version"]) < _version_key(current["bundle_version"]) and not allow_downgrade:
            raise LifecycleError("downgrade requires explicit allow_downgrade")
        records = deepcopy(current["activation_records"])
        valid = {name: name for name in data.portfolio} | data.aliases
        invalid = [row for row in records if valid.get(row["public_name"]) != row["canonical_target"]]
        if invalid:
            raise LifecycleError(f"update invalidates activation records: {invalid}")
        stage, desired = _prepare(
            data,
            current_root=project,
            current=current,
            generation=current["manifest_generation"] + 1,
            mode=current["mode"],
            records=records,
        )
        return stage, desired, data.surface_contract

    result = _execute(
        project_root,
        "update",
        adapter=adapter,
        builder=build,
        migration_plan=migration_plan,
    )
    if result is None:
        raise LifecycleError("update did not produce an installed generation")
    return result


def _transition(
    project_root: Path | str,
    operation: str,
    *,
    adapter: NativeDiscoveryAdapter,
    transform: Any,
) -> dict[str, Any]:
    def build(project: Path, current: dict[str, Any] | None, data: LifecycleInput | None):
        if current is None or data is None:
            raise LifecycleError("toolkit is not installed")
        mode, records = transform(current, data)
        if mode == current["mode"] and records == current["activation_records"]:
            _prove_discovery(project, current, data.surface_contract, adapter)
            return None, current, data.surface_contract
        stage, desired = _prepare(
            data,
            current_root=project,
            current=current,
            generation=current["manifest_generation"] + 1,
            mode=mode,
            records=records,
        )
        return stage, desired, data.surface_contract

    result = _execute(project_root, operation, adapter=adapter, builder=build)
    if result is None:
        raise LifecycleError(f"{operation} did not produce an installed generation")
    return result


def activate(
    project_root: Path | str,
    public_name: str,
    *,
    adapter: NativeDiscoveryAdapter,
    invocation_id: str | None = None,
) -> dict[str, Any]:
    """Persistently activate one canonical name or declared alias."""
    if _PUBLIC_NAME.fullmatch(public_name) is None:
        raise LifecycleError("activation public name is invalid")
    if invocation_id is not None and _UUID4.fullmatch(invocation_id) is None:
        raise LifecycleError("temporary invocation id must be lowercase UUIDv4")

    def transform(current: Mapping[str, Any], data: LifecycleInput):
        if invocation_id is not None:
            surfaces = _surface_records(data.surface_contract).values()
            if any(row["activation"]["temporary_activation"] != "verified" for row in surfaces):
                raise LifecycleError("temporary activation unsupported without verified terminal wrapper and startup cleanup")
            raise LifecycleError("temporary activation wrapper execution belongs to the surface runtime")
        targets = {name: name for name in data.portfolio} | data.aliases
        target = targets.get(public_name)
        if target is None:
            raise LifecycleError(f"unknown activation name: {public_name}")
        if public_name in {"which-shape", "which-skill"}:
            return current["mode"], deepcopy(current["activation_records"])
        records = deepcopy(current["activation_records"])
        record = {"public_name": public_name, "canonical_target": target}
        if record not in records:
            if any(row["public_name"] == public_name for row in records):
                raise LifecycleError("activation name is already bound to a different target")
            records.append(record)
            records.sort(key=lambda row: row["public_name"])
        return current["mode"], records

    return _transition(project_root, "activate", adapter=adapter, transform=transform)


def deactivate(
    project_root: Path | str,
    public_name: str,
    *,
    adapter: NativeDiscoveryAdapter,
) -> dict[str, Any]:
    """Remove exactly one persistent activation record, idempotently."""
    if _PUBLIC_NAME.fullmatch(public_name) is None:
        raise LifecycleError("deactivation public name is invalid")

    def transform(current: Mapping[str, Any], data: LifecycleInput):
        del data
        records = [
            deepcopy(row) for row in current["activation_records"] if row["public_name"] != public_name
        ]
        return current["mode"], records

    return _transition(project_root, "deactivate", adapter=adapter, transform=transform)


def set_mode(
    project_root: Path | str,
    mode: str,
    *,
    adapter: NativeDiscoveryAdapter,
) -> dict[str, Any]:
    """Switch the exact activation mode without changing activation records."""
    if mode not in {"router-only", "full-discovery"}:
        raise LifecycleError("mode must be router-only or full-discovery")

    def transform(current: Mapping[str, Any], data: LifecycleInput):
        del data
        return mode, deepcopy(current["activation_records"])

    return _transition(project_root, "set-mode", adapter=adapter, transform=transform)


def rollback(project_root: Path | str, *, adapter: NativeDiscoveryAdapter) -> dict[str, Any]:
    """Restore the immediately previous validated generation transactionally."""
    def build(project: Path, current: dict[str, Any] | None, data: LifecycleInput | None):
        if current is None or data is None:
            raise LifecycleError("toolkit is not installed")
        state, _ = _load_state(project, current)
        previous = state["previous"]
        if previous is None or previous["manifest_sha256"] != current["previous_manifest_sha256"]:
            raise LifecycleError("no immediately previous validated generation is retained")
        restored_root = Path(tempfile.mkdtemp(prefix="engineering-skills-rollback-"))
        try:
            for row in previous["files"]:
                if row["kind"] == "link":
                    if (
                        row["archive"] is not None
                        or len(row["link_target"].encode()) != row["size"]
                        or _sha(row["link_target"].encode()) != row["sha256"]
                    ):
                        raise LifecycleError(
                            f"previous generation link metadata is corrupt: {row['path']}"
                        )
                    target = restored_root / row["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(row["link_target"])
                else:
                    content = (project / row["archive"]).read_bytes()
                    if len(content) != row["size"] or _sha(content) != row["sha256"]:
                        raise LifecycleError(
                            f"previous generation archive is corrupt: {row['path']}"
                        )
                    _atomic_write(restored_root / row["path"], content)
            manifest_bytes = (project / previous["manifest_archive"]).read_bytes()
            restored_manifest = json.loads(manifest_bytes)
            _atomic_write(restored_root / MANIFEST_PATH, manifest_bytes)
            _, restored_data = _load_state(restored_root, restored_manifest)
            stage, desired = _prepare(
                restored_data,
                current_root=project,
                current=current,
                generation=current["manifest_generation"] + 1,
                mode=restored_manifest["mode"],
                records=deepcopy(restored_manifest["activation_records"]),
            )
            return stage, desired, restored_data.surface_contract
        finally:
            shutil.rmtree(restored_root, ignore_errors=True)

    result = _execute(project_root, "rollback", adapter=adapter, builder=build)
    if result is None:
        raise LifecycleError("rollback did not produce an installed generation")
    return result


def uninstall(project_root: Path | str, *, adapter: NativeDiscoveryAdapter) -> None:
    """Remove only byte-identical manifest-owned objects; preserve host data."""
    project = _root_path(project_root, label="project root", may_create=True)
    with _project_lock(project):
        _recover(project)
        current, data = _current(project)
        if current is None:
            return
        assert data is not None

        _execute_unlocked_uninstall(project, current, adapter)


def _execute_unlocked_uninstall(
    project: Path, current: Mapping[str, Any], adapter: NativeDiscoveryAdapter
) -> None:
    _commit(
        project,
        None,
        None,
        current,
        operation="uninstall",
        adapter=adapter,
        contract=None,
        migration_plan=None,
    )
    for path in sorted(project.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
