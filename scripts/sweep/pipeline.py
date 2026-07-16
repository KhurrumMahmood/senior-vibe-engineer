"""Judgment, packet, and harness-owned verification gates for sweep findings."""
from __future__ import annotations

import copy
import hashlib
import json
import shlex
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .manifest import _validated_manifest, build_diff
from .native import _capture
from .schemas import (
    JUDGMENT_OUTCOMES,
    ParserRunContext,
    SCHEMA_VERSION,
    SchemaValidationError,
    trusted_parser_run_context,
    validate_judgment,
    validate_packet,
)
from .serialization import canonical_json_bytes, canonical_sha256


JUDGMENT_FINDING_LIMIT = 50
JUDGMENT_BYTE_LIMIT = 65_536
VERIFICATION_BYTE_LIMIT = 65_536
SCAN_BYTE_LIMIT = 4_194_304
VERIFICATION_TIMEOUT_SECONDS = 300
ORDINARY_PURPOSES = frozenset({"agent", "dashboard", "rank"})


class JudgmentGateError(ValueError):
    """A judgment is missing, stale, uncertain, failed, or otherwise unusable."""


class VerificationGateError(ValueError):
    """Harness-owned verification could not prove the packet outcome."""


@dataclass(frozen=True)
class HarnessScan:
    """A manifest plus harness-owned replay evidence for its fresh scan."""

    manifest: Mapping[str, Any]
    evidence: Mapping[str, Any]


def _parser_context_for_manifest(
    manifest: Mapping[str, Any],
    *,
    root: Path,
) -> ParserRunContext | None:
    """Require an external runtime identity only when parser providers are present."""
    providers = manifest.get("providers")
    if isinstance(providers, Sequence) and any(
        isinstance(row, Mapping)
        and row.get("provider_kind") == "parser-backed-ecosystem"
        for row in providers
    ):
        return trusted_parser_run_context(root)
    return None


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def _ordered_findings(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(
        manifest["findings"],
        key=lambda row: (
            -row["severity"],
            row["identity"]["provider"],
            row["rule_semantic_key"],
            row["identity"]["path"],
            row["identity"]["semantic_anchor"],
            row["id"],
        ),
    )


# spec:portable-batch-sweep::IM-9
def build_judgment_input(
    manifest: Mapping[str, Any],
    *,
    offset: int = 0,
    finding_limit: int = JUDGMENT_FINDING_LIMIT,
    byte_limit: int = JUDGMENT_BYTE_LIMIT,
    parser_run_context: ParserRunContext | None = None,
) -> dict[str, Any]:
    """Return one bounded classification batch; it is not an ordinary digest."""
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    if not 1 <= finding_limit <= JUDGMENT_FINDING_LIMIT:
        raise ValueError(f"finding_limit must be between 1 and {JUDGMENT_FINDING_LIMIT}")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    if not 1 <= byte_limit <= JUDGMENT_BYTE_LIMIT:
        raise ValueError(f"byte_limit must be between 1 and {JUDGMENT_BYTE_LIMIT}")
    ordered = _ordered_findings(document)
    if offset > len(ordered):
        raise ValueError(f"offset must not exceed finding count {len(ordered)}")
    selected = [
        {
            "finding_id": row["id"],
            "provider": row["identity"]["provider"],
            "rule": row["rule_semantic_key"],
            "path": row["location"]["path"],
            "severity": row["severity"],
            "summary": _clip(row["summary"], 320),
            "metrics": copy.deepcopy(dict(row["metrics"])),
        }
        for row in ordered[offset : offset + finding_limit]
    ]

    def document_for(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "judgment_input",
            "manifest_hash": document["hashes"]["semantic"],
            "offset": offset,
            "next_offset": offset + len(rows) if offset + len(rows) < len(ordered) else None,
            "total": len(ordered),
            "findings": list(rows),
            "omitted": len(ordered) - offset - len(rows),
        }

    result = document_for(selected)
    while selected and len(canonical_json_bytes(result)) > byte_limit:
        selected.pop()
        result = document_for(selected)
    if len(canonical_json_bytes(result)) > byte_limit:
        raise ValueError("byte_limit cannot hold the judgment input envelope")
    return result


def import_judgment_outcomes(
    manifest: Mapping[str, Any],
    outcomes: Sequence[Mapping[str, Any]],
    *,
    parser_run_context: ParserRunContext | None = None,
) -> list[dict[str, str]]:
    """Validate run-local outcomes without silently accepting foreign IDs."""
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    known = {row["id"] for row in document["findings"]}
    required = {"finding_id", "outcome", "reason", "evidence"}
    imported: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(outcomes):
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise JudgmentGateError(f"outcome[{index}] must contain exactly {sorted(required)}")
        if any(not isinstance(raw[name], str) or not raw[name].strip() for name in required):
            raise JudgmentGateError(f"outcome[{index}] fields must be non-empty strings")
        identifier = raw["finding_id"]
        if identifier not in known:
            raise JudgmentGateError(f"unknown finding in outcome[{index}]: {identifier}")
        if identifier in seen:
            raise JudgmentGateError(f"duplicate judgment outcome for {identifier}")
        if raw["outcome"] not in JUDGMENT_OUTCOMES:
            raise JudgmentGateError(f"unrecognized judgment outcome: {raw['outcome']}")
        imported.append({name: raw[name] for name in ("finding_id", "outcome", "reason", "evidence")})
        seen.add(identifier)
    return sorted(imported, key=lambda row: row["finding_id"])


def _judgment_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": document["schema_version"],
        "manifest_hash": document["manifest_hash"],
        "judge": copy.deepcopy(dict(document["judge"])),
        "outcomes": copy.deepcopy(list(document["outcomes"])),
    }


