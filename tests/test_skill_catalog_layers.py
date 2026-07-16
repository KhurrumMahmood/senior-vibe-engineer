from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from _lib.capability_registry import CapabilityRegistry, load_registry
from _lib.skill_catalog import (
    CatalogError,
    discover_skills,
    load_catalog,
    validate_catalog_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / ".claude/skills/_common/skill-catalog-inventory.yml"
SKILLS_DIR = REPO_ROOT / ".claude/skills"

AR3_DEFLAVOR = {
    "architecture-fit",
    "decide",
    "design-it-twice",
    "fix-workflow",
    "impact-feature",
    "organize-project-structure",
    "plan-feature",
    "plan-skill",
    "plan-spec",
    "prevent-regression",
    "propose-folder-reorganization",
    "refactor-subsystem",
    "scope-feature",
    "which-skill",
}


@pytest.fixture
def inventory_payload() -> dict:
    return yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))


@pytest.fixture
def discovered():
    return discover_skills(SKILLS_DIR, project_root=REPO_ROOT)


def _errors(payload: dict, discovered, registry=None) -> list[str]:
    return validate_catalog_payload(
        payload,
        discovered=discovered,
        registry=registry or load_registry(),
    )


def _row(payload: dict, name: str) -> dict:
    return next(row for row in payload["skills"] if row["name"] == name)


def _registry_with_domain_binding() -> CapabilityRegistry:
    source = load_registry()
    data = deepcopy(source.data)
    data["bindings"]["payments"] = {
        "kind": "domain",
        "layer": "domain",
        "languages": ["any"],
        "frameworks": ["any", "none"],
    }
    return CapabilityRegistry(data=data, path=source.path)


def _registry_with_host_binding() -> CapabilityRegistry:
    source = load_registry()
    data = deepcopy(source.data)
    data["bindings"]["tenant-policy"] = {
        "kind": "host",
        "layer": "host-overlay",
        "languages": ["any"],
        "frameworks": ["any", "none"],
    }
    return CapabilityRegistry(data=data, path=source.path)


def test_authoritative_inventory_covers_exact_catalog_and_frozen_sets():
    catalog = load_catalog(INVENTORY, skills_dir=SKILLS_DIR, project_root=REPO_ROOT)

    assert len(catalog.entries) == 76
    assert catalog.ar3_de_flavor_names == frozenset(AR3_DEFLAVOR)
    assert catalog.readiness_counts == {
        "deferred-to-wp8": 60,
        "exemplar-ready": 1,
        "foundation-ready": 15,
        "inventory-only": 0,
    }
    assert catalog.layer_counts == {
        "core": 74,
        "domain": 0,
        "framework": 1,
        "host-overlay": 0,
        "language": 1,
    }
    assert catalog.entries_by_name["extract-enum"].bindings == (
        "core",
        "python",
        "django",
    )
    assert catalog.entries_by_name["engineer-init"].layer == "language"
    assert catalog.entries_by_name["extract-cotton-primitive"].layer == "framework"


@pytest.mark.parametrize("mutation,expected", [
    ("missing", "missing discovered skills"),
    ("unknown", "unknown inventory skills"),
    ("duplicate", "duplicate skill rows"),
])
def test_exact_discovery_rejects_missing_unknown_and_duplicate_rows(
    inventory_payload, discovered, mutation, expected
):
    payload = deepcopy(inventory_payload)
    if mutation == "missing":
        payload["skills"].pop()
    elif mutation == "unknown":
        row = deepcopy(payload["skills"][-1])
        row["name"] = "not-discovered"
        row["path"] = ".claude/skills/not-discovered/SKILL.md"
        payload["skills"].append(row)
    else:
        payload["skills"].append(deepcopy(payload["skills"][0]))

    assert any(expected in error for error in _errors(payload, discovered))


def test_catalog_rejects_multiple_or_unregistered_layers_and_bindings(
    inventory_payload, discovered
):
    payload = deepcopy(inventory_payload)
    _row(payload, "adapt-project")["layer"] = ["core", "framework"]
    _row(payload, "audit-decisions")["layer"] = "imaginary"
    _row(payload, "brainstorm-ideas")["binding"] = "wishful"
    _row(payload, "check-ecosystem-consistency")["bindings"].append("wishful")

    errors = _errors(payload, discovered)
    assert any("layer must be exactly one registered layer ID" in error for error in errors)
    assert any("unregistered layer 'imaginary'" in error for error in errors)
    assert any("unregistered binding 'wishful'" in error for error in errors)


