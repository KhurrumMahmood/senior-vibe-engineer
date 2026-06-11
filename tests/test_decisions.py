"""Characterization tests for scripts/decisions.py.

Drives the ADR-registry CLI through ``decisions.main([...])`` against a
``tmp_path``-seeded decisions directory. ``rebuild`` and ``link-check``
read the module-level ``REPO_ROOT`` constant directly (unguarded
``relative_to`` / path resolution), so those tests monkeypatch it to
``tmp_path``; every other subcommand takes the directory via
``--decisions-dir``.

The ``host:`` link-check branch is pinned explicitly — a host-scoped
applies_to path is advisory when absent (exit 0) and silently OK when
the host file is present, while a bare path is hard drift when absent
(exit 1).
"""
from __future__ import annotations

import datetime
import json

import decisions


def _ddir(tmp_path):
    return tmp_path / "ai-docs" / "decisions"


# ---- init ----------------------------------------------------------------

def test_init_scaffolds_first_adr(tmp_path):
    d = _ddir(tmp_path)
    rc = decisions.main(
        ["--decisions-dir", str(d), "init", "use-text-choices", "--date", "2026-01-01"]
    )
    assert rc == 0
    files = list(d.glob("*.md"))
    assert [f.name for f in files] == ["0001-use-text-choices.md"]
    assert 'id: "0001"' in files[0].read_text(encoding="utf-8")


def test_init_auto_increments_id(tmp_path, write_adr):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="first")
    write_adr(d, id="0002", slug="second")
    rc = decisions.main(["--decisions-dir", str(d), "init", "third"])
    assert rc == 0
    assert (d / "0003-third.md").exists()


def test_init_rejects_bad_slug(tmp_path, capsys):
    rc = decisions.main(["--decisions-dir", str(_ddir(tmp_path)), "init", "Bad Slug"])
    assert rc == 2
    assert "invalid slug" in capsys.readouterr().err


# ---- list / show ---------------------------------------------------------

def test_list_empty(tmp_path, capsys):
    rc = decisions.main(["--decisions-dir", str(_ddir(tmp_path)), "list"])
    assert rc == 0
    assert "(no decisions)" in capsys.readouterr().out


