"""Characterization tests for scripts/ledger.py.

Covers the pure ledger functions (load / save / upsert / review-trigger /
filter / day-math) directly, then drives the CLI through
``ledger.main([...])`` against a ``tmp_path`` ledger JSON via
``--ledger-path`` / ``--repo-root``. ``update --metrics-loc`` is used so
no test path shells out to git.
"""
from __future__ import annotations

import json

import pytest

import ledger


# ---- load / save ---------------------------------------------------------

def test_load_ledger_absent_returns_empty(tmp_path):
    data = ledger.load_ledger(tmp_path / "nope.json")
    assert data == {"version": ledger.LEDGER_VERSION, "entries": {}}


def test_load_ledger_empty_file_returns_empty(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("", encoding="utf-8")
    assert ledger.load_ledger(p)["entries"] == {}


def test_load_ledger_malformed_raises(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("not json at all", encoding="utf-8")
    with pytest.raises(RuntimeError):
        ledger.load_ledger(p)


def test_load_ledger_missing_entries_key_raises(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        ledger.load_ledger(p)


def test_save_and_reload_round_trip(tmp_path):
    p = tmp_path / "ledger.json"
    data = {"version": 1, "entries": {"core/x.py": {"decision": "monitor"}}}
    ledger.save_ledger(data, p)
    assert ledger.load_ledger(p) == data


# ---- upsert_entry --------------------------------------------------------

def test_upsert_entry_inserts(tmp_path):
    led = {"version": 1, "entries": {}}
    entry = ledger.upsert_entry(led, "core/x.py", decision="monitor", rationale="watch it")
    assert entry["decision"] == "monitor"
    assert entry["history"] == []
    assert led["entries"]["core/x.py"]["rationale"] == "watch it"


def test_upsert_entry_rejects_invalid_decision():
    led = {"version": 1, "entries": {}}
    with pytest.raises(ValueError):
        ledger.upsert_entry(led, "core/x.py", decision="bogus", rationale="x")


def test_upsert_entry_snapshots_history():
    led = {"version": 1, "entries": {}}
    ledger.upsert_entry(
        led, "core/x.py", decision="monitor", rationale="first",
        today="2026-01-01", now="2026-01-01T00:00:00Z",
    )
    entry = ledger.upsert_entry(led, "core/x.py", decision="split_queued", rationale="second")
    assert len(entry["history"]) == 1
    assert entry["history"][0]["decision"] == "monitor"
    assert entry["history"][0]["rationale"] == "first"


# ---- entries_needing_review ----------------------------------------------

def test_entries_needing_review_age_trigger():
    led = {"version": 1, "entries": {
        "core/x.py": {
            "last_reviewed": "2026-01-01", "decision": "monitor",
            "metrics_at_review": {"loc": 100}, "next_review_threshold": {},
        },
    }}
    out = ledger.entries_needing_review(led, since_days=30, today="2026-06-01")
    assert [e["path"] for e in out] == ["core/x.py"]


def test_entries_needing_review_skips_planned_decisions():
    led = {"version": 1, "entries": {
        "core/x.py": {
            "last_reviewed": "2020-01-01", "decision": "split_queued",
            "metrics_at_review": {"loc": 100}, "next_review_threshold": {},
        },
    }}
    out = ledger.entries_needing_review(led, since_days=30, today="2026-06-01")
    assert out == []


# ---- filter_entries ------------------------------------------------------

def test_filter_entries_by_single_decision():
    led = {"version": 1, "entries": {
        "a.py": {"decision": "monitor", "metrics_at_review": {"loc": 100}},
        "b.py": {"decision": "split_queued", "metrics_at_review": {"loc": 200}},
    }}
    out = ledger.filter_entries(led, decision="monitor")
    assert [p for p, _ in out] == ["a.py"]


def test_filter_entries_by_comma_string():
    led = {"version": 1, "entries": {
        "a.py": {"decision": "monitor", "metrics_at_review": {"loc": 100}},
        "b.py": {"decision": "split_queued", "metrics_at_review": {"loc": 200}},
    }}
    out = ledger.filter_entries(led, decision="monitor,split_queued")
    assert sorted(p for p, _ in out) == ["a.py", "b.py"]


def test_filter_entries_above_loc():
    led = {"version": 1, "entries": {
        "a.py": {"decision": "monitor", "metrics_at_review": {"loc": 100}},
        "b.py": {"decision": "monitor", "metrics_at_review": {"loc": 900}},
    }}
    out = ledger.filter_entries(led, above_loc=500)
    assert [p for p, _ in out] == ["b.py"]


# ---- _days_between -------------------------------------------------------

def test_days_between_basic():
    assert ledger._days_between("2026-01-01", "2026-01-31") == 30


def test_days_between_none_is_huge():
    assert ledger._days_between(None, "2026-01-01") == 10**6


def test_days_between_unparseable_is_zero():
    assert ledger._days_between("garbage", "2026-01-01") == 0


# ---- drift_scan ----------------------------------------------------------

def test_drift_scan_flags_untracked_big_file(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"x{i} = {i}" for i in range(60)) + "\n", encoding="utf-8")
    out = ledger.drift_scan({"version": 1, "entries": {}}, tmp_path, tmp_path, above_loc=50)
    assert [e["path"] for e in out] == ["big.py"]


def test_drift_scan_skips_tracked_file(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"x{i} = {i}" for i in range(60)) + "\n", encoding="utf-8")
    led = {"version": 1, "entries": {"big.py": {"decision": "monitor"}}}
    out = ledger.drift_scan(led, tmp_path, tmp_path, above_loc=50)
    assert out == []


# ---- main CLI ------------------------------------------------------------

def test_main_update_then_show(tmp_path, capsys):
    lp = tmp_path / "ledger.json"
    rc = ledger.main(
        ["--ledger-path", str(lp), "--repo-root", str(tmp_path), "update", "core/x.py",
         "--decision", "monitor", "--rationale", "keep an eye", "--metrics-loc", "1234"]
    )
    assert rc == 0
    capsys.readouterr()
    rc = ledger.main(
        ["--ledger-path", str(lp), "--repo-root", str(tmp_path), "show", "core/x.py"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "monitor" in out
    assert "1234" in out


def test_main_list_empty_exit_1(tmp_path):
    rc = ledger.main(["--ledger-path", str(tmp_path / "ledger.json"), "list"])
    assert rc == 1


def test_main_show_missing_exit_1(tmp_path, capsys):
    rc = ledger.main(["--ledger-path", str(tmp_path / "ledger.json"), "show", "core/ghost.py"])
    assert rc == 1
    assert "no entry" in capsys.readouterr().err


def test_main_update_invalid_decision_rejected(tmp_path):
    """The CLI rejects an out-of-vocabulary decision via argparse choices."""
    with pytest.raises(SystemExit):
        ledger.main(
            ["--ledger-path", str(tmp_path / "ledger.json"), "update", "core/x.py",
             "--decision", "bogus", "--rationale", "x"]
        )


def test_main_drift_scan_finds_big_file(tmp_path, capsys):
    src = tmp_path / "core"
    src.mkdir()
    (src / "big.py").write_text(
        "\n".join(f"x{i} = 1" for i in range(120)) + "\n", encoding="utf-8"
    )
    rc = ledger.main(
        ["--ledger-path", str(tmp_path / "ledger.json"), "--repo-root", str(tmp_path),
         "drift-scan", "core", "--above-loc", "50"]
    )
    assert rc == 0
    assert "big.py" in capsys.readouterr().out
