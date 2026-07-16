#!/usr/bin/env python3
"""Build and validate deterministic skill projections for every agent surface.

Structural projection and runtime discovery are deliberately separate.  A clean
projection never implies that a runtime discovered or invoked a skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from _lib.capability_registry import CapabilityRegistry, load_registry
from _lib.skill_catalog import DEFAULT_INVENTORY_PATH, load_catalog


SCHEMA_VERSION = 1
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


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _tree_hash(files: Mapping[str, bytes]) -> str:
    lines = [f"{_sha256_bytes(content)}  {path}\n" for path, content in sorted(files.items())]
    return _sha256_bytes("".join(lines).encode())


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


def _source_files(skill_dir: Path) -> list[Path]:
    files = [path for path in skill_dir.rglob("*") if path.is_file()]
    if any(path.is_symlink() for path in files):
        raise ValueError(f"symlinked skill resources are not distributable: {skill_dir}")
    return sorted(files, key=lambda path: path.relative_to(skill_dir).as_posix())


def build_bundle_inventory(
    project_root: Path,
    *,
    aliases: Sequence[Mapping[str, Any]] = (),
    catalog_path: Path | None = None,
    registry: CapabilityRegistry | None = None,
) -> dict[str, Any]:
    """Inventory all distribution-ready skills and their complete resource trees."""
    root = project_root.resolve()
    selected_registry = registry or load_registry()
    default_catalog = root / DEFAULT_INVENTORY_PATH.relative_to(
        DEFAULT_INVENTORY_PATH.parents[3]
    )
    selected_catalog = (catalog_path or default_catalog).resolve()
    skills_dir = root / ".claude" / "skills"
    catalog = load_catalog(
        selected_catalog,
        skills_dir=skills_dir,
        project_root=root,
        registry=selected_registry,
    )
    skills: list[dict[str, Any]] = []
    for entry in catalog.entries:
        if entry.readiness not in READY_STATES:
            continue
        canonical = root / entry.path
        skill_dir = canonical.parent
        files = [
            {
                "path": path.relative_to(skill_dir).as_posix(),
                "sha256": _sha256(path),
            }
            for path in _source_files(skill_dir)
        ]
        skills.append(
            {
                "name": entry.name,
                "source": skill_dir.relative_to(root).as_posix(),
                "files": files,
                "catalog_link": {
                    "inventory": selected_catalog.relative_to(root).as_posix(),
                    "row_sha256": _row_hash(entry.raw),
                },
            }
        )
    inventory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "registry_version": selected_registry.schema_version,
        "registry_sha256": _sha256(selected_registry.path),
        "catalog_sha256": _sha256(selected_catalog),
        "skills": skills,
        "aliases": [dict(alias) for alias in aliases],
    }
    inventory["bundle_sha256"] = _bundle_hash(inventory)
    errors = validate_bundle_inventory(inventory, root, registry=selected_registry)
    if errors:
        raise ValueError("\n".join(errors))
    return inventory


def _alias_targets(
    inventory: Mapping[str, Any], errors: list[str]
) -> dict[str, str]:
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
        if not match or not isinstance(version, int) or int(match.group(2)) != version:
            errors.append(f"alias {name!r} must be a versioned name ending in -v<version>")
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
    selected_registry = registry or load_registry()
    expected_top = {
        "schema_version", "registry_version", "registry_sha256", "catalog_sha256",
        "skills", "aliases", "bundle_sha256",
    }
    if set(inventory) != expected_top:
        errors.append(f"bundle inventory fields differ: {sorted(set(inventory) ^ expected_top)}")
    if inventory.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if inventory.get("registry_version") != selected_registry.schema_version:
        errors.append("registry version differs from the canonical registry")
    if inventory.get("registry_sha256") != _sha256(selected_registry.path):
        errors.append("registry hash differs from the canonical registry")
    if inventory.get("bundle_sha256") != _bundle_hash(inventory):
        errors.append("bundle hash differs from canonical inventory content")
    skills = inventory.get("skills")
    if not isinstance(skills, list) or not skills:
        errors.append("skills must be a non-empty list")
        return errors
    names: list[str] = []
    catalog_paths: set[str] = set()
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
        source_dir = root / source
        if not source_dir.is_dir() or not source_dir.joinpath("SKILL.md").is_file():
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
            path = source_dir / relative
            if not path.is_file():
                errors.append(f"skill {name!r} has stale reference {relative!r}")
            elif _sha256(path) != expected_hash:
                errors.append(f"skill {name!r} source hash differs for {relative!r}")
        actual = [path.relative_to(source_dir).as_posix() for path in _source_files(source_dir)]
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
        if not catalog_path.is_file() or _sha256(catalog_path) != inventory.get("catalog_sha256"):
            errors.append("catalog link or catalog hash is stale")
        else:
            catalog = load_catalog(
                catalog_path,
                skills_dir=root / ".claude" / "skills",
                project_root=root,
                registry=selected_registry,
            )
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
    projected: dict[str, dict[str, bytes]] = {surface: {} for surface in SURFACE_LAYOUTS}
    for surface, (prefix, primary_name) in SURFACE_LAYOUTS.items():
        for invocation, canonical in sorted(invocations.items()):
            skill = skills[canonical]
            for file_row in skill["files"]:
                relative = file_row["path"]
                destination_name = primary_name if relative == "SKILL.md" else relative
                destination = f"{surface}/{prefix}/{invocation}/{destination_name}"
                content = (root / skill["source"] / relative).read_bytes()
                if invocation != canonical and relative == "SKILL.md":
                    content = _alias_skill(content, canonical, invocation)
                projected[surface][destination] = content
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
    projected["codex"]["codex/.codex-plugin/plugin.json"] = (
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
    selected_registry = registry or load_registry()
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
    selected_registry = registry or load_registry()
    errors = validate_bundle_inventory(inventory, project_root, registry=selected_registry)
    expected = _expected_projection_files(inventory, project_root, selected_registry)
    expected_surfaces = set(selected_registry.identifiers("agent_surfaces"))
    surfaces = manifest.get("surfaces", {})
    expected_manifest_fields = {
        "schema_version", "registry_version", "registry_sha256", "bundle_sha256",
        "projection_sha256", "surfaces",
    }
    if set(manifest) != expected_manifest_fields:
        errors.append("projection manifest fields differ from the structural contract")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("projection schema version differs from the structural contract")
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
    command: Sequence[str], cwd: Path, result: subprocess.CompletedProcess[bytes]
) -> dict[str, Any]:
    raw = result.stdout + result.stderr
    return {
        "command": list(command),
        "cwd": str(cwd.resolve()),
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "output_sha256": _sha256_bytes(raw),
    }


def _git_revision(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


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
    selected_registry = registry or load_registry()
    structural_errors = validate_projections(
        inventory, project_root, output_root, manifest, registry=selected_registry
    )
    source_files = {
        f"{skill['source']}/{row['path']}": (project_root / skill["source"] / row["path"]).read_bytes()
        for skill in inventory["skills"]
        for row in skill["files"]
    }
    common = {
        "registry_version": selected_registry.schema_version,
        "registry_sha256": inventory["registry_sha256"],
        "source_revision": _git_revision(project_root),
        "source_sha256": _tree_hash(source_files),
        "bundle_sha256": inventory["bundle_sha256"],
        "projection_sha256": manifest["projection_sha256"],
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
            "status": "unavailable",
            "reason": "runtime executable is unavailable",
            "version_probe": None,
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
        record["version_probe"] = _command_record(version_command, root, version_result)
        expected_version = str(contract["minimum_surface_version"])
        observed_version = (version_result.stdout + version_result.stderr).decode(
            "utf-8", errors="replace"
        )
        version_is_pinned = expected_version[0].isdigit()
        exact_version = re.search(
            rf"(?<![0-9.]){re.escape(expected_version)}(?![0-9.])", observed_version
        )
        if version_result.returncode != 0 or (version_is_pinned and not exact_version):
            record["status"] = "unsupported"
            record["reason"] = f"runtime version does not match pinned {expected_version}"
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
            invocation_names = sorted(
                [skill["name"] for skill in inventory["skills"]]
                + list(_resolved_aliases(inventory))
            )
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
                probe = _command_record(command, fixture, discovery_result)
                probe["fixture_sha256"] = _tree_hash(fixture_files)
                record["discovery_probes"].append(probe)
                output = discovery_result.stdout.decode("utf-8", errors="replace")
                if discovery_result.returncode != 0 or name not in output:
                    missing.append(name)
            if not missing:
                record["status"] = "verified"
                record["reason"] = (
                    "runtime listed every invocation in isolated one-skill fixtures"
                )
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
        record["discovery_probe"] = _command_record(command, root, discovery_result)
        record["discovery_probes"] = [record["discovery_probe"]]
        output = discovery_result.stdout.decode("utf-8", errors="replace")
        expected_names = sorted(
            [skill["name"] for skill in inventory["skills"]]
            + list(_resolved_aliases(inventory))
        )
        if surface == "gemini":
            missing = [
                name for name in expected_names if f"\n{name} [Enabled]\n" not in f"\n{output}"
            ]
        if discovery_result.returncode == 0 and not missing:
            record["status"] = "verified"
            record["reason"] = (
                "runtime listed every canonical invocation from the isolated projection"
            )
        else:
            record["status"] = "unsupported"
            record["reason"] = f"runtime discovery did not list canonical invocations: {missing}"
        records[surface] = record
    return {"schema_version": SCHEMA_VERSION, "records": records}


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
        manifest = _load_json(args.output_root / "projection-manifest.json")
        evidence = collect_runtime_evidence(
            inventory, root, args.output_root.resolve(), manifest, args.runtime_home.resolve()
        )
        args.evidence_output.write_bytes(_canonical_bytes(evidence))
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
