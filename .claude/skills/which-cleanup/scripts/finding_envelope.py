"""Normalize producer findings and apply one declared scan-scope adapter."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from scope_modes import adapter_kind, recommendation_scan


COMPLETENESS = {"complete", "partial", "unsupported", "failed"}


class FindingEnvelopeError(ValueError):
    """A producer finding cannot be represented safely by the shared contract."""


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FindingEnvelopeError(f"{field} must be a non-empty string")
    return value.strip()


def _line(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise FindingEnvelopeError(f"{field} must be a positive integer or null")
    return value


def _relative_path(value: object) -> str | None:
    if value is None:
        return None
    path = _nonempty_string(value, "path")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise FindingEnvelopeError("path must be project-relative")
    return parsed.as_posix()


def normalize_finding(detector: str, raw: object) -> dict[str, Any]:
    """Return one namespaced, JSON-safe finding without discarding producer detail."""
    if not isinstance(raw, dict):
        raise FindingEnvelopeError("finding must be an object")
    kind = _nonempty_string(raw.get("kind"), "kind")
    subject = _nonempty_string(raw.get("subject"), "subject")
    path = _relative_path(raw.get("path"))
    line_start = _line(raw.get("line_start"), "line_start")
    line_end = _line(raw.get("line_end"), "line_end")
    if line_start is None and line_end is not None:
        raise FindingEnvelopeError("line_end requires line_start")
    if line_start is not None and line_end is None:
        line_end = line_start
    if line_start is not None and line_end is not None and line_end < line_start:
        raise FindingEnvelopeError("line_end cannot precede line_start")
    evidence = raw.get("evidence")
    detail = raw.get("detail", {})
    if not isinstance(evidence, dict):
        raise FindingEnvelopeError("evidence must be an object")
    if not isinstance(detail, dict):
        raise FindingEnvelopeError("detail must be an object")
    completeness = raw.get("completeness")
    if completeness not in COMPLETENESS:
        raise FindingEnvelopeError("completeness has an unsupported value")
    return {
        "kind": f"{detector}:{kind}",
        "subject": subject,
        "path": path,
        "line_start": line_start,
        "line_end": line_end,
        "evidence": evidence,
        "completeness": completeness,
        "detail": detail,
    }


def _request_payload(request) -> dict[str, Any]:
    try:
        payload = request.to_dict()
    except AttributeError as exc:
        raise FindingEnvelopeError("request must implement to_dict") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FindingEnvelopeError("request has an unsupported schema")
    return payload


def _ranges_by_path(request: dict[str, Any]) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    try:
        for change in request["changes"]:
            ranges[change["path"]] = [
                (item["start"], item["end"]) for item in change["line_ranges"]
            ]
    except (KeyError, TypeError) as exc:
        raise FindingEnvelopeError("request change ranges are invalid") from exc
    return ranges


def _apply_line_filter(
    findings: list[dict[str, Any]], request: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    ranges = _ranges_by_path(request)
    kept = []
    filtered_count = 0
    for finding in findings:
        path = finding["path"]
        start = finding["line_start"]
        end = finding["line_end"]
        if path is None or start is None or end is None:
            kept.append({**finding, "scope_attribution": "unlocated-review-required"})
            continue
        if any(
            changed_start <= end and changed_end >= start
            for changed_start, changed_end in ranges.get(path, [])
        ):
            kept.append({**finding, "scope_attribution": "changed-line"})
        else:
            filtered_count += 1
    return kept, filtered_count


def build_finding_artifact(
    *,
    detector: str,
    detector_version: str,
    raw_findings: list[object],
    request,
    contract: dict[str, Any],
    supported_modes_field: str = "current_modes",
    allow_compatible_widening: bool = True,
) -> dict[str, Any]:
    """Build one complete scope artifact from an already-computed finding set."""
    detector = _nonempty_string(detector, "detector")
    detector_version = _nonempty_string(detector_version, "detector_version")
    if contract.get("skill") != detector:
        raise FindingEnvelopeError("detector does not match the scope contract")
    if not isinstance(raw_findings, list):
        raise FindingEnvelopeError("raw_findings must be a list")
    request_payload = _request_payload(request)
    normalized = [normalize_finding(detector, raw) for raw in raw_findings]
    scan = recommendation_scan(
        request,
        contract,
        supported_modes_field=supported_modes_field,
        allow_compatible_widening=allow_compatible_widening,
    )
    if scan["effective_mode"] is None:
        findings: list[dict[str, Any]] = []
        filtered_count = 0
        refusal_count = 1
    elif scan["effective_mode"] == "diff-lines":
        findings, filtered_count = _apply_line_filter(normalized, request_payload)
        refusal_count = 0
    else:
        findings = [
            {**finding, "scope_attribution": scan["effective_mode"]}
            for finding in normalized
        ]
        filtered_count = 0
        refusal_count = 0
    incomplete_count = sum(
        finding["completeness"] != "complete"
        or finding["scope_attribution"] == "unlocated-review-required"
        for finding in findings
    ) + refusal_count
    error_count = sum(
        finding["completeness"] == "failed" for finding in findings
    )
    return {
        "schema_version": 1,
        "detector": detector,
        "detector_version": detector_version,
        "contract": {
            "finding_granularity": contract["finding_granularity"],
            "diff_semantics": contract["diff_semantics"],
            "behavior_family": contract["behavior_family"],
            "adapter": adapter_kind(contract),
        },
        "scan_request": request_payload,
        "scan": scan,
        "findings": findings,
        "metrics": {
            "raw_finding_count": len(normalized),
            "actionable_finding_count": len(findings),
            "scope_filtered_count": filtered_count,
            "incomplete_or_error_count": incomplete_count,
            "error_count": error_count,
        },
    }
