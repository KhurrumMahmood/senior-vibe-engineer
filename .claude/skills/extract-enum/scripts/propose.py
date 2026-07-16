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
WIRE_IDENTITY_KEYS = frozenset({"literal", "value", "wire_value", "name", "symbol"})


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
    members = [
        {"name": _member_name(str(choice["wire_value"])), "wire_value": str(choice["wire_value"])}
        for choice in choices
    ]
    wire_values = {member["wire_value"] for member in members}
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
    temporary_roots: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        return {
            item_key: _normalized(
                item_value,
                key=item_key,
                temporary_roots=temporary_roots,
            )
            for item_key, item_value in sorted(value.items())
            if item_key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        rows = [
            _normalized(item, key=key, temporary_roots=temporary_roots)
            for item in value
        ]
        if key.endswith("_unordered_table"):
            return sorted(rows, key=lambda item: json.dumps(item, sort_keys=True))
        return rows
    if isinstance(value, str):
        text = value
        if key not in WIRE_IDENTITY_KEYS:
            for root in temporary_roots:
                prefix = root.rstrip("/")
                if text == prefix or text.startswith(prefix + "/"):
                    text = "<TEMP_ROOT>" + text[len(prefix):]
                    break
        if key.endswith("_markdown"):
            text = re.sub(r"\s+", " ", text).strip()
        return text
    return value


def _contains_temporary_root(
    value: Any,
    roots: tuple[str, ...],
    *,
    key: str = "",
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_temporary_root(item_value, roots, key=item_key)
            for item_key, item_value in value.items()
            if item_key not in VOLATILE_KEYS
        )
    if isinstance(value, list):
        return any(_contains_temporary_root(item, roots, key=key) for item in value)
    if not isinstance(value, str) or key in WIRE_IDENTITY_KEYS:
        return False
    return any(
        value == root.rstrip("/") or value.startswith(root.rstrip("/") + "/")
        for root in roots
    )


def _validate_temporary_roots(values: list[str]) -> tuple[str, ...]:
    roots = tuple(values)
    if len(roots) != len(set(roots)):
        raise ValueError("--temporary-root values must be unique")
    if any(not value.startswith("/") or value == "/" or "\x00" in value for value in roots):
        raise ValueError("--temporary-root values must be non-root absolute paths")
    return roots


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
    temporary_roots: tuple[str, ...] = (),
) -> list[str]:
    """Apply only AR-8 normalizations, then report semantic differences."""
    return _differences(
        _normalized(actual, temporary_roots=temporary_roots),
        _normalized(expected, temporary_roots=temporary_roots),
    )


def render_proposal(semantics: dict[str, Any]) -> str:
    target = semantics["target"]
    model = target["model_class"]
    class_name = f"{model}Status"
    kwargs = semantics["current_kwargs"]
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
    labels = {member["wire_value"]: member["wire_value"].replace("_", " ").title() for member in semantics["members"]}
    for member in semantics["members"]:
        lines.append(
            f"    {member['name']} = {member['wire_value']!r}, {labels[member['wire_value']]!r}"
        )
    lines.extend(
        [
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
    parser.add_argument(
        "--temporary-root",
        action="append",
        default=[],
        help="Exact temporary absolute prefix allowed to normalize in both semantic inputs",
    )
    args = parser.parse_args(argv)
    try:
        temporary_roots = _validate_temporary_roots(args.temporary_root)
        if args.compare:
            if args.oracle is None:
                raise ValueError("--compare requires --oracle")
            semantic = _read_json(args.compare)
        else:
            if args.output is None or args.semantic_output is None:
                raise ValueError("--targets requires --output and --semantic-output")
            semantic = build_semantics(_read_json(args.targets))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(render_proposal(semantic), encoding="utf-8")
            _write_json(args.semantic_output, semantic)
        oracle = _read_json(args.oracle) if args.oracle is not None else None
        differences = (
            compare_semantics(semantic, oracle, temporary_roots=temporary_roots)
            if oracle is not None
            else []
        )
        applied_temporary_root = bool(
            temporary_roots
            and oracle is not None
            and (
                _contains_temporary_root(semantic, temporary_roots)
                or _contains_temporary_root(oracle, temporary_roots)
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
