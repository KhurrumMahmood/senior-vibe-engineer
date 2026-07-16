"""Deterministic public command services for the productized sweep."""
from __future__ import annotations

import copy
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from _lib.capability_registry import load_registry

from .manifest import FindingInput, build_diff, build_manifest
from .native import execute_provider, provider_contracts_from_registry
from .schemas import validate_diff, validate_manifest


EXIT_OK = 0
EXIT_CHANGED = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_PROVIDER = 4
EXIT_OUTPUT = 5

DIGEST_FINDING_LIMIT = 50
DIGEST_BYTE_LIMIT = 65_536


@dataclass(frozen=True)
class RatchetResult:
    """One deterministic ratchet decision before any baseline write."""

    diff: Mapping[str, Any]
    violations: tuple[str, ...]
    tighten: bool


def atomic_write_bytes(destination: Path | str, content: bytes) -> None:
    """Publish one byte artifact without exposing a partial file."""
    path = Path(destination).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _normalized_source(source: Mapping[str, Any]) -> dict[str, Any]:
    required = {"revision", "dirty", "dirty_state_hash"}
    if set(source) != required:
        raise ValueError(f"source must contain exactly {sorted(required)}")
    revision = source["revision"]
    dirty = source["dirty"]
    dirty_hash = source["dirty_state_hash"]
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("source revision must be non-empty")
    if type(dirty) is not bool:
        raise ValueError("source dirty must be an explicit boolean")
    if (
        not isinstance(dirty_hash, str)
        or len(dirty_hash) != 64
        or any(character not in "0123456789abcdef" for character in dirty_hash)
    ):
        raise ValueError("source dirty_state_hash must be a lowercase SHA-256 digest")
    return {"revision": revision, "dirty": dirty, "dirty_state_hash": dirty_hash}


# spec:portable-batch-sweep::IM-7
def scan_native(
    *,
    root: Path | str,
    languages: Sequence[str],
    scopes: Sequence[str],
    case_sensitive: bool,
    source: Mapping[str, Any],
    executables: Mapping[str, Path | str],
) -> dict[str, Any]:
    """Run the registry-selected native battery with explicit tool identities."""
    host_root = Path(root).absolute()
    if not host_root.is_dir():
        raise ValueError(f"scan root is not a directory: {host_root}")
    if not languages:
        raise ValueError("at least one language is required")
    if not scopes:
        raise ValueError("at least one scope is required")
    if type(case_sensitive) is not bool:
        raise ValueError("case_sensitive must be explicit")

    registry = load_registry()
    contracts = []
    for language in sorted(set(languages)):
        contracts.extend(provider_contracts_from_registry(language, registry=registry))
    expected = {contract.provider for contract in contracts}
    supplied = set(executables)
    if supplied != expected:
        missing = sorted(expected - supplied)
        unknown = sorted(supplied - expected)
        raise ValueError(f"explicit tool map mismatch: missing={missing}, unknown={unknown}")

    observations: list[Mapping[str, Any]] = []
    findings: list[FindingInput] = []
    for index, contract in enumerate(
        sorted(contracts, key=lambda item: (item.provider, item.language))
    ):
        executable = Path(executables[contract.provider]).absolute()
        pinned = replace(contract, executable_candidates=(str(executable),))
        result = execute_provider(pinned, root=host_root, observation_index=index)
        observations.append(result.observation)
        findings.extend(result.findings)

    return build_manifest(
        capability_registry_version=registry.schema_version,
        paths=tuple(scopes),
        case_sensitive=case_sensitive,
        roots=tuple(scopes),
        exclusions=(),
        source=_normalized_source(source),
        providers=observations,
        findings=findings,
        repo_root=host_root,
    )


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def render_digest(
    manifest: Mapping[str, Any],
    *,
    finding_limit: int = DIGEST_FINDING_LIMIT,
    byte_limit: int = DIGEST_BYTE_LIMIT,
) -> bytes:
    """Render a bounded ID-addressable view; never copy the full finding set."""
    document = validate_manifest(manifest)
    if not 1 <= finding_limit <= DIGEST_FINDING_LIMIT:
        raise ValueError(f"finding_limit must be between 1 and {DIGEST_FINDING_LIMIT}")
    if not 1 <= byte_limit <= DIGEST_BYTE_LIMIT:
        raise ValueError(f"byte_limit must be between 1 and {DIGEST_BYTE_LIMIT}")
    ordered = sorted(
        document["findings"],
        key=lambda row: (
            -row["severity"],
            row["identity"]["provider"],
            row["rule_semantic_key"],
            row["identity"]["path"],
            row["identity"]["semantic_anchor"],
            row["id"],
        ),
    )
    selected = ordered[:finding_limit]

    def encode(rows: Sequence[Mapping[str, Any]]) -> bytes:
        lines = [
            f"# sweep digest ({document['total']} findings)",
            "",
            f"Manifest: `{document['hashes']['semantic']}`",
            "Counts: "
            + ", ".join(f"{name}={count}" for name, count in document["counts"].items()),
            "",
        ]
        for row in rows:
            location = row["location"]
            position = f":{location['line']}" if location["line"] is not None else ""
            lines.append(
                f"- `{row['id']}` s{row['severity']} "
                f"{_clip(row['rule_semantic_key'], 96)} "
                f"{_clip(location['path'], 240)}{position} — {_clip(row['summary'], 320)}"
            )
        omitted = len(ordered) - len(rows)
        lines.extend(
            [
                "",
                f"{omitted} more findings omitted; full findings stay in the manifest.",
            ]
        )
        return ("\n".join(lines) + "\n").encode("utf-8")

    content = encode(selected)
    # Fixed per-field clipping keeps the normal 50-row artifact well below 64 KiB.
    # A smaller caller-provided byte bound reduces rows, never truncates UTF-8/IDs.
    while selected and len(content) > byte_limit:
        selected.pop()
        content = encode(selected)
    if len(content) > byte_limit:
        raise ValueError("byte_limit cannot hold the digest header")
    return content


