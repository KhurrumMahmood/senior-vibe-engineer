"""Strict readers for the release-root distribution reference tables.

The tables are trust inputs rather than authoring conveniences.  Read their
raw bytes canonically and validate their closed semantic contracts before a
release builder, installer, or lifecycle command consumes them.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .host_profile import HOST_PROFILE_SCHEMA_VERSION


SURFACE_IDS = frozenset({"augment", "claude-code", "codex", "cursor", "gemini"})
ALIAS_ROW_FIELDS = frozenset(
    {
        "public_name",
        "canonical_target",
        "surface_spellings",
        "introduced_release",
        "retirement_release",
    }
)
TABLE_NAMES = ("aliases-v1", "compatibility-v1", "legacy-layouts-v1")
_PUBLIC_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INTEGER_COMPATIBILITY = {
    "alias_schema": 1,
    "bundle_index_schema": 1,
    "capability_registry_contract": 1,
    "capability_registry_schema": 1,
    "catalog_inventory_schema": 1,
    "dispatch_pack_schema": 1,
    "dispatch_result_schema": 1,
    "dispatcher_policy_schema": 1,
    "host_profile_schema": HOST_PROFILE_SCHEMA_VERSION,
    "installed_manifest_schema": 1,
    "legacy_layout_schema": 1,
    "release_root_schema": 1,
}
_SURFACE_COMPATIBILITY = {
    "augment": "imported-rules-v1",
    "claude-code": "2.1.211",
    "codex": "0.144.1",
    "cursor": "project-rules-v1",
    "gemini": "0.45.0",
}


class DistributionContractError(ValueError):
    """A distribution reference table is not safe to consume."""


def canonical_json_bytes(value: Any) -> bytes:
    """Encode the integer-only RFC-8785 subset used by distribution tables."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as exc:
        raise DistributionContractError("document is not canonical JSON data") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DistributionContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_integer_number(value: str) -> None:
    raise DistributionContractError(f"non-integer JSON number: {value}")


def load_canonical_json(path: Path | str) -> Any:
    """Load strict UTF-8 JSON and require its raw bytes to be canonical."""
    source = Path(path)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_non_integer_number,
            parse_float=_reject_non_integer_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DistributionContractError(f"{source}: invalid strict UTF-8 JSON") from exc
    if raw != canonical_json_bytes(value):
        raise DistributionContractError(f"{source}: raw bytes are not RFC-8785 canonical")
    return value


