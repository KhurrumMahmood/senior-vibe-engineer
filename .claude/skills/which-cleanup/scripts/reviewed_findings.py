#!/usr/bin/env python3
"""Remember reviewed findings without hiding changed or invalid evidence.

The committed ledger contains human decisions, not raw scanner output.  Raw
findings stay in their producer artifacts; decision events retain only stable
identity, location, and a SHA-256 fingerprint of the bounded evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
FINGERPRINT_VERSION = 1
RECORD_KIND = "finding-decision-event"
DISPOSITIONS = {
    "false-positive",
    "accepted-debt",
    "intentional-exception",
    "fixed",
    "superseded",
    "withdrawn",
    "review-due",
}
SUPPRESSING_DISPOSITIONS = {
    "false-positive",
    "accepted-debt",
    "intentional-exception",
}
TERMINATING_DISPOSITIONS = {"superseded", "withdrawn"}
INITIAL_DISPOSITIONS = DISPOSITIONS - TERMINATING_DISPOSITIONS
HEX_256 = re.compile(r"^[0-9a-f]{64}$")
MAX_LENGTHS = {
    "event_id": 128,
    "detector": 128,
    "detector_version": 128,
    "kind": 256,
    "subject": 1000,
    "path": 1000,
    "disposition": 32,
    "rationale": 2000,
    "reviewer": 320,
    "source_scan": 512,
    "recorded_at": 64,
    "review_trigger": 500,
}


class DecisionMemoryError(ValueError):
    """Decision memory input is invalid or unsafe to append."""


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionMemoryError(f"{field} must be a non-empty string")
    return value.strip()


def _canonical_json(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise DecisionMemoryError("finding evidence must be finite JSON data") from exc
    return encoded.encode("utf-8")


def evidence_fingerprint(finding: dict[str, Any]) -> str:
    """Hash the exact portable evidence/context without retaining its contents."""
    payload = {
        "evidence": finding.get("evidence"),
        "line_end": finding.get("line_end"),
        "line_start": finding.get("line_start"),
        "path": finding.get("path"),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _identity(detector: str, kind: str, subject: str) -> tuple[str, str, str]:
    return detector, kind, subject


def _location_identity(
    detector: str, event_or_finding: dict[str, Any]
) -> tuple[object, ...]:
    return (
        detector,
        event_or_finding.get("kind"),
        event_or_finding.get("path"),
        event_or_finding.get("line_start"),
        event_or_finding.get("line_end"),
    )


def _parse_time(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_event_shape(event: object, line_number: int) -> list[str]:
    prefix = f"line {line_number}"
    if not isinstance(event, dict):
        return [f"{prefix}: event must be an object"]
    errors: list[str] = []
    required_strings = (
        "event_id",
        "detector",
        "detector_version",
        "kind",
        "subject",
        "disposition",
        "rationale",
        "reviewer",
        "source_scan",
        "recorded_at",
    )
    if event.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{prefix}: unsupported schema_version")
    if event.get("record_kind") != RECORD_KIND:
        errors.append(f"{prefix}: unsupported record_kind")
    for field in required_strings:
        if not isinstance(event.get(field), str) or not event[field].strip():
            errors.append(f"{prefix}: {field} must be a non-empty string")
        elif len(event[field]) > MAX_LENGTHS[field]:
            errors.append(f"{prefix}: {field} exceeds the bounded decision schema")
    detector = event.get("detector")
    kind = event.get("kind")
    if isinstance(detector, str) and isinstance(kind, str) and not kind.startswith(
        f"{detector}:"
    ):
        errors.append(f"{prefix}: kind must be namespaced by detector")
    disposition = event.get("disposition")
    if disposition not in DISPOSITIONS:
        errors.append(f"{prefix}: unsupported disposition")
    fingerprint = event.get("evidence_fingerprint")
    if not isinstance(fingerprint, str) or not HEX_256.fullmatch(fingerprint):
        errors.append(f"{prefix}: evidence_fingerprint must be lowercase SHA-256")
    fingerprint_version = event.get("fingerprint_version")
    if (
        isinstance(fingerprint_version, bool)
        or not isinstance(fingerprint_version, int)
        or fingerprint_version < 1
    ):
        errors.append(f"{prefix}: fingerprint_version must be a positive integer")
    if not _parse_time(event.get("recorded_at")):
        errors.append(f"{prefix}: recorded_at must be ISO-8601")
    path = event.get("path")
    if path is not None and (not isinstance(path, str) or not path):
        errors.append(f"{prefix}: path must be a string or null")
    elif isinstance(path, str):
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts or len(path) > MAX_LENGTHS["path"]:
            errors.append(f"{prefix}: path must be a bounded project-relative path")
    for field in ("line_start", "line_end"):
        value = event.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 1
        ):
            errors.append(f"{prefix}: {field} must be a positive integer or null")
    start, end = event.get("line_start"), event.get("line_end")
    if start is None and end is not None:
        errors.append(f"{prefix}: line_end requires line_start")
    if isinstance(start, int) and isinstance(end, int) and end < start:
        errors.append(f"{prefix}: line_end cannot precede line_start")
    target = event.get("target_event_id")
    if disposition in TERMINATING_DISPOSITIONS:
        if not isinstance(target, str) or not target:
            errors.append(f"{prefix}: terminating disposition requires target_event_id")
    elif target is not None:
        errors.append(f"{prefix}: target_event_id is only valid for terminating events")
    trigger = event.get("review_trigger")
    if trigger is not None and (not isinstance(trigger, str) or not trigger.strip()):
        errors.append(f"{prefix}: review_trigger must be a non-empty string or null")
    elif isinstance(trigger, str) and len(trigger) > MAX_LENGTHS["review_trigger"]:
        errors.append(f"{prefix}: review_trigger exceeds the bounded decision schema")
    forbidden = {"evidence", "detail", "source", "original_finding", "code"}
    copied = sorted(forbidden.intersection(event))
    if copied:
        errors.append(f"{prefix}: decision event copies raw fields: {', '.join(copied)}")
    return errors


def validate_events(events: Iterable[object]) -> dict[str, Any]:
    """Validate schema, unique IDs, and append-only state transitions."""
    event_list = list(events)
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    active: dict[tuple[str, str, str], dict[str, Any]] = {}
    ended: set[str] = set()

    for line_number, event in enumerate(event_list, start=1):
        shape_errors = _validate_event_shape(event, line_number)
        errors.extend(shape_errors)
        if shape_errors or not isinstance(event, dict):
            continue
        event_id = event["event_id"]
        if event_id in by_id:
            errors.append(f"line {line_number}: duplicate event_id {event_id}")
            continue
        by_id[event_id] = event
        identity = _identity(event["detector"], event["kind"], event["subject"])
        disposition = event["disposition"]
        if disposition in TERMINATING_DISPOSITIONS:
            target_id = event["target_event_id"]
            target = by_id.get(target_id)
            if target is None:
                errors.append(
                    f"line {line_number}: target_event_id must reference an earlier event"
                )
                continue
            target_identity = _identity(
                target["detector"], target["kind"], target["subject"]
            )
            if target_identity != identity:
                errors.append(f"line {line_number}: terminating event identity changed")
                continue
            immutable = (
                "detector",
                "detector_version",
                "kind",
                "subject",
                "path",
                "line_start",
                "line_end",
                "evidence_fingerprint",
                "fingerprint_version",
                "source_scan",
            )
            if any(event.get(field) != target.get(field) for field in immutable):
                errors.append(
                    f"line {line_number}: terminating event changed target evidence"
                )
                continue
            if target_id in ended or active.get(identity, {}).get("event_id") != target_id:
                errors.append(f"line {line_number}: target event is not active")
                continue
            ended.add(target_id)
            active.pop(identity, None)
            continue
        if identity in active:
            errors.append(
                f"line {line_number}: conflicting active decisions for "
                f"{event['detector']} {event['kind']} {event['subject']}"
            )
            continue
        active[identity] = event

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "event_count": len(event_list),
        "active_count": len(active),
        "errors": errors,
        "active_events": active,
    }


def load_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load JSONL. Missing is an empty ledger; malformed input is fail-open."""
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"decision ledger unreadable: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: malformed JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: event must be an object")
            continue
        events.append(value)
    return events, errors


