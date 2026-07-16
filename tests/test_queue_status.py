"""Queue contract round-trip (spec IM-8, plan §2 criterion 6).

A staged packet file causes the session-start hook to report a pending
count, and the documented manual-pickup command lists the same item.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sweep.schemas import validate_packet

REPO_ROOT = Path(__file__).resolve().parents[1]
FINDING_ID = "f2_0123456789abcdef01234567"


def _packet() -> dict:
    return {
        "schema_version": 1,
        "finding_ids": [FINDING_ID],
        "scope": ["app/a.py"],
        "recipe": "remove the finding",
        "verification": ".venv/bin/python -m pytest -q tests/test_a.py",
        "expected_delta": {"fixed": [FINDING_ID], "allowed_new": [], "metrics": []},
        "token_budget": 8_000,
        "manifest_hash": "a" * 64,
        "judgment_hash": "b" * 64,
    }


def _load_queue_mod():
    spec = importlib.util.spec_from_file_location(
        "queue_status_mod", REPO_ROOT / "scripts" / "queue_status.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stage_hook_list_roundtrip(tmp_path, capsys):
    q = _load_queue_mod()

    # empty queue: hook is silent, list says empty
    assert q.main(["--root", str(tmp_path), "hook"]) == 0
    assert capsys.readouterr().out == ""
    assert q.main(["--root", str(tmp_path), "list"]) == 0
    assert "queue empty" in capsys.readouterr().out

    # stage a legacy flat item; new sweep items use stage-sweep below
    rc = q.main([
        "--root", str(tmp_path), "stage", "fix-dispatch",
        "--recipe", "collapse the 30-branch dispatch",
        "--scope", "app/b.py", "--scope", "app/a.py",
        "--verification", "pytest -q tests/test_dispatch.py",
        "--expected-delta", "1 fixed, 0 new",
        "--token-budget", "35000",
        "--origin", "reports/unify-shadows/SC-3/proposal.md",
    ])
    assert rc == 0
    item_path = tmp_path / ".engineering" / "local" / "queue" / "fix-dispatch.json"
    item = json.loads(item_path.read_text())
    assert item["scope"] == ["app/a.py", "app/b.py"]  # packet field, sorted
    assert item["recipe"] and item["verification"] and item["token_budget"] == 35000
    assert item["status"] == "staged" and item["staged_at"]
    capsys.readouterr()

    # hook reports the pending count; list shows the same item
    assert q.main(["--root", str(tmp_path), "hook"]) == 0
    hook_line = capsys.readouterr().out
    assert "1 staged work item(s) pending" in hook_line and "fix-dispatch" in hook_line
    assert q.main(["--root", str(tmp_path), "list"]) == 0
    assert "fix-dispatch" in capsys.readouterr().out

    # the projection's queue section sees it too
    spec = importlib.util.spec_from_file_location(
        "status_mod_q", REPO_ROOT / "scripts" / "status.py"
    )
    status_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(status_mod)
    section = status_mod.build_status(tmp_path)["sections"]["queue"]
    assert section["count"] == 1
    assert section["items"][0]["id"] == "fix-dispatch"


def test_stage_rejects_unsafe_id(tmp_path, capsys):
    q = _load_queue_mod()
    assert q.main(["--root", str(tmp_path), "stage", "///", "--recipe", "r"]) == 2


def test_stage_sweep_validates_and_preserves_closed_packet_with_separate_metadata(
    tmp_path, capsys
):
    q = _load_queue_mod()
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(_packet()))

    assert q.main([
        "--root", str(tmp_path), "stage-sweep", "sweep-one",
        "--packet", str(packet_path), "--origin", "sweep:test",
    ]) == 0
    staged = json.loads(
        (tmp_path / ".engineering" / "local" / "queue" / "sweep-one.json").read_text()
    )
    assert staged["kind"] == "sweep_packet"
    assert staged["origin"] == "sweep:test"
    assert staged["status"] == "staged" and staged["staged_at"]
    assert validate_packet(staged["packet"]) == _packet()
    assert not ({"recipe", "scope", "expected_delta"} & set(staged))

    capsys.readouterr()
    assert q.main(["--root", str(tmp_path), "list"]) == 0
    listed = capsys.readouterr().out
    assert "sweep-one" in listed and "remove the finding" in listed


def test_stage_sweep_rejects_loose_and_over_budget_packets(tmp_path, capsys):
    q = _load_queue_mod()
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps({"recipe": "loose bypass", "scope": ["app/a.py"]}))
    assert q.main([
        "--root", str(tmp_path), "stage-sweep", "bad", "--packet", str(packet_path)
    ]) == 2
    assert not (tmp_path / ".engineering" / "local" / "queue" / "bad.json").exists()

    packet_path.write_text(json.dumps({**_packet(), "token_budget": 100_001}))
    assert q.main([
        "--root", str(tmp_path), "stage-sweep", "too-large", "--packet", str(packet_path)
    ]) == 2
    assert "deterministic ceiling" in capsys.readouterr().err


def test_hook_surfaces_silent_non_terminal_plans(tmp_path, capsys):
    """W-G (consistency-session-execution): the session-start hook flags
    non-terminal plans gone silent >14 days; terminal/fresh plans stay quiet."""
    import os
    import time

    q = _load_queue_mod()
    plans = tmp_path / "ai-docs" / "plans"
    plans.mkdir(parents=True)
    old = time.time() - 30 * 86400
    for name, status in (("stalled-a", "scoped"), ("done-b", "promoted")):
        p = plans / f"{name}.md"
        p.write_text(f"---\nname: {name}\nstatus: {status}\n---\n\n# {name}\n")
        os.utime(p, (old, old))
    fresh = plans / "fresh-c.md"
    fresh.write_text("---\nname: fresh-c\nstatus: scoped\n---\n\n# c\n")

    assert q.main(["--root", str(tmp_path), "hook"]) == 0
    out = capsys.readouterr().out
    assert "stalled-a (scoped)" in out
    assert "done-b" not in out and "fresh-c" not in out
