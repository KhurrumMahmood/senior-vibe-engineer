"""Deterministic, evidence-bearing multi-root host profiles (WP2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .capability_registry import CapabilityRegistry, load_registry


HOST_PROFILE_SCHEMA_VERSION = 1
SKIP_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "vendored",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "reports",
    }
)
DEFAULT_EXCLUSIONS = (
    ("**/.git/**", "version-control metadata"),
    ("**/.venv/**", "project-local Python environment"),
    ("**/node_modules/**", "installed JavaScript dependencies"),
    ("**/vendor/**", "vendored third-party source"),
    ("**/dist/**", "generated distribution output"),
    ("**/build/**", "generated build output"),
    ("**/target/**", "generated Rust build output"),
)
COMMAND_KINDS = ("build", "dev", "lint", "setup", "test")


def _ignored(path: Path, repo_root: Path) -> bool:
    try:
        parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return any(part in SKIP_PARTS for part in parts)


def _rel(path: Path, repo_root: Path) -> str:
    relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    return relative or "."


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_package(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_roots(repo_root: Path, registry: CapabilityRegistry) -> list[Path]:
    markers = tuple(registry.data["project_root"]["root_markers"])
    candidates: set[Path] = set()
    for marker in markers:
        for path in repo_root.rglob(marker):
            if path.is_file() and not _ignored(path, repo_root):
                candidates.add(path.parent)
    if not candidates:
        candidates.add(repo_root)
    return sorted(candidates, key=lambda path: _rel(path, repo_root))


def _marker_evidence(
    root: Path,
    repo_root: Path,
    markers: list[str],
) -> tuple[str, str] | None:
    for marker in markers:
        path = root / marker
        if path.is_file():
            return "marker", _rel(path, repo_root)
    return None


def _extension_evidence(
    root: Path,
    repo_root: Path,
    extensions: list[str],
) -> tuple[str, str] | None:
    for extension in extensions:
        for path in sorted(root.rglob(f"*{extension}")):
            if path.is_file() and not _ignored(path, repo_root):
                return "extension", _rel(path, repo_root)
    return None


def _package_corpus(root: Path, repo_root: Path) -> list[tuple[Path, str]]:
    paths = [
        root / "requirements.txt",
        root / "pyproject.toml",
        root / "package.json",
        root / "Cargo.toml",
        root / "go.mod",
    ]
    return [(path, _read(path).lower()) for path in paths if path.is_file() and not _ignored(path, repo_root)]


def _token_evidence(
    corpus: list[tuple[Path, str]],
    repo_root: Path,
    tokens: list[str],
) -> tuple[str, str] | None:
    for token in tokens:
        lowered = str(token).lower()
        for path, text in corpus:
            if lowered in text:
                return "package-token", _rel(path, repo_root)
    return None


def _detect_stack(root: Path, repo_root: Path, registry: CapabilityRegistry) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    stack = {"languages": [], "frameworks": [], "tools": []}
    evidence: list[dict[str, str]] = []
    corpus = _package_corpus(root, repo_root)

    for category in ("languages", "frameworks", "tools"):
        for identifier, entry in registry.data[category].items():
            if category == "languages" and not entry.get("subject"):
                continue
            if category == "frameworks" and identifier in {"any", "none"}:
                continue
            observed = _marker_evidence(
                root,
                repo_root,
                list(entry.get("project_markers", entry.get("file_markers", []))),
            )
            if observed is None and category == "languages":
                observed = _extension_evidence(root, repo_root, list(entry.get("extensions", [])))
            if observed is None:
                observed = _token_evidence(corpus, repo_root, list(entry.get("package_tokens", [])))
            if observed is None:
                continue
            stack[category].append(identifier)
            evidence.append(
                {
                    "category": category,
                    "identifier": identifier,
                    "kind": observed[0],
                    "path": observed[1],
                }
            )

    if (root / "package.json").is_file() and not any(
        "package-manager" in registry.data["tools"][tool].get("roles", [])
        for tool in stack["tools"]
    ):
        fallback = next(
            (
                identifier
                for identifier, entry in registry.data["tools"].items()
                if entry.get("fallback_for") == "package.json"
            ),
            None,
        )
        if fallback:
            stack["tools"].append(fallback)
            evidence.append(
                {
                    "category": "tools",
                    "identifier": fallback,
                    "kind": "fallback-marker",
                    "path": _rel(root / "package.json", repo_root),
                }
            )

    return (
        {key: sorted(set(values)) for key, values in stack.items()},
        sorted(evidence, key=lambda item: (item["category"], item["identifier"], item["path"])),
    )


def _commands(root: Path, stack: dict[str, list[str]], registry: CapabilityRegistry) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {kind: [] for kind in COMMAND_KINDS}
    languages = set(stack["languages"])
    frameworks = set(stack["frameworks"])
    tools = set(stack["tools"])
    if "python" in languages:
        python = ".venv/bin/python" if (root / ".venv" / "bin" / "python").is_file() else "python3"
        commands["setup"].append("python3 -m venv .venv")
        if (root / "requirements.txt").is_file():
            commands["setup"].append(".venv/bin/python -m pip install -r requirements.txt")
        if "django" in frameworks:
            commands["test"].append(f"{python} manage.py test")
            commands["dev"].append(f"{python} manage.py runserver")
        elif "pytest" in tools or (root / "tests").is_dir():
            commands["test"].append(f"{python} -m pytest")
        else:
            commands["test"].append(f"{python} -m unittest discover")
        if "ruff" in tools:
            commands["lint"].append(f"{python} -m ruff check .")
    if "rust" in languages:
        commands["build"].append("cargo build")
        commands["test"].append("cargo test")
        commands["lint"].append("cargo clippy --all-targets --all-features -- -D warnings")
    if "go" in languages:
        commands["build"].append("go build ./...")
        commands["test"].append("go test ./...")
        commands["lint"].append("go vet ./...")
    package = _load_package(root / "package.json")
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    package_managers = [
        tool
        for tool in sorted(tools)
        if "package-manager" in registry.data["tools"][tool].get("roles", [])
        and registry.data["tools"][tool].get("run_script_command")
    ]
    prefix = registry.data["tools"][package_managers[0]]["run_script_command"] if package_managers else "npm run"
    for name in sorted(scripts):
        command = f"{prefix} {name}"
        if "test" in name:
            commands["test"].append(command)
        if "lint" in name or "typecheck" in name:
            commands["lint"].append(command)
        if name in {"dev", "start"}:
            commands["dev"].append(command)
        if name in {"build", "compile"}:
            commands["build"].append(command)
    return {kind: sorted(set(commands[kind])) for kind in COMMAND_KINDS}


def _code_roots(root: Path, repo_root: Path, registry: CapabilityRegistry) -> list[str]:
    extensions = {
        extension
        for entry in registry.data["languages"].values()
        if entry.get("subject")
        for extension in entry.get("extensions", [])
    }
    roots: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in extensions or _ignored(path, repo_root):
            continue
        relative = path.relative_to(root)
        owner = root if len(relative.parts) == 1 else root / relative.parts[0]
        roots.add(_rel(owner, repo_root))
    return sorted(roots)


def _manifest_profiles(repo_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = repo_root / ".engineering" / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    component = payload.get("component_profile")
    if not isinstance(component, dict):
        component = {}
    normalized_component = {
        "definitions_root": str(component.get("definitions_root", "")),
        "extensions": sorted(str(item) for item in component.get("extensions", []) if isinstance(item, str)),
        "kind": str(component.get("kind", "none") or "none"),
        "reference_pattern": str(component.get("reference_pattern", "")),
    }
    labels = payload.get("surface_labels")
    normalized_labels = (
        {str(key): str(value) for key, value in sorted(labels.items())}
        if isinstance(labels, dict)
        else {}
    )
    return normalized_component, normalized_labels


def _profile_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# spec:portable-host-profile-routing::IM-1
# spec:portable-host-profile-routing::IM-2
def profile_host(repo_root: Path | str, *, registry: CapabilityRegistry | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    selected_registry = registry or load_registry()
    roots: list[dict[str, Any]] = []
    for candidate in _candidate_roots(root, selected_registry):
        stack, evidence = _detect_stack(candidate, root, selected_registry)
        roots.append(
            {
                "path": _rel(candidate, root),
                "languages": stack["languages"],
                "frameworks": stack["frameworks"],
                "tools": stack["tools"],
                "code_roots": _code_roots(candidate, root, selected_registry),
                "commands": _commands(candidate, stack, selected_registry),
                "evidence": evidence,
            }
        )
    component, labels = _manifest_profiles(root)
    aggregate = {
        category: sorted({identifier for item in roots for identifier in item[category]})
        for category in ("languages", "frameworks", "tools")
    }
    payload: dict[str, Any] = {
        "schema_version": HOST_PROFILE_SCHEMA_VERSION,
        "capability_registry_version": selected_registry.schema_version,
        "capability_contract_version": selected_registry.contract_version,
        "project": {"name": root.name},
        "roots": roots,
        "stack": {
            **aggregate,
            "project_roots": [{"path": item["path"], "kind": "code"} for item in roots],
        },
        "exclusions": [
            {"pattern": pattern, "reason": reason}
            for pattern, reason in DEFAULT_EXCLUSIONS
        ],
        "component_profile": component,
        "surface_labels": labels,
    }
    payload["profile_sha256"] = _profile_hash(payload)
    return payload


def validate_host_profile(
    payload: dict[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
) -> list[str]:
    selected_registry = registry or load_registry()
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["host-profile must be a mapping"]

    def require_keys(value: object, expected: set[str], prefix: str) -> bool:
        if not isinstance(value, dict):
            errors.append(f"{prefix} must be a mapping")
            return False
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        if missing:
            errors.append(f"{prefix} is missing fields: {missing}")
        if extra:
            errors.append(f"{prefix} has unknown fields: {extra}")
        return not missing and not extra

    def string_list(value: object, prefix: str) -> list[str] | None:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            errors.append(f"{prefix} must be a list of strings")
            return None
        if any(not item.strip() for item in value):
            errors.append(f"{prefix} entries must be non-empty")
        if value != sorted(set(value)):
            errors.append(f"{prefix} must be unique and sorted")
        return value

    def relative_path(value: object, prefix: str, *, allow_empty: bool = False) -> bool:
        if not isinstance(value, str) or (not value and not allow_empty):
            errors.append(f"{prefix} must be a {'possibly empty ' if allow_empty else 'non-empty '}string")
            return False
        if not value:
            return True
        candidate = PurePosixPath(value)
        if (
            "\\" in value
            or "\x00" in value
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.as_posix() != value
        ):
            errors.append(f"{prefix} must be a normalized relative POSIX path")
            return False
        return True

    top_fields = {
        "schema_version",
        "capability_registry_version",
        "capability_contract_version",
        "project",
        "roots",
        "stack",
        "exclusions",
        "component_profile",
        "surface_labels",
        "profile_sha256",
    }
    require_keys(payload, top_fields, "host-profile")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != HOST_PROFILE_SCHEMA_VERSION
    ):
        errors.append("unsupported host-profile schema_version")
    if (
        type(payload.get("capability_registry_version")) is not int
        or payload.get("capability_registry_version") != selected_registry.schema_version
    ):
        errors.append("host-profile capability_registry_version does not match registry")
    if (
        type(payload.get("capability_contract_version")) is not int
        or payload.get("capability_contract_version") != selected_registry.contract_version
    ):
        errors.append("host-profile capability_contract_version does not match registry")
    project = payload.get("project")
    if require_keys(project, {"name"}, "host-profile.project"):
        name = project.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append("host-profile.project.name must be a non-empty string")

    roots_value = payload.get("roots")
    if not isinstance(roots_value, list) or not roots_value:
        errors.append("host-profile roots must be a non-empty list")
        roots: list[object] = []
    else:
        roots = roots_value
    paths = [item.get("path") for item in roots if isinstance(item, dict)]
    if (
        len(paths) != len(roots)
        or any(not isinstance(path, str) for path in paths)
        or paths != sorted(set(paths))
    ):
        errors.append("host-profile root paths must be unique and sorted")
    root_stacks: list[dict[str, list[str]]] = []
    for index, item in enumerate(roots):
        prefix = f"host-profile.roots[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        require_keys(
            item,
            {"path", "languages", "frameworks", "tools", "code_roots", "commands", "evidence"},
            prefix,
        )
        relative_path(item.get("path"), f"{prefix}.path")
        stack: dict[str, list[str]] = {}
        for category in ("languages", "frameworks", "tools"):
            identifiers = string_list(item.get(category), f"{prefix}.{category}")
            stack[category] = identifiers or []
        if all(isinstance(item.get(category), list) for category in stack):
            errors.extend(selected_registry.validate_stack(stack, prefix=prefix))
        root_stacks.append(stack)

        code_roots = string_list(item.get("code_roots"), f"{prefix}.code_roots")
        for root_index, code_root in enumerate(code_roots or []):
            relative_path(code_root, f"{prefix}.code_roots[{root_index}]")

        commands = item.get("commands")
        if require_keys(commands, set(COMMAND_KINDS), f"{prefix}.commands"):
            for command_kind in COMMAND_KINDS:
                string_list(commands.get(command_kind), f"{prefix}.commands.{command_kind}")

        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{prefix}.evidence must be a list")
            evidence = []
        observed: set[tuple[str, str]] = set()
        evidence_order: list[tuple[str, str, str]] = []
        for evidence_index, record in enumerate(evidence):
            evidence_prefix = f"{prefix}.evidence[{evidence_index}]"
            if not require_keys(
                record,
                {"category", "identifier", "kind", "path"},
                evidence_prefix,
            ):
                continue
            category = record.get("category")
            identifier = record.get("identifier")
            kind = record.get("kind")
            evidence_path = record.get("path")
            if category not in {"languages", "frameworks", "tools"}:
                errors.append(f"{evidence_prefix}.category is invalid")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"{evidence_prefix}.identifier must be a non-empty string")
            if kind not in {"marker", "extension", "package-token", "fallback-marker"}:
                errors.append(f"{evidence_prefix}.kind is invalid")
            path_ok = relative_path(evidence_path, f"{evidence_prefix}.path")
            if isinstance(category, str) and isinstance(identifier, str):
                if category in stack and identifier not in stack[category]:
                    errors.append(f"{evidence_prefix} does not match an asserted stack identifier")
                observed.add((category, identifier))
            if (
                isinstance(category, str)
                and isinstance(identifier, str)
                and isinstance(evidence_path, str)
                and path_ok
            ):
                evidence_order.append((category, identifier, evidence_path))
        if len(evidence_order) != len(evidence) or evidence_order != sorted(set(evidence_order)):
            errors.append(f"{prefix}.evidence must be unique and sorted")
        for category, identifiers in stack.items():
            for identifier in identifiers:
                if (category, identifier) not in observed:
                    errors.append(
                        f"{prefix}.{category}.{identifier} has no evidence"
                    )

    stack_value = payload.get("stack")
    stack_fields = {"languages", "frameworks", "tools", "project_roots"}
    if require_keys(stack_value, stack_fields, "host-profile.stack"):
        aggregate: dict[str, list[str]] = {}
        for category in ("languages", "frameworks", "tools"):
            values = string_list(stack_value.get(category), f"host-profile.stack.{category}")
            aggregate[category] = values or []
        errors.extend(selected_registry.validate_stack(aggregate, prefix="host-profile.stack"))
        expected_aggregate = {
            category: sorted({identifier for root_stack in root_stacks for identifier in root_stack[category]})
            for category in ("languages", "frameworks", "tools")
        }
        if aggregate != expected_aggregate:
            errors.append("host-profile.stack does not equal the aggregate root stack")

        project_roots = stack_value.get("project_roots")
        if not isinstance(project_roots, list):
            errors.append("host-profile.stack.project_roots must be a list")
        else:
            projected_paths: list[str] = []
            for project_index, record in enumerate(project_roots):
                project_prefix = f"host-profile.stack.project_roots[{project_index}]"
                if not require_keys(record, {"path", "kind"}, project_prefix):
                    continue
                if relative_path(record.get("path"), f"{project_prefix}.path"):
                    projected_paths.append(record["path"])
                if record.get("kind") != "code":
                    errors.append(f"{project_prefix}.kind must be 'code'")
            if projected_paths != paths:
                errors.append("host-profile.stack.project_roots must exactly project root paths")

    exclusions = payload.get("exclusions")
    if not isinstance(exclusions, list):
        errors.append("host-profile.exclusions must be a list")
    else:
        patterns: list[str] = []
        for index, item in enumerate(exclusions):
            prefix = f"host-profile.exclusions[{index}]"
            if not require_keys(item, {"pattern", "reason"}, prefix):
                continue
            pattern = item.get("pattern")
            reason = item.get("reason")
            if not isinstance(pattern, str) or not pattern.strip():
                errors.append(f"{prefix}.pattern must be a non-empty string")
            else:
                patterns.append(pattern)
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{prefix}.reason must be a non-empty string")
        if len(patterns) != len(set(patterns)):
            errors.append("host-profile exclusion patterns must be unique")

    component = payload.get("component_profile")
    if require_keys(
        component,
        {"kind", "definitions_root", "reference_pattern", "extensions"},
        "host-profile.component_profile",
    ):
        if not isinstance(component.get("kind"), str) or not component["kind"].strip():
            errors.append("host-profile.component_profile.kind must be a non-empty string")
        relative_path(
            component.get("definitions_root"),
            "host-profile.component_profile.definitions_root",
            allow_empty=True,
        )
        if not isinstance(component.get("reference_pattern"), str):
            errors.append("host-profile.component_profile.reference_pattern must be a string")
        extensions = string_list(
            component.get("extensions"),
            "host-profile.component_profile.extensions",
        )
        if extensions is not None and any(
            not extension.startswith(".") or "/" in extension or "\\" in extension
            for extension in extensions
        ):
            errors.append("host-profile.component_profile.extensions must be file suffixes")

    labels = payload.get("surface_labels")
    if not isinstance(labels, dict):
        errors.append("host-profile.surface_labels must be a mapping")
    else:
        for selector, label in labels.items():
            if not isinstance(selector, str) or not selector.strip():
                errors.append("host-profile.surface_labels selectors must be non-empty strings")
            if not isinstance(label, str) or not label.strip():
                errors.append("host-profile.surface_labels values must be non-empty strings")

    claimed_hash = payload.get("profile_sha256")
    if not isinstance(claimed_hash, str):
        errors.append("host-profile profile_sha256 must be a string")
    unhashed = dict(payload)
    unhashed.pop("profile_sha256", None)
    if claimed_hash != _profile_hash(unhashed):
        errors.append("host-profile profile_sha256 does not match content")
    return errors
