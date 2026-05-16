"""Characterization tests for scripts/plans.py.

Drives the plans-registry CLI through ``plans.main([...])`` against a
``tmp_path``-seeded plans directory. ``promote`` shells out to
``specs.py`` via subprocess to scaffold the successor spec; these tests
cover every guard that returns *before* that subprocess call (plan not
found, already promoted, not architected, bad spec id, spec exists) and
leave the subprocess leg as the one boundary not unit-tested here.
"""
from __future__ import annotations

import json

import plans


def _pdir(tmp_path):
    return tmp_path / "ai-docs" / "plans"


# ---- init ----------------------------------------------------------------

def test_init_scaffolds_plan(tmp_path):
    p = _pdir(tmp_path)
    rc = plans.main(["--plans-dir", str(p), "init", "search-revamp", "--date", "2026-01-01"])
    assert rc == 0
    text = (p / "search-revamp.md").read_text(encoding="utf-8")
    assert "name: search-revamp" in text
    assert "status: draft" in text


def test_init_rejects_bad_slug(tmp_path, capsys):
    rc = plans.main(["--plans-dir", str(_pdir(tmp_path)), "init", "Bad Slug"])
    assert rc == 2
    assert "invalid slug" in capsys.readouterr().err


def test_init_existing_without_force(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="dupe")
    rc = plans.main(["--plans-dir", str(p), "init", "dupe"])
    assert rc == 2
    assert "already exists" in capsys.readouterr().err


def test_init_existing_with_force(tmp_path, write_plan):
    p = _pdir(tmp_path)
    write_plan(p, slug="dupe")
    rc = plans.main(["--plans-dir", str(p), "init", "dupe", "--force"])
    assert rc == 0


# ---- list / show ---------------------------------------------------------

def test_list_empty(tmp_path, capsys):
    rc = plans.main(["--plans-dir", str(_pdir(tmp_path)), "list"])
    assert rc == 0
    assert "(no plans)" in capsys.readouterr().out


def test_list_renders_plans(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", title="Alpha Plan")
    rc = plans.main(["--plans-dir", str(p), "list"])
    assert rc == 0
    assert "Alpha Plan" in capsys.readouterr().out


def test_list_json(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", status="scoped")
    rc = plans.main(["--plans-dir", str(p), "list", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["name"] == "alpha-plan"
    assert payload[0]["status"] == "scoped"


def test_show_found(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", title="Alpha Plan")
    rc = plans.main(["--plans-dir", str(p), "show", "alpha-plan"])
    assert rc == 0
    assert "Alpha Plan" in capsys.readouterr().out


def test_show_not_found(tmp_path, capsys):
    rc = plans.main(["--plans-dir", str(_pdir(tmp_path)), "show", "ghost"])
    assert rc == 1
    assert "no plan matches" in capsys.readouterr().err


# ---- audit ---------------------------------------------------------------

def test_audit_clean(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", status="draft")
    rc = plans.main(["--plans-dir", str(p), "audit"])
    assert rc == 0
    assert "no drift" in capsys.readouterr().out


def test_audit_invalid_status(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", status="bogus")
    rc = plans.main(["--plans-dir", str(p), "audit"])
    assert rc == 1
    assert "invalid status" in capsys.readouterr().out


def test_audit_promoted_without_successor_spec(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="alpha-plan", status="promoted")
    rc = plans.main(["--plans-dir", str(p), "audit"])
    assert rc == 1
    assert "successor_spec is unset" in capsys.readouterr().out


def test_audit_successor_spec_missing_file(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    s = tmp_path / "ai-docs" / "specs"
    write_plan(p, slug="alpha-plan", status="promoted", successor_spec="ghost-spec")
    rc = plans.main(["--plans-dir", str(p), "--specs-dir", str(s), "audit"])
    assert rc == 1
    assert "spec file does not exist" in capsys.readouterr().out


def test_audit_motivating_decision_missing(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    dec = tmp_path / "ai-docs" / "decisions"
    write_plan(p, slug="alpha-plan", status="draft", motivating_decision="0042")
    rc = plans.main(["--plans-dir", str(p), "--decisions-dir", str(dec), "audit"])
    assert rc == 1
    assert "ADR does not exist" in capsys.readouterr().out


# ---- promote (guard paths that return before the specs.py subprocess) ----

def test_promote_plan_not_found(tmp_path, capsys):
    rc = plans.main(
        ["--plans-dir", str(_pdir(tmp_path)), "promote", "ghost", "--code-roots", "core/x.py"]
    )
    assert rc == 1
    assert "no plan matches" in capsys.readouterr().err


def test_promote_not_architected_without_force(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="early-plan", status="draft")
    rc = plans.main(
        ["--plans-dir", str(p), "promote", "early-plan", "--code-roots", "core/x.py"]
    )
    assert rc == 2
    assert "not architected" in capsys.readouterr().err


def test_promote_already_promoted(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="done-plan", status="promoted")
    rc = plans.main(
        ["--plans-dir", str(p), "promote", "done-plan", "--code-roots", "core/x.py"]
    )
    assert rc == 2
    assert "cannot re-promote" in capsys.readouterr().err


def test_promote_architected_rejects_bad_spec_id(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    write_plan(p, slug="ready-plan", status="architected")
    rc = plans.main(
        ["--plans-dir", str(p), "promote", "ready-plan",
         "--spec-id", "Bad Id", "--code-roots", "core/x.py"]
    )
    assert rc == 2
    assert "invalid spec id" in capsys.readouterr().err


def test_promote_architected_spec_exists_without_force(tmp_path, write_plan, capsys):
    p = _pdir(tmp_path)
    s = tmp_path / "ai-docs" / "specs"
    s.mkdir(parents=True)
    (s / "ready-plan.md").write_text("---\nid: ready-plan\n---\n", encoding="utf-8")
    write_plan(p, slug="ready-plan", status="architected")
    rc = plans.main(
        ["--plans-dir", str(p), "--specs-dir", str(s), "promote", "ready-plan",
         "--code-roots", "core/x.py"]
    )
    assert rc == 2
    assert "already exists" in capsys.readouterr().err
