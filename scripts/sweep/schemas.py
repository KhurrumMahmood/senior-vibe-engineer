"""Runtime schemas for the batch-sweep artifact boundary.

These validators define the closed version-1 envelopes. They validate
already-normalized data; the manifest module owns identity assignment,
legacy migration, and writing while later slices own command behavior.
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from _lib.finding_identity import FINDING_ID_SCHEMA_VERSION, FindingIdentity

from .serialization import canonical_sha256


SCHEMA_VERSION = 1
# spec:portable-batch-sweep::IM-2
DEFAULT_MANIFEST_PATH = ".engineering/sweep/manifest.json"

FAILURE_KINDS = frozenset(
    {
        "missing_executable",
        "unexpected_exit",
        "parse_failure",
        "timeout",
        "truncated_output",
        "output_overflow",
        "output_corruption",
        "missing_completion",
        "schema_mismatch",
    }
)
PROVIDER_STATUSES = frozenset({"completed", "failed"})
EXIT_CLASSIFICATIONS = frozenset({"clean", "diagnostics", "tool_failure"})
JUDGMENT_OUTCOMES = frozenset({"actionable", "not_actionable", "uncertain", "failed"})

_SHA256 = re.compile(r"[0-9a-f]{64}")
_FINDING_ID = re.compile(r"f2_[0-9a-f]{24}")
_LEGACY_ID = re.compile(r"(?:f2_[0-9a-f]{24}|[0-9a-f]{12})")
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_PARSER_PROVIDER_KIND = "parser-backed-ecosystem"
_PARSER_PROVIDERS = frozenset({"cx", "omnibus"})
_VERSIONED_ENVELOPES = frozenset(
    {"failure", "provider_observation", "manifest", "diff", "judgment", "packet"}
)


class SchemaValidationError(ValueError):
    """A deterministic schema-boundary rejection."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True)
class ParserRunContext:
    """Externally trusted identity for one parser-backed provider run."""

    workspace_root: str
    executable: str
    provider_process_path: str
    provider_process_sha256: str

    @property
    def identity_sha256(self) -> str:
        return canonical_sha256(
            {
                "workspace_root": self.workspace_root,
                "executable": self.executable,
                "provider_process_path": self.provider_process_path,
                "provider_process_sha256": self.provider_process_sha256,
            }
        )


def trusted_parser_run_context(workspace_root: Path | str) -> ParserRunContext:
    """Resolve trusted runtime identity without consulting observation data."""
    try:
        root = Path(workspace_root).resolve(strict=True)
        provider_process = (
            Path(__file__).resolve().with_name("provider_process.py").resolve(strict=True)
        )
        provider_process_bytes = provider_process.read_bytes()
    except OSError as exc:
        raise SchemaValidationError(
            "parser_run_context",
            f"trusted runtime path is missing or unreadable: {exc}",
        ) from exc
    if not root.is_dir():
        raise SchemaValidationError("parser_run_context.workspace_root", "must be a directory")
    if not provider_process.is_file():
        raise SchemaValidationError(
            "parser_run_context.provider_process_path",
            "canonical provider process must be a file",
        )
    return ParserRunContext(
        workspace_root=root.as_posix(),
        executable=sys.executable,
        provider_process_path=provider_process.as_posix(),
        provider_process_sha256=hashlib.sha256(provider_process_bytes).hexdigest(),
    )


def _fail(path: str, message: str) -> None:
    raise SchemaValidationError(path, message)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    if not all(isinstance(key, str) for key in value):
        _fail(path, "object keys must be strings")
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _required(document: Mapping[str, Any], names: Sequence[str], path: str) -> None:
    """Require the exact fields declared by a versioned envelope."""
    missing = [name for name in names if name not in document]
    if missing:
        _fail(path, f"missing required fields: {', '.join(missing)}")
    allowed = set(names)
    if path in _VERSIONED_ENVELOPES:
        allowed.add("schema_version")
    unknown = sorted(set(document) - allowed)
    if unknown:
        _fail(path, f"unknown fields for schema version {SCHEMA_VERSION}: {', '.join(unknown)}")


def _version(document: Mapping[str, Any], path: str) -> None:
    version = document.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        _fail(path, f"schema_version must be {SCHEMA_VERSION}")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
    return value


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(path, f"must be an integer >= {minimum}")
    return value


def _number(value: Any, path: str, *, minimum: float = 0) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be a number")
    if not math.isfinite(value) or value < minimum:
        _fail(path, f"must be finite and >= {minimum}")
    return value


def _sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(path, "must be a lowercase SHA-256 digest")
    return value


def _finding_id(value: Any, path: str, *, legacy: bool = False) -> str:
    pattern = _LEGACY_ID if legacy else _FINDING_ID
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail(path, "must be a finding identity")
    return value


