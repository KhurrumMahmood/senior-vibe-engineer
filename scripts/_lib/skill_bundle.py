"""Build and verify ADR 0042's acyclic offline distribution trust graph.

This module deliberately stops at a new, empty install image. Transactional
host mutation, update, rollback, activation, and uninstall belong to IM-15.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .distribution_contracts import (
    CONTRACT_ROOT,
    SCHEMA_NAMES,
    TABLE_NAMES,
    DistributionContractError,
    canonical_json_bytes,
    canonical_sha256,
    load_canonical_json,
    load_distribution_tables,
    validate_distribution_contract,
)


RELEASE_ROOT_NAME = "release-root-v1.json"
BUNDLE_INDEX_NAME = "bundle-index-v1.json"
INSTALLED_MANIFEST_PATH = ".engineering/installed-manifest-v1.json"
BOOTSTRAP_METADATA_TEMPLATE = ".engineering/bootstrap/{surface_id}/bootstrap-v1.json"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RESERVED_GRAPH_NAMES = {
    RELEASE_ROOT_NAME,
    BUNDLE_INDEX_NAME,
    "installed-manifest-v1.json",
}
_RECIPE_FIELDS = {
    "schema_version",
    "surface_id",
    "manifest_locator",
    "bootstrap_metadata_path",
    "routers",
    "runtime_files",
}
_RECIPE_ROUTER_FIELDS = {"canonical_name", "blob_id", "path"}
_RECIPE_RUNTIME_FIELDS = {"blob_id", "path"}
_SURFACE_IDS = {"augment", "claude-code", "codex", "cursor", "gemini"}
_DISCOVERY_PREFIXES = (
    ".augment/rules/imported/",
    ".claude/skills/",
    ".cursor/rules/",
    ".gemini/skills/",
    "skills/",
)


class BundleTrustError(DistributionContractError):
    """An offline release or install image violates its trust contract."""


@dataclass(frozen=True)
class BlobSource:
    """One immutable bundle-index input rooted below ``source_root``."""

    kind: str
    blob_id: str
    source: str
    media_type: str


@dataclass(frozen=True)
class VerifiedBundle:
    """A release verified from its out-of-band root through every raw blob."""

    root: Path
    release_root: dict[str, Any]
    bundle_index: dict[str, Any]
    release_root_sha256: str
    bundle_index_sha256: str
    blobs_by_id: Mapping[str, dict[str, Any]]
    surface_contract: dict[str, Any]


def raw_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_relative_path(value: object, *, location: str = "path") -> str:
    """Require one NFC-normalized, non-traversing relative POSIX path."""
    if not isinstance(value, str) or not value:
        raise BundleTrustError(f"{location} must be a non-empty string")
    if value != unicodedata.normalize("NFC", value):
        raise BundleTrustError(f"{location} must be NFC")
    if "\\" in value or "\x00" in value or value.startswith("/"):
        raise BundleTrustError(f"{location} must be a relative POSIX path")
    segments = value.split("/")
    if any(not segment for segment in segments):
        raise BundleTrustError(f"{location} contains an empty slash-separated segment")
    # Inspect the raw slash-separated representation before constructing a
    # PurePosixPath: pathlib normalizes explicit ``.`` segments away.
    if any(segment in {".", ".."} for segment in segments):
        raise BundleTrustError(f"{location} contains an empty or dot segment")
    if len(value.encode("utf-8")) > 1024:
        raise BundleTrustError(f"{location} exceeds 1024 UTF-8 bytes")
    return value


def _root_path(path: Path, *, must_exist: bool) -> Path:
    """Reject a caller-supplied root symlink before obtaining its absolute path."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if must_exist:
            raise BundleTrustError(f"trusted root is missing: {path}") from None
    else:
        if stat.S_ISLNK(metadata.st_mode):
            raise BundleTrustError(f"trusted root must not be a symlink: {path}")
    return path.resolve()


def _safe_path(root: Path, relative: str, *, must_exist: bool) -> Path:
    validate_relative_path(relative)
    if root.is_symlink() or not root.is_dir():
        raise BundleTrustError(f"trusted root is not a real directory: {root}")
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except FileNotFoundError:
            if must_exist:
                raise BundleTrustError(f"trusted path is missing: {relative}") from None
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise BundleTrustError(f"trusted path traverses a symlink: {relative}")
        if cursor != root / relative and not stat.S_ISDIR(metadata.st_mode):
            raise BundleTrustError(f"trusted path has a non-directory ancestor: {relative}")
    return cursor


def _read_file(root: Path, relative: str) -> bytes:
    path = _safe_path(root, relative, must_exist=True)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise BundleTrustError(f"trusted path is not a regular file: {relative}")
    return path.read_bytes()


