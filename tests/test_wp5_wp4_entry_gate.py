"""Fault-injection tests for the WP5 IM-12 dependency entry gate."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts import check_wp5_wp4_entry_gate as gate


def _text(path: Path) -> str:
    return (gate.REPO_ROOT / path).read_text(encoding="utf-8")


def test_authoritative_tracker_and_final_clean_verifier_are_bound() -> None:
    gate.validate_tracker(_text(gate.TRACKER))
    report = gate.REPO_ROOT / gate.FINAL_REPORT
    gate.validate_final_report(report.read_text(encoding="utf-8"), gate._sha256(report))


@pytest.mark.parametrize(
    "old,new",
    [
        ("| WP4 Multi-language analysis substrate | verified |", "| WP4 Multi-language analysis substrate | implemented |"),
        ("AC-4.1–AC-4.6", "AC-4.1–AC-4.5"),
        ("parser-backed WP5 work is dependency-ready", "parser work may start"),
    ],
)
def test_tracker_rejects_unverified_or_weaker_handoff(old: str, new: str) -> None:
    tampered = _text(gate.TRACKER).replace(old, new)
    with pytest.raises(gate.GateFailure):
        gate.validate_tracker(tampered)


def test_final_report_rejects_hash_or_fresh_artifact_drift() -> None:
    report = _text(gate.FINAL_REPORT)
    with pytest.raises(gate.GateFailure, match="hash"):
        gate.validate_final_report(report, "0" * 64)
    tampered = report.replace(gate.FRESH_VERIFIER_HASHES["fresh Linux report"], "0" * 64)
    with pytest.raises(gate.GateFailure):
        gate.validate_final_report(tampered, gate.EVIDENCE_SHA256[gate.FINAL_REPORT])


def test_platform_matrix_binds_both_platforms_tools_and_stable_result() -> None:
    matrix = gate.validate_platform_matrix()
    assert matrix["required_platforms"] == ["Darwin-arm64", "Linux-x86_64"]
    attacks = []
    weaker = copy.deepcopy(matrix)
    weaker["required_platforms"] = ["Darwin-arm64"]
    attacks.append(weaker)
    wrong_tool = copy.deepcopy(matrix)
    wrong_tool["executions"]["Linux-x86_64"]["tree_sitter"] = "0.25.0"
    attacks.append(wrong_tool)
    stale = copy.deepcopy(matrix)
    stale["stable_result_sha256"] = "0" * 64
    attacks.append(stale)
    for attack in attacks:
        with pytest.raises(gate.GateFailure):
            gate.validate_platform_matrix_payload(attack)


def test_repository_preflight_passes_without_claiming_parser_entry() -> None:
    result = gate.check(preflight_only=True)
    assert result["verified_revision"] == gate.VERIFIED_REVISION
    assert result["preflight_only"] is True
    assert result["entry_allowed"] is False


def test_dependency_record_scope_includes_tracker_and_all_bound_evidence() -> None:
    assert str(gate.TRACKER) in gate.DEPENDENCY_RECORD_PATHS
    assert {str(path) for path in gate.EVIDENCE_SHA256} <= set(
        gate.DEPENDENCY_RECORD_PATHS
    )
