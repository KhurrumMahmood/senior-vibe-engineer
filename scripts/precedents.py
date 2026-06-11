#!/usr/bin/env python3
"""Precedent registry CLI.

Validates `.claude/docs/precedents.yml`, the lightweight case-law index for
current implementation mechanisms. ADRs preserve historical decisions; this
registry points to today's canonical examples, guards, exceptions, and
supersession path.

Subcommands:
  check             Validate registry shape, references, guards, and links
  list              List precedents
  show <id>         Print one precedent as JSON

Exit codes: 0 = clean / results, 1 = drift / not found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = REPO_ROOT / ".claude" / "docs" / "precedents.yml"

VALID_STATUSES = {"active", "proposed", "deprecated", "superseded"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*\.v[0-9]+$")
GLOB_CHARS = set("*?[]")
REQUIRED_FIELDS = {
    "id",
    "status",
    "title",
    "summary",
    "applies_to",
    "canonical_examples",
    "guards",
    "supersedes",
    "superseded_by",
}


class PrecedentError(ValueError):
    """Raised when the registry cannot be read as a list of mappings."""


def relpath(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def load_precedents(registry: Path) -> list[dict[str, Any]]:
    if not registry.exists():
        raise PrecedentError(f"{registry}: registry does not exist")
    try:
        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PrecedentError(f"{registry}: invalid YAML: {exc}") from exc
    if data is None:
        return []
    if not isinstance(data, list):
        raise PrecedentError(f"{registry}: top-level value must be a list")
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise PrecedentError(f"{registry}: entry {index} must be a mapping")
    return data


def _path_matches(project_root: Path, pattern: str) -> list[Path]:
    normalized = pattern.lstrip("/")
    if any(char in normalized for char in GLOB_CHARS):
        return sorted(path for path in project_root.glob(normalized) if path.exists())
    path = project_root / normalized
    return [path] if path.exists() else []


def _python_guard_exists(project_root: Path, guard: str) -> bool:
    parts = guard.split(".")
    for index in range(len(parts), 0, -1):
        module_path = project_root.joinpath(*parts[:index]).with_suffix(".py")
        if not module_path.exists():
            continue
        source = module_path.read_text(encoding="utf-8", errors="ignore")
        return all(token in source for token in parts[index:])
    return False


def _guard_exists(project_root: Path, guard: str) -> bool:
    normalized = guard.lstrip("/")
    if (project_root / ".claude" / "skills" / normalized).exists():
        return True
    command_path = normalized.split(maxsplit=1)[0]
    if "/" in command_path and (project_root / command_path).exists():
        return True
    if "." in normalized and _python_guard_exists(project_root, normalized):
        return True
    return False


def check_precedents(precedents: list[dict[str, Any]], project_root: Path) -> list[str]:
    diagnostics: list[str] = []
    ids: dict[str, dict[str, Any]] = {}

    for index, precedent in enumerate(precedents, start=1):
        precedent_id = str(precedent.get("id") or f"<entry {index}>")
        missing = REQUIRED_FIELDS - set(precedent)
        if missing:
            diagnostics.append(f"{precedent_id}: missing required fields: {sorted(missing)}")
            continue
        if not ID_RE.match(precedent_id):
            diagnostics.append(f"{precedent_id}: invalid id; use lowercase dotted id ending in .vN")
        if precedent_id in ids:
            diagnostics.append(f"{precedent_id}: duplicate id")
        ids[precedent_id] = precedent

        status = precedent.get("status")
        if status not in VALID_STATUSES:
            diagnostics.append(f"{precedent_id}: invalid status {status!r}; allowed: {sorted(VALID_STATUSES)}")
        if not str(precedent.get("title") or "").strip():
            diagnostics.append(f"{precedent_id}: title is empty")
        if not str(precedent.get("summary") or "").strip():
            diagnostics.append(f"{precedent_id}: summary is empty")

        for field in ("applies_to", "canonical_examples", "guards", "supersedes"):
            if not _is_sequence(precedent.get(field)):
                diagnostics.append(f"{precedent_id}: {field} must be a list of strings")

        if not precedent.get("applies_to"):
            diagnostics.append(f"{precedent_id}: applies_to is empty")
        if not precedent.get("canonical_examples"):
            diagnostics.append(f"{precedent_id}: canonical_examples is empty")
        if not precedent.get("guards"):
            diagnostics.append(f"{precedent_id}: guards is empty")

        for pattern in precedent.get("applies_to") or []:
            if not _path_matches(project_root, pattern):
                diagnostics.append(f"{precedent_id}: applies_to {pattern!r} matches no files")
        for example in precedent.get("canonical_examples") or []:
            path = project_root / example.lstrip("/")
            if not path.exists():
                diagnostics.append(f"{precedent_id}: canonical example {example!r} does not exist")
        for guard in precedent.get("guards") or []:
            if not _guard_exists(project_root, guard):
                diagnostics.append(f"{precedent_id}: guard {guard!r} does not resolve to a skill, command, or dotted test")

        superseded_by = precedent.get("superseded_by")
        if status == "active" and superseded_by:
            diagnostics.append(f"{precedent_id}: active precedent cannot set superseded_by")
        if status == "superseded" and not superseded_by:
            diagnostics.append(f"{precedent_id}: superseded precedent must set superseded_by")
        if status in {"deprecated", "superseded"} and not str(precedent.get("migration_note") or "").strip():
            diagnostics.append(f"{precedent_id}: {status} precedent must carry migration_note")

    for precedent_id, precedent in ids.items():
        for supersedes in precedent.get("supersedes") or []:
            if supersedes not in ids:
                diagnostics.append(f"{precedent_id}: supersedes {supersedes!r}, which does not exist")
                continue
            target = ids[supersedes]
            if target.get("superseded_by") != precedent_id:
                diagnostics.append(
                    f"{precedent_id}: supersedes {supersedes!r}, but {supersedes} does not point back via superseded_by"
                )
        superseded_by = precedent.get("superseded_by")
        if superseded_by and superseded_by not in ids:
            diagnostics.append(f"{precedent_id}: superseded_by {superseded_by!r}, which does not exist")

    return diagnostics


def cmd_check(args: argparse.Namespace) -> int:
    try:
        precedents = load_precedents(args.registry)
    except PrecedentError as exc:
        if args.json:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        else:
            print(f"ERROR {exc}")
        return 1
    diagnostics = check_precedents(precedents, args.project_root)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not diagnostics,
                    "precedents_total": len(precedents),
                    "errors_total": len(diagnostics),
                    "errors": diagnostics,
                },
                indent=2,
            )
        )
        return 1 if diagnostics else 0
    for diagnostic in diagnostics:
        print(f"ERROR {diagnostic}")
    if diagnostics:
        print(f"\n{len(diagnostics)} precedent registry error(s).", file=sys.stderr)
        return 1
    print(f"OK - {len(precedents)} precedents")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    precedents = load_precedents(args.registry)
    if args.json:
        print(json.dumps(precedents, indent=2))
        return 0
    for precedent in precedents:
        marker = f" -> {precedent['superseded_by']}" if precedent.get("superseded_by") else ""
        print(f"{precedent['id']} [{precedent['status']}]{marker} - {precedent['title']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    precedents = load_precedents(args.registry)
    for precedent in precedents:
        if precedent.get("id") == args.id:
            print(json.dumps(precedent, indent=2))
            return 0
    print(f"error: no precedent matches id={args.id!r}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect the precedent registry.")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--project-root", type=Path)
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="Validate registry references and supersession links")
    check.add_argument("--registry", type=Path)
    check.add_argument("--project-root", type=Path)
    check.add_argument("--json", action="store_true")

    list_cmd = sub.add_parser("list", help="List precedents")
    list_cmd.add_argument("--registry", type=Path)
    list_cmd.add_argument("--project-root", type=Path)
    list_cmd.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Print one precedent as JSON")
    show.add_argument("--registry", type=Path)
    show.add_argument("--project-root", type=Path)
    show.add_argument("id")

    args = parser.parse_args(argv)
    args.registry = (args.registry or DEFAULT_REGISTRY).resolve()
    args.project_root = (args.project_root or REPO_ROOT).resolve()
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