def _write_file(root: Path, relative: str, content: bytes) -> None:
    path = _safe_path(root, relative, must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise BundleTrustError(f"refusing to replace output path: {relative}")
    path.write_bytes(content)


def _row(path: str, content: bytes) -> dict[str, Any]:
    return {"path": path, "size": len(content), "sha256": raw_sha256(content)}


def tree_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return exact NFC/UTF-8 sorted tree rows after strict path validation."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if set(row) != {"path", "size", "sha256"}:
            raise BundleTrustError(f"tree row {index} has unknown or missing fields")
        path = validate_relative_path(row["path"], location=f"tree[{index}].path")
        if path in seen:
            raise BundleTrustError(f"duplicate tree path: {path}")
        seen.add(path)
        size, digest = row["size"], row["sha256"]
        if type(size) is not int or size < 0:
            raise BundleTrustError(f"tree[{index}].size must be a nonnegative integer")
        if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
            raise BundleTrustError(f"tree[{index}].sha256 is invalid")
        normalized.append({"path": path, "size": size, "sha256": digest})
    return sorted(normalized, key=lambda item: item["path"].encode("utf-8"))


def tree_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    return canonical_sha256(tree_rows(rows))


def _verify_row(root: Path, row: Mapping[str, Any], *, location: str) -> bytes:
    if set(row) != {"path", "size", "sha256"}:
        raise BundleTrustError(f"{location} has unknown or missing fields")
    content = _read_file(root, validate_relative_path(row["path"], location=location))
    if row["size"] != len(content) or row["sha256"] != raw_sha256(content):
        raise BundleTrustError(f"{location} raw size or SHA-256 differs")
    return content


def _strict_json_bytes(content: bytes, *, location: str, canonical: bool) -> Any:
    try:
        text = content.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _unique_pairs(pairs, location),
            parse_float=lambda value: _reject_number(value, location),
            parse_constant=lambda value: _reject_number(value, location),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleTrustError(f"{location} is not strict UTF-8 JSON") from exc
    if canonical and content != canonical_json_bytes(value):
        raise BundleTrustError(f"{location} raw bytes are not canonical JCS")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]], location: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BundleTrustError(f"{location} contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_number(value: str, location: str) -> None:
    raise BundleTrustError(f"{location} contains non-integer JSON number {value}")


def _surface_map(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["surface_id"]: row for row in contract["surfaces"]}


def _validate_recipe(
    value: object,
    *,
    surface_contract: Mapping[str, Any],
    blob_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _RECIPE_FIELDS:
        raise BundleTrustError("projection recipe has unknown or missing fields")
    if value["schema_version"] != 1 or value["surface_id"] not in _SURFACE_IDS:
        raise BundleTrustError("projection recipe has unknown version or surface")
    surface_id = value["surface_id"]
    surface = _surface_map(surface_contract)[surface_id]
    manifest_locator = validate_relative_path(
        value["manifest_locator"], location="projection recipe manifest_locator"
    )
    if manifest_locator != INSTALLED_MANIFEST_PATH:
        raise BundleTrustError("projection recipe manifest locator differs from v1")
    expected_metadata = BOOTSTRAP_METADATA_TEMPLATE.format(surface_id=surface_id)
    if value["bootstrap_metadata_path"] != expected_metadata:
        raise BundleTrustError("projection recipe bootstrap metadata path differs from v1")
    routers = value["routers"]
    if not isinstance(routers, list) or len(routers) != 2:
        raise BundleTrustError("projection recipe must declare exactly two routers")
    expected_paths = surface["generated_identity"]
    expected_routers = {"which-shape": expected_paths["which_shape"], "which-skill": expected_paths["which_skill"]}
    seen_names: set[str] = set()
    seen_paths: set[str] = {expected_metadata}
    for index, row in enumerate(routers):
        if not isinstance(row, dict) or set(row) != _RECIPE_ROUTER_FIELDS:
            raise BundleTrustError(f"projection recipe routers[{index}] is not closed")
        name, blob_id = row["canonical_name"], row["blob_id"]
        if name not in expected_routers or row["path"] != expected_routers.get(name):
            raise BundleTrustError("projection recipe router path differs from surface identity")
        if blob_id not in blob_ids or blob_id != name:
            raise BundleTrustError("projection recipe router blob is missing or mislabeled")
        validate_relative_path(row["path"])
        if name in seen_names or row["path"] in seen_paths:
            raise BundleTrustError("projection recipe router is duplicated")
        seen_names.add(name)
        seen_paths.add(row["path"])
    if seen_names != set(expected_routers):
        raise BundleTrustError("projection recipe omits a complete router procedure")
    runtime_files = value["runtime_files"]
    if not isinstance(runtime_files, list):
        raise BundleTrustError("projection recipe runtime_files must be an array")
    for index, row in enumerate(runtime_files):
        if not isinstance(row, dict) or set(row) != _RECIPE_RUNTIME_FIELDS:
            raise BundleTrustError(f"projection recipe runtime_files[{index}] is not closed")
        if row["blob_id"] not in blob_ids:
            raise BundleTrustError("projection recipe runtime blob is missing")
        path = validate_relative_path(row["path"])
        if PurePosixPath(path).name in {"SKILL.md", "SKILL.mdc"}:
            raise BundleTrustError("projection runtime file cannot add an ambient skill header")
        if path in seen_paths:
            raise BundleTrustError("projection recipe target path is duplicated")
        seen_paths.add(path)
    if runtime_files != sorted(runtime_files, key=lambda row: row["path"].encode("utf-8")):
        raise BundleTrustError("projection recipe runtime files are not UTF-8 path sorted")
    return value


def _build_release_bundle(
    source_root: Path,
    output_root: Path,
    *,
    bundle_version: str,
    blobs: Sequence[BlobSource],
    installer: str,
    surface_activation_contract: str,
    contract_root: Path = CONTRACT_ROOT,
) -> str:
    """Create a deterministic release and return its out-of-band root digest."""
    source = _root_path(source_root, must_exist=True)
    output = _root_path(output_root, must_exist=False)
    if output.exists() and (
        output.is_symlink() or not output.is_dir() or any(output.iterdir())
    ):
        raise BundleTrustError("release output must be absent or an empty real directory")
    output.mkdir(parents=True, exist_ok=True)

    ids = [item.blob_id for item in blobs]
    if len(ids) != len(set(ids)) or any(_ID.fullmatch(item) is None for item in ids):
        raise BundleTrustError("bundle blob ids must be unique safe IDs")
    required_kinds = {"catalog": 1, "registry": 1, "profile": 1}
    for kind, count in required_kinds.items():
        if sum(item.kind == kind for item in blobs) != count:
            raise BundleTrustError(f"bundle must contain exactly {count} {kind} blob")
    if {item.blob_id for item in blobs if item.kind == "router"} != {
        "which-shape",
        "which-skill",
    }:
        raise BundleTrustError("bundle must contain exactly both canonical router blobs")

    blob_rows: list[dict[str, Any]] = []
    source_bytes: dict[str, bytes] = {}
    for item in sorted(blobs, key=lambda candidate: candidate.blob_id.encode("utf-8")):
        content = _read_file(source, item.source)
        digest = raw_sha256(content)
        relative = f"blobs/sha256/{digest}/{item.blob_id}"
        _write_file(output, relative, content)
        blob_rows.append(
            {
                "kind": item.kind,
                "id": item.blob_id,
                **_row(relative, content),
                "media_type": item.media_type,
            }
        )
        source_bytes[item.blob_id] = content

    contract_content = _read_file(source, surface_activation_contract)
    contract = _strict_json_bytes(
        contract_content, location="surface activation contract", canonical=True
    )
    validate_distribution_contract("surface-activation-contract-v1", contract)
    _write_file(output, "surface-activation-contract-v1.json", contract_content)
    blob_ids = set(ids)
    for item in blobs:
        if item.kind == "projection-recipe":
            recipe = _strict_json_bytes(
                source_bytes[item.blob_id],
                location=f"projection recipe {item.blob_id}",
                canonical=True,
            )
            _validate_recipe(recipe, surface_contract=contract, blob_ids=blob_ids)

    by_kind = {kind: next(row for row in blob_rows if row["kind"] == kind) for kind in required_kinds}
    bundle_index = {
        "schema_version": 1,
        "bundle_version": bundle_version,
        "catalog_inventory_sha256": by_kind["catalog"]["sha256"],
        "capability_registry_sha256": by_kind["registry"]["sha256"],
        "required_profile_sha256": by_kind["profile"]["sha256"],
        "blobs": blob_rows,
        "tree_sha256": tree_sha256(
            [{key: row[key] for key in ("path", "size", "sha256")} for row in blob_rows]
        ),
    }
    validate_distribution_contract("bundle-index-v1", bundle_index)
    bundle_bytes = canonical_json_bytes(bundle_index)
    _write_file(output, BUNDLE_INDEX_NAME, bundle_bytes)

    schema_rows: list[dict[str, Any]] = []
    for name in SCHEMA_NAMES:
        content = (contract_root / f"{name}.schema.json").read_bytes()
        parsed = _strict_json_bytes(content, location=f"schema {name}", canonical=False)
        expected_id = f"urn:engineering-skills:schema:{name.removesuffix('-v1')}:v1"
        if not isinstance(parsed, dict) or parsed.get("$id") != expected_id:
            raise BundleTrustError(f"schema {name} has the wrong exact $id")
        relative = f"schemas/{name}.schema.json"
        _write_file(output, relative, content)
        schema_rows.append({"schema_id": name, **_row(relative, content)})

    canonical_names = {
        row["id"] for row in blob_rows if row["kind"] in {"procedure", "router"}
    }
    tables = load_distribution_tables(contract_root, canonical_names=canonical_names)
    expected_versions = tables["compatibility-v1"]["surfaces"]
    if any(
        surface["runtime_version"] != expected_versions[surface["surface_id"]]
        for surface in contract["surfaces"]
    ):
        raise BundleTrustError("surface contract versions differ from compatibility-v1")
    table_rows: list[dict[str, Any]] = []
    for name in TABLE_NAMES:
        content = (contract_root / f"{name}.json").read_bytes()
        relative = f"tables/{name}.json"
        _write_file(output, relative, content)
        table_rows.append({"table_id": name, **_row(relative, content)})

    installer_content = _read_file(source, installer)
    installer_path = "installer/skill-bundle.py"
    _write_file(output, installer_path, installer_content)
    release_root = {
        "schema_version": 1,
        "bundle_version": bundle_version,
        "bundle_index": _row(BUNDLE_INDEX_NAME, bundle_bytes),
        "installer": _row(installer_path, installer_content),
        "surface_activation_contract": _row(
            "surface-activation-contract-v1.json", contract_content
        ),
        "schemas": schema_rows,
        "tables": table_rows,
    }
    validate_distribution_contract("release-root-v1", release_root)
    release_bytes = canonical_json_bytes(release_root)
    _write_file(output, RELEASE_ROOT_NAME, release_bytes)
    digest = raw_sha256(release_bytes)
    verify_release_bundle(output, digest)
    return digest


def build_release_bundle(
    source_root: Path,
    output_root: Path,
    *,
    bundle_version: str,
    blobs: Sequence[BlobSource],
    installer: str,
    surface_activation_contract: str,
    contract_root: Path = CONTRACT_ROOT,
) -> str:
    """Build a release and normalize all trust failures to ``BundleTrustError``."""
    try:
        return _build_release_bundle(
            source_root,
            output_root,
            bundle_version=bundle_version,
            blobs=blobs,
            installer=installer,
            surface_activation_contract=surface_activation_contract,
            contract_root=contract_root,
        )
    except BundleTrustError:
        raise
    except DistributionContractError as exc:
        raise BundleTrustError(str(exc)) from exc


def _verify_release_bundle(bundle_root: Path, expected_release_root_sha256: str) -> VerifiedBundle:
    """Verify external root -> canonical release -> bundle -> every raw blob."""
    root = _root_path(bundle_root, must_exist=True)
    if _HASH.fullmatch(expected_release_root_sha256) is None:
        raise BundleTrustError("expected release-root SHA-256 must be lowercase hexadecimal")
    release_bytes = _read_file(root, RELEASE_ROOT_NAME)
    if raw_sha256(release_bytes) != expected_release_root_sha256:
        raise BundleTrustError("release root differs from the out-of-band SHA-256")
    release = _strict_json_bytes(release_bytes, location=RELEASE_ROOT_NAME, canonical=True)
    validate_distribution_contract("release-root-v1", release)
    if any(PurePosixPath(row["path"]).name == RELEASE_ROOT_NAME for row in [release["bundle_index"], release["installer"], release["surface_activation_contract"], *release["schemas"], *release["tables"]]):
        raise BundleTrustError("release root contains a self edge")

    bundle_bytes = _verify_row(root, release["bundle_index"], location="bundle_index")
    bundle = _strict_json_bytes(bundle_bytes, location=BUNDLE_INDEX_NAME, canonical=True)
    validate_distribution_contract("bundle-index-v1", bundle)
    if bundle["bundle_version"] != release["bundle_version"]:
        raise BundleTrustError("release and bundle versions differ")
    if release["bundle_index"]["path"] != BUNDLE_INDEX_NAME:
        raise BundleTrustError("release root bundle-index path differs from v1")

    schema_ids = [row["schema_id"] for row in release["schemas"]]
    table_ids = [row["table_id"] for row in release["tables"]]
    if schema_ids != list(SCHEMA_NAMES) or table_ids != list(TABLE_NAMES):
        raise BundleTrustError("release schema/table IDs or order differ from exact v1")
    for row in release["schemas"]:
        if row["path"] != f"schemas/{row['schema_id']}.schema.json":
            raise BundleTrustError("release schema path differs from its exact schema ID")
        content = _verify_row(root, {key: row[key] for key in ("path", "size", "sha256")}, location=f"schema {row['schema_id']}")
        parsed = _strict_json_bytes(content, location=f"schema {row['schema_id']}", canonical=False)
        expected_id = f"urn:engineering-skills:schema:{row['schema_id'].removesuffix('-v1')}:v1"
        if not isinstance(parsed, dict) or parsed.get("$id") != expected_id:
            raise BundleTrustError(f"schema {row['schema_id']} has the wrong exact $id")
    for row in release["tables"]:
        if row["path"] != f"tables/{row['table_id']}.json":
            raise BundleTrustError("release table path differs from its exact table ID")
        _verify_row(root, {key: row[key] for key in ("path", "size", "sha256")}, location=f"table {row['table_id']}")
    table_root = _safe_path(root, "tables", must_exist=True)
    canonical_names = {row["id"] for row in bundle["blobs"] if row["kind"] in {"procedure", "router"}}
    tables = load_distribution_tables(table_root, canonical_names=canonical_names)

    contract_bytes = _verify_row(root, release["surface_activation_contract"], location="surface activation contract")
    if release["surface_activation_contract"]["path"] != "surface-activation-contract-v1.json":
        raise BundleTrustError("surface activation contract path differs from v1")
    contract = _strict_json_bytes(contract_bytes, location="surface activation contract", canonical=True)
    validate_distribution_contract("surface-activation-contract-v1", contract)
    expected_versions = tables["compatibility-v1"]["surfaces"]
    if any(
        surface["runtime_version"] != expected_versions[surface["surface_id"]]
        for surface in contract["surfaces"]
    ):
        raise BundleTrustError("surface contract versions differ from compatibility-v1")
    _verify_row(root, release["installer"], location="installer")

    ids: set[str] = set()
    paths: set[str] = set()
    rows: list[dict[str, Any]] = []
    blobs_by_id: dict[str, dict[str, Any]] = {}
    for row in bundle["blobs"]:
        if row["id"] in ids or row["path"] in paths:
            raise BundleTrustError("bundle blob IDs and paths must be unique")
        ids.add(row["id"])
        paths.add(row["path"])
        if PurePosixPath(row["path"]).name in _RESERVED_GRAPH_NAMES:
            raise BundleTrustError("bundle index contains a backward or self edge")
        expected_prefix = f"blobs/sha256/{row['sha256']}/"
        if not row["path"].startswith(expected_prefix):
            raise BundleTrustError("bundle blob path is not content-addressed")
        content = _verify_row(root, {key: row[key] for key in ("path", "size", "sha256")}, location=f"blob {row['id']}")
        rows.append({key: row[key] for key in ("path", "size", "sha256")})
        blobs_by_id[row["id"]] = row
        if row["kind"] == "projection-recipe":
            recipe = _strict_json_bytes(content, location=f"projection recipe {row['id']}", canonical=True)
            _validate_recipe(recipe, surface_contract=contract, blob_ids=ids | {item["id"] for item in bundle["blobs"]})
    if bundle["blobs"] != sorted(
        bundle["blobs"], key=lambda item: item["id"].encode("utf-8")
    ):
        raise BundleTrustError("bundle blobs are not sorted by UTF-8 blob id")
    if bundle["tree_sha256"] != tree_sha256(rows):
        raise BundleTrustError("bundle-index tree digest differs from exact blob rows")
    for kind, field in (("catalog", "catalog_inventory_sha256"), ("registry", "capability_registry_sha256"), ("profile", "required_profile_sha256")):
        kind_rows = [row for row in bundle["blobs"] if row["kind"] == kind]
        if len(kind_rows) != 1 or kind_rows[0]["sha256"] != bundle[field]:
            raise BundleTrustError(f"bundle {field} is not bound to exactly one {kind} blob")
    if {row["id"] for row in bundle["blobs"] if row["kind"] == "router"} != {"which-shape", "which-skill"}:
        raise BundleTrustError("bundle does not contain exactly both routers")
    for row in bundle["blobs"]:
        if row["kind"] != "projection-recipe":
            continue
        recipe = _strict_json_bytes(
            _read_file(root, row["path"]),
            location=f"projection recipe {row['id']}",
            canonical=True,
        )
        for router in recipe["routers"]:
            if blobs_by_id[router["blob_id"]]["kind"] != "router":
                raise BundleTrustError("projection recipe router does not reference a router blob")
        for runtime in recipe["runtime_files"]:
            if blobs_by_id[runtime["blob_id"]]["kind"] != "asset":
                raise BundleTrustError("projection recipe runtime does not reference an asset blob")
    return VerifiedBundle(
        root=root,
        release_root=release,
        bundle_index=bundle,
        release_root_sha256=expected_release_root_sha256,
        bundle_index_sha256=raw_sha256(bundle_bytes),
        blobs_by_id=blobs_by_id,
        surface_contract=contract,
    )


def verify_release_bundle(
    bundle_root: Path, expected_release_root_sha256: str
) -> VerifiedBundle:
    """Normalize every structural/table failure to the public trust error type."""
    try:
        return _verify_release_bundle(bundle_root, expected_release_root_sha256)
    except BundleTrustError:
        raise
    except DistributionContractError as exc:
        raise BundleTrustError(str(exc)) from exc


def _load_recipe(bundle: VerifiedBundle, recipe_id: str) -> dict[str, Any]:
    row = bundle.blobs_by_id.get(recipe_id)
    if row is None or row["kind"] != "projection-recipe":
        raise BundleTrustError(f"unknown projection recipe: {recipe_id}")
    value = _strict_json_bytes(
        _read_file(bundle.root, row["path"]),
        location=f"projection recipe {recipe_id}",
        canonical=True,
    )
    return _validate_recipe(
        value,
        surface_contract=bundle.surface_contract,
        blob_ids=set(bundle.blobs_by_id),
    )


def _load_recipe_set(
    bundle: VerifiedBundle,
    *,
    recipe_id: str | None,
    recipe_ids: Sequence[str] | None,
) -> list[dict[str, Any]]:
    if (recipe_id is None) == (recipe_ids is None):
        raise BundleTrustError("supply exactly one recipe_id or ordered recipe_ids set")
    selected_ids = [recipe_id] if recipe_id is not None else list(recipe_ids or ())
    if not 1 <= len(selected_ids) <= 5 or len(selected_ids) != len(set(selected_ids)):
        raise BundleTrustError("recipe set must contain 1 through 5 unique IDs")
    recipes = [_load_recipe(bundle, selected) for selected in selected_ids]
    surfaces = [recipe["surface_id"] for recipe in recipes]
    if len(surfaces) != len(set(surfaces)):
        raise BundleTrustError("recipe set contains a duplicate surface")
    return recipes


def _materialize_install_image(
    bundle: VerifiedBundle,
    output_root: Path,
    *,
    recipe_id: str | None,
    recipe_ids: Sequence[str] | None,
) -> dict[str, Any]:
    """Materialize a new router-only image without implementing host lifecycle."""
    output = _root_path(output_root, must_exist=False)
    if output.exists() and (
        output.is_symlink() or not output.is_dir() or any(output.iterdir())
    ):
        raise BundleTrustError("install image output must be absent or an empty real directory")
    output.mkdir(parents=True, exist_ok=True)
    recipes = _load_recipe_set(
        bundle, recipe_id=recipe_id, recipe_ids=recipe_ids
    )

    catalog_rows: list[dict[str, Any]] = []
    catalog_prefix = f".engineering/catalog/{bundle.bundle_index_sha256}"
    for row in bundle.bundle_index["blobs"]:
        target = f"{catalog_prefix}/{row['path']}"
        content = _read_file(bundle.root, row["path"])
        _write_file(output, target, content)
        catalog_rows.append(_row(target, content))

    bootstrap_by_surface: dict[str, list[dict[str, Any]]] = {}
    for recipe in recipes:
        surface_id = recipe["surface_id"]
        bootstrap_rows: list[dict[str, Any]] = []
        router_records: list[dict[str, Any]] = []
        runtime_records: list[dict[str, Any]] = []
        for recipe_row, target_records in (
            *((row, router_records) for row in recipe["routers"]),
            *((row, runtime_records) for row in recipe["runtime_files"]),
        ):
            blob = bundle.blobs_by_id[recipe_row["blob_id"]]
            content = _read_file(bundle.root, blob["path"])
            _write_file(output, recipe_row["path"], content)
            record = _row(recipe_row["path"], content)
            if target_records is router_records:
                record = {"canonical_name": recipe_row["canonical_name"], **record}
            target_records.append(record)
            bootstrap_rows.append(_row(recipe_row["path"], content))

        surface = _surface_map(bundle.surface_contract)[surface_id]
        bootstrap = {
            "schema_version": 1,
            "surface_id": surface_id,
            "surface_identity": {
                "public_identity": surface["public_identity"],
                "generated_identity": surface["generated_identity"],
            },
            "manifest_locator": recipe["manifest_locator"],
            "release_root_sha256": bundle.release_root_sha256,
            "bundle_index_sha256": bundle.bundle_index_sha256,
            "routers": router_records,
            "runtime_files": runtime_records,
        }
        bootstrap_bytes = canonical_json_bytes(bootstrap)
        _write_file(output, recipe["bootstrap_metadata_path"], bootstrap_bytes)
        bootstrap_rows.append(_row(recipe["bootstrap_metadata_path"], bootstrap_bytes))
        bootstrap_by_surface[surface_id] = tree_rows(bootstrap_rows)
    all_bootstrap_rows = tree_rows(
        [row for rows in bootstrap_by_surface.values() for row in rows]
    )

    recovery_bytes = canonical_json_bytes(
        {"schema_version": 1, "state": "clean", "temporary_records": []}
    )
    recovery_path = ".engineering/recovery-v1.json"
    _write_file(output, recovery_path, recovery_bytes)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_sha256": "0" * 64,
        "manifest_generation": 1,
        "previous_manifest_sha256": None,
        "bundle_version": bundle.bundle_index["bundle_version"],
        "release_root_sha256": bundle.release_root_sha256,
        "bundle_index_sha256": bundle.bundle_index_sha256,
        "surface_activation_contract_sha256": bundle.release_root[
            "surface_activation_contract"
        ]["sha256"],
        "catalog_hash": bundle.bundle_index["catalog_inventory_sha256"],
        "mode": "router-only",
        "activation_records": [],
        "surface_set": [recipe["surface_id"] for recipe in recipes],
        "owned_paths": {
            "catalog_store": catalog_rows,
            "bootstrap_projections": all_bootstrap_rows,
            "activation_projections": [],
            "full_discovery_projections": [],
            "activation_state": [],
            "recovery_journal": [_row(recovery_path, recovery_bytes)],
            "generated_links": [],
        },
        "generated_files": [
            {
                "ownership_class": "bootstrap",
                "surface_id": surface_id,
                **row,
            }
            for surface_id, rows in bootstrap_by_surface.items()
            for row in rows
        ],
        "bootstrap_trees": [
            {
                "surface_id": surface_id,
                "file_count": len(rows),
                "tree_sha256": tree_sha256(rows),
            }
            for surface_id, rows in bootstrap_by_surface.items()
        ],
        "recovery": {
            "state": "clean",
            "journal_path": recovery_path,
            "journal_sha256": raw_sha256(recovery_bytes),
            "temporary_records": [],
        },
        "cleanup": {
            "state": "clean",
            "last_cleaned_generation": 1,
            "failure_code": None,
        },
        "delegation_policy": {
            "dispatcher_policy_version": 1,
            "project_lane_limit": 1,
            "delegation_depth": 1,
            "max_workflow_packs": 16,
            "max_dispatches_per_pack": 2,
            "deadline_seconds": 1200,
            "total_token_budget": 32768,
            "output_token_budget": 8192,
            "fallback_reasons": [
                "conversation_state_required",
                "user_interaction_required",
                "nondelegable_authority_required",
                "surface_worker_unsupported",
                "user_confirmed_after_worker_failure",
            ],
        },
    }
    manifest["manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    validate_distribution_contract("installed-manifest-v1", manifest)
    _write_file(output, INSTALLED_MANIFEST_PATH, canonical_json_bytes(manifest))
    verify_install_image(
        bundle,
        output,
        recipe_id=recipe_id,
        recipe_ids=recipe_ids,
    )
    return manifest


def materialize_install_image(
    bundle: VerifiedBundle,
    output_root: Path,
    *,
    recipe_id: str | None = None,
    recipe_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a new image and normalize all trust failures."""
    try:
        return _materialize_install_image(
            bundle,
            output_root,
            recipe_id=recipe_id,
            recipe_ids=recipe_ids,
        )
    except BundleTrustError:
        raise
    except DistributionContractError as exc:
        raise BundleTrustError(str(exc)) from exc


def _verify_surface_bootstrap(
    bundle: VerifiedBundle,
    root: Path,
    recipe: dict[str, Any],
    bootstrap_bytes: Mapping[str, bytes],
    surface_paths: set[str],
) -> None:
    metadata_bytes = bootstrap_bytes.get(recipe["bootstrap_metadata_path"])
    if metadata_bytes is None:
        raise BundleTrustError("bootstrap metadata is absent from the exact bootstrap tree")
    metadata = _strict_json_bytes(metadata_bytes, location="bootstrap metadata", canonical=True)
    expected_keys = {
        "schema_version",
        "surface_id",
        "surface_identity",
        "manifest_locator",
        "release_root_sha256",
        "bundle_index_sha256",
        "routers",
        "runtime_files",
    }
    if not isinstance(metadata, dict) or set(metadata) != expected_keys:
        raise BundleTrustError("bootstrap metadata has unknown or missing fields")
    if metadata["schema_version"] != 1 or metadata["manifest_locator"] != INSTALLED_MANIFEST_PATH:
        raise BundleTrustError("bootstrap schema version or relative manifest locator differs")
    if metadata["surface_id"] != recipe["surface_id"]:
        raise BundleTrustError("bootstrap surface id differs from its recipe")
    if metadata["release_root_sha256"] != bundle.release_root_sha256 or metadata[
        "bundle_index_sha256"
    ] != bundle.bundle_index_sha256:
        raise BundleTrustError("bootstrap release digests differ")
    expected_surface = _surface_map(bundle.surface_contract)[recipe["surface_id"]]
    if metadata["surface_identity"] != {
        "public_identity": expected_surface["public_identity"],
        "generated_identity": expected_surface["generated_identity"],
    }:
        raise BundleTrustError("bootstrap surface identity differs")
    manifest_path = _safe_path(root, metadata["manifest_locator"], must_exist=True)
    if manifest_path != root / INSTALLED_MANIFEST_PATH:
        raise BundleTrustError("bootstrap manifest locator escapes the image")

    expected_router_paths = {row["path"] for row in recipe["routers"]}
    if {row["path"] for row in metadata["routers"]} != expected_router_paths:
        raise BundleTrustError("bootstrap does not contain both exact router procedures")
    if {
        (row["canonical_name"], row["path"])
        for row in metadata["routers"]
    } != {
        (row["canonical_name"], row["path"])
        for row in recipe["routers"]
    }:
        raise BundleTrustError("bootstrap router names differ from the exact surface recipe")
    expected_runtime_paths = {row["path"] for row in recipe["runtime_files"]}
    if {row["path"] for row in metadata["runtime_files"]} != expected_runtime_paths:
        raise BundleTrustError("bootstrap runtime file set differs from its recipe")
    expected_paths = expected_router_paths | expected_runtime_paths | {
        recipe["bootstrap_metadata_path"]
    }
    if surface_paths != expected_paths:
        raise BundleTrustError("bootstrap tree contains undeclared or missing files")
    for record in [*metadata["routers"], *metadata["runtime_files"]]:
        content = bootstrap_bytes.get(record["path"])
        if content is None or _row(record["path"], content) != {
            key: record[key] for key in ("path", "size", "sha256")
        }:
            raise BundleTrustError("bootstrap metadata does not hash every exact file byte")


def _verify_install_image(
    bundle: VerifiedBundle,
    image_root: Path,
    *,
    recipe_id: str | None,
    recipe_ids: Sequence[str] | None,
) -> dict[str, Any]:
    """Verify manifest self-domain, catalog locator, and every generated byte."""
    root = _root_path(image_root, must_exist=True)
    manifest_path = _safe_path(root, INSTALLED_MANIFEST_PATH, must_exist=True)
    manifest_bytes = manifest_path.read_bytes()
    manifest = load_canonical_json(manifest_path)
    validate_distribution_contract("installed-manifest-v1", manifest)
    if manifest_bytes != canonical_json_bytes(manifest):
        raise BundleTrustError("installed manifest raw bytes differ from canonical JCS")
    if manifest["release_root_sha256"] != bundle.release_root_sha256 or manifest[
        "bundle_index_sha256"
    ] != bundle.bundle_index_sha256:
        raise BundleTrustError("installed manifest is not bound to the verified release")
    if (
        manifest["bundle_version"] != bundle.bundle_index["bundle_version"]
        or manifest["surface_activation_contract_sha256"]
        != bundle.release_root["surface_activation_contract"]["sha256"]
        or manifest["catalog_hash"]
        != bundle.bundle_index["catalog_inventory_sha256"]
    ):
        raise BundleTrustError("installed manifest forward hashes differ from the bundle")
    if manifest["mode"] != "router-only" or manifest["activation_records"]:
        raise BundleTrustError("new install image must preserve router-only default activation")
    owned = manifest["owned_paths"]
    if owned["activation_projections"] or owned["full_discovery_projections"]:
        raise BundleTrustError("router-only image contains ambient non-router projections")
    if owned["activation_state"] or owned["generated_links"]:
        raise BundleTrustError("new router-only image contains activation state or links")
    if len(owned["recovery_journal"]) != 1:
        raise BundleTrustError("new image must own exactly one clean recovery journal")
    recovery_row = owned["recovery_journal"][0]
    recovery_bytes = _verify_row(root, recovery_row, location="recovery_journal[0]")
    expected_recovery = canonical_json_bytes(
        {"schema_version": 1, "state": "clean", "temporary_records": []}
    )
    if recovery_bytes != expected_recovery:
        raise BundleTrustError("recovery journal bytes differ from the exact clean v1 state")
    if (
        manifest["recovery"]["journal_path"] != recovery_row["path"]
        or manifest["recovery"]["journal_sha256"] != recovery_row["sha256"]
        or manifest["recovery"]["state"] != "clean"
        or manifest["recovery"]["temporary_records"]
    ):
        raise BundleTrustError("manifest recovery state is not bound to its clean journal")

    recipes = _load_recipe_set(
        bundle, recipe_id=recipe_id, recipe_ids=recipe_ids
    )
    if manifest["surface_set"] != [recipe["surface_id"] for recipe in recipes]:
        raise BundleTrustError("installed surface set differs from its projection recipes")
    expected_catalog_prefix = f".engineering/catalog/{bundle.bundle_index_sha256}/"
    for index, row in enumerate(manifest["owned_paths"]["catalog_store"]):
        if not row["path"].startswith(expected_catalog_prefix) or row["path"].startswith(
            _DISCOVERY_PREFIXES
        ):
            raise BundleTrustError("catalog locator is not content-addressed outside discovery")
        _verify_row(root, row, location=f"catalog_store[{index}]")
    expected_catalog = {
        f"{expected_catalog_prefix}{row['path']}": (row["size"], row["sha256"])
        for row in bundle.bundle_index["blobs"]
    }
    actual_catalog = {
        row["path"]: (row["size"], row["sha256"])
        for row in manifest["owned_paths"]["catalog_store"]
    }
    if actual_catalog != expected_catalog:
        raise BundleTrustError("installed catalog rows differ from the verified bundle")

    bootstrap_bytes: dict[str, bytes] = {}
    for index, row in enumerate(manifest["owned_paths"]["bootstrap_projections"]):
        bootstrap_bytes[row["path"]] = _verify_row(
            root, row, location=f"bootstrap_projections[{index}]"
        )
    generated_by_surface: dict[str, set[str]] = {
        surface_id: set() for surface_id in manifest["surface_set"]
    }
    for row in manifest["generated_files"]:
        if row["ownership_class"] == "bootstrap":
            generated_by_surface[row["surface_id"]].add(row["path"])
    for recipe in recipes:
        _verify_surface_bootstrap(
            bundle,
            root,
            recipe,
            bootstrap_bytes,
            generated_by_surface[recipe["surface_id"]],
        )
    manifest_digest = manifest["manifest_sha256"].encode()
    if any(manifest_digest in content for content in bootstrap_bytes.values()):
        raise BundleTrustError("bootstrap contains a backward installed-manifest digest edge")

    declared_files = {INSTALLED_MANIFEST_PATH}
    for class_name, rows in owned.items():
        if class_name == "generated_links":
            continue
        for index, row in enumerate(rows):
            declared_files.add(row["path"])
            if class_name not in {"catalog_store", "bootstrap_projections", "recovery_journal"}:
                _verify_row(root, row, location=f"{class_name}[{index}]")
    actual_files: set[str] = set()
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in [*directory_names, *file_names]:
            candidate = parent / name
            if candidate.is_symlink():
                raise BundleTrustError("install image contains an undeclared symlink")
        for name in file_names:
            actual_files.add((parent / name).relative_to(root).as_posix())
    if actual_files != declared_files:
        raise BundleTrustError("install image files differ from the exact manifest-owned set")
    return manifest


def verify_install_image(
    bundle: VerifiedBundle,
    image_root: Path,
    *,
    recipe_id: str | None = None,
    recipe_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Normalize every manifest/schema failure to the public trust error type."""
    try:
        return _verify_install_image(
            bundle,
            image_root,
            recipe_id=recipe_id,
            recipe_ids=recipe_ids,
        )
    except BundleTrustError:
        raise
    except DistributionContractError as exc:
        raise BundleTrustError(str(exc)) from exc


def recipe_from_json(path: Path) -> tuple[dict[str, Any], list[BlobSource]]:
    """Load the exact closed CLI release recipe (an external, untrusted input)."""
    value = _strict_json_bytes(
        path.read_bytes(), location="release recipe", canonical=True
    )
    expected = {
        "schema_version",
        "bundle_version",
        "installer",
        "surface_activation_contract",
        "blobs",
    }
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != 1:
        raise BundleTrustError("release recipe has unknown fields or version")
    sources: list[BlobSource] = []
    for index, row in enumerate(value["blobs"]):
        if not isinstance(row, dict) or set(row) != {"kind", "id", "source", "media_type"}:
            raise BundleTrustError(f"release recipe blobs[{index}] is not closed")
        sources.append(BlobSource(row["kind"], row["id"], row["source"], row["media_type"]))
    return value, sources
