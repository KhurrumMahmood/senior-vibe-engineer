from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from lint.no_core_framework_leakage import (
    _add_core_companions,
    AllowlistError,
    Document,
    collect_changed_documents,
    lint_documents,
    load_allowlist,
    load_framework_vocabulary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/wp3/core_leakage"
REGISTRY = REPO_ROOT / ".claude/skills/_common/capability-registry.yml"


def _frontmatter(**updates: object) -> dict:
    metadata = {
        "name": "portable-planner",
        "description": "Portable planning procedure.",
        "argument-hint": "<goal>",
        "allowed-tools": "Read",
        "user-invocable": True,
        "tier": "feature",
        "job": "plan",
        "best_for": "Planning from evidence.",
        "not_for": "Framework-native work.",
        "language": "any",
        "framework": "any",
    }
    metadata.update(updates)
    return metadata


def _skill_text(body: str, **metadata: object) -> str:
    return (
        "---\n"
        + yaml.safe_dump(_frontmatter(**metadata), sort_keys=False)
        + "---\n\n# Portable planner\n\n"
        + body
        + "\n"
    )


def _doc(text: str, *, path: str = ".claude/skills/portable-planner/SKILL.md") -> Document:
    return Document(path=path, text=text, source="worktree")


def _inventory() -> dict:
    return {
        "portable-planner": {
            "name": "portable-planner",
            "path": ".claude/skills/portable-planner/SKILL.md",
            "layer": "core",
            "bindings": ("core", "django"),
            "readiness": "foundation-ready",
            "ar3_foundation_member": True,
        }
    }


def _violations(*documents: Document, allowlist=()) -> list:
    return lint_documents(
        documents,
        inventory=_inventory(),
        vocabulary=load_framework_vocabulary(REGISTRY),
        allowlist=allowlist,
    )


def test_canonical_vocabulary_is_registry_owned_and_boundary_matched():
    vocabulary = load_framework_vocabulary(REGISTRY)

    assert vocabulary["django"] == "django"
    assert vocabulary["celery"] == "django"
    assert vocabulary["react"] == "react"
    assert _violations(_doc(_skill_text("A dJaNgO example.")))
    assert _violations(_doc(_skill_text("A CELERY example.")))
    assert _violations(_doc(_skill_text("A React example.")))
    assert not _violations(_doc(_skill_text("A reactive design and djangoish name.")))


@pytest.mark.parametrize("fixture", ["prose.md", "code-fence.md", "link.md"])
def test_bad_prose_code_and_link_fixtures_fail(fixture):
    body = (FIXTURES / "bad" / fixture).read_text(encoding="utf-8")

    violations = _violations(_doc(_skill_text(body)))

    assert any(item.code == "framework-term" for item in violations)


@pytest.mark.parametrize(
    "field,value",
    [
        ("description", "Plan Django changes."),
        ("best_for", "Celery task refactors."),
        ("not_for", "React implementation work."),
        ("argument-hint", "<django-app>"),
        ("max_overhead", "Stop before CELERY changes."),
    ],
)
def test_every_active_frontmatter_prose_field_is_scanned(field, value):
    violations = _violations(_doc(_skill_text("Neutral body.", **{field: value})))

    assert any(item.code == "framework-term" and item.field == field for item in violations)


def test_declared_binding_is_allowed_but_dishonest_core_framework_is_not():
    binding = _doc(
        (FIXTURES / "good/bindings/django.md").read_text(encoding="utf-8"),
        path=".claude/skills/portable-planner/bindings/django.md",
    )
    core = _doc((FIXTURES / "good/SKILL.md").read_text(encoding="utf-8"))

    assert _violations(core, binding) == []
    dishonest = _violations(_doc(_skill_text("Neutral body.", framework="django")))
    assert any(item.code == "dishonest-frontmatter" for item in dishonest)


def test_undeclared_or_nested_binding_is_rejected():
    undeclared = _doc(
        "# Flask binding\n",
        path=".claude/skills/portable-planner/bindings/flask.md",
    )
    nested = _doc(
        "# Nested binding\n",
        path=".claude/skills/portable-planner/bindings/django/example.md",
    )

    assert any(item.code == "undeclared-binding" for item in _violations(undeclared))
    assert any(item.code == "undeclared-binding" for item in _violations(nested))


def test_binding_cannot_repeat_normalized_core_procedure_text():
    paragraph = (
        "Inspect the complete call graph, preserve every observable behavior, "
        "and record the exact verification result before changing code."
    )
    core = _doc(_skill_text(paragraph))
    binding = _doc(
        f"# Binding\n\n**{paragraph.upper()}**\n",
        path=".claude/skills/portable-planner/bindings/django.md",
    )

    assert any(item.code == "duplicated-core-procedure" for item in _violations(core, binding))


def test_core_only_change_loads_existing_bindings_for_duplication(tmp_path):
    repo = tmp_path / "repo"
    core_path = repo / ".claude/skills/portable-planner/SKILL.md"
    binding_path = repo / ".claude/skills/portable-planner/bindings/django.md"
    core_path.parent.mkdir(parents=True)
    binding_path.parent.mkdir(parents=True)
    paragraph = (
        "Inspect the complete call graph, preserve every observable behavior, "
        "and record the exact verification result before changing code."
    )
    core_path.write_text(_skill_text("Neutral original body."), encoding="utf-8")
    binding_path.write_text(f"# Binding\n\n{paragraph}\n", encoding="utf-8")

    documents = _add_core_companions(
        repo,
        [Document(str(core_path.relative_to(repo)), _skill_text(paragraph), "after")],
        _inventory(),
    )

    assert any(document.path.endswith("bindings/django.md") for document in documents)
    assert any(
        item.code == "duplicated-core-procedure" for item in _violations(*documents)
    )


def _allowlist_payload(*, expires_on: date, **updates: object) -> dict:
    entry = {
        "path": ".claude/skills/portable-planner/SKILL.md",
        "term": "django",
        "owner": "portable-skills-maintainers",
        "reason": "Temporary migration while the selected binding is extracted.",
        "expires_on": expires_on.isoformat(),
    }
    entry.update(updates)
    return {"schema_version": 1, "allowlist": [entry]}


def _write_allowlist(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "allowlist.yml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_allowlist_schema_owner_reason_expiry_and_max_ninety_days(tmp_path):
    today = date(2026, 7, 16)
    valid = load_allowlist(
        _write_allowlist(tmp_path, _allowlist_payload(expires_on=today + timedelta(days=90))),
        vocabulary=load_framework_vocabulary(REGISTRY),
        today=today,
    )
    assert valid[0].owner == "portable-skills-maintainers"

    bad_payloads = [
        _allowlist_payload(expires_on=today + timedelta(days=1), owner=""),
        _allowlist_payload(expires_on=today + timedelta(days=1), reason=""),
        _allowlist_payload(expires_on=today - timedelta(days=1)),
        _allowlist_payload(expires_on=today + timedelta(days=91)),
        _allowlist_payload(expires_on=today + timedelta(days=1), ticket="WP3"),
        {"schema_version": 1, "exceptions": []},
    ]
    for payload in bad_payloads:
        with pytest.raises(AllowlistError):
            load_allowlist(
                _write_allowlist(tmp_path, payload),
                vocabulary=load_framework_vocabulary(REGISTRY),
                today=today,
            )


def test_allowlist_cannot_hide_verified_claim(tmp_path):
    today = date(2026, 7, 16)
    allowlist = load_allowlist(
        _write_allowlist(tmp_path, _allowlist_payload(expires_on=today + timedelta(days=1))),
        vocabulary=load_framework_vocabulary(REGISTRY),
        today=today,
    )
    verified = _doc(
        _skill_text("A Django example.", capability_contract=1, support="verified")
    )

    violations = _violations(verified, allowlist=allowlist)

    assert any(item.code == "verified-claim-allowlist" for item in violations)
    assert any(item.code == "framework-term" for item in violations)


def test_valid_allowlist_temporarily_suppresses_only_its_exact_path_and_term(tmp_path):
    today = date(2026, 7, 16)
    allowlist = load_allowlist(
        _write_allowlist(tmp_path, _allowlist_payload(expires_on=today + timedelta(days=1))),
        vocabulary=load_framework_vocabulary(REGISTRY),
        today=today,
    )

    violations = _violations(
        _doc(_skill_text("A Django and Celery example.")), allowlist=allowlist
    )

    assert not any("Django" in item.message for item in violations)
    assert any("Celery" in item.message for item in violations)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    )
    return result.stdout


def test_renamed_skill_scans_before_and_after_blobs(tmp_path):
    repo = tmp_path / "repo"
    old = repo / ".claude/skills/portable-planner/SKILL.md"
    old.parent.mkdir(parents=True)
    old.write_text(_skill_text("A Django example in the original file."), encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.com")
    _git(repo, "config", "user.name", "Fixture")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    new = repo / ".claude/skills/portable-planner-renamed/SKILL.md"
    new.parent.mkdir(parents=True)
    old.rename(new)
    new.write_text(_skill_text("Neutral replacement body."), encoding="utf-8")
    _git(repo, "add", "-A")

    documents = collect_changed_documents(repo, staged=True)

    assert {(doc.source, doc.path) for doc in documents} == {
        ("before", ".claude/skills/portable-planner/SKILL.md"),
        ("after", ".claude/skills/portable-planner-renamed/SKILL.md"),
    }
    assert "Django example" in next(doc.text for doc in documents if doc.source == "before")
    assert any(item.source == "before" for item in _violations(*documents))


# spec:portable-skill-layer-distribution::IM-6
def test_repository_foundation_set_is_clean_and_routing_surfaces_stay_excluded():
    result = subprocess.run(
        [sys.executable, "scripts/lint/no_core_framework_leakage.py", "--all"],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "16 migrated core skill" in result.stdout


def test_source_aware_guard_is_wired_to_precommit_ci_and_doctrine():
    precommit = REPO_ROOT.joinpath(".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = REPO_ROOT.joinpath(".github/workflows/ci.yml").read_text(encoding="utf-8")
    patterns = REPO_ROOT.joinpath(".claude/docs/canonical-patterns.md").read_text(
        encoding="utf-8"
    )

    assert "no_core_framework_leakage.py --staged" in precommit
    assert "no_core_framework_leakage.py --changed-from" in ci
    assert "core-framework-leakage" in patterns
