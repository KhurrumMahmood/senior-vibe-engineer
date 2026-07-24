#!/usr/bin/env python3
"""Validate the declared scan-scope contract for every ``find-*`` skill."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"
)
VALID_MODES = {"diff-lines", "changed-files", "paths", "project"}
VALID_GRANULARITIES = {"line", "symbol", "file", "multi-site", "project"}
VALID_DIFF_SEMANTICS = {
    "filter-findings",
    "seed-analysis",
    "trigger-analysis",
    "not-applicable",
}
VALID_BEHAVIOR_FAMILIES = {
    "line-local",
    "symbol-file-semantic",
    "multi-site-history",
    "project-global",
}
VALID_EXECUTION_KINDS = {"deterministic", "hybrid"}
VALID_SCOPE_CONFIG = {"shared", "custom", "not-supported"}
REQUIRED_ROW_FIELDS = {
    "skill",
    "execution_kind",
    "entrypoints",
    "current_modes",
    "target_modes",
    "current_default_mode",
    "target_default_mode",
    "finding_granularity",
    "diff_semantics",
    "behavior_family",
    "scope_config",
    "rationale",
}


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    """Load one JSON contract, raising normal parse/read failures to the caller."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("scan-scope contract must be a JSON object")
    return payload


def find_skill_names(root: Path) -> set[str]:
    """Return top-level ``find-*`` skill directories that contain ``SKILL.md``."""
    skills_root = root / ".claude" / "skills"
    return {
        path.name
        for path in skills_root.glob("find-*")
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) == len(set(value))
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def _validate_row(root: Path, row: object, index: int) -> list[str]:
    prefix = f"skills[{index}]"
    if not isinstance(row, dict):
        return [f"{prefix}: row must be an object"]
    errors: list[str] = []
    missing = sorted(REQUIRED_ROW_FIELDS - set(row))
    if missing:
        return [f"{prefix}: missing fields: {', '.join(missing)}"]

    skill = row["skill"]
    if not isinstance(skill, str) or not skill.startswith("find-"):
        errors.append(f"{prefix}.skill: must be a find-* name")
        skill = "<invalid>"
    if row["execution_kind"] not in VALID_EXECUTION_KINDS:
        errors.append(f"{skill}.execution_kind: invalid value")
    if row["finding_granularity"] not in VALID_GRANULARITIES:
        errors.append(f"{skill}.finding_granularity: invalid value")
    if row["diff_semantics"] not in VALID_DIFF_SEMANTICS:
        errors.append(f"{skill}.diff_semantics: invalid value")
    if row["behavior_family"] not in VALID_BEHAVIOR_FAMILIES:
        errors.append(f"{skill}.behavior_family: invalid value")
    if not isinstance(row["rationale"], str) or not row["rationale"].strip():
        errors.append(f"{skill}.rationale: must be a non-empty string")

    entrypoints = row["entrypoints"]
    if not _string_list(entrypoints):
        errors.append(f"{skill}.entrypoints: must be unique non-empty paths")
    else:
        skill_root = (root / ".claude" / "skills" / skill).resolve()
        for relative in entrypoints:
            candidate = (skill_root / relative).resolve()
            try:
                candidate.relative_to(skill_root)
            except ValueError:
                errors.append(f"{skill}.entrypoints: path escapes skill root: {relative}")
                continue
            if not candidate.is_file():
                errors.append(f"{skill}.entrypoints: missing file: {relative}")

    current_modes = row["current_modes"]
    target_modes = row["target_modes"]
    for field, modes in (("current_modes", current_modes), ("target_modes", target_modes)):
        if not _string_list(modes):
            errors.append(f"{skill}.{field}: must be unique non-empty modes")
        elif unknown := sorted(set(modes) - VALID_MODES):
            errors.append(f"{skill}.{field}: unknown modes: {', '.join(unknown)}")
    if _string_list(current_modes) and _string_list(target_modes):
        if not set(current_modes) <= set(target_modes):
            errors.append(f"{skill}: current modes must be a subset of target modes")
        if row["current_default_mode"] not in current_modes:
            errors.append(f"{skill}.current_default_mode: not in current_modes")
        if row["target_default_mode"] not in target_modes:
            errors.append(f"{skill}.target_default_mode: not in target_modes")
        if "diff-lines" in target_modes and (
            row["finding_granularity"] != "line"
            or row["diff_semantics"] != "filter-findings"
        ):
            errors.append(
                f"{skill}: diff-lines requires line granularity and filter-findings semantics"
            )
        if row["diff_semantics"] == "trigger-analysis" and "diff-lines" in target_modes:
            errors.append(f"{skill}: trigger-analysis cannot claim diff-lines")

    scope_config = row["scope_config"]
    if not isinstance(scope_config, dict):
        errors.append(f"{skill}.scope_config: must be an object")
    else:
        strategy = scope_config.get("strategy")
        reason = scope_config.get("reason")
        if strategy not in VALID_SCOPE_CONFIG:
            errors.append(f"{skill}.scope_config.strategy: invalid value")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{skill}.scope_config.reason: must be non-empty")
    return errors


def validate_contract(root: Path, payload: dict[str, Any]) -> list[str]:
    """Return all schema, inventory, and entrypoint errors."""
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    rows = payload.get("skills")
    if not isinstance(rows, list):
        return [*errors, "skills must be a list"]
    for index, row in enumerate(rows):
        errors.extend(_validate_row(root, row, index))

    names = [row.get("skill") for row in rows if isinstance(row, dict)]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        errors.append(f"duplicate skills: {', '.join(duplicate_names)}")
    if names != sorted(names):
        errors.append("skill rows must be sorted by skill name")

    expected = find_skill_names(root)
    actual = {name for name in names if isinstance(name, str)}
    if missing := sorted(expected - actual):
        errors.append(f"missing skill rows: {', '.join(missing)}")
    if stale := sorted(actual - expected):
        errors.append(f"stale skill rows: {', '.join(stale)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    try:
        payload = load_contract(args.contract)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        print(f"scan-scope-contract: invalid input: {exc}")
        return 2
    errors = validate_contract(args.project_root.resolve(), payload)
    if errors:
        for error in errors:
            print(f"scan-scope-contract: {error}")
        return 1
    print(f"scan-scope-contract: OK ({len(payload['skills'])} find-* skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
