"""Characterization tests for scripts/precedents.py.

Exercises ``load_precedents`` (the registry-shape guards) and
``check_precedents`` (field / reference / supersession validation)
directly, then drives the CLI through ``precedents.main([...])`` with a
``tmp_path`` registry + project root. A "clean" precedent needs real
files behind its applies_to / canonical_examples / guards, so ``_project``
seeds them.
"""
from __future__ import annotations

import pytest
import yaml

import precedents


def _project(root):
    """Seed the files a valid precedent's references resolve against."""
    (root / "core").mkdir(parents=True, exist_ok=True)
    (root / "core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".claude" / "skills" / "test-guard").mkdir(parents=True, exist_ok=True)


def _valid_precedent(**over):
    p = {
        "id": "safe-parsing.v1",
        "status": "active",
        "title": "Safe parsing",
        "summary": "Use the safe parser.",
        "applies_to": ["core/x.py"],
        "canonical_examples": ["core/x.py"],
        "guards": ["test-guard"],
        "supersedes": [],
        "superseded_by": None,
    }
    p.update(over)
    return p


def _write_registry(path, entries):
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


# ---- load_precedents -----------------------------------------------------

def test_load_precedents_missing_raises(tmp_path):
    with pytest.raises(precedents.PrecedentError):
        precedents.load_precedents(tmp_path / "nope.yml")


def test_load_precedents_empty_file_is_empty_list(tmp_path):
    reg = tmp_path / "precedents.yml"
    reg.write_text("", encoding="utf-8")
    assert precedents.load_precedents(reg) == []


def test_load_precedents_non_list_raises(tmp_path):
    reg = tmp_path / "precedents.yml"
    reg.write_text("key: value\n", encoding="utf-8")
    with pytest.raises(precedents.PrecedentError):
        precedents.load_precedents(reg)


def test_load_precedents_non_mapping_entry_raises(tmp_path):
    reg = tmp_path / "precedents.yml"
    reg.write_text("- just a string\n", encoding="utf-8")
    with pytest.raises(precedents.PrecedentError):
        precedents.load_precedents(reg)


def test_load_precedents_valid(tmp_path):
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent()])
    loaded = precedents.load_precedents(reg)
    assert [p["id"] for p in loaded] == ["safe-parsing.v1"]


# ---- check_precedents ----------------------------------------------------

def test_check_precedents_clean(tmp_path):
    _project(tmp_path)
    assert precedents.check_precedents([_valid_precedent()], tmp_path) == []


def test_check_precedents_missing_fields(tmp_path):
    _project(tmp_path)
    diags = precedents.check_precedents([{"id": "partial.v1"}], tmp_path)
    assert any("missing required fields" in d for d in diags)


def test_check_precedents_invalid_id(tmp_path):
    _project(tmp_path)
    diags = precedents.check_precedents([_valid_precedent(id="BadId")], tmp_path)
    assert any("invalid id" in d for d in diags)


def test_check_precedents_invalid_status(tmp_path):
    _project(tmp_path)
    diags = precedents.check_precedents([_valid_precedent(status="bogus")], tmp_path)
    assert any("invalid status" in d for d in diags)


def test_check_precedents_unresolvable_guard(tmp_path):
    _project(tmp_path)
    diags = precedents.check_precedents(
        [_valid_precedent(guards=["does-not-exist"])], tmp_path
    )
    assert any("guard" in d for d in diags)


# ---- main CLI ------------------------------------------------------------

def test_main_check_clean(tmp_path, capsys):
    _project(tmp_path)
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent()])
    rc = precedents.main(
        ["check", "--registry", str(reg), "--project-root", str(tmp_path)]
    )
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_main_check_drift_exit_1(tmp_path):
    _project(tmp_path)
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent(status="bogus")])
    rc = precedents.main(
        ["check", "--registry", str(reg), "--project-root", str(tmp_path)]
    )
    assert rc == 1


def test_main_list(tmp_path, capsys):
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent()])
    rc = precedents.main(
        ["list", "--registry", str(reg), "--project-root", str(tmp_path)]
    )
    assert rc == 0
    assert "safe-parsing.v1" in capsys.readouterr().out


def test_main_show_found(tmp_path, capsys):
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent()])
    rc = precedents.main(
        ["show", "--registry", str(reg), "--project-root", str(tmp_path), "safe-parsing.v1"]
    )
    assert rc == 0
    assert "safe-parsing.v1" in capsys.readouterr().out


def test_main_show_not_found(tmp_path, capsys):
    reg = _write_registry(tmp_path / "precedents.yml", [_valid_precedent()])
    rc = precedents.main(
        ["show", "--registry", str(reg), "--project-root", str(tmp_path), "ghost.v1"]
    )
    assert rc == 1
    assert "no precedent matches" in capsys.readouterr().err
