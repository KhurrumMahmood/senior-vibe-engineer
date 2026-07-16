#!/usr/bin/env python3
"""Resolve parser adapters and native sweep shims from the shared registry."""
from __future__ import annotations

import argparse
import json
import sys

from _lib.capability_registry import CapabilityRegistry, load_registry


def resolve_shims(
    languages: list[str],
    *,
    registry: CapabilityRegistry | None = None,
) -> dict[str, dict[str, str]]:
    registry = registry or load_registry()
    unknown = sorted(set(languages) - registry.identifiers("languages"))
    if unknown:
        raise ValueError(f"unregistered languages: {unknown}")
    resolved: dict[str, dict[str, str]] = {}
    for language in languages:
        entry = registry.data["scan_targets"].get(language)
        if not entry:
            resolved[language] = {"status": "unsupported"}
        elif entry.get("shim"):
            resolved[language] = {
                "status": entry["support"],
                "provider_kind": "native-shim",
                "provider": entry["shim"],
                "evidence_contract": entry["evidence_contract"],
            }
        else:
            resolved[language] = {
                "status": entry["support"],
                "provider_kind": "adapter",
                "provider": entry["adapter"],
                "evidence_contract": entry["evidence_contract"],
            }
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="+")
    args = parser.parse_args(argv)
    try:
        shims = resolve_shims(args.languages)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"registry_version": load_registry().schema_version, "shims": shims}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
