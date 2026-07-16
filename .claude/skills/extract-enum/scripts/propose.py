#!/usr/bin/env python3
"""Render and semantically verify the Django extract-enum proposal boundary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ALLOWED_NORMALIZATIONS = [
    "temporary_absolute_roots",
    "timestamps_and_scan_ids",
    "markdown_whitespace",
    "semantically_irrelevant_table_order",
]
VOLATILE_KEYS = frozenset({"generated_at", "timestamp", "scan_id"})
BRIDGE_HINT = re.compile(r"vendor|bridge|webhook|external|import", re.IGNORECASE)
PATH_KEYS = frozenset({"file", "field_file", "path"})
TARGET_PATH_KEY = "target"


def _member_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper() or "EMPTY"
    return f"STATUS_{name}" if name[0].isdigit() else name


def _site(site: dict[str, Any]) -> dict[str, str]:
    return {
        "file": str(site["file"]),
        "literal": str(site["literal"]),
        "symbol": str(site["symbol"]),
    }


# spec:portable-skill-layer-distribution::IM-9
def build_semantics(targets: dict[str, Any]) -> dict[str, Any]:
    """Build the framework binding's final semantic contract."""
    if targets.get("carrier_kind") != "django-model-field":
        raise ValueError("Django renderer requires carrier_kind 'django-model-field'")
    literals = [
        {
            "case_variant_of": item.get("case_variant_of"),
            "count": int(item["count"]),
            "value": str(item["value"]),
        }
        for item in targets["literals"]
    ]
    variants = {item["value"] for item in literals if item["case_variant_of"] is not None}
    choices = targets.get("declared_choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("targets have no resolved declared choices; framework binding cannot infer wire identity")
    if any(
        not isinstance(choice, dict)
        or not isinstance(choice.get("wire_value"), str)
        or not isinstance(choice.get("label"), str)
        for choice in choices
    ):
        raise ValueError("declared choices must carry exact string wire_value and label pairs")
    members = [
        {
            "label": str(choice["label"]),
            "name": _member_name(str(choice["wire_value"])),
            "wire_value": str(choice["wire_value"]),
        }
        for choice in choices
    ]
    wire_values = {member["wire_value"] for member in members}
    default = targets["current_kwargs"].get("default")
    if default is not None and default not in wire_values:
        raise ValueError("field default is not one of the declared choice wire values")
    confirmed: list[dict[str, str]] = []
    legacy: list[dict[str, str]] = []
    bridges: list[dict[str, str]] = []
    dynamic: list[dict[str, str]] = []
    for raw in targets["comparison_sites"]:
        site = _site(raw)
        if site["literal"] in variants:
            legacy.append(site)
        elif site["literal"] in wire_values:
            confirmed.append(site)
        elif BRIDGE_HINT.search(" ".join((site["file"], site["symbol"], str(raw.get("evidence", ""))))):
            bridges.append(site)
        else:
            dynamic.append(site)
    assignments = [_site(item) for item in targets["assignment_sites"]]
    def sort_key(item: dict[str, str]) -> tuple[str, str, str]:
        return item["file"], item["symbol"], item["literal"]
    risks: list[dict[str, str]] = [
        {
            "action": "normalize_or_audit_persisted_value",
            "kind": "case_variant",
            "literal": value,
        }
        for value in sorted(variants)
    ]
    risks.extend(
        {
            "action": "keep_or_map_at_bridge",
            "kind": "third_party_bridge",
            "literal": site["literal"],
        }
        for site in sorted(bridges, key=sort_key)
    )
    collected_values = {item["value"] for item in literals}
    if collected_values != wire_values:
        risks.append(
            {
                "action": "reconcile_declared_choices_against_collected_literals",
                "kind": "declared_choices_drift",
            }
        )
    return {
        "assignment_sites": sorted(assignments, key=sort_key),
        "bridge_sites": sorted(bridges, key=sort_key),
        "confirmed_sites": sorted(confirmed, key=sort_key),
        "current_kwargs": dict(targets["current_kwargs"]),
        "dynamic_sites": sorted(dynamic, key=sort_key),
        "legacy_case_sites": sorted(legacy, key=sort_key),
        "literals": literals,
        "members": members,
        "risks": risks,
        "stop": {
            "execute": False,
            "required": [
                "all_sites_migrated",
                "production_values_subset_of_member_wire_values",
                "characterization_tests_green",
                "stringly_status_lint_clean",
            ],
        },
        "summary": {
            "assignments": len(assignments),
            "caller_files": len(targets["callers_by_file"]),
            "case_variants": len(variants),
            "comparisons": len(targets["comparison_sites"]),
            "literals": len(literals),
        },
        "target": {
            "field_file": str(targets["field_file"]),
            "field_symbol": str(targets["field_symbol"]),
            "model_class": str(targets["model_class"]),
            "target": (
                f"{targets['field_file']}::{targets['field_name']}::{targets['model_class']}"
            ),
        },
    }


def _normalized(
    value: Any,
    *,
    key: str = "",
    directory_root: str | None = None,
) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _normalized(
                item_value,
                key=item_key,
                directory_root=directory_root,
            )
            for item_key, item_value in sorted(value.items())
            if item_key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        rows = [
            _normalized(item, key=key, directory_root=directory_root)
            for item in value
        ]
        if key.endswith("_unordered_table"):
            return sorted(rows, key=lambda item: json.dumps(item, sort_keys=True))
        return rows
    if isinstance(value, str):
        text = value
        if directory_root is not None and key in PATH_KEYS:
            text = _normalize_directory_path(text, directory_root)
        elif directory_root is not None and key == TARGET_PATH_KEY:
            path, separator, identity = text.partition("::")
            if separator:
                text = _normalize_directory_path(path, directory_root) + separator + identity
        if key.endswith("_markdown"):
            text = re.sub(r"\s+", " ", text).strip()
        return text
    return value


def _contains_temporary_root(
    value: Any,
    root: str | None,
    *,
    key: str = "",
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_temporary_root(item_value, root, key=item_key)
            for item_key, item_value in value.items()
            if item_key not in VOLATILE_KEYS
        )
    if isinstance(value, list):
        return any(_contains_temporary_root(item, root, key=key) for item in value)
    if not isinstance(value, str) or root is None:
        return False
    candidate = value.partition("::")[0] if key == TARGET_PATH_KEY else value
    if key not in PATH_KEYS and key != TARGET_PATH_KEY:
        return False
    return candidate == root or candidate.startswith(root + "/")


def _normalize_directory_path(value: str, root: str) -> str:
    if value == root or value.startswith(root + "/"):
        return "<TEMP_ROOT>" + value[len(root):]
    return value


def _validate_directory_roots(
    actual_root: str | None,
    expected_root: str | None,
) -> tuple[str | None, str | None]:
    if (actual_root is None) != (expected_root is None):
        raise ValueError("--actual-root and --expected-root must be provided together")
    normalized: list[str | None] = []
    for label, value in (("--actual-root", actual_root), ("--expected-root", expected_root)):
        if value is None:
            normalized.append(None)
            continue
        root = value.rstrip("/")
        if not root.startswith("/") or root == "/" or "\x00" in root:
            raise ValueError(f"{label} must be a non-root absolute directory path")
        normalized.append(root)
    return normalized[0], normalized[1]


def _differences(actual: Any, expected: Any, path: str = "$", *, limit: int = 20) -> list[str]:
    if actual == expected:
        return []
    if type(actual) is not type(expected):
        return [f"{path}: type {type(actual).__name__} != {type(expected).__name__}"]
    if isinstance(actual, dict):
        differences: list[str] = []
        for key in sorted(set(actual) | set(expected)):
            child = f"{path}.{key}"
            if key not in actual:
                differences.append(f"{child}: missing from actual")
            elif key not in expected:
                differences.append(f"{child}: unexpected in actual")
            else:
                differences.extend(_differences(actual[key], expected[key], child, limit=limit))
            if len(differences) >= limit:
                break
        return differences[:limit]
    if isinstance(actual, list):
        differences = []
        if len(actual) != len(expected):
            differences.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(actual, expected, strict=False)):
            differences.extend(_differences(left, right, f"{path}[{index}]", limit=limit))
            if len(differences) >= limit:
                break
        return differences[:limit]
    return [f"{path}: {actual!r} != {expected!r}"]