def _validated_accepts(
    accepts: Sequence[Mapping[str, Any]],
    *,
    allowed_ids: set[str],
    revision: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    required = {"finding_id", "reason", "operator", "revision", "timestamp"}
    for index, raw in enumerate(accepts):
        if set(raw) != required or any(not isinstance(raw[name], str) or not raw[name].strip() for name in required):
            raise ValueError(f"accept[{index}] must contain exactly five non-empty string fields")
        identifier = raw["finding_id"]
        if identifier in seen:
            raise ValueError(f"duplicate accept for {identifier}")
        if identifier not in allowed_ids:
            raise ValueError(f"accept {identifier} does not waive a current regression")
        if raw["revision"] != revision:
            raise ValueError(f"accept {identifier} revision does not match current manifest")
        try:
            timestamp = datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"accept {identifier} timestamp is not ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise ValueError(f"accept {identifier} timestamp must include a timezone")
        rows.append({name: raw[name] for name in ("finding_id", "reason", "operator", "revision", "timestamp")})
        seen.add(identifier)
    return sorted(rows, key=lambda row: row["finding_id"])


def apply_ratchet(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    accepts: Sequence[Mapping[str, Any]],
) -> RatchetResult:
    """Classify regressions and tightening without mutating either manifest."""
    baseline = validate_manifest(baseline)
    current = validate_manifest(current)
    diff = build_diff(baseline, current)
    grown = {
        row["finding_id"]
        for row in diff["metric_changes"]
        if row["after"] > row["before"]
    }
    improvements = [
        row
        for row in diff["metric_changes"]
        if row["after"] < row["before"]
    ]
    accepted = _validated_accepts(
        accepts,
        allowed_ids=set(diff["new"]) | grown,
        revision=current["source"]["revision"],
    )
    accepted_ids = {row["finding_id"] for row in accepted}
    violations = [f"new:{identifier}" for identifier in diff["new"] if identifier not in accepted_ids]
    violations.extend(
        f"metric_grew:{row['finding_id']}:{row['metric']}:{row['before']}:{row['after']}"
        for row in diff["metric_changes"]
        if row["after"] > row["before"] and row["finding_id"] not in accepted_ids
    )
    document = copy.deepcopy(diff)
    document["accepts"] = accepted
    validate_diff(document)
    ordered_violations = tuple(sorted(violations))
    tighten = not ordered_violations and bool(diff["fixed"] or improvements or accepted)
    return RatchetResult(diff=document, violations=ordered_violations, tighten=tighten)