def validate_ledger(path: Path) -> dict[str, Any]:
    events, load_errors = load_events(path)
    result = validate_events(events)
    result["errors"] = [*load_errors, *result["errors"]]
    result["valid"] = not result["errors"]
    result.pop("active_events", None)
    return result


def _validate_artifact(artifact: object) -> dict[str, Any]:
    if not isinstance(artifact, dict) or artifact.get("schema_version") != 1:
        raise DecisionMemoryError("finding artifact has an unsupported schema")
    detector = _nonempty(artifact.get("detector"), "artifact detector")
    _nonempty(artifact.get("detector_version"), "artifact detector_version")
    if not isinstance(artifact.get("findings"), list):
        raise DecisionMemoryError("finding artifact findings must be a list")
    for finding in artifact["findings"]:
        if not isinstance(finding, dict):
            raise DecisionMemoryError("normalized finding must be an object")
        kind = _nonempty(finding.get("kind"), "finding kind")
        if not kind.startswith(f"{detector}:"):
            raise DecisionMemoryError("finding kind is not namespaced by detector")
        _nonempty(finding.get("subject"), "finding subject")
        if not isinstance(finding.get("evidence"), dict):
            raise DecisionMemoryError("finding evidence must be an object")
        path = finding.get("path")
        if path is not None:
            path = _nonempty(path, "finding path")
            parsed = PurePosixPath(path)
            if parsed.is_absolute() or ".." in parsed.parts:
                raise DecisionMemoryError("finding path must be project-relative")
        for field in ("line_start", "line_end"):
            value = finding.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise DecisionMemoryError(f"finding {field} is invalid")
        if finding.get("completeness") not in {
            "complete",
            "partial",
            "unsupported",
            "failed",
        }:
            raise DecisionMemoryError("finding completeness is invalid")
        if not isinstance(finding.get("scope_attribution"), str):
            raise DecisionMemoryError("finding scope_attribution is required")
    return artifact


