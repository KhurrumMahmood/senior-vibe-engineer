"""Tests for find-orphaned-ideas detect_stale_plans.

Regression coverage for the adversarial-review findings on
ai-docs/plans/consistency-session-execution.md (F1): the detector must
fire on plans in any non-terminal status (not just legacy "proposed"),
must age untracked plans via filesystem mtime, and must only exempt
ledger-tracked plans while the ledger idea is actually in-flight.
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIND_PATH = (
    REPO_ROOT / ".claude" / "skills" / "find-orphaned-ideas" / "scripts" / "find.py"
)


def _load_find():
    spec = importlib.util.spec_from_file_location("orphan_find", FIND_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_plan(tmp_path: Path, name: str, status: str, *, age_days: int) -> Path:
    plans_dir = tmp_path / "ai-docs" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    p = plans_dir / f"{name}.md"
    p.write_text(f"---\nname: {name}\nstatus: {status}\n---\n\n# {name}\n")
    old = time.time() - age_days * 86400
    os.utime(p, (old, old))
    return p


def test_scoped_untracked_plan_is_flagged(tmp_path):
    """A scoped, uncommitted plan older than the threshold must surface."""
    find = _load_find()
    _write_plan(tmp_path, "stalled-initiative", "scoped", age_days=40)
    out = find.detect_stale_plans(tmp_path, [], stale_threshold_days=30)
    assert [f["slug"] for f in out] == ["stalled-initiative"]
    assert out[0]["status"] == "scoped"


def test_all_non_terminal_statuses_flag_and_terminal_do_not(tmp_path):
    find = _load_find()
    for status in ("draft", "proposed", "scoped", "impacted", "architected"):
        _write_plan(tmp_path, f"plan-{status}", status, age_days=40)
    for status in ("promoted", "abandoned"):
        _write_plan(tmp_path, f"plan-{status}", status, age_days=40)
    out = find.detect_stale_plans(tmp_path, [], stale_threshold_days=30)
    flagged = {f["status"] for f in out}
    assert flagged == {"draft", "proposed", "scoped", "impacted", "architected"}


def test_fresh_plan_not_flagged(tmp_path):
    find = _load_find()
    _write_plan(tmp_path, "fresh-plan", "scoped", age_days=2)
    assert find.detect_stale_plans(tmp_path, [], stale_threshold_days=30) == []


def test_ledger_exemption_requires_in_flight(tmp_path):
    """A proposed-state ledger intake is NOT active tracking; in-flight is."""
    find = _load_find()
    _write_plan(tmp_path, "tracked-plan", "scoped", age_days=40)

    proposed_only = [
        {"record_kind": "intake", "id": "tracked-plan", "state": "proposed"},
    ]
    out = find.detect_stale_plans(tmp_path, proposed_only, stale_threshold_days=30)
    assert [f["slug"] for f in out] == ["tracked-plan"]

    in_flight = proposed_only + [
        {
            "record_kind": "event",
            "id": "tracked-plan",
            "event_kind": "transition",
            "to_state": "in-flight",
        },
    ]
    out = find.detect_stale_plans(tmp_path, in_flight, stale_threshold_days=30)
    assert out == []
