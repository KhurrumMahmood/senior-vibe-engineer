from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from _lib.distribution_contracts import (
    DistributionContractError,
    canonical_json_bytes,
    validate_distribution_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / ".claude/skills/_common/distribution"
SCHEMA_NAMES = (
    "release-root-v1",
    "bundle-index-v1",
    "installed-manifest-v1",
    "surface-activation-contract-v1",
    "which-shape-result-v1",
    "which-skill-result-v1",
    "dispatch-pack-v1",
    "dispatch-result-v1",
)
TABLE_NAMES = ("aliases-v1", "legacy-layouts-v1", "compatibility-v1")
HASH = "a" * 64
UUID = "123e4567-e89b-42d3-a456-426614174000"
SCHEMA_KEYWORDS = {
    "$defs",
    "$id",
    "$ref",
    "$schema",
    "additionalProperties",
    "allOf",
    "anyOf",
    "const",
    "contains",
    "description",
    "else",
    "enum",
    "if",
    "items",
    "maxContains",
    "maximum",
    "maxItems",
    "maxLength",
    "minContains",
    "minimum",
    "minItems",
    "minLength",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "then",
    "title",
    "type",
    "uniqueItems",
}


class StrictJsonError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/"), ref
    value: Any = root
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    assert isinstance(value, dict)
    return value


def _is_type(value: Any, expected: str) -> bool:
    return {
        "array": isinstance(value, list),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "null": value is None,
        "number": type(value) in {int, float},
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
    }[expected]


def _canonical_bytes(value: Any) -> bytes:
    # Test exemplars use the RFC-8785-compatible JSON subset: integers, strict
    # Unicode strings, arrays, objects, booleans, and null.
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _validation_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    location: str = "$",
) -> list[str]:
    if "$ref" in schema:
        referenced = _resolve_ref(root, schema["$ref"])
        merged = dict(referenced)
        merged.update({key: item for key, item in schema.items() if key != "$ref"})
        return _validation_errors(value, merged, root, location)

    errors: list[str] = []
    expected_types = schema.get("type")
    if expected_types is not None:
        choices = [expected_types] if isinstance(expected_types, str) else expected_types
        if not any(_is_type(value, expected) for expected in choices):
            return [f"{location}: type differs from {choices}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: const differs")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: value is outside enum")

    if isinstance(value, dict):
        required = set(schema.get("required", ()))
        missing = required - set(value)
        if missing:
            errors.append(f"{location}: missing {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(properties)
            if unknown:
                errors.append(f"{location}: unknown {sorted(unknown)}")
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    _validation_errors(item, properties[key], root, f"{location}.{key}")
                )

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{location}: too few items")
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{location}: too many items")
        if schema.get("uniqueItems"):
            encoded = [_canonical_bytes(item) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: duplicate items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(
                    _validation_errors(item, item_schema, root, f"{location}[{index}]")
                )
        if "contains" in schema:
            matches = sum(
                not _validation_errors(item, schema["contains"], root, location)
                for item in value
            )
            if matches < schema.get("minContains", 1):
                errors.append(f"{location}: contains has too few matches")
            if matches > schema.get("maxContains", matches):
                errors.append(f"{location}: contains has too many matches")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: string is too short")
        if len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{location}: string is too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{location}: string does not match pattern")
        if len(value.encode("utf-8")) > schema.get("x-maxUtf8Bytes", 2**63):
            errors.append(f"{location}: string exceeds UTF-8 byte bound")
        if schema.get("x-requireNfc") and unicodedata.normalize("NFC", value) != value:
            errors.append(f"{location}: string is not NFC")

    if type(value) in {int, float}:
        if value < schema.get("minimum", value):
            errors.append(f"{location}: number is below minimum")
        if value > schema.get("maximum", value):
            errors.append(f"{location}: number is above maximum")

    for subschema in schema.get("allOf", ()):
        errors.extend(_validation_errors(value, subschema, root, location))
    if "anyOf" in schema:
        if not any(not _validation_errors(value, item, root, location) for item in schema["anyOf"]):
            errors.append(f"{location}: no anyOf branch matched")
    if "oneOf" in schema:
        matches = sum(
            not _validation_errors(value, item, root, location)
            for item in schema["oneOf"]
        )
        if matches != 1:
            errors.append(f"{location}: expected one oneOf match, got {matches}")
    if "if" in schema:
        branch = "then" if not _validation_errors(value, schema["if"], root, location) else "else"
        if branch in schema:
            errors.extend(_validation_errors(value, schema[branch], root, location))

    if len(_canonical_bytes(value)) > schema.get("x-maxCanonicalBytes", 2**63):
        errors.append(f"{location}: document exceeds canonical byte bound")
    if isinstance(value, list) and "x-maxAggregateArtifactBytes" in schema:
        total = sum(item.get("size", 0) for item in value if isinstance(item, dict))
        if total > schema["x-maxAggregateArtifactBytes"]:
            errors.append(f"{location}: aggregate artifact bytes exceed bound")
    return errors


def _assert_valid(value: Any, schema: dict[str, Any]) -> None:
    assert _validation_errors(value, schema, schema) == []


def _file_row(path: str) -> dict[str, Any]:
    return {"path": path, "size": 1, "sha256": HASH}


def _release_root() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "bundle_version": "1.0.0",
        "bundle_index": _file_row("bundle-index-v1.json"),
        "installer": _file_row("scripts/skill-installer.py"),
        "surface_activation_contract": _file_row("surface-contract-v1.json"),
        "schemas": [
            {"schema_id": name, **_file_row(f"schemas/{name}.schema.json")}
            for name in SCHEMA_NAMES
        ],
        "tables": [
            {"table_id": name, **_file_row(f"tables/{name}.json")}
            for name in TABLE_NAMES
        ],
    }


