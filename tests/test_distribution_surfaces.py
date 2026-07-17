from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from distribution_probe import (
    build_bundle_inventory,
    build_projections,
    collect_runtime_evidence,
    validate_bundle_inventory,
    validate_projections,
    validate_runtime_evidence,
)
from _lib.capability_registry import load_registry


ROOT = Path(__file__).resolve().parents[1]


def _resign(inventory: dict[str, Any]) -> None:
    payload = dict(inventory)
    payload.pop("bundle_sha256", None)
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    inventory["bundle_sha256"] = hashlib.sha256(content).hexdigest()


def _clone_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "project"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(fixture)],
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.invalid"],
        cwd=fixture,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Distribution Tests"],
        cwd=fixture,
        check=True,
    )
    return fixture


def _fixture_registry(fixture: Path):
    return load_registry(fixture / ".claude/skills/_common/capability-registry.yml")


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
    assert manifest["projection_mode"] == "full-discovery"
    assert validate_projections(inventory, ROOT, output, manifest) == []
    canonical = (ROOT / ".claude/skills/extract-enum/SKILL.md").read_bytes()
    assert (output / "augment/.augment/rules/imported/extract-enum/SKILL.md").read_bytes() == canonical
    assert (output / "claude-code/.claude/skills/extract-enum/bindings/django.md").is_file()
    assert (output / "codex/skills/extract-enum/scripts/propose.py").is_file()
    assert (output / "cursor/.cursor/rules/extract-enum/SKILL.mdc").read_bytes() == canonical
    assert (output / "gemini/.gemini/skills/extract-enum/agents/enum-profiler.md").is_file()


def test_bundle_binds_every_load_bearing_reference(inventory: dict[str, Any]) -> None:
    expected = {
        ".claude/docs/skill-catalog.md",
        ".claude/skills/_common/capability-registry.yml",
        ".claude/skills/_common/skill-catalog-inventory.yml",
        ".claude/contracts/skills/_index.yaml",
        *{
            f".claude/contracts/skills/{skill['name']}.yaml"
            for skill in inventory["skills"]
        },
    }

    assert {row["path"] for row in inventory["reference_files"]} == expected
    assert inventory["registry_contract_version"] == 1


