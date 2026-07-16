from __future__ import annotations

import platform
import sys

import yaml

import capability_claims
from _lib.capability_registry import RegistryError, load_registry
from _lib.support_evidence import (
    canonical_evidence_hash,
    sha256_bytes,
    sha256_file,
)


def _write_valid_evidence(root, *, claim=None):
    contract_test = root / "contract_test.py"
    contract_test.write_text("print('verified-fixture')\n", encoding="utf-8")
    evidence = {
        "claim": claim or {"kind": "skill", "id": root.name},
        "fixture": {
            "command": [sys.executable, "contract_test.py"],
            "cwd": ".",
            "expected_stdout_sha256": sha256_bytes(b"verified-fixture\n"),
            "timeout_seconds": 10,
        },
        "artifacts": [
            {
                "kind": "test",
                "path": "contract_test.py",
                "sha256": sha256_file(contract_test),
            },
        ],
        "tools": [
            {
                "name": "python-runtime",
                "command": [sys.executable, "--version"],
            }
        ],
        "platforms": [
            {"system": platform.system(), "machine": platform.machine()}
        ],
    }
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)
    capability_evidence = {
        "typescript": [
            {
                "kind": "test",
                "path": "contract_test.py",
                "sha256": sha256_file(contract_test),
            }
        ]
    }
    return evidence, capability_evidence


def _strict_skill(root, **overrides):
    support_evidence, capability_evidence = _write_valid_evidence(root)
    payload = {
        "capability_contract": 1,
        "language": "typescript",
        "framework": "react",
        "layer": "framework",
        "binding": "react",
        "support": "experimental",
        "capabilities": ["analysis.symbols"],
        "capability_evidence": capability_evidence,
        "support_evidence": support_evidence,
        "scans": [],
    }
    payload.update(overrides)
    return payload


def test_registry_exposes_one_versioned_vocabulary():
    registry = load_registry()

    assert registry.schema_version == 1
    assert registry.contract_version == 1
    assert {"python", "typescript", "rust", "go"} <= registry.identifiers("languages")
    assert {"django", "react"} <= registry.identifiers("frameworks")
    assert "vite" in registry.identifiers("tools")
    assert "vite" not in registry.identifiers("frameworks")
    assert registry.language_for_extension(".tsx") == "typescript"
    assert all(
        entry.get("minimum_surface_version") and entry.get("discovery")
        for entry in registry.data["agent_surfaces"].values()
    )


def test_future_language_is_registered_by_data_not_validator_code(tmp_path):
    source = load_registry().path
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["languages"]["zig"] = {
        "subject": True,
        "extensions": [".zig"],
        "project_markers": ["build.zig"],
    }
    target = tmp_path / "registry.yml"
    target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = load_registry(target)

    assert "zig" in registry.identifiers("languages")
    assert registry.language_for_extension(".zig") == "zig"


def test_strict_contract_accepts_hashed_fixture_and_tool_evidence(tmp_path):
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(tmp_path),
        skill_dir=tmp_path,
    )

    assert errors == []


def test_strict_contract_rejects_invalid_capability_and_layer_binding_pair(tmp_path):
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(
            tmp_path,
            capabilities=["analysis.telepathy"],
            layer="language",
            binding="react",
        ),
        skill_dir=tmp_path,
    )

    assert any("invalid names" in error for error in errors)
    assert any("belongs to layer" in error for error in errors)


def test_strict_contract_rejects_any_without_per_subject_executable_evidence(tmp_path):
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(
            tmp_path,
            language="any",
            framework="any",
            layer="core",
            binding="core",
            portable_subjects=["python", "typescript"],
            capability_evidence={
                "python": _write_valid_evidence(tmp_path)[1]["typescript"]
            },
        ),
        skill_dir=tmp_path,
    )

    assert any("every portable subject" in error and "typescript" in error for error in errors)


