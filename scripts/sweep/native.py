"""Registry-driven native-provider execution and normalization."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from _lib.capability_registry import CapabilityRegistry, load_registry

from ._native_parsers import NativeOutputError, parse_native_output
from .manifest import FindingInput
from .process import CapturedProcess, capture_process
from .schemas import SCHEMA_VERSION, validate_failure, validate_provider_observation


@dataclass(frozen=True)
class ProviderContract:
    """One native command contract authored in the canonical registry."""

    provider: str
    language: str
    provider_kind: str
    executable_candidates: tuple[str, ...]
    argv: tuple[str, ...]
    version_argv: tuple[str, ...]
    version_pattern: str
    timeout_seconds: float
    output_format: str
    output_stream: str
    output_byte_limit: int
    clean_exit_codes: frozenset[int]
    diagnostic_exit_codes: frozenset[int]
    semantic_rule_version: int
    toolkit_root: Path = field(compare=False, repr=False)


@dataclass(frozen=True)
class ProviderResult:
    """A completed observation and its normalized pre-manifest findings."""

    observation: Mapping[str, Any]
    findings: tuple[FindingInput, ...]


class ProviderExecutionError(RuntimeError):
    """A loud typed provider failure with a schema-valid failed observation."""

    def __init__(self, failure: Mapping[str, Any], observation: Mapping[str, Any]):
        self.failure = failure
        self.observation = observation
        super().__init__(f"{failure['kind']}: {failure['message']}")


def _toolkit_root(registry: CapabilityRegistry) -> Path:
    default = Path(__file__).resolve().parents[2]
    for parent in registry.path.parents:
        if parent.joinpath("scripts", "sweep_shims.py").is_file():
            return parent
    return default


# spec:portable-batch-sweep::IM-5
def provider_contracts_from_registry(
    language: str,
    *,
    registry: CapabilityRegistry | None = None,
) -> tuple[ProviderContract, ...]:
    """Resolve all native providers for one language without local identifiers."""
    registry = registry or load_registry()
    if language not in registry.identifiers("languages"):
        raise ValueError(f"unregistered language: {language}")
    providers = registry.data["sweep_targets"].get(language, [])
    root = _toolkit_root(registry)
    contracts: list[ProviderContract] = []
    for provider in providers:
        entry = registry.data["sweep_providers"][provider]
        if entry["provider_kind"] != "native":
            continue
        contracts.append(
            ProviderContract(
                provider=provider,
                language=language,
                provider_kind=entry["provider_kind"],
                executable_candidates=tuple(entry["executable"]),
                argv=tuple(entry["argv"]),
                version_argv=tuple(entry["version_argv"]),
                version_pattern=entry["version_pattern"],
                timeout_seconds=float(entry["timeout_seconds"]),
                output_format=entry["output_format"],
                output_stream=entry["output_stream"],
                output_byte_limit=int(entry["output_byte_limit"]),
                clean_exit_codes=frozenset(entry["clean_exit_codes"]),
                diagnostic_exit_codes=frozenset(entry["diagnostic_exit_codes"]),
                semantic_rule_version=int(entry["semantic_rule_version"]),
                toolkit_root=root,
            )
        )
    return tuple(contracts)


def discover_executable(contract: ProviderContract, *, root: Path | str) -> Path | None:
    """Resolve a declared candidate against the host, toolkit, then process PATH."""
    host_root = Path(root).resolve()
    for candidate in contract.executable_candidates:
        candidate_path = Path(candidate)
        options: list[Path] = []
        if candidate_path.is_absolute():
            options.append(candidate_path)
        else:
            options.extend((host_root / candidate_path, contract.toolkit_root / candidate_path))
        for option in options:
            if option.is_file() and os.access(option, os.X_OK):
                # Preserve the executable basename for dispatching symlink shims such as
                # rustup's `cargo`; resolving that link changes argv[0] to rustup-init.
                return option.absolute()
        if len(candidate_path.parts) == 1:
            discovered = shutil.which(candidate)
            if discovered:
                return Path(discovered).absolute()
    return None


def _command_document(contract: ProviderContract, executable: str) -> dict[str, Any]:
    return {
        "executable": executable,
        "argv": list(contract.argv),
        "timeout_seconds": contract.timeout_seconds,
        "output_format": contract.output_format,
        "output_byte_limit": contract.output_byte_limit,
    }


def _raw_document(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    return {
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


def _scope_document(*, case_sensitive: bool) -> dict[str, Any]:
    """Native provider commands execute from and cover the complete host root."""
    return {
        "paths": ["."],
        "case_sensitive": case_sensitive,
        "roots": ["."],
        "exclusions": [],
    }


def _exit_code(code: int) -> int:
    return code if code >= 0 else 128 + abs(code)


def _failed(
    contract: ProviderContract,
    *,
    kind: str,
    message: str,
    details: Mapping[str, Any],
    executable: str,
    tool_version: str,
    exit_code: int,
    stdout: bytes,
    stderr: bytes,
    case_sensitive: bool = True,
) -> ProviderExecutionError:
    failure = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "provider": contract.provider,
        "message": message,
        "details": dict(details),
    }
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": contract.provider,
        "language": contract.language,
        "provider_kind": contract.provider_kind,
        "scope": _scope_document(case_sensitive=case_sensitive),
        "command": _command_document(contract, executable),
        "tool_version": tool_version or "unavailable",
        "exit": {"code": _exit_code(exit_code), "classification": "tool_failure"},
        "raw": _raw_document(stdout, stderr),
        "status": "failed",
        "failure": failure,
    }
    validate_failure(failure)
    validate_provider_observation(observation)
    return ProviderExecutionError(failure, observation)


def _decode(
    contract: ProviderContract,
    *,
    payload: bytes,
    executable: str,
    tool_version: str,
    exit_code: int,
    stdout: bytes,
    stderr: bytes,
    case_sensitive: bool = True,
) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _failed(
            contract,
            kind="output_corruption",
            message="native output is not valid UTF-8",
            details={"offset": exc.start},
            executable=executable,
            tool_version=tool_version,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            case_sensitive=case_sensitive,
        ) from exc


def _selected_payload(contract: ProviderContract, stdout: bytes, stderr: bytes) -> bytes:
    if contract.output_stream == "stdout":
        return stdout
    if contract.output_stream == "stderr":
        return stderr
    if stdout.strip() and stderr.strip():
        raise NativeOutputError(
            "schema_mismatch",
            "provider emitted diagnostic payloads on both stdout and stderr",
        )
    return stdout if stdout.strip() else stderr


def normalize_provider_output(
    contract: ProviderContract,
    *,
    root: Path | str,
    stdout: bytes,
    stderr: bytes,
    exit_code: int,
    tool_version: str,
    executable: str,
    observation_index: int = 0,
    case_sensitive: bool = True,
) -> ProviderResult:
    """Validate and normalize complete captured bytes; never accept a prefix."""
    raw_size = len(stdout) + len(stderr)
    if raw_size > contract.output_byte_limit:
        raise _failed(
            contract,
            kind="output_overflow",
            message="native output exceeds the registry byte ceiling",
            details={"bytes": raw_size, "limit": contract.output_byte_limit},
            executable=executable,
            tool_version=tool_version,
            exit_code=exit_code,
            stdout=stdout[: contract.output_byte_limit],
            stderr=stderr[: contract.output_byte_limit],
            case_sensitive=case_sensitive,
        )
    try:
        payload = _selected_payload(contract, stdout, stderr)
    except NativeOutputError as exc:
        raise _failed(
            contract,
            kind=exc.kind,
            message=str(exc),
            details=exc.details,
            executable=executable,
            tool_version=tool_version,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            case_sensitive=case_sensitive,
        ) from exc
    text = _decode(
        contract,
        payload=payload,
        executable=executable,
        tool_version=tool_version,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        case_sensitive=case_sensitive,
    )
    recognized = contract.clean_exit_codes | contract.diagnostic_exit_codes
    if exit_code not in recognized:
        raise _failed(
            contract,
            kind="unexpected_exit",
            message="native provider returned an unrecognized exit code",
            details={"exit_code": exit_code, "recognized": sorted(recognized)},
            executable=executable,
            tool_version=tool_version,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            case_sensitive=case_sensitive,
        )
    try:
        findings = parse_native_output(
            contract,
            text=text,
            root=Path(root).resolve(),
            observation_index=observation_index,
        )
    except NativeOutputError as exc:
        raise _failed(
            contract,
            kind=exc.kind,
            message=str(exc),
            details=exc.details,
            executable=executable,
            tool_version=tool_version,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            case_sensitive=case_sensitive,
        ) from exc
    classification = (
        "diagnostics"
        if exit_code in contract.diagnostic_exit_codes or findings
        else "clean"
    )
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": contract.provider,
        "language": contract.language,
        "provider_kind": contract.provider_kind,
        "scope": _scope_document(case_sensitive=case_sensitive),
        "command": _command_document(contract, executable),
        "tool_version": tool_version,
        "exit": {"code": exit_code, "classification": classification},
        "raw": _raw_document(stdout, stderr),
        "status": "completed",
        "failure": None,
    }
    validate_provider_observation(observation)
    return ProviderResult(observation=observation, findings=findings)


def _capture(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    output_byte_limit: int,
    env: Mapping[str, str] | None,
) -> CapturedProcess:
    return capture_process(
        argv,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        output_byte_limit=output_byte_limit,
    )


def _probe_version(
    contract: ProviderContract,
    *,
    executable: Path,
    root: Path,
    env: Mapping[str, str] | None,
    case_sensitive: bool,
) -> str:
    capture = _capture(
        (str(executable), *contract.version_argv),
        cwd=root,
        timeout_seconds=contract.timeout_seconds,
        output_byte_limit=min(contract.output_byte_limit, 65536),
        env=env,
    )
    if capture.fault is not None:
        raise _failed(
            contract,
            kind=capture.fault,
            message=f"native provider version probe {capture.fault.replace('_', ' ')}",
            details={"phase": "version_probe"},
            executable=str(executable),
            tool_version="unavailable",
            exit_code=capture.code,
            stdout=capture.stdout,
            stderr=capture.stderr,
            case_sensitive=case_sensitive,
        )
    if capture.code != 0:
        raise _failed(
            contract,
            kind="unexpected_exit",
            message="native provider version probe failed",
            details={"phase": "version_probe", "exit_code": capture.code},
            executable=str(executable),
            tool_version="unavailable",
            exit_code=capture.code,
            stdout=capture.stdout,
            stderr=capture.stderr,
            case_sensitive=case_sensitive,
        )
    combined = b"\n".join(part for part in (capture.stdout.strip(), capture.stderr.strip()) if part)
    version = _decode(
        contract,
        payload=combined,
        executable=str(executable),
        tool_version="unavailable",
        exit_code=capture.code,
        stdout=capture.stdout,
        stderr=capture.stderr,
        case_sensitive=case_sensitive,
    ).strip()
    if re.fullmatch(contract.version_pattern, version) is None:
        raise _failed(
            contract,
            kind="schema_mismatch",
            message="native provider version does not match the registry contract",
            details={"phase": "version_probe", "version": version},
            executable=str(executable),
            tool_version=version or "unavailable",
            exit_code=capture.code,
            stdout=capture.stdout,
            stderr=capture.stderr,
            case_sensitive=case_sensitive,
        )
    return version


def _atomic_write(path: Path, content: bytes) -> None:
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


def _execute_discovered(
    contract: ProviderContract,
    *,
    root: Path,
    executable: Path,
    artifact_dir: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    tool_version: str | None = None,
    observation_index: int = 0,
    case_sensitive: bool = True,
) -> ProviderResult:
    version = tool_version or _probe_version(
        contract,
        executable=executable,
        root=root,
        env=env,
        case_sensitive=case_sensitive,
    )
    capture = _capture(
        (str(executable), *contract.argv),
        cwd=root,
        timeout_seconds=contract.timeout_seconds,
        output_byte_limit=contract.output_byte_limit,
        env=env,
    )
    if capture.fault is not None:
        raise _failed(
            contract,
            kind=capture.fault,
            message=f"native provider {capture.fault.replace('_', ' ')}",
            details={
                "bytes": len(capture.stdout) + len(capture.stderr),
                "limit": contract.output_byte_limit,
            },
            executable=str(executable),
            tool_version=version,
            exit_code=capture.code,
            stdout=capture.stdout,
            stderr=capture.stderr,
            case_sensitive=case_sensitive,
        )
    result = normalize_provider_output(
        contract,
        root=root,
        stdout=capture.stdout,
        stderr=capture.stderr,
        exit_code=capture.code,
        tool_version=version,
        executable=str(executable),
        observation_index=observation_index,
        case_sensitive=case_sensitive,
    )
    if artifact_dir is not None:
        destination = Path(artifact_dir)
        _atomic_write(destination / f"{contract.provider}.stdout", capture.stdout)
        _atomic_write(destination / f"{contract.provider}.stderr", capture.stderr)
    return result


def execute_provider(
    contract: ProviderContract,
    *,
    root: Path | str,
    artifact_dir: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    tool_version: str | None = None,
    observation_index: int = 0,
    case_sensitive: bool = True,
) -> ProviderResult:
    """Execute one provider with bounded capture, group timeout, and atomic raw artifacts."""
    host_root = Path(root).resolve()
    executable = discover_executable(contract, root=host_root)
    if executable is None:
        raise _failed(
            contract,
            kind="missing_executable",
            message="no registry-declared executable candidate is available",
            details={"candidates": list(contract.executable_candidates)},
            executable=contract.executable_candidates[0],
            tool_version="unavailable",
            exit_code=127,
            stdout=b"",
            stderr=b"",
            case_sensitive=case_sensitive,
        )
    if contract.provider == "clippy":
        with tempfile.TemporaryDirectory(prefix="sweep-cargo-target-") as cargo_target:
            execution_env = dict(os.environ if env is None else env)
            execution_env.setdefault("CARGO_TARGET_DIR", cargo_target)
            return _execute_discovered(
                contract,
                root=host_root,
                executable=executable,
                artifact_dir=artifact_dir,
                env=execution_env,
                tool_version=tool_version,
                observation_index=observation_index,
                case_sensitive=case_sensitive,
            )
    return _execute_discovered(
        contract,
        root=host_root,
        executable=executable,
        artifact_dir=artifact_dir,
        env=env,
        tool_version=tool_version,
        observation_index=observation_index,
        case_sensitive=case_sensitive,
    )
