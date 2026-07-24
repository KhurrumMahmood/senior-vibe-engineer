"""Tests for the .engineering/ state-home resolver and its activation API
(.claude/skills/_common/engineering_home.py).

Covers the skill-activation accessors (skill_activation / is_skill_active /
inactive_reason) across the default-active opt-out model, the flipped allowlist,
and the tolerated-malformed cases, plus the path resolvers (manifest_path /
project_dir / docs_path) and version check. Stdlib-only; everything is driven
against tmp_path-seeded manifests so no tracked file is read or mutated.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EH_PATH = REPO_ROOT / ".claude" / "skills" / "_common" / "engineering_home.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eh = _load_module("engineering_home_under_test", EH_PATH)


def _write_manifest(root: Path, payload: dict) -> Path:
    path = eh.manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


# --- path resolvers ---------------------------------------------------------


def test_manifest_and_project_dir_resolve_under_engineering(tmp_path):
    assert eh.manifest_path(tmp_path) == tmp_path / ".engineering" / "manifest.json"
    assert eh.project_dir(tmp_path) == tmp_path / ".engineering" / "project"
    assert eh.subsystem_registry_path(tmp_path) == (
        tmp_path / ".engineering" / "subsystems.yaml"
    )
    assert eh.subsystem_maps_dir(tmp_path) == (
        tmp_path / ".engineering" / "docs" / "subsystems"
    )


def test_subsystem_registry_falls_back_and_rejects_conflicting_homes(
    tmp_path, capsys
):
    legacy = tmp_path / ".claude" / "subsystems.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("subsystems: {}\n", encoding="utf-8")

    path, used_legacy = eh.resolve_subsystem_registry(tmp_path)
    assert path == legacy
    assert used_legacy is True
    assert "move it to" in capsys.readouterr().err

    canonical = tmp_path / ".engineering" / "subsystems.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("subsystems: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="both canonical and legacy"):
        eh.resolve_subsystem_registry(tmp_path)


def test_subsystem_maps_fall_back_and_reject_conflicting_homes(tmp_path, capsys):
    legacy = tmp_path / ".claude" / "docs" / "subsystems"
    legacy.mkdir(parents=True)
    (legacy / "billing.md").write_text("# Billing\n", encoding="utf-8")

    path, used_legacy = eh.resolve_subsystem_maps_dir(tmp_path)
    assert path == legacy
    assert used_legacy is True
    assert "move it to" in capsys.readouterr().err

    canonical = tmp_path / ".engineering" / "docs" / "subsystems"
    canonical.mkdir(parents=True)
    with pytest.raises(ValueError, match="both canonical and legacy"):
        eh.resolve_subsystem_maps_dir(tmp_path)


def test_read_manifest_absent_returns_none(tmp_path):
    assert eh.read_manifest(tmp_path) is None


def test_read_manifest_malformed_returns_none(tmp_path):
    path = eh.manifest_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert eh.read_manifest(tmp_path) is None


def test_read_manifest_non_object_returns_none(tmp_path):
    _write_manifest(tmp_path, {})  # placeholder, overwrite with a bare list
    eh.manifest_path(tmp_path).write_text("[1, 2, 3]", encoding="utf-8")
    assert eh.read_manifest(tmp_path) is None


# --- version check ----------------------------------------------------------


def test_check_version_absent_is_ok(tmp_path):
    assert eh.check_version(tmp_path) == (True, None)


def test_check_version_matching_is_ok(tmp_path):
    _write_manifest(tmp_path, {"version": eh.MANIFEST_VERSION})
    assert eh.check_version(tmp_path) == (True, eh.MANIFEST_VERSION)


def test_check_version_mismatch_flags_for_migration(tmp_path):
    _write_manifest(tmp_path, {"version": eh.MANIFEST_VERSION + 1})
    ok, found = eh.check_version(tmp_path)
    assert ok is False
    assert found == eh.MANIFEST_VERSION + 1


# --- skill activation: absent / empty defaults ------------------------------


def test_absent_manifest_every_skill_active(tmp_path):
    assert eh.is_skill_active(tmp_path, "find-frontend-duplication") is True
    assert eh.inactive_reason(tmp_path, "find-frontend-duplication") is None
    activation = eh.skill_activation(tmp_path)
    assert activation == {"default": "active", "inactive": {}, "active": {}}


def test_manifest_without_skills_block_every_skill_active(tmp_path):
    _write_manifest(tmp_path, {"version": eh.MANIFEST_VERSION})
    assert eh.is_skill_active(tmp_path, "anything") is True
    assert eh.skill_activation(tmp_path)["default"] == "active"


# --- skill activation: default-active opt-out (the normal case) -------------


def test_default_active_opt_out_marks_listed_skill_inactive(tmp_path):
    _write_manifest(tmp_path, {
        "version": eh.MANIFEST_VERSION,
        "skills": {
            "default": "active",
            "inactive": {"find-route-sprawl": "no HTTP route surface"},
        },
    })
    assert eh.is_skill_active(tmp_path, "find-route-sprawl") is False
    assert eh.inactive_reason(tmp_path, "find-route-sprawl") == "no HTTP route surface"
    # A skill not in the opt-out list stays active, with no reason.
    assert eh.is_skill_active(tmp_path, "find-omnibus") is True
    assert eh.inactive_reason(tmp_path, "find-omnibus") is None


def test_inactive_reason_none_when_opt_out_records_no_reason(tmp_path):
    _write_manifest(tmp_path, {
        "version": eh.MANIFEST_VERSION,
        "skills": {"default": "active", "inactive": {"find-route-sprawl": ""}},
    })
    assert eh.is_skill_active(tmp_path, "find-route-sprawl") is False
    # Inactive, but no recorded reason => None (not the empty string).
    assert eh.inactive_reason(tmp_path, "find-route-sprawl") is None


def test_inactive_block_as_bare_list_is_tolerated(tmp_path):
    _write_manifest(tmp_path, {
        "version": eh.MANIFEST_VERSION,
        "skills": {"default": "active", "inactive": ["find-route-sprawl"]},
    })
    assert eh.is_skill_active(tmp_path, "find-route-sprawl") is False
    assert eh.inactive_reason(tmp_path, "find-route-sprawl") is None
    assert eh.skill_activation(tmp_path)["inactive"] == {"find-route-sprawl": ""}


# --- skill activation: flipped allowlist ------------------------------------


def test_flipped_allowlist_only_listed_skills_active(tmp_path):
    _write_manifest(tmp_path, {
        "version": eh.MANIFEST_VERSION,
        "skills": {"default": "inactive", "active": {"find-omnibus": ""}},
    })
    assert eh.is_skill_active(tmp_path, "find-omnibus") is True
    assert eh.is_skill_active(tmp_path, "find-route-sprawl") is False
    # In the flipped model a non-allowlisted skill is inactive but carries no
    # opt-out reason (reasons live on the default-active `inactive` map).
    assert eh.inactive_reason(tmp_path, "find-route-sprawl") is None


def test_unknown_default_value_falls_back_to_active(tmp_path):
    _write_manifest(tmp_path, {
        "version": eh.MANIFEST_VERSION,
        "skills": {"default": "garbage", "inactive": {"x": "y"}},
    })
    # Unrecognized default normalizes to "active"; opt-out list still honored.
    assert eh.skill_activation(tmp_path)["default"] == "active"
    assert eh.is_skill_active(tmp_path, "x") is False
    assert eh.is_skill_active(tmp_path, "other") is True


def test_non_dict_skills_block_is_tolerated(tmp_path):
    _write_manifest(tmp_path, {"version": eh.MANIFEST_VERSION, "skills": "nope"})
    assert eh.skill_activation(tmp_path) == {
        "default": "active", "inactive": {}, "active": {},
    }
    assert eh.is_skill_active(tmp_path, "anything") is True
