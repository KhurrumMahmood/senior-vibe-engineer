#!/usr/bin/env python3
"""Render a plain-Python StrEnum from collected carrier evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any


def _member_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper() or "EMPTY"
    return f"STATUS_{name}" if name[0].isdigit() else name


def build_semantics(targets: dict[str, Any]) -> dict[str, Any]:
    """Build a framework-neutral enum proposal without importing host code."""
    if targets.get("carrier_kind") != "python-attribute":
        raise ValueError("plain-Python renderer requires carrier_kind 'python-attribute'")
    choices = targets.get("declared_choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(
            "plain-Python rendering requires a declared carrier vocabulary"
        )
    values = [str(choice["wire_value"]) for choice in choices]
    if len(values) != len(set(values)):
        raise ValueError("declared carrier vocabulary contains duplicate wire values")
    members = [{"name": _member_name(value), "wire_value": value} for value in values]
    names = [member["name"] for member in members]
    if len(names) != len(set(names)):
        raise ValueError("canonical wire values collide after enum-member normalization")
    classifications = targets.get("site_classifications")
    if not isinstance(classifications, list):
        raise ValueError("plain-Python rendering requires exhaustive site classifications")

    def key(item: dict[str, Any], site_type: str | None = None) -> tuple[object, ...]:
        return (
            site_type or item.get("site_type"),
            item.get("file"),
            item.get("symbol"),
            item.get("literal"),
            item.get("lineno"),
        )

    expected = Counter(
        key(site, site_type)
        for site_type, sites in (
            ("comparison", targets["comparison_sites"]),
            ("assignment", targets["assignment_sites"]),
        )
        for site in sites
    )
    provided = Counter(key(item) for item in classifications if isinstance(item, dict))
    if provided != expected or len(classifications) != sum(provided.values()):
        raise ValueError("plain-Python rendering requires exhaustive site classifications")
    allowed = {"assignment", "bridge", "case_risk", "confirmed", "dynamic"}
    if any(item.get("kind") not in allowed for item in classifications):
        raise ValueError("site classifications contain an unsupported kind")
    dynamic = [item for item in classifications if item["kind"] == "dynamic"]
    if dynamic:
        raise ValueError("unresolved dynamic ownership blocks plain-Python rendering")
    allowed_by_site_type = {
        "assignment": {"assignment", "bridge", "case_risk"},
        "comparison": {"bridge", "case_risk", "confirmed"},
    }
    for item in classifications:
        site_type = item["site_type"]
        if item["kind"] not in allowed_by_site_type[site_type]:
            raise ValueError(
                f"{site_type} site has incompatible classification {item['kind']!r}"
            )
    wire_values = set(values)
    folded_values = {value.casefold() for value in values}
    for item in classifications:
        literal = str(item["literal"])
        kind = item["kind"]
        if kind in {"assignment", "confirmed"} and literal not in wire_values:
            raise ValueError(f"{kind} site is outside the declared carrier vocabulary")
        if kind == "case_risk" and (
            literal in wire_values or literal.casefold() not in folded_values
        ):
            raise ValueError("case-risk site does not match a declared wire value")

    def classified(kind: str) -> list[dict[str, Any]]:
        return [item for item in classifications if item["kind"] == kind]

    variants = sorted(str(item["literal"]) for item in classified("case_risk"))
    carrier = str(targets["model_class"])
    field = str(targets["field_name"])
    return {
        "carrier_kind": "python-attribute",
        "assignment_sites": classified("assignment"),
        "bridge_sites": classified("bridge"),
        "case_risk_sites": classified("case_risk"),
        "confirmed_sites": classified("confirmed"),
        "members": members,
        "risks": [
            {
                "action": "normalize_before_replacing_bare_strings",
                "kind": "case_variant",
                "literal": value,
            }
            for value in variants
        ],
        "stop": {
            "execute": False,
            "required": [
                "all_sites_migrated",
                "characterization_tests_green",
                "stringly_status_lint_clean",
            ],
        },
        "target": {
            "carrier": carrier,
            "field": field,
            "file": str(targets["field_file"]),
            "symbol": str(targets["field_symbol"]),
        },
    }


def render_enum(semantics: dict[str, Any]) -> str:
    target = semantics["target"]
    class_name = f"{target['carrier']}{str(target['field']).title()}"
    lines = ["from enum import StrEnum", "", "", f"class {class_name}(StrEnum):"]
    lines.extend(
        f"    {member['name']} = {member['wire_value']!r}"
        for member in semantics["members"]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--semantic-output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        semantics = build_semantics(_read_json(args.targets))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_enum(semantics), encoding="utf-8")
        args.semantic_output.parent.mkdir(parents=True, exist_ok=True)
        args.semantic_output.write_text(
            json.dumps(semantics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("plain-Python enum proposal rendered", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
