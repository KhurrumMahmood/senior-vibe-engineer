from __future__ import annotations

import json
from pathlib import Path

import skill_meta
from _lib.skill_catalog import CatalogError


def _write_skill(skills_dir: Path, name: str, *, job: str) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"""---
name: {name}
description: Test skill for the {job} job.
argument-hint: "<target>"
allowed-tools: Read
user-invocable: true
tier: maintenance
job: {job}
best_for: |
  Exercising the {job} job enum in a complete skill contract.
not_for: |
  Production use; this fixture only validates frontmatter.
language: any
framework: any
---

# /{name}

Fixture body.
""",
        encoding="utf-8",
    )


def test_construct_and_diagnose_are_valid_skill_jobs(tmp_path, capsys):
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "construct-fixture", job="construct")
    _write_skill(skills_dir, "diagnose-fixture", job="diagnose")

    rc = skill_meta.main(["--skills-dir", str(skills_dir), "lint", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"] == []
    assert sorted(payload["skills_with_new_contract"]) == [
        "construct-fixture",
        "diagnose-fixture",
    ]


def test_versioned_contract_is_validated_by_canonical_registry(tmp_path, capsys):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "bad-capability"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        """---
name: bad-capability
description: Strict capability fixture.
argument-hint: "<target>"
allowed-tools: Read
user-invocable: true
tier: maintenance
job: suspect
best_for: Strict schema validation.
not_for: Production use.
language: any
framework: any
capability_contract: 1
layer: framework
binding: react
support: verified
capabilities: [analysis.telepathy]
capability_evidence:
  python: [test:python-fixture]
portable_subjects: [python, typescript]
scans: [css]
---
""",
        encoding="utf-8",
    )

    rc = skill_meta.main(["--skills-dir", str(skills_dir), "lint", "--json"])

    assert rc == 1
    errors = json.loads(capsys.readouterr().out)["errors"]
    assert any("invalid names" in error for error in errors)
    assert any("binding 'react'" in error for error in errors)
    assert any("every portable subject" in error for error in errors)
    assert any("no registered adapter or shim" in error for error in errors)
    assert any("executable skill script" in error for error in errors)


def test_catalog_inventory_errors_are_part_of_metadata_lint(
    tmp_path, capsys, monkeypatch
):
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "construct-fixture", job="construct")
    inventory = tmp_path / "inventory.yml"
    inventory.write_text("schema_version: 1\nskills: []\n", encoding="utf-8")

    def fail_catalog(*args, **kwargs):
        raise CatalogError("inventory does not cover the discovered skill")

    monkeypatch.setattr(skill_meta, "load_catalog", fail_catalog)
    rc = skill_meta.main([
        "--skills-dir",
        str(skills_dir),
        "--catalog-inventory",
        str(inventory),
        "lint",
        "--json",
    ])

    assert rc == 1
    errors = json.loads(capsys.readouterr().out)["errors"]
    assert errors == [
        f"{inventory}: inventory does not cover the discovered skill"
    ]