def _dismissible(artifact: dict[str, Any], finding: dict[str, Any]) -> bool:
    return (
        artifact.get("contract", {}).get("finding_granularity") == "line"
        and finding.get("completeness") == "complete"
        and finding.get("scope_attribution") != "unlocated-review-required"
        and isinstance(finding.get("path"), str)
        and isinstance(finding.get("line_start"), int)
        and isinstance(finding.get("line_end"), int)
    )


def filter_artifact(
    artifact: object,
    events: Iterable[object],
    *,
    show_reviewed: bool = False,
) -> dict[str, Any]:
    """Apply valid active decisions; invalid decision data returns all findings."""
    source = _validate_artifact(artifact)
    event_list = list(events)
    validation = validate_events(event_list)
    if not validation["valid"]:
        warnings = [
            "decision memory invalid; all findings shown",
            *validation["errors"],
        ]
        result = dict(source)
        result["findings"] = [
            {**finding, "review": {"status": "unfiltered-invalid-memory"}}
            for finding in source["findings"]
        ]
        result["review_memory"] = {
            "schema_version": SCHEMA_VERSION,
            "status": "fail-open",
            "warnings": warnings,
            "show_reviewed": show_reviewed,
        }
        result["metrics"] = {
            **source.get("metrics", {}),
            "pre_review_finding_count": len(source["findings"]),
            "reviewed_suppressed_count": 0,
            "review_due_count": 0,
            "nondismissible_count": 0,
            "post_review_finding_count": len(source["findings"]),
        }
        return result

    detector = source["detector"]
    current_fingerprint_version = source.get(
        "fingerprint_version", FINGERPRINT_VERSION
    )
    if current_fingerprint_version != FINGERPRINT_VERSION:
        warnings = [
            "finding fingerprint semantics are newer or incompatible; all findings shown"
        ]
        result = dict(source)
        result["findings"] = [
            {
                **finding,
                "review": {
                    "status": "review-due",
                    "reason": "fingerprint-version-changed",
                },
            }
            for finding in source["findings"]
        ]
        result["review_memory"] = {
            "schema_version": SCHEMA_VERSION,
            "status": "fail-open",
            "warnings": warnings,
            "show_reviewed": show_reviewed,
        }
        result["metrics"] = {
            **source.get("metrics", {}),
            "pre_review_finding_count": len(source["findings"]),
            "reviewed_suppressed_count": 0,
            "review_due_count": len(source["findings"]),
            "nondismissible_count": 0,
            "post_review_finding_count": len(source["findings"]),
        }
        return result

    active = validation["active_events"]
    by_location: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for event in active.values():
        by_location.setdefault(_location_identity(event["detector"], event), []).append(
            event
        )

    actionable: list[dict[str, Any]] = []
    reviewed: list[dict[str, Any]] = []
    due_count = 0
    nondismissible_count = 0
    for finding in source["findings"]:
        if not _dismissible(source, finding):
            nondismissible_count += 1
            actionable.append(
                {
                    **finding,
                    "review": {
                        "status": "actionable",
                        "reason": "finding-class-not-dismissible",
                    },
                }
            )
            continue
        identity = _identity(detector, finding["kind"], finding["subject"])
        event = active.get(identity)
        fingerprint = evidence_fingerprint(finding)
        if event is None:
            location_matches = by_location.get(
                _location_identity(detector, finding), []
            )
            if location_matches:
                due_count += 1
                actionable.append(
                    {
                        **finding,
                        "review": {
                            "status": "review-due",
                            "reason": "subject-changed",
                            "prior_event_ids": [
                                item["event_id"] for item in location_matches
                            ],
                        },
                    }
                )
            else:
                actionable.append(
                    {**finding, "review": {"status": "actionable", "reason": "new"}}
                )
            continue
        if event["fingerprint_version"] != current_fingerprint_version:
            due_count += 1
            actionable.append(
                {
                    **finding,
                    "review": {
                        "status": "review-due",
                        "reason": "fingerprint-version-changed",
                        "prior_event_id": event["event_id"],
                    },
                }
            )
        elif event["evidence_fingerprint"] != fingerprint:
            due_count += 1
            actionable.append(
                {
                    **finding,
                    "review": {
                        "status": "review-due",
                        "reason": "evidence-changed",
                        "prior_event_id": event["event_id"],
                    },
                }
            )
        elif event["disposition"] in SUPPRESSING_DISPOSITIONS:
            reviewed_finding = {
                **finding,
                "review": {
                    "status": "reviewed",
                    "disposition": event["disposition"],
                    "event_id": event["event_id"],
                },
            }
            reviewed.append(reviewed_finding)
            if show_reviewed:
                actionable.append(reviewed_finding)
        else:
            reason = (
                "fixed-finding-recurred"
                if event["disposition"] == "fixed"
                else "review-requested"
            )
            due_count += 1
            actionable.append(
                {
                    **finding,
                    "review": {
                        "status": "regression"
                        if event["disposition"] == "fixed"
                        else "review-due",
                        "reason": reason,
                        "prior_event_id": event["event_id"],
                    },
                }
            )

    result = dict(source)
    result["findings"] = actionable
    result["review_memory"] = {
        "schema_version": SCHEMA_VERSION,
        "status": "applied",
        "warnings": [],
        "show_reviewed": show_reviewed,
        "reviewed_count": len(reviewed),
    }
    result["metrics"] = {
        **source.get("metrics", {}),
        "pre_review_finding_count": len(source["findings"]),
        "reviewed_suppressed_count": 0 if show_reviewed else len(reviewed),
        "review_due_count": due_count,
        "nondismissible_count": nondismissible_count,
        "post_review_finding_count": len(actionable),
    }
    return result