def compare_semantics(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    actual_root: str | None = None,
    expected_root: str | None = None,
) -> list[str]:
    """Apply only AR-8 normalizations, then report semantic differences."""
    actual_root, expected_root = _validate_directory_roots(actual_root, expected_root)
    return _differences(
        _normalized(actual, directory_root=actual_root),
        _normalized(expected, directory_root=expected_root),
    )


def render_proposal(semantics: dict[str, Any], *, field_constructor: str) -> str:
    target = semantics["target"]
    model = target["model_class"]
    class_name = f"{model}Status"
    kwargs = semantics["current_kwargs"]
    if field_constructor not in {"CharField", "TextField"}:
        raise ValueError(f"unsupported model field constructor: {field_constructor!r}")
    field_lines = [f"{target['target'].split('::')[1]} = models.{field_constructor}("]
    for option, value in sorted(kwargs.items()):
        if option in {"choices_ref", "tuple_choices"}:
            continue
        if option == "default":
            field_lines.append(
                f"    default={class_name}.{_member_name(str(value))},"
            )
        else:
            field_lines.append(f"    {option}={value!r},")
    field_lines.append(f"    choices={class_name}.choices,")
    field_lines.append(")")
    lines = [
        f"# Proposal — extract-enum: {target['field_symbol']}",
        "",
        "## Target",
        f"`{target['target']}` with current keyword arguments `{json.dumps(kwargs, sort_keys=True)}`.",
        "",
        "## Proposed enum",
        "",
        "```python",
        "from django.db import models",
        "",
        "",
        f"class {class_name}(models.TextChoices):",
    ]
    for member in semantics["members"]:
        lines.append(
            f"    {member['name']} = {member['wire_value']!r}, {member['label']!r}"
        )
    lines.extend(
        [
            "```",
            "",
            "## Field change",
            "",
            "Preserve the existing field constructor and unrelated keyword arguments; replace only the enum contract:",
            "",
            "```python",
            *field_lines,
            "```",
            "",
            "## Caller migration",
            "",
            "| Classification | File | Symbol | Literal |",
            "|---|---|---|---|",
        ]
    )
    for classification, key in (
        ("confirmed", "confirmed_sites"),
        ("case risk", "legacy_case_sites"),
        ("bridge", "bridge_sites"),
        ("assignment", "assignment_sites"),
        ("dynamic", "dynamic_sites"),
    ):
        for site in semantics[key]:
            lines.append(
                f"| {classification} | `{site['file']}` | `{site['symbol']}` | `{site['literal']}` |"
            )
    lines.extend(["", "## Data-migration risks"])
    for risk in semantics["risks"]:
        literal = f" `{risk['literal']}`" if "literal" in risk else ""
        lines.append(f"- `{risk['kind']}`{literal}: `{risk['action']}`.")
    lines.extend(
        [
            "",
            "## Pre-deploy distinct-value audit",
            "",
            "Run this read-only query against production before adding the choices validator:",
            "",
            "```python",
            f"list({model}.objects.values_list('{target['target'].split('::')[1]}', flat=True).distinct())",
            "```",
            "",
            "Every returned value must be a proposed member wire value or an explicitly mapped legacy value.",
            "",
            "## Data-normalization migration",
            "",
            "Add a reversible data migration for every case/legacy value above. Run it before the schema migration that enables `choices`.",
            "",
            "## Schema migration",
            "",
            "After the distinct-value audit and data normalization, generate and inspect the field-only migration:",
            "",
            "```text",
            ".venv/bin/python manage.py makemigrations",
            ".venv/bin/python manage.py migrate",
            "```",
            "",
            "## Characterization tests",
            "",
            "Pin every current member wire value, default, case-risk mapping, and bridge behavior before editing callers.",
            "",
            "## Subsystem tests",
            "",
            "Run the narrow model/service tests that read, write, filter, serialize, and deserialize this field, then run the stringly-status lint.",
            "",
            "## Stop condition",
            "",
            "Do not execute until:",
            *[f"- `{condition}`" for condition in semantics["stop"]["required"]],
            "",
            "Human review is required before execution.",
        ]
    )
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read JSON artifact {path}: {exc}") from exc
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--targets", type=Path)
    mode.add_argument("--compare", type=Path, metavar="SEMANTIC_JSON")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--semantic-output", type=Path)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--normalization-report", type=Path)
    parser.add_argument("--actual-root", help="Temporary directory root for the actual artifact")
    parser.add_argument("--expected-root", help="Temporary directory root for the oracle artifact")
    args = parser.parse_args(argv)
    try:
        actual_root, expected_root = _validate_directory_roots(
            args.actual_root, args.expected_root
        )
        if args.compare:
            if args.oracle is None:
                raise ValueError("--compare requires --oracle")
            semantic = _read_json(args.compare)
        else:
            if args.output is None or args.semantic_output is None:
                raise ValueError("--targets requires --output and --semantic-output")
            targets = _read_json(args.targets)
            semantic = build_semantics(targets)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                render_proposal(
                    semantic,
                    field_constructor=str(targets["field_constructor"]),
                ),
                encoding="utf-8",
            )
            _write_json(args.semantic_output, semantic)
        oracle = _read_json(args.oracle) if args.oracle is not None else None
        differences = (
            compare_semantics(
                semantic,
                oracle,
                actual_root=actual_root,
                expected_root=expected_root,
            )
            if oracle is not None
            else []
        )
        applied_temporary_root = bool(
            actual_root is not None
            and oracle is not None
            and (
                _contains_temporary_root(semantic, actual_root)
                or _contains_temporary_root(oracle, expected_root)
            )
        )
        report = {
            "allowed": ALLOWED_NORMALIZATIONS,
            "applied": ["temporary_absolute_roots"] if applied_temporary_root else [],
            "equivalent": not differences,
        }
        if args.normalization_report:
            _write_json(args.normalization_report, report)
        if differences:
            raise ValueError("semantic mismatch at " + "; ".join(differences))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    message = "semantic equivalence: clean" if args.oracle is not None else "proposal rendered"
    print(message, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