def _repo_path(value: Any, path: str, *, allow_root: bool = True) -> str:
    text = _text(value, path)
    if "\\" in text:
        _fail(path, "must use POSIX separators")
    candidate = PurePosixPath(text)
    normalized = candidate.as_posix()
    if candidate.is_absolute() or normalized.startswith("../") or "/../" in normalized:
        _fail(path, "must remain inside the repository")
    if not allow_root and normalized == ".":
        _fail(path, "must identify a path below the repository root")
    if normalized != text:
        _fail(path, "must already be normalized")
    return text


def _sorted_unique_strings(
    value: Any,
    path: str,
    item_validator: Callable[[Any, str], str] = _text,
    *,
    nonempty: bool = False,
) -> list[str]:
    rows = _sequence(value, path)
    if nonempty and not rows:
        _fail(path, "must not be empty")
    validated = [item_validator(item, f"{path}[{index}]") for index, item in enumerate(rows)]
    if validated != sorted(set(validated)):
        _fail(path, "must be sorted and contain no duplicates")
    return validated


def validate_failure(document: Any) -> Mapping[str, Any]:
    failure = _mapping(document, "failure")
    _version(failure, "failure")
    _required(failure, ("kind", "provider", "message", "details"), "failure")
    if failure["kind"] not in FAILURE_KINDS:
        _fail("failure.kind", f"must be one of {sorted(FAILURE_KINDS)}")
    _text(failure["provider"], "failure.provider")
    _text(failure["message"], "failure.message")
    _mapping(failure["details"], "failure.details")
    return failure


def _validate_scope(
    document: Any,
    path: str,
    *,
    paths_nonempty: bool,
) -> Mapping[str, Any]:
    scope = _mapping(document, path)
    _required(scope, ("paths", "case_sensitive", "roots", "exclusions"), path)
    _sorted_unique_strings(
        scope["paths"],
        f"{path}.paths",
        lambda value, item_path: _repo_path(value, item_path),
        nonempty=paths_nonempty,
    )
    if not isinstance(scope["case_sensitive"], bool):
        _fail(f"{path}.case_sensitive", "must be a boolean")
    _sorted_unique_strings(
        scope["roots"],
        f"{path}.roots",
        lambda value, item_path: _repo_path(value, item_path),
        nonempty=True,
    )
    _sorted_unique_strings(
        scope["exclusions"],
        f"{path}.exclusions",
        lambda value, item_path: _repo_path(value, item_path),
    )
    return scope