def test_strict_contract_rejects_fabricated_any_evidence_strings(tmp_path):
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(
            tmp_path,
            language="any",
            framework="any",
            layer="core",
            binding="core",
            portable_subjects=["python", "typescript"],
            capability_evidence={
                "python": ["trust-me"],
                "typescript": ["also-trust-me"],
            },
        ),
        skill_dir=tmp_path,
    )

    assert any("must be a mapping" in error for error in errors)


def test_strict_contract_requires_every_capability_test_to_execute(tmp_path):
    registry = load_registry()
    metadata = _strict_skill(tmp_path)
    unexecuted = tmp_path / "unexecuted_test.py"
    unexecuted.write_text("print('not-run')\n", encoding="utf-8")
    metadata["capability_evidence"]["typescript"].append(
        {"kind": "test", "path": "unexecuted_test.py", "sha256": sha256_file(unexecuted)}
    )

    errors = registry.validate_skill_contract(metadata, skill_dir=tmp_path)

    assert any("does not execute all capability evidence tests" in error for error in errors)


def test_strict_contract_rejects_scan_without_adapter_or_executable(tmp_path):
    registry = load_registry()
    metadata = _strict_skill(tmp_path, scans=["css"])

    errors = registry.validate_skill_contract(metadata, skill_dir=tmp_path)

    assert any("no registered adapter or shim" in error for error in errors)
    assert any("executable skill script" in error for error in errors)


def test_verified_scan_rejects_empty_script_fake_command_hash_platform_and_ceiling(tmp_path):
    registry = load_registry()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "empty.py").write_text("", encoding="utf-8")
    metadata = _strict_skill(tmp_path, scans=["typescript"], support="verified")
    metadata["support_evidence"] = {
        "fixture": {
            "command": False,
            "expected_stdout_sha256": "bad",
        },
        "artifacts": metadata["capability_evidence"]["typescript"],
        "tools": [],
        "platforms": [{"system": "Atlantis", "machine": "dream"}],
        "evidence_hash": "bad",
    }

    errors = registry.validate_skill_contract(metadata, skill_dir=tmp_path)

    assert any("argv list" in error for error in errors)
    assert any("lowercase SHA-256" in error for error in errors)
    assert any("not a supported platform" in error for error in errors)
    assert any("support ceiling is 'experimental'" in error for error in errors)
    assert any("executable skill script" in error for error in errors)


def test_stack_validation_rejects_react_vite_category_confusion():
    registry = load_registry()

    errors = registry.validate_stack(
        {"languages": ["typescript"], "frameworks": ["react", "vite"], "tools": []}
    )

    assert errors == ["stack.frameworks contains unregistered identifiers: ['vite']"]


def test_support_claims_demote_mechanically_when_evidence_is_stale(tmp_path):
    registry = load_registry()
    evidence, _capability = _write_valid_evidence(tmp_path)
    (tmp_path / "contract_test.py").write_text("# changed after attestation\n", encoding="utf-8")

    state, reasons = registry.evaluate_support(
        {"state": "verified", "evidence": evidence},
        root=tmp_path,
    )

    assert state == "unsupported"
    assert any("sha256 mismatch" in reason for reason in reasons)


def test_support_promotion_is_one_step_and_tied_to_tool_fixture_evidence(tmp_path):
    registry = load_registry()
    evidence, _capability = _write_valid_evidence(tmp_path)

    state, reasons = registry.transition_support("unsupported", evidence, root=tmp_path)
    assert (state, reasons) == ("experimental", [])

    state, reasons = registry.transition_support("experimental", evidence, root=tmp_path)
    assert (state, reasons) == ("verified", [])

    state, reasons = registry.transition_support(
        "experimental", evidence, root=tmp_path, ceiling="experimental"
    )
    assert state == "experimental"
    assert "support_ceiling:experimental" in reasons


