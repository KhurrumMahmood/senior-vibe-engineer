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
import os
import re
import shutil
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
GO_SOURCE_ROOT_CANDIDATES = ("cmd", "internal", "pkg")
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
# These exclusions are deliberately JavaScript-family-specific.  The Python
# counter below preserves the reference path's original skip behavior.
JAVASCRIPT_FAMILY_NON_SOURCE_PARTS = frozenset({
    "build",
    "coverage",
    "dist",
    "generated",
    "test",
    "tests",
    "__tests__",
    "vendor",
})
GO_NON_SOURCE_PARTS = JAVASCRIPT_FAMILY_NON_SOURCE_PARTS | frozenset({
    "testdata",
    "fixture",
    "fixtures",
    "third_party",
    "third-party",
    "deps",
    "dependencies",
})
JAVA_NON_SOURCE_PARTS = GO_NON_SOURCE_PARTS | frozenset({
    ".gradle",
    "gen",
    "integrationtest",
    "out",
    "target",
    "testfixtures",
})
JAVA_TEST_NAMES = ("*Test.java", "*Tests.java", "*IT.java")
JAVA_GENERATED_MARKER_RE = re.compile(
    r"(?m)^\s*// Code generated .* DO NOT EDIT\.\s*$"
)
JAVA_GENERATED_ANNOTATION_RE = re.compile(
    r"(?m)^\s*@(?:javax\.annotation\.processing\.)?Generated(?:\s*\(|\s*$)"
)
SENSITIVE_NAME_RE = re.compile(
    r"(secret|credential|token|password|key|auth|ai_runtime|intelligence|sidecar|"
    r"payment|billing|migration|agent_policy)",
    re.IGNORECASE,
)
TERM_RE = re.compile(r"^\*\*([^*\n:]{2,80})\*\*:", re.MULTILINE)
SCAN_ID_RE = re.compile(r"^scan-[A-Za-z0-9][A-Za-z0-9_.-]{0,58}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_id(value: str | None) -> str:
    if value is None:
        candidate = dt.datetime.now(dt.timezone.utc).strftime("scan-%Y%m%d-%H%M%S")
    elif value.startswith("scan-"):
        candidate = value
    else:
        candidate = f"scan-{value}"
    if not SCAN_ID_RE.fullmatch(candidate):
        raise ValueError("--timestamp must form one safe scan-<id> path component")
    return candidate


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
    if is_common_ignored(path) or any(part in JAVASCRIPT_FAMILY_NON_SOURCE_PARTS for part in path.parts):
        return False
    name = path.name
    return not (name.endswith(".d.ts") or name.endswith(".spec.ts") or name.endswith(".spec.tsx")
                or name.endswith(".test.ts") or name.endswith(".test.tsx"))


def is_javascript_source(path: Path) -> bool:
    """Recognize first-party JavaScript without inferring a framework."""
    if path.suffix not in {".js", ".jsx", ".mjs", ".cjs"}:
        return False
    if is_common_ignored(path) or any(part in JAVASCRIPT_FAMILY_NON_SOURCE_PARTS for part in path.parts):
        return False
    name = path.name.lower()
    return not (
        name.endswith((".spec.js", ".spec.jsx", ".spec.mjs", ".spec.cjs"))
        or name.endswith((".test.js", ".test.jsx", ".test.mjs", ".test.cjs"))
        or ".generated." in name
        or name.endswith((".min.js", ".min.jsx", ".min.mjs", ".min.cjs"))
    )


def _is_generated_go(path: Path) -> bool:
    """Match Go's canonical marker only in the leading comment preamble."""
    in_block_comment = False
    try:
        with path.open(encoding="utf-8") as source:
            for raw_line in source:
                remaining = raw_line.lstrip("\ufeff \t")
                while True:
                    if in_block_comment:
                        end = remaining.find("*/")
                        if end < 0:
                            break
                        in_block_comment = False
                        remaining = remaining[end + 2 :].lstrip()
                        continue
                    if not remaining.strip():
                        break
                    if remaining.startswith("//"):
                        if re.fullmatch(
                            r"// Code generated .* DO NOT EDIT\.",
                            remaining.rstrip("\r\n"),
                        ):
                            return True
                        break
                    if remaining.startswith("/*"):
                        in_block_comment = True
                        remaining = remaining[2:]
                        continue
                    return False
    except (OSError, UnicodeDecodeError):
        return False
    return False


def is_go_source(path: Path, project_root: Path) -> bool:
    """Recognize authored Go source without parsing or loading packages."""
    if path.suffix != ".go":
        return False
    try:
        policy_parts = path.resolve().relative_to(project_root.resolve()).parts
    except ValueError:
        return False
    if any(part in COMMON_SKIP_PARTS for part in policy_parts) or any(
        part in GO_NON_SOURCE_PARTS for part in policy_parts
    ):
        return False
    if path.name.endswith("_test.go") or "generated" in path.name.casefold():
        return False
    return not _is_generated_go(path)


def _has_symlink_boundary(path: Path, project_root: Path) -> bool:
    """Reject a selected file reached through any symlinked path component."""
    try:
        relative = path.absolute().relative_to(project_root.absolute())
    except ValueError:
        return True
    cursor = project_root.absolute()
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            return True
    return False


def is_java_source(path: Path, project_root: Path) -> bool:
    """Recognize authored Java source without parsing or invoking the JDK."""
    if path.suffix.casefold() != ".java" or _has_symlink_boundary(path, project_root):
        return False
    try:
        policy_parts = path.resolve().relative_to(project_root.resolve()).parts
    except ValueError:
        return False
    if any(part in COMMON_SKIP_PARTS for part in policy_parts) or any(
        part.casefold() in JAVA_NON_SOURCE_PARTS for part in policy_parts
    ):
        return False
    if any(path.match(pattern) for pattern in JAVA_TEST_NAMES):
        return False
    name = path.name.casefold()
    if "generated" in name or name.endswith("_generated.java"):
        return False
    try:
        head = path.read_text(encoding="utf-8")[:4096]
    except (OSError, UnicodeDecodeError):
        return False
    return not (
        JAVA_GENERATED_MARKER_RE.search(head)
        or JAVA_GENERATED_ANNOTATION_RE.search(head)
    )


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
    root_go_paths = [
        item
        for item in root.glob("*.go")
        if is_within(item, root) and is_go_source(item, root)
    ]
    root_java_paths = [
        item
        for item in root.glob("*.java")
        if is_within(item, root) and is_java_source(item, root)
    ]
    if root_go_paths or root_java_paths:
        root_row: dict[str, Any] = {
            "path": ".",
            "python_files": 0,
            "typescript_files": 0,
            "typescript_file_kinds": {"ts": 0, "tsx": 0},
            "markdown_files": sum(1 for item in root.glob("*.md") if item.is_file()),
            "source_languages": [
                language
                for language, paths in (("go", root_go_paths), ("java", root_java_paths))
                if paths
            ],
        }
        if root_go_paths:
            root_row["go_files"] = len(root_go_paths)
        if root_java_paths:
            root_row["java_files"] = len(root_java_paths)
        rows.append(root_row)
    for name in (*SOURCE_ROOT_CANDIDATES, *GO_SOURCE_ROOT_CANDIDATES):
        path = root / name
        if not path.is_dir() or not is_within(path, root):
            continue
        go_paths = [
            item
            for item in path.rglob("*.go")
            if is_within(item, root) and is_go_source(item, root)
        ]
        java_paths = [
            item
            for item in path.rglob("*.java")
            if is_within(item, root) and is_java_source(item, root)
        ]
        if name in GO_SOURCE_ROOT_CANDIDATES and not go_paths:
            continue
        python_files = sum(
            1 for item in path.rglob("*.py") if is_within(item, root) and not is_common_ignored(item)
        )
        ts_paths = [
            item for item in path.rglob("*.ts") if is_within(item, root) and is_typescript_source(item)
        ]
        tsx_paths = [
            item for item in path.rglob("*.tsx") if is_within(item, root) and is_typescript_source(item)
        ]
        typescript_files = len(ts_paths) + len(tsx_paths)
        javascript_paths = {
            suffix[1:]: [
                item
                for item in path.rglob(f"*{suffix}")
                if is_within(item, root) and is_javascript_source(item)
            ]
            for suffix in (".js", ".jsx", ".mjs", ".cjs")
        }
        javascript_files = sum(len(paths) for paths in javascript_paths.values())
        go_files = len(go_paths)
        java_files = len(java_paths)
        source_languages: list[str] = []
        if python_files:
            source_languages.append("python")
        if typescript_files:
            source_languages.append("typescript")
        if javascript_files:
            source_languages.append("javascript")
        if go_files:
            source_languages.append("go")
        if java_files:
            source_languages.append("java")
        markdown_files = sum(
            1 for item in path.rglob("*.md") if is_within(item, root) and not is_common_ignored(item)
        )
        row = {
            "path": name,
            "python_files": python_files,
            "typescript_files": typescript_files,
            "typescript_file_kinds": {"ts": len(ts_paths), "tsx": len(tsx_paths)},
            "markdown_files": markdown_files,
            "source_languages": source_languages,
        }
        # Preserve the established Python/TypeScript adapter shape until a
        # first-party JavaScript file is actually observed. JavaScript hosts
        # receive the explicit count and suffix breakdown needed to audit the
        # new evidence claim.
        if javascript_files:
            row["javascript_files"] = javascript_files
            row["javascript_file_kinds"] = {
                suffix: len(paths) for suffix, paths in javascript_paths.items()
            }
        if go_files:
            row["go_files"] = go_files
        if java_files:
            row["java_files"] = java_files
        rows.append(row)

    # Maven and Gradle multi-module repositories commonly put Java sources at
    # <module>/src/main/java.  Keep the established flat candidate rows (for
    # example root/src) intact, then add only nested Java source roots not
    # already represented by one of those rows.
    existing_candidates = [
        root / name
        for name in (*SOURCE_ROOT_CANDIDATES, *GO_SOURCE_ROOT_CANDIDATES)
        if (root / name).is_dir() and is_within(root / name, root)
    ]
    for path in sorted(root.rglob("src/main/java")):
        if (
            not path.is_dir()
            or not is_within(path, root)
            or any(is_within(path, candidate) for candidate in existing_candidates)
        ):
            continue
        java_paths = [
            item
            for item in path.rglob("*.java")
            if is_within(item, root) and is_java_source(item, root)
        ]
        if not java_paths:
            continue
        rows.append({
            "path": relative(path, root),
            "python_files": 0,
            "typescript_files": 0,
            "typescript_file_kinds": {"ts": 0, "tsx": 0},
            "markdown_files": 0,
            "source_languages": ["java"],
            "java_files": len(java_paths),
        })
    return rows


def detect_stack(root: Path, roots: list[dict[str, Any]]) -> dict[str, Any]:
    package_paths = [path for path in sorted(root.glob("**/package.json")) if not is_common_ignored(path)]
    requirements = [path for path in sorted(root.glob("**/requirements*.txt")) if not is_common_ignored(path)]
    has_python_marker = (root / "manage.py").exists() or (root / "pyproject.toml").exists() or bool(requirements)
    languages: list[str] = []
    # Keep the reference Python language heuristic: source-file counts feed
    # source-root facts and cautions, not a new stack-language inference.
    if has_python_marker:
        languages.append("python")
    if any(row["typescript_files"] for row in roots):
        languages.append("typescript")
    if any(row.get("javascript_files", 0) for row in roots):
        languages.append("javascript")
    elif package_paths and not languages:
        languages.append("javascript")
    if (root / "go.mod").is_file() or (root / "go.work").is_file() or any(
        row.get("go_files", 0) for row in roots
    ):
        languages.append("go")
    java_markers = (
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
    )
    if any((root / marker).is_file() for marker in java_markers) or any(
        row.get("java_files", 0) for row in roots
    ):
        languages.append("java")

    package_managers: list[str] = []
    for marker, manager in (("pnpm-lock.yaml", "pnpm"), ("package-lock.json", "npm"), ("yarn.lock", "yarn")):
        if (root / marker).is_file():
            package_managers.append(manager)
    if package_paths and not package_managers:
        package_managers.append("npm")
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        package_managers.append("pip")
    if (root / "go.mod").is_file():
        package_managers.append("go")
    if (root / "pom.xml").is_file():
        package_managers.append("maven")
    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        package_managers.append("gradle")

    requirements_text = "\n".join(read_text(path) for path in requirements)
    python_config = requirements_text + "\n" + read_text(root / "pyproject.toml")
    frameworks = ["django"] if (root / "manage.py").exists() or "django" in python_config.lower() else []

    markers = [name for name in (
        "manage.py", "pyproject.toml", "requirements.txt", "package.json", "pnpm-lock.yaml", "vite.config.ts", "tsconfig.json",
        "go.mod", "go.work", "pom.xml", "mvnw", "build.gradle",
        "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradlew",
    ) if (root / name).exists()]
    return {
        "languages": languages,
        # Preserve the reference Python Django marker while refusing to infer
        # a Node framework from package dependency names.
        "frameworks": frameworks,
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
    if "go" in stack["languages"] and (root / "go.mod").is_file():
        commands["test"].append("go test ./...")
    if "java" in stack["languages"] and (root / "pom.xml").is_file():
        commands["test"].append("./mvnw test" if (root / "mvnw").is_file() else "mvn test")
    if "java" in stack["languages"] and (
        (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file()
    ):
        commands["test"].append(
            "./gradlew test" if (root / "gradlew").is_file() else "gradle test"
        )
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
        elif path.is_file() and SENSITIVE_NAME_RE.search(rel) and path.suffix in {
            ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".java", ".md"
        } and (path.suffix != ".java" or is_java_source(path, root)):
            surfaces.append({"path": rel, "kind": "file", "reason": "sensitive-looking name"})
    return surfaces


def standardization(source_root_rows: list[dict[str, Any]], guards: dict[str, Any]) -> dict[str, Any]:
    has_many_files = any(
        row["python_files"] > 200
        or row["typescript_files"] > 200
        or row.get("javascript_files", 0) > 200
        or row.get("go_files", 0) > 200
        or row.get("java_files", 0) > 200
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
        "status": "complete",
        "analysis": {
            language: {
                "status": "complete",
                "analyzer": "filesystem-source-inventory",
            }
            for language in ("go", "java")
            if language in stack["languages"]
        },
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
            line = (
                f"- {row['path']} — Python: {row['python_files']}; TypeScript: {row['typescript_files']} "
                f"({kinds['ts']} .ts, {kinds['tsx']} .tsx); Markdown: {row['markdown_files']}; "
            )
            if row.get("javascript_files"):
                js_kinds = row["javascript_file_kinds"]
                line += (
                    f"JavaScript: {row['javascript_files']} ({js_kinds['js']} .js, "
                    f"{js_kinds['jsx']} .jsx, {js_kinds['mjs']} .mjs, {js_kinds['cjs']} .cjs); "
                )
            if row.get("go_files"):
                line += f"Go: {row['go_files']}; "
            if row.get("java_files"):
                line += f"Java: {row['java_files']}; "
            lines.append(line + f"classified: {', '.join(row['source_languages']) or 'none'}")
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


def _validate_latest_replaceable(latest: Path) -> None:
    if not (latest.exists() or latest.is_symlink()):
        return
    if latest.is_dir() and not latest.is_symlink():
        raise ValueError("latest scan link must be replaceable")
    if not (latest.is_file() or latest.is_symlink()):
        raise ValueError("latest scan link must be replaceable")


def _cleanup_scan_artifact(scan_dir: Path) -> None:
    try:
        shutil.rmtree(scan_dir)
    except OSError:
        pass


def write_discovery(project_root: Path, artifact_root: Path, *, timestamp: str | None, apply: bool, no_host_write: bool) -> Path:
    if apply and no_host_write:
        raise ValueError("--apply and --no-host-write are mutually exclusive")
    if no_host_write and is_within(artifact_root, project_root):
        raise ValueError("--no-host-write requires --artifact-root outside --project-root")
    sid = scan_id(timestamp)
    artifact_root = artifact_root.resolve()
    reports_parent = artifact_root / "reports"
    reports_parent.mkdir(parents=True, exist_ok=True)
    reports_parent = reports_parent.resolve()
    if not is_within(reports_parent, artifact_root):
        raise ValueError("artifact report directory must stay beneath --artifact-root")
    reports_root = reports_parent / "adapt-project"
    reports_root.mkdir(exist_ok=True)
    reports_root = reports_root.resolve()
    if not is_within(reports_root, artifact_root):
        raise ValueError("artifact report directory must stay beneath --artifact-root")
    scan_dir = (reports_root / sid).resolve()
    if scan_dir.parent != reports_root or not is_within(scan_dir, reports_root):
        raise ValueError("scan directory must stay beneath artifact reports")
    latest = reports_root / "latest"
    _validate_latest_replaceable(latest)
    latest_temporary = reports_root / f".{sid}.latest"
    if latest_temporary.exists() or latest_temporary.is_symlink():
        raise ValueError("temporary latest scan link already exists")
    scan_created = False
    try:
        scan_dir.mkdir()
        scan_created = True
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
        if apply:
            destination = project_root / ".engineering" / "project" / "adapter.yml"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(serialized, encoding="utf-8")
        latest_temporary.symlink_to(scan_dir.name)
        if latest_temporary.resolve() != scan_dir or not is_within(latest_temporary.resolve(), reports_root):
            raise ValueError("latest scan link must stay beneath artifact reports")
        os.replace(latest_temporary, latest)
    except OSError as exc:
        if latest_temporary.exists() or latest_temporary.is_symlink():
            try:
                latest_temporary.unlink()
            except OSError:
                pass
        if scan_created:
            _cleanup_scan_artifact(scan_dir)
        raise ValueError("could not create contained latest scan link") from exc
    except ValueError:
        if latest_temporary.exists() or latest_temporary.is_symlink():
            try:
                latest_temporary.unlink()
            except OSError:
                pass
        if scan_created:
            _cleanup_scan_artifact(scan_dir)
        raise
    return scan_dir


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover objective host-project facts for adapt-project")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-root", type=Path, help="Defaults to project-root")
    parser.add_argument("--timestamp", help="Stable scan timestamp, e.g. 20260719-120000")
    parser.add_argument("--apply", action="store_true", help="Write .engineering/project/adapter.yml")
    parser.add_argument("--no-host-write", action="store_true", help="Require artifact-root outside project-root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    artifact_root = args.artifact_root.resolve() if args.artifact_root else project_root
    try:
        print(write_discovery(
            project_root,
            artifact_root,
            timestamp=args.timestamp,
            apply=args.apply,
            no_host_write=args.no_host_write,
        ))
    except ValueError as exc:
        print(f"error: status=failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
