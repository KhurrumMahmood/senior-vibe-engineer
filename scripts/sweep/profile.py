"""Strict host/sweep profile contract for registry-selected scans."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from _lib.capability_registry import CapabilityRegistry, load_registry

from .serialization import canonical_sha256


PROFILE_SCHEMA_VERSION = 1
PROFILE_BYTE_LIMIT = 65_536
PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "languages",
        "paths",
        "roots",
        "exclusions",
        "case_sensitive",
    }
)


class SweepProfileError(ValueError):
    """A sweep profile cannot designate one complete registry-backed scan."""


@dataclass(frozen=True)
class SweepProfile:
    """One validated scan scope independent of machine filesystem case rules."""

    languages: tuple[str, ...]
    paths: tuple[str, ...]
    roots: tuple[str, ...]
    exclusions: tuple[str, ...]
    case_sensitive: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "languages": list(self.languages),
            "paths": list(self.paths),
            "roots": list(self.roots),
            "exclusions": list(self.exclusions),
            "case_sensitive": self.case_sensitive,
        }

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.as_document())


def _repo_path(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SweepProfileError(f"{field} values must be non-empty strings")
    if "\\" in value:
        raise SweepProfileError(f"{field} values must use POSIX separators")
    candidate = PurePosixPath(value)
    rendered = candidate.as_posix()
    if candidate.is_absolute() or rendered in {"", ".."} or ".." in candidate.parts:
        raise SweepProfileError(f"{field} contains a path outside the repository: {value}")
    if rendered.startswith("./") or rendered.endswith("/"):
        raise SweepProfileError(f"{field} paths must be canonical: {value}")
    return rendered


def _paths(
    value: Any,
    *,
    field: str,
    case_sensitive: bool,
    nonempty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SweepProfileError(f"{field} must be an array")
    rows = tuple(_repo_path(item, field=field) for item in value)
    if nonempty and not rows:
        raise SweepProfileError(f"{field} must not be empty")
    if list(rows) != sorted(set(rows)):
        raise SweepProfileError(f"{field} must be sorted and unique")
    folded = [row if case_sensitive else row.casefold() for row in rows]
    if len(folded) != len(set(folded)):
        raise SweepProfileError(f"{field} contains case-equivalent duplicates")
    return rows


def _within(path: str, boundary: str, *, case_sensitive: bool) -> bool:
    if not case_sensitive:
        path = path.casefold()
        boundary = boundary.casefold()
    return boundary == "." or path == boundary or path.startswith(f"{boundary}/")


def validate_sweep_profile(
    document: Mapping[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
) -> SweepProfile:
    """Validate a profile without inferring case policy or providers locally."""
    if not isinstance(document, Mapping) or set(document) != PROFILE_FIELDS:
        raise SweepProfileError(f"profile fields must be exactly {sorted(PROFILE_FIELDS)}")
    if document["schema_version"] != PROFILE_SCHEMA_VERSION:
        raise SweepProfileError(
            f"profile schema_version must be {PROFILE_SCHEMA_VERSION}"
        )
    case_sensitive = document["case_sensitive"]
    if type(case_sensitive) is not bool:
        raise SweepProfileError("case_sensitive must be an explicit boolean")
    registry = registry or load_registry()
    languages = document["languages"]
    if (
        not isinstance(languages, list)
        or not languages
        or any(not isinstance(language, str) or not language for language in languages)
        or languages != sorted(set(languages))
    ):
        raise SweepProfileError("languages must be a sorted unique non-empty string array")
    unknown = sorted(set(languages) - registry.identifiers("languages"))
    if unknown:
        raise SweepProfileError(f"languages contains unregistered identifiers: {unknown}")
    without_battery = [
        language for language in languages if not registry.data["sweep_targets"].get(language)
    ]
    if without_battery:
        raise SweepProfileError(
            f"languages lack a registered sweep battery: {without_battery}"
        )

    paths = _paths(
        document["paths"],
        field="paths",
        case_sensitive=case_sensitive,
        nonempty=True,
    )
    roots = _paths(
        document["roots"],
        field="roots",
        case_sensitive=case_sensitive,
        nonempty=True,
    )
    exclusions = _paths(
        document["exclusions"],
        field="exclusions",
        case_sensitive=case_sensitive,
        nonempty=False,
    )
    outside_roots = [
        path
        for path in paths
        if not any(_within(path, root, case_sensitive=case_sensitive) for root in roots)
    ]
    if outside_roots:
        raise SweepProfileError(f"paths are outside roots: {outside_roots}")
    outside_exclusions = [
        exclusion
        for exclusion in exclusions
        if not any(
            _within(exclusion, root, case_sensitive=case_sensitive) for root in roots
        )
    ]
    if outside_exclusions:
        raise SweepProfileError(f"exclusions are outside roots: {outside_exclusions}")
    fully_excluded = [
        path
        for path in paths
        if any(_within(path, exclusion, case_sensitive=case_sensitive) for exclusion in exclusions)
    ]
    if fully_excluded:
        raise SweepProfileError(f"scope paths are fully excluded: {fully_excluded}")
    return SweepProfile(
        languages=tuple(languages),
        paths=paths,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )


def load_sweep_profile(
    path: Path | str,
    *,
    registry: CapabilityRegistry | None = None,
) -> SweepProfile:
    """Read one bounded JSON profile and apply the strict profile contract."""
    source = Path(path)
    try:
        content = source.read_bytes()
    except OSError as exc:
        raise SweepProfileError(f"cannot read sweep profile {source}: {exc}") from exc
    if len(content) > PROFILE_BYTE_LIMIT:
        raise SweepProfileError(
            f"sweep profile exceeds {PROFILE_BYTE_LIMIT}-byte limit"
        )
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SweepProfileError(f"sweep profile is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(document, Mapping):
        raise SweepProfileError("sweep profile must be a JSON object")
    return validate_sweep_profile(document, registry=registry)
