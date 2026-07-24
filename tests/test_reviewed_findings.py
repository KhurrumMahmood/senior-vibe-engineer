"""Portable reviewed-finding memory and evidence-change behavior."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROUTER_SCRIPTS = ROOT / ".claude" / "skills" / "which-cleanup" / "scripts"
CONTRACTS = ROOT / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"


def _load(name: str):
    if str(ROUTER_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(ROUTER_SCRIPTS))
    path = ROUTER_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"review_memory_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _artifact(
    *,
    detector: str = "find-comment-drift",
    subject: str = "src/app.py:2:obvious-narration",
    evidence: str = "Create the item",
    completeness: str = "complete",
    granularity: str = "line",
    line: int | None = 2,
) -> dict:
    return {
        "schema_version": 1,
        "detector": detector,
        "detector_version": "portable-v1",
        "contract": {"finding_granularity": granularity},
        "scan_request": {"schema_version": 1, "selector": {"kind": "paths"}},
        "scan": {"effective_mode": "paths"},
        "findings": [
            {
                "kind": f"{detector}:obvious_narration_comment",
                "subject": subject,
                "path": "src/app.py",
                "line_start": line,
                "line_end": line,
                "evidence": {"summary": evidence},
                "completeness": completeness,
                "scope_attribution": "paths",
                "detail": {"recommendation": "delete narration"},
            }
        ],
        "metrics": {"actionable_finding_count": 1},
    }


def _event(memory, artifact: dict, **overrides) -> dict:
    values = {
        "subject": artifact["findings"][0]["subject"],
        "disposition": "false-positive",
        "rationale": "Reviewed against the adjacent function; intent is not narration.",
        "reviewer": "maintainer@example.invalid",
        "source_scan": "scan-001",
        "event_id": "fde_001",
        "recorded_at": "2026-07-23T12:00:00Z",
    }
    values.update(overrides)
    return memory.build_decision_event(artifact, **values)


def test_unchanged_review_is_hidden_by_default_and_inspectable_on_request() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact)

    filtered = memory.filter_artifact(artifact, [event])
    shown = memory.filter_artifact(artifact, [event], show_reviewed=True)

    assert filtered["findings"] == []
    assert filtered["metrics"]["pre_review_finding_count"] == 1
    assert filtered["metrics"]["reviewed_suppressed_count"] == 1
    assert filtered["review_memory"]["reviewed_count"] == 1
    assert shown["findings"][0]["review"] == {
        "status": "reviewed",
        "disposition": "false-positive",
        "event_id": "fde_001",
    }
    assert shown["metrics"]["reviewed_suppressed_count"] == 0


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda row: row["evidence"].update(summary="Delete the item"), "evidence-changed"),
        (lambda row: row.update(subject="src/app.py:2:different-subject"), "subject-changed"),
    ],
)
def test_changed_evidence_or_subject_resurfaces_for_review(mutation, reason) -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact)
    mutation(artifact["findings"][0])

    result = memory.filter_artifact(artifact, [event])

    assert len(result["findings"]) == 1
    assert result["findings"][0]["review"]["status"] == "review-due"
    assert result["findings"][0]["review"]["reason"] == reason
    assert result["metrics"]["review_due_count"] == 1


def test_fingerprint_semantics_change_fails_open_and_requests_review() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact)
    artifact["fingerprint_version"] = 2

    result = memory.filter_artifact(artifact, [event])

    assert len(result["findings"]) == 1
    assert result["findings"][0]["review"]["reason"] == "fingerprint-version-changed"
    assert result["review_memory"]["status"] == "fail-open"
    assert result["review_memory"]["warnings"]


def test_fixed_decision_never_suppresses_recurrence() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact, disposition="fixed")

    result = memory.filter_artifact(artifact, [event])

    assert result["findings"][0]["review"] == {
        "status": "regression",
        "reason": "fixed-finding-recurred",
        "prior_event_id": "fde_001",
    }


def test_toolkit_or_detector_release_alone_does_not_invalidate_review() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact)
    artifact["detector_version"] = "portable-v99"

    result = memory.filter_artifact(artifact, [event])

    assert result["findings"] == []
    assert result["metrics"]["reviewed_suppressed_count"] == 1


@pytest.mark.parametrize(
    "artifact",
    [
        _artifact(completeness="failed"),
        _artifact(completeness="partial"),
        _artifact(granularity="file"),
        _artifact(granularity="project", line=None),
    ],
)
def test_failures_incomplete_and_wider_obligations_cannot_be_dismissed(artifact) -> None:
    memory = _load("reviewed_findings")

    with pytest.raises(memory.DecisionMemoryError, match="cannot be dismissed"):
        _event(memory, artifact)
    result = memory.filter_artifact(artifact, [])
    assert result["findings"][0]["review"]["reason"] == "finding-class-not-dismissible"


def test_invalid_ledger_is_reported_and_fails_open() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    event = _event(memory, artifact)
    duplicate = {**event}

    result = memory.filter_artifact(artifact, [event, duplicate])

    assert len(result["findings"]) == 1
    assert result["review_memory"]["status"] == "fail-open"
    assert any("duplicate event_id" in item for item in result["review_memory"]["warnings"])


def test_malformed_file_fails_open_with_exact_warning(tmp_path: Path) -> None:
    memory = _load("reviewed_findings")
    ledger = tmp_path / "finding-decisions.jsonl"
    ledger.write_text("{not json}\n", encoding="utf-8")

    result = memory.filter_from_ledger(_artifact(), ledger)

    assert len(result["findings"]) == 1
    assert result["review_memory"]["status"] == "fail-open"
    assert any("malformed JSON" in item for item in result["review_memory"]["warnings"])


def test_conflicting_active_decisions_and_invalid_transitions_are_rejected() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact()
    first = _event(memory, artifact)
    conflicting = _event(memory, artifact, disposition="accepted-debt", event_id="fde_002")
    invalid_termination = memory.terminate_event(
        first,
        disposition="withdrawn",
        rationale="No longer applicable.",
        reviewer="maintainer@example.invalid",
        event_id="fde_003",
        recorded_at="2026-07-23T13:00:00Z",
    )
    invalid_termination["target_event_id"] = "missing"

    conflict_result = memory.validate_events([first, conflicting])
    transition_result = memory.validate_events([first, invalid_termination])

    assert not conflict_result["valid"]
    assert "conflicting active decisions" in conflict_result["errors"][0]
    assert not transition_result["valid"]
    assert "earlier event" in transition_result["errors"][0]

    changed_termination = memory.terminate_event(
        first,
        disposition="superseded",
        rationale="Replace the judgment.",
        reviewer="maintainer@example.invalid",
        event_id="fde_004",
        recorded_at="2026-07-23T14:00:00Z",
    )
    changed_termination["evidence_fingerprint"] = "0" * 64
    changed_result = memory.validate_events([first, changed_termination])
    assert not changed_result["valid"]
    assert "changed target evidence" in changed_result["errors"][0]


def test_decision_event_keeps_hash_and_identity_but_not_raw_evidence() -> None:
    memory = _load("reviewed_findings")
    artifact = _artifact(evidence="SECRET_API_TOKEN=do-not-copy")

    event = _event(memory, artifact)
    serialized = json.dumps(event)

    assert event["evidence_fingerprint"] == memory.evidence_fingerprint(
        artifact["findings"][0]
    )
    assert "SECRET_API_TOKEN" not in serialized
    assert "evidence" not in event
    assert "detail" not in event


def test_untrusted_artifact_cannot_record_absolute_or_traversal_paths() -> None:
    memory = _load("reviewed_findings")
    for unsafe in ("/private/source.py", "../source.py"):
        artifact = _artifact()
        artifact["findings"][0]["path"] = unsafe
        with pytest.raises(memory.DecisionMemoryError, match="project-relative"):
            memory.filter_artifact(artifact, [])


def test_record_filter_show_withdraw_cli_loop(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(_artifact()), encoding="utf-8")
    ledger = tmp_path / ".engineering" / "quality" / "finding-decisions.jsonl"
    tool = ROUTER_SCRIPTS / "reviewed_findings.py"
    base = [sys.executable, "-I", "-S", str(tool), "--decisions", str(ledger)]

    record = subprocess.run(
        [
            *base,
            "record",
            "--artifact",
            str(artifact_path),
            "--subject",
            _artifact()["findings"][0]["subject"],
            "--disposition",
            "false-positive",
            "--rationale",
            "Reviewed manually.",
            "--reviewer",
            "maintainer@example.invalid",
            "--source-scan",
            "scan-cli",
            "--event-id",
            "fde_cli_1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert record.returncode == 0, record.stderr

    hidden_path = tmp_path / "hidden.json"
    hidden = subprocess.run(
        [*base, "filter", "--artifact", str(artifact_path), "--output", str(hidden_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert hidden.returncode == 0, hidden.stderr
    assert json.loads(hidden_path.read_text())["findings"] == []

    shown = subprocess.run(
        [*base, "filter", "--artifact", str(artifact_path), "--show-reviewed"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["findings"][0]["review"]["status"] == "reviewed"

    withdrawn = subprocess.run(
        [
            *base,
            "withdraw",
            "--target-event-id",
            "fde_cli_1",
            "--rationale",
            "Revisit this finding.",
            "--reviewer",
            "maintainer@example.invalid",
            "--event-id",
            "fde_cli_2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert withdrawn.returncode == 0, withdrawn.stderr
    visible = subprocess.run(
        [*base, "filter", "--artifact", str(artifact_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert visible.returncode == 0, visible.stderr
    assert json.loads(visible.stdout)["findings"][0]["review"]["reason"] == "new"


def test_all_scope_producers_pass_through_shared_filter_without_decisions() -> None:
    memory = _load("reviewed_findings")
    contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))["skills"]
    seen = set()
    for contract in contracts:
        artifact = _artifact(
            detector=contract["skill"],
            granularity=contract["finding_granularity"],
            line=2 if contract["finding_granularity"] == "line" else None,
        )
        artifact["findings"][0]["kind"] = f"{contract['skill']}:fixture"
        result = memory.filter_artifact(artifact, [])
        assert len(result["findings"]) == 1
        seen.add(contract["skill"])
    assert len(seen) == 30


def test_real_comment_drift_record_filter_show_and_evidence_change(tmp_path: Path) -> None:
    memory = _load("reviewed_findings")
    envelope = _load("finding_envelope")
    request_module = _load("scan_request")
    detector_path = (
        ROOT / ".claude" / "skills" / "find-comment-drift" / "scripts" / "detect.py"
    )
    detector_scripts = detector_path.parent
    if str(detector_scripts) not in sys.path:
        sys.path.insert(0, str(detector_scripts))
    spec = importlib.util.spec_from_file_location("review_memory_comment_detector", detector_path)
    assert spec and spec.loader
    detector = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = detector
    spec.loader.exec_module(detector)

    host = tmp_path / "host"
    source = host / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("# Create item\nvalue = 1\n", encoding="utf-8")
    contract = next(
        row
        for row in json.loads(CONTRACTS.read_text(encoding="utf-8"))["skills"]
        if row["skill"] == "find-comment-drift"
    )
    request = request_module.ScanRequest(
        project_root=str(host),
        requested_mode="paths",
        selector={"kind": "paths", "paths": ["src/app.py"]},
        content_basis="working-tree",
        line_filter_safe=None,
        changes=(
            request_module.PathChange(
                path="src/app.py",
                change_type="explicit",
                old_path=None,
                current_exists=True,
                binary=False,
                line_ranges=(),
            ),
        ),
    )

    def build() -> dict:
        found = detector.scan_files([source], host)
        assert len(found) == 1
        raw = [
            {
                "kind": finding.pattern,
                "subject": f"{finding.file}:{finding.lineno}:{finding.pattern}",
                "path": finding.file,
                "line_start": finding.lineno,
                "line_end": finding.end_lineno or finding.lineno,
                "evidence": {"summary": finding.summary},
                "completeness": "complete",
                "detail": {"recommendation": finding.recommendation},
            }
            for finding in found
        ]
        return envelope.build_finding_artifact(
            detector="find-comment-drift",
            detector_version="portable-v1",
            raw_findings=raw,
            request=request,
            contract=contract,
            supported_modes_field="target_modes",
            allow_compatible_widening=False,
        )

    first = build()
    decision = _event(
        memory,
        first,
        subject=first["findings"][0]["subject"],
        event_id="fde_comment_pilot",
    )
    assert memory.filter_artifact(first, [decision])["findings"] == []
    assert memory.filter_artifact(first, [decision], show_reviewed=True)["findings"]

    source.write_text("# Delete item\nvalue = 1\n", encoding="utf-8")
    changed = memory.filter_artifact(build(), [decision])
    assert changed["findings"][0]["review"]["reason"] == "evidence-changed"


def test_copied_router_decision_tool_runs_without_repository_imports(tmp_path: Path) -> None:
    copied = tmp_path / "which-cleanup"
    shutil.copytree(ROUTER_SCRIPTS.parent, copied)
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(_artifact()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(copied / "scripts" / "reviewed_findings.py"),
            "--decisions",
            str(tmp_path / "missing.jsonl"),
            "filter",
            "--artifact",
            str(artifact),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["findings"][0]["review"]["reason"] == "new"


def test_committed_schema_is_agent_neutral_and_excludes_raw_payloads() -> None:
    schema = json.loads(
        (ROOT / ".engineering" / "quality" / "finding-decision-schema.json").read_text()
    )
    assert schema["properties"]["record_kind"]["const"] == "finding-decision-event"
    assert "evidence" not in schema["properties"]
    assert "original_finding" not in schema["properties"]
    assert set(schema["properties"]["disposition"]["enum"]) == {
        "false-positive",
        "accepted-debt",
        "intentional-exception",
        "fixed",
        "superseded",
        "withdrawn",
        "review-due",
    }