def parser_command_binding(
    command_document: Any,
    *,
    provider: str,
    language: str,
    scope: Mapping[str, Any],
    run_context: ParserRunContext | None,
    path: str = "provider_observation.command",
) -> str:
    """Parse one exact parser-process argv and bind it to normalized provenance."""
    if run_context is None:
        _fail(path, "parser provider validation requires an external trusted run context")
    canonical_context = trusted_parser_run_context(run_context.workspace_root)
    if run_context != canonical_context:
        _fail(path, "parser run context must match the loaded canonical runtime identity")
    command = _mapping(command_document, path)
    argv = _sequence(command.get("argv"), f"{path}.argv")
    if len(argv) < 10 or not all(isinstance(argument, str) for argument in argv):
        _fail(f"{path}.argv", "must contain the canonical parser provider command")
    executable = _text(command.get("executable"), f"{path}.executable")
    if argv[0] != executable:
        _fail(f"{path}.argv[0]", "must exactly match command.executable")
    if executable != run_context.executable:
        _fail(f"{path}.executable", "must match the trusted parser executable")
    if argv[1] != run_context.provider_process_path:
        _fail(f"{path}.argv[1]", "must be the trusted canonical provider process path")

    cursor = 2

    def required_value(flag: str) -> str:
        nonlocal cursor
        if cursor + 1 >= len(argv) or argv[cursor] != flag:
            _fail(f"{path}.argv[{cursor}]", f"must be {flag}")
        value = argv[cursor + 1]
        if not value or value.startswith("--"):
            _fail(f"{path}.argv[{cursor + 1}]", f"must be the value for {flag}")
        cursor += 2
        return value

    command_provider = required_value("--provider")
    command_language = required_value("--language")
    project_root = required_value("--project-root")
    if command_provider != provider:
        _fail(f"{path}.argv", "provider flag must match provider_observation.provider")
    if command_language != language:
        _fail(f"{path}.argv", "language flag must match provider_observation.language")
    if command_provider not in _PARSER_PROVIDERS:
        _fail(f"{path}.argv", "parser provider flag is not recognized")
    if (command_provider, command_language) not in {
        ("cx", "python"),
        ("omnibus", "python"),
        ("omnibus", "typescript"),
    }:
        _fail(f"{path}.argv", "parser provider/language pair is not supported")
    if "\\" in project_root:
        _fail(f"{path}.argv", "project root must use POSIX separators")
    canonical_project_root = PurePosixPath(project_root)
    if (
        not canonical_project_root.is_absolute()
        or canonical_project_root.as_posix() != project_root
        or ".." in canonical_project_root.parts
    ):
        _fail(f"{path}.argv", "project root must be an absolute normalized path")
    if project_root != run_context.workspace_root:
        _fail(f"{path}.argv", "project root must match the trusted run workspace")

    values: dict[str, list[str]] = {"--path": [], "--root": [], "--exclude": []}
    order = {"--path": 0, "--root": 1, "--exclude": 2}
    last_order = 0
    case_sensitive: bool | None = None
    while cursor < len(argv):
        flag = argv[cursor]
        if flag == "--case-sensitive":
            if cursor != len(argv) - 2 or case_sensitive is not None:
                _fail(f"{path}.argv[{cursor}]", "case policy must be the single final flag")
            rendered = argv[cursor + 1]
            if rendered not in {"true", "false"}:
                _fail(f"{path}.argv[{cursor + 1}]", "case policy must be true or false")
            case_sensitive = rendered == "true"
            cursor += 2
            continue
        if flag not in values:
            _fail(f"{path}.argv[{cursor}]", "unknown or misplaced parser provider flag")
        if cursor + 1 >= len(argv):
            _fail(f"{path}.argv[{cursor}]", "flag requires a value")
        flag_order = order[flag]
        if flag_order < last_order:
            _fail(f"{path}.argv[{cursor}]", "parser provider flags are misordered")
        last_order = flag_order
        rendered = argv[cursor + 1]
        if not rendered or rendered.startswith("--"):
            _fail(f"{path}.argv[{cursor + 1}]", f"must be the value for {flag}")
        values[flag].append(rendered)
        cursor += 2
    if case_sensitive is None:
        _fail(f"{path}.argv", "missing final --case-sensitive flag")

    parsed_scope = {
        "paths": values["--path"],
        "case_sensitive": case_sensitive,
        "roots": values["--root"],
        "exclusions": values["--exclude"],
    }
    _validate_scope(parsed_scope, f"{path}.scope", paths_nonempty=False)
    if dict(parsed_scope) != dict(scope):
        _fail(f"{path}.argv", "parsed command scope must exactly match provider_observation.scope")
    if command.get("output_format") != "canonical-jsonl":
        _fail(f"{path}.output_format", "parser providers require canonical-jsonl")
    return canonical_sha256(
        {
            "provider": command_provider,
            "language": command_language,
            "project_root": project_root,
            "scope": parsed_scope,
            "command": dict(command),
            "run_context_sha256": run_context.identity_sha256,
        }
    )


