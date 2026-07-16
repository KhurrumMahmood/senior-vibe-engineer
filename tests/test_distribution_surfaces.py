from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from distribution_probe import (
    build_bundle_inventory,
    build_projections,
    collect_runtime_evidence,
    validate_bundle_inventory,
    validate_projections,
)


ROOT = Path(__file__).resolve().parents[1]


def _resign(inventory: dict[str, Any]) -> None:
    payload = dict(inventory)
    payload.pop("bundle_sha256", None)
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    inventory["bundle_sha256"] = hashlib.sha256(content).hexdigest()


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return build_bundle_inventory(ROOT)


def test_ready_bundle_inventory_projects_complete_skill_trees_to_five_surfaces(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"

    manifest = build_projections(inventory, ROOT, output)

    assert len(inventory["skills"]) == 16
    assert set(manifest["surfaces"]) == {
        "augment",
        "claude-code",
        "codex",
        "cursor",
        "gemini",
    }
    assert validate_projections(inventory, ROOT, output, manifest) == []
    canonical = (ROOT / ".claude/skills/extract-enum/SKILL.md").read_bytes()
    assert (output / "augment/.augment/rules/imported/extract-enum/SKILL.md").read_bytes() == canonical
    assert (output / "claude-code/.claude/skills/extract-enum/bindings/django.md").is_file()
    assert (output / "codex/skills/extract-enum/scripts/propose.py").is_file()
    assert (output / "cursor/.cursor/rules/extract-enum/SKILL.mdc").read_bytes() == canonical
    assert (output / "gemini/.gemini/skills/extract-enum/agents/enum-profiler.md").is_file()


def test_projection_validation_rejects_surface_divergence(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    target = output / "cursor/.cursor/rules/plan-feature/SKILL.mdc"
    target.write_text("divergent duplicate\n", encoding="utf-8")

    errors = validate_projections(inventory, ROOT, output, manifest)

    assert any("cursor: divergent duplicate content" in error for error in errors)
    assert any("on-disk projection hash differs" in error for error in errors)


def test_projection_validation_rejects_undeclared_duplicate_path(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    duplicate = output / "augment/.augment/rules/imported/plan-feature-copy.md"
    duplicate.write_bytes((ROOT / ".claude/skills/plan-feature/SKILL.md").read_bytes())

    errors = validate_projections(inventory, ROOT, output, manifest)

    assert any("augment: undeclared, duplicate" in error for error in errors)


def test_bundle_validation_rejects_path_traversal(inventory: dict[str, Any]) -> None:
    attacked = copy.deepcopy(inventory)
    attacked["skills"][0]["files"][0]["path"] = "../outside.md"
    _resign(attacked)

    errors = validate_bundle_inventory(attacked, ROOT)

    assert any("path traversal" in error for error in errors)


def test_bundle_validation_rejects_incomplete_ready_catalog_set(
    inventory: dict[str, Any],
) -> None:
    attacked = copy.deepcopy(inventory)
    attacked["skills"].pop()
    _resign(attacked)

    errors = validate_bundle_inventory(attacked, ROOT)

    assert any("distribution-ready set" in error for error in errors)


@pytest.mark.parametrize(
    ("aliases", "message"),
    [
        (
            [
                {"name": "plan-feature-v1", "target": "plan-feature", "version": 1},
                {"name": "plan-feature-v1", "target": "plan-feature", "version": 1},
            ],
            "alias collision",
        ),
        (
            [{"name": "plan-feature-v1", "target": "removed-skill", "version": 1}],
            "stale target",
        ),
        (
            [
                {"name": "plan-feature-v1", "target": "plan-feature-v2", "version": 1},
                {"name": "plan-feature-v2", "target": "plan-feature-v1", "version": 2},
            ],
            "alias cycle",
        ),
    ],
)
def test_bundle_validation_rejects_invalid_alias_graphs(
    inventory: dict[str, Any], aliases: list[dict[str, Any]], message: str
) -> None:
    attacked = copy.deepcopy(inventory)
    attacked["aliases"] = aliases
    _resign(attacked)

    errors = validate_bundle_inventory(attacked, ROOT)

    assert any(message in error for error in errors)


def test_versioned_alias_projects_as_a_deterministic_invocation(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    with_alias = copy.deepcopy(inventory)
    with_alias["aliases"] = [
        {"name": "plan-feature-v1", "target": "plan-feature", "version": 1}
    ]
    _resign(with_alias)

    output = tmp_path / "matrix"
    manifest = build_projections(with_alias, ROOT, output)

    assert validate_projections(with_alias, ROOT, output, manifest) == []
    alias_text = (output / "gemini/.gemini/skills/plan-feature-v1/SKILL.md").read_text()
    assert "\nname: plan-feature-v1\n" in alias_text
    assert "\nname: plan-feature\n" not in alias_text


def test_runtime_evidence_is_separate_and_records_typed_unavailable(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lambda _name: None,
    )

    assert {record["status"] for record in evidence["records"].values()} == {"unavailable"}
    for record in evidence["records"].values():
        assert record["structural_validation"] == {
            "result": "pass",
            "errors": [],
            "satisfies_runtime_discovery": False,
        }
        assert record["source_revision"]
        assert record["bundle_sha256"] == inventory["bundle_sha256"]
        assert record["projection_sha256"] == manifest["projection_sha256"]
        assert len(record["fixture_sha256"]) == 64


def test_runtime_evidence_binds_exact_gemini_and_auggie_commands_and_outputs(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    names = [skill["name"] for skill in inventory["skills"]]

    def lookup(name: str) -> str | None:
        return {"gemini": "/runtime/gemini", "auggie": "/runtime/auggie"}.get(name)

    def runner(
        command: list[str], _cwd: Path, _env: dict[str, str] | None
    ) -> subprocess.CompletedProcess[bytes]:
        if command[-1] == "--version":
            version = b"0.45.0\n" if command[0].endswith("gemini") else b"0.32.0\n"
            return subprocess.CompletedProcess(command, 0, version, b"")
        if command[1:] == ["skills", "list"]:
            stdout = "Discovered Agent Skills:\n\n" + "".join(
                f"{name} [Enabled]\n  Description: test\n" for name in names
            )
            return subprocess.CompletedProcess(command, 0, stdout.encode(), b"")
        stdout = "\n".join(f".augment/rules/imported/{name}/SKILL.md" for name in names)
        return subprocess.CompletedProcess(command, 0, stdout.encode(), b"MCP warning\n")

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lookup,
        runner=runner,
    )

    gemini = evidence["records"]["gemini"]
    augment = evidence["records"]["augment"]
    assert gemini["status"] == augment["status"] == "verified"
    assert gemini["discovery_probe"]["command"] == ["/runtime/gemini", "skills", "list"]
    assert len(augment["discovery_probes"]) == len(names)
    assert augment["discovery_probes"][0]["command"] == [
        "/runtime/auggie",
        "rules",
        "list",
    ]
    assert len(gemini["discovery_probe"]["output_sha256"]) == 64
    assert len(augment["discovery_probes"][0]["output_sha256"]) == 64
    assert augment["discovery_probes"][0]["stderr"] == "MCP warning\n"
