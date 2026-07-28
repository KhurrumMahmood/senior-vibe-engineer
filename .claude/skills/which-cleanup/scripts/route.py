#!/usr/bin/env python3
"""Portable closeout router for an independently installed /which-cleanup."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scan_request import ScanRequestError, build_scan_request
from scope_modes import load_scope_contracts, recommendation_scan

DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository
DEFAULT_CLI_VERSION = "1.5.19"
HELP_EPILOG = """\
Role:
  Inspect recent work and recommend the bounded checks needed to bring it up to
  standard. Use which-shape for an overall workflow and which-skill for one
  tactical skill choice.

Operation:
  --help only prints this text; it never scans, installs, or edits anything.
  Normal routing resolves explicit paths or a Git scope, then returns eligible
  on-demand guide/tool closures.
  Non-router skills stay in the external project-scoped library by default.
  A missing library yields an exact bootstrap command.
  Read-only compatibility status:
    python3 .agents/skills/which-skill/scripts/status.py --project-root "$PWD"

Requirements and limits:
  The router needs Python 3.11+ and Git for Git-derived scopes. Selected checks
  may require language-native tools or manual review; capability output reports
  unsupported paths instead of pretending they ran. Use --scope-mode to choose
  changed-line, whole-changed-file, explicit-path, or project attribution.