def test_support_promotion_uses_registry_tool_policy_not_claimed_pattern(tmp_path):
    registry = load_registry()
    evidence, _capability = _write_valid_evidence(tmp_path)
    evidence["tools"][0] = {
        "name": "python-runtime",
        "command": [sys.executable, "-c", "print('Python 2.7.0')"],
        "version_pattern": ".*",
    }
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)

    state, reasons = registry.transition_support("unsupported", evidence, root=tmp_path)

    assert state == "unsupported"
    assert any("registry-owned" in reason for reason in reasons)

    del evidence["tools"][0]["version_pattern"]
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)
    state, reasons = registry.transition_support("unsupported", evidence, root=tmp_path)
    assert state == "unsupported"
    assert any("registry-owned argv tail" in reason for reason in reasons)

    fake_python = tmp_path / "fake-python"
    fake_python.write_text("#!/bin/sh\necho 'Python 3.11.10'\n", encoding="utf-8")
    fake_python.chmod(0o755)
    evidence["tools"][0]["command"] = [str(fake_python), "--version"]
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)
    state, reasons = registry.transition_support("unsupported", evidence, root=tmp_path)
    assert state == "unsupported"
    assert any("current Python runtime" in reason for reason in reasons)


def test_support_rejects_unbound_claim_unexecuted_test_and_escaping_symlink(tmp_path):
    registry = load_registry()
    evidence, _capability = _write_valid_evidence(tmp_path)
    evidence["claim"] = {"kind": "skill", "id": "someone-else"}
    evidence["fixture"]["command"] = [sys.executable, "-c", "print('verified-fixture')"]
    outside = tmp_path.parent / "outside-evidence.py"
    outside.write_text("print('verified-fixture')\n", encoding="utf-8")
    (tmp_path / "escape.py").symlink_to(outside)
    evidence["artifacts"].append(
        {"kind": "fixture", "path": "escape.py", "sha256": sha256_file(outside)}
    )
    evidence["evidence_hash"] = canonical_evidence_hash(evidence)

    state, reasons = registry.evaluate_support(
        {"state": "verified", "evidence": evidence},
        root=tmp_path,
        expected_claim={"kind": "skill", "id": tmp_path.name},
    )

    assert state == "unsupported"
    assert any("must be bound" in reason for reason in reasons)
    assert any("execute exactly one attested" in reason for reason in reasons)
    assert any("resolves outside" in reason for reason in reasons)


