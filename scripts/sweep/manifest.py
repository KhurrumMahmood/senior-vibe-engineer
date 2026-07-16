"""Canonical manifest construction, identity migration, and set comparison."""
from __future__ import annotations

import copy
import json
import os
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from _lib.finding_identity import FindingIdentity, normalize_repo_path

from .schemas import (
    SCHEMA_VERSION,
    SchemaValidationError,
    validate_diff,
    validate_manifest,
    validate_provider_observation,
)
from .serialization import canonical_json_bytes, canonical_sha256


class ManifestIdentityError(ValueError):
    """Raised when identities or migration aliases are not one-to-one."""


@dataclass(frozen=True)
class FindingInput:
    """A normalized provider finding before identity occurrence assignment."""

    provider: str
    language: str
    native_rule_id: str
    rule_semantic_key: str
    path: str | Path
    semantic_anchor: str
    native_severity: str
    severity: int
    message: str
    summary: str
    metrics: Mapping[str, int | float]
    observation_index: int
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    legacy_ids: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class PrototypeMigration:
    """Explicit context required to interpret an unversioned prototype manifest."""

    capability_registry_version: int
    case_sensitive: bool
    roots: Sequence[str]
    exclusions: Sequence[str]
    source: Mapping[str, Any]
    providers: Sequence[Mapping[str, Any]]
    language_by_provider: Mapping[str, str]
    semantic_rule_versions: Mapping[str, int]
    repo_root: Path | str | None = None


def _finding_identifier(identity: FindingIdentity) -> str:
    """Return ADR 0040's public identity; isolated for collision fault injection."""
    return identity.identifier()


def _normalize_scope_path(value: str | Path, *, case_sensitive: bool) -> str:
    text = Path(value).as_posix()
    if "\\" in str(value):
        raise ValueError("scope paths must use POSIX separators")
    candidate = PurePosixPath(text)
    normalized = candidate.as_posix()
    if candidate.is_absolute() or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("scope path must remain inside the repository")
    return normalized if case_sensitive else normalized.casefold()


def _source_position(value: int | None) -> tuple[int, int]:
    return (1, 0) if value is None else (0, value)


def _canonical_candidate(candidate: FindingInput, *, case_sensitive: bool, repo_root: Path | str | None):
    identity = FindingIdentity(
        provider=candidate.provider,
        rule=candidate.rule_semantic_key,
        language=candidate.language,
        path=normalize_repo_path(
            candidate.path,
            repo_root=repo_root,
            case_sensitive=case_sensitive,
        ),
        semantic_anchor=candidate.semantic_anchor,
        occurrence=0,
        case_sensitive=case_sensitive,
    )
    payload = identity.canonical_payload()
    group = tuple(payload[name] for name in ("provider", "rule", "language", "path", "semantic_anchor"))
    source_order = (
        _source_position(candidate.line),
        _source_position(candidate.column),
        _source_position(candidate.end_line),
        _source_position(candidate.end_column),
        canonical_sha256(
            {
                "native_rule_id": candidate.native_rule_id,
                "native_severity": candidate.native_severity,
                "severity": candidate.severity,
                "message": candidate.message,
                "summary": candidate.summary,
                "metrics": dict(candidate.metrics),
                "observation_index": candidate.observation_index,
                "legacy_ids": sorted(candidate.legacy_ids),
            }
        ),
    )
    return group, source_order, payload