def _bundle_index() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "bundle_version": "1.0.0",
        "catalog_inventory_sha256": HASH,
        "capability_registry_sha256": HASH,
        "required_profile_sha256": HASH,
        "blobs": [
            {
                "kind": "catalog",
                "id": "skill-catalog",
                "path": "catalog/inventory.json",
                "size": 1,
                "sha256": HASH,
                "media_type": "application/json",
            }
        ],
        "tree_sha256": HASH,
    }


def _surface_contract() -> dict[str, Any]:
    versions = {
        "claude-code": "2.1.211",
        "codex": "0.144.1",
        "augment": "imported-rules-v1",
        "cursor": "project-rules-v1",
        "gemini": "0.45.0",
    }
    identities = {
        "claude-code": {
            "public_identity": {
                "which_shape": "/which-shape",
                "which_skill": "/which-skill",
                "alias_template": "/{public-name}",
            },
            "generated_identity": {
                "which_shape": ".claude/skills/which-shape/SKILL.md",
                "which_skill": ".claude/skills/which-skill/SKILL.md",
                "alias_template": ".claude/skills/{public-name}/SKILL.md",
            },
        },
        "codex": {
            "public_identity": {
                "which_shape": "$engineering-skills:which-shape",
                "which_skill": "$engineering-skills:which-skill",
                "alias_template": "$engineering-skills:{public-name}",
            },
            "generated_identity": {
                "which_shape": "skills/which-shape/SKILL.md",
                "which_skill": "skills/which-skill/SKILL.md",
                "alias_template": "skills/{public-name}/SKILL.md",
            },
        },
        "augment": {
            "public_identity": {
                "which_shape": "use skill which-shape",
                "which_skill": "use skill which-skill",
                "alias_template": "use skill {public-name}",
            },
            "generated_identity": {
                "which_shape": ".augment/rules/imported/which-shape/SKILL.md",
                "which_skill": ".augment/rules/imported/which-skill/SKILL.md",
                "alias_template": ".augment/rules/imported/{public-name}/SKILL.md",
            },
        },
        "cursor": {
            "public_identity": {
                "which_shape": "use skill which-shape",
                "which_skill": "use skill which-skill",
                "alias_template": "use skill {public-name}",
            },
            "generated_identity": {
                "which_shape": ".cursor/rules/which-shape/SKILL.mdc",
                "which_skill": ".cursor/rules/which-skill/SKILL.mdc",
                "alias_template": ".cursor/rules/{public-name}/SKILL.mdc",
            },
        },
        "gemini": {
            "public_identity": {
                "which_shape": "use skill which-shape",
                "which_skill": "use skill which-skill",
                "alias_template": "use skill {public-name}",
            },
            "generated_identity": {
                "which_shape": ".gemini/skills/which-shape/SKILL.md",
                "which_skill": ".gemini/skills/which-skill/SKILL.md",
                "alias_template": ".gemini/skills/{public-name}/SKILL.md",
            },
        },
    }
    return {
        "schema_version": 1,
        "contract_version": 1,
        "surfaces": [
            {
                "surface_id": surface,
                "runtime_version": {"lower": version, "upper": version},
                "projection_format": f"{surface}-projection-v1",
                **identities[surface],
                "discovery": {
                    "command": [surface, "list"],
                    "parser_id": f"{surface}-list-v1",
                    "offline_non_model": True,
                },
                "activation": {
                    "operation": f"{surface}-activation-v1",
                    "temporary_activation": "unsupported",
                    "terminal_wrapper": None,
                    "startup_cleanup": None,
                },
                "worker": {
                    "fresh_worker": "unsupported",
                    "launcher": None,
                    "version_range": None,
                    "selected_procedure_injection": None,
                    "cancellation": None,
                    "result": None,
                    "zero_conversation_turns_proof": None,
                    "budget_enforcement": None,
                },
            }
            for surface, version in versions.items()
        ],
    }


