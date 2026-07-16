from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from _lib.binding_loader import BindingLoadError, compose_skill_bindings
from _lib.capability_registry import CapabilityRegistry, load_registry
from _lib.host_profile import profile_host
from _lib.skill_catalog import SkillCatalogEntry, load_catalog


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _entry(bindings: tuple[str, ...]) -> SkillCatalogEntry:
    return SkillCatalogEntry(
        name="portable-enum",
        path=".claude/skills/portable-enum/SKILL.md",
        current_language="any",
        current_framework="any",
        layer="core",
        binding="core",
        bindings=bindings,
        placement="concept-plus-binding" if len(bindings) > 1 else "concept",
        readiness="exemplar-ready",
        rationale="test",
        ar3_foundation_member=False,
        raw={},
    )


def _skill(tmp_path: Path, bindings: tuple[str, ...]) -> Path:
    root = tmp_path / "catalog" / "portable-enum"
    _write(
        root / "SKILL.md",
        "---\nname: portable-enum\ndescription: Test.\n---\n\n# Core\n\nShared invariant.\n",
    )
    for binding in bindings:
        if binding != "core":
            _write(root / "bindings" / f"{binding}.md", f"# {binding}\n\n{binding} mechanics.\n")
    return root


def _seed_python(root: Path, *, django: bool = False) -> None:
    _write(root / "requirements.txt", "Django==5.2\n" if django else "pytest==9\n")
    _write(root / "app.py", "value = 1\n")
    if django:
        _write(root / "manage.py", "#!/usr/bin/env python3\n")


def _seed_typescript(root: Path, *, react: bool = False) -> None:
    dependencies = {"vite": "7.0.0"}
    if react:
        dependencies["react"] = "19.0.0"
    _write(root / "package.json", json.dumps({"dependencies": dependencies}))
    _write(root / "tsconfig.json", "{}\n")
    _write(root / "src" / "app.ts", "export const value = 1;\n")


def _registry_with_binding(identifier: str, entry: dict) -> CapabilityRegistry:
    base = load_registry()
    data = copy.deepcopy(base.data)
    data["bindings"][identifier] = entry
    return CapabilityRegistry(data=data, path=base.path)


def test_per_root_precedence_is_isolated_and_evidence_is_deterministic(tmp_path):
    _seed_python(tmp_path / "backend", django=True)
    _seed_typescript(tmp_path / "web", react=True)
    bindings = ("core", "python", "javascript-typescript", "django", "react")
    skill = _skill(tmp_path, bindings)
    profile = profile_host(tmp_path)

    first = compose_skill_bindings(skill, _entry(bindings), profile)
    second = compose_skill_bindings(skill, _entry(bindings), profile)

    assert first == second
    by_root = {render.root: render for render in first}
    assert tuple(by_root) == ("backend", "web")
    assert by_root["backend"].selected_bindings == ("core", "python", "django")
    assert by_root["web"].selected_bindings == (
        "core",
        "javascript-typescript",
        "react",
    )
    assert "react mechanics" not in by_root["backend"].content
    assert "django mechanics" not in by_root["web"].content
    evidence = json.dumps([item.evidence for item in first], sort_keys=True)
    assert str(tmp_path) not in evidence
    assert all(item.evidence["profile_sha256"] == profile["profile_sha256"] for item in first)


def test_same_precedence_is_ambiguous_without_one_explicit_root_choice(tmp_path):
    _seed_python(tmp_path)
    registry = _registry_with_binding(
        "python-alt",
        {
            "kind": "language",
            "layer": "language",
            "languages": ["python"],
            "frameworks": ["any", "none"],
        },
    )
    bindings = ("core", "python", "python-alt")
    skill = _skill(tmp_path, bindings)
    profile = profile_host(tmp_path, registry=registry)

    with pytest.raises(BindingLoadError, match="ambiguous.*language.*python.*python-alt"):
        compose_skill_bindings(skill, _entry(bindings), profile, registry=registry)

    selected = compose_skill_bindings(
        skill,
        _entry(bindings),
        profile,
        registry=registry,
        explicit_bindings_by_root={".": ["python-alt"]},
    )
    assert selected[0].selected_bindings == ("core", "python-alt")


