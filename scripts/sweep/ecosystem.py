"""Isolated parser-backed ecosystem detectors normalized for sweep manifests.

The recorded provider command is the command that actually runs. Detection
and parsing remain with the existing ecosystem detectors and verified WP4 fact
providers; this module owns scope validation, process isolation, artifact
capture, failure typing, and finding normalization only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

from _lib.lang_adapter import ANALYSIS_INTERFACE_VERSION, AnalysisFailure, iter_adapters

from .manifest import FindingInput
from .process import CapturedProcess, capture_process
from .schemas import FAILURE_KINDS, SCHEMA_VERSION, validate_provider_observation
from .serialization import canonical_json_bytes


PARSER_ECOSYSTEM_LANGUAGES = frozenset({"python", "typescript"})
_OUTPUT_BYTE_LIMIT = 4 * 1024 * 1024
_TIMEOUT_SECONDS = 300
_TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
_PROVIDER_PROCESS = Path(__file__).resolve().with_name("provider_process.py")
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


class _ScopeFailure(ValueError):
    """A provider request that cannot designate an eligible in-repo scope."""

    def __init__(self, message: str, **details: Any) -> None:
        self.details = details
        super().__init__(message)


class _CompletionFailure(ValueError):
    """A zero-exit provider payload without one exact final completion record."""


def _detector_path(skill: str) -> Path:
    return _TOOLKIT_ROOT / ".claude" / "skills" / skill / "scripts" / "detect.py"


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


def _completion_record(provider: str, language: str, finding_count: int) -> dict[str, Any]:
    return {
        "type": "provider_completion",
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "language": language,
        "finding_count": finding_count,
    }


def _raw_record(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    return {
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


@dataclass(frozen=True)
class _ExecutedScope:
    paths: tuple[Path, ...]
    roots: tuple[Path, ...]
    exclusions: tuple[Path, ...]
    case_sensitive: bool


def _validate_scope(
    project_root: Path,
    scope: Mapping[str, Any],
    *,
    provider: str,
) -> _ExecutedScope:
    try:
        root = project_root.resolve(strict=True)
    except OSError as exc:
        raise _ScopeFailure(
            f"project root is missing or unreadable: {project_root}",
            project_root=project_root.as_posix(),
        ) from exc
    if not root.is_dir():
        raise _ScopeFailure("project root must be a directory", project_root=root.as_posix())
    case_sensitive = scope.get("case_sensitive")
    if not isinstance(case_sensitive, bool):
        raise _ScopeFailure("provider scope requires an explicit case policy")

    def resolve_entries(name: str, *, strict: bool) -> tuple[Path, ...]:
        values = scope.get(name)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise _ScopeFailure(f"provider scope {name} must be an array of paths")
        if values != sorted(set(values)):
            raise _ScopeFailure(f"provider scope {name} must be sorted and unique")
        resolved: list[Path] = []
        for rendered in values:
            if any(character in rendered for character in "*?[]"):
                raise _ScopeFailure("scope globs are not executable provider paths", path=rendered)
            candidate = root / rendered
            try:
                candidate = candidate.resolve(strict=strict)
            except OSError as exc:
                raise _ScopeFailure(
                    f"scope {name[:-1]} is missing or unreadable",
                    path=rendered,
                ) from exc
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise _ScopeFailure(
                    f"scope {name[:-1]} escapes the project root",
                    path=rendered,
                ) from exc
            resolved.append(candidate)
        return tuple(resolved)

    paths = resolve_entries("paths", strict=True)
    roots = resolve_entries("roots", strict=True)
    exclusions = resolve_entries("exclusions", strict=False)
    if not paths:
        raise _ScopeFailure("provider requires at least one scope path", paths=[])
    if not roots or not all(boundary.is_dir() for boundary in roots):
        raise _ScopeFailure("provider roots must be existing directories")
    if provider == "omnibus" and len(paths) != 1:
        raise _ScopeFailure(
            "one omnibus observation requires exactly one scope path",
            paths=[path.as_posix() for path in paths],
        )

    def within(path: Path, boundary: Path) -> bool:
        rendered_path = path.as_posix()
        rendered_boundary = boundary.as_posix()
        if not case_sensitive:
            rendered_path = rendered_path.casefold()
            rendered_boundary = rendered_boundary.casefold()
        return rendered_path == rendered_boundary or rendered_path.startswith(
            f"{rendered_boundary}/"
        )

    for path in paths:
        if not any(within(path, boundary) for boundary in roots):
            raise _ScopeFailure(
                "scope path is outside the executed roots",
                path=path.as_posix(),
            )
        if provider == "cx" and not (
            path.is_dir() or (path.is_file() and path.suffix.lower() == ".py")
        ):
            raise _ScopeFailure(
                "complexity scope must be a Python file or directory",
                path=path.as_posix(),
            )
        if provider == "omnibus" and not path.is_dir():
            raise _ScopeFailure("omnibus scope must be a directory", path=path.as_posix())
    if any(not any(within(exclusion, boundary) for boundary in roots) for exclusion in exclusions):
        raise _ScopeFailure("scope exclusions must remain inside executed roots")
    return _ExecutedScope(paths, roots, exclusions, case_sensitive)


def _detect_complexity_records(
    project_root: Path,
    scope: Mapping[str, Any],
) -> list[dict[str, Any]]:
    executed = _validate_scope(project_root, scope, provider="cx")
    module = _load_detector(_detector_path("find-complexity-hotspots"), "_sweep_cx_process")
    selected = module.select_python_files(
        project_root.resolve(),
        [path.as_posix() for path in executed.paths],
        include_tests=False,
        roots=executed.roots,
        exclusions=executed.exclusions,
        case_sensitive=executed.case_sensitive,
    )
    if not selected:
        raise _ScopeFailure(
            "complexity scope contains no files eligible under the detector selection contract",
            paths=[path.as_posix() for path in executed.paths],
        )
    return module.detect(
        project_root.resolve(),
        [path.as_posix() for path in selected],
        include_tests=False,
        max_findings=None,
        roots=executed.roots,
        exclusions=executed.exclusions,
        case_sensitive=executed.case_sensitive,
    )


def _detect_omnibus_records(
    project_root: Path,
    scope: Mapping[str, Any],
    *,
    language: str,
) -> list[dict[str, Any]]:
    if language not in PARSER_ECOSYSTEM_LANGUAGES:
        raise _ScopeFailure(
            "parser-backed omnibus supports only python and typescript",
            language=language,
        )
    executed = _validate_scope(project_root, scope, provider="omnibus")
    target = executed.paths[0]
    module = _load_detector(_detector_path("find-omnibus"), "_sweep_omnibus_process")
    records, selected_count = module.detect_with_file_count(
        target,
        project_root.resolve(),
        languages={language},
        roots=executed.roots,
        exclusions=executed.exclusions,
        case_sensitive=executed.case_sensitive,
    )
    if selected_count == 0:
        raise _ScopeFailure(
            "omnibus scope contains no files eligible under the detector selection contract",
            path=target.as_posix(),
            language=language,
        )
    unique = {canonical_json_bytes(record): record for record in records}
    return sorted(unique.values(), key=lambda row: (-int(row["score"]), str(row["file"])))


def _failure_envelope(kind: str, message: str, details: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(
        {"failure": {"kind": kind, "message": message, "details": dict(details)}}
    )


def provider_process_main(argv: list[str] | None = None) -> int:
    """Run one detector in a child process and emit only canonical artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("cx", "omnibus"))
    parser.add_argument("--language", required=True)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--case-sensitive", required=True, choices=("true", "false"))
    args = parser.parse_args(argv)
    scope = {
        "paths": args.path,
        "case_sensitive": args.case_sensitive == "true",
        "roots": args.root,
        "exclusions": args.exclude,
    }
    try:
        if args.provider == "cx":
            if args.language != "python":
                raise _ScopeFailure("complexity provider supports only python")
            records = _detect_complexity_records(args.project_root, scope)
        else:
            records = _detect_omnibus_records(
                args.project_root,
                scope,
                language=args.language,
            )
    except _ScopeFailure as exc:
        sys.stderr.buffer.write(_failure_envelope("schema_mismatch", str(exc), exc.details))
        return 2
    except AnalysisFailure as exc:
        kind = _ANALYSIS_FAILURE_KINDS.get(exc.code, "output_corruption")
        sys.stderr.buffer.write(_failure_envelope(kind, str(exc), exc.to_dict()))
        return 2
    except (FileNotFoundError, ImportError, ModuleNotFoundError) as exc:
        sys.stderr.buffer.write(
            _failure_envelope(
                "missing_executable",
                f"{type(exc).__name__}: {exc}",
                {"exception": type(exc).__name__},
            )
        )
        return 2
    except Exception as exc:  # noqa: BLE001 - isolated provider boundary
        sys.stderr.buffer.write(
            _failure_envelope(
                "output_corruption",
                f"{type(exc).__name__}: {exc}",
                {"exception": type(exc).__name__},
            )
        )
        return 2
    sys.stdout.buffer.write(
        _raw_bytes([*records, _completion_record(args.provider, args.language, len(records))])
    )
    return 0