def _require_exact_keys(
    value: object, expected: frozenset[str] | set[str], location: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DistributionContractError(f"{location} must be an object")
    if set(value) != expected:
        raise DistributionContractError(
            f"{location} must contain exactly {sorted(expected)}"
        )
    return value


def _require_schema_one(value: object, location: str) -> None:
    if type(value) is not int or value != 1:
        raise DistributionContractError(f"{location}.schema_version must equal integer 1")


def validate_alias_table(
    value: object, canonical_names: Sequence[str] | set[str] | frozenset[str]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validate aliases-v1 and resolve every alias to a canonical procedure."""
    table = _require_exact_keys(value, {"aliases", "schema_version"}, "aliases-v1")
    _require_schema_one(table["schema_version"], "aliases-v1")
    aliases = table["aliases"]
    if not isinstance(aliases, list):
        raise DistributionContractError("aliases-v1.aliases must be an array")

    canonical = set(canonical_names)
    if any(not isinstance(name, str) or _PUBLIC_NAME.fullmatch(name) is None for name in canonical):
        raise DistributionContractError("canonical procedure names must use public-name grammar")

    rows: list[dict[str, Any]] = []
    direct: dict[str, str] = {}
    for index, candidate in enumerate(aliases):
        location = f"aliases-v1.aliases[{index}]"
        row = _require_exact_keys(candidate, ALIAS_ROW_FIELDS, location)
        public_name = row["public_name"]
        target = row["canonical_target"]
        if not isinstance(public_name, str) or _PUBLIC_NAME.fullmatch(public_name) is None:
            raise DistributionContractError(f"{location}.public_name is not a safe public name")
        if not isinstance(target, str) or _PUBLIC_NAME.fullmatch(target) is None:
            raise DistributionContractError(
                f"{location}.canonical_target is not a safe public name"
            )
        if public_name in canonical or public_name in direct:
            raise DistributionContractError(f"alias collision: {public_name!r}")

        spellings = _require_exact_keys(
            row["surface_spellings"], SURFACE_IDS, f"{location}.surface_spellings"
        )
        if any(spelling != public_name for spelling in spellings.values()):
            raise DistributionContractError(
                f"{location}.surface_spellings must all equal public_name"
            )
        introduced = row["introduced_release"]
        if type(introduced) is not int or introduced < 1:
            raise DistributionContractError(
                f"{location}.introduced_release must be a positive integer"
            )
        retirement = row["retirement_release"]
        if retirement is not None and (
            type(retirement) is not int or retirement < introduced
        ):
            raise DistributionContractError(
                f"{location}.retirement_release must be null or at least introduced_release"
            )
        direct[public_name] = target
        rows.append(dict(row))

    public_names = [row["public_name"] for row in rows]
    if public_names != sorted(public_names):
        raise DistributionContractError("aliases-v1.aliases must be sorted by public_name")

    known_targets = canonical | set(direct)
    resolved: dict[str, str] = {}
    for public_name, target in direct.items():
        if target not in known_targets:
            raise DistributionContractError(
                f"alias {public_name!r} has stale target {target!r}"
            )
        seen = {public_name}
        while target in direct:
            if target in seen:
                raise DistributionContractError(f"alias cycle includes {public_name!r}")
            seen.add(target)
            target = direct[target]
        resolved[public_name] = target
    return rows, resolved


def validate_legacy_layouts_table(value: object) -> None:
    """Validate the explicit initial empty legacy-layout authority."""
    table = _require_exact_keys(value, {"layouts", "schema_version"}, "legacy-layouts-v1")
    _require_schema_one(table["schema_version"], "legacy-layouts-v1")
    if table["layouts"] != []:
        raise DistributionContractError(
            "legacy-layouts-v1.layouts must remain empty until a closed row contract exists"
        )


def validate_compatibility_table(value: object) -> None:
    """Validate every exact compatibility-v1 bound and router identifier."""
    expected_keys = {
        "router_ids",
        "schema_version",
        "surfaces",
        *_INTEGER_COMPATIBILITY,
    }
    table = _require_exact_keys(value, expected_keys, "compatibility-v1")
    _require_schema_one(table["schema_version"], "compatibility-v1")
    for field, expected in _INTEGER_COMPATIBILITY.items():
        bound = _require_exact_keys(
            table[field], {"lower", "upper"}, f"compatibility-v1.{field}"
        )
        if any(
            type(bound[key]) is not int or bound[key] != expected
            for key in ("lower", "upper")
        ):
            raise DistributionContractError(
                f"compatibility-v1.{field} must pin {expected} exactly"
            )
    if table["router_ids"] != {
        "which_shape": "which-shape-lexical-v1",
        "which_skill": "which-skill-overlap-v1",
    }:
        raise DistributionContractError("compatibility-v1.router_ids differ from v1")
    expected_surfaces = {
        surface: {"lower": version, "upper": version}
        for surface, version in _SURFACE_COMPATIBILITY.items()
    }
    if table["surfaces"] != expected_surfaces:
        raise DistributionContractError("compatibility-v1.surfaces differ from v1")


def load_distribution_tables(
    contract_root: Path | str,
    *,
    canonical_names: Sequence[str] | set[str] | frozenset[str],
) -> dict[str, Any]:
    """Load and validate all three release-root reference tables."""
    root = Path(contract_root)
    tables = {
        name: load_canonical_json(root / f"{name}.json") for name in TABLE_NAMES
    }
    validate_alias_table(tables["aliases-v1"], canonical_names)
    validate_compatibility_table(tables["compatibility-v1"])
    validate_legacy_layouts_table(tables["legacy-layouts-v1"])
    return tables
