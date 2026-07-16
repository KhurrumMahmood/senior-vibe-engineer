"""Versioned contracts shared by the productized batch-sweep pipeline."""

from pathlib import Path
import sys


# Support both ``python -m sweep`` with ``scripts`` on sys.path and the public
# ``python -m scripts.sweep`` form from a bundle root.
_SCRIPTS_ROOT = str(Path(__file__).resolve().parents[1])
if _SCRIPTS_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPTS_ROOT)

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
from .commands import (
    EXIT_CHANGED,
    EXIT_INPUT,
    EXIT_OK,
    EXIT_OUTPUT,
    EXIT_PROVIDER,
    EXIT_USAGE,
    RatchetResult,
    apply_ratchet,
    render_digest,
    scan_native,
    scan_profile,
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
from .pipeline import (
    HarnessScan,
    JudgmentGateError,
    VerificationGateError,
    build_judgment,
    build_judgment_input,
    build_packet,
    import_judgment_outcomes,
    render_judged_digest,
    read_changed_paths,
    run_scan_command,
    run_verification_command,
    validate_judged_digest,
    verify_packet,
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
    "EXIT_CHANGED",
    "EXIT_INPUT",
    "EXIT_OK",
    "EXIT_OUTPUT",
    "EXIT_PROVIDER",
    "EXIT_USAGE",
    "FindingInput",
    "HarnessScan",
    "JudgmentGateError",
    "ManifestIdentityError",
    "PrototypeMigration",
    "RatchetResult",
    "ProviderContract",
    "ProviderExecutionError",
    "ProviderResult",
    "SchemaValidationError",
    "VerificationGateError",
    "build_diff",
    "build_manifest",
    "build_judgment",
    "build_judgment_input",
    "build_packet",
    "canonical_json_bytes",
    "canonical_json_text",
    "canonical_sha256",
    "apply_ratchet",
    "discover_executable",
    "execute_provider",
    "import_judgment_outcomes",
    "migrate_prototype_manifest",
    "normalize_provider_output",
    "provider_contracts_from_registry",
    "read_manifest",
    "render_digest",
    "render_judged_digest",
    "read_changed_paths",
    "run_scan_command",
    "run_verification_command",
    "scan_native",
    "scan_profile",
    "validate_diff",
    "validate_failure",
    "validate_judgment",
    "validate_judged_digest",
    "validate_manifest",
    "validate_packet",
    "validate_provider_observation",
    "verify_packet",
    "write_manifest",
]