def _installed_manifest() -> dict[str, Any]:
    empty_file_classes = {
        "catalog_store": [],
        "bootstrap_projections": [],
        "activation_projections": [],
        "full_discovery_projections": [],
        "activation_state": [],
        "recovery_journal": [],
        "generated_links": [],
    }
    return {
        "schema_version": 1,
        "manifest_sha256": HASH,
        "manifest_generation": 1,
        "previous_manifest_sha256": None,
        "bundle_version": "1.0.0",
        "release_root_sha256": HASH,
        "bundle_index_sha256": HASH,
        "surface_activation_contract_sha256": HASH,
        "catalog_hash": HASH,
        "mode": "router-only",
        "activation_records": [],
        "surface_set": ["claude-code"],
        "owned_paths": empty_file_classes,
        "generated_files": [
            {
                "ownership_class": "bootstrap",
                "surface_id": "claude-code",
                **_file_row(path),
            }
            for path in (
                ".claude/skills/which-shape/SKILL.md",
                ".claude/skills/which-skill/SKILL.md",
            )
        ],
        "bootstrap_trees": [
            {"surface_id": "claude-code", "file_count": 2, "tree_sha256": HASH}
        ],
        "recovery": {
            "state": "clean",
            "journal_path": ".engineering/recovery-v1.json",
            "journal_sha256": HASH,
            "temporary_records": [],
        },
        "cleanup": {
            "state": "clean",
            "last_cleaned_generation": 1,
            "failure_code": None,
        },
        "delegation_policy": {
            "dispatcher_policy_version": 1,
            "project_lane_limit": 1,
            "delegation_depth": 1,
            "max_workflow_packs": 16,
            "max_dispatches_per_pack": 2,
            "deadline_seconds": 1200,
            "total_token_budget": 32768,
            "output_token_budget": 8192,
            "fallback_reasons": [
                "conversation_state_required",
                "user_interaction_required",
                "nondelegable_authority_required",
                "surface_worker_unsupported",
                "user_confirmed_after_worker_failure",
            ],
        },
    }


def _shape_result() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "router_id": "which-shape-lexical-v1",
        "normalizer_id": "ascii-wordset-v1",
        "task_sha256": HASH,
        "profile_sha256": HASH,
        "status": "ok",
        "candidates": [],
        "error": None,
    }


def _skill_result() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "router_id": "which-skill-overlap-v1",
        "normalizer_id": "ascii-wordset-v1",
        "scorer_id": "which-skill-overlap-v1",
        "threshold": 5,
        "task_sha256": HASH,
        "profile_sha256": HASH,
        "quick": False,
        "status": "ok",
        "candidates": [],
        "excluded": [],
        "error": None,
    }


def _dispatch_pack() -> dict[str, Any]:
    body = "Do the selected work."
    body_sha256 = hashlib.sha256(body.encode()).hexdigest()
    arguments = "plan the feature"
    return {
        "schema_version": 1,
        "workflow_id": UUID,
        "dispatch_id": UUID,
        "prior_dispatch_id": None,
        "invocation_id": None,
        "clarification_id": None,
        "workflow_pack_ordinal": 1,
        "attempt_ordinal": 1,
        "execution_lane": "fresh-worker",
        "continuation_reason": "initial_selection",
        "fallback_reason": None,
        "selection": {
            "canonical_name": "plan-feature",
            "public_name": "plan-feature",
            "selection_basis": "unique_winner",
            "source_sha256": body_sha256,
            "rendered_sha256": body_sha256,
        },
        "roots": [
            {"project_root": "/workspace", "profile_sha256": HASH, "bindings": []}
        ],
        "task": {
            "arguments": arguments,
            "sha256": hashlib.sha256(canonical_json_bytes(arguments)).hexdigest(),
        },
        "procedure": {
            "body": body,
            "raw_sha256": body_sha256,
            "rendered_sha256": body_sha256,
        },
        "dependencies": [],
        "prior_result_sha256": None,
        "continuation_plan_sha256": None,
        "side_effect_ledger_sha256": None,
        "budget": {
            "deadline_started_monotonic_ns": 1,
            "remaining_milliseconds": 1200000,
            "remaining_total_tokens": 32768,
            "remaining_output_tokens": 8192,
        },
    }


def _dispatch_result() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow_id": UUID,
        "dispatch_id": UUID,
        "prior_dispatch_id": None,
        "workflow_pack_ordinal": 1,
        "attempt_ordinal": 1,
        "execution_lane": "fresh-worker",
        "continuation_reason": "initial_selection",
        "fallback_reason": None,
        "status": "success",
        "summary": "Completed.",
        "error_code": None,
        "error_message": None,
        "failure_kind": None,
        "side_effect_disposition": "none",
        "side_effect_ledger_sha256": None,
        "elapsed_milliseconds": 1,
        "input_tokens": 10,
        "output_tokens": 5,
        "artifacts": [],
    }


VALID_DOCUMENTS = {
    "release-root-v1": _release_root,
    "bundle-index-v1": _bundle_index,
    "installed-manifest-v1": _installed_manifest,
    "surface-activation-contract-v1": _surface_contract,
    "which-shape-result-v1": _shape_result,
    "which-skill-result-v1": _skill_result,
    "dispatch-pack-v1": _dispatch_pack,
    "dispatch-result-v1": _dispatch_result,
}


