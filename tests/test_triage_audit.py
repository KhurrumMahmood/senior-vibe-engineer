"""Characterization tests for scripts/triage_audit.py.

Drives the auditor via ``triage_audit.run_audit()`` against synthetic JSONL
fixtures built in ``tmp_path``. The CLI entry-point (``triage_audit.main()``)
is exercised for exit-code assertions and the --md / --json output paths.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


import triage_audit


# ---- fixture helpers --------------------------------------------------------

NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def _eff(tmp_path: Path, records: list[dict]) -> Path:
    return _write_jsonl(tmp_path / "effectiveness.jsonl", records)


def _find(tmp_path: Path, records: list[dict]) -> Path:
    return _write_jsonl(tmp_path / "findings.jsonl", records)


def _dism(tmp_path: Path, records: list[dict]) -> Path:
    return _write_jsonl(tmp_path / "dismissals.jsonl", records)


def _ts(days_ago: int) -> str:
    dt = NOW - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(eff: Path, fin: Path, dis: Path, grace: int = 7) -> dict:
    return triage_audit.run_audit(
        effectiveness_path=eff,
        findings_path=fin,
        dismissals_path=dis,
        grace_days=grace,
        now=NOW,
    )


# ---- unaccounted scan -------------------------------------------------------

def test_unaccounted_scan_returned(tmp_path):
    """A scan older than grace with no acknowledgment appears in unaccounted."""
    eff = _eff(tmp_path, [
        {"skill": "find-async-lifecycle-drift", "scan_id": "scan-001",
         "target": "/sites", "findings_total": 28, "ts": _ts(30)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert len(result["unaccounted"]) == 1
    row = result["unaccounted"][0]
    assert row["skill"] == "find-async-lifecycle-drift"
    assert row["scan_id"] == "scan-001"
    assert row["findings_total"] == 28
    assert row["age_days"] == 30


def test_unaccounted_scan_exits_1(tmp_path):
    eff = _eff(tmp_path, [
        {"skill": "find-async-lifecycle-drift", "scan_id": "s1",
         "target": "/sites", "findings_total": 5, "ts": _ts(10)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    rc = triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
        "--grace-days", "7",
    ])
    assert rc == 1


# ---- acknowledged by finding ------------------------------------------------

def test_acknowledged_by_source_scan_match(tmp_path):
    """findings.jsonl with source_scan == scan_id acknowledges the scan."""
    eff = _eff(tmp_path, [
        {"skill": "find-test-obligation-drift", "scan_id": "scan-abc",
         "target": "git diff", "findings_total": 4, "ts": _ts(20)},
    ])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_1", "source_scan": "scan-abc",
         "source_skill": "find-test-obligation-drift", "status": "open",
         "created_at": _ts(19)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []
    assert result["acknowledged_count"] == 1


def test_acknowledged_by_skill_within_window(tmp_path):
    """findings.jsonl with matching source_skill and ts within grace acknowledges."""
    eff = _eff(tmp_path, [
        {"skill": "find-layer-violation", "scan_id": "scan-xyz",
         "target": "core/views", "findings_total": 8, "ts": _ts(15)},
    ])
    # Finding references the skill; its own ts is within grace window (3 days ago)
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_2", "source_scan": "different-scan",
         "source_skill": "find-layer-violation", "status": "open",
         "created_at": _ts(3)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []


# ---- acknowledged by dismissal ----------------------------------------------

def test_acknowledged_by_dismissal_scan_id(tmp_path):
    """dismissals.jsonl with matching scan_id acknowledges the scan."""
    eff = _eff(tmp_path, [
        {"skill": "find-implicit-state", "scan_id": "scan-implicit-1",
         "target": "core/", "findings_total": 5, "ts": _ts(12)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [
        {"record_kind": "finding", "source_skill": "find-implicit-state",
         "source_scan": "scan-implicit-1", "status": "active",
         "id": "dm_abc", "created_at": _ts(11)},
    ])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []
    assert result["acknowledged_count"] == 1


def test_acknowledged_by_dismissal_skill_within_window(tmp_path):
    """dismissals.jsonl with matching skill within grace acknowledges the scan."""
    eff = _eff(tmp_path, [
        {"skill": "find-implicit-state", "scan_id": "scan-imp-2",
         "target": "core/", "findings_total": 3, "ts": _ts(14)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [
        {"record_kind": "finding", "source_skill": "find-implicit-state",
         "id": "dm_xyz", "created_at": _ts(4)},
    ])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []


# ---- within grace (not yet due) ---------------------------------------------

def test_within_grace_not_reported(tmp_path):
    """A scan younger than grace is not yet due — not unaccounted."""
    eff = _eff(tmp_path, [
        {"skill": "find-dead-route-surface", "scan_id": "scan-new",
         "target": "/sites", "findings_total": 2, "ts": _ts(3)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis, grace=7)
    assert result["unaccounted"] == []
    assert result["within_grace_count"] == 1


def test_zero_findings_ignored(tmp_path):
    """Scans with findings_total == 0 are never audited."""
    eff = _eff(tmp_path, [
        {"skill": "find-transaction-overreach", "scan_id": "scan-clean",
         "target": "core/", "findings_total": 0, "ts": _ts(30)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []
    assert result["acknowledged_count"] == 0


# ---- superseded scan collapse -----------------------------------------------

def test_superseded_scans_collapse_to_count(tmp_path):
    """Only the latest scan per (skill, target) is evaluated; older runs collapse."""
    eff = _eff(tmp_path, [
        # Older run — superseded
        {"skill": "find-async-lifecycle-drift", "scan_id": "scan-old",
         "target": "/sites", "findings_total": 28, "ts": _ts(30)},
        # Newer run of the same skill+target — latest
        {"skill": "find-async-lifecycle-drift", "scan_id": "scan-new",
         "target": "/sites", "findings_total": 28, "ts": _ts(20)},
    ])
    fin = _find(tmp_path, [
        # Acknowledges the latest scan only
        {"record_kind": "finding", "id": "qf_x", "source_scan": "scan-new",
         "source_skill": "find-async-lifecycle-drift", "status": "open",
         "created_at": _ts(19)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    # scan-new is acknowledged; scan-old is superseded (not a separate failure)
    assert result["unaccounted"] == []
    assert result["superseded_count"] == 1
    assert result["acknowledged_count"] == 1


def test_superseded_older_run_unaccounted_does_not_appear(tmp_path):
    """Even if the superseded scan has no ack, only the latest counts."""
    eff = _eff(tmp_path, [
        {"skill": "find-omnibus", "scan_id": "old-scan",
         "target": "core/", "findings_total": 10, "ts": _ts(40)},
        {"skill": "find-omnibus", "scan_id": "new-scan",
         "target": "core/", "findings_total": 5, "ts": _ts(25)},
    ])
    fin = _find(tmp_path, [
        # Only new-scan is acknowledged
        {"record_kind": "finding", "id": "qf_y", "source_scan": "new-scan",
         "source_skill": "find-omnibus", "status": "open",
         "created_at": _ts(24)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []
    assert result["superseded_count"] == 1


# ---- open-finding aging -----------------------------------------------------

def test_open_finding_aging_reported(tmp_path):
    """open findings from findings.jsonl appear in open_findings with age."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_open_1",
         "source_skill": "find-implicit-state",
         "source_scan": "scan-001", "pattern": "stringly_compare",
         "status": "open", "created_at": _ts(25)},
        {"record_kind": "finding", "id": "qf_open_2",
         "source_skill": "find-layer-violation",
         "source_scan": "scan-002", "pattern": "extract_service",
         "status": "open", "created_at": _ts(10)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert len(result["open_findings"]) == 2
    # Oldest first
    assert result["open_findings"][0]["id"] == "qf_open_1"
    assert result["open_findings"][0]["age_days"] == 25
    assert result["open_findings"][1]["id"] == "qf_open_2"
    assert result["open_findings"][1]["age_days"] == 10


def test_resolved_finding_excluded(tmp_path):
    """A finding with a later resolving event is excluded from open_findings."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_fixed",
         "source_skill": "find-omnibus", "source_scan": "s1",
         "pattern": "confirmed_omnibus", "status": "open",
         "created_at": _ts(20)},
        {"record_kind": "event", "id": "qf_fixed",
         "event_kind": "status", "status": "fixed",
         "event_at": _ts(18)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["open_findings"] == []


def test_false_positive_event_excludes_finding(tmp_path):
    """A false-positive event closes a finding from open_findings."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_fp",
         "source_skill": "find-implicit-state", "source_scan": "s2",
         "pattern": "tuple_identity", "status": "open",
         "created_at": _ts(15)},
        {"record_kind": "event", "id": "qf_fp",
         "event_kind": "status", "status": "false-positive",
         "event_at": _ts(14)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["open_findings"] == []


def test_open_finding_no_resolving_event(tmp_path):
    """A finding with only a non-resolving event stays open."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_deferred",
         "source_skill": "triage-debt", "source_scan": "s3",
         "pattern": "top_n", "status": "deferred",
         "created_at": _ts(8)},
        # invalidated event — not a resolution
        {"record_kind": "event", "id": "qf_deferred",
         "event_kind": "invalidated", "event_at": _ts(7)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    # "deferred" is not in the open statuses checked, so it should not appear
    assert result["open_findings"] == []


def test_uncertain_finding_appears_in_open(tmp_path):
    """Status=uncertain findings appear as open."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_unc",
         "source_skill": "find-concept-divergence", "source_scan": "s4",
         "pattern": "concept-drift", "status": "uncertain",
         "created_at": _ts(5)},
    ])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert len(result["open_findings"]) == 1
    assert result["open_findings"][0]["id"] == "qf_unc"


