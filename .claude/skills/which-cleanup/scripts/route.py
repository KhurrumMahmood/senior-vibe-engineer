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


def locations(source: str, skill: str) -> dict[str, str]:
    return {
        "definition": f"{source}::.claude/skills/{skill}/SKILL.md",
        "bundled_tooling": f"{source}::.claude/skills/{skill}/scripts/",
        "shared_tooling": f"{source}::scripts/",
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
    target, paths = resolve_paths(args, root)
    band = scope_band(len(paths))
    recs = []
    for skill, reason in recommendations(paths, band):
        recs.append(
            {
                "skill": skill,
                "reason": reason,
                "install": {
                    "source": args.source,
                    "skills_cli_version": args.skills_cli_version,
                    "agent": args.agent,
                    "command": install_command(
                        source=args.source,
                        version=args.skills_cli_version,
                        skill=skill,
                        agent=args.agent,
                    ),
                },
                "locations": locations(args.source, skill),
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
            "Install a recommended skill to load its task-specific instructions and tooling."
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
                f"  Install: {item['install']['command']}",
                f"  Definition/tooling: {item['locations']['definition']}",
            ]
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