def _walk_schemas(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_schemas(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_schemas(child)


# spec:portable-skill-layer-distribution::IM-14
def test_im_14_phase_1_checks_in_exact_closed_contract_set() -> None:
    actual_schemas = {item.name.removesuffix(".schema.json") for item in CONTRACT_ROOT.glob("*.schema.json")}
    actual_tables = {
        item.name.removesuffix(".json")
        for item in CONTRACT_ROOT.glob("*.json")
        if not item.name.endswith(".schema.json")
    }

    assert actual_schemas == set(SCHEMA_NAMES)
    assert actual_tables == set(TABLE_NAMES)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_im_14_schemas_are_draft_2020_12_recursively_closed(name: str) -> None:
    schema = _load_json(CONTRACT_ROOT / f"{name}.schema.json")

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == f"urn:engineering-skills:schema:{name.removesuffix('-v1')}:v1"
    for subschema in _walk_schemas(schema):
        if set(subschema) & SCHEMA_KEYWORDS:
            assert all(key in SCHEMA_KEYWORDS or key.startswith("x-") for key in subschema)
        if "$ref" in subschema:
            _resolve_ref(schema, subschema["$ref"])
        if subschema.get("type") == "object":
            assert subschema.get("additionalProperties") is False
            assert set(subschema.get("required", ())) == set(subschema.get("properties", ()))


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_im_14_schema_accepts_its_closed_v1_exemplar(name: str) -> None:
    schema = _load_json(CONTRACT_ROOT / f"{name}.schema.json")
    _assert_valid(VALID_DOCUMENTS[name](), schema)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_im_14_schema_rejects_unknown_and_missing_top_level_fields(name: str) -> None:
    schema = _load_json(CONTRACT_ROOT / f"{name}.schema.json")
    valid = VALID_DOCUMENTS[name]()
    with_unknown = copy.deepcopy(valid)
    with_unknown["private_trust_override"] = HASH
    with_missing = copy.deepcopy(valid)
    with_missing.pop(next(iter(schema["required"])))

    assert any("unknown" in error for error in _validation_errors(with_unknown, schema, schema))
    assert any("missing" in error for error in _validation_errors(with_missing, schema, schema))


def test_im_14_deep_negative_contract_attacks_fail_closed() -> None:
    attacks: list[tuple[str, dict[str, Any]]] = []

    release = _release_root()
    release["schemas"][0]["schema_id"] = "bundle-index-v1"
    attacks.append(("release-root-v1", release))

    bundle = _bundle_index()
    bundle["blobs"][0]["path"] = "../outside.json"
    attacks.append(("bundle-index-v1", bundle))

    manifest = _installed_manifest()
    manifest["mode"] = "named"
    attacks.append(("installed-manifest-v1", manifest))

    surface_contract = _surface_contract()
    surface_contract["surfaces"][0]["surface_id"] = "codex"
    attacks.append(("surface-activation-contract-v1", surface_contract))

    pack = _dispatch_pack()
    pack["procedure"]["ambient_skill_body"] = "unselected"
    attacks.append(("dispatch-pack-v1", pack))

    pack = _dispatch_pack()
    pack["attempt_ordinal"] = 2
    attacks.append(("dispatch-pack-v1", pack))

    pack = _dispatch_pack()
    pack["workflow_pack_ordinal"] = 1.5
    attacks.append(("dispatch-pack-v1", pack))

    pack = _dispatch_pack()
    pack["roots"][0]["project_root"] = "/workspace/../escape"
    attacks.append(("dispatch-pack-v1", pack))

    result = _dispatch_result()
    result.update({"status": "cancelled", "failure_kind": "timeout"})
    attacks.append(("dispatch-result-v1", result))

    result = _dispatch_result()
    result["artifacts"] = [
        {
            "uri": f"artifact://sha256/{HASH}",
            "name": "artifact.bin",
            "media_type": "application/octet-stream",
            "size": 16777217,
            "sha256": HASH,
        }
    ]
    attacks.append(("dispatch-result-v1", result))

    shape = _shape_result()
    shape["candidates"] = [
        {"shape_id": "system", "score": 1, "confidence": "low", "rationales": ["invented"]}
    ]
    attacks.append(("which-shape-result-v1", shape))

    shape = _shape_result()
    shape["candidates"] = [
        {"shape_id": "system", "score": 40, "confidence": "medium", "rationales": []}
    ]
    attacks.append(("which-shape-result-v1", shape))

    pack = _dispatch_pack()
    pack["selection"]["selection_basis"] = "user_confirmed"
    attacks.append(("dispatch-pack-v1", pack))

    pack = _dispatch_pack()
    pack["workflow_pack_ordinal"] = 2
    attacks.append(("dispatch-pack-v1", pack))

    result = _dispatch_result()
    result["workflow_pack_ordinal"] = 2
    attacks.append(("dispatch-result-v1", result))

    for name, attacked in attacks:
        schema = _load_json(CONTRACT_ROOT / f"{name}.schema.json")
        assert _validation_errors(attacked, schema, schema), name


def test_surface_contract_accepts_fully_evidenced_verified_capabilities() -> None:
    contract = _surface_contract()
    surface = contract["surfaces"][0]
    surface["activation"] = {
        "operation": "claude-code-activation-v1",
        "temporary_activation": "verified",
        "terminal_wrapper": "claude-code-terminal-wrapper-v1",
        "startup_cleanup": "claude-code-startup-cleanup-v1",
    }
    surface["worker"] = {
        "fresh_worker": "verified",
        "launcher": "claude-code-worker-v1",
        "version_range": {"lower": "2.1.211", "upper": "2.1.211"},
        "selected_procedure_injection": "selected-procedure-pack-v1",
        "cancellation": "claude-code-cancellation-v1",
        "result": "dispatch-result-v1",
        "zero_conversation_turns_proof": "fresh-worker-probe-v1",
        "budget_enforcement": "dispatch-budget-wrapper-v1",
    }
    schema = _load_json(
        CONTRACT_ROOT / "surface-activation-contract-v1.schema.json"
    )

    _assert_valid(contract, schema)


@pytest.mark.parametrize(("identity", "field"), (
    ("public_identity", "which_shape"),
    ("public_identity", "which_skill"),
    ("public_identity", "alias_template"),
    ("generated_identity", "which_shape"),
    ("generated_identity", "which_skill"),
    ("generated_identity", "alias_template"),
))
def test_surface_contract_rejects_inexact_identity_for_every_surface(
    identity: str, field: str
) -> None:
    schema = _load_json(
        CONTRACT_ROOT / "surface-activation-contract-v1.schema.json"
    )

    for surface_index in range(5):
        contract = _surface_contract()
        contract["surfaces"][surface_index][identity][field] = "plausible-but-wrong"

        assert _validation_errors(contract, schema, schema), (
            contract["surfaces"][surface_index]["surface_id"],
            identity,
            field,
        )


@pytest.mark.parametrize("missing_proof", ("terminal_wrapper", "startup_cleanup"))
def test_verified_temporary_activation_rejects_null_proof_fields(
    missing_proof: str,
) -> None:
    contract = _surface_contract()
    activation = contract["surfaces"][0]["activation"]
    activation.update(
        {
            "temporary_activation": "verified",
            "terminal_wrapper": "terminal-wrapper-v1",
            "startup_cleanup": "startup-cleanup-v1",
        }
    )
    activation[missing_proof] = None
    schema = _load_json(
        CONTRACT_ROOT / "surface-activation-contract-v1.schema.json"
    )

    assert _validation_errors(contract, schema, schema)


@pytest.mark.parametrize(
    "missing_proof",
    (
        "launcher",
        "version_range",
        "selected_procedure_injection",
        "cancellation",
        "result",
        "zero_conversation_turns_proof",
        "budget_enforcement",
    ),
)
def test_verified_fresh_worker_rejects_null_proof_or_enforcement_fields(
    missing_proof: str,
) -> None:
    contract = _surface_contract()
    worker = contract["surfaces"][0]["worker"]
    worker.update(
        {
            "fresh_worker": "verified",
            "launcher": "worker-launcher-v1",
            "version_range": {"lower": "2.1.211", "upper": "2.1.211"},
            "selected_procedure_injection": "selected-procedure-pack-v1",
            "cancellation": "worker-cancellation-v1",
            "result": "dispatch-result-v1",
            "zero_conversation_turns_proof": "fresh-worker-probe-v1",
            "budget_enforcement": "dispatch-budget-wrapper-v1",
        }
    )
    worker[missing_proof] = None
    schema = _load_json(
        CONTRACT_ROOT / "surface-activation-contract-v1.schema.json"
    )

    assert _validation_errors(contract, schema, schema)


def test_im_14_strict_loader_rejects_duplicate_json_keys() -> None:
    with pytest.raises(StrictJsonError, match="duplicate key"):
        json.loads('{"schema_version":1,"schema_version":1}', object_pairs_hook=_unique_object)


@pytest.mark.parametrize(
    ("name", "document"),
    (
        ("dispatch-pack-v1", _dispatch_pack()),
        ("surface-activation-contract-v1", _surface_contract()),
    ),
)
def test_production_validator_runs_structural_unknown_field_gate(
    name: str, document: dict[str, Any]
) -> None:
    wrong_version_type = copy.deepcopy(document)
    wrong_version_type["schema_version"] = True
    _assert_semantically_invalid(
        name, wrong_version_type, "schema_version: const differs"
    )

    document["private_trust_override"] = HASH

    _assert_semantically_invalid(name, document, "unknown.*private_trust_override")


def test_attempt_two_requires_a_new_dispatch_id() -> None:
    prior = _dispatch_result()
    prior.update(
        {
            "status": "failed",
            "error_code": "worker_failed",
            "error_message": "failed",
            "failure_kind": "worker_failed",
            "side_effect_disposition": "rolled_back",
        }
    )
    retry = _dispatch_pack()
    retry.update(
        {
            "prior_dispatch_id": prior["dispatch_id"],
            "attempt_ordinal": 2,
            "continuation_reason": "user_confirmed_worker_retry",
            "prior_result_sha256": hashlib.sha256(
                canonical_json_bytes(prior)
            ).hexdigest(),
            "continuation_plan_sha256": "b" * 64,
            "budget": {
                **retry["budget"],
                "remaining_milliseconds": 1199999,
                "remaining_total_tokens": 32753,
                "remaining_output_tokens": 8187,
            },
        }
    )

    _assert_semantically_invalid(
        "dispatch-pack-v1",
        retry,
        "dispatch_id must differ",
        prior_result=prior,
    )


@pytest.mark.parametrize("attack", ("procedure", "binding", "task"))
def test_dispatch_pack_hashes_actual_inline_content(attack: str) -> None:
    pack = _dispatch_pack()
    binding_body = "Apply the selected binding."
    binding_digest = hashlib.sha256(binding_body.encode()).hexdigest()
    pack["roots"][0]["bindings"] = [
        {
            "binding_id": "python",
            "body": binding_body,
            "raw_sha256": binding_digest,
            "rendered_sha256": binding_digest,
        }
    ]
    if attack == "procedure":
        pack["procedure"]["body"] += " tampered"
        match = "procedure.raw_sha256 must hash"
    elif attack == "binding":
        pack["roots"][0]["bindings"][0]["body"] += " tampered"
        match = r"bindings\[0\].raw_sha256 must hash"
    else:
        pack["task"]["arguments"] += " tampered"
        match = "task.sha256 must hash"

    _assert_semantically_invalid("dispatch-pack-v1", pack, match)


def test_manifest_rejects_cross_surface_router_paths_after_coherent_rehash() -> None:
    manifest = _installed_manifest()
    for row, path in zip(
        manifest["generated_files"],
        ("skills/which-shape/SKILL.md", "skills/which-skill/SKILL.md"),
        strict=True,
    ):
        row["path"] = path
    manifest["owned_paths"]["bootstrap_projections"] = [
        {key: row[key] for key in ("path", "size", "sha256")}
        for row in manifest["generated_files"]
    ]
    tree_rows = [
        {key: row[key] for key in ("path", "size", "sha256")}
        for row in manifest["generated_files"]
    ]
    manifest["bootstrap_trees"][0]["tree_sha256"] = hashlib.sha256(
        canonical_json_bytes(tree_rows)
    ).hexdigest()
    manifest["manifest_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {
                key: value
                for key, value in manifest.items()
                if key != "manifest_sha256"
            }
        )
    ).hexdigest()

    _assert_semantically_invalid(
        "installed-manifest-v1", manifest, "exact surface router paths"
    )