def build_judgment(
    manifest: Mapping[str, Any],
    *,
    judge_identity: str,
    judge_version: str,
    outcomes: Sequence[Mapping[str, Any]],
    parser_run_context: ParserRunContext | None = None,
) -> dict[str, Any]:
    """Build one content-addressed run-local judgment artifact."""
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "manifest_hash": document["hashes"]["semantic"],
        "judge": {"identity": judge_identity, "version": judge_version},
        "outcomes": import_judgment_outcomes(
            document,
            outcomes,
            parser_run_context=parser_run_context,
        ),
        "judgment_hash": "0" * 64,
    }
    result["judgment_hash"] = canonical_sha256(_judgment_projection(result))
    validate_judgment(result)
    return result


def _validated_judgment(
    manifest: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    require_complete: bool,
    parser_run_context: ParserRunContext | None = None,
) -> Mapping[str, Any]:
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    try:
        validated = validate_judgment(judgment)
    except (SchemaValidationError, KeyError, TypeError) as exc:
        raise JudgmentGateError(str(exc)) from exc
    expected_hash = canonical_sha256(_judgment_projection(validated))
    if validated["judgment_hash"] != expected_hash:
        raise JudgmentGateError("judgment hash does not bind its content")
    if validated["manifest_hash"] != document["hashes"]["semantic"]:
        raise JudgmentGateError("judgment is stale for the selected manifest")
    known = {row["id"] for row in document["findings"]}
    outcomes = {row["finding_id"]: row for row in validated["outcomes"]}
    unknown = sorted(set(outcomes) - known)
    if unknown:
        raise JudgmentGateError(f"judgment contains unknown finding IDs: {unknown}")
    if require_complete:
        missing = sorted(known - set(outcomes))
        if missing:
            raise JudgmentGateError(f"missing judgment outcomes for {missing}")
        blocked = sorted(
            (identifier, row["outcome"])
            for identifier, row in outcomes.items()
            if row["outcome"] in {"uncertain", "failed"}
        )
        if blocked:
            labels = ", ".join(f"{identifier}:{outcome}" for identifier, outcome in blocked)
            raise JudgmentGateError(f"judgment blocks ordinary consumption: {labels}")
    return validated


def _digest_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    return {name: copy.deepcopy(document[name]) for name in document if name != "digest_hash"}


