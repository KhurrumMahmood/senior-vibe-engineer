#!/usr/bin/env python3
"""Run the offline transactional skill lifecycle against a verified bundle."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from _lib.distribution_contracts import load_canonical_json
from _lib.skill_bundle import (
    BundleTrustError,
    materialize_install_image,
    verify_install_image,
    verify_release_bundle,
)
from _lib.skill_installer import (
    LifecycleError,
    LifecycleInput,
    NativeDiscoveryAdapter,
    activate,
    deactivate,
    install,
    rollback,
    set_mode,
    uninstall,
    update,
    verify,
)


def _adapter(specification: str) -> NativeDiscoveryAdapter:
    """Load an explicitly configured native discovery adapter factory."""
    if ":" not in specification:
        raise LifecycleError("--adapter must be module.path:factory")
    module_name, attribute = specification.rsplit(":", 1)
    try:
        factory = getattr(importlib.import_module(module_name), attribute)
        adapter = factory()
    except (ImportError, AttributeError, TypeError) as exc:
        raise LifecycleError(f"cannot load native discovery adapter: {exc}") from exc
    if not getattr(adapter, "offline_non_model", False):
        raise LifecycleError("native discovery adapter must declare offline_non_model=true")
    if not callable(getattr(adapter, "discover", None)) or not callable(
        getattr(adapter, "proves_generated_links", None)
    ):
        raise LifecycleError("native discovery adapter is missing required operations")
    return adapter


def _verified_input(
    bundle_root: Path,
    release_sha256: str,
    recipe_ids: list[str],
) -> tuple[LifecycleInput, Path]:
    bundle = verify_release_bundle(bundle_root, release_sha256)
    image = Path(tempfile.mkdtemp(prefix="engineering-skills-install-image-"))
    try:
        manifest = materialize_install_image(bundle, image, recipe_ids=recipe_ids)
        verify_install_image(bundle, image, recipe_ids=recipe_ids)
        portfolio_rows = [
            row
            for row in bundle.bundle_index["blobs"]
            if row["kind"] in {"procedure", "router"}
        ]
        prefix = f".engineering/catalog/{bundle.bundle_index_sha256}/"
        aliases_table = load_canonical_json(bundle.root / "tables/aliases-v1.json")
        data = LifecycleInput.from_verified(
            root=image,
            manifest=manifest,
            surface_contract=bundle.surface_contract,
            canonical_sources={row["id"]: f"{prefix}{row['path']}" for row in portfolio_rows},
            portfolio=[row["id"] for row in portfolio_rows],
            aliases={
                row["public_name"]: row["canonical_target"]
                for row in aliases_table["aliases"]
            },
        )
        return data, image
    except BaseException:
        shutil.rmtree(image, ignore_errors=True)
        raise


def _print_manifest(manifest: dict[str, Any] | None) -> None:
    if manifest is not None:
        print(json.dumps(manifest, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--adapter", required=True, help="module.path:factory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "update"):
        child = subparsers.add_parser(command)
        child.add_argument("--bundle-root", type=Path, required=True)
        child.add_argument("--release-sha256", required=True)
        child.add_argument("--recipe-id", action="append", required=True)
        if command == "update":
            child.add_argument("--allow-downgrade", action="store_true")
    subparsers.add_parser("verify")
    subparsers.add_parser("rollback")
    subparsers.add_parser("uninstall")
    activate_parser = subparsers.add_parser("activate")
    activate_parser.add_argument("public_name")
    activate_parser.add_argument("--invocation-id")
    deactivate_parser = subparsers.add_parser("deactivate")
    deactivate_parser.add_argument("public_name")
    mode_parser = subparsers.add_parser("set-mode")
    mode_parser.add_argument("mode", choices=("router-only", "full-discovery"))
    args = parser.parse_args(argv)

    image: Path | None = None
    try:
        adapter = _adapter(args.adapter)
        if args.command in {"install", "update"}:
            data, image = _verified_input(
                args.bundle_root,
                args.release_sha256,
                args.recipe_id,
            )
            if args.command == "install":
                result = install(args.project_root, data, adapter=adapter)
            else:
                result = update(
                    args.project_root,
                    data,
                    adapter=adapter,
                    allow_downgrade=args.allow_downgrade,
                )
        elif args.command == "verify":
            result = verify(args.project_root, adapter=adapter)
        elif args.command == "rollback":
            result = rollback(args.project_root, adapter=adapter)
        elif args.command == "activate":
            result = activate(
                args.project_root,
                args.public_name,
                adapter=adapter,
                invocation_id=args.invocation_id,
            )
        elif args.command == "deactivate":
            result = deactivate(args.project_root, args.public_name, adapter=adapter)
        elif args.command == "set-mode":
            result = set_mode(args.project_root, args.mode, adapter=adapter)
        else:
            uninstall(args.project_root, adapter=adapter)
            result = None
        _print_manifest(result)
        return 0
    except (BundleTrustError, LifecycleError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if image is not None:
            shutil.rmtree(image, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