def test_im_14_alias_and_legacy_tables_are_explicitly_empty_and_closed() -> None:
    aliases = _load_json(CONTRACT_ROOT / "aliases-v1.json")
    legacy = _load_json(CONTRACT_ROOT / "legacy-layouts-v1.json")

    assert aliases == {"schema_version": 1, "aliases": []}
    assert legacy == {"schema_version": 1, "layouts": []}


def test_im_14_compatibility_table_pins_every_closed_bound() -> None:
    compatibility = _load_json(CONTRACT_ROOT / "compatibility-v1.json")
    integer_bounds = {
        "release_root_schema": 1,
        "bundle_index_schema": 1,
        "installed_manifest_schema": 1,
        "alias_schema": 1,
        "legacy_layout_schema": 1,
        "dispatcher_policy_schema": 1,
        "dispatch_pack_schema": 1,
        "dispatch_result_schema": 1,
        "catalog_inventory_schema": 1,
        "capability_registry_schema": 1,
        "capability_registry_contract": 1,
        "host_profile_schema": 1,
    }
    surface_bounds = {
        "claude-code": "2.1.211",
        "codex": "0.144.1",
        "augment": "imported-rules-v1",
        "cursor": "project-rules-v1",
        "gemini": "0.45.0",
    }

    assert set(compatibility) == {
        "schema_version",
        *integer_bounds,
        "router_ids",
        "surfaces",
    }
    assert compatibility["schema_version"] == 1
    assert all(compatibility[key] == {"lower": value, "upper": value} for key, value in integer_bounds.items())
    assert compatibility["router_ids"] == {
        "which_shape": "which-shape-lexical-v1",
        "which_skill": "which-skill-overlap-v1",
    }
    assert compatibility["surfaces"] == {
        key: {"lower": value, "upper": value} for key, value in surface_bounds.items()
    }

    shape_schema = _load_json(CONTRACT_ROOT / "which-shape-result-v1.schema.json")
    skill_schema = _load_json(CONTRACT_ROOT / "which-skill-result-v1.schema.json")
    assert shape_schema["properties"]["router_id"]["const"] == compatibility["router_ids"][
        "which_shape"
    ]
    assert skill_schema["properties"]["router_id"]["const"] == compatibility["router_ids"][
        "which_skill"
    ]
    assert skill_schema["properties"]["scorer_id"]["const"] == compatibility["router_ids"][
        "which_skill"
    ]


