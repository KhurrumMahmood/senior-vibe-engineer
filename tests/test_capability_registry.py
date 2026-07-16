from __future__ import annotations

import yaml

from _lib.capability_registry import RegistryError, load_registry


def _strict_skill(**overrides):
    payload = {
        "capability_contract": 1,
        "language": "typescript",
        "framework": "react",
        "layer": "framework",
        "binding": "react",
        "support": "experimental",
        "capabilities": ["analysis.symbols"],
        "capability_evidence": {"typescript": ["test:fixture"]},
        "support_evidence": {
            "fixture_results": "pass",
            "tool_versions": {"parser": "1.0"},
            "platform": "test-platform",
        },
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


def test_strict_contract_rejects_invalid_capability_and_layer_binding_pair():
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(
            capabilities=["analysis.telepathy"],
            layer="language",
            binding="react",
        )
    )

    assert any("invalid names" in error for error in errors)
    assert any("belongs to layer" in error for error in errors)


def test_strict_contract_rejects_any_without_per_subject_executable_evidence():
    registry = load_registry()

    errors = registry.validate_skill_contract(
        _strict_skill(
            language="any",
            framework="any",
            layer="core",
            binding="core",
            portable_subjects=["python", "typescript"],
            capability_evidence={"python": ["test:python-fixture"]},
        )
    )

    assert any("every portable subject" in error and "typescript" in error for error in errors)


def test_strict_contract_rejects_scan_without_adapter_or_executable(tmp_path):
    registry = load_registry()
    metadata = _strict_skill(scans=["css"])

    errors = registry.validate_skill_contract(metadata, skill_dir=tmp_path)

    assert any("no registered adapter or shim" in error for error in errors)
    assert any("executable skill script" in error for error in errors)


def test_stack_validation_rejects_react_vite_category_confusion():
    registry = load_registry()

    errors = registry.validate_stack(
        {"languages": ["typescript"], "frameworks": ["react", "vite"], "tools": []}
    )

    assert errors == ["stack.frameworks contains unregistered identifiers: ['vite']"]


def test_support_claims_demote_mechanically_when_evidence_is_stale():
    registry = load_registry()

    state, reasons = registry.evaluate_support(
        {
            "state": "verified",
            "evidence": {
                "fixture_results": "fail",
                "tool_versions": {"parser": "1.0"},
                "platform": "linux-x86_64",
                "deterministic_command": "run fixture",
                "evidence_hash": "abc",
                "tool_version_in_range": True,
                "platform_supported": True,
            },
        }
    )

    assert state == "unsupported"
    assert "fixture_failure" in reasons


def test_support_promotion_is_one_step_and_tied_to_tool_fixture_evidence():
    registry = load_registry()
    experimental_evidence = {
        "fixture_results": "pass",
        "tool_versions": {"parser": "1.0"},
        "platform": "linux-x86_64",
        "tool_version_in_range": True,
        "platform_supported": True,
    }

    state, reasons = registry.transition_support("unsupported", experimental_evidence)
    assert (state, reasons) == ("experimental", [])

    state, reasons = registry.transition_support("experimental", {
        **experimental_evidence,
        "deterministic_command": "run fixtures",
        "evidence_hash": "abc",
    })
    assert (state, reasons) == ("verified", [])

    state, reasons = registry.transition_support("verified", {
        **experimental_evidence,
        "deterministic_command": "run fixtures",
        "evidence_hash": "abc",
        "tool_version_in_range": False,
    })
    assert state == "unsupported"
    assert "tool_version_outside_verified_range" in reasons


def test_completion_floor_rejects_missing_or_unsupported_required_cells():
    registry = load_registry()
    claims = {
        "stacks": {
            stack: {capability: "verified" for capability in floor["required"]}
            for stack, floor in registry.data["completion_floor"]["stacks"].items()
        },
        "agent_surfaces": {
            surface: "verified"
            for surface in registry.data["completion_floor"]["required_agent_surfaces"]
        },
    }
    claims["stacks"]["rust"].pop("failure.loud")
    claims["stacks"]["go"]["failure.loud"] = "unsupported"
    claims["agent_surfaces"].pop("gemini")

    errors = registry.validate_completion_claims(claims)

    assert "rust.failure.loud must be verified, got None" in errors
    assert "go.failure.loud must be verified, got 'unsupported'" in errors
    assert "agent_surfaces.gemini must be verified, got None" in errors


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
