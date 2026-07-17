"""Closed semantic contract for exact known legacy distribution layouts."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import re
from typing import Any
import unicodedata


_SAFE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ROW_FIELDS = frozenset(
    {
        "layout_id",
        "manifest_id",
        "version_range",
        "release_root_sha256",
        "tree_sha256",
        "files",
        "action",
    }
)
_FILE_FIELDS = frozenset({"path", "size", "sha256", "role"})


def _closed(
    value: object,
    fields: set[str] | frozenset[str],
    location: str,
    error_type: type[Exception],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        raise error_type(f"{location} must contain exactly {sorted(fields)}")
    return value


def _safe_path(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and value == unicodedata.normalize("NFC", value)
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and len(value.encode("utf-8")) <= 1024
    )


def validate_legacy_layouts_table(
    value: object,
    *,
    error_type: type[Exception],
    canonical_sha256: Callable[[Any], str],
) -> None:
    """Validate exact rows; an honestly empty production authority is valid."""
    table = _closed(
        value, {"layouts", "schema_version"}, "legacy-layouts-v1", error_type
    )
    if table["schema_version"] != 1:
        raise error_type("legacy-layouts-v1.schema_version must equal 1")
    layouts = table["layouts"]
    if not isinstance(layouts, list):
        raise error_type("legacy-layouts-v1.layouts must be an array")
    seen_ids: set[str] = set()
    for index, candidate in enumerate(layouts):
        location = f"legacy-layouts-v1.layouts[{index}]"
        row = _closed(candidate, _ROW_FIELDS, location, error_type)
        for field in ("layout_id", "manifest_id"):
            item = row[field]
            if not isinstance(item, str) or _SAFE_ID.fullmatch(item) is None:
                raise error_type(f"{location}.{field} is not a safe ID")
        if row["layout_id"] in seen_ids:
            raise error_type(f"duplicate legacy layout_id: {row['layout_id']!r}")
        seen_ids.add(row["layout_id"])
        version = _closed(
            row["version_range"], {"lower", "upper"}, f"{location}.version_range", error_type
        )
        if any(not isinstance(version[key], str) or not version[key] for key in ("lower", "upper")):
            raise error_type(f"{location}.version_range must have nonempty closed bounds")
        for field in ("release_root_sha256", "tree_sha256"):
            digest = row[field]
            if not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
                raise error_type(f"{location}.{field} is not SHA-256")
        if row["action"] not in {"adopt", "retire"}:
            raise error_type(f"{location}.action is unsupported")
        files = row["files"]
        if not isinstance(files, list) or not files:
            raise error_type(f"{location}.files must be a nonempty array")
        identities: list[dict[str, Any]] = []
        paths: set[str] = set()
        marker_count = 0
        for file_index, candidate_file in enumerate(files):
            file_location = f"{location}.files[{file_index}]"
            file_row = _closed(candidate_file, _FILE_FIELDS, file_location, error_type)
            path = file_row["path"]
            if not _safe_path(path):
                raise error_type(f"{file_location}.path is not a safe NFC relative POSIX path")
            if path in paths:
                raise error_type(f"duplicate legacy file path: {path}")
            paths.add(path)
            size, digest = file_row["size"], file_row["sha256"]
            if type(size) is not int or size < 0 or not isinstance(digest, str) or _HASH.fullmatch(digest) is None:
                raise error_type(f"{file_location} has invalid byte identity")
            if file_row["role"] not in {"content", "ownership-marker"}:
                raise error_type(f"{file_location}.role is unsupported")
            marker_count += file_row["role"] == "ownership-marker"
            identities.append({"path": path, "size": size, "sha256": digest})
        if marker_count == 0:
            raise error_type(f"{location}.files requires an ownership-marker")
        if [row["path"] for row in identities] != sorted(
            (row["path"] for row in identities), key=lambda item: item.encode("utf-8")
        ):
            raise error_type(f"{location}.files must be UTF-8 path sorted")
        if row["tree_sha256"] != canonical_sha256(identities):
            raise error_type(f"{location}.tree_sha256 differs")
    if [row["layout_id"] for row in layouts] != sorted(
        (row["layout_id"] for row in layouts), key=lambda item: item.encode("utf-8")
    ):
        raise error_type("legacy-layouts-v1.layouts must be UTF-8 layout_id sorted")