def filter_from_ledger(
    artifact: object, ledger: Path, *, show_reviewed: bool = False
) -> dict[str, Any]:
    events, load_errors = load_events(ledger)
    if load_errors:
        # One deliberately malformed sentinel makes the shared fail-open path run.
        events = [*events, {"load_errors": load_errors}]
    result = filter_artifact(artifact, events, show_reviewed=show_reviewed)
    if load_errors:
        result["review_memory"]["warnings"].extend(load_errors)
    return result


def build_decision_event(
    artifact: object,
    *,
    subject: str,
    disposition: str,
    rationale: str,
    reviewer: str,
    source_scan: str,
    event_id: str | None = None,
    recorded_at: str | None = None,
    review_trigger: str | None = None,
) -> dict[str, Any]:
    source = _validate_artifact(artifact)
    if disposition not in INITIAL_DISPOSITIONS:
        raise DecisionMemoryError("use terminate_event for withdrawn or superseded")
    matches = [row for row in source["findings"] if row["subject"] == subject]
    if len(matches) != 1:
        raise DecisionMemoryError("subject must select exactly one finding")
    finding = matches[0]
    if not _dismissible(source, finding):
        raise DecisionMemoryError("this finding class cannot be dismissed")
    return {
        "schema_version": SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "event_id": event_id or f"fde_{uuid.uuid4().hex}",
        "detector": source["detector"],
        "detector_version": source["detector_version"],
        "kind": finding["kind"],
        "subject": finding["subject"],
        "path": finding["path"],
        "line_start": finding["line_start"],
        "line_end": finding["line_end"],
        "evidence_fingerprint": evidence_fingerprint(finding),
        "fingerprint_version": FINGERPRINT_VERSION,
        "disposition": disposition,
        "rationale": _nonempty(rationale, "rationale"),
        "reviewer": _nonempty(reviewer, "reviewer"),
        "source_scan": _nonempty(source_scan, "source_scan"),
        "recorded_at": recorded_at
        or datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        **({"review_trigger": review_trigger.strip()} if review_trigger else {}),
    }


