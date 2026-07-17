#!/usr/bin/env python3
"""Run the closed, offline transactional skill lifecycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from _lib.skill_bundle import BundleTrustError
from _lib.skill_installer import (
    BundleInstallRequest,
    LifecycleError,
    activate,
    deactivate,
    install,
    preview_migration,
    rollback,
    set_mode,
    uninstall,
    update,
    verify,
)


def _request(args: argparse.Namespace) -> BundleInstallRequest:
    return BundleInstallRequest(
        bundle_root=args.bundle_root,
        release_root_sha256=args.release_sha256,
        recipe_ids=tuple(args.recipe_id),
    )


def _print(value: dict[str, Any] | None) -> None:
    if value is not None:
        print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "update", "preview-migration"):
        child = subparsers.add_parser(command)
        child.add_argument("--bundle-root", type=Path, required=True)
        child.add_argument("--release-sha256", required=True)
        child.add_argument("--recipe-id", action="append", required=True)
        if command in {"install", "update"}:
            child.add_argument("--apply-migration", action="store_true")
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

    try:
        if args.command == "install":
            result = install(
                args.project_root,
                _request(args),
                apply_migration=args.apply_migration,
            )
        elif args.command == "update":
            result = update(
                args.project_root,
                _request(args),
                allow_downgrade=args.allow_downgrade,
                apply_migration=args.apply_migration,
            )
        elif args.command == "preview-migration":
            result = preview_migration(args.project_root, _request(args))
        elif args.command == "verify":
            result = verify(args.project_root)
        elif args.command == "rollback":
            result = rollback(args.project_root)
        elif args.command == "activate":
            result = activate(
                args.project_root,
                args.public_name,
                invocation_id=args.invocation_id,
            )
        elif args.command == "deactivate":
            result = deactivate(args.project_root, args.public_name)
        elif args.command == "set-mode":
            result = set_mode(args.project_root, args.mode)
        else:
            uninstall(args.project_root)
            result = None
        _print(result)
        return 0
    except (BundleTrustError, LifecycleError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
