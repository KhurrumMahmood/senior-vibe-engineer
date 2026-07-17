#!/usr/bin/env python3
"""Build and validate deterministic skill projections for every agent surface.

Structural projection and runtime discovery are deliberately separate.  A clean
projection never implies that a runtime discovered or invoked a skill.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from _lib.capability_registry import CapabilityRegistry, load_registry
from _lib.native_discovery import (
    NativeDiscoveryParseError,
    parse_gemini_skills_list,
    validate_gemini_skills_list_stderr,
)
from _lib.skill_catalog import DEFAULT_INVENTORY_PATH, SkillCatalog, load_catalog


SCHEMA_VERSION = 1
PROJECTION_MODE = "full-discovery"
READY_STATES = frozenset({"foundation-ready", "exemplar-ready"})
SURFACE_LAYOUTS = {
    "augment": (".augment/rules/imported", "SKILL.md"),
    "claude-code": (".claude/skills", "SKILL.md"),
    "codex": ("skills", "SKILL.md"),
    "cursor": (".cursor/rules", "SKILL.mdc"),
    "gemini": (".gemini/skills", "SKILL.md"),
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
VERSIONED_ALIAS_RE = re.compile(r"^(.+)-v([1-9][0-9]*)$")
PUBLIC_CATALOG_PATH = PurePosixPath(".claude/docs/skill-catalog.md")
CONTRACTS_INDEX_PATH = PurePosixPath(".claude/contracts/skills/_index.yaml")
CACHE_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
CACHE_SUFFIXES = frozenset({".pyc", ".pyo"})


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _tree_hash(files: Mapping[str, bytes]) -> str:
    lines = [f"{_sha256_bytes(content)}  {path}\n" for path, content in sorted(files.items())]
    return _sha256_bytes("".join(lines).encode())


def _git_output(project_root: Path, arguments: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        capture_output=True,
        check=True,
    )
    return result.stdout


def _is_cache_artifact(relative: str) -> bool:
    path = PurePosixPath(relative)
    return any(part in CACHE_PARTS for part in path.parts) or path.suffix in CACHE_SUFFIXES


def _git_tree_files(project_root: Path, paths: Sequence[str]) -> dict[str, bytes]:
    """Read regular, non-cache blobs from the exact reviewed HEAD tree."""
    clean_paths = sorted(set(paths))
    if not clean_paths:
        return {}
    output = _git_output(project_root, ["archive", "--format=tar", "HEAD", *clean_paths])
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(output), mode="r:") as archive:
        for member in archive.getmembers():
            relative = member.name.rstrip("/")
            if member.issym() or member.islnk():
                raise ValueError(f"symlinked source is not distributable: {relative}")
            if _is_cache_artifact(relative):
                raise ValueError(f"committed cache artifact is not distributable: {relative}")
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot read reviewed Git blob: {relative}")
            files[relative] = extracted.read()
    return files


def _dirty_tracked_paths(project_root: Path, paths: Sequence[str]) -> list[str]:
    clean_paths = sorted(set(paths))
    if not clean_paths:
        return []
    output = _git_output(
        project_root,
        ["diff", "--name-only", "-z", "HEAD", "--", *clean_paths],
    )
    return sorted(path.decode() for path in output.split(b"\0") if path)


def _require_clean_tracked_sources(project_root: Path, paths: Sequence[str]) -> None:
    dirty = _dirty_tracked_paths(project_root, paths)
    if dirty:
        raise ValueError(f"dirty load-bearing source state: {dirty}")


def _require_exact_worktree_sources(project_root: Path, sources: Sequence[str]) -> None:
    """Reject every live source entry not present in the reviewed HEAD archive."""
    reviewed = set(_git_tree_files(project_root, sources))
    actual: set[str] = set()
    for source in sorted(set(sources)):
        source_root = project_root / source
        if not source_root.is_dir():
            continue
        actual.update(
            path.relative_to(project_root).as_posix()
            for path in source_root.rglob("*")
            if path.is_file() or path.is_symlink()
        )
    extras = sorted(actual - reviewed)
    if extras:
        raise ValueError(f"untracked or ignored load-bearing files: {extras}")
    missing = sorted(reviewed - actual)
    if missing:
        raise ValueError(f"reviewed load-bearing files are absent from the worktree: {missing}")


def _directory_tree_hash(path: Path) -> str:
    if not path.is_dir():
        return _tree_hash({})
    return _tree_hash(
        {
            candidate.relative_to(path).as_posix(): candidate.read_bytes()
            for candidate in sorted(path.rglob("*"))
            if candidate.is_file()
        }
    )


def _path_is_clean(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _row_hash(row: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(dict(row)))


def _bundle_hash(inventory: Mapping[str, Any]) -> str:
    payload = dict(inventory)
    payload.pop("bundle_sha256", None)
    return _sha256_bytes(_canonical_bytes(payload))


def _document_hash(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(dict(value)))


def _reference_paths(
    root: Path,
    registry: CapabilityRegistry,
    catalog_path: Path,
    skill_names: Sequence[str],
) -> list[str]:
    paths = {
        registry.path.resolve().relative_to(root).as_posix(),
        catalog_path.resolve().relative_to(root).as_posix(),
        PUBLIC_CATALOG_PATH.as_posix(),
        CONTRACTS_INDEX_PATH.as_posix(),
        *(f".claude/contracts/skills/{name}.yaml" for name in skill_names),
    }
    return sorted(paths)


def _validate_reference_semantics(
    root: Path, skill_names: Sequence[str], errors: list[str]
) -> None:
    public_catalog = root / PUBLIC_CATALOG_PATH
    if public_catalog.is_file():
        text = public_catalog.read_text(encoding="utf-8")
        for name in skill_names:
            if f"/{name}" not in text:
                errors.append(f"public catalog has no invocation entry for {name!r}")

    contract_names: set[str] = set()
    for name in skill_names:
        path = root / f".claude/contracts/skills/{name}.yaml"
        if not path.is_file():
            continue
        try:
            contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"skill contract {path.relative_to(root)} is invalid YAML: {exc}")
            continue
        if not isinstance(contract, dict) or contract.get("skill") != name:
            errors.append(f"skill contract for {name!r} does not declare the same skill")
        else:
            contract_names.add(name)

    index_path = root / CONTRACTS_INDEX_PATH
    if index_path.is_file():
        try:
            index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"contracts index is invalid YAML: {exc}")
        else:
            rows = index.get("skills") if isinstance(index, dict) else None
            if not isinstance(rows, list):
                errors.append("contracts index skills must be a list")
                rows = []
            invalid_rows = [
                position
                for position, row in enumerate(rows)
                if not isinstance(row, dict) or not isinstance(row.get("skill"), str)
            ]
            if invalid_rows:
                errors.append(f"contracts index has invalid skill rows: {invalid_rows}")
            indexed_name_rows = [
                row["skill"]
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("skill"), str)
            ]
            duplicates = sorted(
                name for name, count in Counter(indexed_name_rows).items() if count > 1
            )
            if duplicates:
                errors.append(f"contracts index has duplicate skill rows: {duplicates}")
            indexed_names = set(indexed_name_rows)
            reviewed_skill_files = _git_tree_files(root, [".claude/skills"])
            allowed_index_names = {
                path.parts[2]
                for relative in reviewed_skill_files
                if len((path := PurePosixPath(relative)).parts) == 4
                and path.parts[:2] == (".claude", "skills")
                and path.parts[2] != "_common"
                and path.name == "SKILL.md"
            }
            unknown = sorted(indexed_names - allowed_index_names)
            if unknown:
                errors.append(f"contracts index has unknown skill rows: {unknown}")
            missing = sorted(allowed_index_names - indexed_names)
            if missing:
                errors.append(f"contracts index omits canonical skills: {missing}")
            declared_count = index.get("skill_count") if isinstance(index, dict) else None
            if (
                not isinstance(declared_count, int)
                or isinstance(declared_count, bool)
                or declared_count != len(rows)
            ):
                errors.append("contracts index skill_count differs from row count")
    if contract_names != set(skill_names):
        missing = sorted(set(skill_names) - contract_names)
        if missing:
            errors.append(f"skill contracts are missing or invalid for: {missing}")


def _source_file_sets(
    project_root: Path, sources: Sequence[str]
) -> dict[str, dict[str, bytes]]:
    source_list = sorted(set(sources))
    all_files = _git_tree_files(project_root, source_list)
    return {
        source: {
            relative.removeprefix(f"{source}/"): content
            for relative, content in all_files.items()
            if relative.startswith(f"{source}/")
        }
        for source in source_list
    }


def _load_catalog_from_git(
    project_root: Path,
    catalog_path: Path,
    registry: CapabilityRegistry,
) -> SkillCatalog:
    catalog_relative = catalog_path.resolve().relative_to(project_root).as_posix()
    files = _git_tree_files(project_root, [".claude/skills", catalog_relative])
    with tempfile.TemporaryDirectory(prefix="distribution-catalog-") as raw_temp:
        fixture = Path(raw_temp)
        for relative, content in files.items():
            target = fixture / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return load_catalog(
            fixture / catalog_relative,
            skills_dir=fixture / ".claude/skills",
            project_root=fixture,
            registry=registry,
        )


def build_bundle_inventory(
    project_root: Path,
    *,
    aliases: Sequence[Mapping[str, Any]] = (),
    catalog_path: Path | None = None,
    registry: CapabilityRegistry | None = None,
) -> dict[str, Any]:
    """Inventory all distribution-ready skills and their complete resource trees."""
    root = project_root.resolve()
    selected_registry = registry or load_registry(
        root / ".claude/skills/_common/capability-registry.yml"
    )
    default_catalog = root / DEFAULT_INVENTORY_PATH.relative_to(
        DEFAULT_INVENTORY_PATH.parents[3]
    )
    selected_catalog = (catalog_path or default_catalog).resolve()
    initial_paths = [
        selected_registry.path.resolve().relative_to(root).as_posix(),
        selected_catalog.relative_to(root).as_posix(),
        ".claude/skills",
    ]
    _require_clean_tracked_sources(root, initial_paths)
    catalog = _load_catalog_from_git(root, selected_catalog, selected_registry)
    skills: list[dict[str, Any]] = []
    ready_entries = [entry for entry in catalog.entries if entry.readiness in READY_STATES]
    ready_sources = [(root / entry.path).parent.relative_to(root).as_posix() for entry in ready_entries]
    _require_exact_worktree_sources(root, ready_sources)
    source_file_sets = _source_file_sets(root, ready_sources)
    for entry, source in zip(ready_entries, ready_sources, strict=True):
        source_files = source_file_sets[source]
        files = [
            {
                "path": relative,
                "sha256": _sha256_bytes(content),
            }
            for relative, content in sorted(source_files.items())
        ]
        skills.append(
            {
                "name": entry.name,
                "source": source,
                "files": files,
                "catalog_link": {
                    "inventory": selected_catalog.relative_to(root).as_posix(),
                    "row_sha256": _row_hash(entry.raw),
                },
            }
        )
    reference_paths = _reference_paths(
        root, selected_registry, selected_catalog, [skill["name"] for skill in skills]
    )
    load_bearing = [*reference_paths, *(skill["source"] for skill in skills)]
    _require_clean_tracked_sources(root, load_bearing)
    git_files = _git_tree_files(root, load_bearing)
    missing_references = sorted(set(reference_paths) - set(git_files))
    if missing_references:
        raise ValueError(f"load-bearing references are not tracked at HEAD: {missing_references}")
    inventory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_revision": _git_revision(root),
        "source_tree": _git_tree(root),
        "registry_version": selected_registry.schema_version,
        "registry_contract_version": selected_registry.contract_version,
        "registry_sha256": _sha256_bytes(
            git_files[selected_registry.path.resolve().relative_to(root).as_posix()]
        ),
        "catalog_sha256": _sha256_bytes(
            git_files[selected_catalog.relative_to(root).as_posix()]
        ),
        "skills": skills,
        "aliases": [dict(alias) for alias in aliases],
    }
    inventory["reference_files"] = [
        {"path": relative, "sha256": _sha256_bytes(git_files[relative])}
        for relative in reference_paths
    ]
    inventory["bundle_sha256"] = _bundle_hash(inventory)
    errors = validate_bundle_inventory(inventory, root, registry=selected_registry)
    if errors:
        raise ValueError("\n".join(errors))
    return inventory


def _alias_targets(
    inventory: Mapping[str, Any], errors: list[str]
) -> dict[str, str]:
    # spec:portable-skill-layer-distribution::IM-12
    canonical = {
        skill.get("name")
        for skill in inventory.get("skills", [])
        if isinstance(skill, dict) and isinstance(skill.get("name"), str)
    }
    aliases: dict[str, str] = {}
    for index, alias in enumerate(inventory.get("aliases", [])):
        if not isinstance(alias, dict):
            errors.append(f"aliases[{index}] must be a mapping")
            continue
        if set(alias) != {"name", "target", "version"}:
            errors.append(f"aliases[{index}] must contain exactly name, target, and version")
            continue
        name, target, version = alias["name"], alias["target"], alias["version"]
        match = VERSIONED_ALIAS_RE.fullmatch(name) if isinstance(name, str) else None
        if (
            not isinstance(name, str)
            or not NAME_RE.fullmatch(name)
            or not match
            or not isinstance(version, int)
            or isinstance(version, bool)
            or int(match.group(2)) != version
        ):
            errors.append(
                f"alias {name!r} must be a safe public invocation ending in -v<version>"
            )
            continue
        if name in canonical or name in aliases:
            errors.append(f"alias collision: {name!r}")
            continue
        if not isinstance(target, str):
            errors.append(f"alias {name!r} target must be a string")
            continue
        aliases[name] = target

    known = canonical | set(aliases)
    for name, target in aliases.items():
        if target not in known:
            errors.append(f"alias {name!r} has stale target {target!r}")
            continue
        seen = {name}
        cursor = target
        while cursor in aliases:
            if cursor in seen:
                errors.append(f"alias cycle includes {name!r}")
                break
            seen.add(cursor)
            cursor = aliases[cursor]
    return aliases


def validate_bundle_inventory(
    inventory: Mapping[str, Any],
    project_root: Path,
    *,
    registry: CapabilityRegistry | None = None,
) -> list[str]:
    """Validate source, catalog, registry, resource, hash, and alias contracts."""
    errors: list[str] = []
    root = project_root.resolve()
    selected_registry = registry or load_registry(
        root / ".claude/skills/_common/capability-registry.yml"
    )
    expected_top = {
        "schema_version", "source_revision", "source_tree", "registry_version", "registry_contract_version",
        "registry_sha256", "catalog_sha256", "reference_files", "skills", "aliases",
        "bundle_sha256",
    }
    if set(inventory) != expected_top:
        errors.append(f"bundle inventory fields differ: {sorted(set(inventory) ^ expected_top)}")
    if inventory.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if inventory.get("registry_version") != selected_registry.schema_version:
        errors.append("registry version differs from the canonical registry")
    if inventory.get("registry_contract_version") != selected_registry.contract_version:
        errors.append("registry contract version differs from the canonical registry")
    if inventory.get("source_revision") != _git_revision(root):
        errors.append("bundle source revision differs from the reviewed Git revision")
    if inventory.get("source_tree") != _git_tree(root):
        errors.append("bundle source tree differs from the reviewed Git tree")
    if inventory.get("bundle_sha256") != _bundle_hash(inventory):
        errors.append("bundle hash differs from canonical inventory content")
    skills = inventory.get("skills")
    if not isinstance(skills, list) or not skills:
        errors.append("skills must be a non-empty list")
        return errors
    names: list[str] = []
    catalog_paths: set[str] = set()
    source_paths: list[str] = []
    candidate_sources = [
        skill.get("source")
        for skill in skills
        if isinstance(skill, dict) and _path_is_clean(skill.get("source"))
    ]
    source_file_sets = _source_file_sets(root, candidate_sources)
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict) or set(skill) != {"name", "source", "files", "catalog_link"}:
            errors.append(f"skills[{index}] has invalid fields")
            continue
        name = skill["name"]
        source = skill["source"]
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"skills[{index}].name is invalid: {name!r}")
            continue
        names.append(name)
        if not _path_is_clean(source) or PurePosixPath(source).name != name:
            errors.append(f"skill {name!r} source path is invalid: {source!r}")
            continue
        source_paths.append(source)
        git_source_files = source_file_sets.get(source, {})
        if "SKILL.md" not in git_source_files:
            errors.append(f"skill {name!r} source is stale: {source!r}")
            continue
        file_rows = skill["files"]
        if not isinstance(file_rows, list) or not file_rows:
            errors.append(f"skill {name!r} files must be non-empty")
            continue
        paths: list[str] = []
        for file_row in file_rows:
            if not isinstance(file_row, dict) or set(file_row) != {"path", "sha256"}:
                errors.append(f"skill {name!r} has invalid file record")
                continue
            relative, expected_hash = file_row["path"], file_row["sha256"]
            if not _path_is_clean(relative):
                errors.append(f"skill {name!r} has path traversal or invalid path: {relative!r}")
                continue
            paths.append(relative)
            if not isinstance(expected_hash, str) or not HASH_RE.fullmatch(expected_hash):
                errors.append(f"skill {name!r} has invalid hash for {relative!r}")
                continue
            content = git_source_files.get(relative)
            if content is None:
                errors.append(f"skill {name!r} has stale reference {relative!r}")
            elif _sha256_bytes(content) != expected_hash:
                errors.append(f"skill {name!r} source hash differs for {relative!r}")
        actual = sorted(git_source_files)
        if paths != sorted(paths) or paths != actual:
            errors.append(f"skill {name!r} resource inventory is incomplete, stale, or unsorted")
        link = skill["catalog_link"]
        if not isinstance(link, dict) or set(link) != {"inventory", "row_sha256"}:
            errors.append(f"skill {name!r} has invalid catalog link")
        elif not _path_is_clean(link["inventory"]):
            errors.append(f"skill {name!r} catalog link is not a clean path")
        else:
            catalog_paths.add(link["inventory"])
    if names != sorted(names):
        errors.append("skills must be sorted by canonical invocation name")
    if len(names) != len(set(names)):
        errors.append("canonical invocation names collide")
    if len(catalog_paths) == 1:
        catalog_path = root / next(iter(catalog_paths))
        catalog_relative = catalog_path.relative_to(root).as_posix()
        catalog_blob = _git_tree_files(root, [catalog_relative]).get(catalog_relative)
        if catalog_blob is None or _sha256_bytes(catalog_blob) != inventory.get("catalog_sha256"):
            errors.append("catalog link or catalog hash is stale")
        else:
            catalog = _load_catalog_from_git(root, catalog_path, selected_registry)
            rows = catalog.entries_by_name
            expected_ready_names = sorted(
                entry.name for entry in catalog.entries if entry.readiness in READY_STATES
            )
            if names != expected_ready_names:
                errors.append(
                    "bundle skill names differ from the catalog distribution-ready set"
                )
            for skill in skills:
                if not isinstance(skill, dict) or skill.get("name") not in rows:
                    continue
                catalog_entry = rows[skill["name"]]
                if skill["source"] != PurePosixPath(catalog_entry.path).parent.as_posix():
                    errors.append(f"skill {skill['name']!r} source differs from its catalog path")
                if skill["catalog_link"].get("row_sha256") != _row_hash(catalog_entry.raw):
                    errors.append(f"skill {skill['name']!r} catalog row link is stale")
    else:
        errors.append("all skills must link one canonical catalog inventory")

    reference_rows = inventory.get("reference_files")
    declared_references: dict[str, str] = {}
    if not isinstance(reference_rows, list):
        errors.append("reference_files must be a list")
    else:
        reference_paths: list[str] = []
        candidate_reference_paths = [
            row.get("path")
            for row in reference_rows
            if isinstance(row, dict) and _path_is_clean(row.get("path"))
        ]
        reference_git_files = _git_tree_files(root, candidate_reference_paths)
        for index, row in enumerate(reference_rows):
            if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
                errors.append(f"reference_files[{index}] must contain exactly path and sha256")
                continue
            relative, expected_hash = row["path"], row["sha256"]
            if not _path_is_clean(relative):
                errors.append(f"reference_files[{index}] has an invalid relative path")
                continue
            reference_paths.append(relative)
            if not isinstance(expected_hash, str) or not HASH_RE.fullmatch(expected_hash):
                errors.append(f"reference_files[{index}] has an invalid hash")
                continue
            content = reference_git_files.get(relative)
            if content is None:
                errors.append(f"reference file is missing: {relative}")
            elif _sha256_bytes(content) != expected_hash:
                errors.append(f"reference hash differs for {relative}")
            declared_references[relative] = expected_hash
        duplicates = sorted(
            path for path, count in Counter(reference_paths).items() if count > 1
        )
        if duplicates:
            errors.append(f"duplicate reference paths: {duplicates}")
        if reference_paths != sorted(reference_paths):
            errors.append("reference_files must be sorted by path")
        if len(catalog_paths) == 1:
            expected_references = _reference_paths(
                root,
                selected_registry,
                root / next(iter(catalog_paths)),
                names,
            )
            if set(declared_references) != set(expected_references):
                errors.append("reference_files differ from the load-bearing reference set")
    load_bearing = [*declared_references, *source_paths]
    try:
        dirty = _dirty_tracked_paths(root, load_bearing)
    except subprocess.SubprocessError as exc:
        errors.append(f"cannot inspect reviewed Git source tree: {exc}")
    else:
        if dirty:
            errors.append(f"dirty load-bearing source state: {dirty}")
    try:
        _require_exact_worktree_sources(root, source_paths)
    except ValueError as exc:
        errors.append(str(exc))
    registry_relative = selected_registry.path.resolve().relative_to(root).as_posix()
    registry_blob = _git_tree_files(root, [registry_relative]).get(registry_relative)
    if registry_blob is None or _sha256_bytes(registry_blob) != inventory.get("registry_sha256"):
        errors.append("registry hash differs from the reviewed Git tree")
    _validate_reference_semantics(root, names, errors)
    _alias_targets(inventory, errors)
    return errors


def _resolved_aliases(inventory: Mapping[str, Any]) -> dict[str, str]:
    aliases = {alias["name"]: alias["target"] for alias in inventory["aliases"]}
    result: dict[str, str] = {}
    for name, target in aliases.items():
        while target in aliases:
            target = aliases[target]
        result[name] = target
    return result


def _alias_skill(content: bytes, canonical: str, alias: str) -> bytes:
    text = content.decode("utf-8")
    replaced, count = re.subn(
        rf"(?m)^name:\s*{re.escape(canonical)}\s*$", f"name: {alias}", text, count=1
    )
    if count != 1:
        raise ValueError(f"canonical skill {canonical!r} has no exact frontmatter name")
    return replaced.encode()


def _expected_projection_files(
    inventory: Mapping[str, Any], project_root: Path, registry: CapabilityRegistry
) -> dict[str, dict[str, bytes]]:
    root = project_root.resolve()
    skills = {skill["name"]: skill for skill in inventory["skills"]}
    invocations = {name: name for name in skills} | _resolved_aliases(inventory)
    source_contents = _source_file_sets(
        root, [skill["source"] for skill in skills.values()]
    )
    projected: dict[str, dict[str, bytes]] = {surface: {} for surface in SURFACE_LAYOUTS}
    for surface, (prefix, primary_name) in SURFACE_LAYOUTS.items():
        origins: dict[str, str] = {}
        for invocation, canonical in sorted(invocations.items()):
            skill = skills[canonical]
            source_files = source_contents[skill["source"]]
            for file_row in skill["files"]:
                relative = file_row["path"]
                destination_name = primary_name if relative == "SKILL.md" else relative
                destination = f"{surface}/{prefix}/{invocation}/{destination_name}"
                origin = f"{skill['source']}/{relative}"
                if destination in projected[surface]:
                    raise ValueError(
                        f"{surface}: projection target collision at {destination!r} "
                        f"between {origins[destination]!r} and {origin!r}"
                    )
                content = source_files[relative]
                if invocation != canonical and relative == "SKILL.md":
                    content = _alias_skill(content, canonical, invocation)
                projected[surface][destination] = content
                origins[destination] = origin
    codex_manifest = {
        "name": "engineering-skills",
        "version": "1.0.0",
        "description": "Deterministic projection of the portable engineering skill bundle.",
        "author": {"name": "engineering-skills"},
        "license": "MIT",
        "skills": "./skills/",
        "interface": {
            "displayName": "Engineering Skills",
            "shortDescription": "Portable senior-engineering procedures.",
            "longDescription": "Canonical skill procedures projected from one content-addressed bundle inventory.",
            "developerName": "engineering-skills",
            "category": "Developer Tools",
            "capabilities": ["Read"],
            "defaultPrompt": ["Use the matching engineering skill when its trigger contract applies."],
        },
    }
    codex_manifest_path = "codex/.codex-plugin/plugin.json"
    if codex_manifest_path in projected["codex"]:
        raise ValueError(f"codex: projection target collision at {codex_manifest_path!r}")
    projected["codex"][codex_manifest_path] = (
        json.dumps(codex_manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    expected = registry.identifiers("agent_surfaces")
    if set(projected) != set(expected):
        raise ValueError(
            f"surface projection mismatch: handlers={sorted(projected)}, registry={sorted(expected)}"
        )
    return projected


def build_projections(
    inventory: Mapping[str, Any],
    project_root: Path,
    output_root: Path,
    *,
    registry: CapabilityRegistry | None = None,
) -> dict[str, Any]:
    """Project one validated bundle inventory into all registered surfaces."""
    # spec:portable-skill-layer-distribution::IM-10
    selected_registry = registry or load_registry(
        project_root.resolve() / ".claude/skills/_common/capability-registry.yml"
    )
    errors = validate_bundle_inventory(inventory, project_root, registry=selected_registry)
    if errors:
        raise ValueError("\n".join(errors))
    output = output_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output_root must be absent or empty")
    expected = _expected_projection_files(inventory, project_root, selected_registry)
    for surface_files in expected.values():
        for relative, content in surface_files.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    surface_manifest = {
        surface: {
            "discovery": selected_registry.data["agent_surfaces"][surface]["discovery"],
            "minimum_surface_version": str(
                selected_registry.data["agent_surfaces"][surface]["minimum_surface_version"]
            ),
            "files": [
                {"path": path, "sha256": _sha256_bytes(content)}
                for path, content in sorted(files.items())
            ],
        }
        for surface, files in sorted(expected.items())
    }
    all_files = {path: content for files in expected.values() for path, content in files.items()}
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_revision": inventory["source_revision"],
        "source_tree": inventory["source_tree"],
        "projection_mode": PROJECTION_MODE,
        "registry_version": selected_registry.schema_version,
        "registry_sha256": inventory["registry_sha256"],
        "bundle_sha256": inventory["bundle_sha256"],
        "projection_sha256": _tree_hash(all_files),
        "surfaces": surface_manifest,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "projection-manifest.json").write_bytes(_canonical_bytes(manifest))
    return manifest


def validate_projections(
    inventory: Mapping[str, Any],
    project_root: Path,
    output_root: Path,
    manifest: Mapping[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
) -> list[str]:
    """Validate structural projections only; never return runtime support claims."""
    selected_registry = registry or load_registry(
        project_root.resolve() / ".claude/skills/_common/capability-registry.yml"
    )
    errors = validate_bundle_inventory(inventory, project_root, registry=selected_registry)
    if errors:
        return errors
    expected = _expected_projection_files(inventory, project_root, selected_registry)
    expected_surfaces = set(selected_registry.identifiers("agent_surfaces"))
    surfaces = manifest.get("surfaces", {})
    expected_manifest_fields = {
        "schema_version", "source_revision", "source_tree", "projection_mode", "registry_version", "registry_sha256",
        "bundle_sha256", "projection_sha256", "surfaces",
    }
    if set(manifest) != expected_manifest_fields:
        errors.append("projection manifest fields differ from the structural contract")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("projection schema version differs from the structural contract")
    if manifest.get("source_revision") != inventory.get("source_revision"):
        errors.append("projection source revision differs from the bundle")
    if manifest.get("source_tree") != inventory.get("source_tree"):
        errors.append("projection source tree differs from the bundle")
    if manifest.get("projection_mode") != PROJECTION_MODE:
        errors.append("projection mode must be the explicit full-discovery portfolio")
    if manifest.get("registry_version") != selected_registry.schema_version:
        errors.append("projection registry version differs from the canonical registry")
    if not isinstance(surfaces, dict) or set(surfaces) != expected_surfaces:
        errors.append("projection manifest does not cover every supported surface")
        return errors
    actual_files: dict[str, bytes] = {}
    for surface, surface_files in expected.items():
        contract = selected_registry.data["agent_surfaces"][surface]
        expected_surface_fields = {"discovery", "minimum_surface_version", "files"}
        surface_manifest = surfaces[surface]
        if not isinstance(surface_manifest, dict):
            errors.append(f"{surface}: manifest must be a mapping")
            continue
        if set(surface_manifest) != expected_surface_fields:
            errors.append(f"{surface}: manifest fields differ from the surface contract")
        if surface_manifest.get("discovery") != contract["discovery"]:
            errors.append(f"{surface}: discovery contract differs from the registry")
        if surface_manifest.get("minimum_surface_version") != str(
            contract["minimum_surface_version"]
        ):
            errors.append(f"{surface}: minimum surface version differs from the registry")
        declared = surface_manifest.get("files", [])
        declared_paths = [
            row.get("path") for row in declared if isinstance(row, dict)
        ]
        duplicate_targets = sorted(
            path
            for path, count in Counter(declared_paths).items()
            if isinstance(path, str) and count > 1
        )
        if duplicate_targets:
            errors.append(f"{surface}: duplicate manifest targets: {duplicate_targets}")
        declared_map = {
            row.get("path"): row.get("sha256") for row in declared if isinstance(row, dict)
        }
        expected_hashes = {path: _sha256_bytes(content) for path, content in surface_files.items()}
        if declared_map != expected_hashes:
            errors.append(f"{surface}: declared locations or hashes diverge")
        for relative, expected_content in surface_files.items():
            path = output_root / relative
            if not path.is_file():
                errors.append(f"{surface}: missing projected file {relative}")
                continue
            content = path.read_bytes()
            actual_files[relative] = content
            if content != expected_content:
                errors.append(f"{surface}: divergent duplicate content at {relative}")
        actual_surface_paths = {
            path.relative_to(output_root).as_posix()
            for path in (output_root / surface).rglob("*")
            if path.is_file()
        }
        if actual_surface_paths != set(surface_files):
            errors.append(f"{surface}: undeclared, duplicate, or missing projection paths")
    expected_hash = _tree_hash({path: content for files in expected.values() for path, content in files.items()})
    if manifest.get("projection_sha256") != expected_hash:
        errors.append("projection hash differs from expected surface content")
    if actual_files and _tree_hash(actual_files) != expected_hash:
        errors.append("on-disk projection hash differs from canonical projection")
    if manifest.get("bundle_sha256") != inventory.get("bundle_sha256"):
        errors.append("projection is bound to a stale bundle")
    if manifest.get("registry_sha256") != inventory.get("registry_sha256"):
        errors.append("projection is bound to a stale registry")
    manifest_path = output_root / "projection-manifest.json"
    if not manifest_path.is_file() or manifest_path.read_bytes() != _canonical_bytes(dict(manifest)):
        errors.append("projection manifest file differs from supplied manifest")
    return errors


def _run(
    command: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)


def _command_record(
    command: Sequence[str],
    cwd: Path,
    result: subprocess.CompletedProcess[bytes],
    *,
    bind_cwd: bool = False,
) -> dict[str, Any]:
    raw = result.stdout + result.stderr
    record = {
        "argv": list(command),
        "cwd": str(cwd.resolve()),
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "output_sha256": _sha256_bytes(raw),
    }
    if bind_cwd:
        record["cwd_sha256"] = _directory_tree_hash(cwd)
    return record


def _git_revision(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _git_tree(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _platform_record() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }


def _reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _prepare_claude_marketplace(
    projection_root: Path, runtime_home: Path
) -> tuple[Path, Path, dict[str, str]]:
    workspace = runtime_home / "claude-code-runtime"
    _reset_directory(workspace)
    marketplace = workspace / "marketplace"
    plugin = marketplace / "plugins" / "engineering-skills"
    (plugin / ".claude-plugin").mkdir(parents=True)
    shutil.copytree(projection_root / ".claude" / "skills", plugin / "skills")
    plugin_manifest = {
        "name": "engineering-skills",
        "version": "1.0.0",
        "description": "Full-discovery projection of portable engineering skills.",
        "author": {"name": "engineering-skills"},
        "license": "MIT",
    }
    (plugin / ".claude-plugin" / "plugin.json").write_bytes(
        _canonical_bytes(plugin_manifest)
    )
    marketplace_manifest = {
        "name": "engineering-skills-local",
        "description": "Isolated local discovery fixture.",
        "owner": {"name": "engineering-skills"},
        "plugins": [
            {
                "name": "engineering-skills",
                "source": "./plugins/engineering-skills",
                "description": "Full-discovery projection of portable engineering skills.",
            }
        ],
    }
    manifest_dir = marketplace / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "marketplace.json").write_bytes(_canonical_bytes(marketplace_manifest))
    home = workspace / "home"
    home.mkdir()
    env = dict(os.environ)
    env["HOME"] = str(home)
    return workspace, marketplace, env


def _prepare_codex_marketplace(
    projection_root: Path, runtime_home: Path
) -> tuple[Path, Path, dict[str, str]]:
    workspace = runtime_home / "codex-runtime"
    _reset_directory(workspace)
    marketplace = workspace / "marketplace"
    plugin = marketplace / "plugins" / "engineering-skills"
    shutil.copytree(projection_root, plugin)
    marketplace_manifest = {
        "name": "engineering-skills-local",
        "interface": {"displayName": "Engineering Skills Local"},
        "plugins": [
            {
                "name": "engineering-skills",
                "source": {"source": "local", "path": "./plugins/engineering-skills"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                "category": "Developer Tools",
            }
        ],
    }
    manifest_dir = marketplace / ".agents" / "plugins"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "marketplace.json").write_bytes(_canonical_bytes(marketplace_manifest))
    home = workspace / "home"
    codex_home = workspace / "codex-home"
    project = workspace / "project"
    home.mkdir()
    codex_home.mkdir()
    project.mkdir()
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    return project, marketplace, env


def _claude_detail_names(output: str) -> set[str]:
    match = re.search(r"(?m)^\s*Skills \([0-9]+\)\s+(.+)$", output)
    if not match:
        return set()
    return {name.strip() for name in match.group(1).split(",") if name.strip()}


def _nested_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _nested_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _nested_strings(item)]
    return []


def _codex_prompt_names(output: str) -> set[str]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return set()
    names: set[str] = set()
    for text in _nested_strings(payload):
        names.update(
            re.findall(
                r"(?m)^- engineering-skills:([a-z0-9]+(?:-[a-z0-9]+)*):",
                text,
            )
        )
    return names


def collect_runtime_evidence(
    inventory: Mapping[str, Any],
    project_root: Path,
    output_root: Path,
    manifest: Mapping[str, Any],
    runtime_home: Path,
    *,
    registry: CapabilityRegistry | None = None,
    executable_lookup: Callable[[str], str | None] = shutil.which,
    runner: Callable[[Sequence[str], Path, Mapping[str, str] | None], subprocess.CompletedProcess[bytes]] = _run,
) -> dict[str, Any]:
    """Collect runtime-only discovery records, including typed non-success states."""
    selected_registry = registry or load_registry(
        project_root.resolve() / ".claude/skills/_common/capability-registry.yml"
    )
    structural_errors = validate_projections(
        inventory, project_root, output_root, manifest, registry=selected_registry
    )
    source_files = _git_tree_files(
        project_root.resolve(), [skill["source"] for skill in inventory["skills"]]
    )
    isolated_root = runtime_home.resolve()
    common = {
        "registry_version": selected_registry.schema_version,
        "registry_contract_version": selected_registry.contract_version,
        "registry_sha256": inventory["registry_sha256"],
        "source_revision": _git_revision(project_root),
        "source_tree": _git_tree(project_root),
        "source_sha256": _tree_hash(source_files),
        "bundle_sha256": inventory["bundle_sha256"],
        "inventory_sha256": _document_hash(inventory),
        "manifest_sha256": _document_hash(manifest),
        "projection_sha256": manifest["projection_sha256"],
        "projection_mode": manifest["projection_mode"],
        "platform": _platform_record(),
        "runtime_root": str(isolated_root),
        "structural_validation": {
            "result": "pass" if not structural_errors else "fail",
            "errors": structural_errors,
            "satisfies_runtime_discovery": False,
        },
    }
    records: dict[str, Any] = {}
    for surface in sorted(selected_registry.identifiers("agent_surfaces")):
        root = output_root / surface
        fixture_files = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        contract = selected_registry.data["agent_surfaces"][surface]
        record: dict[str, Any] = {
            **common,
            "surface": surface,
            "surface_contract_version": str(contract["minimum_surface_version"]),
            "discovery_contract": contract["discovery"],
            "fixture_sha256": _tree_hash(fixture_files),
            "projection_path": str(root.resolve()),
            "projection_mode": manifest["projection_mode"],
            "status": "unavailable",
            "reason": "runtime executable is unavailable",
            "version_probe": None,
            "setup_probes": [],
            "discovery_probe": None,
            "discovery_probes": [],
        }
        executable_name = {
            "augment": "auggie",
            "claude-code": "claude",
        }.get(surface, surface)
        executable = executable_lookup(executable_name)
        if executable is None:
            records[surface] = record
            continue
        version_command = [executable, "--version"]
        version_result = runner(version_command, root, None)
        record["version_probe"] = _command_record(
            version_command, root, version_result, bind_cwd=True
        )
        expected_version = _expected_runtime_version(surface, selected_registry)
        observed_version = (version_result.stdout + version_result.stderr).decode(
            "utf-8", errors="replace"
        )
        exact_version = True
        if expected_version:
            exact_version = (
                observed_version.strip() == expected_version
                if surface == "gemini"
                else re.search(
                    rf"(?<![0-9.]){re.escape(expected_version)}(?![0-9.])",
                    observed_version,
                )
                is not None
            )
        if version_result.returncode != 0 or not exact_version:
            record["status"] = "unsupported"
            record["reason"] = f"runtime version does not match pinned {expected_version}"
            records[surface] = record
            continue

        invocation_names = sorted(
            [skill["name"] for skill in inventory["skills"]]
            + list(_resolved_aliases(inventory))
        )
        if surface == "claude-code":
            workspace, marketplace, env = _prepare_claude_marketplace(
                root, runtime_home
            )
            setup_commands = [
                [executable, "plugin", "validate", str(marketplace)],
                [executable, "plugin", "marketplace", "add", str(marketplace)],
                [
                    executable,
                    "plugin",
                    "install",
                    "engineering-skills@engineering-skills-local",
                ],
                [executable, "plugin", "list", "--json"],
            ]
            setup_failed = False
            for command in setup_commands:
                result = runner(command, workspace, env)
                record["setup_probes"].append(_command_record(command, workspace, result))
                if result.returncode != 0:
                    setup_failed = True
                    break
            if setup_failed:
                record["status"] = "unsupported"
                record["reason"] = "isolated local Claude plugin setup failed"
                records[surface] = record
                continue
            command = [
                executable,
                "plugin",
                "details",
                "engineering-skills@engineering-skills-local",
            ]
            result = runner(command, workspace, env)
            probe = _command_record(command, workspace, result, bind_cwd=True)
            record["discovery_probe"] = probe
            record["discovery_probes"] = [probe]
            observed = _claude_detail_names(
                result.stdout.decode("utf-8", errors="replace")
            )
            if result.returncode == 0 and observed == set(invocation_names) and not structural_errors:
                record["status"] = "verified"
                record["reason"] = "Claude plugin details listed the exact full-discovery skill set"
            elif structural_errors:
                record["status"] = "unsupported"
                record["reason"] = "structural validation failed; runtime proof is inadmissible"
            else:
                record["status"] = "unsupported"
                record["reason"] = "Claude plugin details differed from the full-discovery skill set"
            records[surface] = record
            continue

        if surface == "codex":
            project, marketplace, env = _prepare_codex_marketplace(root, runtime_home)
            setup_commands = [
                [
                    executable,
                    "plugin",
                    "marketplace",
                    "add",
                    str(marketplace),
                    "--json",
                ],
                [
                    executable,
                    "plugin",
                    "add",
                    "engineering-skills@engineering-skills-local",
                    "--json",
                ],
                [executable, "plugin", "list"],
            ]
            setup_failed = False
            for command in setup_commands:
                result = runner(command, project, env)
                record["setup_probes"].append(_command_record(command, project, result))
                if result.returncode != 0:
                    setup_failed = True
                    break
            auth_output = "".join(
                probe["stdout"] for probe in record["setup_probes"]
            )
            if setup_failed or '"authPolicy": "ON_USE"' not in auth_output:
                record["status"] = "unsupported"
                record["reason"] = "isolated local Codex plugin setup or ON_USE policy failed"
                records[surface] = record
                continue
            command = [executable, "-C", str(project), "debug", "prompt-input", "probe"]
            result = runner(command, project, env)
            probe = _command_record(command, project, result, bind_cwd=True)
            record["discovery_probe"] = probe
            record["discovery_probes"] = [probe]
            observed = _codex_prompt_names(
                result.stdout.decode("utf-8", errors="replace")
            )
            if result.returncode == 0 and observed == set(invocation_names) and not structural_errors:
                record["status"] = "verified"
                record["reason"] = "Codex prompt-input listed the exact namespaced full-discovery skill set"
            elif structural_errors:
                record["status"] = "unsupported"
                record["reason"] = "structural validation failed; runtime proof is inadmissible"
            else:
                record["status"] = "unsupported"
                record["reason"] = "Codex prompt-input differed from the full-discovery skill set"
            records[surface] = record
            continue

        if surface not in {"augment", "gemini"}:
            record["status"] = "unsupported"
            record["reason"] = "no non-model isolated command proves project skill discovery"
            records[surface] = record
            continue
        home = runtime_home / surface
        env = dict(os.environ)
        env["HOME"] = str(home)
        if surface == "augment":
            home.mkdir(parents=True, exist_ok=True)
            env["AUGMENT_DISABLE_AUTO_UPDATE"] = "1"
            command = [executable, "rules", "list"]
            missing: list[str] = []
            for name in invocation_names:
                fixture = runtime_home / "augment-fixtures" / name
                source = root / ".augment" / "rules" / "imported" / name
                fixture_rule = fixture / ".augment" / "rules" / "imported" / name
                fixture_files: dict[str, bytes] = {}
                for source_file in sorted(source.rglob("*")):
                    if not source_file.is_file():
                        continue
                    relative = source_file.relative_to(source).as_posix()
                    content = source_file.read_bytes()
                    fixture_files[f".augment/rules/imported/{name}/{relative}"] = content
                    target = fixture_rule / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                discovery_result = runner(command, fixture, env)
                probe = _command_record(command, fixture, discovery_result, bind_cwd=True)
                probe["invocation"] = name
                probe["fixture_sha256"] = _tree_hash(fixture_files)
                record["discovery_probes"].append(probe)
                output = discovery_result.stdout.decode("utf-8", errors="replace")
                if discovery_result.returncode != 0 or name not in output:
                    missing.append(name)
            if not missing and not structural_errors:
                record["status"] = "verified"
                record["reason"] = (
                    "runtime listed every invocation in isolated one-skill fixtures"
                )
            elif structural_errors:
                record["status"] = "unsupported"
                record["reason"] = "structural validation failed; runtime proof is inadmissible"
            else:
                record["status"] = "unsupported"
                record["reason"] = (
                    "runtime discovery did not list isolated invocations: " f"{missing}"
                )
            records[surface] = record
            continue
        else:
            settings = home / ".gemini" / "settings.json"
            settings.parent.mkdir(parents=True, exist_ok=True)
            settings.write_text(
                '{"security":{"folderTrust":{"enabled":false}}}\n', encoding="utf-8"
            )
            command = [executable, "skills", "list"]
        discovery_result = runner(command, root, env)
        record["discovery_probe"] = _command_record(
            command, root, discovery_result, bind_cwd=True
        )
        record["discovery_probes"] = [record["discovery_probe"]]
        if surface == "gemini":
            try:
                validate_gemini_skills_list_stderr(discovery_result.stderr)
                observed = {
                    row.name
                    for row in parse_gemini_skills_list(
                        discovery_result.stdout, project_root=root
                    )
                }
            except NativeDiscoveryParseError:
                observed = set()
            missing = sorted(set(invocation_names) - observed)
        if (
            discovery_result.returncode == 0
            and observed == set(invocation_names)
            and not structural_errors
        ):
            record["status"] = "verified"
            record["reason"] = (
                "runtime listed every canonical invocation from the isolated projection"
            )
        elif structural_errors:
            record["status"] = "unsupported"
            record["reason"] = "structural validation failed; runtime proof is inadmissible"
        else:
            record["status"] = "unsupported"
            record["reason"] = f"runtime discovery did not list canonical invocations: {missing}"
        records[surface] = record
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_root": str(isolated_root),
        "inventory_sha256": _document_hash(inventory),
        "manifest_sha256": _document_hash(manifest),
        "records": records,
    }


def _validate_command_record(
    value: Any,
    *,
    label: str,
    errors: list[str],
    extra_fields: frozenset[str] = frozenset(),
    bind_cwd: bool = False,
) -> None:
    required = {"argv", "cwd", "exit_code", "stdout", "stderr", "output_sha256"}
    if bind_cwd:
        required.add("cwd_sha256")
    if not isinstance(value, dict) or set(value) != required | set(extra_fields):
        errors.append(f"{label} fields differ from the command evidence contract")
        return
    argv = value["argv"]
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
        errors.append(f"{label}.argv must be a non-empty list of strings")
    cwd = value["cwd"]
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        errors.append(f"{label}.cwd must be an absolute path")
    elif bind_cwd:
        if not Path(cwd).is_dir():
            errors.append(f"{label}.cwd no longer exists")
        elif value.get("cwd_sha256") != _directory_tree_hash(Path(cwd)):
            errors.append(f"{label}.cwd content hash is foreign or stale")
    if not isinstance(value["exit_code"], int) or isinstance(value["exit_code"], bool):
        errors.append(f"{label}.exit_code must be an integer")
    stdout, stderr = value["stdout"], value["stderr"]
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        errors.append(f"{label} stdout and stderr must be strings")
    else:
        expected = _sha256_bytes(stdout.encode() + stderr.encode())
        if value["output_sha256"] != expected:
            errors.append(f"{label} output hash differs from stdout/stderr")
    if "fixture_sha256" in extra_fields and not (
        isinstance(value.get("fixture_sha256"), str)
        and HASH_RE.fullmatch(value["fixture_sha256"])
    ):
        errors.append(f"{label}.fixture_sha256 must be a SHA-256 digest")
    if "invocation" in extra_fields and not (
        isinstance(value.get("invocation"), str)
        and NAME_RE.fullmatch(value["invocation"])
    ):
        errors.append(f"{label}.invocation must be a safe public invocation")


def _expected_runtime_version(surface: str, registry: CapabilityRegistry) -> str | None:
    minimum = str(registry.data["agent_surfaces"][surface]["minimum_surface_version"])
    if minimum[0].isdigit():
        return minimum
    if surface == "augment":
        return "0.32.0"
    return None


def _probe_observed_version(probe: Mapping[str, Any]) -> str:
    return f"{probe.get('stdout', '')}{probe.get('stderr', '')}"


def validate_runtime_evidence(
    evidence: Mapping[str, Any],
    inventory: Mapping[str, Any],
    project_root: Path,
    output_root: Path,
    manifest: Mapping[str, Any],
    permitted_runtime_root: Path,
    *,
    registry: CapabilityRegistry | None = None,
) -> list[str]:
    """Validate content-addressed runtime records without granting support claims."""
    errors: list[str] = []
    root = project_root.resolve()
    selected_registry = registry or load_registry(
        root / ".claude/skills/_common/capability-registry.yml"
    )
    structural_errors = validate_projections(
        inventory, root, output_root, manifest, registry=selected_registry
    )
    if structural_errors:
        errors.extend(f"structural validation: {error}" for error in structural_errors)
    expected_top = {
        "schema_version", "runtime_root", "inventory_sha256", "manifest_sha256", "records"
    }
    if set(evidence) != expected_top:
        errors.append("runtime evidence fields differ from the evidence contract")
    if evidence.get("schema_version") != SCHEMA_VERSION:
        errors.append("runtime evidence schema version differs")
    inventory_hash = _document_hash(inventory)
    manifest_hash = _document_hash(manifest)
    if evidence.get("inventory_sha256") != inventory_hash:
        errors.append("runtime evidence is bound to a foreign inventory")
    if evidence.get("manifest_sha256") != manifest_hash:
        errors.append("runtime evidence is bound to a foreign manifest")
    runtime_root = permitted_runtime_root.resolve()
    runtime_root_value = evidence.get("runtime_root")
    if runtime_root_value != str(runtime_root):
        errors.append("runtime evidence differs from the permitted isolated runtime root")
    records = evidence.get("records")
    expected_surfaces = set(selected_registry.identifiers("agent_surfaces"))
    if not isinstance(records, dict) or set(records) != expected_surfaces:
        errors.append("runtime evidence does not cover every supported surface")
        return errors

    source_files = _git_tree_files(root, [skill["source"] for skill in inventory["skills"]])
    common_expected = {
        "registry_version": selected_registry.schema_version,
        "registry_contract_version": selected_registry.contract_version,
        "registry_sha256": inventory["registry_sha256"],
        "source_revision": _git_revision(root),
        "source_tree": _git_tree(root),
        "source_sha256": _tree_hash(source_files),
        "bundle_sha256": inventory["bundle_sha256"],
        "inventory_sha256": inventory_hash,
        "manifest_sha256": manifest_hash,
        "projection_sha256": manifest["projection_sha256"],
        "projection_mode": manifest["projection_mode"],
        "platform": _platform_record(),
        "runtime_root": str(runtime_root),
    }
    record_fields = {
        *common_expected,
        "structural_validation", "surface", "surface_contract_version",
        "discovery_contract", "fixture_sha256", "projection_path", "projection_mode",
        "status", "reason", "version_probe", "setup_probes", "discovery_probe",
        "discovery_probes",
    }
    expected_names = sorted(
        [skill["name"] for skill in inventory["skills"]]
        + list(_resolved_aliases(inventory))
    )
    for surface in sorted(expected_surfaces):
        record = records[surface]
        label = f"records.{surface}"
        if not isinstance(record, dict) or set(record) != record_fields:
            errors.append(f"{label} fields differ from the runtime record contract")
            continue
        for field, expected in common_expected.items():
            if record.get(field) != expected:
                errors.append(f"{label}.{field} differs from the current source/evidence binding")
        contract = selected_registry.data["agent_surfaces"][surface]
        if record.get("surface") != surface:
            errors.append(f"{label}.surface differs")
        if record.get("surface_contract_version") != str(contract["minimum_surface_version"]):
            errors.append(f"{label}.surface_contract_version differs from the registry")
        if record.get("discovery_contract") != contract["discovery"]:
            errors.append(f"{label}.discovery_contract differs from the registry")
        surface_root = output_root / surface
        fixture_files = {
            path.relative_to(surface_root).as_posix(): path.read_bytes()
            for path in sorted(surface_root.rglob("*"))
            if path.is_file()
        }
        if record.get("fixture_sha256") != _tree_hash(fixture_files):
            errors.append(f"{label}.fixture_sha256 is foreign or stale")
        if record.get("projection_path") != str(surface_root.resolve()):
            errors.append(f"{label}.projection_path differs from the validated fixture")
        structural = record.get("structural_validation")
        expected_structural = {
            "result": "pass" if not structural_errors else "fail",
            "errors": structural_errors,
            "satisfies_runtime_discovery": False,
        }
        if structural != expected_structural:
            errors.append(f"{label}.structural_validation differs from direct validation")
        status = record.get("status")
        if status not in {"verified", "unsupported", "unavailable"}:
            errors.append(f"{label}.status is invalid")
        if status == "verified" and structural_errors:
            errors.append(f"{label} claims verified runtime discovery after structural failure")
        if status == "unavailable":
            if record.get("reason") != "runtime executable is unavailable":
                errors.append(f"{label}.reason differs from the unavailable runtime contract")
            if any(
                record.get(field)
                for field in ("version_probe", "setup_probes", "discovery_probe", "discovery_probes")
            ):
                errors.append(f"{label} unavailable runtime record contains command evidence")

        version_probe = record.get("version_probe")
        if version_probe is not None:
            _validate_command_record(
                version_probe,
                label=f"{label}.version_probe",
                errors=errors,
                bind_cwd=True,
            )
            if version_probe.get("cwd") != str(surface_root.resolve()):
                errors.append(f"{label}.version_probe.cwd differs from the surface fixture")
            if version_probe.get("argv", [])[1:] != ["--version"]:
                errors.append(f"{label}.version_probe did not execute --version")
            expected_version = _expected_runtime_version(surface, selected_registry)
            if expected_version:
                observed_version = _probe_observed_version(version_probe)
                exact_version = (
                    observed_version.strip() == expected_version
                    if surface == "gemini"
                    else re.search(
                        rf"(?<![0-9.]){re.escape(expected_version)}(?![0-9.])",
                        observed_version,
                    )
                    is not None
                )
                if not exact_version:
                    errors.append(
                        f"{label}.version_probe does not prove exact {expected_version}"
                    )
        elif status != "unavailable":
            errors.append(f"{label} has no version probe for a present runtime")

        setup_probes = record.get("setup_probes")
        if not isinstance(setup_probes, list):
            errors.append(f"{label}.setup_probes must be a list")
            setup_probes = []
        for index, probe in enumerate(setup_probes):
            _validate_command_record(
                probe, label=f"{label}.setup_probes[{index}]", errors=errors
            )

        discovery_probe = record.get("discovery_probe")
        probes = record.get("discovery_probes")
        if not isinstance(probes, list):
            errors.append(f"{label}.discovery_probes must be a list")
            continue
        for index, probe in enumerate(probes):
            extra = (
                frozenset({"fixture_sha256", "invocation"})
                if surface == "augment"
                else frozenset()
            )
            _validate_command_record(
                probe,
                label=f"{label}.discovery_probes[{index}]",
                errors=errors,
                extra_fields=extra,
                bind_cwd=True,
            )
        if discovery_probe is not None:
            _validate_command_record(
                discovery_probe,
                label=f"{label}.discovery_probe",
                errors=errors,
                bind_cwd=True,
            )
            if probes != [discovery_probe]:
                errors.append(f"{label}.discovery_probe differs from discovery_probes")
        elif surface != "augment" and probes:
            errors.append(f"{label} has probe rows without a primary discovery_probe")

        if status != "verified":
            continue
        if not probes:
            errors.append(f"{label} claims verified discovery without a discovery command")
            continue
        if any(not isinstance(probe, dict) for probe in [*setup_probes, *probes]):
            errors.append(f"{label} contains a non-mapping verified command record")
            continue
        if any(probe.get("exit_code") != 0 for probe in [*setup_probes, *probes]):
            errors.append(f"{label} claims verified discovery with a failed command")
        if not isinstance(version_probe, dict) or version_probe.get("exit_code") != 0:
            errors.append(f"{label} verified runtime version probe failed")
        elif any(
            probe.get("argv", [None])[0] != version_probe.get("argv", [None])[0]
            for probe in [*setup_probes, *probes]
        ):
            errors.append(f"{label} runtime commands use a different executable")
        verified_reasons = {
            "augment": "runtime listed every invocation in isolated one-skill fixtures",
            "claude-code": "Claude plugin details listed the exact full-discovery skill set",
            "codex": "Codex prompt-input listed the exact namespaced full-discovery skill set",
            "gemini": "runtime listed every canonical invocation from the isolated projection",
        }
        if record.get("reason") != verified_reasons.get(surface):
            errors.append(f"{label}.reason differs from the verified discovery contract")
        if surface == "claude-code":
            if len(setup_probes) != 4:
                errors.append(f"{label} requires validate, marketplace-add, install, and list probes")
            else:
                setup_cwd = setup_probes[0].get("cwd")
                marketplace = (
                    str(Path(setup_cwd) / "marketplace")
                    if isinstance(setup_cwd, str)
                    else ""
                )
                expected_setup = [
                    ["plugin", "validate", marketplace],
                    ["plugin", "marketplace", "add", marketplace],
                    ["plugin", "install", "engineering-skills@engineering-skills-local"],
                    ["plugin", "list", "--json"],
                ]
                if [probe.get("argv", [])[1:] for probe in setup_probes] != expected_setup:
                    errors.append(f"{label} Claude setup commands differ from the isolated contract")
                if any(probe.get("cwd") != setup_cwd for probe in setup_probes):
                    errors.append(f"{label} Claude setup commands use different fixture roots")
                if setup_cwd != str(runtime_root / "claude-code-runtime"):
                    errors.append(f"{label} Claude fixture is outside the permitted runtime root")
                projected_skills = {
                    path.relative_to(surface_root / ".claude/skills").as_posix(): path.read_bytes()
                    for path in sorted((surface_root / ".claude/skills").rglob("*"))
                    if path.is_file()
                }
                packaged_root = Path(setup_cwd or ".") / "marketplace/plugins/engineering-skills/skills"
                packaged_skills = {
                    path.relative_to(packaged_root).as_posix(): path.read_bytes()
                    for path in sorted(packaged_root.rglob("*"))
                    if path.is_file()
                }
                if packaged_skills != projected_skills:
                    errors.append(f"{label} Claude marketplace package differs from the projection")
            argv = probes[0].get("argv", [])
            if argv[1:] != [
                "plugin", "details", "engineering-skills@engineering-skills-local"
            ]:
                errors.append(f"{label} did not use Claude plugin details discovery")
            if setup_probes and probes[0].get("cwd") != setup_probes[0].get("cwd"):
                errors.append(f"{label} Claude discovery cwd differs from setup cwd")
            observed = _claude_detail_names(probes[0].get("stdout", ""))
            if observed != set(expected_names):
                errors.append(f"{label} Claude discovery names differ from the inventory")
        elif surface == "codex":
            if len(setup_probes) != 3:
                errors.append(f"{label} requires marketplace-add, plugin-add, and list probes")
            else:
                setup_cwd = setup_probes[0].get("cwd")
                workspace = Path(setup_cwd or ".").parent
                marketplace = str(workspace / "marketplace")
                expected_setup = [
                    ["plugin", "marketplace", "add", marketplace, "--json"],
                    ["plugin", "add", "engineering-skills@engineering-skills-local", "--json"],
                    ["plugin", "list"],
                ]
                if [probe.get("argv", [])[1:] for probe in setup_probes] != expected_setup:
                    errors.append(f"{label} Codex setup commands differ from the isolated contract")
                if any(probe.get("cwd") != setup_cwd for probe in setup_probes):
                    errors.append(f"{label} Codex setup commands use different fixture roots")
                if setup_cwd != str(runtime_root / "codex-runtime/project"):
                    errors.append(f"{label} Codex fixture is outside the permitted runtime root")
                projected_files = {
                    path.relative_to(surface_root).as_posix(): path.read_bytes()
                    for path in sorted(surface_root.rglob("*"))
                    if path.is_file()
                }
                packaged_root = workspace / "marketplace/plugins/engineering-skills"
                packaged_files = {
                    path.relative_to(packaged_root).as_posix(): path.read_bytes()
                    for path in sorted(packaged_root.rglob("*"))
                    if path.is_file()
                }
                if packaged_files != projected_files:
                    errors.append(f"{label} Codex marketplace package differs from the projection")
            setup_output = "".join(probe.get("stdout", "") for probe in setup_probes)
            if '"authPolicy": "ON_USE"' not in setup_output:
                errors.append(f"{label} does not bind the required ON_USE authentication policy")
            argv = probes[0].get("argv", [])
            if len(argv) < 6 or argv[-3:] != ["debug", "prompt-input", "probe"]:
                errors.append(f"{label} did not use Codex prompt-input discovery")
            elif argv[1:3] != ["-C", probes[0].get("cwd")]:
                errors.append(f"{label} Codex -C root differs from the recorded cwd")
            observed = _codex_prompt_names(probes[0].get("stdout", ""))
            if observed != set(expected_names):
                errors.append(f"{label} Codex discovery names differ from the inventory")
        if surface == "gemini":
            if probes[0].get("argv", [])[1:] != ["skills", "list"]:
                errors.append(f"{label} did not use Gemini skills list discovery")
            if probes[0].get("cwd") != str(surface_root.resolve()):
                errors.append(f"{label} Gemini discovery cwd differs from the surface fixture")
            try:
                validate_gemini_skills_list_stderr(probes[0]["stderr"])
                observed = {
                    row.name
                    for row in parse_gemini_skills_list(
                        probes[0]["stdout"], project_root=surface_root
                    )
                }
            except NativeDiscoveryParseError as exc:
                errors.append(f"{label} Gemini discovery output is invalid: {exc}")
                observed = set()
            if observed != set(expected_names):
                errors.append(f"{label} Gemini discovery names differ from the inventory")
        elif surface == "augment":
            invocations = [probe.get("invocation") for probe in probes]
            if sorted(invocations) != expected_names or len(invocations) != len(set(invocations)):
                errors.append(f"{label} Augment discovery probes differ from the invocation set")
            skill_rows = {skill["name"]: skill for skill in inventory["skills"]}
            resolved = {name: name for name in skill_rows} | _resolved_aliases(inventory)
            for probe in probes:
                if probe.get("argv", [])[1:] != ["rules", "list"]:
                    errors.append(f"{label} did not use Augment rules list discovery")
                invocation = probe.get("invocation")
                if invocation not in resolved:
                    continue
                source = surface_root / ".augment/rules/imported" / invocation
                expected_files = {
                    f".augment/rules/imported/{invocation}/{path.relative_to(source).as_posix()}": path.read_bytes()
                    for path in sorted(source.rglob("*"))
                    if path.is_file()
                }
                if probe.get("fixture_sha256") != _tree_hash(expected_files):
                    errors.append(f"{label} probe for {invocation!r} is bound to a foreign fixture")
                expected_cwd = runtime_root / "augment-fixtures" / invocation
                if probe.get("cwd") != str(expected_cwd):
                    errors.append(
                        f"{label} probe cwd differs from the permitted runtime root "
                        f"for invocation {invocation!r}"
                    )
                observed = set(
                    re.findall(
                        r"\.augment/rules/imported/([a-z0-9]+(?:-[a-z0-9]+)*)/SKILL\.md",
                        probe.get("stdout", ""),
                    )
                )
                if observed != {invocation}:
                    errors.append(
                        f"{label} probe output differs from isolated invocation {invocation!r}"
                    )
        elif surface not in {"claude-code", "codex"}:
            errors.append(f"{label} uses an unvalidated verified discovery mechanism")
    return errors


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    project = subparsers.add_parser("project", help="build and validate all surface projections")
    project.add_argument("project_root", type=Path)
    project.add_argument("output_root", type=Path)
    project.add_argument("--inventory-output", type=Path)
    runtime = subparsers.add_parser("runtime", help="collect separate runtime discovery evidence")
    runtime.add_argument("project_root", type=Path)
    runtime.add_argument("output_root", type=Path)
    runtime.add_argument("runtime_home", type=Path)
    runtime.add_argument("evidence_output", type=Path)
    verify = subparsers.add_parser(
        "verify-matrix", help="validate structural projections and runtime evidence read-only"
    )
    verify.add_argument("project_root", nargs="?", type=Path, default=Path("."))
    verify.add_argument("--fixtures", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    verify.add_argument("--runtime-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        inventory = build_bundle_inventory(root)
        if args.command == "project":
            manifest = build_projections(inventory, root, args.output_root.resolve())
            errors = validate_projections(inventory, root, args.output_root.resolve(), manifest)
            if errors:
                for error in errors:
                    print(f"ERROR {error}")
                return 1
            if args.inventory_output:
                args.inventory_output.write_bytes(_canonical_bytes(inventory))
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0
        if args.command == "verify-matrix":
            fixtures = args.fixtures.resolve()
            manifest = _load_json(fixtures / "projection-manifest.json")
            evidence = _load_json(args.evidence.resolve())
            errors = validate_runtime_evidence(
                evidence,
                inventory,
                root,
                fixtures,
                manifest,
                args.runtime_root,
            )
            if errors:
                for error in errors:
                    print(f"ERROR {error}")
                return 1
            statuses = {
                surface: record["status"]
                for surface, record in sorted(evidence["records"].items())
            }
            print(json.dumps({"result": "pass", "statuses": statuses}, sort_keys=True))
            return 0
        manifest = _load_json(args.output_root / "projection-manifest.json")
        evidence = collect_runtime_evidence(
            inventory, root, args.output_root.resolve(), manifest, args.runtime_home.resolve()
        )
        errors = validate_runtime_evidence(
            evidence,
            inventory,
            root,
            args.output_root.resolve(),
            manifest,
            args.runtime_home,
        )
        if errors:
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
            return 1
        args.evidence_output.write_bytes(_canonical_bytes(evidence))
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