def validate_provider_observation(
    document: Any,
    *,
    parser_run_context: ParserRunContext | None = None,
) -> Mapping[str, Any]:
    observation = _mapping(document, "provider_observation")
    _version(observation, "provider_observation")
    provider_kind = _text(
        observation.get("provider_kind"),
        "provider_observation.provider_kind",
    )
    fields = (
        "provider",
        "language",
        "provider_kind",
        "scope",
        "command",
        "tool_version",
        "exit",
        "raw",
        "status",
        "failure",
    )
    if provider_kind == _PARSER_PROVIDER_KIND:
        fields = (*fields, "completion")
    _required(
        observation,
        fields,
        "provider_observation",
    )
    provider = _text(observation["provider"], "provider_observation.provider")
    language = _text(observation["language"], "provider_observation.language")
    tool_version = _text(observation["tool_version"], "provider_observation.tool_version")
    if tool_version.startswith("analysis-v") and provider_kind != _PARSER_PROVIDER_KIND:
        _fail(
            "provider_observation.provider_kind",
            "analysis detector versions require the parser-backed observation contract",
        )

    command = _mapping(observation["command"], "provider_observation.command")
    _required(
        command,
        ("executable", "argv", "timeout_seconds", "output_format", "output_byte_limit"),
        "provider_observation.command",
    )
    _text(command["executable"], "provider_observation.command.executable")
    argv = _sequence(command["argv"], "provider_observation.command.argv")
    if not argv:
        _fail("provider_observation.command.argv", "must not be empty")
    for index, argument in enumerate(argv):
        if not isinstance(argument, str):
            _fail(f"provider_observation.command.argv[{index}]", "must be a string")
    _number(command["timeout_seconds"], "provider_observation.command.timeout_seconds", minimum=0.001)
    _text(command["output_format"], "provider_observation.command.output_format")
    byte_limit = _integer(
        command["output_byte_limit"],
        "provider_observation.command.output_byte_limit",
        minimum=1,
    )

    exit_state = _mapping(observation["exit"], "provider_observation.exit")
    _required(exit_state, ("code", "classification"), "provider_observation.exit")
    if type(exit_state["code"]) is not int:
        _fail("provider_observation.exit.code", "must be an integer process return code")
    if exit_state["classification"] not in EXIT_CLASSIFICATIONS:
        _fail("provider_observation.exit.classification", "is not recognized")

    status = observation["status"]
    if status not in PROVIDER_STATUSES:
        _fail("provider_observation.status", f"must be one of {sorted(PROVIDER_STATUSES)}")
    failure = observation["failure"]
    scope = _validate_scope(
        observation["scope"],
        "provider_observation.scope",
        paths_nonempty=status == "completed",
    )

    raw = _mapping(observation["raw"], "provider_observation.raw")
    _required(
        raw,
        ("stdout_sha256", "stderr_sha256", "stdout_bytes", "stderr_bytes"),
        "provider_observation.raw",
    )
    _sha256(raw["stdout_sha256"], "provider_observation.raw.stdout_sha256")
    _sha256(raw["stderr_sha256"], "provider_observation.raw.stderr_sha256")
    stdout_bytes = _integer(raw["stdout_bytes"], "provider_observation.raw.stdout_bytes")
    stderr_bytes = _integer(raw["stderr_bytes"], "provider_observation.raw.stderr_bytes")
    overflow_failure = (
        status == "failed"
        and isinstance(failure, Mapping)
        and failure.get("kind") == "output_overflow"
    )
    if stdout_bytes + stderr_bytes > byte_limit and not overflow_failure:
        _fail("provider_observation.raw", "artifact exceeds command output_byte_limit")

    if status == "completed":
        if failure is not None:
            _fail("provider_observation.failure", "completed observation must not carry a failure")
        if exit_state["classification"] == "tool_failure":
            _fail("provider_observation.exit", "completed observation cannot be a tool failure")
    else:
        validated_failure = validate_failure(failure)
        if validated_failure["provider"] != provider:
            _fail("provider_observation.failure.provider", "must match the observation provider")
        if exit_state["classification"] != "tool_failure":
            _fail("provider_observation.exit", "failed observation must be a tool failure")

    if provider_kind == _PARSER_PROVIDER_KIND:
        binding = parser_command_binding(
            command,
            provider=provider,
            language=language,
            scope=scope,
            run_context=parser_run_context,
        )
        completion = observation["completion"]
        if status == "failed":
            if completion is not None:
                _fail(
                    "provider_observation.completion",
                    "failed parser observation must not carry completion evidence",
                )
            return observation
        completed = _mapping(completion, "provider_observation.completion")
        _version(completed, "provider_observation.completion")
        _required(
            completed,
            (
                "schema_version",
                "type",
                "provider",
                "language",
                "finding_count",
                "stdout_sha256",
                "stdout_bytes",
                "stderr_sha256",
                "stderr_bytes",
                "provider_process_sha256",
                "run_context_sha256",
                "command_scope_sha256",
            ),
            "provider_observation.completion",
        )
        if completed["type"] != "provider_completion":
            _fail("provider_observation.completion.type", "must identify provider_completion")
        if completed["provider"] != provider:
            _fail("provider_observation.completion.provider", "must match the observation provider")
        if completed["language"] != language:
            _fail("provider_observation.completion.language", "must match the observation language")
        finding_count = _integer(
            completed["finding_count"],
            "provider_observation.completion.finding_count",
        )
        if completed["stdout_sha256"] != raw["stdout_sha256"]:
            _fail("provider_observation.completion.stdout_sha256", "must match captured stdout")
        if completed["stdout_bytes"] != raw["stdout_bytes"]:
            _fail("provider_observation.completion.stdout_bytes", "must match captured stdout")
        if completed["stderr_sha256"] != raw["stderr_sha256"]:
            _fail("provider_observation.completion.stderr_sha256", "must match captured stderr")
        if completed["stderr_bytes"] != raw["stderr_bytes"]:
            _fail("provider_observation.completion.stderr_bytes", "must match captured stderr")
        if completed["provider_process_sha256"] != parser_run_context.provider_process_sha256:
            _fail(
                "provider_observation.completion.provider_process_sha256",
                "must match the trusted canonical provider process content",
            )
        if completed["run_context_sha256"] != parser_run_context.identity_sha256:
            _fail(
                "provider_observation.completion.run_context_sha256",
                "must match the external trusted run context",
            )
        if raw["stdout_bytes"] == 0:
            _fail("provider_observation.raw.stdout_bytes", "completed parser stdout must not be empty")
        if raw["stderr_bytes"] != 0 or raw["stderr_sha256"] != _EMPTY_SHA256:
            _fail("provider_observation.raw", "completed parser observation must have empty stderr")
        if completed["command_scope_sha256"] != binding:
            _fail(
                "provider_observation.completion.command_scope_sha256",
                "must bind the exact parsed command and observation scope",
            )
        if exit_state["code"] != 0:
            _fail("provider_observation.exit.code", "completed parser process must exit zero")
        expected_classification = "diagnostics" if finding_count else "clean"
        if exit_state["classification"] != expected_classification:
            _fail(
                "provider_observation.exit.classification",
                "must agree with parser completion finding_count",
            )
    return observation


