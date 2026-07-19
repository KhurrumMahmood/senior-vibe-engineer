#!/usr/bin/env python3
"""Stdlib-only discovery command for the installed ``adapt-project`` skill.

This intentionally stays family-local.  It records objective host facts and
does not choose a Node framework from package metadata.  The emitted
``adapter.yml`` is JSON, which is also valid YAML, so a stock copied skill does
not need PyYAML or repository imports.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


ADAPTER_SCHEMA_VERSION = 1
SOURCE_ROOT_CANDIDATES = (
    "app",
    "src",
    "core",
    "lib",
    "packages",
    "tests",
    "testing",
    "scripts",
    "docs",
    "ai-docs",
    ".claude",
)
DOC_NAMES = ("AGENTS.md", "CLAUDE.md", "CONTEXT.md", "ONBOARDING.md", "README.md")
COMMON_SKIP_PARTS = frozenset({
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "reports",
    "worktrees",
})
# These exclusions are deliberately TypeScript-specific.  The Python counter
# below preserves the reference path's original skip behavior.
TYPESCRIPT_NON_SOURCE_PARTS = frozenset({
    "build",
    "coverage",
    "dist",
    "generated",
    "test",
    "tests",
    "__tests__",
    "vendor",
})
SENSITIVE_NAME_RE = re.compile(
    r"(secret|credential|token|password|key|auth|ai_runtime|intelligence|sidecar|"
    r"payment|billing|migration|agent_policy)",
    re.IGNORECASE,
)
TERM_RE = re.compile(r"^\*\*([^*\n:]{2,80})\*\*:", re.MULTILINE)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_id(value: str | None) -> str:
    if value:
        return value if value.startswith("scan-") else f"scan-{value}"
    return dt.datetime.now(dt.timezone.utc).strftime("scan-%Y%m%d-%H%M%S")


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path, limit: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def is_common_ignored(path: Path) -> bool:
    return any(part in COMMON_SKIP_PARTS for part in path.parts)


def is_typescript_source(path: Path) -> bool:
    if path.suffix not in {".ts", ".tsx"}:
        return False
    if is_common_ignored(path) or any(part in TYPESCRIPT_NON_SOURCE_PARTS for part in path.parts):
        return False
    name = path.name
    return not (name.endswith(".d.ts") or name.endswith(".spec.ts") or name.endswith(".spec.tsx")
                or name.endswith(".test.ts") or name.endswith(".test.tsx"))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def load_package(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def source_roots(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in SOURCE_ROOT_CANDIDATES:
        path = root / name
        if not path.is_dir():
            continue
        python_files = sum(1 for item in path.rglob("*.py") if not is_common_ignored(item))
        ts_paths = [item for item in path.rglob("*.ts") if is_typescript_source(item)]
        tsx_paths = [item for item in path.rglob("*.tsx") if is_typescript_source(item)]
        typescript_files = len(ts_paths) + len(tsx_paths)
        source_languages: list[str] = []
        if python_files:
            source_languages.append("python")
        if typescript_files:
            source_languages.append("typescript")
        markdown_files = sum(1 for item in path.rglob("*.md") if not is_common_ignored(item))
        rows.append({
            "path": name,
            "python_files": python_files,
            "typescript_files": typescript_files,
            "typescript_file_kinds": {"ts": len(ts_paths), "tsx": len(tsx_paths)},
            "markdown_files": markdown_files,
            "source_languages": source_languages,
        })
    return rows


def detect_stack(root: Path, roots: list[dict[str, Any]]) -> dict[str, Any]:
    package_paths = [path for path in sorted(root.glob("**/package.json")) if not is_common_ignored(path)]
    has_python_marker = any((root / name).exists() for name in ("manage.py", "pyproject.toml", "requirements.txt"))
    languages: list[str] = []
    if has_python_marker or any(row["python_files"] for row in roots):
        languages.append("python")
    if any(row["typescript_files"] for row in roots):
        languages.append("typescript")
    elif package_paths:
        languages.append("javascript")

    package_managers: list[str] = []
    for marker, manager in (("pnpm-lock.yaml", "pnpm"), ("package-lock.json", "npm"), ("yarn.lock", "yarn")):
        if (root / marker).is_file():
            package_managers.append(manager)
    if package_paths and not package_managers:
        package_managers.append("npm")
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        package_managers.append("pip")

    markers = [name for name in (
        "manage.py", "pyproject.toml", "requirements.txt", "package.json", "pnpm-lock.yaml", "vite.config.ts", "tsconfig.json",
    ) if (root / name).exists()]
    return {
        "languages": languages,
        # Dependency names are not framework facts.  They are intentionally
        # omitted until a host supplies an explicit framework marker.
        "frameworks": [],
        "package_managers": sorted(set(package_managers)),
        "markers": markers,
        "package_json_paths": [relative(path, root) for path in package_paths[:12]],
    }


def detect_commands(root: Path, stack: dict[str, Any]) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {"test": [], "lint": [], "dev": [], "setup": []}
    if "python" in stack["languages"]:
        python = ".venv/bin/python" if (root / ".venv/bin/python").exists() else "python3"
        if (root / "manage.py").exists():
            commands["test"].append(f"{python} manage.py test")
            commands["dev"].append(f"{python} manage.py runserver")
        commands["setup"].append("python3 -m venv .venv")
        if (root / "requirements.txt").exists():
            commands["setup"].append(".venv/bin/python -m pip install -r requirements.txt")
    for path in [root / "package.json", *sorted(root.glob("*/package.json"))]:
        package = load_package(path)
        scripts = package.get("scripts")
        if not isinstance(scripts, dict):
            continue
        prefix = "pnpm" if (path.parent / "pnpm-lock.yaml").exists() or (root / "pnpm-lock.yaml").exists() else "npm run"
        for name in scripts:
            command = f"cd {relative(path.parent, root)} && {prefix} {name}"
            if "test" in name:
                commands["test"].append(command)
            if "lint" in name or "typecheck" in name:
                commands["lint"].append(command)
            if name in {"dev", "start"}:
                commands["dev"].append(command)
    return {kind: sorted(set(values)) for kind, values in commands.items()}


def detect_docs(root: Path) -> dict[str, Any]:
    claude_docs = root / ".claude" / "docs"
    decisions = root / "ai-docs" / "decisions"
    return {
        "root_docs": [name for name in DOC_NAMES if (root / name).is_file()],
        "claude_docs": [relative(path, root) for path in sorted(claude_docs.rglob("*.md"))][:80] if claude_docs.is_dir() else [],
        "decision_docs": [relative(path, root) for path in sorted(decisions.glob("*.md"))][:80] if decisions.is_dir() else [],
        "has_context_glossary": (root / "CONTEXT.md").is_file(),
    }


def extract_domain_terms(root: Path) -> list[dict[str, str]]:
    sources = ("CONTEXT.md",) if (root / "CONTEXT.md").is_file() else ("AGENTS.md", ".claude/CLAUDE.md")
    terms: dict[str, str] = {}
    for name in sources:
        for match in TERM_RE.finditer(read_text(root / name)):
            term = " ".join(match.group(1).split())
            if 2 <= len(term) <= 80:
                terms.setdefault(term, name)
    return [{"term": term, "source": source} for term, source in sorted(terms.items())[:80]]


def detect_ci(root: Path) -> dict[str, Any]:
    workflows = root / ".github" / "workflows"
    return {
        "workflows": [relative(path, root) for path in sorted(workflows.glob("*.*"))] if workflows.is_dir() else [],
        "pre_commit_config": (root / ".pre-commit-config.yaml").is_file(),
    }


def detect_lints_and_guards(root: Path) -> dict[str, Any]:
    lint_root = root / "scripts" / "lint"
    policy_root = root / "scripts" / "agent_policy"
    precommit = read_text(root / ".pre-commit-config.yaml")
    return {
        "lint_rules": [relative(path, root) for path in sorted(lint_root.glob("*.py")) if path.name != "__init__.py"] if lint_root.is_dir() else [],
        "agent_policy_files": [relative(path, root) for path in sorted(policy_root.glob("*.py"))] if policy_root.is_dir() else [],
        "pre_commit_hooks": re.findall(r"^\s+- id: ([A-Za-z0-9_.-]+)", precommit, flags=re.MULTILINE)[:80],
    }


def detect_sensitive_surfaces(root: Path) -> list[dict[str, str]]:
    surfaces: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if len(surfaces) >= 80:
            break
        if is_common_ignored(path):
            continue
        rel = relative(path, root)
        if path.is_dir() and SENSITIVE_NAME_RE.search(rel):
            surfaces.append({"path": rel, "kind": "directory", "reason": "sensitive-looking name"})
        elif path.is_file() and path.name in {".env", ".env.local"}:
            surfaces.append({"path": rel, "kind": "file", "reason": "environment secrets file"})
        elif path.is_file() and SENSITIVE_NAME_RE.search(rel) and path.suffix in {".py", ".ts", ".tsx", ".md"}:
            surfaces.append({"path": rel, "kind": "file", "reason": "sensitive-looking name"})
    return surfaces


def standardization(source_root_rows: list[dict[str, Any]], guards: dict[str, Any]) -> dict[str, Any]:
    has_many_files = any(
        row["python_files"] > 200 or row["typescript_files"] > 200
        for row in source_root_rows
    )
    cautions = [
        "Observed frequency is not evidence of health; do not standardize common patterns until reviewed.",
        "Treat high-churn or low-test surfaces as stabilization candidates before turning them into doctrine.",
    ]
    if has_many_files:
        cautions.append("Large source roots may contain mixed-quality legacy code; extract exemplars selectively.")
    if not guards["lint_rules"]:
        cautions.append("No local guardrail surface detected; standardization should start with read-only proposals.")
    return {
        "observed_patterns_are_not_canonical": True,
        "cautions": cautions,
        "recommended_first_pass": [
            "separate healthy exemplars from merely common shapes",
            "mark known-bad current practices in the project profile",
            "promote only patterns with tests, guards, or clear owner approval",
        ],
    }


def discover(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    roots = source_roots(root)
    stack = detect_stack(root, roots)
    guards = detect_lints_and_guards(root)
    adapter: dict[str, Any] = {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "project": {"name": root.name, "root": str(root)},
        "stack": stack,
        "commands": detect_commands(root, stack),
        "source_roots": roots,
        "ci": detect_ci(root),
        "docs": detect_docs(root),
        "domain_terms": extract_domain_terms(root),
        "sensitive_surfaces": detect_sensitive_surfaces(root),
        "guards": guards,
    }
    adapter["standardization"] = standardization(roots, guards)
    adapter["open_questions"] = [
        "Which observed patterns are healthy enough to teach future agents, and which are just legacy frequency?",
        "Which workflows are correctness-critical enough to require guards before refactors?",
        "Which sensitive surfaces should block final handoff unless tests or an explicit not-run reason are present?",
    ]
    if not adapter["domain_terms"]:
        adapter["open_questions"].append("What domain vocabulary should be captured before agents start naming things?")
    if not adapter["ci"]["workflows"]:
        adapter["open_questions"].append("What verification should count as the project default when CI is absent or incomplete?")
    return adapter


def adapter_markdown(adapter: dict[str, Any]) -> str:
    stack = adapter["stack"]
    lines = [
        f"# Adapt Project Report — {adapter['project']['name']}",
        "",
        "## Stack",
        f"- Languages: {', '.join(stack['languages']) or '(none detected)'}",
        f"- Frameworks: {', '.join(stack['frameworks']) or '(none detected)'}",
        f"- Package managers: {', '.join(stack['package_managers']) or '(none detected)'}",
        "",
        "## Source Roots",
    ]
    if adapter["source_roots"]:
        for row in adapter["source_roots"]:
            kinds = row["typescript_file_kinds"]
            lines.append(
                f"- {row['path']} — Python: {row['python_files']}; TypeScript: {row['typescript_files']} "
                f"({kinds['ts']} .ts, {kinds['tsx']} .tsx); Markdown: {row['markdown_files']}; "
                f"classified: {', '.join(row['source_languages']) or 'none'}"
            )
    else:
        lines.append("- (none inferred)")
    lines.extend(["", "## Commands"])
    for kind, commands in adapter["commands"].items():
        lines.append(f"- {kind}: {', '.join(commands) if commands else '(none inferred)'}")
    lines.extend(["", "## Sensitive Surfaces"])
    if adapter["sensitive_surfaces"]:
        lines.extend(f"- `{row['path']}` — {row['reason']}" for row in adapter["sensitive_surfaces"][:20])
    else:
        lines.append("- (none inferred)")
    lines.extend(["", "## Standardization Cautions"])
    lines.extend(f"- {note}" for note in adapter["standardization"]["cautions"])
    lines.extend(["", "## Open Questions"])
    lines.extend(f"- {question}" for question in adapter["open_questions"])
    return "\n".join(lines) + "\n"


def write_discovery(project_root: Path, artifact_root: Path, *, timestamp: str | None, apply: bool, no_host_write: bool) -> Path:
    if apply and no_host_write:
        raise ValueError("--apply and --no-host-write are mutually exclusive")
    if no_host_write and is_within(artifact_root, project_root):
        raise ValueError("--no-host-write requires --artifact-root outside --project-root")
    sid = scan_id(timestamp)
    scan_dir = artifact_root / "reports" / "adapt-project" / sid
    scan_dir.mkdir(parents=True, exist_ok=True)
    adapter = discover(project_root)
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    (scan_dir / "adapter.yml").write_text(serialized, encoding="utf-8")
    (scan_dir / "adapter.json").write_text(serialized, encoding="utf-8")
    (scan_dir / "report.md").write_text(adapter_markdown(adapter), encoding="utf-8")
    (scan_dir / "evidence.json").write_text(json.dumps({
        "skill": "adapt-project",
        "scan_id": sid,
        "produced_at": utc_now(),
        "evidence": {"adapter": "adapter.yml", "report": "report.md"},
        "notes": "no host writes" if no_host_write else "",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = scan_dir.parent / "latest"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(scan_dir.name)
    except OSError:
        pass
    if apply:
        destination = project_root / ".engineering" / "project" / "adapter.yml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized, encoding="utf-8")
    return scan_dir


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover objective host-project facts for adapt-project")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-root", type=Path, default=Path.cwd())
    parser.add_argument("--timestamp", help="Stable scan timestamp, e.g. 20260719-120000")
    parser.add_argument("--apply", action="store_true", help="Write .engineering/project/adapter.yml")
    parser.add_argument("--no-host-write", action="store_true", help="Require artifact-root outside project-root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        print(write_discovery(
            args.project_root.resolve(),
            args.artifact_root.resolve(),
            timestamp=args.timestamp,
            apply=args.apply,
            no_host_write=args.no_host_write,
        ))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
