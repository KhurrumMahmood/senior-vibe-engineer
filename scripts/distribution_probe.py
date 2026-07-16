#!/usr/bin/env python3
"""Prototype surface projections from one canonical skill source (ADR 0042)."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Callable

from _lib.capability_registry import CapabilityRegistry, load_registry


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_skill(source: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "SKILL.md"
    shutil.copyfile(source, target)
    return [target]


def _codex_projection(source: Path, root: Path) -> list[Path]:
    skill_files = _copy_skill(source, root / "skills" / source.parent.name)
    manifest_dir = root / ".codex-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "plugin.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "engineering-skills-probe",
                "version": "0.0.1",
                "description": "Generated discovery probe for the engineering-skills catalog.",
                "author": {"name": "engineering-skills"},
                "license": "MIT",
                "skills": "./skills/",
                "interface": {
                    "displayName": "Engineering Skills Probe",
                    "shortDescription": "Validates generated skill discovery.",
                    "longDescription": "A temporary projection used to validate the composed distribution contract.",
                    "developerName": "engineering-skills",
                    "category": "Developer Tools",
                    "capabilities": ["Read"],
                    "defaultPrompt": ["Use the generated probe skill."],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return [manifest, *skill_files]


def _instruction_projection(source: Path, target: Path, surface: str) -> list[Path]:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# Generated {surface} projection\n\n"
        f"Canonical skill: `{source.parent.name}`\n"
        f"Canonical SHA-256: `{_digest(source)}`\n",
        encoding="utf-8",
    )
    return [target]


def build_projections(
    source_skill: Path,
    output_root: Path,
    *,
    registry: CapabilityRegistry | None = None,
) -> dict[str, list[str]]:
    registry = registry or load_registry()
    if source_skill.name != "SKILL.md" or not source_skill.is_file():
        raise ValueError("source_skill must be an existing SKILL.md")
    handlers: dict[str, Callable[[], list[Path]]] = {
        "claude-code": lambda: _copy_skill(
            source_skill,
            output_root / "claude-code" / ".claude" / "skills" / source_skill.parent.name,
        ),
        "codex": lambda: _codex_projection(source_skill, output_root / "codex"),
        "augment": lambda: _instruction_projection(
            source_skill,
            output_root / "augment" / ".augment" / "rules" / "imported" / f"{source_skill.parent.name}.md",
            "Augment",
        ),
        "cursor": lambda: _instruction_projection(
            source_skill,
            output_root / "cursor" / ".cursor" / "rules" / f"{source_skill.parent.name}.mdc",
            "Cursor",
        ),
        "gemini": lambda: _instruction_projection(
            source_skill,
            output_root / "gemini" / ".gemini" / f"{source_skill.parent.name}.md",
            "Gemini",
        ),
    }
    expected = registry.identifiers("agent_surfaces")
    if set(handlers) != set(expected):
        raise ValueError(
            f"surface projection mismatch: handlers={sorted(handlers)}, registry={sorted(expected)}"
        )
    manifest: dict[str, list[str]] = {}
    for surface in sorted(handlers):
        files = handlers[surface]()
        manifest[surface] = [str(path.relative_to(output_root)) for path in files]
    return manifest


def validate_projections(
    source_skill: Path,
    output_root: Path,
    manifest: dict[str, list[str]],
    *,
    registry: CapabilityRegistry | None = None,
) -> list[str]:
    registry = registry or load_registry()
    errors: list[str] = []
    if set(manifest) != set(registry.identifiers("agent_surfaces")):
        errors.append("projection manifest does not cover every supported surface")
    source_digest = _digest(source_skill)
    for surface, relatives in manifest.items():
        if not relatives:
            errors.append(f"{surface}: no discovery artifact")
            continue
        paths = [output_root / relative for relative in relatives]
        if any(not path.is_file() for path in paths):
            errors.append(f"{surface}: missing declared discovery artifact")
            continue
        if surface in {"claude-code", "codex"}:
            skill = next((path for path in paths if path.name == "SKILL.md"), None)
            if skill is None or _digest(skill) != source_digest:
                errors.append(f"{surface}: projected skill differs from canonical source")
        else:
            if source_digest not in paths[0].read_text(encoding="utf-8"):
                errors.append(f"{surface}: projection does not attest canonical source")
    codex_manifest = output_root / "codex" / ".codex-plugin" / "plugin.json"
    if codex_manifest.is_file():
        payload = json.loads(codex_manifest.read_text(encoding="utf-8"))
        if payload.get("name") != "engineering-skills-probe" or payload.get("skills") != "./skills/":
            errors.append("codex: invalid plugin discovery manifest")
    return errors


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_skill", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = build_projections(args.source_skill.resolve(), args.output_root.resolve())
        errors = validate_projections(
            args.source_skill.resolve(), args.output_root.resolve(), manifest
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
