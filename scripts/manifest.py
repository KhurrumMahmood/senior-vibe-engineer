#!/usr/bin/env python3
"""Skill-activation manifest CLI (`.engineering/manifest.json`).

Activation is *applicability*: which skills apply to THIS repo at all. The
normal case is "most skills apply" — `default: active` with a short opt-out
list (`skills.inactive`), each entry carrying a human reason. This CLI manages
that default-active opt-out list; the flipped allowlist form
(`default: inactive` + `skills.active`) is an advanced manual override read by
`engineering_home.is_skill_active` but not written here.

Activation is orthogonal to ADR 0020 maturity x stakes rung-gating
(`project-state.json`), which selects which *standards* fire — not whether a
whole skill runs.

Subcommands:
  show                          Print the activation block (default + inactive).
  is-active <skill>             Exit 0 if the skill applies here, 1 if inactive.
  deactivate <skill> <reason>   Opt a skill out (records the reason).
  activate <skill>              Opt a skill back in (drop from inactive).

Exit codes: 0 ok / active · 1 inactive (is-active only) · 2 usage error.
Stdlib-only; reads/writes the committed-zone manifest via engineering_home.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_COMMON = REPO_ROOT / ".claude" / "skills" / "_common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))
import engineering_home as eh  # noqa: E402


def _load_raw(root: Path) -> dict:
    """Manifest dict for mutation, defaulting to a fresh versioned stub."""
    return eh.read_manifest(root) or {"version": eh.MANIFEST_VERSION}


def _write(root: Path, manifest: dict) -> None:
    path = eh.manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _skills_block(manifest: dict) -> dict:
    """The mutable `skills` block, created in default-active shape if absent."""
    block = manifest.get("skills")
    if not isinstance(block, dict):
        block = {"default": "active", "inactive": {}}
        manifest["skills"] = block
    block.setdefault("default", "active")
    if not isinstance(block.get("inactive"), dict):
        block["inactive"] = {}
    return block


def cmd_show(root: Path) -> int:
    activation = eh.skill_activation(root)
    print(f"default: {activation['default']}")
    inactive = activation["inactive"]
    if inactive:
        print("inactive:")
        for name in sorted(inactive):
            print(f"  - {name}: {inactive[name] or '(no reason recorded)'}")
    else:
        print("inactive: (none — every skill applies)")
    if activation["default"] == "inactive" and activation["active"]:
        print("active (allowlist):")
        for name in sorted(activation["active"]):
            print(f"  - {name}")
    return 0


def cmd_is_active(root: Path, skill: str) -> int:
    if eh.is_skill_active(root, skill):
        print(f"{skill}: active")
        return 0
    reason = eh.inactive_reason(root, skill)
    print(f"{skill}: inactive" + (f" ({reason})" if reason else ""))
    return 1


def cmd_deactivate(root: Path, skill: str, reason: str) -> int:
    manifest = _load_raw(root)
    _skills_block(manifest)["inactive"][skill] = reason
    _write(root, manifest)
    print(f"deactivated {skill}: {reason}")
    return 0


def cmd_activate(root: Path, skill: str) -> int:
    manifest = _load_raw(root)
    inactive = _skills_block(manifest)["inactive"]
    if skill in inactive:
        del inactive[skill]
        _write(root, manifest)
        print(f"activated {skill}")
    else:
        print(f"{skill} was already active")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skill-activation manifest CLI.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=REPO_ROOT,
        help=(
            "Repo whose .engineering/manifest.json to read/write "
            "(default: this toolkit repo, for dogfooding)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show", help="Print the activation block.")
    p_is = sub.add_parser("is-active", help="Exit 0 if active, 1 if inactive.")
    p_is.add_argument("skill")
    p_de = sub.add_parser("deactivate", help="Opt a skill out (with reason).")
    p_de.add_argument("skill")
    p_de.add_argument("reason")
    p_ac = sub.add_parser("activate", help="Opt a skill back in.")
    p_ac.add_argument("skill")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()

    if args.command == "show":
        return cmd_show(root)
    if args.command == "is-active":
        return cmd_is_active(root, args.skill)
    if args.command == "deactivate":
        return cmd_deactivate(root, args.skill, args.reason)
    if args.command == "activate":
        return cmd_activate(root, args.skill)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
