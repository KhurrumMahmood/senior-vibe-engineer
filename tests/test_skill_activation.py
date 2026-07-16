from __future__ import annotations

import json

import pytest

from _lib.host_profile import profile_host
from _lib.skill_activation import (
    ActivationError,
    decide_catalog_activation,
    decide_skill_activation,
    load_host_profile,
)


def _typescript_profile(root):
    root.joinpath("package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "19.0.0"},
                "devDependencies": {"typescript": "5.9.3", "vite": "7.0.0"},
                "scripts": {"build": "vite build", "test": "vitest"},
            }
        ),
        encoding="utf-8",
    )
    root.joinpath("tsconfig.json").write_text("{}\n", encoding="utf-8")
    source = root / "src"
    source.mkdir()
    source.joinpath("App.tsx").write_text("export const App = () => <main />;\n", encoding="utf-8")
    return profile_host(root)


def test_profile_filters_django_skill_and_explains_typescript_inclusion(tmp_path):
    profile = _typescript_profile(tmp_path)
    skills = [
        {
            "name": "django-detector",
            "language": "python",
            "framework": "django",
        },
        {
            "name": "react-detector",
            "language": "typescript",
            "framework": "react",
        },
        {
            "name": "portable-planner",
            "language": "any",
            "framework": "any",
        },
    ]

    decisions = decide_catalog_activation(
        skills,
        project_root=tmp_path,
        profile=profile,
        manifest={},
    )

    assert decisions["django-detector"].active is False
    assert "no profile root matches" in decisions["django-detector"].exclusion_reasons[-1]
    assert decisions["react-detector"].active is True
    assert decisions["react-detector"].matched_roots == (".",)
    assert decisions["react-detector"].layer == "framework"
    assert decisions["react-detector"].binding == "react"
    assert decisions["portable-planner"].active is True


def test_manual_opt_out_can_narrow_but_allowlist_cannot_override_profile(tmp_path):
    profile = _typescript_profile(tmp_path)
    manifest = {
        "skills": {
            "default": "active",
            "inactive": {"react-detector": "host has a different UI audit"},
        }
    }
    react = {"name": "react-detector", "language": "typescript", "framework": "react"}
    django = {"name": "django-detector", "language": "python", "framework": "django"}

    opted_out = decide_skill_activation(
        react,
        project_root=tmp_path,
        profile=profile,
        manifest=manifest,
    )
    allowlisted = decide_skill_activation(
        django,
        project_root=tmp_path,
        profile=profile,
        manifest={"skills": {"default": "inactive", "active": {"django-detector": ""}}},
    )

    assert opted_out.active is False
    assert "different UI audit" in opted_out.exclusion_reasons[0]
    assert allowlisted.active is False
    assert any("no profile root matches" in reason for reason in allowlisted.exclusion_reasons)


def test_required_capability_layer_and_binding_are_all_enforced(tmp_path):
    profile = _typescript_profile(tmp_path)
    metadata = {
        "name": "react-symbols",
        "language": "typescript",
        "framework": "react",
        "layer": "framework",
        "binding": "react",
        "bindings": [],
        "capabilities": ["analysis.symbols"],
    }

    accepted = decide_skill_activation(
        metadata,
        project_root=tmp_path,
        profile=profile,
        manifest={},
        required_capabilities=["analysis.symbols"],
        required_layers=["framework"],
        required_bindings=["react"],
    )
    rejected = decide_skill_activation(
        metadata,
        project_root=tmp_path,
        profile=profile,
        manifest={},
        required_capabilities=["analysis.calls"],
        required_layers=["language"],
        required_bindings=["django"],
    )

    assert accepted.active is True
    assert any("declares required capabilities" in reason for reason in accepted.reasons)
    assert rejected.active is False
    assert len(rejected.exclusion_reasons) == 3


def test_missing_profile_preserves_manual_migration_behavior(tmp_path):
    decision = decide_skill_activation(
        {"name": "legacy-django", "language": "python", "framework": "django"},
        project_root=tmp_path,
        manifest={},
    )

    assert decision.active is True
    assert any("canonical host profile absent" in reason for reason in decision.reasons)


def test_invalid_durable_profile_is_fatal_not_default_active(tmp_path):
    path = tmp_path / ".engineering" / "project" / "host-profile.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 999}\n', encoding="utf-8")

    with pytest.raises(ActivationError, match="invalid host profile"):
        load_host_profile(tmp_path)


def test_unregistered_skill_identifiers_never_default_active_without_profile(tmp_path):
    decision = decide_skill_activation(
        {
            "name": "fabricated-skill",
            "language": "telepathy",
            "framework": "dream-ui",
            "layer": "imaginary",
            "binding": "wishful",
            "capabilities": ["analysis.mind-reading"],
        },
        project_root=tmp_path,
        manifest={},
    )

    assert decision.active is False
    assert any("unregistered skill language" in reason for reason in decision.exclusion_reasons)
    assert any("unregistered skill framework" in reason for reason in decision.exclusion_reasons)
    assert any("unregistered skill layer" in reason for reason in decision.exclusion_reasons)
    assert any("unregistered skill binding" in reason for reason in decision.exclusion_reasons)
    assert any("unregistered capabilities" in reason for reason in decision.exclusion_reasons)