def terminate_event(
    target: dict[str, Any],
    *,
    disposition: str,
    rationale: str,
    reviewer: str,
    event_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    if disposition not in TERMINATING_DISPOSITIONS:
        raise DecisionMemoryError("termination must be withdrawn or superseded")
    event = {
        key: target[key]
        for key in (
            "detector",
            "detector_version",
            "kind",
            "subject",
            "path",
            "line_start",
            "line_end",
            "evidence_fingerprint",
            "fingerprint_version",
            "source_scan",
        )
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "event_id": event_id or f"fde_{uuid.uuid4().hex}",
        **event,
        "disposition": disposition,
        "rationale": _nonempty(rationale, "rationale"),
        "reviewer": _nonempty(reviewer, "reviewer"),
        "recorded_at": recorded_at
        or datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "target_event_id": target["event_id"],
    }


def append_event(path: Path, event: dict[str, Any]) -> None:
    events, load_errors = load_events(path)
    if load_errors:
        raise DecisionMemoryError("cannot append to malformed decision ledger")
    validation = validate_events([*events, event])
    if not validation["valid"]:
        raise DecisionMemoryError("; ".join(validation["errors"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecisionMemoryError(f"cannot read JSON artifact: {path}") from exc


def _write_json(value: object, path: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(text, end="")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate, record, withdraw, or apply reviewed-finding decisions."
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path(".engineering/quality/finding-decisions.jsonl"),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")

    record = commands.add_parser("record")
    record.add_argument("--artifact", type=Path, required=True)
    record.add_argument("--subject", required=True)
    record.add_argument("--disposition", choices=sorted(INITIAL_DISPOSITIONS), required=True)
    record.add_argument("--rationale", required=True)
    record.add_argument("--reviewer", required=True)
    record.add_argument("--source-scan", required=True)
    record.add_argument("--review-trigger")
    record.add_argument("--event-id")

    terminate = commands.add_parser("terminate")
    terminate.add_argument("--target-event-id", required=True)
    terminate.add_argument(
        "--disposition", choices=sorted(TERMINATING_DISPOSITIONS), required=True
    )
    terminate.add_argument("--rationale", required=True)
    terminate.add_argument("--reviewer", required=True)
    terminate.add_argument("--event-id")

    withdraw = commands.add_parser("withdraw")
    withdraw.add_argument("--target-event-id", required=True)
    withdraw.add_argument("--rationale", required=True)
    withdraw.add_argument("--reviewer", required=True)
    withdraw.add_argument("--event-id")

    apply = commands.add_parser("filter")
    apply.add_argument("--artifact", type=Path, required=True)
    apply.add_argument("--output", type=Path)
    apply.add_argument("--show-reviewed", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_ledger(args.decisions)
            _write_json(result, None)
            return 0 if result["valid"] else 1
        if args.command == "record":
            event = build_decision_event(
                _read_json(args.artifact),
                subject=args.subject,
                disposition=args.disposition,
                rationale=args.rationale,
                reviewer=args.reviewer,
                source_scan=args.source_scan,
                event_id=args.event_id,
                review_trigger=args.review_trigger,
            )
            append_event(args.decisions, event)
            _write_json(event, None)
            return 0
        if args.command in {"terminate", "withdraw"}:
            events, load_errors = load_events(args.decisions)
            validation = validate_events(events)
            if load_errors or not validation["valid"]:
                raise DecisionMemoryError("decision ledger is invalid")
            target = next(
                (
                    event
                    for event in validation["active_events"].values()
                    if event["event_id"] == args.target_event_id
                ),
                None,
            )
            if target is None:
                raise DecisionMemoryError("target event is not active")
            event = terminate_event(
                target,
                disposition=(
                    args.disposition if args.command == "terminate" else "withdrawn"
                ),
                rationale=args.rationale,
                reviewer=args.reviewer,
                event_id=args.event_id,
            )
            append_event(args.decisions, event)
            _write_json(event, None)
            return 0
        result = filter_from_ledger(
            _read_json(args.artifact),
            args.decisions,
            show_reviewed=args.show_reviewed,
        )
        _write_json(result, args.output)
        for warning in result["review_memory"]["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
        return 0
    except DecisionMemoryError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