def _assert_semantically_invalid(
    name: str,
    document: dict[str, Any],
    match: str,
    **context: Any,
) -> None:
    with pytest.raises(DistributionContractError, match=match):
        validate_distribution_contract(name, document, **context)


def test_im_14_router_semantics_enforce_confidence_thresholds_and_ordering() -> None:
    shape = _shape_result()
    shape["candidates"] = [
        {"shape_id": "system", "score": 40, "confidence": "high", "rationales": []},
        {"shape_id": "feature", "score": 24, "confidence": "medium", "rationales": []},
        {"shape_id": "quick", "score": 23, "confidence": "low", "rationales": []},
    ]
    validate_distribution_contract("which-shape-result-v1", shape)

    wrong_confidence = copy.deepcopy(shape)
    wrong_confidence["candidates"][0]["confidence"] = "medium"
    _assert_semantically_invalid(
        "which-shape-result-v1", wrong_confidence, "confidence: const differs"
    )

    wrong_order = copy.deepcopy(shape)
    wrong_order["candidates"].reverse()
    _assert_semantically_invalid(
        "which-shape-result-v1", wrong_order, "candidates must be sorted"
    )

    low_ok = copy.deepcopy(shape)
    low_ok["candidates"] = [low_ok["candidates"][-1]]
    low_ok["status"] = "ok"
    _assert_semantically_invalid(
        "which-shape-result-v1", low_ok, "status ok requires a unique top score at least 24"
    )

    skill = _skill_result()
    skill["candidates"] = [
        {
            "canonical_name": "zeta",
            "public_name": "zeta",
            "score": 6,
            "applicability": "compatible",
            "roots": [{"project_root_sha256": HASH, "bindings": []}],
            "rationales": [],
        },
        {
            "canonical_name": "alpha",
            "public_name": "alpha",
            "score": 5,
            "applicability": "compatible",
            "roots": [{"project_root_sha256": HASH, "bindings": []}],
            "rationales": [],
        },
    ]
    validate_distribution_contract("which-skill-result-v1", skill)

    below_threshold = copy.deepcopy(skill)
    below_threshold["candidates"][0]["score"] = 4
    below_threshold["candidates"][1]["score"] = 3
    below_threshold["status"] = "ok"
    _assert_semantically_invalid(
        "which-skill-result-v1", below_threshold, "below threshold 5"
    )

    wrong_order = copy.deepcopy(skill)
    wrong_order["candidates"].reverse()
    _assert_semantically_invalid(
        "which-skill-result-v1", wrong_order, "candidates must be sorted"
    )

    no_candidate = _skill_result()
    no_candidate["status"] = "proceed_directly"
    _assert_semantically_invalid(
        "which-skill-result-v1", no_candidate, "requires quick=true or compatible candidates"
    )

    zero_compatible_quick = _skill_result()
    zero_compatible_quick.update(
        {
            "quick": True,
            "status": "error",
            "error": "no_compatible_candidate",
            "excluded": [
                {
                    "canonical_name": "plan-feature",
                    "public_name": "plan-feature",
                    "score": 5,
                    "exclusions": ["binding_incompatible"],
                }
            ],
        }
    )
    validate_distribution_contract("which-skill-result-v1", zero_compatible_quick)

    forged_zero_compatible = copy.deepcopy(zero_compatible_quick)
    forged_zero_compatible["excluded"] = []
    _assert_semantically_invalid(
        "which-skill-result-v1",
        forged_zero_compatible,
        "requires zero candidates and at least one excluded row",
    )