# ---- malformed line tolerance -----------------------------------------------

def test_malformed_lines_skipped_with_warning(tmp_path):
    """Non-JSON lines increment warning count; valid lines still parsed."""
    eff_path = tmp_path / "eff.jsonl"
    eff_path.write_text(
        json.dumps({"skill": "find-omnibus", "scan_id": "s1",
                    "target": "core/", "findings_total": 5, "ts": _ts(30)}) + "\n"
        + "NOT VALID JSON\n"
        + json.dumps({"skill": "find-dormant", "scan_id": "s2",
                      "target": "core/", "findings_total": 3, "ts": _ts(20)}) + "\n",
        encoding="utf-8",
    )
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    result = triage_audit.run_audit(
        effectiveness_path=eff_path,
        findings_path=fin,
        dismissals_path=dis,
        grace_days=7,
        now=NOW,
    )
    assert result["warnings"] == 1
    # Both valid records should be parsed: 2 unaccounted
    assert len(result["unaccounted"]) == 2


def test_empty_files_handled(tmp_path):
    """Empty JSONL files produce no errors and empty results."""
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    result = _run(eff, fin, dis)
    assert result["unaccounted"] == []
    assert result["open_findings"] == []
    assert result["warnings"] == 0


def test_missing_dismissals_file_handled(tmp_path):
    """A non-existent dismissals file is treated as empty (no crash)."""
    eff = _eff(tmp_path, [
        {"skill": "find-async-lifecycle-drift", "scan_id": "s1",
         "target": "/sites", "findings_total": 28, "ts": _ts(30)},
    ])
    fin = _find(tmp_path, [])
    dis_path = tmp_path / "nonexistent_dismissals.jsonl"  # does not exist
    result = triage_audit.run_audit(
        effectiveness_path=eff,
        findings_path=fin,
        dismissals_path=dis_path,
        grace_days=7,
        now=NOW,
    )
    assert len(result["unaccounted"]) == 1


