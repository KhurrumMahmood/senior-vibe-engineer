#!/usr/bin/env python3
"""Render a plain-Python StrEnum from collected carrier evidence."""
from __future__ import annotations

import argparse
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
    values = sorted(
        {
            str(item["value"])
            for item in targets["literals"]
            if item.get("case_variant_of") is None
        }
    )
    if not values:
        raise ValueError("targets contain no canonical string literals")
    members = [{"name": _member_name(value), "wire_value": value} for value in values]
    names = [member["name"] for member in members]
    if len(names) != len(set(names)):
        raise ValueError("canonical wire values collide after enum-member normalization")
    variants = sorted(
        str(item["value"])
        for item in targets["literals"]
        if item.get("case_variant_of") is not None
    )
    carrier = str(targets["model_class"])
    field = str(targets["field_name"])
    return {
        "carrier_kind": "python-attribute",
        "members": members,
        "risks": [
            {
                "action": "normalize_before_replacing_bare_strings",
                "kind": "case_variant",
                "literal": value,
            }
            for value in variants
        ],
        "sites": {
            "assignments": targets["assignment_sites"],
            "comparisons": targets["comparison_sites"],
        },
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