def test_bundle_rejects_untracked_or_ignored_load_bearing_files(tmp_path: Path) -> None:
    fixture = _clone_fixture(tmp_path)
    clean = build_bundle_inventory(fixture, registry=_fixture_registry(fixture))
    assert clean["source_revision"] == subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=fixture,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert clean["source_tree"] == subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=fixture,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    cache = fixture / ".claude/skills/extract-enum/__pycache__/propose.cpython-311.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"foreign bytecode\n")
    assert subprocess.run(
        ["git", "check-ignore", str(cache)], cwd=fixture, check=False
    ).returncode == 0

    with pytest.raises(ValueError, match="untracked or ignored load-bearing files"):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))

    cache.unlink()
    fixture.joinpath(".claude/skills/extract-enum/untracked-notes.txt").write_text(
        "foreign resource\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="untracked or ignored load-bearing files"):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))

    fixture.joinpath(".claude/skills/extract-enum/untracked-notes.txt").unlink()
    fixture.joinpath(".claude/skills/extract-enum/SKILL.md").write_text(
        "dirty load-bearing source\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="dirty load-bearing source"):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))


def test_bundle_rejects_committed_cache_artifact(tmp_path: Path) -> None:
    fixture = _clone_fixture(tmp_path)
    cache = fixture / ".claude/skills/extract-enum/scripts/__pycache__/propose.cpython-311.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"committed bytecode\n")
    subprocess.run(["git", "add", "-f", str(cache)], cwd=fixture, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture cache"], cwd=fixture, check=True)

    with pytest.raises(ValueError, match="committed cache artifact"):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))


def test_projection_rejects_collision_after_cursor_primary_remap(tmp_path: Path) -> None:
    fixture = _clone_fixture(tmp_path)
    collision = fixture / ".claude/skills/extract-enum/SKILL.mdc"
    collision.write_text("foreign canonical resource\n", encoding="utf-8")
    subprocess.run(["git", "add", str(collision)], cwd=fixture, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture collision"], cwd=fixture, check=True)
    inventory = build_bundle_inventory(fixture, registry=_fixture_registry(fixture))

    with pytest.raises(ValueError, match="cursor: projection target collision"):
        build_projections(
            inventory,
            fixture,
            tmp_path / "matrix",
            registry=_fixture_registry(fixture),
        )


def test_bundle_rejects_duplicate_contract_index_rows_before_set_collapse(
    tmp_path: Path,
) -> None:
    fixture = _clone_fixture(tmp_path)
    index_path = fixture / ".claude/contracts/skills/_index.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    index["skills"].append(copy.deepcopy(index["skills"][0]))
    index["skill_count"] += 1
    index_path.write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")
    subprocess.run(["git", "add", str(index_path)], cwd=fixture, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture duplicate"], cwd=fixture, check=True)

    with pytest.raises(ValueError, match="contracts index has duplicate skill rows"):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))


@pytest.mark.parametrize(
    ("attack", "message"),
    [
        ("unknown", "contracts index has unknown skill rows"),
        ("count", "contracts index skill_count differs from row count"),
    ],
)
def test_bundle_rejects_unknown_contract_index_rows_and_count_mismatch(
    tmp_path: Path, attack: str, message: str
) -> None:
    fixture = _clone_fixture(tmp_path)
    index_path = fixture / ".claude/contracts/skills/_index.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    if attack == "unknown":
        foreign = copy.deepcopy(index["skills"][0])
        foreign["skill"] = "foreign-skill"
        index["skills"].append(foreign)
        index["skill_count"] += 1
    else:
        index["skill_count"] += 1
    index_path.write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")
    subprocess.run(["git", "add", str(index_path)], cwd=fixture, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture index"], cwd=fixture, check=True)

    with pytest.raises(ValueError, match=message):
        build_bundle_inventory(fixture, registry=_fixture_registry(fixture))


@pytest.mark.parametrize(
    "relative",
    [
        ".claude/docs/skill-catalog.md",
        ".claude/contracts/skills/plan-feature.yaml",
        ".claude/contracts/skills/_index.yaml",
    ],
)
def test_bundle_validation_rejects_tampered_reference_file(
    tmp_path: Path, inventory: dict[str, Any], relative: str
) -> None:
    fixture = _clone_fixture(tmp_path)
    target = fixture / relative
    target.write_text("broken: true\n", encoding="utf-8")
    registry = _fixture_registry(fixture)

    errors = validate_bundle_inventory(inventory, fixture, registry=registry)

    assert any("dirty load-bearing source state" in error for error in errors)


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


def test_projection_validation_rejects_duplicate_manifest_target(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    manifest["surfaces"]["gemini"]["files"].append(
        copy.deepcopy(manifest["surfaces"]["gemini"]["files"][0])
    )
    output.joinpath("projection-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    errors = validate_projections(inventory, ROOT, output, manifest)

    assert any("duplicate manifest target" in error for error in errors)


def test_projection_validation_returns_errors_for_malformed_inventory(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    attacked = copy.deepcopy(inventory)
    del attacked["skills"][0]["files"][0]["path"]
    _resign(attacked)

    errors = validate_projections(attacked, ROOT, output, manifest)

    assert any("invalid file record" in error for error in errors)


def test_bundle_validation_rejects_path_traversal(inventory: dict[str, Any]) -> None:
    attacked = copy.deepcopy(inventory)
    attacked["skills"][0]["files"][0]["path"] = "../outside.md"
    _resign(attacked)

    errors = validate_bundle_inventory(attacked, ROOT)

    assert any("path traversal" in error for error in errors)


@pytest.mark.parametrize(
    "name",
    ["../plan-feature-v1", "nested/plan-feature-v1", "Plan-Feature-v1", "plan_feature-v1"],
)
def test_bundle_validation_rejects_unsafe_alias_invocation(
    inventory: dict[str, Any], name: str
) -> None:
    attacked = copy.deepcopy(inventory)
    attacked["aliases"] = [{"name": name, "target": "plan-feature", "version": 1}]
    _resign(attacked)

    errors = validate_bundle_inventory(attacked, ROOT)

    assert any("safe public invocation" in error for error in errors)


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
        assert record["registry_contract_version"] == 1
        assert record["source_tree"]
        assert record["platform"]["system"]
        assert record["inventory_sha256"] == evidence["inventory_sha256"]
        assert record["manifest_sha256"] == evidence["manifest_sha256"]
    assert validate_runtime_evidence(
        evidence, inventory, ROOT, output, manifest, tmp_path / "home"
    ) == []


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
                f"{name} [Enabled]\n  Description: test\n"
                f"  Location:    {(_cwd / '.gemini/skills' / name / 'SKILL.md').resolve()}\n\n"
                for name in names
            )
            return subprocess.CompletedProcess(command, 0, stdout.encode(), b"")
        stdout = f".augment/rules/imported/{_cwd.name}/SKILL.md"
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
    assert gemini["discovery_probe"]["argv"] == ["/runtime/gemini", "skills", "list"]
    assert len(augment["discovery_probes"]) == len(names)
    assert augment["discovery_probes"][0]["argv"] == [
        "/runtime/auggie",
        "rules",
        "list",
    ]
    assert len(gemini["discovery_probe"]["output_sha256"]) == 64
    assert len(augment["discovery_probes"][0]["output_sha256"]) == 64
    assert augment["discovery_probes"][0]["stderr"] == "MCP warning\n"

    attacked = copy.deepcopy(evidence)
    attacked["records"]["gemini"]["version_probe"]["exit_code"] = 37
    errors = validate_runtime_evidence(
        attacked, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("version probe failed" in error for error in errors)

    attacked = copy.deepcopy(evidence)
    attacked_probe = attacked["records"]["gemini"]["version_probe"]
    attacked_probe["stdout"] = "gemini-cli 0.45.0\n"
    attacked_probe["output_sha256"] = hashlib.sha256(
        (attacked_probe["stdout"] + attacked_probe["stderr"]).encode()
    ).hexdigest()
    errors = validate_runtime_evidence(
        attacked, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("does not prove exact 0.45.0" in error for error in errors)

    attacked = copy.deepcopy(evidence)
    attacked["records"]["augment"]["reason"] = "moved fixture accepted"
    errors = validate_runtime_evidence(
        attacked, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("reason differs" in error for error in errors)

    augment_probe = evidence["records"]["augment"]["discovery_probes"][0]
    augment_cwd = Path(augment_probe["cwd"])
    moved = tmp_path / "outside-runtime-root" / augment_cwd.name
    moved.parent.mkdir()
    shutil.move(str(augment_cwd), moved)
    attacked = copy.deepcopy(evidence)
    attacked_probe = attacked["records"]["augment"]["discovery_probes"][0]
    attacked_probe["cwd"] = str(moved)
    errors = validate_runtime_evidence(
        attacked, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("permitted runtime root" in error for error in errors)


def test_runtime_evidence_uses_native_non_model_claude_and_codex_discovery(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    names = [skill["name"] for skill in inventory["skills"]]

    def lookup(name: str) -> str | None:
        return {"claude": "/runtime/claude", "codex": "/runtime/codex"}.get(name)

    def runner(
        command: list[str], _cwd: Path, _env: dict[str, str] | None
    ) -> subprocess.CompletedProcess[bytes]:
        if command[-1] == "--version":
            version = b"2.1.211 (Claude Code)\n" if command[0].endswith("claude") else b"codex-cli 0.144.1\n"
            return subprocess.CompletedProcess(command, 0, version, b"")
        if command[0].endswith("claude") and command[1:3] == ["plugin", "details"]:
            stdout = f"Component inventory\n  Skills ({len(names)})  {', '.join(names)}\n"
            return subprocess.CompletedProcess(command, 0, stdout.encode(), b"")
        if command[0].endswith("codex") and "debug" in command:
            skill_text = "<skills_instructions>\n" + "".join(
                f"- engineering-skills:{name}: test\n" for name in names
            )
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps([{"text": skill_text}]).encode(),
                b"",
            )
        if command[0].endswith("codex") and command[1:3] == ["plugin", "add"]:
            return subprocess.CompletedProcess(command, 0, b'{"authPolicy": "ON_USE"}\n', b"")
        return subprocess.CompletedProcess(command, 0, b"ok\n", b"")

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lookup,
        runner=runner,
    )

    assert evidence["records"]["claude-code"]["status"] == "verified"
    assert evidence["records"]["codex"]["status"] == "verified"
    assert validate_runtime_evidence(
        evidence, inventory, ROOT, output, manifest, tmp_path / "home"
    ) == []

    attacked = copy.deepcopy(evidence)
    attacked["records"]["codex"]["discovery_probe"]["argv"][-1] = "foreign"
    attacked["records"]["codex"]["discovery_probes"][0]["argv"][-1] = "foreign"
    errors = validate_runtime_evidence(
        attacked, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("prompt-input discovery" in error for error in errors)

    claude_cwd = Path(evidence["records"]["claude-code"]["setup_probes"][0]["cwd"])
    claude_cwd.joinpath(
        "marketplace/plugins/engineering-skills/skills/plan-feature/SKILL.md"
    ).write_text("foreign package\n", encoding="utf-8")
    errors = validate_runtime_evidence(
        evidence, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("marketplace package differs" in error for error in errors)


def test_router_only_discovery_cannot_satisfy_full_discovery_projection(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)

    def runner(
        command: list[str], _cwd: Path, _env: dict[str, str] | None
    ) -> subprocess.CompletedProcess[bytes]:
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, b"2.1.211 (Claude Code)\n", b"")
        if command[1:3] == ["plugin", "details"]:
            return subprocess.CompletedProcess(
                command, 0, b"Component inventory\n  Skills (2)  which-shape, which-skill\n", b""
            )
        return subprocess.CompletedProcess(command, 0, b"ok\n", b"")

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lambda name: "/runtime/claude" if name == "claude" else None,
        runner=runner,
    )

    assert evidence["records"]["claude-code"]["status"] == "unsupported"
    assert evidence["records"]["claude-code"]["projection_mode"] == "full-discovery"


def test_runtime_evidence_validation_rejects_foreign_or_tampered_bindings(
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

    attacks = {
        "source_revision": lambda value: value["records"]["gemini"].__setitem__(
            "source_revision", "0" * 40
        ),
        "source_tree": lambda value: value["records"]["gemini"].__setitem__(
            "source_tree", "0" * 40
        ),
        "registry_contract_version": lambda value: value["records"]["gemini"].__setitem__(
            "registry_contract_version", 999
        ),
        "fixture_sha256": lambda value: value["records"]["gemini"].__setitem__(
            "fixture_sha256", "0" * 64
        ),
        "projection_sha256": lambda value: value["records"]["gemini"].__setitem__(
            "projection_sha256", "0" * 64
        ),
        "inventory_sha256": lambda value: value["records"]["gemini"].__setitem__(
            "inventory_sha256", "0" * 64
        ),
        "manifest_sha256": lambda value: value["records"]["gemini"].__setitem__(
            "manifest_sha256", "0" * 64
        ),
    }
    for label, attack in attacks.items():
        attacked = copy.deepcopy(evidence)
        attack(attacked)
        errors = validate_runtime_evidence(
            attacked, inventory, ROOT, output, manifest, tmp_path / "home"
        )
        assert errors, label


def test_runtime_evidence_validation_rejects_tampered_command_output(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    names = [skill["name"] for skill in inventory["skills"]]

    def runner(
        command: list[str], _cwd: Path, _env: dict[str, str] | None
    ) -> subprocess.CompletedProcess[bytes]:
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, b"0.45.0\n", b"")
        stdout = "Discovered Agent Skills:\n\n" + "".join(
            f"{name} [Enabled]\n  Description: test\n"
            f"  Location:    {(_cwd / '.gemini/skills' / name / 'SKILL.md').resolve()}\n\n"
            for name in names
        )
        return subprocess.CompletedProcess(command, 0, stdout.encode(), b"")

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lambda name: "/runtime/gemini" if name == "gemini" else None,
        runner=runner,
    )
    evidence["records"]["gemini"]["discovery_probe"]["stdout"] += "tampered\n"

    errors = validate_runtime_evidence(
        evidence, inventory, ROOT, output, manifest, tmp_path / "home"
    )

    assert any("output hash" in error for error in errors)


def test_runtime_collection_never_verifies_a_structurally_invalid_projection(
    tmp_path: Path, inventory: dict[str, Any]
) -> None:
    output = tmp_path / "matrix"
    manifest = build_projections(inventory, ROOT, output)
    output.joinpath("gemini/.gemini/skills/plan-feature/SKILL.md").write_text(
        "tampered\n", encoding="utf-8"
    )
    names = [skill["name"] for skill in inventory["skills"]]

    def runner(
        command: list[str], _cwd: Path, _env: dict[str, str] | None
    ) -> subprocess.CompletedProcess[bytes]:
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, b"0.45.0\n", b"")
        stdout = "Discovered Agent Skills:\n\n" + "".join(
            f"{name} [Enabled]\n  Description: test\n"
            f"  Location:    {(_cwd / '.gemini/skills' / name / 'SKILL.md').resolve()}\n\n"
            for name in names
        )
        return subprocess.CompletedProcess(command, 0, stdout.encode(), b"")

    evidence = collect_runtime_evidence(
        inventory,
        ROOT,
        output,
        manifest,
        tmp_path / "home",
        executable_lookup=lambda name: "/runtime/gemini" if name == "gemini" else None,
        runner=runner,
    )

    assert evidence["records"]["gemini"]["status"] != "verified"
    errors = validate_runtime_evidence(
        evidence, inventory, ROOT, output, manifest, tmp_path / "home"
    )
    assert any("structural" in error for error in errors)


def test_verify_matrix_cli_is_read_only_and_rejects_tampered_evidence(
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
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts/distribution_probe.py"),
        "verify-matrix",
        str(ROOT),
        "--fixtures",
        str(output),
        "--evidence",
        str(evidence_path),
        "--runtime-root",
        str(tmp_path / "home"),
    ]

    index_path = ROOT / ".claude/contracts/skills/_index.yaml"
    before_index = index_path.read_bytes()
    clean = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    evidence["records"]["cursor"]["fixture_sha256"] = "0" * 64
    evidence_path.write_text(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    attacked = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)

    assert clean.returncode == 0
    assert index_path.read_bytes() == before_index
    assert '"result": "pass"' in clean.stdout
    assert attacked.returncode == 1
    assert "foreign or stale" in attacked.stdout


def test_documented_current_acceptance_commands_name_real_tests_and_flags() -> None:
    spec = (ROOT / "ai-docs/specs/portable-skill-layer-distribution.md").read_text(
        encoding="utf-8"
    )
    command_section = spec.split("## Deterministic interfaces and acceptance commands", 1)[1]
    command_section = command_section.split("## Adversarial acceptance matrix", 1)[0]
    documented_tests = set(re.findall(r"tests/[A-Za-z0-9_/-]+\.py", command_section))

    assert documented_tests
    assert all((ROOT / path).is_file() for path in documented_tests)
    assert "--check-index" not in command_section
    assert "--strict --no-index" in command_section


def test_documented_strict_intent_drift_acceptance_is_clean_and_read_only() -> None:
    index_path = ROOT / ".claude/contracts/skills/_index.yaml"
    before = index_path.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude/skills/find-skill-intent-drift/scripts/scan.py"),
            "--strict",
            "--no-index",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "TOTAL findings: 0" in result.stdout
    assert index_path.read_bytes() == before
