#!/usr/bin/env python3
"""Inventory repository source files and classify roles without analyzing code."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path


SUPPORTED_SUFFIXES = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
}
UNSUPPORTED_SUFFIXES = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
}

EXCLUDED_DIRECTORIES = {
    ".git": "repository_metadata",
    ".hg": "repository_metadata",
    ".svn": "repository_metadata",
    ".venv": "external_dependency",
    "venv": "external_dependency",
    "node_modules": "external_dependency",
    "vendor": "external_dependency",
    "vendored": "external_dependency",
    "dist": "build_output",
    "build": "build_output",
    "coverage": "build_output",
    ".next": "build_output",
    "target": "build_output",
    "__pycache__": "cache",
    ".mypy_cache": "cache",
    ".pytest_cache": "cache",
    ".ruff_cache": "cache",
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


def _language_for(path: Path) -> tuple[str | None, bool]:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return SUPPORTED_SUFFIXES[suffix], True
    if suffix in UNSUPPORTED_SUFFIXES:
        return UNSUPPORTED_SUFFIXES[suffix], False
    return None, False


def _is_test_name(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered.startswith("test_")
        or lowered.endswith("_test.py")
        or any(
            marker in lowered
            for marker in (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
        )
    )


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


def _is_config_name(name: str) -> bool:
    lowered = name.lower()
    return (
        ".config." in lowered
        or lowered
        in {
            "conftest.py",
            "manage.py",
            "settings.py",
            "vite.config.ts",
            "webpack.config.ts",
        }
    )


def _role(path: Path, project_root: Path) -> tuple[str, str, str]:
    relative = path.relative_to(project_root)
    parts = {part.lower() for part in relative.parts[:-1]}
    name = path.name.lower()

    if parts & FIXTURE_DIRECTORIES and not parts & TEST_DIRECTORIES:
        return "unknown", "ambiguous", "fixture_or_product_data"
    if parts & GENERATED_DIRECTORIES or _is_generated_name(name):
        return "generated", "classified", "generated_path_or_name"
    if parts & TEST_DIRECTORIES or _is_test_name(name):
        return "test", "classified", "test_path_or_name"
    if name.endswith(".d.ts") or name.endswith(".pyi"):
        return "declaration", "classified", "declaration_suffix"
    if _is_config_name(name):
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
            reason = EXCLUDED_DIRECTORIES.get(child_name.lower())
            if child.is_symlink():
                reason = "symlink_boundary"
            if reason is not None:
                if relative not in seen_excluded:
                    seen_excluded.add(relative)
                    excluded_roots.append({"path": relative, "reason": reason})
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
                        {"path": relative, "reason": "symlink_boundary"}
                    )
                continue
            language, supported = _language_for(path)
            if language is None:
                continue
            relative = _relative(path, project_root)
            if relative in seen_files:
                continue
            seen_files.add(relative)
            role, classification, reason = _role(path, project_root)
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


def build_inventory(project_root: Path, source_roots: list[Path]) -> dict:
    project = _validate_root(project_root, label="project root")
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
            seen_files=seen_files,
            seen_excluded=seen_excluded,
        )
        files.extend(root_files)
        excluded_roots.extend(root_excluded)

    files.sort(key=lambda row: row["path"])
    excluded_roots.sort(key=lambda row: row["path"])
    classification = Counter(row["classification"] for row in files)
    roles = Counter(row["role"] for row in files)
    languages = Counter(row["language"] for row in files)
    return {
        "schema_version": 1,
        "status": "complete",
        "project_root": str(project),
        "source_roots": [_relative(root, project) or "." for root in resolved_roots],
        "capabilities": {
            "inventory_languages": ["python", "typescript"],
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
            "languages": dict(sorted(languages.items())),
        },
    }


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
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
        payload = build_inventory(project, args.source_root)
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
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output is not None:
        _write_atomic(output, rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