def _finding_rows(
    findings: Sequence[FindingInput],
    *,
    case_sensitive: bool,
    repo_root: Path | str | None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[tuple[tuple[Any, ...], FindingInput, Mapping[str, Any]]]] = (
        defaultdict(list)
    )
    for candidate in findings:
        group, source_order, payload = _canonical_candidate(
            candidate,
            case_sensitive=case_sensitive,
            repo_root=repo_root,
        )
        grouped[group].append((source_order, candidate, payload))

    rows: list[dict[str, Any]] = []
    payload_by_identifier: dict[str, Mapping[str, Any]] = {}
    alias_owner: dict[str, str] = {}
    for group in sorted(grouped):
        for occurrence, (_, candidate, base_payload) in enumerate(sorted(grouped[group], key=lambda item: item[0])):
            identity = FindingIdentity(
                provider=str(base_payload["provider"]),
                rule=str(base_payload["rule"]),
                language=str(base_payload["language"]),
                path=str(base_payload["path"]),
                semantic_anchor=str(base_payload["semantic_anchor"]),
                occurrence=occurrence,
                case_sensitive=case_sensitive,
            )
            payload = identity.canonical_payload()
            identifier = _finding_identifier(identity)
            previous_payload = payload_by_identifier.get(identifier)
            if previous_payload is not None and dict(previous_payload) != payload:
                raise ManifestIdentityError(
                    f"finding digest collision for {identifier}: unequal ADR 0040 payloads"
                )
            payload_by_identifier[identifier] = payload

            aliases = list(candidate.legacy_ids)
            if len(aliases) != len(set(aliases)):
                raise ManifestIdentityError(f"duplicate legacy alias on {identifier}")
            for alias in aliases:
                owner = alias_owner.get(alias)
                if owner is not None and owner != identifier:
                    raise ManifestIdentityError(
                        f"ambiguous legacy alias {alias}: claimed by {owner} and {identifier}"
                    )
                alias_owner[alias] = identifier

            rows.append(
                {
                    "finding_id_schema": 2,
                    "id": identifier,
                    "identity": payload,
                    "legacy_ids": sorted(aliases),
                    "native_rule_id": candidate.native_rule_id,
                    "rule_semantic_key": candidate.rule_semantic_key.strip(),
                    "native_severity": candidate.native_severity,
                    "severity": candidate.severity,
                    "location": {
                        "path": payload["path"],
                        "line": candidate.line,
                        "column": candidate.column,
                        "end_line": candidate.end_line,
                        "end_column": candidate.end_column,
                    },
                    "message": candidate.message,
                    "summary": candidate.summary,
                    "metrics": dict(candidate.metrics),
                    "provenance": {
                        "provider": payload["provider"],
                        "observation_index": candidate.observation_index,
                    },
                }
            )

    current_ids = set(payload_by_identifier)
    for alias, owner in alias_owner.items():
        if alias == owner:
            raise ManifestIdentityError(f"cyclic legacy alias {alias} points to itself")
        if alias in current_ids:
            raise ManifestIdentityError(
                f"cross-payload legacy alias {alias} references a current finding id"
            )
    return sorted(
        rows,
        key=lambda row: (
            row["identity"]["provider"],
            row["identity"]["language"],
            row["rule_semantic_key"],
            row["identity"]["path"],
            row["identity"]["semantic_anchor"],
            row["identity"]["occurrence"],
            row["id"],
        ),
    )


def _manifest_hashes(document: Mapping[str, Any]) -> dict[str, str]:
    semantic = {
        name: copy.deepcopy(document[name])
        for name in (
            "schema_version",
            "finding_id_schema",
            "capability_registry_version",
            "scope",
            "source",
            "status",
            "findings",
            "counts",
            "total",
        )
    }
    semantic["providers"] = [
        {
            "provider": row["provider"],
            "language": row["language"],
            "provider_kind": row["provider_kind"],
            "status": row["status"],
        }
        for row in document["providers"]
    ]
    artifacts = {
        "schema_version": document["schema_version"],
        "providers": copy.deepcopy(document["providers"]),
    }
    return {
        "semantic": canonical_sha256(semantic),
        "artifacts": canonical_sha256(artifacts),
    }


def _validated_manifest(document: Mapping[str, Any]) -> Mapping[str, Any]:
    validated = validate_manifest(document)
    if dict(validated["hashes"]) != _manifest_hashes(validated):
        raise SchemaValidationError(
            "manifest.hashes",
            "must bind the canonical manifest content",
        )
    return validated


# spec:portable-batch-sweep::IM-3
def build_manifest(
    *,
    capability_registry_version: int,
    paths: Sequence[str | Path],
    case_sensitive: bool,
    roots: Sequence[str | Path],
    exclusions: Sequence[str | Path],
    source: Mapping[str, Any],
    providers: Sequence[Mapping[str, Any]],
    findings: Sequence[FindingInput],
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """Build the only writable sweep-manifest schema from normalized inputs."""
    if not isinstance(case_sensitive, bool):
        raise TypeError("case_sensitive must be an explicit boolean")
    validated_providers = [copy.deepcopy(dict(validate_provider_observation(row))) for row in providers]
    validated_providers.sort(key=lambda row: (row["provider"], row["language"]))
    rows = _finding_rows(
        findings,
        case_sensitive=case_sensitive,
        repo_root=repo_root,
    )
    provider_keys = {(row["provider"], row["language"]) for row in validated_providers}
    for row in rows:
        key = (row["identity"]["provider"], row["identity"]["language"])
        if key not in provider_keys:
            raise SchemaValidationError(
                "manifest.findings",
                f"finding provider/language {key!r} has no completed observation",
            )

    scope = {
        "paths": sorted({_normalize_scope_path(value, case_sensitive=case_sensitive) for value in paths}),
        "case_sensitive": case_sensitive,
        "roots": sorted({_normalize_scope_path(value, case_sensitive=case_sensitive) for value in roots}),
        "exclusions": sorted(
            {_normalize_scope_path(value, case_sensitive=case_sensitive) for value in exclusions}
        ),
    }
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "finding_id_schema": 2,
        "capability_registry_version": capability_registry_version,
        "scope": scope,
        "source": copy.deepcopy(dict(source)),
        "status": "complete",
        "providers": validated_providers,
        "findings": rows,
        "counts": dict(sorted(Counter(row["identity"]["provider"] for row in rows).items())),
        "total": len(rows),
        "hashes": {},
    }
    document["hashes"] = _manifest_hashes(document)
    validate_manifest(document)
    return document


