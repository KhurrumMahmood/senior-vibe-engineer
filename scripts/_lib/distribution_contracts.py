"""Reference semantic validation for ADR 0042 distribution contracts.

Draft 2020-12 validation remains the structural gate.  This module owns the
cross-field, cross-document, canonical-byte, and ordering rules that JSON
Schema cannot express.  Callers must run both gates before trusting a record.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from .host_profile import HOST_PROFILE_SCHEMA_VERSION


CONTRACT_ROOT = Path(__file__).resolve().parents[2] / ".claude/skills/_common/distribution"
SURFACE_IDS = frozenset({"augment", "claude-code", "codex", "cursor", "gemini"})
ALIAS_ROW_FIELDS = frozenset(
    {
        "public_name",
        "canonical_target",
        "surface_spellings",
        "introduced_release",
        "retirement_release",
    }
)
TABLE_NAMES = ("aliases-v1", "compatibility-v1", "legacy-layouts-v1")
SHAPE_ROUTER_ID = "which-shape-lexical-v1"
SKILL_ROUTER_ID = "which-skill-overlap-v1"
SKILL_THRESHOLD = 5
MAX_TOTAL_TOKENS = 32768
MAX_OUTPUT_TOKENS = 8192
PACK_RESULT_TUPLE = (
    "workflow_id",
    "dispatch_id",
    "prior_dispatch_id",
    "workflow_pack_ordinal",
    "attempt_ordinal",
    "execution_lane",
    "continuation_reason",
    "fallback_reason",
)
INITIAL_PARENT_FALLBACKS = {
    "conversation_state_required",
    "user_interaction_required",
    "nondelegable_authority_required",
    "surface_worker_unsupported",
}
_PUBLIC_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INTEGER_COMPATIBILITY = {
    "alias_schema": 1,
    "bundle_index_schema": 1,
    "capability_registry_contract": 1,
    "capability_registry_schema": 1,
    "catalog_inventory_schema": 1,
    "dispatch_pack_schema": 1,
    "dispatch_result_schema": 1,
    "dispatcher_policy_schema": 1,
    "host_profile_schema": HOST_PROFILE_SCHEMA_VERSION,
    "installed_manifest_schema": 1,
    "legacy_layout_schema": 1,
    "release_root_schema": 1,
}
_SURFACE_COMPATIBILITY = {
    "augment": "imported-rules-v1",
    "claude-code": "2.1.211",
    "codex": "0.144.1",
    "cursor": "project-rules-v1",
    "gemini": "0.45.0",
}


class DistributionContractError(ValueError):
    """A distribution trust input violates its structural or semantic contract."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DistributionContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_integer_number(value: str) -> None:
    raise DistributionContractError(f"non-integer JSON number: {value}")


def load_canonical_json(path: Path | str) -> Any:
    """Load strict UTF-8 JSON and require its raw bytes to be canonical."""
    source = Path(path)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_non_integer_number,
            parse_float=_reject_non_integer_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DistributionContractError(f"{source}: invalid strict UTF-8 JSON") from exc
    if raw != canonical_json_bytes(value):
        raise DistributionContractError(f"{source}: raw bytes are not RFC-8785 canonical")
    return value