def test_completion_floor_rejects_missing_or_unsupported_required_cells(tmp_path):
    registry = load_registry()
    claims = {
        "stacks": {
            stack: {
                capability: {
                    "state": "verified",
                    "evidence": _write_valid_evidence(
                        tmp_path,
                        claim={
                            "kind": "stack-capability",
                            "id": f"{stack}.{capability}",
                        },
                    )[0],
                }
                for capability in floor["required"]
            }
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {
            surface: {
                "state": "verified",
                "evidence": _write_valid_evidence(
                    tmp_path,
                    claim={
                        "kind": "agent-surface",
                        "id": f"{surface}@{entry['minimum_surface_version']}",
                    },
                )[0],
                "surface_version": entry["minimum_surface_version"],
            }
            for surface, entry in registry.data["agent_surfaces"].items()
        },
    }

    assert registry.validate_completion_claims(claims, evidence_root=tmp_path) == []

    claims["stacks"]["rust"].pop("failure.loud")
    claims["stacks"]["go"]["failure.loud"] = "unsupported"
    claims["agent_surfaces"].pop("gemini")

    errors = registry.validate_completion_claims(claims, evidence_root=tmp_path)

    assert any("rust.failure.loud must be an evidence-backed claim" in error for error in errors)
    assert any("go.failure.loud must be an evidence-backed claim" in error for error in errors)
    assert any("agent_surfaces.gemini must be an evidence-backed claim" in error for error in errors)


def test_completion_floor_rejects_evidence_reused_for_another_cell(tmp_path):
    registry = load_registry()
    evidence, _capability = _write_valid_evidence(
        tmp_path,
        claim={"kind": "stack-capability", "id": "python-django.profile"},
    )
    claims = {
        "stacks": {
            stack: {
                capability: {"state": "verified", "evidence": evidence}
                for capability in floor["required"]
            }
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {},
    }

    errors = registry.validate_completion_claims(claims, evidence_root=tmp_path)

    assert any("typescript-node-react.profile" in error and "must be bound" in error for error in errors)


def test_completion_floor_rejects_bare_verified_labels_and_old_surface_version():
    registry = load_registry()
    claims = {
        "stacks": {
            stack: {capability: "verified" for capability in floor["required"]}
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {
            surface: {"state": "verified", "surface_version": "0", "evidence": {}}
            for surface in registry.data["completion_floor"]["required_agent_surfaces"]
        },
    }

    errors = registry.validate_completion_claims(claims, execute_evidence=False)

    assert any("must be an evidence-backed claim" in error for error in errors)
    assert any("does not satisfy pinned minimum" in error for error in errors)


def test_completion_claims_cli_fails_bare_verified_labels(tmp_path, capsys):
    registry = load_registry()
    claims = {
        "stacks": {
            stack: {capability: "verified" for capability in floor["required"]}
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {},
    }
    path = tmp_path / "claims.yml"
    path.write_text(yaml.safe_dump(claims), encoding="utf-8")

    rc = capability_claims.main(
        [str(path), "--evidence-root", str(tmp_path), "--no-execute"]
    )

    assert rc == 1
    assert '"status": "fail"' in capsys.readouterr().out


def test_completion_claims_cli_structural_mode_cannot_pass_gate(tmp_path, capsys):
    registry = load_registry()
    claims = {
        "stacks": {
            stack: {
                capability: {
                    "state": "verified",
                    "evidence": _write_valid_evidence(
                        tmp_path,
                        claim={
                            "kind": "stack-capability",
                            "id": f"{stack}.{capability}",
                        },
                    )[0],
                }
                for capability in floor["required"]
            }
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {
            surface: {
                "state": "verified",
                "surface_version": entry["minimum_surface_version"],
                "evidence": _write_valid_evidence(
                    tmp_path,
                    claim={
                        "kind": "agent-surface",
                        "id": f"{surface}@{entry['minimum_surface_version']}",
                    },
                )[0],
            }
            for surface, entry in registry.data["agent_surfaces"].items()
        },
    }
    path = tmp_path / "claims.yml"
    path.write_text(yaml.safe_dump(claims), encoding="utf-8")

    rc = capability_claims.main(
        [str(path), "--evidence-root", str(tmp_path), "--no-execute"]
    )

    assert rc == 3
    assert '"status": "structural-only"' in capsys.readouterr().out


def test_registry_rejects_binding_that_names_unknown_language(tmp_path):
    payload = yaml.safe_load(load_registry().path.read_text(encoding="utf-8"))
    payload["bindings"]["broken"] = {
        "kind": "language",
        "layer": "language",
        "languages": ["cobol"],
        "frameworks": ["none"],
    }
    target = tmp_path / "registry.yml"
    target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    try:
        load_registry(target)
    except RegistryError as exc:
        assert "unknown languages" in str(exc)
    else:
        raise AssertionError("invalid registry unexpectedly loaded")


def test_registry_rejects_undefined_completion_floor_outcome(tmp_path):
    payload = yaml.safe_load(load_registry().path.read_text(encoding="utf-8"))
    payload["completion_floor"]["stacks"]["rust"]["required"].append("magic.unregistered")
    target = tmp_path / "registry.yml"
    target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    try:
        load_registry(target)
    except RegistryError as exc:
        assert "undefined outcomes" in str(exc)
    else:
        raise AssertionError("undefined completion outcome unexpectedly loaded")
