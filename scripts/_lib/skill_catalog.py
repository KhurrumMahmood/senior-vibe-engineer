"""Strict reader for the authoritative portable-skill placement inventory.

The inventory is a planning and distribution-readiness authority. It does not
promote legacy skill frontmatter into the versioned capability contract and it
does not select bindings at runtime.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from _lib.capability_registry import CapabilityRegistry, load_registry
from _lib.yaml_frontmatter import FrontmatterError, read


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DEFAULT_INVENTORY_PATH = (
    DEFAULT_SKILLS_DIR / "_common" / "skill-catalog-inventory.yml"
)
SCHEMA_VERSION = 1
# spec:portable-skill-layer-distribution::IM-1
READINESS_STATES = frozenset(
    {
        "inventory-only",
        "foundation-ready",
        "exemplar-ready",
        "deferred-to-wp8",
    }
)
PLACEMENTS = frozenset({"concept", "concept-plus-binding", "native"})
ROW_FIELDS = frozenset(
    {
        "name",
        "path",
        "current",
        "layer",
        "binding",
        "bindings",
        "placement",
        "readiness",
        "rationale",
        "ar3_foundation_member",
    }
)
TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "rationales", "ar3_de_flavor_members", "skills"}
)
RATIONALE_FIELDS = frozenset({"description", "layer", "placement"})


class CatalogError(ValueError):
    """The catalog inventory or its relationship to discovered skills is invalid."""


@dataclass(frozen=True)
class DiscoveredSkill:
    name: str
    path: str
    language: Any
    framework: Any
    frontmatter_name: Any


@dataclass(frozen=True)
class SkillCatalogEntry:
    name: str
    path: str
    current_language: str
    current_framework: str
    layer: str
    binding: str
    bindings: tuple[str, ...]
    placement: str
    readiness: str
    rationale: str
    ar3_foundation_member: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class SkillCatalog:
    path: Path
    entries: tuple[SkillCatalogEntry, ...]
    ar3_de_flavor_names: frozenset[str]

    @property
    def entries_by_name(self) -> dict[str, SkillCatalogEntry]:
        return {entry.name: entry for entry in self.entries}

    @property
    def readiness_counts(self) -> dict[str, int]:
        counts = Counter(entry.readiness for entry in self.entries)
        return {state: counts[state] for state in sorted(READINESS_STATES)}

    @property
    def layer_counts(self) -> dict[str, int]:
        counts = Counter(entry.layer for entry in self.entries)
        return {
            layer: counts[layer]
            for layer in ("core", "domain", "framework", "host-overlay", "language")
        }


def discover_skills(
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    *,
    project_root: Path = REPO_ROOT,
) -> dict[str, DiscoveredSkill]:
    """Discover only immediate ``<skill>/SKILL.md`` children."""
    root = project_root.resolve()
    discovered: dict[str, DiscoveredSkill] = {}
    errors: list[str] = []
    for skill_md in sorted(skills_dir.resolve().glob("*/SKILL.md")):
        name = skill_md.parent.name
        try:
            metadata = read(skill_md).metadata
        except FrontmatterError as exc:
            errors.append(str(exc))
            continue
        try:
            relative = skill_md.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"{skill_md}: discovered path is outside project root {root}")
            continue
        discovered[name] = DiscoveredSkill(
            name=name,
            path=relative,
            language=metadata.get("language"),
            framework=metadata.get("framework"),
            frontmatter_name=metadata.get("name"),
        )
    if errors:
        raise CatalogError("\n".join(errors))
    return discovered


def _validate_row(
    row: Any,
    *,
    index: int,
    discovered: Mapping[str, DiscoveredSkill],
    registry: CapabilityRegistry,
    rationales: Mapping[str, Mapping[str, str]],
    errors: list[str],
) -> tuple[str | None, str | None, bool]:
    prefix = f"skills[{index}]"
    if not isinstance(row, dict):
        errors.append(f"{prefix} must be a mapping")
        return None, None, False
    missing = sorted(ROW_FIELDS - set(row))
    unknown = sorted(set(row) - ROW_FIELDS)
    if missing:
        errors.append(f"{prefix} missing fields: {missing}")
    if unknown:
        errors.append(f"{prefix} has unknown fields: {unknown}")

    name = row.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{prefix}.name must be a non-empty string")
        name = None
    label = f"skill {name!r}" if name else prefix

    path = row.get("path")
    if not isinstance(path, str) or not path:
        errors.append(f"{label}: path must be a non-empty string")
    elif name in discovered and path != discovered[name].path:
        errors.append(
            f"{label}: path {path!r} does not match discovered path "
            f"{discovered[name].path!r}"
        )

    current = row.get("current")
    if not isinstance(current, dict) or set(current) != {"language", "framework"}:
        errors.append(
            f"{label}: current must contain exactly language and framework"
        )
        current = {}
    language = current.get("language")
    framework = current.get("framework")
    if language not in registry.identifiers("languages"):
        errors.append(f"{label}: current.language is unregistered: {language!r}")
    if framework not in registry.identifiers("frameworks"):
        errors.append(f"{label}: current.framework is unregistered: {framework!r}")
    if name in discovered:
        skill = discovered[name]
        if skill.frontmatter_name != name:
            errors.append(
                f"{label}: discovered frontmatter name is {skill.frontmatter_name!r}"
            )
        if language != skill.language:
            errors.append(
                f"{label}: current.language {language!r} does not match "
                f"frontmatter {skill.language!r}"
            )
        if framework != skill.framework:
            errors.append(
                f"{label}: current.framework {framework!r} does not match "
                f"frontmatter {skill.framework!r}"
            )

    layer = row.get("layer")
    registered_layers = registry.identifiers("layers")
    if not isinstance(layer, str):
        errors.append(f"{label}: layer must be exactly one registered layer ID")
        layer = None
    elif layer not in registered_layers:
        errors.append(f"{label}: unregistered layer {layer!r}")

    binding = row.get("binding")
    registered_bindings = registry.identifiers("bindings")
    if not isinstance(binding, str):
        errors.append(f"{label}: binding must be exactly one registered binding ID")
        binding = None
    elif binding not in registered_bindings:
        errors.append(f"{label}: unregistered binding {binding!r}")

    bindings = row.get("bindings")
    if not isinstance(bindings, list) or any(not isinstance(item, str) for item in bindings):
        errors.append(f"{label}: bindings must be a list of registered binding IDs")
        bindings = []
    else:
        duplicates = sorted(item for item, count in Counter(bindings).items() if count > 1)
        if duplicates:
            errors.append(f"{label}: duplicate bindings: {duplicates}")
        for item in bindings:
            if item not in registered_bindings:
                errors.append(f"{label}: unregistered binding {item!r}")
        if binding is not None and binding not in bindings:
            errors.append(f"{label}: primary binding {binding!r} is absent from bindings")
        if binding is not None and bindings and bindings[0] != binding:
            errors.append(f"{label}: primary binding {binding!r} must be first in bindings")

    if binding in registered_bindings and layer in registered_layers:
        binding_layer = registry.data["bindings"][binding].get("layer")
        if binding_layer != layer:
            errors.append(
                f"{label}: primary binding {binding!r} belongs to layer "
                f"{binding_layer!r}, not {layer!r}"
            )

    placement = row.get("placement")
    if placement not in PLACEMENTS:
        errors.append(f"{label}: placement must be one of {sorted(PLACEMENTS)}")
    elif layer == "core":
        expected = "concept-plus-binding" if len(bindings) > 1 else "concept"
        if placement != expected:
            if len(bindings) > 1:
                errors.append(
                    f"{label}: core with overlays must use placement "
                    "'concept-plus-binding'"
                )
            else:
                errors.append(f"{label}: core without overlays must use placement 'concept'")
    elif layer in registered_layers and placement != "native":
        errors.append(f"{label}: non-core shipping layers must use placement 'native'")

    readiness = row.get("readiness")
    if readiness not in READINESS_STATES:
        errors.append(f"{label}: unregistered readiness {readiness!r}")

    rationale = row.get("rationale")
    if rationale not in rationales:
        errors.append(f"{label}: unregistered rationale {rationale!r}")
    else:
        rationale_contract = rationales[rationale]
        required_layer = rationale_contract["layer"]
        required_placement = rationale_contract["placement"]
        if layer != required_layer:
            errors.append(
                f"{label}: rationale {rationale!r} requires layer "
                f"{required_layer!r}, got {layer!r}"
            )
        if placement != required_placement:
            errors.append(
                f"{label}: rationale {rationale!r} requires placement "
                f"{required_placement!r}, got {placement!r}"
            )

    ar3_member = row.get("ar3_foundation_member")
    if not isinstance(ar3_member, bool):
        errors.append(f"{label}: ar3_foundation_member must be a bool")
        ar3_member = False
    if ar3_member and readiness != "foundation-ready":
        errors.append(f"{label}: AR-3 members must be foundation-ready")

    return name, binding if layer == "domain" else None, ar3_member


def validate_catalog_payload(
    payload: Any,
    *,
    discovered: Mapping[str, DiscoveredSkill],
    registry: CapabilityRegistry,
) -> list[str]:
    """Return every strict inventory validation error without mutating input."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["catalog inventory must be a mapping"]
    missing_top = sorted(TOP_LEVEL_FIELDS - set(payload))
    unknown_top = sorted(set(payload) - TOP_LEVEL_FIELDS)
    if missing_top:
        errors.append(f"missing top-level fields: {missing_top}")
    if unknown_top:
        errors.append(f"unknown top-level fields: {unknown_top}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION}, got "
            f"{payload.get('schema_version')!r}"
        )

    rationales = payload.get("rationales")
    if not isinstance(rationales, dict) or not rationales:
        errors.append("rationales must be a non-empty ID-to-contract mapping")
        rationale_contracts: dict[str, Mapping[str, str]] = {}
    else:
        rationale_contracts = {}
        for rationale_id, contract in rationales.items():
            if not isinstance(rationale_id, str) or not rationale_id:
                errors.append("rationales must use non-empty string IDs")
                continue
            if not isinstance(contract, dict) or set(contract) != RATIONALE_FIELDS:
                errors.append(
                    f"rationale {rationale_id!r} must contain exactly "
                    f"{sorted(RATIONALE_FIELDS)}"
                )
                continue
            if not isinstance(contract["description"], str) or not contract["description"].strip():
                errors.append(f"rationale {rationale_id!r} description must be non-empty")
                continue
            if contract["layer"] not in registry.identifiers("layers"):
                errors.append(
                    f"rationale {rationale_id!r} names unregistered layer "
                    f"{contract['layer']!r}"
                )
                continue
            if contract["placement"] not in PLACEMENTS:
                errors.append(
                    f"rationale {rationale_id!r} names invalid placement "
                    f"{contract['placement']!r}"
                )
                continue
            rationale_contracts[rationale_id] = contract

    rows = payload.get("skills")
    if not isinstance(rows, list):
        errors.append("skills must be a list")
        return errors

    names: list[str] = []
    domain_bindings: list[str] = []
    row_ar3_names: set[str] = set()
    for index, row in enumerate(rows):
        name, domain_binding, ar3_member = _validate_row(
            row,
            index=index,
            discovered=discovered,
            registry=registry,
            rationales=rationale_contracts,
            errors=errors,
        )
        if name is not None:
            names.append(name)
            if ar3_member:
                row_ar3_names.add(name)
        if domain_binding is not None:
            domain_bindings.append(domain_binding)

    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate skill rows: {duplicates}")
    if names != sorted(names):
        errors.append("skill rows must be sorted by name")
    inventory_names = set(names)
    discovered_names = set(discovered)
    missing = sorted(discovered_names - inventory_names)
    unknown = sorted(inventory_names - discovered_names)
    if missing:
        errors.append(f"missing discovered skills: {missing}")
    if unknown:
        errors.append(f"unknown inventory skills: {unknown}")

    ar3 = payload.get("ar3_de_flavor_members")
    if not isinstance(ar3, list) or any(not isinstance(name, str) for name in ar3):
        errors.append("ar3_de_flavor_members must be a list of skill names")
    else:
        ar3_names = set(ar3)
        if len(ar3_names) != len(ar3):
            errors.append("ar3_de_flavor_members contains duplicates")
        if ar3 != sorted(ar3):
            errors.append("ar3_de_flavor_members must be sorted")
        if ar3_names != row_ar3_names:
            errors.append(
                "ar3_de_flavor_members disagrees with row membership: "
                f"list_only={sorted(ar3_names - row_ar3_names)}, "
                f"rows_only={sorted(row_ar3_names - ar3_names)}"
            )
        unknown_ar3 = sorted(ar3_names - discovered_names)
        if unknown_ar3:
            errors.append(f"ar3_de_flavor_members names unknown skills: {unknown_ar3}")

    for binding, count in sorted(Counter(domain_bindings).items()):
        if count < 3:
            errors.append(
                f"domain binding {binding!r} has {count} members; at least 3 are required"
            )
    return errors


