#!/usr/bin/env python3
"""Inventory repository source files and classify roles without analyzing code."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from collections import Counter
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parent.parent
if str(LIBRARY_ROOT) not in sys.path:
    # Isolated execution intentionally imports only from this exact library root.
    sys.path.insert(0, str(LIBRARY_ROOT))

from scripts._lib.language_support.profile import (  # noqa: E402
    SCHEMA_VERSION as PROFILE_SCHEMA_VERSION,
    LanguageProfile,
    ProfileError,
    load_profiles,
)
from scripts._lib.language_support.lifecycle import write_text_atomic  # noqa: E402


DEFAULT_PROFILES_ROOT = Path(__file__).resolve().parent / "language_profiles"

UNSUPPORTED_SUFFIXES = {
    ".rs": "rust",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".rb": "ruby",
}

EXCLUDED_DIRECTORIES = {
    ".git": ("tooling", "repository_metadata"),
    ".hg": ("tooling", "repository_metadata"),
    ".svn": ("tooling", "repository_metadata"),
    ".venv": ("vendor", "external_dependency"),
    "venv": ("vendor", "external_dependency"),
    "node_modules": ("vendor", "external_dependency"),
    "vendor": ("vendor", "external_dependency"),
    "vendored": ("vendor", "external_dependency"),
    "dist": ("build", "build_output"),
    "build": ("build", "build_output"),
    "coverage": ("build", "build_output"),
    ".next": ("build", "build_output"),
    "target": ("build", "build_output"),
    "__pycache__": ("build", "cache"),
    ".mypy_cache": ("build", "cache"),
    ".pytest_cache": ("build", "cache"),
    ".ruff_cache": ("build", "cache"),
}

TEST_DIRECTORIES = {"test", "tests", "__tests__"}
FIXTURE_DIRECTORIES = {"fixture", "fixtures"}
TOOL_DIRECTORIES = {"script", "scripts", "tool", "tools", "bin"}
MIGRATION_DIRECTORIES = {"migration", "migrations"}
GENERATED_DIRECTORIES = {"generated", "gen"}


class InventoryError(ValueError):
    """Invalid or unsafe inventory request."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _language_for(
    path: Path,
    suffix_profiles: dict[str, LanguageProfile],
) -> tuple[str | None, bool, LanguageProfile | None]:
    suffix = path.suffix.lower()
    profile = suffix_profiles.get(suffix)
    if profile is not None:
        return profile.language, True, profile
    if suffix in UNSUPPORTED_SUFFIXES:
        return UNSUPPORTED_SUFFIXES[suffix], False, None
    return None, False, None


def _matches(name: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in globs)


def _is_generated_name(name: str) -> bool:
    lowered = name.lower()
    return any(
        marker in lowered
        for marker in (
            ".generated.",
            ".gen.",
            ".bundle.",
            ".min.",
            "_generated.",
        )
    )


def _is_config_name(name: str, profile: LanguageProfile | None) -> bool:
    lowered = name.lower()
    configured = (
        {item.lower() for item in profile.source_roles.configuration_files}
        if profile is not None
        else set()
    )
    return ".config." in lowered or lowered in configured


def _role(
    path: Path,
    project_root: Path,
    profile: LanguageProfile | None,
) -> tuple[str, str, str]:
    relative = path.relative_to(project_root)
    parts = {part.lower() for part in relative.parts[:-1]}
    name = path.name.lower()

    if parts & FIXTURE_DIRECTORIES and not parts & TEST_DIRECTORIES:
        return "unknown", "ambiguous", "fixture_or_product_data"
    if parts & GENERATED_DIRECTORIES or _is_generated_name(name):
        return "generated", "classified", "generated_path_or_name"
    if parts & TEST_DIRECTORIES or (
        profile is not None and _matches(path.name, profile.source_roles.test_file_globs)
    ):
        return "test", "classified", "test_path_or_name"
    if profile is not None and _matches(
        path.name, profile.source_roles.declaration_file_globs
    ):
        return "declaration", "classified", "declaration_suffix"
    if _is_config_name(name, profile):
        return "configuration", "classified", "configuration_name"
    if parts & MIGRATION_DIRECTORIES:
        return "migration", "classified", "migration_path"
    if parts & TOOL_DIRECTORIES:
        return "tooling", "classified", "tooling_path"
    return "source", "classified", "source_default"


def _validate_root(raw: Path, *, label: str) -> Path:
    if not raw.exists():
        raise InventoryError(f"{label} does not exist: {raw}")
    if raw.is_symlink():
        raise InventoryError(f"{label} may not be a symbolic link: {raw}")
    resolved = raw.resolve()
    if not resolved.is_dir():
        raise InventoryError(f"{label} must be a directory: {raw}")
    return resolved