def write_manifest(destination: Path | str, document: Mapping[str, Any]) -> dict[str, Any]:
    """Atomically write a validated current-schema manifest as canonical JSON."""
    validated = copy.deepcopy(dict(validate_manifest(document)))
    validated["hashes"] = _manifest_hashes(validated)
    validate_manifest(validated)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(canonical_json_bytes(validated))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return validated


def _prototype_finding(
    row: Mapping[str, Any],
    *,
    migration: PrototypeMigration,
    provider_indexes: Mapping[str, int],
) -> FindingInput:
    if not isinstance(row, Mapping):
        raise SchemaValidationError("manifest.findings", "prototype finding must be an object")
    required = {"id", "rule", "path", "symbol", "severity", "summary", "line"}
    missing = sorted(required - set(row))
    unknown = sorted(set(row) - required - {"count"})
    if missing or unknown:
        detail = f"missing {missing}" if missing else f"unknown {unknown}"
        raise SchemaValidationError("manifest.findings", f"invalid prototype finding fields: {detail}")
    rule = row["rule"]
    if not isinstance(rule, str) or ":" not in rule:
        raise SchemaValidationError("manifest.findings.rule", "must be provider:native-rule")
    provider, native_rule = rule.split(":", 1)
    language = migration.language_by_provider.get(provider)
    if language is None or provider not in provider_indexes:
        raise SchemaValidationError(
            "manifest.findings.provider",
            f"prototype provider {provider!r} requires explicit language and observation",
        )
    version = migration.semantic_rule_versions.get(rule)
    if type(version) is not int or version < 1:
        raise SchemaValidationError(
            "manifest.findings.rule",
            f"prototype rule {rule!r} requires a positive semantic version",
        )
    symbol = row["symbol"]
    if not isinstance(symbol, str):
        raise SchemaValidationError("manifest.findings.symbol", "must be a string")
    anchor = f"symbol:{' '.join(symbol.split())}" if symbol.strip() else f"anonymous:{native_rule}"
    metrics = {"count": row["count"]} if "count" in row else {}
    return FindingInput(
        provider=provider,
        language=language,
        native_rule_id=native_rule,
        rule_semantic_key=f"{rule}:v{version}",
        path=row["path"],
        semantic_anchor=anchor,
        native_severity=f"prototype:{row['severity']}",
        severity=row["severity"],
        line=row["line"],
        column=None,
        end_line=None,
        end_column=None,
        message=row["summary"],
        summary=row["summary"],
        metrics=metrics,
        observation_index=provider_indexes[provider],
        legacy_ids=(row["id"],),
    )


# spec:portable-batch-sweep::IM-4
def migrate_prototype_manifest(
    document: Mapping[str, Any],
    migration: PrototypeMigration,
) -> dict[str, Any]:
    """Interpret the one supported legacy shape and return current schema only."""
    prototype = validate_manifest(document, allow_prototype=True)
    if prototype["errors"]:
        raise SchemaValidationError(
            "manifest.errors",
            "a failed prototype run cannot migrate to a complete manifest",
        )
    providers = [copy.deepcopy(dict(validate_provider_observation(row))) for row in migration.providers]
    providers.sort(key=lambda row: (row["provider"], row["language"]))
    provider_indexes = {row["provider"]: index for index, row in enumerate(providers)}
    if len(provider_indexes) != len(providers):
        raise SchemaValidationError("manifest.providers", "prototype migration providers must be unique")
    findings = [
        _prototype_finding(row, migration=migration, provider_indexes=provider_indexes)
        for row in prototype["findings"]
    ]
    return build_manifest(
        capability_registry_version=migration.capability_registry_version,
        paths=prototype["scope"],
        case_sensitive=migration.case_sensitive,
        roots=migration.roots,
        exclusions=migration.exclusions,
        source=migration.source,
        providers=providers,
        findings=findings,
        repo_root=migration.repo_root,
    )


