#!/usr/bin/env python3
"""Portable closeout router for an independently installed /which-cleanup."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository
DEFAULT_CLI_VERSION = "1.5.19"


class ResolutionFailure(Exception):
    """A requested path or Git scope could not be resolved safely."""

    def __init__(self, *, target: str, code: str, detail: str) -> None:
        super().__init__(detail)
        self.target = target
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict:
        return {
            "status": "resolution_failed",
            "resolution": {
                "status": "failed",
                "target": self.target,
                "code": self.code,
                "detail": self.detail,
            },
        }


def _run_git(root: Path, args: list[str], *, target: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ResolutionFailure(
            target=target,
            code="git_unavailable",
            detail="Git is unavailable; use explicit in-project paths instead.",
        ) from exc
    if result.returncode != 0:
        raise ResolutionFailure(
            target=target,
            code="git_scope_unresolvable",
            detail=f"Git could not resolve {target}.",
        )
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def _require_git_repository(root: Path, *, target: str) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ResolutionFailure(
            target=target,
            code="git_unavailable",
            detail="Git is unavailable; use explicit in-project paths instead.",
        ) from exc
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise ResolutionFailure(
            target=target,
            code="not_git_repository",
            detail="The project root is not inside a Git working tree; use explicit in-project paths instead.",
        )


def _normalize_explicit_paths(root: Path, paths: list[str]) -> list[str]:
    normalized = set()
    for raw_path in paths:
        if not raw_path.strip():
            raise ResolutionFailure(
                target="explicit paths",
                code="empty_explicit_path",
                detail="An explicit path is empty; provide a project-relative path.",
            )
        path = Path(raw_path)
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        try:
            project_relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ResolutionFailure(
                target="explicit paths",
                code="path_outside_project",
                detail=f"Explicit path resolves outside the project root: {raw_path}",
            ) from exc
        normalized.add(project_relative.as_posix())
    return sorted(normalized)


def resolve_paths(args: argparse.Namespace, root: Path) -> tuple[str, list[str]]:
    if args.paths:
        return "explicit paths", _normalize_explicit_paths(root, args.paths)
    if args.staged:
        target = "staged diff"
        _require_git_repository(root, target=target)
        return target, _run_git(root, ["diff", "--cached", "--name-only"], target=target)
    if args.changed_from is not None:
        target = f"changes from {args.changed_from or '<empty>'}"
        if not args.changed_from.strip():
            raise ResolutionFailure(
                target=target,
                code="empty_git_scope",
                detail="The changed-from ref is empty; provide a ref or explicit in-project paths.",
            )
        _require_git_repository(root, target=target)
        return target, _run_git(
            root, ["diff", "--name-only", args.changed_from], target=target
        )
    if args.commit is not None:
        target = f"commit {args.commit or '<empty>'}"
        if not args.commit.strip():
            raise ResolutionFailure(
                target=target,
                code="empty_git_scope",
                detail="The commit ref is empty; provide a commit or explicit in-project paths.",
            )
        _require_git_repository(root, target=target)
        return target, _run_git(
            root,
            ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", args.commit],
            target=target,
        )
    if args.range is not None:
        target = f"range {args.range or '<empty>'}"
        if not args.range.strip():
            raise ResolutionFailure(
                target=target,
                code="empty_git_scope",
                detail="The Git range is empty; provide a range or explicit in-project paths.",
            )
        _require_git_repository(root, target=target)
        return target, _run_git(root, ["diff", "--name-only", args.range], target=target)
    target = "working tree"
    _require_git_repository(root, target=target)
    return target, sorted(
        set(_run_git(root, ["diff", "--name-only"], target=target))
        | set(_run_git(root, ["diff", "--cached", "--name-only"], target=target))
        | set(
            _run_git(
                root,
                ["ls-files", "--others", "--exclude-standard"],
                target=target,
            )
        )
    )


def scope_band(file_count: int) -> str:
    if file_count <= 1:
        return "trivial"
    if file_count <= 5:
        return "small"
    if file_count <= 20:
        return "medium"
    return "large"


def install_command(*, source: str, version: str, skills: list[str], agent: str) -> str:
    command = ["npx", "--yes", f"skills@{version}", "add", source]
    for skill in skills:
        command.extend(["--skill", skill])
    command.extend(["--agent", agent, "--copy", "-y"])
    return "DO_NOT_TRACK=1 " + shlex.join(command)


def declared_closure(library_root: Path, skill: str) -> list[str]:
    """Return the manifest-declared closure, falling back to the primary skill.

    Capability validation below remains authoritative. This small lookup exists
    only so the handoff can ask that validator for the complete closure instead
    of incorrectly treating a companion-backed skill as a singleton.
    """
    manifest = library_root / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 3:
            raise TypeError("unsupported capability manifest schema")
        rows = payload["skills"]
        if not isinstance(rows, list):
            raise TypeError("skills must be a list")
        names = {
            row["skill"]
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("skill"), str)
        }
        row = next(
            row
            for row in rows
            if isinstance(row, dict) and row.get("skill") == skill
        )
        closure = row["on_demand_closure"]["closure_skills"]
        if (
            not isinstance(closure, list)
            or not closure
            or closure[0] != skill
            or len(closure) != len(set(closure))
            or any(not isinstance(member, str) or not member for member in closure)
            or any(member not in names for member in closure)
        ):
            raise TypeError("selected capability closure is invalid")
        return closure
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        StopIteration,
        TypeError,
    ):
        return [skill]


def library_handoff(library_root: Path, skill: str) -> dict:
    skills = declared_closure(library_root, skill)
    guides = []
    for member in skills:
        guide = library_root / ".claude" / "skills" / member / "SKILL.md"
        bundled_tooling = guide.parent / "scripts"
        guides.append(
            {
                "skill": member,
                "skill_root": str(guide.parent),
                "guide": str(guide),
                "bundled_tooling": (
                    str(bundled_tooling) if bundled_tooling.is_dir() else None
                ),
            }
        )
    shared_tooling = library_root / "scripts"
    source_inventory = shared_tooling / "source_inventory.py"
    common_guidance = library_root / ".claude" / "skills" / "_common"
    shared_guidance = library_root / ".claude" / "docs"
    runtime_python = library_root / ".venv" / "bin" / "python"
    return {
        "mode": "on_demand_library",
        "available": all(Path(item["guide"]).is_file() for item in guides),
        "default_execution": "fresh_non_context_subagent",
        "library_root": str(library_root),
        "skills": skills,
        "guides": guides,
        "shared_tooling": str(shared_tooling) if shared_tooling.is_dir() else None,
        "source_inventory_tool": str(source_inventory) if source_inventory.is_file() else None,
        "common_guidance": str(common_guidance) if common_guidance.is_dir() else None,
        "shared_guidance": str(shared_guidance) if shared_guidance.is_dir() else None,
        "runtime": {
            "available": runtime_python.is_file(),
            "python": str(runtime_python),
        },
        "capabilities": capability_handoff(library_root, skills),
        "instruction": (
            "For a non-trivial closeout, give a fresh non-context sub-agent the bounded paths, "
            "reason, selected skill root, library runtime Python, and shared guidance/tool paths. "
            "For a tiny check, read from the same bounded roots directly. Do not install the "
            "skill unless the user explicitly asks."
        ),
    }


CAPABILITY_FIELDS = (
    "skill",
    "expansion_disposition",
    "typescript_disposition",
    "javascript_disposition",
    "go_disposition",
    "java_disposition",
    "php_disposition",
    "swift_disposition",
    "c_disposition",
    "cpp_disposition",
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
        if not isinstance(payload, dict) or payload.get("schema_version") != 3:
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
    *,
    source: str,
    version: str,
    skill: str,
    skills: list[str],
    agent: str,
    capabilities: dict,
) -> dict:
    result = {
        "skill": skill,
        "skills": skills,
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
            skills=skills,
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
                    skills=handoff["skills"],
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
        lines.append(f"- /{item['skill']}: {item['reason']}")
        for guide in item["handoff"]["guides"]:
            lines.append(f"  Guide /{guide['skill']}: {guide['guide']}")
        lines.append(f"  Default: {item['handoff']['default_execution']}")
        if item["handoff"]["runtime"]["available"]:
            lines.append(f"  Runtime Python: {item['handoff']['runtime']['python']}")
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
    selected = int(args.staged) + sum(
        value is not None for value in (args.changed_from, args.commit, args.range)
    )
    if args.paths and selected or selected > 1:
        parser.error("choose exactly one path or diff scope")
    try:
        result = build_result(args)
    except ResolutionFailure as exc:
        if args.json:
            print(json.dumps(exc.as_dict(), indent=2, sort_keys=True))
        else:
            print(f"error: {exc.detail}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
