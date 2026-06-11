"""Characterization tests for scripts/specs.py.

``specs.py`` is the largest substrate script (2200+ LOC); this suite is
deliberately core-path only — the pure parsing / sizing / code-root
functions plus the non-git subcommands driven through ``specs.main([...])``
with ``--specs-dir`` / ``--repo-root`` / ``--index-path`` overrides.

The git-grep-free subcommands (``rebuild`` / ``audit``) need no tmp git
repo: ``specs.py`` imports no ``subprocess`` and greps code with a Python
regex pass. The ``resolve_code_roots`` rejection paths (absolute roots,
``../`` climbs) are pinned because they are a path-traversal guard.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import specs


def _spec(loc):
    """Build a minimal Spec object for size-audit tests."""
    return specs.Spec(
        spec_id="sample",
        path=Path("sample.md"),
        frontmatter={},
        title="Sample",
        status="draft",
        code_roots=[],
        last_audited=None,
        loc=loc,
    )


# ---- audit_size ----------------------------------------------------------

def test_audit_size_ok():
    assert specs.audit_size(_spec(100))["level"] == "ok"


def test_audit_size_soft_warn():
    assert specs.audit_size(_spec(600))["level"] == "soft_warn"


def test_audit_size_hard_error():
    assert specs.audit_size(_spec(1200))["level"] == "hard_error"


# ---- parse_checklist_items ----------------------------------------------

def test_parse_checklist_items_extracts_marks():
    body = (
        "## Implementation\n"
        "- [ ] IM-1: not started\n"
        "- [x] IM-2: done\n"
        "- [~] AR-1: partial\n"
        "not a checklist line\n"
    )
    items = specs.parse_checklist_items(body)
    by_id = {it.item_id: it for it in items}
    assert len(items) == 3
    assert by_id["IM-1"].status == " "
    assert by_id["IM-2"].status == "x"
    assert by_id["AR-1"].status == "~"
    assert by_id["IM-2"].section == "IM"
    assert by_id["IM-1"].description == "not started"


def test_parse_checklist_items_lr_section():
    items = specs.parse_checklist_items("- [x] LR-U-3: a learning\n")
    assert len(items) == 1
    assert items[0].section == "LR-U"


# ---- _coerce_date_str ----------------------------------------------------

def test_coerce_date_str_none():
    assert specs._coerce_date_str(None) is None


def test_coerce_date_str_date_object():
    assert specs._coerce_date_str(datetime.date(2026, 1, 2)) == "2026-01-02"


def test_coerce_date_str_passthrough():
    assert specs._coerce_date_str("2026-03-04") == "2026-03-04"


# ---- _default_title_from_id ----------------------------------------------

def test_default_title_from_id():
    assert specs._default_title_from_id("crawling-views") == "Crawling Views"
    assert specs._default_title_from_id("async_tasks") == "Async Tasks"


# ---- resolve_code_roots --------------------------------------------------

def test_resolve_code_roots_accepts_relative(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    resolved = specs.resolve_code_roots(tmp_path, ["core/x.py"])
    assert len(resolved) == 1
    assert resolved[0].name == "x.py"


def test_resolve_code_roots_rejects_absolute(tmp_path, capsys):
    resolved = specs.resolve_code_roots(tmp_path, ["/etc/passwd"])
    assert resolved == []
    assert "absolute" in capsys.readouterr().err


def test_resolve_code_roots_rejects_escaping(tmp_path, capsys):
    resolved = specs.resolve_code_roots(tmp_path, ["../../etc"])
    assert resolved == []
    assert "outside" in capsys.readouterr().err


# ---- find_spec_files -----------------------------------------------------

def test_find_spec_files_excludes_index_and_readme(tmp_path):
    (tmp_path / "real-spec.md").write_text("---\nid: real-spec\n---\n", encoding="utf-8")
    (tmp_path / "INDEX.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    found = specs.find_spec_files(tmp_path)
    assert [p.name for p in found] == ["real-spec.md"]


# ---- load_spec / load_all_specs ------------------------------------------

def test_load_spec_parses_frontmatter_and_items(tmp_path, write_spec):
    path = write_spec(
        tmp_path, spec_id="parsed-spec", status="active", code_roots=["core/x.py"],
        body="## Implementation\n- [x] IM-1: done\n",
    )
    spec = specs.load_spec(path)
    assert spec.spec_id == "parsed-spec"
    assert spec.status == "active"
    assert spec.code_roots == ["core/x.py"]
    assert [it.item_id for it in spec.items] == ["IM-1"]


def test_load_all_specs_skips_malformed(tmp_path, write_spec, capsys):
    write_spec(tmp_path, spec_id="good-spec")
    (tmp_path / "broken.md").write_text("---\nkey: [unclosed\n---\nbody\n", encoding="utf-8")
    loaded = specs.load_all_specs(tmp_path)
    assert [s.spec_id for s in loaded] == ["good-spec"]
    assert "skipping broken.md" in capsys.readouterr().err


# ---- main: list / show ---------------------------------------------------

def test_cmd_list_empty(tmp_path, capsys):
    s = tmp_path / "specs"
    s.mkdir()
    rc = specs.main(["--specs-dir", str(s), "list"])
    assert rc == 1
    assert "no specs match" in capsys.readouterr().err


def test_cmd_list_renders(tmp_path, write_spec, capsys):
    write_spec(tmp_path, spec_id="alpha-spec", title="Alpha Spec")
    rc = specs.main(["--specs-dir", str(tmp_path), "list"])
    assert rc == 0
    assert "alpha-spec" in capsys.readouterr().out


def test_cmd_list_json(tmp_path, write_spec, capsys):
    write_spec(tmp_path, spec_id="alpha-spec", status="active")
    rc = specs.main(["--specs-dir", str(tmp_path), "list", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["id"] == "alpha-spec"


def test_cmd_show_found(tmp_path, write_spec, capsys):
    write_spec(
        tmp_path, spec_id="alpha-spec", body="## Implementation\n- [x] IM-1: done\n"
    )
    rc = specs.main(
        ["--specs-dir", str(tmp_path), "--repo-root", str(tmp_path), "show", "alpha-spec"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha-spec" in out
    assert "IM-1" in out


def test_cmd_show_not_found(tmp_path, capsys):
    rc = specs.main(["--specs-dir", str(tmp_path), "show", "ghost"])
    assert rc == 1
    assert "no spec with id" in capsys.readouterr().err


# ---- main: size-check ----------------------------------------------------

def test_cmd_size_check_clean(tmp_path, write_spec, capsys):
    write_spec(tmp_path, spec_id="small-spec")
    rc = specs.main(["--specs-dir", str(tmp_path), "size-check"])
    assert rc == 0
    assert "under" in capsys.readouterr().out


def test_cmd_size_check_hard_error(tmp_path, write_spec, capsys):
    big_body = "# Big\n\n" + "\n".join(f"line {i}" for i in range(1100))
    write_spec(tmp_path, spec_id="huge-spec", body=big_body)
    rc = specs.main(["--specs-dir", str(tmp_path), "size-check"])
    assert rc == 1
    assert "hard_error" in capsys.readouterr().out


# ---- main: init ----------------------------------------------------------

def test_cmd_init_scaffolds_spec(tmp_path):
    s = tmp_path / "specs"
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    rc = specs.main(
        ["--specs-dir", str(s), "--repo-root", str(tmp_path), "init", "new-spec",
         "--code-roots", "core/x.py", "--date", "2026-01-01"]
    )
    assert rc == 0
    text = (s / "new-spec.md").read_text(encoding="utf-8")
    assert "id: new-spec" in text
    assert "status: STUB" in text


def test_cmd_init_rejects_missing_code_root(tmp_path, capsys):
    s = tmp_path / "specs"
    rc = specs.main(
        ["--specs-dir", str(s), "--repo-root", str(tmp_path), "init", "new-spec",
         "--code-roots", "core/ghost.py"]
    )
    assert rc == 2
    assert "do not exist" in capsys.readouterr().err


def test_cmd_init_allow_missing(tmp_path):
    s = tmp_path / "specs"
    rc = specs.main(
        ["--specs-dir", str(s), "--repo-root", str(tmp_path), "init", "new-spec",
         "--code-roots", "core/ghost.py", "--allow-missing"]
    )
    assert rc == 0
    assert (s / "new-spec.md").exists()


def test_cmd_init_rejects_bad_id(tmp_path, capsys):
    s = tmp_path / "specs"
    rc = specs.main(
        ["--specs-dir", str(s), "--repo-root", str(tmp_path), "init", "Bad Id",
         "--code-roots", "core/x.py"]
    )
    assert rc == 2
    assert "invalid spec id" in capsys.readouterr().err


# ---- main: rebuild / audit -----------------------------------------------

def test_cmd_rebuild_writes_index(tmp_path, write_spec):
    write_spec(tmp_path, spec_id="idx-spec")
    index_path = tmp_path / "out" / "spec-index.json"
    rc = specs.main(
        ["--specs-dir", str(tmp_path), "--repo-root", str(tmp_path),
         "--index-path", str(index_path), "rebuild"]
    )
    assert rc == 0
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert "idx-spec" in payload["specs"]


def test_cmd_audit_clean(tmp_path, write_spec, capsys):
    write_spec(tmp_path, spec_id="audited-spec")
    rc = specs.main(["--specs-dir", str(tmp_path), "--repo-root", str(tmp_path), "audit"])
    assert rc == 0
    assert "Audited 1 spec" in capsys.readouterr().out