# ---- exit codes -------------------------------------------------------------

def test_exit_0_all_accounted(tmp_path):
    eff = _eff(tmp_path, [
        {"skill": "find-layer-violation", "scan_id": "s1",
         "target": "core/", "findings_total": 8, "ts": _ts(10)},
    ])
    fin = _find(tmp_path, [
        {"record_kind": "finding", "id": "qf_z", "source_scan": "s1",
         "source_skill": "find-layer-violation", "status": "open",
         "created_at": _ts(9)},
    ])
    dis = _dism(tmp_path, [])
    rc = triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
    ])
    assert rc == 0


def test_exit_0_all_within_grace(tmp_path):
    eff = _eff(tmp_path, [
        {"skill": "find-dead-route-surface", "scan_id": "s-new",
         "target": "/sites", "findings_total": 2, "ts": _ts(2)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    rc = triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
        "--grace-days", "7",
        "--now", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ])
    assert rc == 0


def test_cli_rejects_invalid_explicit_clock(tmp_path):
    eff = _eff(tmp_path, [])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    rc = triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
        "--now", "not-a-timestamp",
    ])
    assert rc == 2


# ---- output format ----------------------------------------------------------

def test_md_output_written(tmp_path):
    eff = _eff(tmp_path, [
        {"skill": "find-async-lifecycle-drift", "scan_id": "scan-001",
         "target": "/sites", "findings_total": 28, "ts": _ts(30)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    md_path = tmp_path / "report.md"
    triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
        "--md", str(md_path),
    ])
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "UNACCOUNTED" in content
    assert "find-async-lifecycle-drift" in content


def test_json_output_written(tmp_path):
    eff = _eff(tmp_path, [
        {"skill": "find-async-lifecycle-drift", "scan_id": "scan-001",
         "target": "/sites", "findings_total": 28, "ts": _ts(30)},
    ])
    fin = _find(tmp_path, [])
    dis = _dism(tmp_path, [])
    json_path = tmp_path / "report.json"
    triage_audit.main([
        "--effectiveness", str(eff),
        "--findings", str(fin),
        "--dismissals", str(dis),
        "--json", str(json_path),
    ])
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "unaccounted" in data
    assert len(data["unaccounted"]) == 1
