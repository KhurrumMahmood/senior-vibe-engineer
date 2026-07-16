#!/usr/bin/env python3
"""Resolve parser adapters and native sweep shims from the shared registry."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _lib.capability_registry import CapabilityRegistry, load_registry
from sweep.native import ProviderContract, provider_contracts_from_registry


def resolve_native_providers(
    languages: list[str],
    *,
    registry: CapabilityRegistry | None = None,
) -> dict[str, tuple[ProviderContract, ...]]:
    """Resolve each language's native sweep providers from the canonical registry."""
    registry = registry or load_registry()
    unknown = sorted(set(languages) - registry.identifiers("languages"))
    if unknown:
        raise ValueError(f"unregistered languages: {unknown}")
    return {
        language: provider_contracts_from_registry(language, registry=registry)
        for language in languages
    }


def resolve_shims(
    languages: list[str],
    *,
    registry: CapabilityRegistry | None = None,
) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    unknown = sorted(set(languages) - registry.identifiers("languages"))
    if unknown:
        raise ValueError(f"unregistered languages: {unknown}")
    native = resolve_native_providers(languages, registry=registry)
    resolved: dict[str, dict[str, Any]] = {}
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
        if native[language]:
            resolved[language]["native_providers"] = [
                contract.provider for contract in native[language]
            ]
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
