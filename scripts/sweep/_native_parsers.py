"""Strict native-output adapters for the registry-declared sweep providers."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from _lib.finding_identity import normalize_repo_path

from .manifest import FindingInput


class NativeOutputError(ValueError):
    """A typed parse, completion, or provider-schema rejection."""

    def __init__(self, kind: str, message: str, details: Mapping[str, object] | None = None):
        self.kind = kind
        self.details = dict(details or {})
        super().__init__(message)


class NativeContract(Protocol):
    provider: str
    language: str
    output_format: str
    semantic_rule_version: int


def _schema(message: str, **details: object) -> NativeOutputError:
    return NativeOutputError("schema_mismatch", message, details)


def _parse_json(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        stripped = text.rstrip()
        kind = "truncated_output" if exc.pos >= max(0, len(stripped) - 1) else "parse_failure"
        raise NativeOutputError(
            kind,
            f"native JSON is not complete and valid: {exc.msg}",
            {"line": exc.lineno, "column": exc.colno, "offset": exc.pos},
        ) from exc


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise _schema(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise _schema(f"{label} must be an array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _schema(f"{label} must be a non-empty string")
    return value


def _positive_int(value: object, label: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if type(value) is not int or value < 1:
        raise _schema(f"{label} must be a positive integer")
    return value


def _path(value: object, *, root: Path, label: str) -> str:
    text = _text(value, label)
    try:
        return normalize_repo_path(text, repo_root=root)
    except ValueError as exc:
        raise _schema(f"{label} is outside the scanned root", value=text) from exc


def _anchor(native_rule_id: str, message: str) -> str:
    return f"native:{native_rule_id}:{' '.join(message.split())}"


def _finding(
    contract: NativeContract,
    *,
    root: Path,
    path: object,
    native_rule_id: str,
    native_severity: str,
    severity: int,
    message: str,
    observation_index: int,
    line: int | None,
    column: int | None,
    end_line: int | None = None,
    end_column: int | None = None,
) -> FindingInput:
    normalized_path = _path(path, root=root, label="diagnostic path")
    return FindingInput(
        provider=contract.provider,
        language=contract.language,
        native_rule_id=native_rule_id,
        rule_semantic_key=(
            f"{contract.provider}:{native_rule_id}:v{contract.semantic_rule_version}"
        ),
        path=normalized_path,
        semantic_anchor=_anchor(native_rule_id, message),
        native_severity=native_severity,
        severity=severity,
        message=message,
        summary=message,
        metrics={},
        observation_index=observation_index,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
    )


def _parse_ruff(
    contract: NativeContract, text: str, root: Path, observation_index: int
) -> tuple[FindingInput, ...]:
    rows = _array(_parse_json(text), "Ruff output")
    findings: list[FindingInput] = []
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"Ruff diagnostic {index}")
        location = _mapping(row.get("location"), f"Ruff diagnostic {index}.location")
        end = _mapping(row.get("end_location"), f"Ruff diagnostic {index}.end_location")
        native_rule = _text(row.get("code"), f"Ruff diagnostic {index}.code")
        message = _text(row.get("message"), f"Ruff diagnostic {index}.message")
        findings.append(
            _finding(
                contract,
                root=root,
                path=row.get("filename"),
                native_rule_id=native_rule,
                native_severity="diagnostic",
                severity=2,
                message=message,
                observation_index=observation_index,
                line=_positive_int(location.get("row"), "Ruff location.row"),
                column=_positive_int(location.get("column"), "Ruff location.column"),
                end_line=_positive_int(end.get("row"), "Ruff end_location.row"),
                end_column=_positive_int(end.get("column"), "Ruff end_location.column"),
            )
        )
    return tuple(findings)


def _parse_eslint(
    contract: NativeContract, text: str, root: Path, observation_index: int
) -> tuple[FindingInput, ...]:
    files = _array(_parse_json(text), "ESLint output")
    findings: list[FindingInput] = []
    for file_index, raw_file in enumerate(files):
        file_row = _mapping(raw_file, f"ESLint file {file_index}")
        path = file_row.get("filePath")
        messages = _array(file_row.get("messages"), f"ESLint file {file_index}.messages")
        for message_index, raw_message in enumerate(messages):
            row = _mapping(raw_message, f"ESLint message {file_index}:{message_index}")
            severity = row.get("severity")
            if type(severity) is not int or severity not in {1, 2}:
                raise _schema("ESLint message severity must be 1 or 2")
            native_rule = row.get("ruleId")
            if native_rule is None and row.get("fatal") is True:
                native_rule = "eslint:parsing-error"
            native_rule = _text(native_rule, "ESLint message.ruleId")
            message = _text(row.get("message"), "ESLint message.message")
            findings.append(
                _finding(
                    contract,
                    root=root,
                    path=path,
                    native_rule_id=native_rule,
                    native_severity=str(severity),
                    severity=severity + 1,
                    message=message,
                    observation_index=observation_index,
                    line=_positive_int(row.get("line"), "ESLint message.line"),
                    column=_positive_int(row.get("column"), "ESLint message.column"),
                    end_line=_positive_int(
                        row.get("endLine"), "ESLint message.endLine", optional=True
                    ),
                    end_column=_positive_int(
                        row.get("endColumn"), "ESLint message.endColumn", optional=True
                    ),
                )
            )
    return tuple(findings)


_TSC_DIAGNOSTIC = re.compile(
    r"^(?P<path>.+)\((?P<line>[1-9][0-9]*),(?P<column>[1-9][0-9]*)\): "
    r"(?P<severity>error|warning) TS(?P<code>[0-9]+): (?P<message>.+)$"
)


def _parse_typescript(
    contract: NativeContract, text: str, root: Path, observation_index: int
) -> tuple[FindingInput, ...]:
    findings: list[FindingInput] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        match = _TSC_DIAGNOSTIC.fullmatch(line)
        if match is None:
            raise _schema("TypeScript diagnostic line has an unknown shape", line=index + 1)
        severity = match.group("severity")
        message = match.group("message")
        findings.append(
            _finding(
                contract,
                root=root,
                path=match.group("path"),
                native_rule_id=f"TS{match.group('code')}",
                native_severity=severity,
                severity=3 if severity == "error" else 2,
                message=message,
                observation_index=observation_index,
                line=int(match.group("line")),
                column=int(match.group("column")),
            )
        )
    return tuple(findings)


_CARGO_REASONS = frozenset(
    {"compiler-artifact", "compiler-message", "build-script-executed", "build-finished"}
)


def _parse_json_lines(text: str) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            kind = "truncated_output" if index == len(text.splitlines()) - 1 else "parse_failure"
            raise NativeOutputError(
                kind,
                f"native JSON line {index + 1} is not complete and valid: {exc.msg}",
                {"line": index + 1, "column": exc.colno},
            ) from exc
        rows.append(_mapping(value, f"native JSON line {index + 1}"))
    return rows


def _parse_clippy(
    contract: NativeContract, text: str, root: Path, observation_index: int
) -> tuple[FindingInput, ...]:
    rows = _parse_json_lines(text)
    completed = False
    findings: list[FindingInput] = []
    for index, row in enumerate(rows):
        reason = _text(row.get("reason"), f"Cargo row {index}.reason")
        if reason not in _CARGO_REASONS:
            raise _schema("Cargo JSON row has an unknown reason", reason=reason)
        if reason == "build-finished":
            if row.get("success") is not True:
                raise _schema("Cargo build-finished sentinel must report success")
            completed = True
            continue
        if reason != "compiler-message":
            continue
        message_row = _mapping(row.get("message"), f"Cargo row {index}.message")
        code_row = message_row.get("code")
        if code_row is None:
            continue
        native_rule = _text(
            _mapping(code_row, f"Cargo row {index}.message.code").get("code"),
            f"Cargo row {index}.message.code.code",
        )
        if not native_rule.startswith("clippy::"):
            continue
        spans = _array(message_row.get("spans"), f"Cargo row {index}.message.spans")
        span_rows = [_mapping(span, f"Cargo row {index}.message.spans") for span in spans]
        primary = next((span for span in span_rows if span.get("is_primary") is True), None)
        if primary is None:
            raise _schema("Clippy diagnostic requires a primary span")
        level = _text(message_row.get("level"), f"Cargo row {index}.message.level")
        severity = {"failure-note": 1, "note": 1, "help": 1, "warning": 2, "error": 3}.get(
            level
        )
        if severity is None:
            raise _schema("Clippy diagnostic has an unknown native severity", level=level)
        message = _text(message_row.get("message"), f"Cargo row {index}.message.message")
        findings.append(
            _finding(
                contract,
                root=root,
                path=primary.get("file_name"),
                native_rule_id=native_rule,
                native_severity=level,
                severity=severity,
                message=message,
                observation_index=observation_index,
                line=_positive_int(primary.get("line_start"), "Clippy span.line_start"),
                column=_positive_int(primary.get("column_start"), "Clippy span.column_start"),
                end_line=_positive_int(primary.get("line_end"), "Clippy span.line_end"),
                end_column=_positive_int(primary.get("column_end"), "Clippy span.column_end"),
            )
        )
    if not completed:
        raise NativeOutputError(
            "missing_completion",
            "Cargo JSON output lacks a successful build-finished sentinel",
        )
    return tuple(findings)


_GO_POSITION = re.compile(r"^(?P<path>.+):(?P<line>[1-9][0-9]*):(?P<column>[1-9][0-9]*)$")


def _parse_go_vet(
    contract: NativeContract, text: str, root: Path, observation_index: int
) -> tuple[FindingInput, ...]:
    json_start = text.find("{")
    if json_start > 0:
        preamble = text[:json_start]
        if any(
            line and not line.startswith("# ")
            for line in preamble.splitlines()
        ):
            raise _schema("Go vet output has an unknown driver preamble")
        text = text[json_start:]
    packages = _mapping(_parse_json(text), "Go vet output")
    findings: list[FindingInput] = []
    for package, raw_analyzers in sorted(packages.items()):
        analyzers = _mapping(raw_analyzers, f"Go vet package {package}")
        for analyzer, raw_diagnostics in sorted(analyzers.items()):
            native_rule = _text(analyzer, f"Go vet package {package} analyzer")
            diagnostics = _array(
                raw_diagnostics, f"Go vet package {package}.{native_rule} diagnostics"
            )
            for index, raw_diagnostic in enumerate(diagnostics):
                row = _mapping(raw_diagnostic, f"Go vet diagnostic {package}:{native_rule}:{index}")
                position = _text(row.get("posn"), "Go vet diagnostic.posn")
                match = _GO_POSITION.fullmatch(position)
                if match is None:
                    raise _schema("Go vet diagnostic position has an unknown shape", posn=position)
                message = _text(row.get("message"), "Go vet diagnostic.message")
                findings.append(
                    _finding(
                        contract,
                        root=root,
                        path=match.group("path"),
                        native_rule_id=native_rule,
                        native_severity="diagnostic",
                        severity=2,
                        message=message,
                        observation_index=observation_index,
                        line=int(match.group("line")),
                        column=int(match.group("column")),
                    )
                )
    return tuple(findings)


_PARSERS = {
    "ruff-json": _parse_ruff,
    "eslint-json": _parse_eslint,
    "typescript-diagnostics-text": _parse_typescript,
    "cargo-json-lines": _parse_clippy,
    "go-vet-json": _parse_go_vet,
}


def parse_native_output(
    contract: NativeContract,
    *,
    text: str,
    root: Path,
    observation_index: int,
) -> tuple[FindingInput, ...]:
    """Parse a complete decoded payload with the registry-selected adapter."""
    parser = _PARSERS.get(contract.output_format)
    if parser is None:
        raise _schema("registry selected an unknown native output format", format=contract.output_format)
    return parser(contract, text, root, observation_index)