def test_im_14_dispatch_pack_semantics_enforce_selection_and_digest_domains() -> None:
    pack = _dispatch_pack()
    validate_distribution_contract("dispatch-pack-v1", pack)

    user_confirmed = copy.deepcopy(pack)
    user_confirmed["selection"]["selection_basis"] = "user_confirmed"
    _assert_semantically_invalid(
        "dispatch-pack-v1", user_confirmed, "clarification_id: type differs"
    )

    wrong_initial_ordinal = copy.deepcopy(pack)
    wrong_initial_ordinal["workflow_pack_ordinal"] = 2
    _assert_semantically_invalid(
        "dispatch-pack-v1", wrong_initial_ordinal, "workflow_pack_ordinal: const differs"
    )

    wrong_sequence_ordinal = copy.deepcopy(pack)
    wrong_sequence_ordinal["continuation_reason"] = "confirmed_sequence_step"
    _assert_semantically_invalid(
        "dispatch-pack-v1", wrong_sequence_ordinal, "workflow_pack_ordinal: number is below minimum"
    )

    wrong_digest_domain = copy.deepcopy(pack)
    wrong_digest_domain["procedure"]["raw_sha256"] = "b" * 64
    _assert_semantically_invalid(
        "dispatch-pack-v1", wrong_digest_domain, "selection.source_sha256 must equal"
    )