def _validate_finding(document: Any, path: str, *, case_sensitive: bool) -> Mapping[str, Any]:
    finding = _mapping(document, path)
    _required(
        finding,
        (
            "finding_id_schema",
            "id",
            "identity",
            "legacy_ids",
            "native_rule_id",
            "rule_semantic_key",
            "native_severity",
            "severity",
            "location",
            "message",
            "summary",
            "metrics",
            "provenance",
        ),
        path,
    )
    if finding["finding_id_schema"] != FINDING_ID_SCHEMA_VERSION:
        _fail(f"{path}.finding_id_schema", f"must be {FINDING_ID_SCHEMA_VERSION}")
    identifier = _finding_id(finding["id"], f"{path}.id")
    identity = _mapping(finding["identity"], f"{path}.identity")
    _required(
        identity,
        ("schema", "provider", "rule", "language", "path", "semantic_anchor", "occurrence"),
        f"{path}.identity",
    )
    if identity["schema"] != FINDING_ID_SCHEMA_VERSION:
        _fail(f"{path}.identity.schema", f"must be {FINDING_ID_SCHEMA_VERSION}")
    occurrence = _integer(identity["occurrence"], f"{path}.identity.occurrence")
    canonical_identity = FindingIdentity(
        provider=_text(identity["provider"], f"{path}.identity.provider"),
        rule=_text(identity["rule"], f"{path}.identity.rule"),
        language=_text(identity["language"], f"{path}.identity.language"),
        path=_repo_path(identity["path"], f"{path}.identity.path", allow_root=False),
        semantic_anchor=_text(identity["semantic_anchor"], f"{path}.identity.semantic_anchor"),
        occurrence=occurrence,
        case_sensitive=case_sensitive,
    )
    expected_payload = canonical_identity.canonical_payload()
    if dict(identity) != expected_payload:
        _fail(f"{path}.identity", "must contain the canonical ADR 0040 payload")
    expected = canonical_identity.identifier()
    if identifier != expected:
        _fail(f"{path}.id", "does not match the ADR 0040 identity payload")
    _sorted_unique_strings(
        finding["legacy_ids"],
        f"{path}.legacy_ids",
        lambda value, item_path: _finding_id(value, item_path, legacy=True),
    )
    _text(finding["native_rule_id"], f"{path}.native_rule_id")
    semantic_key = _text(finding["rule_semantic_key"], f"{path}.rule_semantic_key")
    if semantic_key != identity["rule"]:
        _fail(f"{path}.rule_semantic_key", "must match identity.rule")
    _text(finding["native_severity"], f"{path}.native_severity")
    severity = _integer(finding["severity"], f"{path}.severity", minimum=1)
    if severity > 3:
        _fail(f"{path}.severity", "must be <= 3")
    location = _mapping(finding["location"], f"{path}.location")
    _required(location, ("path", "line", "column", "end_line", "end_column"), f"{path}.location")
    if _repo_path(location["path"], f"{path}.location.path", allow_root=False) != identity["path"]:
        _fail(f"{path}.location.path", "must match identity.path")
    for name in ("line", "column", "end_line", "end_column"):
        if location[name] is not None:
            _integer(location[name], f"{path}.location.{name}", minimum=1)
    _text(finding["message"], f"{path}.message")
    _text(finding["summary"], f"{path}.summary")
    metrics = _mapping(finding["metrics"], f"{path}.metrics")
    for name, value in metrics.items():
        _text(name, f"{path}.metrics key")
        _number(value, f"{path}.metrics.{name}")
    provenance = _mapping(finding["provenance"], f"{path}.provenance")
    _required(provenance, ("provider", "observation_index"), f"{path}.provenance")
    if _text(provenance["provider"], f"{path}.provenance.provider") != identity["provider"]:
        _fail(f"{path}.provenance.provider", "must match identity.provider")
    _integer(provenance["observation_index"], f"{path}.provenance.observation_index")
    return finding


