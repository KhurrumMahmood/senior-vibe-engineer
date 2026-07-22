from __future__ import annotations

import json
from pathlib import Path

import skill_meta


def _write_skill(skills_dir: Path, name: str, *, job: str, extra: str = "") -> None:
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
{extra}---

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


def test_install_with_requires_distinct_nonempty_companion_names(tmp_path, capsys):
    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "valid-fixture",
        job="diagnose",
        extra="install_with: [companion-fixture]\n",
    )
    _write_skill(
        skills_dir,
        "invalid-fixture",
        job="diagnose",
        extra="install_with: [invalid-fixture, invalid-fixture]\n",
    )

    rc = skill_meta.main(["--skills-dir", str(skills_dir), "lint", "--json"])

    assert rc == 1
    errors = json.loads(capsys.readouterr().out)["errors"]
    assert any("contains duplicate companion skills" in error for error in errors)
    assert any("must not contain the skill itself" in error for error in errors)
