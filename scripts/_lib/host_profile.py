"""Deterministic, evidence-bearing multi-root host profiles (WP2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
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
    if payload.get("schema_version") != HOST_PROFILE_SCHEMA_VERSION:
        errors.append("unsupported host-profile schema_version")
    if payload.get("capability_registry_version") != selected_registry.schema_version:
        errors.append("host-profile capability_registry_version does not match registry")
    if payload.get("capability_contract_version") != selected_registry.contract_version:
        errors.append("host-profile capability_contract_version does not match registry")
    roots = payload.get("roots")
    if not isinstance(roots, list) or not roots:
        errors.append("host-profile roots must be a non-empty list")
        return errors
    paths = [item.get("path") for item in roots if isinstance(item, dict)]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        errors.append("host-profile root paths must be unique and sorted")
    for index, item in enumerate(roots):
        if not isinstance(item, dict):
            errors.append(f"host-profile roots[{index}] must be a mapping")
            continue
        stack = {category: item.get(category, []) for category in ("languages", "frameworks", "tools")}
        errors.extend(selected_registry.validate_stack(stack, prefix=f"host-profile.roots[{index}]"))
        evidence = item.get("evidence")
        observed = {
            (record.get("category"), record.get("identifier"))
            for record in evidence
            if isinstance(record, dict)
        } if isinstance(evidence, list) else set()
        for category, identifiers in stack.items():
            if not isinstance(identifiers, list):
                continue
            for identifier in identifiers:
                if (category, identifier) not in observed:
                    errors.append(
                        f"host-profile.roots[{index}].{category}.{identifier} has no evidence"
                    )
        commands = item.get("commands")
        if not isinstance(commands, dict) or set(commands) != set(COMMAND_KINDS):
            errors.append(f"host-profile.roots[{index}].commands has invalid shape")
    exclusions = payload.get("exclusions")
    if not isinstance(exclusions, list) or any(
        not isinstance(item, dict) or not item.get("pattern") or not item.get("reason")
        for item in exclusions or []
    ):
        errors.append("host-profile exclusions require pattern and reason")
    claimed_hash = payload.get("profile_sha256")
    unhashed = dict(payload)
    unhashed.pop("profile_sha256", None)
    if claimed_hash != _profile_hash(unhashed):
        errors.append("host-profile profile_sha256 does not match content")
    return errors