def _validate_prototype_manifest(document: Mapping[str, Any]) -> Mapping[str, Any]:
    _required(document, ("target", "scope", "counts", "total", "errors", "findings"), "manifest")
    _text(document["target"], "manifest.target")
    _sequence(document["scope"], "manifest.scope")
    counts = _mapping(document["counts"], "manifest.counts")
    for name, count in counts.items():
        _text(name, "manifest.counts key")
        _integer(count, f"manifest.counts.{name}")
    total = _integer(document["total"], "manifest.total")
    findings = _sequence(document["findings"], "manifest.findings")
    if total != len(findings) or total != sum(counts.values()):
        _fail("manifest.total", "must match findings and derived counts")
    _mapping(document["errors"], "manifest.errors")
    return document


def validate_manifest(
    document: Any,
    *,
    allow_prototype: bool = False,
    parser_run_context: ParserRunContext | None = None,
) -> Mapping[str, Any]:
    manifest = _mapping(document, "manifest")
    if "schema_version" not in manifest:
        if allow_prototype:
            return _validate_prototype_manifest(manifest)
        _fail("manifest.schema_version", "missing; prototype manifests require explicit migration mode")
    _version(manifest, "manifest")
    _required(
        manifest,
        (
            "finding_id_schema",
            "capability_registry_version",
            "scope",
            "source",
            "status",
            "providers",
            "findings",
            "counts",
            "total",
            "hashes",
        ),
        "manifest",
    )
    if manifest["finding_id_schema"] != FINDING_ID_SCHEMA_VERSION:
        _fail("manifest.finding_id_schema", f"must be {FINDING_ID_SCHEMA_VERSION}")
    _integer(manifest["capability_registry_version"], "manifest.capability_registry_version", minimum=1)

    scope = _validate_scope(manifest["scope"], "manifest.scope", paths_nonempty=True)

    source = _mapping(manifest["source"], "manifest.source")
    _required(source, ("revision", "dirty", "dirty_state_hash"), "manifest.source")
    _text(source["revision"], "manifest.source.revision")
    if not isinstance(source["dirty"], bool):
        _fail("manifest.source.dirty", "must be a boolean")
    _sha256(source["dirty_state_hash"], "manifest.source.dirty_state_hash")

    if manifest["status"] != "complete":
        _fail("manifest.status", "only a complete run may publish a sweep manifest")
    providers = _sequence(manifest["providers"], "manifest.providers")
    if not providers:
        _fail("manifest.providers", "publishable manifest must declare completed providers")
    validated_providers = [
        validate_provider_observation(row, parser_run_context=parser_run_context)
        for row in providers
    ]
    if any(row["status"] != "completed" for row in validated_providers):
        _fail("manifest.providers", "publishable manifest requires every provider to complete")
    provider_order = [(row["provider"], row["language"]) for row in validated_providers]
    if provider_order != sorted(set(provider_order)):
        _fail("manifest.providers", "must be sorted by provider/language with no duplicates")

    def within(path: str, boundary: str, *, case_sensitive: bool) -> bool:
        if not case_sensitive:
            path = path.casefold()
            boundary = boundary.casefold()
        return boundary == "." or path == boundary or path.startswith(f"{boundary}/")

    for index, observation in enumerate(validated_providers):
        observed_scope = observation["scope"]
        if observed_scope["case_sensitive"] != scope["case_sensitive"]:
            _fail(
                f"manifest.providers[{index}].scope.case_sensitive",
                "must match manifest scope case policy",
            )
    rows = _sequence(manifest["findings"], "manifest.findings")
    findings = [
        _validate_finding(row, f"manifest.findings[{index}]", case_sensitive=scope["case_sensitive"])
        for index, row in enumerate(rows)
    ]
    scope_paths = scope["paths"]
    roots = scope["roots"]
    exclusions = scope["exclusions"]

    for index, row in enumerate(findings):
        path = row["identity"]["path"]
        if not any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in scope_paths
        ) or not any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in roots
        ):
            _fail(
                f"manifest.findings[{index}].identity.path",
                "must remain inside the declared scope paths and roots",
            )
        if any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in exclusions
        ):
            _fail(
                f"manifest.findings[{index}].identity.path",
                "must not fall under a declared exclusion",
            )
        observation_index = row["provenance"]["observation_index"]
        if observation_index >= len(validated_providers):
            _fail(
                f"manifest.findings[{index}].provenance.observation_index",
                "must reference the canonical provider array",
            )
        observation = validated_providers[observation_index]
        expected = (row["identity"]["provider"], row["identity"]["language"])
        actual = (observation["provider"], observation["language"])
        if actual != expected:
            _fail(
                f"manifest.findings[{index}].provenance.observation_index",
                f"references provider/language {actual!r}, expected {expected!r}",
            )
        observed_scope = observation["scope"]
        if not any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in observed_scope["paths"]
        ) or not any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in observed_scope["roots"]
        ) or any(
            within(path, boundary, case_sensitive=scope["case_sensitive"])
            for boundary in observed_scope["exclusions"]
        ):
            _fail(
                f"manifest.findings[{index}].provenance.observation_index",
                "finding must remain inside its actual observation scope",
            )
    for index, observation in enumerate(validated_providers):
        observed_scope = observation["scope"]
        if dict(observed_scope) != dict(scope):
            _fail(
                f"manifest.providers[{index}].scope",
                "must exactly match manifest scope",
            )
        if observation["provider_kind"] == _PARSER_PROVIDER_KIND:
            observed_count = sum(
                row["provenance"]["observation_index"] == index for row in findings
            )
            if observation["completion"]["finding_count"] != observed_count:
                _fail(
                    f"manifest.providers[{index}].completion.finding_count",
                    "must match findings whose provenance references this observation",
                )
    identifiers = [row["id"] for row in findings]
    if len(identifiers) != len(set(identifiers)):
        _fail("manifest.findings", "duplicate finding id")
    current_ids = set(identifiers)
    alias_owners: dict[str, str] = {}
    for index, row in enumerate(findings):
        for alias in row["legacy_ids"]:
            if alias in current_ids:
                _fail(
                    f"manifest.findings[{index}].legacy_ids",
                    "legacy alias must not reference a current finding id",
                )
            previous_owner = alias_owners.get(alias)
            if previous_owner is not None:
                _fail(
                    f"manifest.findings[{index}].legacy_ids",
                    f"legacy alias {alias} is claimed by multiple findings",
                )
            alias_owners[alias] = row["id"]
    finding_order = [
        (
            row["identity"]["provider"],
            row["identity"]["language"],
            row["rule_semantic_key"],
            row["identity"]["path"],
            row["identity"]["semantic_anchor"],
            row["identity"]["occurrence"],
            row["id"],
        )
        for row in findings
    ]
    if finding_order != sorted(finding_order):
        _fail("manifest.findings", "must use canonical finding order")

    counts = _mapping(manifest["counts"], "manifest.counts")
    derived_counts = dict(sorted(Counter(row["identity"]["provider"] for row in findings).items()))
    if dict(counts) != derived_counts:
        _fail("manifest.counts", "must be derived from validated findings")
    if manifest["total"] != len(findings):
        _fail("manifest.total", "must match validated findings")
    hashes = _mapping(manifest["hashes"], "manifest.hashes")
    _required(hashes, ("semantic", "artifacts"), "manifest.hashes")
    _sha256(hashes["semantic"], "manifest.hashes.semantic")
    _sha256(hashes["artifacts"], "manifest.hashes.artifacts")
    return manifest