def load_catalog(
    path: Path = DEFAULT_INVENTORY_PATH,
    *,
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    project_root: Path = REPO_ROOT,
    registry: CapabilityRegistry | None = None,
) -> SkillCatalog:
    """Read and validate the inventory against exact filesystem discovery."""
    inventory_path = path.resolve()
    try:
        payload = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogError(f"cannot read catalog inventory: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CatalogError(f"invalid YAML in catalog inventory: {exc}") from exc
    discovered = discover_skills(skills_dir, project_root=project_root)
    selected_registry = registry or load_registry()
    errors = validate_catalog_payload(
        payload,
        discovered=discovered,
        registry=selected_registry,
    )
    if errors:
        raise CatalogError("\n".join(errors))

    entries = tuple(
        SkillCatalogEntry(
            name=row["name"],
            path=row["path"],
            current_language=row["current"]["language"],
            current_framework=row["current"]["framework"],
            layer=row["layer"],
            binding=row["binding"],
            bindings=tuple(row["bindings"]),
            placement=row["placement"],
            readiness=row["readiness"],
            rationale=row["rationale"],
            ar3_foundation_member=row["ar3_foundation_member"],
            raw=dict(row),
        )
        for row in payload["skills"]
    )
    return SkillCatalog(
        path=inventory_path,
        entries=entries,
        ar3_de_flavor_names=frozenset(payload["ar3_de_flavor_members"]),
    )
