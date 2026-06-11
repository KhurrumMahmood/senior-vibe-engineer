#!/usr/bin/env python3
"""Project adaptation helpers for `/adapt-project` and `/project-interview`.

The script has two jobs:

* discover objective repo facts without mutating the target project;
* draft the human-approved profile questions that turn those facts into
  project doctrine.

Host writes are opt-in via ``--apply``. Dogfood runs should pass
``--no-host-write`` and an external ``--artifact-root``.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent

# The committed-zone path layout (`.engineering/...`) lives in exactly one
# place — engineering_home — so durable host writes never re-bake the folder
# convention (ADR 0021). Stdlib + PyYAML script; engineering_home is stdlib.
sys.path.insert(0, str(REPO_ROOT / ".claude" / "skills" / "_common"))
import engineering_home as _eh  # noqa: E402

ADAPTER_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = 1
TIMESTAMP_RE = re.compile(r"^scan-\d{8}-\d{6}$")

DOC_NAMES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CONTEXT.md",
    "ONBOARDING.md",
    "README.md",
)
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
SENSITIVE_NAME_RE = re.compile(
    r"(secret|credential|token|password|key|auth|ai_runtime|intelligence|sidecar|"
    r"payment|billing|migration|agent_policy)",
    re.IGNORECASE,
)
TERM_RE = re.compile(r"^\*\*([^*\n:]{2,80})\*\*:", re.MULTILINE)
SKIP_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "reports",
    "worktrees",
}


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_id(now: str | None = None) -> str:
    if now:
        if now.startswith("scan-"):
            return now
        return f"scan-{now}"
    return _dt.datetime.now(_dt.timezone.utc).strftime("scan-%Y%m%d-%H%M%S")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path, limit: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _is_ignored_path(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _safe_yaml_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_write_mode(project_root: Path, artifact_root: Path, *, apply: bool, no_host_write: bool) -> None:
    if apply and no_host_write:
        raise ValueError("--apply and --no-host-write are mutually exclusive")
    if no_host_write and _is_within(artifact_root, project_root):
        raise ValueError("--no-host-write requires --artifact-root outside --project-root")


def _list_existing(root: Path, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if (root / name).exists()]


def _load_package_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def detect_stack(root: Path) -> dict[str, Any]:
    requirements = "\n".join(_read_text(path) for path in sorted(root.glob("**/requirements*.txt")) if not _is_ignored_path(path))
    pyproject = _read_text(root / "pyproject.toml")
    package_paths = sorted(root.glob("**/package.json"))
    package_paths = [p for p in package_paths if not _is_ignored_path(p)]
    package_text = "\n".join(_read_text(p) for p in package_paths[:8])

    languages: list[str] = []
    frameworks: list[str] = []
    package_managers: list[str] = []

    if (root / "manage.py").exists() or (root / "pyproject.toml").exists() or requirements:
        languages.append("python")
    if package_paths:
        languages.append("javascript/typescript")
    if (root / "manage.py").exists() or _contains_any(requirements + pyproject, ("django",)):
        frameworks.append("django")
    if _contains_any(package_text, ('"react"', '"@types/react"', "react-router")):
        frameworks.append("react")
    if _contains_any(package_text, ("vite", "vitest")):
        frameworks.append("vite/vitest")
    if (root / "pnpm-lock.yaml").exists():
        package_managers.append("pnpm")
    if (root / "package-lock.json").exists():
        package_managers.append("npm")
    if (root / "yarn.lock").exists():
        package_managers.append("yarn")
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        package_managers.append("pip")
    if package_paths and not any(manager in package_managers for manager in ("pnpm", "npm", "yarn")):
        package_managers.append("npm")

    return {
        "languages": sorted(set(languages)),
        "frameworks": sorted(set(frameworks)),
        "package_managers": sorted(set(package_managers)),
        "markers": _list_existing(
            root,
            (
                "manage.py",
                "pyproject.toml",
                "requirements.txt",
                "package.json",
                "pnpm-lock.yaml",
                "vite.config.ts",
                "tsconfig.json",
            ),
        ),
        "package_json_paths": [_rel(p, root) for p in package_paths[:12]],
    }


def detect_commands(root: Path, stack: dict[str, Any]) -> dict[str, Any]:
    commands: dict[str, list[str]] = {"test": [], "lint": [], "dev": [], "setup": []}
    if "python" in stack.get("languages", []):
        python = ".venv/bin/python" if (root / ".venv/bin/python").exists() else "python3"
        if (root / "manage.py").exists():
            commands["test"].append(f"{python} manage.py test")
            commands["dev"].append(f"{python} manage.py runserver")
        commands["setup"].append("python3 -m venv .venv")
        if (root / "requirements.txt").exists():
            commands["setup"].append(".venv/bin/pip install -r requirements.txt")
    if (root / ".venv/bin/ruff").exists():
        commands["lint"].append(".venv/bin/ruff check <path>")
    elif (root / "pyproject.toml").exists():
        commands["lint"].append("ruff check <path>")
    package_paths = [root / "package.json", *sorted(root.glob("*/package.json"))]
    for path in package_paths:
        pkg = _load_package_json(path)
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        prefix = "pnpm" if (path.parent / "pnpm-lock.yaml").exists() or (root / "pnpm-lock.yaml").exists() else "npm run"
        for name in scripts:
            if "test" in name:
                commands["test"].append(f"cd {_rel(path.parent, root)} && {prefix} {name}")
            if "lint" in name or "typecheck" in name:
                commands["lint"].append(f"cd {_rel(path.parent, root)} && {prefix} {name}")
            if name in {"dev", "start"}:
                commands["dev"].append(f"cd {_rel(path.parent, root)} && {prefix} {name}")
    return {k: sorted(set(v)) for k, v in commands.items()}


def detect_docs(root: Path) -> dict[str, Any]:
    root_docs = [name for name in DOC_NAMES if (root / name).is_file()]
    claude_docs = sorted(_rel(p, root) for p in (root / ".claude" / "docs").rglob("*.md"))
    decision_docs = sorted(_rel(p, root) for p in (root / "ai-docs" / "decisions").glob("*.md"))
    return {
        "root_docs": root_docs,
        "claude_docs": claude_docs[:80],
        "decision_docs": decision_docs[:80],
        "has_context_glossary": (root / "CONTEXT.md").is_file(),
    }


def extract_domain_terms(root: Path) -> list[dict[str, str]]:
    terms: dict[str, str] = {}
    sources = ("CONTEXT.md",) if (root / "CONTEXT.md").is_file() else ("AGENTS.md", ".claude/CLAUDE.md")
    for rel in sources:
        path = root / rel
        text = _read_text(path)
        for match in TERM_RE.finditer(text):
            term = " ".join(match.group(1).split())
            if 2 <= len(term) <= 80:
                terms.setdefault(term, rel)
    return [{"term": term, "source": source} for term, source in sorted(terms.items())[:80]]


def detect_source_roots(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in SOURCE_ROOT_CANDIDATES:
        path = root / name
        if not path.is_dir():
            continue
        py_count = sum(1 for _ in path.rglob("*.py") if not _is_ignored_path(_))
        js_count = sum(1 for _ in path.rglob("*.ts") if not _is_ignored_path(_))
        js_count += sum(1 for _ in path.rglob("*.tsx") if not _is_ignored_path(_))
        md_count = sum(1 for _ in path.rglob("*.md") if not _is_ignored_path(_))
        out.append({"path": name, "python_files": py_count, "ts_files": js_count, "markdown_files": md_count})
    return out


def detect_ci(root: Path) -> dict[str, Any]:
    workflows = sorted(_rel(p, root) for p in (root / ".github" / "workflows").glob("*.*"))
    return {
        "workflows": workflows,
        "pre_commit_config": (root / ".pre-commit-config.yaml").is_file(),
    }


def detect_lints_and_guards(root: Path) -> dict[str, Any]:
    lint_paths = sorted(p for p in (root / "scripts" / "lint").glob("*.py") if p.name != "__init__.py")
    policy_paths = sorted((root / "scripts" / "agent_policy").glob("*.py"))
    precommit = _read_text(root / ".pre-commit-config.yaml")
    hooks = re.findall(r"^\s+- id: ([A-Za-z0-9_.-]+)", precommit, flags=re.MULTILINE)
    return {
        "lint_rules": [_rel(p, root) for p in lint_paths],
        "agent_policy_files": [_rel(p, root) for p in policy_paths],
        "pre_commit_hooks": hooks[:80],
    }


def detect_sensitive_surfaces(root: Path) -> list[dict[str, str]]:
    surfaces: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if len(surfaces) >= 80:
            break
        if _is_ignored_path(path):
            continue
        rel = _rel(path, root)
        if path.is_dir() and SENSITIVE_NAME_RE.search(rel):
            surfaces.append({"path": rel, "kind": "directory", "reason": "sensitive-looking name"})
        elif path.is_file() and path.name in {".env", ".env.local"}:
            surfaces.append({"path": rel, "kind": "file", "reason": "environment secrets file"})
        elif path.is_file() and SENSITIVE_NAME_RE.search(rel) and path.suffix in {".py", ".ts", ".tsx", ".md"}:
            surfaces.append({"path": rel, "kind": "file", "reason": "sensitive-looking name"})
    return surfaces


def detect_skill_surface(root: Path) -> dict[str, Any]:
    skills_dir = root / ".claude" / "skills"
    skills = sorted(p.parent.name for p in skills_dir.glob("*/SKILL.md"))
    overlays = sorted(_rel(p, root) for p in skills_dir.glob("*/knowledge/*specifics.md"))
    return {
        "skill_count": len(skills),
        "skills": skills[:120],
        "project_specific_knowledge_files": overlays[:120],
    }


def build_standardization_cautions(adapter: dict[str, Any]) -> dict[str, Any]:
    source_roots = adapter.get("source_roots", [])
    lint_rules = adapter.get("guards", {}).get("lint_rules", [])
    has_many_files = any(root.get("python_files", 0) > 200 for root in source_roots)
    has_local_guards = bool(lint_rules)
    cautions = [
        "Observed frequency is not evidence of health; do not standardize common patterns until reviewed.",
        "Treat high-churn or low-test surfaces as stabilization candidates before turning them into doctrine.",
    ]
    if has_many_files:
        cautions.append("Large source roots may contain mixed-quality legacy code; extract exemplars selectively.")
    if not has_local_guards:
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


def discover_project(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    stack = detect_stack(root)
    adapter: dict[str, Any] = {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "project": {"name": root.name, "root": str(root)},
        "stack": stack,
        "commands": detect_commands(root, stack),
        "source_roots": detect_source_roots(root),
        "ci": detect_ci(root),
        "docs": detect_docs(root),
        "domain_terms": extract_domain_terms(root),
        "sensitive_surfaces": detect_sensitive_surfaces(root),
        "guards": detect_lints_and_guards(root),
        "skills": detect_skill_surface(root),
    }
    adapter["standardization"] = build_standardization_cautions(adapter)
    adapter["open_questions"] = build_adapter_questions(adapter)
    return adapter


def build_adapter_questions(adapter: dict[str, Any]) -> list[str]:
    questions = [
        "Which observed patterns are healthy enough to teach future agents, and which are just legacy frequency?",
        "Which workflows are correctness-critical enough to require guards before refactors?",
        "Which sensitive surfaces should block final handoff unless tests or an explicit not-run reason are present?",
    ]
    if not adapter.get("domain_terms"):
        questions.append("What domain vocabulary should be captured before agents start naming things?")
    if not adapter.get("ci", {}).get("workflows"):
        questions.append("What verification should count as the project default when CI is absent or incomplete?")
    return questions


def build_profile_from_discovery(adapter: dict[str, Any]) -> dict[str, Any]:
    terms = [row["term"] for row in adapter.get("domain_terms", [])[:12]]
    workflows = []
    for path in adapter.get("docs", {}).get("claude_docs", []):
        if "/workflows/" in path or path.endswith("workflows.md"):
            workflows.append(path)
    if not workflows:
        workflows = [root["path"] for root in adapter.get("source_roots", [])[:5]]

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "user_approved": False,
        "project": {
            "name": adapter.get("project", {}).get("name"),
            "purpose": None,
            "maturity": "unknown",
            "desired_direction": None,
        },
        "known_from_repo": {
            "stack": adapter.get("stack", {}),
            "candidate_domain_terms": terms,
            "candidate_workflows": workflows[:10],
            "existing_guardrails": adapter.get("guards", {}).get("pre_commit_hooks", [])[:20],
        },
        "needs_user_input": {
            "critical_workflows": [
                "Which workflows would cause the most damage if an agent broke them?",
                "Which workflows are important but currently too messy to canonize?",
            ],
            "risk_posture": [
                "Is this project a prototype, feature shop, durable system, or regulated/safety-critical system?",
                "Where should the agent slow down even if the code change looks small?",
            ],
            "intentional_tradeoffs": [
                "Which ugly-looking current patterns are intentional tradeoffs?",
                "Which common current patterns are known bad and should not be standardized?",
            ],
            "future_direction": [
                "What should this project become over the next 1-3 months?",
                "What cleanup or stabilization path should agents prefer before adding new surface area?",
            ],
        },
        "standardization_policy": {
            "do_not_canonize_by_frequency": True,
            "requires_human_approval_for_canonical_patterns": True,
            "notes": adapter.get("standardization", {}).get("cautions", []),
        },
    }


def adapter_markdown(adapter: dict[str, Any]) -> str:
    stack = adapter.get("stack", {})
    lines = [
        f"# Adapt Project Report — {adapter.get('project', {}).get('name')}",
        "",
        "## Stack",
        f"- Languages: {', '.join(stack.get('languages', [])) or '(none detected)'}",
        f"- Frameworks: {', '.join(stack.get('frameworks', [])) or '(none detected)'}",
        f"- Package managers: {', '.join(stack.get('package_managers', [])) or '(none detected)'}",
        "",
        "## Commands",
    ]
    for kind, commands in adapter.get("commands", {}).items():
        lines.append(f"- {kind}: {', '.join(commands) if commands else '(none inferred)'}")
    lines.extend(["", "## Sensitive Surfaces"])
    for row in adapter.get("sensitive_surfaces", [])[:20]:
        lines.append(f"- `{row['path']}` — {row['reason']}")
    if not adapter.get("sensitive_surfaces"):
        lines.append("- (none inferred)")
    lines.extend(["", "## Standardization Cautions"])
    for note in adapter.get("standardization", {}).get("cautions", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Open Questions"])
    for question in adapter.get("open_questions", []):
        lines.append(f"- {question}")
    return "\n".join(lines) + "\n"


def profile_markdown(profile: dict[str, Any]) -> str:
    project = profile.get("project", {})
    lines = [
        f"# Project Profile Draft — {project.get('name')}",
        "",
        "> Draft generated from repository discovery. Human approval is required",
        "> before these facts become project doctrine.",
        "",
        "## Known From Repo",
    ]
    known = profile.get("known_from_repo", {})
    lines.append(f"- Stack: {known.get('stack', {})}")
    lines.append(f"- Candidate domain terms: {', '.join(known.get('candidate_domain_terms', [])) or '(none)'}")
    lines.append(f"- Candidate workflows: {', '.join(known.get('candidate_workflows', [])) or '(none)'}")
    lines.extend(["", "## Interview Questions"])
    for group, questions in profile.get("needs_user_input", {}).items():
        lines.append(f"### {group.replace('_', ' ').title()}")
        for question in questions:
            lines.append(f"- {question}")
        lines.append("")
    lines.extend(["## Standardization Policy"])
    for note in profile.get("standardization_policy", {}).get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines).rstrip() + "\n"


def open_questions_markdown(profile: dict[str, Any]) -> str:
    lines = ["# Project Open Questions", ""]
    for group, questions in profile.get("needs_user_input", {}).items():
        lines.append(f"## {group.replace('_', ' ').title()}")
        for question in questions:
            lines.append(f"- [ ] {question}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _scan_dir(artifact_root: Path, skill: str, sid: str) -> Path:
    return artifact_root / "reports" / skill / sid


def _update_latest(scan_dir: Path) -> None:
    latest = scan_dir.parent / "latest"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(scan_dir.name)
    except OSError:
        # Some platforms disallow symlinks; the timestamped directory is the
        # load-bearing artifact.
        pass


def write_discovery(
    project_root: Path,
    artifact_root: Path,
    *,
    timestamp: str | None,
    apply: bool,
    no_host_write: bool,
) -> Path:
    _validate_write_mode(project_root, artifact_root, apply=apply, no_host_write=no_host_write)
    sid = scan_id(timestamp)
    adapter = discover_project(project_root)
    scan_dir = _scan_dir(artifact_root, "adapt-project", sid)
    scan_dir.mkdir(parents=True, exist_ok=True)
    _safe_yaml_dump(scan_dir / "adapter.yml", adapter)
    _write_json(scan_dir / "adapter.json", adapter)
    (scan_dir / "report.md").write_text(adapter_markdown(adapter), encoding="utf-8")
    (scan_dir / "evidence.json").write_text(
        json.dumps(
            {
                "skill": "adapt-project",
                "scan_id": sid,
                "produced_at": utc_now(),
                "evidence": {"adapter": "adapter.yml", "report": "report.md"},
                "notes": "no host writes" if no_host_write else "",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _update_latest(scan_dir)
    if apply:
        dest = _eh.project_dir(project_root) / "adapter.yml"
        _safe_yaml_dump(dest, adapter)
    return scan_dir


def write_profile_draft(
    project_root: Path,
    artifact_root: Path,
    *,
    timestamp: str | None,
    apply: bool,
    no_host_write: bool,
) -> Path:
    _validate_write_mode(project_root, artifact_root, apply=apply, no_host_write=no_host_write)
    sid = scan_id(timestamp)
    adapter = discover_project(project_root)
    profile = build_profile_from_discovery(adapter)
    scan_dir = _scan_dir(artifact_root, "project-interview", sid)
    scan_dir.mkdir(parents=True, exist_ok=True)
    _safe_yaml_dump(scan_dir / "profile.yml", profile)
    (scan_dir / "profile.md").write_text(profile_markdown(profile), encoding="utf-8")
    (scan_dir / "open-questions.md").write_text(open_questions_markdown(profile), encoding="utf-8")
    (scan_dir / "repo-facts.yml").write_text(
        yaml.safe_dump(adapter, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    (scan_dir / "evidence.json").write_text(
        json.dumps(
            {
                "skill": "project-interview",
                "scan_id": sid,
                "produced_at": utc_now(),
                "evidence": {
                    "profile": "profile.yml",
                    "profile_summary": "profile.md",
                    "open_questions": "open-questions.md",
                },
                "notes": "draft profile; human approval required",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _update_latest(scan_dir)
    if apply:
        dest_dir = _eh.project_dir(project_root)
        _safe_yaml_dump(dest_dir / "profile.yml", profile)
        (dest_dir / "profile.md").write_text(profile_markdown(profile), encoding="utf-8")
        (dest_dir / "open-questions.md").write_text(open_questions_markdown(profile), encoding="utf-8")
    return scan_dir


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def validate_adapter_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "project", "stack", "commands", "source_roots", "standardization"):
        if key not in payload:
            errors.append(f"missing required adapter key: {key}")
    if payload.get("schema_version") != ADAPTER_SCHEMA_VERSION:
        errors.append("unsupported adapter schema_version")
    if not isinstance(payload.get("project"), dict):
        errors.append("adapter.project must be a mapping")
    if not isinstance(payload.get("standardization"), dict):
        errors.append("adapter.standardization must be a mapping")
    return errors


def validate_profile_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "user_approved", "project", "known_from_repo", "needs_user_input"):
        if key not in payload:
            errors.append(f"missing required profile key: {key}")
    if payload.get("schema_version") != PROFILE_SCHEMA_VERSION:
        errors.append("unsupported profile schema_version")
    if not isinstance(payload.get("needs_user_input"), dict):
        errors.append("profile.needs_user_input must be a mapping")
    return errors


def evaluate_dogfood(project_root: Path, artifact_root: Path, *, reference: str | None = None) -> Path:
    if _is_within(artifact_root, project_root):
        raise ValueError("dogfood evaluation requires --artifact-root outside --project-root")
    adapter = discover_project(project_root)
    profile = build_profile_from_discovery(adapter)
    expected = []
    if reference and "host-a" in reference.lower():
        expected = [
            ("Django stack", "django" in adapter.get("stack", {}).get("frameworks", [])),
            ("venv Python command", any(".venv/bin/python" in c for c in adapter.get("commands", {}).get("test", []))),
            ("Site domain term", any(row["term"] == "Terminology" or "Site" in row["term"] for row in adapter.get("domain_terms", []))),
            ("Site Intelligence surface", any("site_intelligence" in row["path"] for row in adapter.get("sensitive_surfaces", []))),
            ("agent policy guard surface", bool(adapter.get("guards", {}).get("agent_policy_files"))),
        ]

    good = [name for name, ok in expected if ok]
    missing = [name for name, ok in expected if not ok]
    needs_interview = profile.get("needs_user_input", {})
    lines = [
        f"# Dogfood Evaluation — {project_root.name}",
        "",
        "## Good Inference",
    ]
    if good:
        lines.extend(f"- {item}" for item in good)
    else:
        lines.append("- Stack/docs/source-root discovery completed; no reference-specific checks requested.")
    lines.extend(["", "## Needs Interview"])
    for group, questions in needs_interview.items():
        lines.append(f"- {group}: {questions[0] if questions else 'needs human input'}")
    lines.extend(["", "## False Inference"])
    lines.append("- None identified mechanically; requires human review of adapter.yml.")
    lines.extend(["", "## Missing But Important"])
    if missing:
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append("- No reference-specific required marker was missing.")
    lines.extend(["", "## Kernel Candidate"])
    lines.append("- Standardization caution: observed frequency must not become doctrine without review.")
    lines.append("- Project profile and adapter schemas are generally reusable across host projects.")
    lines.extend(["", "## Host-Only"])
    for term in adapter.get("domain_terms", [])[:8]:
        lines.append(f"- {term['term']} ({term['source']})")
    if not adapter.get("domain_terms"):
        lines.append("- No host-only domain terms detected.")

    artifact_root.mkdir(parents=True, exist_ok=True)
    path = artifact_root / "evaluation.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _print_scan(path: Path) -> None:
    print(path)


def cmd_discover(args: argparse.Namespace) -> int:
    try:
        path = write_discovery(
            args.project_root.resolve(),
            args.artifact_root.resolve(),
            timestamp=args.timestamp,
            apply=args.apply,
            no_host_write=args.no_host_write,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_scan(path)
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    try:
        path = write_profile_draft(
            args.project_root.resolve(),
            args.artifact_root.resolve(),
            timestamp=args.timestamp,
            apply=args.apply,
            no_host_write=args.no_host_write,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_scan(path)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        path = evaluate_dogfood(args.project_root.resolve(), args.artifact_root.resolve(), reference=args.reference)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(path)
    return 0


def cmd_validate_adapter(args: argparse.Namespace) -> int:
    try:
        payload = _load_yaml(args.path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validate_adapter_payload(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("adapter OK")
    return 0


def cmd_validate_profile(args: argparse.Namespace) -> int:
    try:
        payload = _load_yaml(args.path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validate_profile_payload(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("profile OK")
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-root", type=Path, default=Path.cwd())
    parser.add_argument("--timestamp", help="Stable scan timestamp for tests, e.g. 20260517-120000")
    parser.add_argument("--apply", action="store_true", help="Write durable .engineering/project files")
    parser.add_argument("--no-host-write", action="store_true", help="Assert this run must not write to project-root")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project adaptation and interview helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    discover = sub.add_parser("discover", help="Discover objective project adapter facts")
    add_common_args(discover)
    discover.set_defaults(func=cmd_discover)

    interview = sub.add_parser("interview", help="Draft a project interview profile")
    add_common_args(interview)
    interview.set_defaults(func=cmd_interview)

    evaluate = sub.add_parser("evaluate", help="Write a dogfood evaluation report")
    evaluate.add_argument("--project-root", type=Path, default=Path.cwd())
    evaluate.add_argument("--artifact-root", type=Path, required=True)
    evaluate.add_argument("--reference")
    evaluate.set_defaults(func=cmd_evaluate)

    va = sub.add_parser("validate-adapter", help="Validate adapter.yml schema")
    va.add_argument("path", type=Path)
    va.set_defaults(func=cmd_validate_adapter)

    vp = sub.add_parser("validate-profile", help="Validate profile.yml schema")
    vp.add_argument("path", type=Path)
    vp.set_defaults(func=cmd_validate_profile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