"""


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


def _selector(args: argparse.Namespace) -> tuple[str, str | None, str]:
    if args.paths:
        return "paths", None, "explicit paths"
    if args.staged:
        return "staged", None, "staged diff"
    if args.changed_from is not None:
        return (
            "changed-from",
            args.changed_from,
            f"changes from {args.changed_from or '<empty>'}",
        )
    if args.commit is not None:
        return "commit", args.commit, f"commit {args.commit or '<empty>'}"
    if args.range is not None:
        return "range", args.range, f"range {args.range or '<empty>'}"
    if getattr(args, "scope_mode", "auto") == "project":
        return "project", None, "project"
    return "working-tree", None, "working tree"


def _scan_request(args: argparse.Namespace, root: Path):
    selector_kind, selector_value, target = _selector(args)
    try:
        request = build_scan_request(
            root,
            requested_mode=getattr(args, "scope_mode", "auto"),
            selector_kind=selector_kind,
            selector_value=selector_value,
            explicit_paths=args.paths or None,
        )
    except ScanRequestError as exc:
        detail = exc.detail
        if exc.code == "git_scope_unresolvable":
            detail = f"Git could not resolve {target}."
        elif exc.code == "empty_git_scope":
            detail = (
                f"The {selector_kind} ref is empty; provide a ref or explicit "
                "in-project paths."
            )
        raise ResolutionFailure(target=target, code=exc.code, detail=detail) from exc
    return target, request


def scope_band(file_count: int) -> str:
    if file_count <= 1:
        return "trivial"
    if file_count <= 5:
        return "small"
    if file_count <= 20:
        return "medium"
    return "large"


def path_languages(paths: list[str]) -> set[str]:
    """Return only language signals that affect closeout install eligibility."""
    languages: set[str] = set()
    suffixes = {Path(path).suffix.casefold() for path in paths}
    language_suffixes = {
        "typescript": {".ts", ".tsx"},
        "javascript": {".js", ".jsx", ".mjs", ".cjs"},
        "go": {".go"},
        "java": {".java"},
        "kotlin": {".kt"},
        "csharp": {".cs"},
        "php": {".php"},
        "ruby": {".rb"},
        "swift": {".swift"},
        "c": {".c", ".h"},
        "cpp": {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"},
        "rust": {".rs"},
        "dart": {".dart"},
    }
    for language, owned_suffixes in language_suffixes.items():
        if suffixes & owned_suffixes:
            languages.add(language)
    return languages


def bootstrap_command(*, project_root: Path, source: str) -> str:
    """Return the exact non-executing repair command for a missing library."""
    script = (
        project_root
        / ".agents"
        / "skills"
        / "which-skill"
        / "scripts"
        / "bootstrap_library.py"
    )
    return shlex.join(
        [
            "python3",
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(project_root),
            "--source",
            source,
        ]
    )


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
        if not isinstance(payload, dict) or payload.get("schema_version") != 5:
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


def library_handoff(
    library_root: Path,
    skill: str,
    *,
    project_root: Path,
    source: str,
) -> dict:
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
    capability_inventory = shared_tooling / "capability_inventory.py"
    common_guidance = library_root / ".claude" / "skills" / "_common"
    shared_guidance = library_root / ".claude" / "docs"
    runtime_python = library_root / ".venv" / "bin" / "python"
    available = all(Path(item["guide"]).is_file() for item in guides)
    return {
        "mode": "on_demand_library",
        "available": available,
        "default_execution": "fresh_non_context_subagent",
        "library_root": str(library_root),
        "skills": skills,
        "guides": guides if available else [],
        "shared_tooling": str(shared_tooling) if shared_tooling.is_dir() else None,
        "source_inventory_tool": str(source_inventory) if source_inventory.is_file() else None,
        "capability_inventory_tool": (
            str(capability_inventory) if capability_inventory.is_file() else None
        ),
        "common_guidance": str(common_guidance) if common_guidance.is_dir() else None,
        "shared_guidance": str(shared_guidance) if shared_guidance.is_dir() else None,
        "runtime": {
            "available": runtime_python.is_file(),
            "python": str(runtime_python),
        },
        "capabilities": capability_handoff(library_root, skills),
        "repair": (
            None
            if available
            else {
                "action": "bootstrap_library",
                "command": bootstrap_command(
                    project_root=project_root,
                    source=source,
                ),
            }
        ),
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
    "ruby_disposition",
    "rust_disposition",
    "dart_disposition",
    "kotlin_disposition",
    "csharp_disposition",
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
        if not isinstance(payload, dict) or payload.get("schema_version") != 5:
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
    languages: set[str],
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
    closure_languages = sorted(languages & {"csharp", "dart", "kotlin"})
    if closure_languages:
        try:
            manifest = Path(capabilities["manifest"])
            rows = json.loads(manifest.read_text(encoding="utf-8"))["skills"]
            by_name = {row["skill"]: row for row in rows}
            closure_modes = {}
            for language in closure_languages:
                field = f"{language}_closure_mode"
                for skill_name in skills:
                    closure_modes[(language, skill_name)] = by_name[skill_name][field]
            if any(
                mode not in {"stock-selected-install", "external-library"}
                for mode in closure_modes.values()
            ):
                raise ValueError("invalid selected-language closure mode")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return {
                **result,
                "available": False,
                "reason": "selected_language_closure_mode_unavailable",
                "evidence": [],
            }
        external_only = [
            skill_name
            for (_, skill_name), mode in closure_modes.items()
            if mode == "external-library"
        ]
        if external_only:
            return {
                **result,
                "available": False,
                "reason": "selected_language_requires_external_library",
                "evidence": [
                    {"skill": name, "status": "external-library-only"}
                    for name in sorted(set(external_only))
                ],
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


def recommendation_ineligibility(handoff: dict, languages: set[str]) -> str | None:
    """Explain why a capability-backed closeout recommendation is not actionable."""
    capabilities = handoff["capabilities"]
    if not capabilities.get("available"):
        return None
    for capability in capabilities["skills"]:
        if capability["expansion_disposition"] == "framework-bound":
            return "framework_context_not_declared"
        for language in sorted(languages):
            disposition = capability[f"{language}_disposition"]
            if disposition not in {
                f"{language}-supported",
                "validated-neutral",
                "ecosystem-runtime",
            }:
                return f"{language}_disposition={disposition}"
    return None


def build_result(args: argparse.Namespace) -> dict:
    root = args.project_root.resolve()
    library_root = (
        args.library_root
        or root.parent / ".engineering-skills" / root.name
    )
    if not library_root.is_absolute():
        library_root = root / library_root
    library_root = library_root.resolve()
    target, request = _scan_request(args, root)
    paths = sorted(change.path for change in request.changes)
    band = scope_band(len(paths))
    languages = path_languages(paths)
    scope_contracts = load_scope_contracts(library_root)
    recs = []
    excluded_ineligible = []
    for skill, reason in recommendations(paths, band):
        handoff = library_handoff(
            library_root,
            skill,
            project_root=root,
            source=args.source,
        )
        ineligibility = recommendation_ineligibility(handoff, languages)
        if ineligibility is not None:
            excluded_ineligible.append(
                {
                    "skill": skill,
                    "reason": ineligibility,
                    "languages": sorted(languages),
                }
            )
            continue
        recs.append(
            {
                "skill": skill,
                "reason": reason,
                "scan": recommendation_scan(request, scope_contracts.get(skill)),
                "handoff": handoff,
                "optional_install": optional_install_handoff(
                    source=args.source,
                    version=args.skills_cli_version,
                    skill=skill,
                    skills=handoff["skills"],
                    agent=args.agent,
                    capabilities=handoff["capabilities"],
                    languages=languages,
                ),
            }
        )
    return {
        "target": target,
        "resolved_paths": paths,
        "scan_request": request.to_dict(),
        "scope_band": band,
        "recommendations": recs,
        "excluded_ineligible": excluded_ineligible,
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
        if item["handoff"]["available"]:
            lines.append(f"  Default: {item['handoff']['default_execution']}")
        else:
            lines.append("  Library unavailable. Bootstrap it without running a task:")
            lines.append(f"    {item['handoff']['repair']['command']}")
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
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--changed-from")
    parser.add_argument("--commit")
    parser.add_argument("--range")
    parser.add_argument(
        "--scope-mode",
        choices=("auto", "diff-lines", "changed-files", "paths", "project"),
        default="auto",
        help=(
            "Choose finding attribution: diff-lines reports only findings intersecting "
            "changed lines; changed-files analyzes selected files in full; auto preserves "
            "each scanner's current default."
        ),
    )
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
    if args.scope_mode == "paths" and not args.paths:
        parser.error("paths scope mode requires explicit paths")
    if args.scope_mode == "project" and (args.paths or selected):
        parser.error("project scope mode does not accept paths or a Git selector")
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