def validate_diff(document: Any) -> Mapping[str, Any]:
    diff = _mapping(document, "diff")
    _version(diff, "diff")
    _required(
        diff,
        (
            "before_manifest_hash",
            "after_manifest_hash",
            "fixed",
            "new",
            "persisting",
            "metric_changes",
            "accepts",
        ),
        "diff",
    )
    _sha256(diff["before_manifest_hash"], "diff.before_manifest_hash")
    _sha256(diff["after_manifest_hash"], "diff.after_manifest_hash")
    sets = {
        name: set(
            _sorted_unique_strings(
                diff[name], name, lambda value, path: _finding_id(value, path)
            )
        )
        for name in ("fixed", "new", "persisting")
    }
    if sets["fixed"] & sets["new"] or sets["fixed"] & sets["persisting"] or sets["new"] & sets["persisting"]:
        _fail("diff", "fixed/new/persisting sets must be disjoint")
    changes = _sequence(diff["metric_changes"], "diff.metric_changes")
    change_order: list[tuple[str, str]] = []
    for index, item in enumerate(changes):
        path = f"diff.metric_changes[{index}]"
        change = _mapping(item, path)
        _required(change, ("finding_id", "metric", "before", "after"), path)
        finding_id = _finding_id(change["finding_id"], f"{path}.finding_id")
        metric = _text(change["metric"], f"{path}.metric")
        _number(change["before"], f"{path}.before")
        _number(change["after"], f"{path}.after")
        if finding_id not in sets["persisting"]:
            _fail(f"{path}.finding_id", "metric changes require a persisting finding")
        change_order.append((finding_id, metric))
    if change_order != sorted(set(change_order)):
        _fail("diff.metric_changes", "must be sorted with no duplicate metric changes")
    accepts = _sequence(diff["accepts"], "diff.accepts")
    accept_order: list[str] = []
    for index, item in enumerate(accepts):
        path = f"diff.accepts[{index}]"
        accept = _mapping(item, path)
        _required(accept, ("finding_id", "reason", "operator", "revision", "timestamp"), path)
        accept_order.append(_finding_id(accept["finding_id"], f"{path}.finding_id"))
        for name in ("reason", "operator", "revision", "timestamp"):
            _text(accept[name], f"{path}.{name}")
    if accept_order != sorted(set(accept_order)):
        _fail("diff.accepts", "must be sorted by finding_id with no duplicates")
    return diff


