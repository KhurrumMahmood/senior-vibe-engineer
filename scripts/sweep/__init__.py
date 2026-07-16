"""Versioned contracts shared by the productized batch-sweep pipeline."""

# spec:portable-batch-sweep::IM-1

from .manifest import (
    FindingInput,
    ManifestIdentityError,
    PrototypeMigration,
    build_diff,
    build_manifest,
    migrate_prototype_manifest,
    read_manifest,
    write_manifest,
)
from .native import (
    ProviderContract,
    ProviderExecutionError,
    ProviderResult,
    discover_executable,
    execute_provider,
    normalize_provider_output,
    provider_contracts_from_registry,
)
from .schemas import (
    DEFAULT_MANIFEST_PATH,
    SchemaValidationError,
    validate_diff,
    validate_failure,
    validate_judgment,
    validate_manifest,
    validate_packet,
    validate_provider_observation,
)
from .serialization import canonical_json_bytes, canonical_json_text, canonical_sha256

__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "FindingInput",
    "ManifestIdentityError",
    "PrototypeMigration",
    "ProviderContract",
    "ProviderExecutionError",
    "ProviderResult",
    "SchemaValidationError",
    "build_diff",
    "build_manifest",
    "canonical_json_bytes",
    "canonical_json_text",
    "canonical_sha256",
    "discover_executable",
    "execute_provider",
    "migrate_prototype_manifest",
    "normalize_provider_output",
    "provider_contracts_from_registry",
    "read_manifest",
    "validate_diff",
    "validate_failure",
    "validate_judgment",
    "validate_manifest",
    "validate_packet",
    "validate_provider_observation",
    "write_manifest",
]
