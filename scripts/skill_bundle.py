#!/usr/bin/env python3
"""Build and verify offline skill release bundles and new router-only images."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _lib.skill_bundle import (
    BundleTrustError,
    build_release_bundle,
    materialize_install_image,
    recipe_from_json,
    verify_install_image,
    verify_release_bundle,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-release")
    build.add_argument("source_root", type=Path)
    build.add_argument("recipe", type=Path)
    build.add_argument("output_root", type=Path)

    verify = commands.add_parser("verify-release")
    verify.add_argument("bundle_root", type=Path)
    verify.add_argument("expected_release_root_sha256")

    image = commands.add_parser("build-image")
    image.add_argument("bundle_root", type=Path)
    image.add_argument("expected_release_root_sha256")
    image.add_argument("output_root", type=Path)
    image.add_argument("--recipe-id", dest="recipe_ids", action="append", required=True)

    verify_image = commands.add_parser("verify-image")
    verify_image.add_argument("bundle_root", type=Path)
    verify_image.add_argument("expected_release_root_sha256")
    verify_image.add_argument("image_root", type=Path)
    verify_image.add_argument(
        "--recipe-id", dest="recipe_ids", action="append", required=True
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build-release":
            recipe, blobs = recipe_from_json(args.recipe)
            digest = build_release_bundle(
                args.source_root,
                args.output_root,
                bundle_version=recipe["bundle_version"],
                blobs=blobs,
                installer=recipe["installer"],
                surface_activation_contract=recipe["surface_activation_contract"],
            )
            result = {"release_root_sha256": digest}
        elif args.command == "verify-release":
            bundle = verify_release_bundle(
                args.bundle_root, args.expected_release_root_sha256
            )
            result = {
                "bundle_index_sha256": bundle.bundle_index_sha256,
                "release_root_sha256": bundle.release_root_sha256,
            }
        elif args.command == "build-image":
            bundle = verify_release_bundle(
                args.bundle_root, args.expected_release_root_sha256
            )
            manifest = materialize_install_image(
                bundle, args.output_root, recipe_ids=args.recipe_ids
            )
            result = {"manifest_sha256": manifest["manifest_sha256"]}
        else:
            bundle = verify_release_bundle(
                args.bundle_root, args.expected_release_root_sha256
            )
            manifest = verify_install_image(
                bundle, args.image_root, recipe_ids=args.recipe_ids
            )
            result = {"manifest_sha256": manifest["manifest_sha256"]}
    except (BundleTrustError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