def test_incompatible_explicit_binding_and_zero_required_match_fail_closed(tmp_path):
    _seed_typescript(tmp_path)
    profile = profile_host(tmp_path)
    skill = _skill(tmp_path, ("core", "python", "django"))

    with pytest.raises(BindingLoadError, match="incompatible explicit binding.*django"):
        compose_skill_bindings(
            skill,
            _entry(("core", "python", "django")),
            profile,
            explicit_bindings_by_root={".": ["django"]},
        )

    with pytest.raises(BindingLoadError, match="zero compatible non-core bindings"):
        compose_skill_bindings(skill, _entry(("core", "python", "django")), profile)


def test_registered_subject_without_a_declared_binding_fails_zero_match(tmp_path):
    _write(tmp_path / "Gemfile", "source 'https://example.invalid'\n")
    _write(tmp_path / "app.rb", "VALUE = 1\n")
    profile = profile_host(tmp_path)
    skill = _skill(tmp_path, ("core", "python", "django"))

    with pytest.raises(BindingLoadError, match="zero compatible.*ruby"):
        compose_skill_bindings(skill, _entry(("core", "python", "django")), profile)


def test_one_selected_binding_cannot_hide_an_uncovered_subject_in_the_same_root(tmp_path):
    _seed_python(tmp_path)
    _seed_typescript(tmp_path)
    profile = profile_host(tmp_path)
    skill = _skill(tmp_path, ("core", "python"))

    with pytest.raises(BindingLoadError, match="subjects without compatible bindings.*typescript"):
        compose_skill_bindings(skill, _entry(("core", "python")), profile)


def test_tool_is_not_inferred_as_framework_and_duplicate_blocks_render_once(tmp_path):
    _seed_typescript(tmp_path, react=False)
    bindings = ("core", "javascript-typescript", "react")
    skill = _skill(tmp_path, bindings)
    _write(
        skill / "bindings" / "javascript-typescript.md",
        "# JavaScript and TypeScript\n\nShared invariant.\n\nTyped mechanics.\n",
    )
    profile = profile_host(tmp_path)

    render = compose_skill_bindings(skill, _entry(bindings), profile)[0]

    base = load_registry()
    data = copy.deepcopy(base.data)
    data["bindings"] = dict(reversed(tuple(data["bindings"].items())))
    reordered_registry = CapabilityRegistry(data=data, path=base.path)
    reordered = compose_skill_bindings(
        skill,
        _entry(bindings),
        profile_host(tmp_path, registry=reordered_registry),
        registry=reordered_registry,
    )[0]

    assert render.selected_bindings == ("core", "javascript-typescript")
    assert render.content.count("Shared invariant.") == 1
    assert render.evidence["deduplicated_block_sha256"]
    assert reordered == render


def test_registry_binding_kind_must_match_its_layer_contract(tmp_path):
    _seed_python(tmp_path)
    base = load_registry()
    data = copy.deepcopy(base.data)
    data["bindings"]["python"]["kind"] = "framework"
    registry = CapabilityRegistry(data=data, path=base.path)
    profile = profile_host(tmp_path, registry=registry)
    skill = _skill(tmp_path, ("core", "python"))

    with pytest.raises(BindingLoadError, match="kind.*not allowed by layer"):
        compose_skill_bindings(
            skill,
            _entry(("core", "python")),
            profile,
            registry=registry,
        )


def test_extract_enum_canonical_root_composes_python_then_django(tmp_path):
    _seed_python(tmp_path, django=True)
    profile = profile_host(tmp_path)
    entry = load_catalog().entries_by_name["extract-enum"]
    skill = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "extract-enum"

    render = compose_skill_bindings(skill, entry, profile)[0]

    assert render.selected_bindings == ("core", "python", "django")
    assert render.evidence["skill_path"] == ".claude/skills/extract-enum/SKILL.md"
    assert [source["precedence"] for source in render.evidence["sources"]] == [0, 1, 2]
    assert render.evidence["stack"]["frameworks"] == ["django"]