def _walk_source_root(
    source_root: Path,
    project_root: Path,
    *,
    suffix_profiles: dict[str, LanguageProfile],
    seen_files: set[str],
    seen_excluded: set[str],
) -> tuple[list[dict], list[dict]]:
    files: list[dict] = []
    excluded_roots: list[dict] = []
    for directory, child_directories, filenames in os.walk(source_root, followlinks=False):
        current = Path(directory)
        retained: list[str] = []
        for child_name in sorted(child_directories):
            child = current / child_name
            relative = _relative(child, project_root)
            excluded = EXCLUDED_DIRECTORIES.get(child_name.lower())
            if child.is_symlink():
                excluded = ("symlink", "symlink_boundary")
            if excluded is not None:
                if relative not in seen_excluded:
                    seen_excluded.add(relative)
                    role, reason = excluded
                    excluded_roots.append(
                        {"path": relative, "role": role, "reason": reason}
                    )
                continue
            retained.append(child_name)
        child_directories[:] = retained

        for filename in sorted(filenames):
            path = current / filename
            if path.is_symlink():
                relative = _relative(path, project_root)
                if relative not in seen_excluded:
                    seen_excluded.add(relative)
                    excluded_roots.append(
                        {
                            "path": relative,
                            "role": "symlink",
                            "reason": "symlink_boundary",
                        }
                    )
                continue
            language, supported, profile = _language_for(path, suffix_profiles)
            if language is None:
                continue
            relative = _relative(path, project_root)
            if relative in seen_files:
                continue
            seen_files.add(relative)
            role, classification, reason = _role(path, project_root, profile)
            if not supported:
                classification = "unsupported"
                reason = "language_not_enabled"
            files.append(
                {
                    "path": relative,
                    "language": language,
                    "suffix": path.suffix.lower(),
                    "role": role,
                    "classification": classification,
                    "reason": reason,
                }
            )
    return files, excluded_roots


def build_inventory(
    project_root: Path,
    source_roots: list[Path],
    profiles_root: Path | None = None,
) -> dict:
    project = _validate_root(project_root, label="project root")
    profiles = load_profiles(profiles_root or DEFAULT_PROFILES_ROOT)
    suffix_profiles = {
        suffix: profile
        for profile in profiles.values()
        for suffix in profile.suffixes
    }
    roots = source_roots or [project]
    resolved_roots: list[Path] = []
    for raw in roots:
        candidate = _validate_root(raw, label="source root")
        if not _is_within(candidate, project):
            raise InventoryError(
                f"source root must stay within project root: {raw}"
            )
        resolved_roots.append(candidate)
    resolved_roots = sorted(set(resolved_roots))

    files: list[dict] = []
    excluded_roots: list[dict] = []
    seen_files: set[str] = set()
    seen_excluded: set[str] = set()
    for root in resolved_roots:
        root_files, root_excluded = _walk_source_root(
            root,
            project,
            suffix_profiles=suffix_profiles,
            seen_files=seen_files,
            seen_excluded=seen_excluded,
        )
        files.extend(root_files)
        excluded_roots.extend(root_excluded)

    files.sort(key=lambda row: row["path"])
    excluded_roots.sort(key=lambda row: row["path"])
    classification = Counter(row["classification"] for row in files)
    roles = Counter(row["role"] for row in files)
    excluded_roles = Counter(row["role"] for row in excluded_roots)
    languages = Counter(row["language"] for row in files)
    return {
        "schema_version": 1,
        "status": "complete",
        "project_root": str(project),
        "source_roots": [_relative(root, project) or "." for root in resolved_roots],
        "capabilities": {
            "inventory_languages": sorted(profiles),
            "profile_schema_version": PROFILE_SCHEMA_VERSION,
            "unsupported_languages_are_visible": True,
            "analysis": "none",
            "mutation": "none",
        },
        "files": files,
        "excluded_roots": excluded_roots,
        "counts": {
            "files": len(files),
            "excluded_roots": len(excluded_roots),
            "classification": dict(sorted(classification.items())),
            "roles": dict(sorted(roles.items())),
            "excluded_roles": dict(sorted(excluded_roles.items())),
            "languages": dict(sorted(languages.items())),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=DEFAULT_PROFILES_ROOT,
        help="Directory containing strict language profiles",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        action="append",
        default=[],
        help="Contained source root; repeat for multiple roots (default: project root)",
    )
    parser.add_argument("--output", type=Path, help="Contained JSON output path")
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        project = _validate_root(args.project_root, label="project root")
        if args.output is not None:
            output = args.output.resolve(strict=False)
            if not _is_within(output, project):
                raise InventoryError(
                    f"output must stay within project root: {args.output}"
                )
            if args.output.exists() and args.output.is_symlink():
                raise InventoryError(f"output may not be a symbolic link: {args.output}")
        payload = build_inventory(project, args.source_root, args.profiles_root)
        if output is not None:
            inventoried = [project / row["path"] for row in payload["files"]]
            collides = _relative(output, project) in {
                row["path"] for row in payload["files"]
            } or (
                output.exists()
                and any(output.samefile(path) for path in inventoried)
            )
            if collides:
                raise InventoryError(
                    f"output may not replace an inventoried source file: {args.output}"
                )
    except (InventoryError, ProfileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output is not None:
        write_text_atomic(output, rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