def validate_judged_digest(document: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the closed judgment-gated artifact consumed by status/agents."""
    if not isinstance(document, Mapping):
        raise JudgmentGateError("judged digest must be an object")
    base = {
        "schema_version",
        "kind",
        "purpose",
        "manifest_hash",
        "judgment_hash",
        "total_actionable",
        "omitted_actionable",
        "counts",
        "severity_histogram",
        "outcomes",
        "finding_ids",
        "digest_hash",
    }
    allowed = base | ({"items"} if document.get("purpose") in {"agent", "rank"} else set())
    if set(document) != allowed:
        raise JudgmentGateError(
            f"judged digest fields mismatch: missing={sorted(allowed - set(document))}, "
            f"unknown={sorted(set(document) - allowed)}"
        )
    if document["schema_version"] != SCHEMA_VERSION or document["kind"] != "judged_digest":
        raise JudgmentGateError("judged digest schema/kind is unsupported")
    if document["purpose"] not in ORDINARY_PURPOSES:
        raise JudgmentGateError("judged digest purpose is unsupported")
    for name in ("manifest_hash", "judgment_hash", "digest_hash"):
        value = document[name]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise JudgmentGateError(f"judged digest {name} must be a SHA-256 digest")
    for name in ("total_actionable", "omitted_actionable"):
        if type(document[name]) is not int or document[name] < 0:
            raise JudgmentGateError(f"judged digest {name} must be a nonnegative integer")
    finding_ids = document["finding_ids"]
    if (
        not isinstance(finding_ids, list)
        or finding_ids != sorted(set(finding_ids))
        or len(finding_ids) > JUDGMENT_FINDING_LIMIT
        or any(
            not isinstance(value, str)
            or len(value) != 27
            or not value.startswith("f2_")
            or any(character not in "0123456789abcdef" for character in value[3:])
            for value in finding_ids
        )
    ):
        raise JudgmentGateError("judged digest finding_ids must be sorted unique v2 IDs")
    if document["omitted_actionable"] != document["total_actionable"] - len(finding_ids):
        raise JudgmentGateError("judged digest omitted_actionable is inconsistent")
    for name in ("counts", "severity_histogram", "outcomes"):
        values = document[name]
        if not isinstance(values, Mapping) or any(
            not isinstance(key, str) or type(value) is not int or value < 0
            for key, value in values.items()
        ):
            raise JudgmentGateError(f"judged digest {name} must be nonnegative counts")
    if sum(document["counts"].values()) != document["total_actionable"]:
        raise JudgmentGateError("judged digest provider counts do not match actionable total")
    if sum(document["severity_histogram"].values()) != document["total_actionable"]:
        raise JudgmentGateError("judged digest severity counts do not match actionable total")
    if set(document["outcomes"]) - {"actionable", "not_actionable"}:
        raise JudgmentGateError("ordinary digest contains blocked judgment outcomes")
    if document["outcomes"].get("actionable", 0) != document["total_actionable"]:
        raise JudgmentGateError("judged digest outcome counts do not match actionable total")
    if "items" in document:
        items = document["items"]
        required = {"finding_id", "provider", "rule", "path", "severity", "summary", "metrics"}
        if not isinstance(items, list) or len(items) != len(finding_ids):
            raise JudgmentGateError("judged digest items do not match finding IDs")
        for index, item in enumerate(items):
            if not isinstance(item, Mapping) or set(item) != required:
                raise JudgmentGateError(f"judged digest item[{index}] has invalid fields")
            if item["finding_id"] not in finding_ids:
                raise JudgmentGateError(f"judged digest item[{index}] has an unknown ID")
            for name in ("provider", "rule", "path", "summary"):
                if not isinstance(item[name], str) or not item[name]:
                    raise JudgmentGateError(
                        f"judged digest item[{index}].{name} must be non-empty text"
                    )
            if type(item["severity"]) is not int or not 0 <= item["severity"] <= 4:
                raise JudgmentGateError(
                    f"judged digest item[{index}].severity is invalid"
                )
            if not isinstance(item["metrics"], Mapping):
                raise JudgmentGateError(f"judged digest item[{index}].metrics is invalid")
        if {item["finding_id"] for item in items} != set(finding_ids):
            raise JudgmentGateError("judged digest item IDs do not match finding_ids")
    expected_hash = canonical_sha256(_digest_projection(document))
    if document["digest_hash"] != expected_hash:
        raise JudgmentGateError("judged digest hash does not bind its content")
    if len(canonical_json_bytes(document)) > JUDGMENT_BYTE_LIMIT:
        raise JudgmentGateError("judged digest exceeds the 64-KiB ceiling")
    return document


def render_judged_digest(
    manifest: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    purpose: str,
    finding_limit: int = JUDGMENT_FINDING_LIMIT,
    byte_limit: int = JUDGMENT_BYTE_LIMIT,
    parser_run_context: ParserRunContext | None = None,
) -> dict[str, Any]:
    """Render the only ordinary digest/ranking/dashboard input."""
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    if purpose not in ORDINARY_PURPOSES:
        raise ValueError(f"purpose must be one of {sorted(ORDINARY_PURPOSES)}")
    if not 1 <= finding_limit <= JUDGMENT_FINDING_LIMIT:
        raise ValueError(f"finding_limit must be between 1 and {JUDGMENT_FINDING_LIMIT}")
    if not 1 <= byte_limit <= JUDGMENT_BYTE_LIMIT:
        raise ValueError(f"byte_limit must be between 1 and {JUDGMENT_BYTE_LIMIT}")
    validated = _validated_judgment(
        document,
        judgment,
        require_complete=True,
        parser_run_context=parser_run_context,
    )
    outcomes = {row["finding_id"]: row for row in validated["outcomes"]}
    actionable = [row for row in _ordered_findings(document) if outcomes[row["id"]]["outcome"] == "actionable"]
    selected = actionable[:finding_limit]
    outcome_counts = dict(sorted(Counter(row["outcome"] for row in validated["outcomes"]).items()))

    def build(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "kind": "judged_digest",
            "purpose": purpose,
            "manifest_hash": document["hashes"]["semantic"],
            "judgment_hash": validated["judgment_hash"],
            "total_actionable": len(actionable),
            "omitted_actionable": len(actionable) - len(rows),
            "counts": dict(sorted(Counter(row["identity"]["provider"] for row in actionable).items())),
            "severity_histogram": dict(sorted(Counter(str(row["severity"]) for row in actionable).items())),
            "outcomes": outcome_counts,
            "finding_ids": sorted(row["id"] for row in rows),
            "digest_hash": "0" * 64,
        }
        if purpose in {"agent", "rank"}:
            result["items"] = [
                {
                    "finding_id": row["id"],
                    "provider": row["identity"]["provider"],
                    "rule": row["rule_semantic_key"],
                    "path": row["location"]["path"],
                    "severity": row["severity"],
                    "summary": _clip(row["summary"], 320),
                    "metrics": copy.deepcopy(dict(row["metrics"])),
                }
                for row in rows
            ]
        result["digest_hash"] = canonical_sha256(_digest_projection(result))
        return result

    result = build(selected)
    while selected and len(canonical_json_bytes(result)) > byte_limit:
        selected.pop()
        result = build(selected)
    if len(canonical_json_bytes(result)) > byte_limit:
        raise ValueError("byte_limit cannot hold the judged digest envelope")
    validate_judged_digest(result)
    return result


# spec:portable-batch-sweep::IM-10
def build_packet(
    manifest: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    finding_ids: Sequence[str],
    scope: Sequence[str],
    recipe: str,
    verification: str,
    expected_delta: Mapping[str, Any],
    token_budget: int,
    parser_run_context: ParserRunContext | None = None,
) -> dict[str, Any]:
    """Build a bounded packet only from fresh actionable judgments."""
    document = _validated_manifest(
        manifest,
        parser_run_context=parser_run_context,
    )
    validated = _validated_judgment(
        document,
        judgment,
        require_complete=True,
        parser_run_context=parser_run_context,
    )
    selected = sorted(set(finding_ids))
    if not selected:
        raise JudgmentGateError("packet requires at least one finding ID")
    if len(selected) != len(finding_ids):
        raise JudgmentGateError("packet finding IDs must not contain duplicates")
    outcome_by_id = {row["finding_id"]: row["outcome"] for row in validated["outcomes"]}
    finding_by_id = {row["id"]: row for row in document["findings"]}
    for identifier in selected:
        if identifier not in finding_by_id:
            raise JudgmentGateError(f"packet contains unknown finding ID {identifier}")
        if outcome_by_id[identifier] != "actionable":
            raise JudgmentGateError(f"packet finding {identifier} is not actionable")
    normalized_scope = sorted(set(scope))
    selected_paths = {finding_by_id[identifier]["location"]["path"] for identifier in selected}
    if not selected_paths.issubset(normalized_scope):
        missing = sorted(selected_paths - set(normalized_scope))
        raise SchemaValidationError("packet.scope", f"does not cover selected findings: {missing}")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "finding_ids": selected,
        "scope": normalized_scope,
        "recipe": recipe,
        "verification": verification,
        "expected_delta": copy.deepcopy(dict(expected_delta)),
        "token_budget": token_budget,
        "manifest_hash": document["hashes"]["semantic"],
        "judgment_hash": validated["judgment_hash"],
    }
    validate_packet(packet)
    return packet


def _normalize_changed_path(value: str) -> str:
    candidate = PurePosixPath(value)
    text = candidate.as_posix()
    if candidate.is_absolute() or text == "." or text.startswith("../") or "/../" in text:
        raise VerificationGateError(f"changed path is outside repository: {value}")
    return text


def run_verification_command(argv: Sequence[str], root: Path) -> dict[str, Any]:
    """Run one parsed command without a shell, with bounded output and timeout."""
    try:
        capture = _capture(
            argv,
            cwd=root,
            timeout_seconds=VERIFICATION_TIMEOUT_SECONDS,
            output_byte_limit=VERIFICATION_BYTE_LIMIT,
            env=None,
        )
    except OSError as exc:
        return {
            "argv": list(argv),
            "exit_code": 127,
            "fault": "spawn_failure",
            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "stderr_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
            "stdout_bytes": 0,
            "stderr_bytes": len(str(exc).encode()),
        }
    return {
        "argv": list(argv),
        "exit_code": capture.code,
        "fault": capture.fault,
        "stdout_sha256": hashlib.sha256(capture.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(capture.stderr).hexdigest(),
        "stdout_bytes": len(capture.stdout),
        "stderr_bytes": len(capture.stderr),
    }


def _parse_verification(command: str) -> tuple[str, ...]:
    if not isinstance(command, str) or not command.strip():
        raise VerificationGateError("verification command must be non-empty")
    try:
        argv = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        raise VerificationGateError(f"verification command cannot be parsed: {exc}") from exc
    if not argv:
        raise VerificationGateError("verification command has no argv")
    return argv


def run_scan_command(command: str, root: Path) -> HarnessScan:
    """Run a harness-selected scanner command and require one canonical manifest."""
    argv = _parse_verification(command)
    try:
        capture = _capture(
            argv,
            cwd=root,
            timeout_seconds=VERIFICATION_TIMEOUT_SECONDS,
            output_byte_limit=SCAN_BYTE_LIMIT,
            env=None,
        )
    except OSError as exc:
        raise VerificationGateError(f"harness scan could not start: {exc}") from exc
    if capture.code != 0 or capture.fault:
        raise VerificationGateError("harness scan command failed")
    try:
        raw = json.loads(capture.stdout)
        manifest = _validated_manifest(
            raw,
            parser_run_context=trusted_parser_run_context(root),
        )
    except (json.JSONDecodeError, UnicodeDecodeError, SchemaValidationError) as exc:
        raise VerificationGateError(f"harness scan emitted an invalid manifest: {exc}") from exc
    if capture.stdout != canonical_json_bytes(manifest):
        raise VerificationGateError("harness scan did not emit one canonical manifest")
    return HarnessScan(
        manifest=manifest,
        evidence={
            "argv": list(argv),
            "exit_code": capture.code,
            "stdout_sha256": hashlib.sha256(capture.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(capture.stderr).hexdigest(),
            "stdout_bytes": len(capture.stdout),
            "stderr_bytes": len(capture.stderr),
        },
    )


def read_changed_paths(root: Path) -> list[str]:
    """Derive changed paths from Git; executor-supplied scope claims are ignored."""
    commands = (
        ("git", "diff", "--name-only", "-z", "HEAD", "--"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    )
    paths: set[str] = set()
    for argv in commands:
        try:
            capture = _capture(
                argv,
                cwd=root,
                timeout_seconds=30,
                output_byte_limit=VERIFICATION_BYTE_LIMIT,
                env=None,
            )
        except OSError as exc:
            raise VerificationGateError(f"cannot inspect changed paths: {exc}") from exc
        if capture.code != 0 or capture.fault:
            raise VerificationGateError(
                f"cannot inspect changed paths: {' '.join(argv[:2])} failed"
            )
        try:
            values = capture.stdout.decode("utf-8").split("\0")
        except UnicodeDecodeError as exc:
            raise VerificationGateError("changed paths are not UTF-8") from exc
        paths.update(_normalize_changed_path(value) for value in values if value)
    return sorted(paths)


def _validated_execution_evidence(
    value: Mapping[str, Any], *, label: str, include_fault: bool
) -> dict[str, Any]:
    required = {
        "argv", "exit_code", "stdout_sha256", "stderr_sha256", "stdout_bytes", "stderr_bytes"
    }
    if include_fault:
        required.add("fault")
    if not isinstance(value, Mapping) or set(value) != required:
        raise VerificationGateError(f"{label} evidence has invalid fields")
    argv = value["argv"]
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise VerificationGateError(f"{label} evidence has invalid argv")
    if type(value["exit_code"]) is not int:
        raise VerificationGateError(f"{label} evidence omitted an integer exit_code")
    for name in ("stdout_sha256", "stderr_sha256"):
        digest = value[name]
        if not isinstance(digest, str) or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise VerificationGateError(f"{label} evidence has invalid {name}")
    for name in ("stdout_bytes", "stderr_bytes"):
        if type(value[name]) is not int or value[name] < 0:
            raise VerificationGateError(f"{label} evidence has invalid {name}")
    if include_fault and value["fault"] not in {None, "spawn_failure", "timeout", "output_overflow"}:
        raise VerificationGateError(f"{label} evidence has invalid fault")
    return dict(value)


# spec:portable-batch-sweep::IM-11
def verify_packet(
    packet: Mapping[str, Any],
    before_manifest: Mapping[str, Any],
    judgment: Mapping[str, Any],
    *,
    root: Path,
    scanner: Callable[[], HarnessScan],
    verification_runner: Callable[[Sequence[str], Path], Mapping[str, Any]] = run_verification_command,
    changed_path_reader: Callable[[Path], Sequence[str]] = read_changed_paths,
) -> dict[str, Any]:
    """Verify a packet through the harness-owned command/rescan/diff boundary."""
    parser_run_context = _parser_context_for_manifest(before_manifest, root=root)
    validated_packet = validate_packet(packet)
    before = _validated_manifest(
        before_manifest,
        parser_run_context=parser_run_context,
    )
    validated_judgment = _validated_judgment(
        before,
        judgment,
        require_complete=True,
        parser_run_context=parser_run_context,
    )
    if validated_packet["manifest_hash"] != before["hashes"]["semantic"]:
        raise VerificationGateError("packet manifest hash is stale")
    if validated_packet["judgment_hash"] != validated_judgment["judgment_hash"]:
        raise VerificationGateError("packet judgment hash is stale")
    outcomes = {row["finding_id"]: row["outcome"] for row in validated_judgment["outcomes"]}
    for identifier in validated_packet["finding_ids"]:
        if outcomes.get(identifier) != "actionable":
            raise JudgmentGateError(f"packet finding {identifier} is not actionable")

    try:
        observed_changed = changed_path_reader(root)
    except VerificationGateError:
        raise
    except Exception as exc:
        raise VerificationGateError(f"cannot inspect changed paths: {exc}") from exc
    normalized_changed = sorted({_normalize_changed_path(path) for path in observed_changed})
    out_of_scope = sorted(set(normalized_changed) - set(validated_packet["scope"]))
    if out_of_scope:
        raise VerificationGateError(f"changed paths outside packet scope: {out_of_scope}")

    argv = _parse_verification(validated_packet["verification"])
    verification = _validated_execution_evidence(
        verification_runner(argv, root), label="verification", include_fault=True
    )
    if verification["argv"] != list(argv):
        raise VerificationGateError("verification evidence argv does not match the packet")
    if verification["exit_code"] != 0 or verification.get("fault"):
        raise VerificationGateError("verification command failed")

    try:
        scan_result = scanner()
        if not isinstance(scan_result, HarnessScan):
            raise TypeError("scanner did not return HarnessScan")
        after = _validated_manifest(
            scan_result.manifest,
            parser_run_context=parser_run_context,
        )
        scan_evidence = _validated_execution_evidence(
            scan_result.evidence, label="scan", include_fault=False
        )
    except Exception as exc:
        raise VerificationGateError(f"harness rescan failed: {exc}") from exc
    if scan_evidence["exit_code"] != 0:
        raise VerificationGateError("harness rescan failed: scan evidence is not successful")
    canonical_after = canonical_json_bytes(after)
    if (
        scan_evidence["stdout_sha256"] != hashlib.sha256(canonical_after).hexdigest()
        or scan_evidence["stdout_bytes"] != len(canonical_after)
    ):
        raise VerificationGateError("harness rescan evidence does not bind the after manifest")
    try:
        final_changed = sorted(
            {_normalize_changed_path(path) for path in changed_path_reader(root)}
        )
    except VerificationGateError:
        raise
    except Exception as exc:
        raise VerificationGateError(f"cannot re-inspect changed paths: {exc}") from exc
    final_out_of_scope = sorted(set(final_changed) - set(validated_packet["scope"]))
    if final_out_of_scope:
        raise VerificationGateError(
            f"post-verification paths outside packet scope: {final_out_of_scope}"
        )

    diff = build_diff(
        before,
        after,
        parser_run_context=parser_run_context,
    )
    expected = validated_packet["expected_delta"]
    if diff["fixed"] != expected["fixed"]:
        raise VerificationGateError(
            f"expected fixed {expected['fixed']}, observed {diff['fixed']}"
        )
    unexpected_new = sorted(set(diff["new"]) - set(expected["allowed_new"]))
    if unexpected_new:
        raise VerificationGateError(f"unexpected new findings: {unexpected_new}")
    after_by_id = {row["id"]: row for row in after["findings"]}
    new_paths = {
        after_by_id[identifier]["location"]["path"]
        for identifier in diff["new"]
        if identifier in after_by_id
    }
    if not new_paths.issubset(set(validated_packet["scope"])):
        raise VerificationGateError(
            f"new findings outside packet scope: {sorted(new_paths - set(validated_packet['scope']))}"
        )
    if diff["metric_changes"] != expected["metrics"]:
        raise VerificationGateError(
            f"expected metric delta {expected['metrics']}, observed {diff['metric_changes']}"
        )

    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "verdict": "verified",
        "before_manifest_hash": before["hashes"]["semantic"],
        "after_manifest_hash": after["hashes"]["semantic"],
        "judgment_hash": validated_judgment["judgment_hash"],
        "packet_hash": canonical_sha256(validated_packet),
        "changed_paths": final_changed,
        "pre_verification_changed_paths": normalized_changed,
        "verification": verification,
        "scan": scan_evidence,
        "diff": diff,
        "evidence_hash": "0" * 64,
    }
    evidence["evidence_hash"] = canonical_sha256(
        {name: value for name, value in evidence.items() if name != "evidence_hash"}
    )
    return evidence
