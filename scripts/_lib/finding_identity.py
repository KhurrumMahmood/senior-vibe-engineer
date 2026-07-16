"""Stable, versioned finding identity for mixed-language sweep manifests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


FINDING_ID_SCHEMA_VERSION = 2


def normalize_repo_path(
    path: Path | str,
    *,
    repo_root: Path | str | None = None,
    case_sensitive: bool = True,
) -> str:
    raw = Path(path)
    if raw.is_absolute():
        if repo_root is None:
            raise ValueError("absolute finding paths require repo_root")
        try:
            raw = raw.resolve().relative_to(Path(repo_root).resolve())
        except ValueError as exc:
            raise ValueError("finding path is outside repo_root") from exc
    normalized = PurePosixPath(raw.as_posix()).as_posix()
    if normalized == "." or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("finding path must identify a file inside the repository")
    return normalized if case_sensitive else normalized.casefold()


@dataclass(frozen=True)
class FindingIdentity:
    provider: str
    rule: str
    language: str
    path: str
    semantic_anchor: str
    occurrence: int = 0
    case_sensitive: bool = True

    def canonical_payload(self) -> dict[str, object]:
        for field, value in (
            ("provider", self.provider),
            ("rule", self.rule),
            ("language", self.language),
            ("semantic_anchor", self.semantic_anchor),
        ):
            if not value.strip():
                raise ValueError(f"finding identity {field} must not be empty")
        if self.occurrence < 0:
            raise ValueError("finding identity occurrence must be non-negative")
        return {
            "schema": FINDING_ID_SCHEMA_VERSION,
            "provider": self.provider.strip(),
            "rule": self.rule.strip(),
            "language": self.language.strip(),
            "path": normalize_repo_path(self.path, case_sensitive=self.case_sensitive),
            "semantic_anchor": " ".join(self.semantic_anchor.split()),
            "occurrence": self.occurrence,
        }

    def identifier(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"f{FINDING_ID_SCHEMA_VERSION}_{hashlib.sha256(encoded).hexdigest()[:24]}"


def finding_record(
    identity: FindingIdentity,
    *,
    tool_version: str,
    line: int | None = None,
    legacy_ids: list[str] | None = None,
) -> dict[str, object]:
    """Create the identity envelope; volatile location/tool data stays outside the hash."""
    return {
        "finding_id_schema": FINDING_ID_SCHEMA_VERSION,
        "id": identity.identifier(),
        "identity": identity.canonical_payload(),
        "location": {"line": line},
        "producer": {"version": tool_version},
        "legacy_ids": sorted(set(legacy_ids or [])),
    }