def validate_judgment(document: Any) -> Mapping[str, Any]:
    judgment = _mapping(document, "judgment")
    _version(judgment, "judgment")
    _required(judgment, ("manifest_hash", "judge", "outcomes", "judgment_hash"), "judgment")
    _sha256(judgment["manifest_hash"], "judgment.manifest_hash")
    judge = _mapping(judgment["judge"], "judgment.judge")
    _required(judge, ("identity", "version"), "judgment.judge")
    _text(judge["identity"], "judgment.judge.identity")
    _text(judge["version"], "judgment.judge.version")
    outcomes = _sequence(judgment["outcomes"], "judgment.outcomes")
    order: list[str] = []
    for index, item in enumerate(outcomes):
        path = f"judgment.outcomes[{index}]"
        outcome = _mapping(item, path)
        _required(outcome, ("finding_id", "outcome", "reason", "evidence"), path)
        order.append(_finding_id(outcome["finding_id"], f"{path}.finding_id"))
        if outcome["outcome"] not in JUDGMENT_OUTCOMES:
            _fail(f"{path}.outcome", f"must be one of {sorted(JUDGMENT_OUTCOMES)}")
        _text(outcome["reason"], f"{path}.reason")
        _text(outcome["evidence"], f"{path}.evidence")
    if order != sorted(set(order)):
        _fail("judgment.outcomes", "must be sorted by finding_id with no duplicates")
    _sha256(judgment["judgment_hash"], "judgment.judgment_hash")
    return judgment


def packet_budget_ceiling(scope: Sequence[str]) -> int:
    """Return the deterministic AC-5.7 budget ceiling for normalized scope."""
    scope_bytes = sum(len(path.encode("utf-8")) for path in scope)
    return min(100_000, max(8_000, 8_000 + math.ceil(scope_bytes / 4)))


def validate_packet(document: Any) -> Mapping[str, Any]:
    packet = _mapping(document, "packet")
    _version(packet, "packet")
    _required(
        packet,
        (
            "finding_ids",
            "scope",
            "recipe",
            "verification",
            "expected_delta",
            "token_budget",
            "manifest_hash",
            "judgment_hash",
        ),
        "packet",
    )
    finding_ids = _sorted_unique_strings(
        packet["finding_ids"],
        "packet.finding_ids",
        lambda value, path: _finding_id(value, path),
        nonempty=True,
    )
    scope = _sorted_unique_strings(
        packet["scope"],
        "packet.scope",
        lambda value, path: _repo_path(value, path, allow_root=False),
        nonempty=True,
    )
    _text(packet["recipe"], "packet.recipe")
    _text(packet["verification"], "packet.verification")
    delta = _mapping(packet["expected_delta"], "packet.expected_delta")
    _required(delta, ("fixed", "allowed_new", "metrics"), "packet.expected_delta")
    fixed = _sorted_unique_strings(
        delta["fixed"],
        "packet.expected_delta.fixed",
        lambda value, path: _finding_id(value, path),
    )
    _sorted_unique_strings(
        delta["allowed_new"],
        "packet.expected_delta.allowed_new",
        lambda value, path: _finding_id(value, path),
    )
    if not set(fixed).issubset(finding_ids):
        _fail("packet.expected_delta.fixed", "must refer to packet finding_ids")
    metrics = _sequence(delta["metrics"], "packet.expected_delta.metrics")
    for index, item in enumerate(metrics):
        metric = _mapping(item, f"packet.expected_delta.metrics[{index}]")
        _required(metric, ("finding_id", "metric", "before", "after"), f"packet.expected_delta.metrics[{index}]")
        _finding_id(metric["finding_id"], f"packet.expected_delta.metrics[{index}].finding_id")
        _text(metric["metric"], f"packet.expected_delta.metrics[{index}].metric")
        _number(metric["before"], f"packet.expected_delta.metrics[{index}].before")
        _number(metric["after"], f"packet.expected_delta.metrics[{index}].after")
    budget = _integer(packet["token_budget"], "packet.token_budget", minimum=1)
    ceiling = packet_budget_ceiling(scope)
    if budget > ceiling:
        _fail("packet.token_budget", f"must not exceed deterministic ceiling {ceiling}")
    _sha256(packet["manifest_hash"], "packet.manifest_hash")
    _sha256(packet["judgment_hash"], "packet.judgment_hash")
    return packet