def test_list_renders_each_decision(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", title="Alpha Decision")
    write_adr(d, id="0002", slug="beta", title="Beta Decision")
    rc = decisions.main(["--decisions-dir", str(d), "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Alpha Decision" in out
    assert "Beta Decision" in out


def test_list_json(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", title="Alpha Decision")
    rc = decisions.main(["--decisions-dir", str(d), "list", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["id"] == "0001"
    assert payload[0]["title"] == "Alpha Decision"
    assert "path" not in payload[0]


def test_show_found(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0007", slug="gamma", title="Gamma Decision")
    rc = decisions.main(["--decisions-dir", str(d), "show", "7"])
    assert rc == 0
    assert "Gamma Decision" in capsys.readouterr().out


def test_show_not_found(tmp_path, capsys):
    rc = decisions.main(["--decisions-dir", str(_ddir(tmp_path)), "show", "999"])
    assert rc == 1
    assert "no decision matches" in capsys.readouterr().err


# ---- audit ---------------------------------------------------------------

def test_audit_clean(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="accepted")
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 0
    assert "no drift" in capsys.readouterr().out


def test_audit_invalid_status(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="bogus")
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 1
    assert "invalid status" in capsys.readouterr().out


def test_audit_stale_proposed(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="proposed", date="2020-01-01")
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 1
    assert "proposed for" in capsys.readouterr().out


def test_audit_fresh_proposed_is_clean(tmp_path, write_adr):
    d = _ddir(tmp_path)
    today = datetime.date.today().isoformat()
    write_adr(d, id="0001", slug="alpha", status="proposed", date=today)
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 0


def test_audit_malformed_date(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="proposed", date="not-a-date")
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 1
    assert "malformed date" in capsys.readouterr().out


def test_audit_broken_supersedes(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", supersedes=["0099"])
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 1
    assert "0099" in capsys.readouterr().out


def test_audit_json_exit_code(tmp_path, write_adr, capsys):
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="bogus")
    rc = decisions.main(["--decisions-dir", str(d), "audit", "--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["drift_count"] == 1


# ---- rebuild -------------------------------------------------------------

def test_rebuild_writes_index(tmp_path, write_adr, monkeypatch):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", title="Alpha")
    index_path = tmp_path / "reports" / "architecture" / "decision-index.json"
    rc = decisions.main(
        ["--decisions-dir", str(d), "--index-path", str(index_path), "rebuild"]
    )
    assert rc == 0
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["decisions"][0]["id"] == "0001"
    assert payload["decisions"][0]["path"] == "ai-docs/decisions/0001-alpha.md"


# ---- link-check ----------------------------------------------------------

def test_link_check_clean(tmp_path, write_adr, monkeypatch, capsys):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha")
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 0
    assert "all links resolve" in capsys.readouterr().out


def test_link_check_broken_supersedes(tmp_path, write_adr, monkeypatch, capsys):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", supersedes=["0099"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 1
    assert "not found" in capsys.readouterr().out


def test_link_check_bare_applies_to_absent_is_drift(tmp_path, write_adr, monkeypatch, capsys):
    """A non-host applies_to path that does not exist is hard drift (exit 1)."""
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", applies_to=["core/missing.py"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 1
    assert "path does not exist" in capsys.readouterr().out


def test_link_check_host_applies_to_absent_is_advisory(tmp_path, write_adr, monkeypatch, capsys):
    """A host:-scoped applies_to path that is absent is advisory, not drift."""
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", applies_to=["host:app/missing.py"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "advisory" in out
    assert "host-scoped" in out


def test_link_check_host_applies_to_present_is_silent_ok(tmp_path, write_adr, monkeypatch, capsys):
    """When the host file IS present, link-check resolves it silently — no advisory."""
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "real.py").write_text("x = 1\n", encoding="utf-8")
    write_adr(d, id="0001", slug="alpha", applies_to=["host:app/real.py"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "advisory" not in out
    assert "host-scoped" not in out


# ---- embodied_by (ADR 0033) ------------------------------------------------

def test_audit_accepted_empty_embodiment_is_drift(tmp_path, write_adr, capsys):
    """An accepted ADR with an empty embodied_by is hard drift (exit 1)."""
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", status="accepted", embodied_by=[])
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 1
    assert "embodied_by is empty" in capsys.readouterr().out


def test_audit_proposed_empty_embodiment_is_clean(tmp_path, write_adr):
    """A proposed ADR may leave embodied_by empty — that IS the not-yet-built state."""
    d = _ddir(tmp_path)
    today = datetime.date.today().isoformat()
    write_adr(d, id="0001", slug="alpha", status="proposed", date=today, embodied_by=[])
    rc = decisions.main(["--decisions-dir", str(d), "audit"])
    assert rc == 0


def test_link_check_embodiment_unknown_kind_is_drift(tmp_path, write_adr, monkeypatch, capsys):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", embodied_by=["widget:foo"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 1
    assert "must be <kind>:<ref>" in capsys.readouterr().out


def test_link_check_embodiment_missing_skill_is_drift(tmp_path, write_adr, monkeypatch, capsys):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", embodied_by=["skill:ghost"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().out


def test_link_check_embodiment_resolving_skill_is_silent(tmp_path, write_adr, monkeypatch, capsys):
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    skill_dir = tmp_path / ".claude" / "skills" / "real-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: real-skill\n---\n", encoding="utf-8")
    write_adr(d, id="0001", slug="alpha", embodied_by=["skill:real-skill"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 0
    assert "does not exist" not in capsys.readouterr().out


def test_link_check_embodiment_pending_is_advisory(tmp_path, write_adr, monkeypatch, capsys):
    """A pending: ref is the decided-but-unbuilt backlog — advisory, not drift."""
    monkeypatch.setattr(decisions, "REPO_ROOT", tmp_path)
    d = _ddir(tmp_path)
    write_adr(d, id="0001", slug="alpha", embodied_by=["pending:ai-docs/plans/future.md"])
    rc = decisions.main(["--decisions-dir", str(d), "link-check"])
    assert rc == 0
    assert "decided-but-unbuilt" in capsys.readouterr().out