def _command(
    *,
    provider: str,
    language: str,
    project_root: Path,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    argv = [
        sys.executable,
        _PROVIDER_PROCESS.as_posix(),
        "--provider",
        provider,
        "--language",
        language,
        "--project-root",
        project_root.as_posix(),
    ]
    for path in scope["paths"]:
        argv.extend(("--path", path))
    for root in scope["roots"]:
        argv.extend(("--root", root))
    for exclusion in scope["exclusions"]:
        argv.extend(("--exclude", exclusion))
    argv.extend(("--case-sensitive", "true" if scope["case_sensitive"] else "false"))
    return {
        "executable": sys.executable,
        "argv": argv,
        "timeout_seconds": _TIMEOUT_SECONDS,
        "output_format": "canonical-jsonl",
        "output_byte_limit": _OUTPUT_BYTE_LIMIT,
    }


def _scope_provenance(
    project_root: Path,
    scopes: Sequence[str | Path],
    *,
    roots: Sequence[str | Path] | None,
    exclusions: Sequence[str | Path],
    case_sensitive: bool,
) -> dict[str, Any]:
    root = project_root.resolve()
    invalid = False

    def normalized(values: Sequence[str | Path]) -> list[str]:
        nonlocal invalid
        paths: set[str] = set()
        for raw in values:
            requested = Path(raw)
            candidate = requested if requested.is_absolute() else root / requested
            try:
                relative = candidate.resolve().relative_to(root).as_posix()
            except ValueError:
                invalid = True
                continue
            rendered = relative or "."
            paths.add(rendered if case_sensitive else rendered.casefold())
        return sorted(paths)

    paths = normalized(scopes)
    if roots is None:
        default_roots: list[str | Path] = []
        for raw in scopes:
            requested = Path(raw)
            candidate = requested if requested.is_absolute() else root / requested
            default_roots.append(candidate.parent if candidate.is_file() else raw)
        roots = default_roots
    canonical_roots = normalized(roots)
    canonical_exclusions = normalized(exclusions)
    if invalid:
        paths = []
        canonical_roots = ["."]
        canonical_exclusions = []
    return {
        "paths": paths,
        "case_sensitive": case_sensitive,
        "roots": canonical_roots,
        "exclusions": canonical_exclusions,
    }


def _completed_observation(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    scope: Mapping[str, Any],
    command: Mapping[str, Any],
    captured: CapturedProcess,
    finding_count: int,
) -> dict[str, Any]:
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "language": language,
        "provider_kind": "parser-backed-ecosystem",
        "scope": dict(scope),
        "command": dict(command),
        "tool_version": _tool_version(detector_path, language),
        "exit": {
            "code": captured.returncode,
            "classification": "diagnostics" if finding_count else "clean",
        },
        "raw": dict(captured.raw),
        "status": "completed",
        "failure": None,
    }
    return dict(validate_provider_observation(observation))


