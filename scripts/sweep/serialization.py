"""Deterministic JSON serialization and hashing for sweep artifacts."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class CanonicalJSONError(ValueError):
    """Raised when a value cannot be represented as canonical JSON."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return sorted, compact UTF-8 JSON with exactly one terminal newline."""
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalJSONError(f"value is not canonical JSON: {exc}") from exc
    return f"{encoded}\n".encode("utf-8")


def canonical_json_text(value: Any) -> str:
    """Return the canonical JSON byte representation decoded as UTF-8."""
    return canonical_json_bytes(value).decode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash the canonical JSON bytes for a semantic or artifact projection."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
