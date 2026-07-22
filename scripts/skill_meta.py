#!/usr/bin/env python3
"""Skill frontmatter linter.

Validates the agent decision contract documented in
.claude/skills/_common/skill-frontmatter.md.

Two enforcement modes:

1. Skills that declare `tier:` — must satisfy the FULL new contract
   (tier, job, best_for, not_for, language, framework + the existing
   fields). PR1: every NEW skill (/plan-feature, /decide, /which-skill).

2. Skills that do NOT declare `tier:` — only the existing-field check
   runs (warn-only on missing not_for). PR2 will flip the existing 23
   skills to enforced.

Subcommands:
  lint              Validate every SKILL.md under .claude/skills/
  show <name>       Print parsed frontmatter for one skill (debug)

Frontmatter parsing comes from scripts/_lib/yaml_frontmatter.py (PyYAML).

Exit codes: 0 = clean, 1 = at least one violation, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

_lib_parent = str(SCRIPT_PATH.parent)
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402

EXISTING_REQUIRED = {"name", "description", "argument-hint", "allowed-tools", "user-invocable"}
NEW_CONTRACT_REQUIRED = {"tier", "job", "best_for", "not_for", "language", "framework"}

VALID_TIERS = {"quick", "feature", "system", "new-project", "maintenance", "cross-cutting"}
VALID_JOBS = {
    "plan",
    "map",
    "suspect",
    "explain",
    "refactor",
    "guard",
    "decide",
    "triage",
    "teach",
    "construct",
    "diagnose",
    "meta",
}
VALID_LANGUAGES = {"python", "typescript", "rust", "any"}
VALID_FRAMEWORKS = {"django", "none", "any"}
VALID_SCOUT_MODELS = {"cheap", "careful"}

# PR B-lite: optional task-packet fields. Type-only validation for now —
# values stay free-form so the taxonomy can stabilize from real usage
# before being locked into an enum (per "no big-bang migration").
TASK_PACKET_OPTIONAL: dict[str, type] = {
    "lanes": list,
    "stage": str,
    "entrypoint": bool,
    "consumes": list,
    "produces": list,
    "evidence_required": list,
    "risk_triggers": list,
    "max_overhead": str,
}
INSTALL_OPTIONAL: dict[str, type] = {"install_with": list}


def lint_skill(skill_md: Path, strict: bool) -> tuple[list[str], list[str], bool]:
    """Return (errors, warnings, declares_new_contract).

    PR1 default (strict=False): the new contract is enforced on
    skills declaring `tier:`; everything else is a warning. This lets
    PR1 ship without retroactively breaking CI on the existing 23
    skills (PR2 will backfill them and flip to strict).

    strict=True: every diagnostic is an error. PR2 / future use.
    """
    errors: list[str] = []
    warnings: list[str] = []
    try:
        rel = skill_md.relative_to(REPO_ROOT)
    except ValueError:
        rel = skill_md
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm = parse(text, path=skill_md).metadata
    except FrontmatterError as exc:
        errors.append(f"{rel}: {exc}")
        return errors, warnings, False

    if not fm:
        bucket = errors if strict else warnings
        bucket.append(f"{rel}: missing frontmatter")
        return errors, warnings, False

    declares_new_contract = "tier" in fm

    # Existing-field check applies to every skill.
    missing = EXISTING_REQUIRED - set(fm.keys())
    if missing:
        msg = f"{rel}: missing required existing fields: {sorted(missing)}"
        # Existing-fields are an error for new-contract skills (they should
        # have everything) and a warning for legacy skills until PR2.
        (errors if (declares_new_contract or strict) else warnings).append(msg)

    # New contract check only for skills declaring `tier:` (always error).
    if declares_new_contract:
        new_missing = NEW_CONTRACT_REQUIRED - set(fm.keys())
        if new_missing:
            errors.append(f"{rel}: declares tier but missing new contract fields: {sorted(new_missing)}")
        # Enum membership — use the field's presence (already required
        # by NEW_CONTRACT_REQUIRED) as the gate, not its truthiness;
        # an empty-string `tier:` should fail, not silently pass.
        if "tier" in fm and fm["tier"] not in VALID_TIERS:
            errors.append(f"{rel}: invalid tier {fm['tier']!r}; allowed: {sorted(VALID_TIERS)}")
        if "job" in fm and fm["job"] not in VALID_JOBS:
            errors.append(f"{rel}: invalid job {fm['job']!r}; allowed: {sorted(VALID_JOBS)}")
        if "language" in fm and fm["language"] not in VALID_LANGUAGES:
            errors.append(f"{rel}: invalid language {fm['language']!r}; allowed: {sorted(VALID_LANGUAGES)}")
        if "framework" in fm and fm["framework"] not in VALID_FRAMEWORKS:
            errors.append(f"{rel}: invalid framework {fm['framework']!r}; allowed: {sorted(VALID_FRAMEWORKS)}")
        if "best_for" in fm and not str(fm["best_for"] or "").strip():
            errors.append(f"{rel}: best_for is empty")
        if "not_for" in fm and not str(fm["not_for"] or "").strip():
            errors.append(f"{rel}: not_for is empty")
    elif not strict:
        # Legacy skill in non-strict mode — flag missing not_for as the
        # PR2 audit target, but only as a warning.
        warnings.append(f"{rel}: legacy skill — does not declare new contract (PR2 will backfill)")

    # Optional scout_model — hint to the orchestrator about model class for
    # parallel scout fan-out spawned by this skill. Default is `careful`
    # (current behavior). Skills opt into `cheap` when scout work is read-and-
    # classify (no cross-file synthesis). Applies to any skill that declares it.
    if "scout_model" in fm and fm["scout_model"] not in VALID_SCOUT_MODELS:
        errors.append(
            f"{rel}: invalid scout_model {fm['scout_model']!r}; allowed: {sorted(VALID_SCOUT_MODELS)}"
        )

    # PR B-lite: optional task-packet fields. Type-only, applies to any skill
    # that declares them (not gated on `tier:`). Values stay free-form so the
    # taxonomy can stabilize from real usage before being locked into an enum.
    for field, expected_type in TASK_PACKET_OPTIONAL.items():
        if field not in fm:
            continue
        value = fm[field]
        # bool is a subclass of int, so isinstance(True, int) is True. We need
        # exact-type matching for `entrypoint` to reject `entrypoint: 1`.
        if expected_type is bool:
            if not isinstance(value, bool):
                errors.append(f"{rel}: {field} must be a bool, got {type(value).__name__}")
            continue
        if not isinstance(value, expected_type):
            errors.append(f"{rel}: {field} must be a {expected_type.__name__}, got {type(value).__name__}")
            continue
        if expected_type is list:
            non_strings = [item for item in value if not isinstance(item, str)]
            if non_strings:
                errors.append(f"{rel}: {field} entries must be strings, got {non_strings!r}")
        elif expected_type is str and not value.strip():
            errors.append(f"{rel}: {field} is empty")

    for field, expected_type in INSTALL_OPTIONAL.items():
        if field not in fm:
            continue
        value = fm[field]
        if not isinstance(value, expected_type):
            errors.append(f"{rel}: {field} must be a list, got {type(value).__name__}")
            continue
        if not value:
            errors.append(f"{rel}: {field} must name at least one companion skill")
            continue
        invalid = [item for item in value if not isinstance(item, str) or not item.strip()]
        if invalid:
            errors.append(f"{rel}: {field} entries must be non-empty strings, got {invalid!r}")
        if len(value) != len(set(value)):
            errors.append(f"{rel}: {field} contains duplicate companion skills")
        if fm.get("name") in value:
            errors.append(f"{rel}: {field} must not contain the skill itself")

    # Cross-check: name field must equal directory name.
    expected = skill_md.parent.name
    if fm.get("name") and fm["name"] != expected:
        errors.append(f"{rel}: name={fm['name']!r} does not match directory name {expected!r}")

    return errors, warnings, declares_new_contract


def cmd_lint(args, skills_dir: Path) -> int:
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        print(f"warning: no SKILL.md files under {skills_dir}", file=sys.stderr)
        return 0
    all_errors: list[str] = []
    all_warnings: list[str] = []
    new_contract_skills: list[str] = []
    for sm in skill_files:
        errs, warns, declares_new_contract = lint_skill(sm, strict=args.strict)
        if declares_new_contract:
            new_contract_skills.append(sm.parent.name)
        all_errors.extend(errs)
        all_warnings.extend(warns)
    if args.json:
        print(json.dumps({
            "skills_total": len(skill_files),
            "skills_with_new_contract": new_contract_skills,
            "strict": args.strict,
            "errors_total": len(all_errors),
            "warnings_total": len(all_warnings),
            "errors": all_errors,
            "warnings": all_warnings,
        }, indent=2))
        return 1 if all_errors else 0
    if not args.quiet:
        for w in all_warnings:
            print(f"WARN  {w}")
    for e in all_errors:
        print(f"ERROR {e}")
    if not all_errors and not all_warnings:
        print(f"OK — {len(skill_files)} skills, {len(new_contract_skills)} declaring new contract")
        return 0
    if not all_errors:
        print(f"OK with {len(all_warnings)} warning(s) — {len(skill_files)} skills, {len(new_contract_skills)} declaring new contract")
        return 0
    print(f"\n{len(all_errors)} error(s), {len(all_warnings)} warning(s) across {len(skill_files)} skills.", file=sys.stderr)
    return 1


def cmd_show(args, skills_dir: Path) -> int:
    sm = skills_dir / args.name / "SKILL.md"
    if not sm.exists():
        print(f"error: {sm} does not exist", file=sys.stderr)
        return 2
    try:
        fm = parse(sm.read_text(encoding="utf-8"), path=sm).metadata
    except FrontmatterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(fm, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skill frontmatter linter.")
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint", help="Validate every SKILL.md")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true", help="Treat all diagnostics as errors (PR2+)")
    p.add_argument("--quiet", action="store_true", help="Suppress warnings, only show errors")
    p = sub.add_parser("show", help="Print one skill's parsed frontmatter")
    p.add_argument("name")
    args = parser.parse_args(argv)
    if args.cmd == "lint":
        return cmd_lint(args, args.skills_dir)
    if args.cmd == "show":
        return cmd_show(args, args.skills_dir)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