def test_catalog_rejects_unknown_readiness_and_metadata_drift(
    inventory_payload, discovered
):
    payload = deepcopy(inventory_payload)
    _row(payload, "adapt-project")["readiness"] = "verified"
    _row(payload, "audit-decisions")["current"]["language"] = "python"

    errors = _errors(payload, discovered)
    assert any("unregistered readiness 'verified'" in error for error in errors)
    assert any("current.language" in error and "frontmatter" in error for error in errors)


def test_catalog_rejects_unknown_schema_fields_and_rationale_shape_drift(
    inventory_payload, discovered
):
    payload = deepcopy(inventory_payload)
    payload["support"] = "verified"
    _row(payload, "extract-enum")["rationale"] = "django-framework-native"

    errors = _errors(payload, discovered)
    assert any("unknown top-level fields: ['support']" in error for error in errors)
    assert any(
        "rationale 'django-framework-native' requires layer 'framework'" in error
        for error in errors
    )


def test_domain_cohesion_rejects_two_members_and_accepts_three(
    inventory_payload, discovered
):
    registry = _registry_with_domain_binding()
    payload = deepcopy(inventory_payload)
    payload["rationales"]["domain-native"] = {
        "description": "Three-member domain cohesion fixture.",
        "layer": "domain",
        "placement": "native",
    }
    names = ["adapt-project", "audit-decisions", "brainstorm-ideas"]
    for name in names[:2]:
        row = _row(payload, name)
        row.update(
            layer="domain",
            binding="payments",
            bindings=["payments"],
            placement="native",
            rationale="domain-native",
        )

    errors = _errors(payload, discovered, registry)
    assert any("domain binding 'payments' has 2 members; at least 3" in error for error in errors)

    row = _row(payload, names[2])
    row.update(
        layer="domain",
        binding="payments",
        bindings=["payments"],
        placement="native",
        rationale="domain-native",
    )
    errors = _errors(payload, discovered, registry)
    assert errors == []


def test_singleton_shipping_layers_and_concept_binding_default_are_valid(
    inventory_payload, discovered
):
    assert _errors(inventory_payload, discovered) == []

    payload = deepcopy(inventory_payload)
    _row(payload, "extract-enum")["placement"] = "native"
    errors = _errors(payload, discovered)
    assert any("core with overlays must use placement 'concept-plus-binding'" in error for error in errors)


def test_host_overlay_shipping_contract_is_valid_at_one_member(
    inventory_payload, discovered
):
    payload = deepcopy(inventory_payload)
    payload["rationales"]["host-native"] = {
        "description": "Singleton host shipping-contract fixture.",
        "layer": "host-overlay",
        "placement": "native",
    }
    _row(payload, "adapt-project").update(
        layer="host-overlay",
        binding="tenant-policy",
        bindings=["tenant-policy"],
        placement="native",
        rationale="host-native",
    )

    assert _errors(payload, discovered, _registry_with_host_binding()) == []


def test_ar3_membership_is_explicit_and_cannot_be_reinterpreted(
    inventory_payload, discovered
):
    payload = deepcopy(inventory_payload)
    _row(payload, "refactor-subsystem")["ar3_foundation_member"] = False
    _row(payload, "which-shape")["ar3_foundation_member"] = True

    errors = _errors(payload, discovered)
    assert any("ar3_de_flavor_members disagrees with row membership" in error for error in errors)


def test_deferred_rows_remain_inventory_state_not_support_promotion():
    catalog = load_catalog(INVENTORY, skills_dir=SKILLS_DIR, project_root=REPO_ROOT)

    deferred = [entry for entry in catalog.entries if entry.readiness == "deferred-to-wp8"]
    assert len(deferred) == 60
    assert all(entry.readiness != "foundation-ready" for entry in deferred)
    assert all("support" not in entry.raw for entry in deferred)


def test_plan_skill_asks_the_frozen_placement_question():
    body = (SKILLS_DIR / "plan-skill/SKILL.md").read_text(encoding="utf-8")
    assert (
        "Which shipping layer owns the concept, and if the content is "
        "language/framework-flavored, why is this concept+binding rather "
        "than native? If domain is proposed, name at least three cohesive members."
    ) in body.replace("\n", " ")


def test_load_catalog_reports_all_validation_errors(inventory_payload, tmp_path):
    path = tmp_path / "inventory.yml"
    payload = deepcopy(inventory_payload)
    _row(payload, "adapt-project")["readiness"] = "verified"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(CatalogError, match="unregistered readiness"):
        load_catalog(path, skills_dir=SKILLS_DIR, project_root=REPO_ROOT)