def read_manifest(
    source: Path | str,
    *,
    prototype_migration: PrototypeMigration | None = None,
) -> dict[str, Any]:
    """Read schema 1, or explicitly migrate the sole unversioned legacy shape."""
    try:
        document = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError("manifest", f"cannot read JSON: {exc}") from exc
    if isinstance(document, Mapping) and "schema_version" not in document:
        if prototype_migration is None:
            raise SchemaValidationError(
                "manifest.schema_version",
                "missing; prototype manifests require explicit migration mode",
            )
        return migrate_prototype_manifest(document, prototype_migration)
    return copy.deepcopy(dict(_validated_manifest(document)))


def _continuity_payload(row: Mapping[str, Any]) -> tuple[Any, ...]:
    identity = row["identity"]
    return tuple(
        identity[name]
        for name in ("schema", "provider", "rule", "language", "semantic_anchor", "occurrence")
    )


def _reject_alias_cycles(
    before_by_id: Mapping[str, Mapping[str, Any]],
    after_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    current_ids = set(before_by_id) | set(after_by_id)
    graph: dict[str, set[str]] = defaultdict(set)
    for rows in (before_by_id.values(), after_by_id.values()):
        for row in rows:
            graph[row["id"]].update(alias for alias in row["legacy_ids"] if alias in current_ids)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            raise ManifestIdentityError(f"cyclic legacy alias chain includes {identifier}")
        if identifier in visited:
            return
        visiting.add(identifier)
        for target in graph[identifier]:
            visit(target)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in sorted(graph):
        visit(identifier)


def build_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Classify fixed/new/persisting findings, honoring valid one-release aliases."""
    before = _validated_manifest(before)
    after = _validated_manifest(after)
    if before["scope"]["case_sensitive"] != after["scope"]["case_sensitive"]:
        raise ManifestIdentityError("manifests with different case policies cannot be compared")

    before_by_id = {row["id"]: row for row in before["findings"]}
    after_by_id = {row["id"]: row for row in after["findings"]}
    _reject_alias_cycles(before_by_id, after_by_id)
    matched_before: dict[str, str] = {}
    matched_after: dict[str, str] = {}

    for identifier in sorted(set(before_by_id) & set(after_by_id)):
        matched_before[identifier] = identifier
        matched_after[identifier] = identifier

    for new_id, new_row in after_by_id.items():
        candidates = [alias for alias in new_row["legacy_ids"] if alias in before_by_id]
        if not candidates:
            continue
        if len(candidates) != 1 or new_id in matched_after:
            raise ManifestIdentityError(f"legacy alias for {new_id} is not one-to-one")
        old_id = candidates[0]
        if old_id in matched_before:
            raise ManifestIdentityError(f"ambiguous legacy alias for {old_id}")
        old_row = before_by_id[old_id]
        if new_id in old_row["legacy_ids"]:
            raise ManifestIdentityError(f"cyclic legacy aliases between {old_id} and {new_id}")
        if _continuity_payload(old_row) != _continuity_payload(new_row):
            raise ManifestIdentityError(
                f"cross-payload legacy alias {old_id} cannot identify {new_id}"
            )
        matched_before[old_id] = new_id
        matched_after[new_id] = old_id

    persisting = sorted(matched_after)
    fixed = sorted(set(before_by_id) - set(matched_before))
    new = sorted(set(after_by_id) - set(matched_after))
    metric_changes: list[dict[str, Any]] = []
    for new_id in persisting:
        old_id = matched_after[new_id]
        before_metrics = before_by_id[old_id]["metrics"]
        after_metrics = after_by_id[new_id]["metrics"]
        for metric in sorted(set(before_metrics) & set(after_metrics)):
            if before_metrics[metric] != after_metrics[metric]:
                metric_changes.append(
                    {
                        "finding_id": new_id,
                        "metric": metric,
                        "before": before_metrics[metric],
                        "after": after_metrics[metric],
                    }
                )
    document = {
        "schema_version": SCHEMA_VERSION,
        "before_manifest_hash": before["hashes"]["semantic"],
        "after_manifest_hash": after["hashes"]["semantic"],
        "fixed": fixed,
        "new": new,
        "persisting": persisting,
        "metric_changes": metric_changes,
        "accepts": [],
    }
    validate_diff(document)
    return document
