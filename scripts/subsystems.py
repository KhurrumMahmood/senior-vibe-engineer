#!/usr/bin/env python3
"""Subsystem registry lookup.

Reads `.engineering/subsystems.yaml` (with a bounded legacy fallback) and
answers four questions:

  for-path <path>     Which subsystem owns this path? (longest-prefix wins)
  list                What subsystems exist?
  paths <name>        What path prefixes does this subsystem claim?
  adjacency <name>    What smell tokens should be checked alongside work here?
  show <name>         Full entry for one subsystem.

This is the substrate the planned coverage tracker, query planner, and
`/audit-decisions` `applies_to` validator all build on. Keep it small;
keep it dependency-light.

Exit codes:
  0  match / list / show ok
  1  for-path found no matching subsystem
  2  unknown subsystem name, missing/malformed registry, usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))
import engineering_home as eh  # noqa: E402

DEFAULT_REGISTRY = eh.subsystem_registry_path(REPO_ROOT)


def load_registry(registry: Path) -> dict[str, dict[str, Any]]:
    if not registry.is_file():
        raise FileNotFoundError(f"subsystem registry not found: {registry}")
    try:
        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{registry}: invalid YAML — {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{registry}: expected a mapping at the top level")
    subsystems = data.get("subsystems")
    if not isinstance(subsystems, dict):
        raise ValueError(f"{registry}: missing or non-mapping `subsystems:` key")
    return subsystems


def _normalize(p: str) -> str:
    p = p.strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def _path_matches(path: str, prefix: str) -> bool:
    """A path matches a prefix if the prefix is a directory and `path` lives under it,
    or the prefix is a file path equal to `path`."""
    path = _normalize(path)
    prefix = _normalize(prefix)
    if path == prefix:
        return True
    if prefix.endswith("/") and path.startswith(prefix):
        return True
    return False


def for_path(path: str, registry: dict[str, dict[str, Any]]) -> str | None:
    """Return the subsystem name whose paths claim `path` (longest prefix wins)."""
    best: tuple[int, str] | None = None
    for name, body in registry.items():
        for raw_prefix in body.get("paths") or []:
            if not isinstance(raw_prefix, str):
                continue
            if _path_matches(path, raw_prefix):
                length = len(_normalize(raw_prefix))
                if best is None or length > best[0]:
                    best = (length, name)
    return best[1] if best else None


def cmd_for_path(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    name = for_path(args.path, registry)
    if args.json:
        print(json.dumps({"path": args.path, "subsystem": name}, sort_keys=True))
    else:
        print(name if name else "(no subsystem matches this path)")
    return 0 if name else 1


def cmd_list(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    names = sorted(registry.keys())
    if args.json:
        print(json.dumps({"subsystems": names}, sort_keys=True))
    else:
        for name in names:
            desc = registry[name].get("description", "") or ""
            print(f"{name:<24} {desc}")
    return 0


def cmd_paths(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    body = registry.get(args.name)
    if body is None:
        print(f"unknown subsystem: {args.name}", file=sys.stderr)
        return 2
    paths = body.get("paths") or []
    if args.json:
        print(json.dumps({"subsystem": args.name, "paths": paths}, sort_keys=True))
    else:
        for p in paths:
            print(p)
    return 0


def cmd_adjacency(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    body = registry.get(args.name)
    if body is None:
        print(f"unknown subsystem: {args.name}", file=sys.stderr)
        return 2
    adj = body.get("adjacency") or []
    if args.json:
        print(json.dumps({"subsystem": args.name, "adjacency": adj}, sort_keys=True))
    else:
        for a in adj:
            print(a)
    return 0


def cmd_show(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    body = registry.get(args.name)
    if body is None:
        print(f"unknown subsystem: {args.name}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"subsystem": args.name, **body}, sort_keys=True, default=str))
    else:
        print(f"{args.name}:")
        desc = body.get("description", "") or ""
        if desc:
            print(f"  {desc}")
        for key in ("paths", "related_skills", "related_decisions", "related_specs", "adjacency", "docs"):
            vals = body.get(key) or []
            if vals:
                print(f"  {key}:")
                for v in vals:
                    print(f"    - {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=REPO_ROOT,
        help="Host project root (default: toolkit repository)",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help="Subsystem registry (default: <project-root>/.engineering/subsystems.yaml)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("for-path", help="Look up the subsystem owning a file/directory path")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_for_path)

    p = sub.add_parser("list", help="List all subsystem names")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("paths", help="Print path prefixes claimed by one subsystem")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_paths)

    p = sub.add_parser("adjacency", help="Print adjacency smell tokens for one subsystem")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_adjacency)

    p = sub.add_parser("show", help="Print the full entry for one subsystem")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    registry_path = (
        Path(args.registry).resolve()
        if args.registry
        else eh.resolve_subsystem_registry(root)[0]
    )
    try:
        registry = load_registry(registry_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return args.func(args, registry)


if __name__ == "__main__":
    raise SystemExit(main())