def _require_exact_keys(
    value: object, expected: frozenset[str] | set[str], location: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DistributionContractError(f"{location} must be an object")
    if set(value) != expected:
        raise DistributionContractError(
            f"{location} must contain exactly {sorted(expected)}"
        )
    return value


def _require_schema_one(value: object, location: str) -> None:
    if type(value) is not int or value != 1:
        raise DistributionContractError(f"{location}.schema_version must equal integer 1")


def validate_alias_table(
    value: object, canonical_names: Sequence[str] | set[str] | frozenset[str]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validate aliases-v1 and resolve every alias to a canonical procedure."""
    table = _require_exact_keys(value, {"aliases", "schema_version"}, "aliases-v1")
    _require_schema_one(table["schema_version"], "aliases-v1")
    aliases = table["aliases"]
    if not isinstance(aliases, list):
        raise DistributionContractError("aliases-v1.aliases must be an array")

    canonical = set(canonical_names)
    if any(not isinstance(name, str) or _PUBLIC_NAME.fullmatch(name) is None for name in canonical):
        raise DistributionContractError("canonical procedure names must use public-name grammar")

    rows: list[dict[str, Any]] = []
    direct: dict[str, str] = {}
    for index, candidate in enumerate(aliases):
        location = f"aliases-v1.aliases[{index}]"
        row = _require_exact_keys(candidate, ALIAS_ROW_FIELDS, location)
        public_name = row["public_name"]
        target = row["canonical_target"]
        if not isinstance(public_name, str) or _PUBLIC_NAME.fullmatch(public_name) is None:
            raise DistributionContractError(f"{location}.public_name is not a safe public name")
        if not isinstance(target, str) or _PUBLIC_NAME.fullmatch(target) is None:
            raise DistributionContractError(
                f"{location}.canonical_target is not a safe public name"
            )
        if public_name in canonical or public_name in direct:
            raise DistributionContractError(f"alias collision: {public_name!r}")

        spellings = _require_exact_keys(
            row["surface_spellings"], SURFACE_IDS, f"{location}.surface_spellings"
        )
        if any(spelling != public_name for spelling in spellings.values()):
            raise DistributionContractError(
                f"{location}.surface_spellings must all equal public_name"
            )
        introduced = row["introduced_release"]
        if type(introduced) is not int or introduced < 1:
            raise DistributionContractError(
                f"{location}.introduced_release must be a positive integer"
            )
        retirement = row["retirement_release"]
        if retirement is not None and (
            type(retirement) is not int or retirement < introduced
        ):
            raise DistributionContractError(
                f"{location}.retirement_release must be null or at least introduced_release"
            )
        direct[public_name] = target
        rows.append(dict(row))

    public_names = [row["public_name"] for row in rows]
    if public_names != sorted(public_names):
        raise DistributionContractError("aliases-v1.aliases must be sorted by public_name")

    known_targets = canonical | set(direct)
    resolved: dict[str, str] = {}
    for public_name, target in direct.items():
        if target not in known_targets:
            raise DistributionContractError(
                f"alias {public_name!r} has stale target {target!r}"
            )
        seen = {public_name}
        while target in direct:
            if target in seen:
                raise DistributionContractError(f"alias cycle includes {public_name!r}")
            seen.add(target)
            target = direct[target]
        resolved[public_name] = target
    return rows, resolved


def validate_legacy_layouts_table(value: object) -> None:
    """Validate the explicit initial empty legacy-layout authority."""
    table = _require_exact_keys(value, {"layouts", "schema_version"}, "legacy-layouts-v1")
    _require_schema_one(table["schema_version"], "legacy-layouts-v1")
    if table["layouts"] != []:
        raise DistributionContractError(
            "legacy-layouts-v1.layouts must remain empty until a closed row contract exists"
        )


def validate_compatibility_table(value: object) -> None:
    """Validate every exact compatibility-v1 bound and router identifier."""
    expected_keys = {
        "router_ids",
        "schema_version",
        "surfaces",
        *_INTEGER_COMPATIBILITY,
    }
    table = _require_exact_keys(value, expected_keys, "compatibility-v1")
    _require_schema_one(table["schema_version"], "compatibility-v1")
    for field, expected in _INTEGER_COMPATIBILITY.items():
        bound = _require_exact_keys(
            table[field], {"lower", "upper"}, f"compatibility-v1.{field}"
        )
        if any(
            type(bound[key]) is not int or bound[key] != expected
            for key in ("lower", "upper")
        ):
            raise DistributionContractError(
                f"compatibility-v1.{field} must pin {expected} exactly"
            )
    if table["router_ids"] != {
        "which_shape": "which-shape-lexical-v1",
        "which_skill": "which-skill-overlap-v1",
    }:
        raise DistributionContractError("compatibility-v1.router_ids differ from v1")
    expected_surfaces = {
        surface: {"lower": version, "upper": version}
        for surface, version in _SURFACE_COMPATIBILITY.items()
    }
    if table["surfaces"] != expected_surfaces:
        raise DistributionContractError("compatibility-v1.surfaces differ from v1")


def load_distribution_tables(
    contract_root: Path | str,
    *,
    canonical_names: Sequence[str] | set[str] | frozenset[str],
) -> dict[str, Any]:
    """Load and validate all three release-root reference tables."""
    root = Path(contract_root)
    tables = {
        name: load_canonical_json(root / f"{name}.json") for name in TABLE_NAMES
    }
    validate_alias_table(tables["aliases-v1"], canonical_names)
    validate_compatibility_table(tables["compatibility-v1"])
    validate_legacy_layouts_table(tables["legacy-layouts-v1"])
    return tables


def _json_string(value: str) -> str:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise DistributionContractError("canonical JSON contains invalid Unicode") from exc
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _canonical_json_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        return _json_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise DistributionContractError("canonical JSON object keys must be strings")
        # RFC 8785 inherits ECMAScript's UTF-16 code-unit property ordering.
        keys = sorted(value, key=lambda key: key.encode("utf-16be", errors="strict"))
        return "{" + ",".join(
            f"{_json_string(key)}:{_canonical_json_text(value[key])}" for key in keys
        ) + "}"
    raise DistributionContractError(
        f"canonical JSON permits only integers and JSON primitives, got {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return RFC 8785 bytes for the integer-only subset used by the contracts."""
    return _canonical_json_text(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash the ADR 0042 canonical JSON digest domain."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@lru_cache(maxsize=16)
def _schema(name: str) -> dict[str, Any]:
    path = CONTRACT_ROOT / f"{name}.schema.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistributionContractError(f"cannot load contract schema {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DistributionContractError(f"contract schema {path} is not an object")
    return value


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise DistributionContractError(f"unsupported non-local schema reference: {ref}")
    value: Any = root
    try:
        for part in ref[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError) as exc:
        raise DistributionContractError(f"unresolved schema reference: {ref}") from exc
    if not isinstance(value, dict):
        raise DistributionContractError(f"schema reference is not an object: {ref}")
    return value


def _annotation_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    location: str = "$",
) -> list[str]:
    if "$ref" in schema:
        referenced = _resolve_ref(root, schema["$ref"])
        merged = dict(referenced)
        merged.update({key: item for key, item in schema.items() if key != "$ref"})
        return _annotation_errors(value, merged, root, location)

    errors: list[str] = []
    if isinstance(value, str):
        try:
            byte_length = len(value.encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            errors.append(f"{location} contains invalid Unicode")
        else:
            maximum = schema.get("x-maxUtf8Bytes")
            if maximum is not None and byte_length > maximum:
                errors.append(f"{location} UTF-8 bytes exceed {maximum}")
        if schema.get("x-requireNfc") and unicodedata.normalize("NFC", value) != value:
            errors.append(f"{location} must be NFC")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    _annotation_errors(item, properties[key], root, f"{location}.{key}")
                )
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _annotation_errors(item, item_schema, root, f"{location}[{index}]")
                )
        maximum = schema.get("x-maxAggregateArtifactBytes")
        if maximum is not None:
            total = sum(item.get("size", 0) for item in value if isinstance(item, dict))
            if total > maximum:
                errors.append(f"{location} aggregate artifact bytes exceed {maximum}")

    maximum = schema.get("x-maxCanonicalBytes")
    if maximum is not None:
        try:
            byte_length = len(canonical_json_bytes(value))
        except DistributionContractError as exc:
            errors.append(f"{location} cannot be canonicalized: {exc}")
        else:
            if byte_length > maximum:
                errors.append(f"{location} canonical UTF-8 bytes exceed {maximum}")
    return errors


def _utf8(value: str) -> bytes:
    return value.encode("utf-8", errors="strict")


def _sorted_score_rows(rows: list[dict[str, Any]], *name_fields: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (-row["score"], *(_utf8(row[name]) for name in name_fields)))


def _shape_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document["router_id"] != SHAPE_ROUTER_ID:
        errors.append(f"router_id must equal {SHAPE_ROUTER_ID}")
    candidates = document["candidates"]
    if candidates != _sorted_score_rows(candidates, "shape_id"):
        errors.append("candidates must be sorted by descending score then UTF-8 shape_id")
    for index, candidate in enumerate(candidates):
        score = candidate["score"]
        expected = "high" if score >= 40 else "medium" if score >= 24 else "low"
        if candidate["confidence"] != expected:
            errors.append(
                f"candidates[{index}].confidence must be {expected} for score {score}"
            )
    if document["status"] == "ok":
        top_is_unique = len(candidates) == 1 or (
            len(candidates) > 1 and candidates[0]["score"] > candidates[1]["score"]
        )
        if not candidates or candidates[0]["score"] < 24 or not top_is_unique:
            errors.append("status ok requires a unique top score at least 24")
    if document["status"] == "clarification" and candidates:
        top_is_tied = len(candidates) > 1 and candidates[0]["score"] == candidates[1]["score"]
        if candidates[0]["score"] >= 24 and not top_is_tied:
            errors.append("status clarification requires a top-score tie or score below 24")
    return errors


def _skill_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document["router_id"] != SKILL_ROUTER_ID:
        errors.append(f"router_id must equal {SKILL_ROUTER_ID}")
    if document["scorer_id"] != SKILL_ROUTER_ID:
        errors.append(f"scorer_id must equal {SKILL_ROUTER_ID}")
    if document["threshold"] != SKILL_THRESHOLD:
        errors.append(f"threshold must equal {SKILL_THRESHOLD}")
    for field in ("candidates", "excluded"):
        rows = document[field]
        if rows != _sorted_score_rows(rows, "canonical_name", "public_name"):
            errors.append(
                f"{field} must be sorted by descending score then UTF-8 canonical_name/public_name"
            )
    scores = [candidate["score"] for candidate in document["candidates"]]
    if document["status"] == "ok" and (not scores or max(scores) < SKILL_THRESHOLD):
        errors.append(f"status ok is invalid when every candidate is below threshold {SKILL_THRESHOLD}")
    if document["status"] == "proceed_directly" and not document["quick"] and any(
        score >= SKILL_THRESHOLD for score in scores
    ):
        errors.append(
            f"status proceed_directly is invalid with a candidate at threshold {SKILL_THRESHOLD}"
        )
    if document["quick"] and document["status"] != "proceed_directly":
        errors.append("quick=true requires status proceed_directly")
    if (
        document["status"] == "proceed_directly"
        and not document["quick"]
        and not scores
    ):
        errors.append("status proceed_directly requires quick=true or compatible candidates")
    return errors


def _dispatch_tuple_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    attempt = document["attempt_ordinal"]
    lane = document["execution_lane"]
    reason = document["continuation_reason"]
    fallback = document["fallback_reason"]
    prior_dispatch_id = document["prior_dispatch_id"]
    ordinal = document["workflow_pack_ordinal"]

    if reason == "initial_selection" and ordinal != 1:
        errors.append("initial_selection requires workflow_pack_ordinal 1")
    if reason == "confirmed_sequence_step" and ordinal < 2:
        errors.append("confirmed_sequence_step requires workflow_pack_ordinal 2 through 16")
    if attempt == 1:
        if reason not in {"initial_selection", "confirmed_sequence_step"}:
            errors.append("attempt 1 requires an initial or confirmed sequence reason")
        if prior_dispatch_id is not None:
            errors.append("attempt 1 requires prior_dispatch_id null")
        if lane == "fresh-worker" and fallback is not None:
            errors.append("initial fresh-worker execution requires fallback_reason null")
        if lane == "selected-only-parent" and fallback not in INITIAL_PARENT_FALLBACKS:
            errors.append("initial selected-only-parent execution requires one allowed fallback reason")
    elif lane == "fresh-worker":
        if reason != "user_confirmed_worker_retry" or fallback is not None:
            errors.append("fresh-worker attempt 2 requires the confirmed worker-retry tuple")
        if prior_dispatch_id is None:
            errors.append("attempt 2 requires prior_dispatch_id")
    else:
        if (
            reason != "user_confirmed_parent_continuation"
            or fallback != "user_confirmed_after_worker_failure"
        ):
            errors.append("parent attempt 2 requires the confirmed parent-continuation tuple")
        if prior_dispatch_id is None:
            errors.append("attempt 2 requires prior_dispatch_id")
    return errors


def _pack_errors(
    document: dict[str, Any], prior_result: dict[str, Any] | None
) -> list[str]:
    errors = _dispatch_tuple_errors(document)
    basis = document["selection"]["selection_basis"]
    clarification_id = document["clarification_id"]
    if basis == "user_confirmed" and clarification_id is None:
        errors.append("selection_basis user_confirmed requires clarification_id")
    if basis != "user_confirmed" and clarification_id is not None:
        errors.append("clarification_id must be null unless selection_basis is user_confirmed")

    selection = document["selection"]
    procedure = document["procedure"]
    if selection["source_sha256"] != procedure["raw_sha256"]:
        errors.append("selection.source_sha256 must equal procedure.raw_sha256")
    if selection["rendered_sha256"] != procedure["rendered_sha256"]:
        errors.append("selection.rendered_sha256 must equal procedure.rendered_sha256")

    attempt = document["attempt_ordinal"]
    if attempt == 1:
        for field in (
            "prior_result_sha256",
            "continuation_plan_sha256",
            "side_effect_ledger_sha256",
        ):
            if document[field] is not None:
                errors.append(f"attempt 1 requires {field} null")
        return errors

    for field in ("prior_result_sha256", "continuation_plan_sha256"):
        if document[field] is None:
            errors.append(f"attempt 2 requires {field}")
    if prior_result is None:
        errors.append("attempt 2 semantic validation requires prior_result")
        return errors

    if document["prior_dispatch_id"] != prior_result["dispatch_id"]:
        errors.append("prior_dispatch_id must equal prior_result.dispatch_id")
    if document["prior_result_sha256"] != canonical_sha256(prior_result):
        errors.append("prior_result_sha256 must hash the exact canonical prior result")
    for field in ("workflow_id", "workflow_pack_ordinal"):
        if document[field] != prior_result[field]:
            errors.append(f"attempt 2 {field} must equal prior_result.{field}")
    if prior_result["attempt_ordinal"] != 1:
        errors.append("attempt 2 prior result must be attempt 1")
    if prior_result["execution_lane"] != "fresh-worker":
        errors.append("attempt 2 prior result must be from fresh-worker")
    if prior_result["status"] not in {"failed", "cancelled"}:
        errors.append("attempt 2 prior result must be failed or cancelled")

    disposition = prior_result["side_effect_disposition"]
    if disposition == "unknown":
        errors.append("unknown prior side effects prohibit retry or fallback")
    elif disposition == "committed_known":
        if document["execution_lane"] != "selected-only-parent":
            errors.append("committed_known permits only selected-only-parent continuation")
        if document["side_effect_ledger_sha256"] != prior_result["side_effect_ledger_sha256"]:
            errors.append("committed_known continuation must repeat the side-effect ledger digest")
    elif document["side_effect_ledger_sha256"] is not None:
        errors.append("none or rolled_back prior side effects require no side-effect ledger")

    consumed_total = prior_result["input_tokens"] + prior_result["output_tokens"]
    budget = document["budget"]
    if budget["remaining_total_tokens"] > MAX_TOTAL_TOKENS - consumed_total:
        errors.append("attempt 2 remaining_total_tokens resets the cumulative workflow budget")
    if budget["remaining_output_tokens"] > MAX_OUTPUT_TOKENS - prior_result["output_tokens"]:
        errors.append("attempt 2 remaining_output_tokens resets the cumulative workflow budget")
    if budget["remaining_milliseconds"] > 1_200_000 - prior_result["elapsed_milliseconds"]:
        errors.append("attempt 2 remaining_milliseconds resets the cumulative deadline")
    return errors


def _result_errors(document: dict[str, Any], pack: dict[str, Any] | None) -> list[str]:
    errors = _dispatch_tuple_errors(document)
    if document["input_tokens"] + document["output_tokens"] > MAX_TOTAL_TOKENS:
        errors.append(f"input_tokens + output_tokens exceed {MAX_TOTAL_TOKENS}")
    for index, artifact in enumerate(document["artifacts"]):
        expected_uri = f"artifact://sha256/{artifact['sha256']}"
        if artifact["uri"] != expected_uri:
            errors.append(f"artifacts[{index}] artifact URI digest must equal sha256")

    if pack is None:
        errors.append("dispatch-result-v1 semantic validation requires its dispatch pack")
        return errors
    for field in PACK_RESULT_TUPLE:
        if document[field] != pack[field]:
            errors.append(f"result must repeat pack {field}")
    budget = pack["budget"]
    if document["input_tokens"] + document["output_tokens"] > budget["remaining_total_tokens"]:
        errors.append("result model tokens exceed the pack's remaining total-token budget")
    if document["output_tokens"] > budget["remaining_output_tokens"]:
        errors.append("result output_tokens exceed the pack's remaining output-token budget")
    if document["elapsed_milliseconds"] > budget["remaining_milliseconds"]:
        errors.append("result elapsed time exceeds the pack's remaining deadline")
    return errors


def _file_identity(row: dict[str, Any]) -> tuple[str, int, str]:
    return row["path"], row["size"], row["sha256"]


def _manifest_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    surfaces = set(document["surface_set"])
    bootstrap_surfaces = [tree["surface_id"] for tree in document["bootstrap_trees"]]
    if len(bootstrap_surfaces) != len(set(bootstrap_surfaces)):
        errors.append("bootstrap tree surface_id values must be unique")
    if set(bootstrap_surfaces) != surfaces:
        errors.append("bootstrap tree surfaces must exactly equal surface_set")

    activation_names = [row["public_name"] for row in document["activation_records"]]
    if len(activation_names) != len(set(activation_names)):
        errors.append("activation public_name values must be unique")

    generated = document["generated_files"]
    generated_paths = [row["path"] for row in generated]
    if len(generated_paths) != len(set(generated_paths)):
        errors.append("generated file paths must be unique")
    for row in generated:
        if row["surface_id"] not in surfaces:
            errors.append(f"generated file surface {row['surface_id']} is not selected")

    class_map = {
        "bootstrap": "bootstrap_projections",
        "activation": "activation_projections",
        "full-discovery": "full_discovery_projections",
    }
    owned_paths = document["owned_paths"]
    for ownership_class, owned_class in class_map.items():
        generated_rows = {
            _file_identity(row) for row in generated if row["ownership_class"] == ownership_class
        }
        owned_rows = {_file_identity(row) for row in owned_paths[owned_class]}
        if generated_rows != owned_rows:
            errors.append(
                f"generated {ownership_class} files must exactly equal owned_paths.{owned_class}"
            )

    owned_file_paths: list[str] = []
    for class_name, rows in owned_paths.items():
        if class_name == "generated_links":
            owned_file_paths.extend(row["path"] for row in rows)
        else:
            owned_file_paths.extend(row["path"] for row in rows)
    if len(owned_file_paths) != len(set(owned_file_paths)):
        errors.append("owned path values must be globally unique")

    for tree in document["bootstrap_trees"]:
        rows = [
            {key: row[key] for key in ("path", "size", "sha256")}
            for row in generated
            if row["ownership_class"] == "bootstrap"
            and row["surface_id"] == tree["surface_id"]
        ]
        rows.sort(key=lambda row: _utf8(unicodedata.normalize("NFC", row["path"])))
        if tree["file_count"] != len(rows):
            errors.append(f"bootstrap tree {tree['surface_id']} file_count is inconsistent")
        if tree["tree_sha256"] != canonical_sha256(rows):
            errors.append(f"bootstrap tree {tree['surface_id']} digest is inconsistent")

    temporary_keys: list[tuple[str, str]] = []
    invocation_ids: list[str] = []
    for row in document["recovery"]["temporary_records"]:
        if row["surface_id"] not in surfaces:
            errors.append(f"temporary record surface {row['surface_id']} is not selected")
        temporary_keys.append((row["surface_id"], row["public_name"]))
        invocation_ids.append(row["invocation_id"])
    if len(temporary_keys) != len(set(temporary_keys)):
        errors.append("temporary surface/public_name pairs must be unique")
    if len(invocation_ids) != len(set(invocation_ids)):
        errors.append("temporary invocation_id values must be unique")

    generation = document["manifest_generation"]
    if (generation == 1) != (document["previous_manifest_sha256"] is None):
        errors.append("previous_manifest_sha256 must be null exactly for generation 1")
    if document["cleanup"]["last_cleaned_generation"] > generation:
        errors.append("last_cleaned_generation cannot exceed manifest_generation")
    if document["mode"] == "router-only" and owned_paths["full_discovery_projections"]:
        errors.append("router-only mode cannot own full-discovery projections")

    digest_domain = {key: value for key, value in document.items() if key != "manifest_sha256"}
    if document["manifest_sha256"] != canonical_sha256(digest_domain):
        errors.append("manifest_sha256 must hash the document with only manifest_sha256 omitted")
    return errors


def semantic_validation_errors(
    name: str,
    document: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
    prior_result: dict[str, Any] | None = None,
) -> list[str]:
    """Return every semantic violation for a structurally valid contract record."""
    schema = _schema(name)
    errors = _annotation_errors(document, schema, schema)
    if name == "which-shape-result-v1":
        errors.extend(_shape_errors(document))
    elif name == "which-skill-result-v1":
        errors.extend(_skill_errors(document))
    elif name == "dispatch-pack-v1":
        errors.extend(_pack_errors(document, prior_result))
    elif name == "dispatch-result-v1":
        errors.extend(_result_errors(document, pack))
    elif name == "installed-manifest-v1":
        errors.extend(_manifest_errors(document))
    return errors


def validate_distribution_contract(
    name: str,
    document: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
    prior_result: dict[str, Any] | None = None,
) -> None:
    """Raise when a structurally valid contract violates ADR 0042 semantics."""
    errors = semantic_validation_errors(
        name,
        document,
        pack=pack,
        prior_result=prior_result,
    )
    if errors:
        raise DistributionContractError("; ".join(errors))
