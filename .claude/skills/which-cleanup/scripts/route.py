#!/usr/bin/env python3
"""Portable closeout router for an independently installed /which-cleanup."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository
DEFAULT_CLI_VERSION = "1.5.19"


def _run_git(root: Path, args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def resolve_paths(args: argparse.Namespace, root: Path) -> tuple[str, list[str]]:
    if args.paths:
        return "explicit paths", sorted(set(args.paths))
    if args.staged:
        return "staged diff", _run_git(root, ["diff", "--cached", "--name-only"])
    if args.changed_from:
        return f"changes from {args.changed_from}", _run_git(
            root, ["diff", "--name-only", args.changed_from]
        )
    if args.commit:
        return f"commit {args.commit}", _run_git(
            root, ["diff-tree", "--no-commit-id", "--name-only", "-r", args.commit]
        )
    if args.range:
        return f"range {args.range}", _run_git(root, ["diff", "--name-only", args.range])
    return "working tree", sorted(
        set(_run_git(root, ["diff", "--name-only"]))
        | set(_run_git(root, ["diff", "--cached", "--name-only"]))
        | set(_run_git(root, ["ls-files", "--others", "--exclude-standard"]))
    )


def scope_band(file_count: int) -> str:
    if file_count <= 1:
        return "trivial"
    if file_count <= 5:
        return "small"
    if file_count <= 20:
        return "medium"
    return "large"


def install_command(*, source: str, version: str, skill: str, agent: str) -> str:
    return "DO_NOT_TRACK=1 " + shlex.join(
        [
            "npx",
            "--yes",
            f"skills@{version}",
            "add",
            source,
            "--skill",
            skill,
            "--agent",
            agent,
            "--copy",
            "-y",
        ]
    )


def library_handoff(library_root: Path, skill: str) -> dict:
    guide = library_root / ".claude" / "skills" / skill / "SKILL.md"
    bundled_tooling = guide.parent / "scripts"
    shared_tooling = library_root / "scripts"
    source_inventory = shared_tooling / "source_inventory.py"
    common_guidance = library_root / ".claude" / "skills" / "_common"
    shared_guidance = library_root / ".claude" / "docs"
    return {
        "mode": "on_demand_library",
        "available": guide.is_file(),
        "default_execution": "fresh_non_context_subagent",
        "library_root": str(library_root),
        "skills": [skill],
        "guides": [
            {
                "skill": skill,
                "skill_root": str(guide.parent),
                "guide": str(guide),
                "bundled_tooling": str(bundled_tooling) if bundled_tooling.is_dir() else None,
            }
        ],
        "shared_tooling": str(shared_tooling) if shared_tooling.is_dir() else None,
        "source_inventory_tool": str(source_inventory) if source_inventory.is_file() else None,
        "common_guidance": str(common_guidance) if common_guidance.is_dir() else None,
        "shared_guidance": str(shared_guidance) if shared_guidance.is_dir() else None,
        "capabilities": capability_handoff(library_root, [skill]),
        "instruction": (
            "For a non-trivial closeout, give a fresh non-context sub-agent the bounded paths, "
            "reason, selected skill root, and shared guidance/tool paths. For a tiny check, read "
            "from the same bounded roots directly. Do not install the skill unless the user "
            "explicitly asks."
        ),
    }


CAPABILITY_FIELDS = (
    "skill",
    "expansion_disposition",
    "typescript_disposition",
    "javascript_disposition",
    "fact_level",
    "outcome_class",
    "framework_family",
)


def capability_handoff(library_root: Path, skills: list[str]) -> dict:
    manifest = library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    unavailable = {
        "available": False,
        "manifest": str(manifest),
        "skills": [],
    }
    if not manifest.is_file():
        return {**unavailable, "reason": "manifest_missing"}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 2:
            raise TypeError("unsupported capability manifest schema")
        rows = payload["skills"]
        if not isinstance(rows, list):
            raise TypeError("skills must be a list")
        by_name = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("skill"), str):
                raise TypeError("capability row must have a skill name")
            name = row["skill"]
            if not name or name in by_name:
                raise TypeError("capability skill names must be unique and non-empty")
            by_name[name] = row
        selected = []
        for skill in skills:
            row = by_name[skill]
            if any(field not in row for field in CAPABILITY_FIELDS):
                raise KeyError("selected capability row is incomplete")
            if any(
                not isinstance(row[field], str) or not row[field]
                for field in CAPABILITY_FIELDS
                if field != "framework_family"
            ) or not (
                row["framework_family"] is None
                or isinstance(row["framework_family"], str)
            ):
                raise TypeError("selected capability fields are invalid")
            closure = row["on_demand_closure"]["closure_skills"]
            install_status = row["optional_install"]["status"]
            if (
                not isinstance(closure, list)
                or not closure
                or closure[0] != skill
                or len(closure) != len(set(closure))
                or any(not isinstance(member, str) or not member for member in closure)
                or any(member not in by_name for member in closure)
                or not isinstance(install_status, str)
            ):
                raise TypeError("selected capability closure is invalid")
            selected.append(
                {
                    **{field: row[field] for field in CAPABILITY_FIELDS},
                    "closure_skills": closure,
                    "optional_install_status": install_status,
                }
            )
        if selected and selected[0]["closure_skills"] != skills:
            raise TypeError("router handoff does not match the declared closure")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return {**unavailable, "reason": "manifest_invalid_or_incomplete"}
    return {"available": True, "manifest": str(manifest), "skills": selected}


def optional_install_handoff(
    *, source: str, version: str, skill: str, agent: str, capabilities: dict
) -> dict:
    result = {
        "source": source,
        "skills_cli_version": version,
        "agent": agent,
    }
    if not capabilities["available"]:
        return {
            **result,
            "available": False,
            "reason": capabilities["reason"],
            "evidence": [],
        }
    evidence = [
        {"skill": row["skill"], "status": row["optional_install_status"]}
        for row in capabilities["skills"]
    ]
    if any(row["status"] != "passed" for row in evidence):
        return {
            **result,
            "available": False,
            "reason": "selected_skill_install_not_validated",
            "evidence": evidence,
        }
    return {
        **result,
        "available": True,
        "evidence": evidence,
        "command": install_command(
            source=source,
            version=version,
            skill=skill,
            agent=agent,
        ),
    }


def recommendations(paths: list[str], band: str) -> list[tuple[str, str]]:
    if not paths:
        return []
    items = [
        ("find-test-obligation-drift", "map changed files to required verification"),
        ("find-comment-drift", "check comments and docs affected by the change"),
        ("prevent-regression", "decide whether the completed change needs a durable guard"),
    ]
    if band in {"medium", "large"}:
        items.extend(
            [
                ("find-duplication", "scan the wider changed surface for repeated implementations"),
                ("find-omnibus", "check whether widened modules gained mixed responsibilities"),
            ]
        )
    if band == "large":
        items.append(
            ("find-incomplete-sweep", "check that a wide change reached every sibling call site")
        )
    return items


def build_result(args: argparse.Namespace) -> dict:
    root = args.project_root.resolve()
    library_root = (
        args.library_root
        or root.parent / ".engineering-skills" / root.name
    )
    if not library_root.is_absolute():
        library_root = root / library_root
    library_root = library_root.resolve()
    target, paths = resolve_paths(args, root)
    band = scope_band(len(paths))
    recs = []
    for skill, reason in recommendations(paths, band):
        handoff = library_handoff(library_root, skill)
        recs.append(
            {
                "skill": skill,
                "reason": reason,
                "handoff": handoff,
                "optional_install": optional_install_handoff(
                    source=args.source,
                    version=args.skills_cli_version,
                    skill=skill,
                    agent=args.agent,
                    capabilities=handoff["capabilities"],
                ),
            }
        )
    return {
        "target": target,
        "resolved_paths": paths,
        "scope_band": band,
        "recommendations": recs,
        "source": {
            "repository": args.source,
            "skill_definitions": f"{args.source}::.claude/skills/",
            "shared_tooling": f"{args.source}::scripts/",
        },
        "limitations": (
            "Portable mode uses the universal closeout floor and file-count sizing. "
            "Load a recommendation from the on-demand library; ambient installation is optional."
        ),
    }


def render(result: dict) -> str:
    lines = [
        f"Closeout scope: {result['target']} ({result['scope_band']})",
        f"Changed files: {len(result['resolved_paths'])}",
    ]
    if not result["recommendations"]:
        lines.append("No changed files detected; no cleanup skill is recommended.")
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("Recommended skills:")
    for item in result["recommendations"]:
        lines.extend(
            [
                f"- /{item['skill']}: {item['reason']}",
                f"  Guide: {item['handoff']['guides'][0]['guide']}",
                f"  Default: {item['handoff']['default_execution']}",
            ]
        )
        if item["optional_install"]["available"]:
            lines.extend(
                [
                    "  Optional ambient install (only when explicitly requested):",
                    f"    {item['optional_install']['command']}",
                ]
            )
        else:
            lines.append(
                "  Optional ambient install unavailable: "
                f"{item['optional_install']['reason']}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--changed-from")
    parser.add_argument("--commit")
    parser.add_argument("--range")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument(
        "--library-root", type=Path,
        help="On-demand library root (default: <project-parent>/.engineering-skills/<project-name>)",
    )
    parser.add_argument("--skills-cli-version", default=DEFAULT_CLI_VERSION)
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    selected = sum(bool(value) for value in (args.staged, args.changed_from, args.commit, args.range))
    if args.paths and selected or selected > 1:
        parser.error("choose exactly one path or diff scope")
    result = build_result(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