def test_im_14_dispatch_result_semantics_bind_pack_tuple_attempt_and_prior_result() -> None:
    pack = _dispatch_pack()
    result = _dispatch_result()
    validate_distribution_contract("dispatch-result-v1", result, pack=pack)

    _assert_semantically_invalid(
        "dispatch-result-v1", result, "semantic validation requires its dispatch pack"
    )

    tuple_attack = copy.deepcopy(result)
    tuple_attack["workflow_pack_ordinal"] = 2
    _assert_semantically_invalid(
        "dispatch-result-v1", tuple_attack, "workflow_pack_ordinal: const differs", pack=pack
    )

    prior = copy.deepcopy(result)
    prior.update(
        {
            "status": "failed",
            "error_code": "worker_failed",
            "error_message": "failed",
            "failure_kind": "worker_failed",
            "side_effect_disposition": "rolled_back",
        }
    )
    retry = copy.deepcopy(pack)
    retry.update(
        {
            "dispatch_id": "123e4567-e89b-42d3-a456-426614174001",
            "prior_dispatch_id": prior["dispatch_id"],
            "attempt_ordinal": 2,
            "continuation_reason": "user_confirmed_worker_retry",
            "prior_result_sha256": __import__("hashlib").sha256(
                canonical_json_bytes(prior)
            ).hexdigest(),
            "continuation_plan_sha256": "b" * 64,
            "budget": {
                **pack["budget"],
                "remaining_milliseconds": 1199999,
                "remaining_total_tokens": 32753,
                "remaining_output_tokens": 8187,
            },
        }
    )
    validate_distribution_contract("dispatch-pack-v1", retry, prior_result=prior)

    retry["prior_dispatch_id"] = "123e4567-e89b-42d3-a456-426614174099"
    _assert_semantically_invalid(
        "dispatch-pack-v1", retry, "prior_dispatch_id must equal", prior_result=prior
    )


def test_im_14_semantic_validator_enforces_non_schema_byte_and_artifact_limits() -> None:
    non_nfc = _dispatch_pack()
    non_nfc["roots"][0]["project_root"] = "/workspace/cafe\u0301"
    _assert_semantically_invalid("dispatch-pack-v1", non_nfc, "must be NFC")

    oversized = _dispatch_pack()
    oversized["roots"] = [
        {
            "project_root": f"/workspace/{index}",
            "profile_sha256": HASH,
            "bindings": [
                {
                    "binding_id": f"binding-{binding}",
                    "body": "x" * 32768,
                    "raw_sha256": HASH,
                    "rendered_sha256": HASH,
                }
                for binding in range(16)
            ],
        }
        for index in range(2)
    ]
    _assert_semantically_invalid(
        "dispatch-pack-v1", oversized, "canonical UTF-8 bytes exceed 131072"
    )

    result = _dispatch_result()
    result["artifacts"] = [
        {
            "uri": f"artifact://sha256/{HASH}",
            "name": f"artifact-{index}.bin",
            "media_type": "application/octet-stream",
            "size": 16777216,
            "sha256": HASH,
        }
        for index in range(5)
    ]
    _assert_semantically_invalid(
        "dispatch-result-v1", result, "aggregate artifact bytes exceed 67108864"
    )

    uri_mismatch = _dispatch_result()
    uri_mismatch["artifacts"] = [
        {
            "uri": f"artifact://sha256/{'b' * 64}",
            "name": "artifact.bin",
            "media_type": "application/octet-stream",
            "size": 1,
            "sha256": HASH,
        }
    ]
    _assert_semantically_invalid(
        "dispatch-result-v1", uri_mismatch, "artifact URI digest must equal sha256"
    )

    token_overflow = _dispatch_result()
    token_overflow["input_tokens"] = 30000
    token_overflow["output_tokens"] = 5000
    _assert_semantically_invalid(
        "dispatch-result-v1", token_overflow, r"input_tokens \+ output_tokens exceed 32768"
    )


def test_im_14_installed_manifest_semantics_enforce_surface_and_path_coherence() -> None:
    manifest = _installed_manifest()
    manifest["owned_paths"]["bootstrap_projections"] = [
        {key: bootstrap_file[key] for key in ("path", "size", "sha256")}
        for bootstrap_file in manifest["generated_files"]
    ]
    tree_rows = [
        {key: bootstrap_file[key] for key in ("path", "size", "sha256")}
        for bootstrap_file in manifest["generated_files"]
    ]
    manifest["bootstrap_trees"][0]["tree_sha256"] = __import__("hashlib").sha256(
        canonical_json_bytes(tree_rows)
    ).hexdigest()
    manifest["manifest_sha256"] = __import__("hashlib").sha256(
        canonical_json_bytes({key: value for key, value in manifest.items() if key != "manifest_sha256"})
    ).hexdigest()
    validate_distribution_contract("installed-manifest-v1", manifest)

    duplicate_public = copy.deepcopy(manifest)
    duplicate_public["activation_records"] = [
        {"public_name": "plan-feature", "canonical_target": "plan-feature"},
        {"public_name": "plan-feature", "canonical_target": "scope-feature"},
    ]
    _assert_semantically_invalid(
        "installed-manifest-v1", duplicate_public, "activation public_name values must be unique"
    )

    missing_surface_tree = copy.deepcopy(manifest)
    missing_surface_tree["surface_set"].append("codex")
    _assert_semantically_invalid(
        "installed-manifest-v1", missing_surface_tree, "bootstrap tree surfaces must exactly equal"
    )

    unselected_surface = copy.deepcopy(manifest)
    unselected_surface["generated_files"][0]["surface_id"] = "codex"
    _assert_semantically_invalid(
        "installed-manifest-v1", unselected_surface, "generated file surface.*not selected"
    )

    duplicate_path = copy.deepcopy(manifest)
    duplicate_path["generated_files"].append(copy.deepcopy(duplicate_path["generated_files"][0]))
    _assert_semantically_invalid(
        "installed-manifest-v1", duplicate_path, "generated file paths must be unique"
    )
