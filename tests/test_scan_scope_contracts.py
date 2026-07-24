"""Conformance tests for the finding-producer scan-scope contract."""
from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_scan_scope_contracts.py"
CONTRACTS = ROOT / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_scan_scope_contracts", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_accounts_for_every_find_skill() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)

    assert checker.find_skill_names(ROOT) == {
        row["skill"] for row in payload["skills"]
    }


def test_contract_schema_and_entrypoints_are_valid() -> None:
    checker = _load_checker()

    errors = checker.validate_contract(ROOT, checker.load_contract(CONTRACTS))

    assert errors == []


def test_diff_line_mode_is_reserved_for_line_local_filtering() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)

    diff_line_rows = [
        row for row in payload["skills"] if "diff-lines" in row["target_modes"]
    ]
    assert diff_line_rows
    assert all(row["finding_granularity"] == "line" for row in diff_line_rows)
    assert all(row["diff_semantics"] == "filter-findings" for row in diff_line_rows)


def test_current_modes_do_not_overclaim_target_rollout() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)

    assert any(
        set(row["current_modes"]) != set(row["target_modes"])
        for row in payload["skills"]
    )
    for row in payload["skills"]:
        assert set(row["current_modes"]) <= set(row["target_modes"])


def test_active_adapter_rollout_is_backed_by_real_implementation_and_conformance() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)

    assert payload["adapter_rollout"] == {
        "status": "active",
        "routing_modes_field": "target_modes",
        "implementation": ".claude/skills/which-cleanup/scripts/finding_envelope.py",
        "conformance": "tests/test_finding_scope_conformance.py",
    }
    assert checker.validate_contract(ROOT, payload) == []


def test_checker_rejects_missing_duplicate_and_stale_rows() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)

    missing = deepcopy(payload)
    removed = missing["skills"].pop()
    assert any(
        error.startswith("missing skill rows:")
        for error in checker.validate_contract(ROOT, missing)
    )

    duplicate = deepcopy(payload)
    duplicate["skills"].append(deepcopy(duplicate["skills"][-1]))
    assert any(
        error.startswith("duplicate skills:")
        for error in checker.validate_contract(ROOT, duplicate)
    )

    stale = deepcopy(payload)
    extra = deepcopy(stale["skills"][-1])
    extra["skill"] = "find-z-stale-contract"
    extra["entrypoints"] = [removed["entrypoints"][0]]
    stale["skills"].append(extra)
    errors = checker.validate_contract(ROOT, stale)
    assert any(error.startswith("stale skill rows:") for error in errors)


def test_checker_rejects_overclaimed_modes_and_missing_entrypoints() -> None:
    checker = _load_checker()
    payload = checker.load_contract(CONTRACTS)
    broken = deepcopy(payload)
    row = broken["skills"][0]
    row["current_modes"] = [*row["current_modes"], "diff-lines"]
    row["entrypoints"] = ["scripts/does-not-exist.py"]

    errors = checker.validate_contract(ROOT, broken)

    assert any("current modes must be a subset" in error for error in errors)
    assert any("missing file" in error for error in errors)
