#!/usr/bin/env python3
"""Create and safely apply a project-interview profile draft.

This skill-local helper intentionally performs only objective, lightweight
repository discovery. Human intent remains unknown until the agent records
visible answers in the generated draft.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".agents",
    ".claude",
    ".engineering",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "reports",
    "vendor",
}
LANGUAGE_SUFFIXES = {
    ".cs": "csharp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
}
SAFE_TIMESTAMP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scan_id(timestamp: str | None) -> str:
    value = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if not SAFE_TIMESTAMP.fullmatch(value):
        raise ValueError("--timestamp must contain only letters, digits, dot, underscore, or hyphen")
    return f"scan-{value}"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _iter_source_files(root: Path, *, max_files: int = 5000):
    seen = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS and not name.startswith("."))
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink():
                continue
            seen += 1
            if seen > max_files:
                return
            yield path


def _load_package_json(root: Path) -> dict[str, Any]:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _discover(root: Path) -> dict[str, Any]:
    package = _load_package_json(root)
    language_counts: dict[str, int] = {}
    for path in _iter_source_files(root):
        language = LANGUAGE_SUFFIXES.get(path.suffix.lower())
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1

    source_roots = [
        name
        for name in ("src", "app", "apps", "lib", "packages")
        if (root / name).is_dir()
    ]
    workflow_candidates: list[str] = []
    for source_root in source_roots:
        base = root / source_root
        workflow_candidates.extend(
            path.relative_to(root).as_posix()
            for path in sorted(base.iterdir())
            if path.is_dir() and not path.name.startswith(".")
        )

    package_managers = []
    for filename, manager in (
        ("package-lock.json", "npm"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("Gemfile.lock", "bundler"),
        ("Cargo.lock", "cargo"),
        ("go.mod", "go"),
    ):
        if (root / filename).is_file():
            package_managers.append(manager)

    scripts = package.get("scripts")
    commands = {
        key: value
        for key, value in (scripts.items() if isinstance(scripts, dict) else [])
        if key in {"build", "check", "dev", "lint", "test", "typecheck"}
        and isinstance(value, str)
    }
    dependencies: dict[str, Any] = {}
    for key in ("dependencies", "devDependencies"):
        value = package.get(key)
        if isinstance(value, dict):
            dependencies.update(value)
    frameworks = [
        label
        for dependency, label in (
            ("next", "next"),
            ("react", "react"),
            ("vue", "vue"),
            ("express", "express"),
            ("fastify", "fastify"),
            ("@nestjs/core", "nestjs"),
        )
        if dependency in dependencies
    ]

    guardrails = sorted(
        path.relative_to(root).as_posix()
        for guard_root in (root / "scripts" / "lint", root / "tests")
        if guard_root.is_dir()
        for path in guard_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )[:50]

    return {
        "project_name": package.get("name") if isinstance(package.get("name"), str) else root.name,
        "languages": sorted(language_counts),
        "language_file_counts": dict(sorted(language_counts.items())),
        "frameworks": frameworks,
        "package_managers": package_managers,
        "commands": commands,
        "source_roots": source_roots,
        "candidate_workflows": workflow_candidates[:20],
        "existing_guardrails": guardrails,
    }


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_./-]+", text) and text.lower() not in {
        "false",
        "null",
        "true",
    }:
        return text
    return json.dumps(text, ensure_ascii=False)


def _yaml_lines(value: Any, *, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if not isinstance(value, dict):
        raise TypeError("top-level YAML value must be a mapping")
    lines: list[str] = []
    for key, item in value.items():
        if isinstance(item, dict):
            if item:
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {{}}")
        elif isinstance(item, list):
            rendered = ", ".join(_yaml_scalar(entry) for entry in item)
            lines.append(f"{prefix}{key}: [{rendered}]")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
    return lines


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text("\n".join(_yaml_lines(payload)) + "\n", encoding="utf-8")


def _profile(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "user_approved": False,
        "project": {
            "name": facts["project_name"],
            "purpose": None,
            "users": [],
            "maturity": "unknown",
            "desired_direction": None,
        },
        "known_from_repo": {
            "stack": {
                "languages": facts["languages"],
                "frameworks": facts["frameworks"],
                "package_managers": facts["package_managers"],
            },
            "source_roots": facts["source_roots"],
            "candidate_workflows": facts["candidate_workflows"],
            "existing_guardrails": facts["existing_guardrails"],
        },
        "needs_user_input": {
            "critical_workflows": [
                "Which workflows would cause the most damage if an agent broke them?",
                "Which important workflows are currently too messy to canonize?",
            ],
            "risk_posture": [
                "Is this prototype, feature-shop, durable, or regulated work?",
                "Where should agents slow down even when a change looks small?",
            ],
            "intentional_tradeoffs": [
                "Which ugly-looking current patterns are intentional tradeoffs?",
                "Which repeated patterns are known bad and must not be standardized?",
            ],
            "future_direction": [
                "What should this project become next?",
                "What stabilization should precede new surface area?",
            ],
        },
        "standardization_policy": {
            "do_not_canonize_by_frequency": True,
            "requires_human_approval_for_canonical_patterns": True,
            "notes": ["Repository frequency is evidence to investigate, not project doctrine."],
        },
    }


def _profile_markdown(profile: dict[str, Any]) -> str:
    known = profile["known_from_repo"]
    stack = known["stack"]
    lines = [
        f"# Project Profile Draft — {profile['project']['name']}",
        "",
        "> Objective repository facts only. Human answers and approval are still required.",
        "",
        "## Known From Repo",
        f"- Languages: {', '.join(stack['languages']) or '(none detected)'}",
        f"- Frameworks: {', '.join(stack['frameworks']) or '(none detected)'}",
        f"- Package managers: {', '.join(stack['package_managers']) or '(none detected)'}",
        f"- Source roots: {', '.join(known['source_roots']) or '(none detected)'}",
        f"- Candidate workflows: {', '.join(known['candidate_workflows']) or '(none detected)'}",
        "",
        "## Human Intent",
        "- Purpose: unanswered",
        "- Users: unanswered",
        "- Critical workflows: unanswered",
        "- Risk posture: unanswered",
        "- Intentional tradeoffs: unanswered",
        "- Known-bad patterns: unanswered",
        "- Desired direction: unanswered",
        "",
        "## Standardization Policy",
        "- Do not canonize a pattern from frequency alone.",
        "- Human approval is required before project intent becomes doctrine.",
    ]
    return "\n".join(lines) + "\n"


def _open_questions_markdown(profile: dict[str, Any]) -> str:
    lines = ["# Project Open Questions", ""]
    for group, questions in profile["needs_user_input"].items():
        lines.append(f"## {group.replace('_', ' ').title()}")
        lines.extend(f"- [ ] {question}" for question in questions)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _update_latest(scan_dir: Path) -> None:
    latest = scan_dir.parent / "latest"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(scan_dir.name)
    except OSError:
        pass


def create_draft(
    project_root: Path,
    artifact_root: Path,
    *,
    timestamp: str | None,
    no_host_write: bool,
) -> Path:
    project_root = project_root.resolve()
    artifact_root = artifact_root.resolve()
    if not project_root.is_dir():
        raise ValueError(f"project root not found: {project_root}")
    if no_host_write and _is_within(artifact_root, project_root):
        raise ValueError("--no-host-write requires --artifact-root outside --project-root")

    scan_dir = artifact_root / "reports" / "project-interview" / _scan_id(timestamp)
    scan_dir.mkdir(parents=True, exist_ok=False)
    facts = _discover(project_root)
    profile = _profile(facts)
    _write_yaml(scan_dir / "profile.yml", profile)
    (scan_dir / "profile.md").write_text(_profile_markdown(profile), encoding="utf-8")
    (scan_dir / "open-questions.md").write_text(
        _open_questions_markdown(profile), encoding="utf-8"
    )
    (scan_dir / "repo-facts.json").write_text(
        json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (scan_dir / "evidence.json").write_text(
        json.dumps(
            {
                "skill": "project-interview",
                "scan_id": scan_dir.name,
                "produced_at": _utc_now(),
                "evidence": {
                    "profile": "profile.yml",
                    "profile_summary": "profile.md",
                    "open_questions": "open-questions.md",
                },
                "notes": "draft profile; human answers and approval required",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _update_latest(scan_dir)
    return scan_dir


def _profile_is_approved(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    values = re.findall(r"^user_approved:\s*(true|false)\s*$", text, flags=re.MULTILINE)
    return values == ["true"]


def apply_profile(project_root: Path, scan_dir: Path) -> Path:
    project_root = project_root.resolve()
    scan_dir = scan_dir.resolve()
    if not project_root.is_dir():
        raise ValueError(f"project root not found: {project_root}")
    if not scan_dir.is_dir():
        raise ValueError(f"scan directory not found: {scan_dir}")
    required = [scan_dir / name for name in ("profile.yml", "profile.md", "open-questions.md")]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"scan is missing required profile artifacts: {', '.join(missing)}")
    if not _profile_is_approved(scan_dir / "profile.yml"):
        raise PermissionError("profile.yml user_approved is not true; capture visible human answers first")

    engineering = project_root / ".engineering"
    destination = engineering / "project"
    if engineering.is_symlink() or destination.is_symlink():
        raise ValueError("refusing to apply through a symlinked .engineering/project path")
    destination.mkdir(parents=True, exist_ok=True)
    for source in required:
        target = destination / source.name
        if target.is_symlink():
            raise ValueError(f"refusing to replace symlinked profile artifact: {target}")
        shutil.copyfile(source, target)
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft", help="discover repo facts and create an unapproved draft")
    draft.add_argument("--project-root", type=Path, required=True)
    draft.add_argument("--artifact-root", type=Path, required=True)
    draft.add_argument("--timestamp")
    draft.add_argument("--no-host-write", action="store_true")

    apply = subparsers.add_parser("apply", help="copy a human-approved scan into .engineering/project")
    apply.add_argument("--project-root", type=Path, required=True)
    apply.add_argument("--scan-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "draft":
            result = create_draft(
                args.project_root,
                args.artifact_root,
                timestamp=args.timestamp,
                no_host_write=args.no_host_write,
            )
        else:
            result = apply_profile(args.project_root, args.scan_dir)
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