def _failed_observation(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    scope: Mapping[str, Any],
    command: Mapping[str, Any],
    captured: CapturedProcess,
    failure_kind: str,
    message: str,
    details: Mapping[str, Any],
) -> dict[str, Any]:
    observation = {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "language": language,
        "provider_kind": "parser-backed-ecosystem",
        "scope": dict(scope),
        "command": dict(command),
        "tool_version": _tool_version(detector_path, language),
        "exit": {"code": captured.returncode, "classification": "tool_failure"},
        "raw": dict(captured.raw),
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


def _failure_from_stderr(stderr: bytes | None) -> tuple[str, str, Mapping[str, Any]]:
    if stderr is None:
        return "output_overflow", "provider stderr exceeds its byte limit", {}
    try:
        envelope = json.loads(stderr)
        failure = envelope["failure"]
        kind = failure["kind"]
        message = failure["message"]
        details = failure["details"]
        if kind not in FAILURE_KINDS or not isinstance(message, str) or not isinstance(details, dict):
            raise ValueError("invalid failure envelope")
        return kind, message, details
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return (
            "unexpected_exit",
            "provider exited without a valid typed failure envelope",
            {"stderr_sha256": hashlib.sha256(stderr).hexdigest()},
        )


def _parse_records(stdout: bytes, *, provider: str, language: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid provider JSONL at line {number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"provider JSONL line {number} must be an object")
        rows.append(row)
    completion_indexes = [
        index for index, row in enumerate(rows) if row.get("type") == "provider_completion"
    ]
    if completion_indexes != [len(rows) - 1]:
        raise _CompletionFailure("provider requires exactly one final completion record")
    records = rows[:-1]
    expected = _completion_record(provider, language, len(records))
    if rows[-1] != expected:
        raise _CompletionFailure("provider completion record does not match its payload")
    return records


def _run_provider(
    *,
    provider: str,
    language: str,
    detector_path: Path,
    project_root: Path,
    scopes: Sequence[str | Path],
    observation_index: int,
    roots: Sequence[str | Path] | None,
    exclusions: Sequence[str | Path],
    case_sensitive: bool,
) -> EcosystemProviderRun:
    scope = _scope_provenance(
        project_root,
        scopes,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )
    command = _command(
        provider=provider,
        language=language,
        project_root=project_root,
        scope=scope,
    )
    try:
        captured = capture_process(
            command["argv"],
            cwd=project_root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            timeout_seconds=float(command["timeout_seconds"]),
            output_byte_limit=int(command["output_byte_limit"]),
        )
    except OSError as exc:
        empty = b""
        captured = CapturedProcess(127, False, False, _raw_record(empty, empty), empty, empty)
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind="missing_executable",
            message=f"{type(exc).__name__}: {exc}",
            details={"exception": type(exc).__name__},
        )
        return EcosystemProviderRun(observation, ())

    if captured.timed_out:
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind="timeout",
            message=f"provider exceeded {command['timeout_seconds']}s deadline",
            details={
                "timeout_seconds": command["timeout_seconds"],
                "stdout_sha256": captured.raw["stdout_sha256"],
                "stderr_sha256": captured.raw["stderr_sha256"],
            },
        )
        return EcosystemProviderRun(observation, ())

    byte_limit = int(command["output_byte_limit"])
    if captured.output_overflow or (
        captured.raw["stdout_bytes"] > byte_limit
        or captured.raw["stderr_bytes"] > byte_limit
    ):
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind="output_overflow",
            message=f"provider artifact exceeds {byte_limit} bytes",
            details=dict(captured.raw),
        )
        return EcosystemProviderRun(observation, ())

    if captured.returncode != 0:
        kind, message, details = _failure_from_stderr(captured.stderr)
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind=kind,
            message=message,
            details=details,
        )
        return EcosystemProviderRun(observation, ())

    try:
        records = _parse_records(captured.stdout, provider=provider, language=language)
        normalizer = _complexity_finding if provider == "cx" else _omnibus_finding
        findings = tuple(normalizer(record, observation_index) for record in records)
    except _CompletionFailure as exc:
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind="missing_completion",
            message=str(exc),
            details={"stdout_sha256": captured.raw["stdout_sha256"]},
        )
        return EcosystemProviderRun(observation, ())
    except Exception as exc:  # noqa: BLE001 - provider output boundary
        observation = _failed_observation(
            provider=provider,
            language=language,
            detector_path=detector_path,
            scope=scope,
            command=command,
            captured=captured,
            failure_kind="output_corruption",
            message=f"{type(exc).__name__}: {exc}",
            details={"exception": type(exc).__name__},
        )
        return EcosystemProviderRun(observation, ())

    observation = _completed_observation(
        provider=provider,
        language=language,
        detector_path=detector_path,
        scope=scope,
        command=command,
        captured=captured,
        finding_count=len(findings),
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
    roots: Sequence[str | Path] | None = None,
    exclusions: Sequence[str | Path] = (),
    case_sensitive: bool = True,
) -> EcosystemProviderRun:
    """Execute the characterized Python complexity provider in isolation."""
    repo_root = repo_root.resolve()
    return _run_provider(
        provider="cx",
        language="python",
        detector_path=_detector_path("find-complexity-hotspots"),
        project_root=repo_root,
        scopes=scopes,
        observation_index=observation_index,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )


# spec:portable-batch-sweep::IM-14
def run_omnibus_provider(
    repo_root: Path,
    scopes: Sequence[str | Path],
    *,
    language: str,
    observation_index: int,
    roots: Sequence[str | Path] | None = None,
    exclusions: Sequence[str | Path] = (),
    case_sensitive: bool = True,
) -> EcosystemProviderRun:
    """Execute one eligible parser-backed omnibus language observation."""
    if language not in PARSER_ECOSYSTEM_LANGUAGES:
        raise ValueError("parser-backed omnibus supports only python and typescript")
    repo_root = repo_root.resolve()
    return _run_provider(
        provider="omnibus",
        language=language,
        detector_path=_detector_path("find-omnibus"),
        project_root=repo_root,
        scopes=scopes,
        observation_index=observation_index,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )
