#!/usr/bin/env python3
"""Select install layers and bindings from a canonical stack profile."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from _lib.capability_registry import CapabilityRegistry, load_registry


def select_install(
    stack: dict[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
    explicit_bindings: list[str] | None = None,
) -> dict[str, Any]:
    registry = registry or load_registry()
    errors = registry.validate_stack(stack)
    if errors:
        raise ValueError("; ".join(errors))
    languages = set(stack.get("languages", []))
    frameworks = set(stack.get("frameworks", []))
    candidates: list[str] = []
    for identifier, entry in registry.data["bindings"].items():
        if identifier == "core":
            candidates.append(identifier)
            continue
        binding_languages = set(entry.get("languages", []))
        binding_frameworks = set(entry.get("frameworks", []))
        if entry.get("kind") == "language" and languages.intersection(binding_languages):
            candidates.append(identifier)
        elif entry.get("kind") == "framework" and (
            languages.intersection(binding_languages)
            and frameworks.intersection(binding_frameworks)
        ):
            candidates.append(identifier)

    explicit = set(explicit_bindings or [])
    unknown_explicit = sorted(explicit - registry.identifiers("bindings"))
    if unknown_explicit:
        raise ValueError(f"explicit bindings are not registered: {unknown_explicit}")
    grouped: dict[tuple[str, str], list[str]] = {}
    for identifier in candidates:
        entry = registry.data["bindings"][identifier]
        grouped.setdefault((entry["layer"], entry["kind"]), []).append(identifier)
    selected: list[str] = []
    for key, values in grouped.items():
        if len(values) == 1:
            selected.extend(values)
            continue
        chosen = sorted(set(values) & explicit)
        if len(chosen) != 1:
            raise ValueError(
                f"ambiguous binding selection at {key[0]}/{key[1]}: {sorted(values)}; "
                "split project roots or explicitly select one binding"
            )
        selected.extend(chosen)

    selected_languages = {
        language
        for identifier in selected
        for language in registry.data["bindings"][identifier].get("languages", [])
    }
    required_languages = {
        language
        for language in languages
        if registry.data["languages"].get(language, {}).get("installation_subject")
    }
    missing_languages = sorted(required_languages - selected_languages)
    selected_frameworks = {
        framework
        for identifier in selected
        for framework in registry.data["bindings"][identifier].get("frameworks", [])
    }
    missing_frameworks = sorted(frameworks - {"any", "none"} - selected_frameworks)
    if missing_languages or missing_frameworks:
        raise ValueError(
            f"unsupported binding selection: languages={missing_languages}, frameworks={missing_frameworks}"
        )

    order = {identifier: index for index, identifier in enumerate(registry.data["bindings"])}
    selected.sort(key=order.__getitem__)
    layers = sorted({registry.data["bindings"][name]["layer"] for name in selected})
    return {
        "schema_version": 1,
        "capability_registry_version": registry.schema_version,
        "capability_contract_version": registry.contract_version,
        "layers": layers,
        "bindings": selected,
        "stack": stack,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="Adapter/profile YAML containing a stack mapping")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default is YAML)")
    args = parser.parse_args(argv)
    try:
        payload = yaml.safe_load(args.profile.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("profile must contain a mapping")
        stack = payload.get("stack")
        if stack is None and isinstance(payload.get("known_from_repo"), dict):
            stack = payload["known_from_repo"].get("stack")
        if not isinstance(stack, dict):
            raise ValueError("profile does not contain a stack mapping")
        selection = select_install(stack)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(selection, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(selection, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
