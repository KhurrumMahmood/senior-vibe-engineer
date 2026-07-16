"""Parser-backed ecosystem detectors normalized for sweep manifests.

This module owns only the WP5 observation seam. Detection and parsing remain
with the existing ecosystem detectors and the verified WP4 fact providers;
the historical prototype is neither imported nor executed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence

from _lib.lang_adapter import (
    ANALYSIS_INTERFACE_VERSION,
    AnalysisFailure,
    iter_adapters,
)

from .manifest import FindingInput
from .schemas import SCHEMA_VERSION, validate_provider_observation
from .serialization import canonical_json_bytes


# WP5 intentionally consumes only the characterized Python complexity member
# and Python/TypeScript omnibus member. Rust and Go keep their native shims.
PARSER_ECOSYSTEM_LANGUAGES = frozenset({"python", "typescript"})
_OUTPUT_BYTE_LIMIT = 4 * 1024 * 1024
_TIMEOUT_SECONDS = 300
_TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
_ANALYSIS_FAILURE_KINDS = {
    "parse_error": "parse_failure",
    "missing_tool": "missing_executable",
    "tool_timeout": "timeout",
    "corrupt_output": "output_corruption",
    "tool_failure": "unexpected_exit",
    "unsupported_capability": "schema_mismatch",
    "unsupported_language": "schema_mismatch",
}


@dataclass(frozen=True)
class EcosystemProviderRun:
    """One validated provider observation and its unpublished findings."""

    observation: Mapping[str, Any]
    findings: tuple[FindingInput, ...]


def _detector_path(repo_root: Path, skill: str) -> Path:
    return repo_root / ".claude" / "skills" / skill / "scripts" / "detect.py"


def _load_detector(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load detector {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _adapter_version(language: str) -> str:
    matches = sorted(
        (adapter.name, adapter.provider_version)
        for adapter in iter_adapters()
        if adapter.language == language
    )
    if len(matches) != 1:
        raise ValueError(f"expected one verified WP4 adapter for {language}, got {matches}")
    name, version = matches[0]
    return f"analysis-v{ANALYSIS_INTERFACE_VERSION}:{name}@{version}"


def _tool_version(detector_path: Path, language: str) -> str:
    try:
        digest = hashlib.sha256(detector_path.read_bytes()).hexdigest()
    except OSError:
        digest = "unavailable"
    return f"{_adapter_version(language)}+detector-sha256:{digest}"


def _legacy_id(rule: str, path: str, symbol: str) -> str:
    """Retain the prototype SHA1 identifier as a one-release migration alias."""
    return hashlib.sha1(f"{rule}|{path}|{symbol}".encode()).hexdigest()[:12]


def _raw_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(dict(record)) for record in records)


def _raw_record(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    return {
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


def _command(
    detector_path: Path,
    *,
    provider: str,
    language: str,
    project_root: Path,
    scopes: Sequence[str | Path],
) -> dict[str, Any]:
    rendered_scopes = [Path(scope).as_posix() for scope in scopes]
    if provider == "cx":
        argv = [
            sys.executable,
            detector_path.as_posix(),
            "--project-root",
            project_root.as_posix(),
            "--output",
            "provider-output.jsonl",
            "--max-findings",
            "500",
            *rendered_scopes,
        ]
    else:
        argv = [
            sys.executable,
            detector_path.as_posix(),
            "--target",
            rendered_scopes[0],
            "--project-root",
            project_root.as_posix(),
            "--output",
            "provider-output.jsonl",
            "--language",
            language,
        ]
    return {
        "executable": sys.executable,
        "argv": argv,
        "timeout_seconds": _TIMEOUT_SECONDS,
        "output_format": "jsonl",
        "output_byte_limit": _OUTPUT_BYTE_LIMIT,
    }


def _completed_observation(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    project_root: Path,
    scopes: Sequence[str | Path],
    stdout: bytes,
) -> dict[str, Any]:
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "language": language,
        "provider_kind": "parser-backed-ecosystem",
        "command": _command(
            detector_path,
            provider=provider,
            language=language,
            project_root=project_root,
            scopes=scopes,
        ),
        "tool_version": _tool_version(detector_path, language),
        "exit": {"code": 0, "classification": "diagnostics" if stdout else "clean"},
        "raw": _raw_record(stdout, b""),
        "status": "completed",
        "failure": None,
    }
    return dict(validate_provider_observation(observation))


def _failed_observation(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    project_root: Path,
    scopes: Sequence[str | Path],
    failure_kind: str,
    message: str,
    details: Mapping[str, Any],
    stdout: bytes = b"",
) -> dict[str, Any]:
    stderr = (message.rstrip() + "\n").encode()
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "language": language,
        "provider_kind": "parser-backed-ecosystem",
        "command": _command(
            detector_path,
            provider=provider,
            language=language,
            project_root=project_root,
            scopes=scopes,
        ),
        "tool_version": _tool_version(detector_path, language),
        "exit": {"code": 1, "classification": "tool_failure"},
        "raw": _raw_record(stdout, stderr),
        "status": "failed",
        "failure": {
            "schema_version": SCHEMA_VERSION,
            "kind": failure_kind,
            "provider": provider,
            "message": message,
            "details": dict(details),
        },
    }
    return dict(validate_provider_observation(observation))


def _run_provider(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    project_root: Path,
    scopes: Sequence[str | Path],
    detector: Callable[[], list[dict[str, Any]]],
    normalize: Callable[[Mapping[str, Any], int], FindingInput],
) -> EcosystemProviderRun:
    stdout = b""
    try:
        records = detector()
        stdout = _raw_bytes(records)
        if len(stdout) > _OUTPUT_BYTE_LIMIT:
            observation = _failed_observation(
                provider=provider,
                language=language,
                detector_path=detector_path,
                project_root=project_root,
                scopes=scopes,
                failure_kind="output_overflow",
                message=f"detector output exceeds {_OUTPUT_BYTE_LIMIT} bytes",
                details={"stdout_bytes": len(stdout)},
            )
            return EcosystemProviderRun(observation, ())
        findings = tuple(normalize(record, index) for index, record in enumerate(records))
    except AnalysisFailure as exc:
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            project_root=project_root,
            scopes=scopes,
            failure_kind=_ANALYSIS_FAILURE_KINDS.get(exc.code, "output_corruption"),
            message=str(exc),
            details=exc.to_dict(),
            stdout=stdout,
        )
        return EcosystemProviderRun(observation, ())
    except Exception as exc:  # noqa: BLE001 - typed provider boundary
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            project_root=project_root,
            scopes=scopes,
            failure_kind="output_corruption",
            message=f"{type(exc).__name__}: {exc}",
            details={"exception": type(exc).__name__},
            stdout=stdout,
        )
        return EcosystemProviderRun(observation, ())

    observation = _completed_observation(
        provider=provider,
        language=language,
        detector_path=detector_path,
        project_root=project_root,
        scopes=scopes,
        stdout=stdout,
    )
    return EcosystemProviderRun(observation, findings)


def _number(record: Mapping[str, Any], name: str, default: int = 0) -> int:
    value = record.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    return int(value)


def _text(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _complexity_finding(
    record: Mapping[str, Any],
    observation_index: int,
) -> FindingInput:
    pattern = _text(record, "pattern")
    path = Path(_text(record, "file")).as_posix()
    symbol = str(record.get("symbol") or "<module>")
    impact = _number(record, "impact")
    summary = _text(record, "summary")
    metrics = {"impact": impact}
    for name in ("branch_score", "loc"):
        if name in record:
            metrics[name] = _number(record, name)
    prototype_rule = f"cx:{pattern}"
    return FindingInput(
        provider="cx",
        language="python",
        native_rule_id=pattern,
        rule_semantic_key=f"{prototype_rule}:v1",
        path=path,
        semantic_anchor=f"symbol:{symbol}",
        native_severity=str(record.get("confidence") or "unknown"),
        severity=3 if impact >= 80 else 2 if impact >= 50 else 1,
        message=summary,
        summary=summary,
        metrics=metrics,
        observation_index=observation_index,
        line=_number(record, "lineno", 1),
        legacy_ids=(_legacy_id(prototype_rule, path, symbol),),
    )


def _omnibus_finding(
    record: Mapping[str, Any],
    observation_index: int,
) -> FindingInput:
    path = Path(_text(record, "file")).as_posix()
    language = _text(record, "language")
    clusters = _number(record, "cluster_count")
    risk_signals = record.get("risk_signals", [])
    if not isinstance(risk_signals, list) or not all(isinstance(item, str) for item in risk_signals):
        raise ValueError("risk_signals must be an array of strings")
    message = (
        f"{_number(record, 'loc')} LOC, {clusters} symbol clusters, "
        f"risk signals: {','.join(risk_signals[:4])}"
    )
    return FindingInput(
        provider="omnibus",
        language=language,
        native_rule_id="omnibus",
        rule_semantic_key="omnibus:v1",
        path=path,
        semantic_anchor="module",
        native_severity="high" if clusters >= 10 else "medium",
        severity=3 if clusters >= 10 else 2,
        message=message,
        summary=str(record.get("srp_sentence") or message),
        metrics={
            "loc": _number(record, "loc"),
            "clusters": clusters,
            "and_count": _number(record, "and_count"),
            "score": _number(record, "score"),
            "risk_score": _number(record, "risk_score"),
        },
        observation_index=observation_index,
        line=1,
        legacy_ids=(_legacy_id("omnibus", path, ""),) if language == "python" else (),
    )


# spec:portable-batch-sweep::IM-13
def run_complexity_provider(
    repo_root: Path,
    scopes: Sequence[str | Path],
    *,
    observation_index: int,
) -> EcosystemProviderRun:
    """Run the characterized Python complexity detector through the WP5 seam."""
    repo_root = repo_root.resolve()
    if not scopes:
        raise ValueError("complexity provider requires at least one scope")
    detector_path = _detector_path(_TOOLKIT_ROOT, "find-complexity-hotspots")
    try:
        module = _load_detector(detector_path, "_sweep_complexity_detector")
    except Exception as exc:  # noqa: BLE001 - detector discovery boundary
        observation = _failed_observation(
            provider="cx",
            language="python",
            detector_path=detector_path,
            project_root=repo_root,
            scopes=scopes,
            failure_kind="missing_executable" if isinstance(exc, (FileNotFoundError, ImportError)) else "unexpected_exit",
            message=f"{type(exc).__name__}: {exc}",
            details={"exception": type(exc).__name__},
        )
        return EcosystemProviderRun(observation, ())
    return _run_provider(
        provider="cx",
        language="python",
        detector_path=detector_path,
        project_root=repo_root,
        scopes=scopes,
        detector=lambda: module.detect(
            repo_root,
            [Path(scope).as_posix() for scope in scopes],
            include_tests=False,
            max_findings=500,
        ),
        normalize=lambda record, _index: _complexity_finding(record, observation_index),
    )


# spec:portable-batch-sweep::IM-14
def run_omnibus_provider(
    repo_root: Path,
    scopes: Sequence[str | Path],
    *,
    language: str,
    observation_index: int,
) -> EcosystemProviderRun:
    """Run one eligible parser-backed omnibus language observation."""
    if language not in PARSER_ECOSYSTEM_LANGUAGES:
        raise ValueError("parser-backed omnibus supports only python and typescript")
    repo_root = repo_root.resolve()
    if len(scopes) != 1:
        raise ValueError("one omnibus observation requires exactly one scope")
    detector_path = _detector_path(_TOOLKIT_ROOT, "find-omnibus")
    try:
        module = _load_detector(detector_path, "_sweep_omnibus_detector")
    except Exception as exc:  # noqa: BLE001 - detector discovery boundary
        observation = _failed_observation(
            provider="omnibus",
            language=language,
            detector_path=detector_path,
            project_root=repo_root,
            scopes=scopes,
            failure_kind="missing_executable" if isinstance(exc, (FileNotFoundError, ImportError)) else "unexpected_exit",
            message=f"{type(exc).__name__}: {exc}",
            details={"exception": type(exc).__name__},
        )
        return EcosystemProviderRun(observation, ())

    def detect() -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for scope in scopes:
            target = Path(scope)
            if not target.is_absolute():
                target = repo_root / target
            records.extend(
                module.detect(target, repo_root, languages={language})
            )
        unique = {
            canonical_json_bytes(record): record
            for record in records
        }
        return sorted(
            unique.values(),
            key=lambda row: (-int(row["score"]), str(row["file"])),
        )

    return _run_provider(
        provider="omnibus",
        language=language,
        detector_path=detector_path,
        project_root=repo_root,
        scopes=scopes,
        detector=detect,
        normalize=lambda record, _index: _omnibus_finding(record, observation_index),
    )
