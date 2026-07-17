"""Deterministic IM-13 portfolio and discovery-state snapshots.

This module describes portfolio content and activation sets only.  It does not
materialize files, mutate a manifest, or implement installer transactions.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .capability_registry import CapabilityRegistry, load_registry
from .skill_catalog import SkillCatalogEntry, load_catalog


READY_STATES = frozenset({"foundation-ready", "exemplar-ready"})
ROUTERS = ("which-shape", "which-skill")
ACTIVATION_MODES = ("router-only", "full-discovery")
SURFACE_CONTRACTS: dict[str, dict[str, str]] = {
    "augment": {
        "generated_identity": ".augment/rules/imported/{public_name}/SKILL.md",
        "public_syntax": "use skill {public_name}",
    },
    "claude-code": {
        "generated_identity": ".claude/skills/{public_name}/SKILL.md",
        "public_syntax": "/{public_name}",
    },
    "codex": {
        "generated_identity": "skills/{public_name}/SKILL.md",
        "plugin": "engineering-skills",
        "public_syntax": "$engineering-skills:{public_name}",
    },
    "cursor": {
        "generated_identity": ".cursor/rules/{public_name}/SKILL.mdc",
        "public_syntax": "use skill {public_name}",
    },
    "gemini": {
        "generated_identity": ".gemini/skills/{public_name}/SKILL.md",
        "public_syntax": "use skill {public_name}",
    },
}
_PUBLIC_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSIONED_ALIAS = re.compile(r"^(.+)-v([1-9][0-9]*)$")


class PortfolioSnapshotError(ValueError):
    """The snapshot inputs cannot describe an exact deterministic state."""


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _markdown_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n[ \t]*\n", text.strip()) if block.strip()]


def _render_sources(sources: Sequence[bytes]) -> bytes:
    blocks: list[str] = []
    seen: set[str] = set()
    for content in sources:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PortfolioSnapshotError("portfolio source is not UTF-8") from exc
        for block in _markdown_blocks(text):
            normalized = re.sub(r"\s+", " ", block).strip().casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            blocks.append(block)
    return ("\n\n".join(blocks) + "\n").encode("utf-8")


def _resolve_aliases(
    aliases: Sequence[Mapping[str, Any]], canonical_names: set[str]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    direct: dict[str, str] = {}
    for index, raw in enumerate(aliases):
        if not isinstance(raw, Mapping) or set(raw) != {"name", "target", "version"}:
            raise PortfolioSnapshotError(
                f"aliases[{index}] must contain exactly name, target, and version"
            )
        name = raw["name"]
        target = raw["target"]
        version = raw["version"]
        match = _VERSIONED_ALIAS.fullmatch(name) if isinstance(name, str) else None
        if (
            match is None
            or not _PUBLIC_NAME.fullmatch(name)
            or not isinstance(version, int)
            or isinstance(version, bool)
            or int(match.group(2)) != version
        ):
            raise PortfolioSnapshotError(
                f"alias {name!r} must be a safe public name ending in its -v<version>"
            )
        if not isinstance(target, str):
            raise PortfolioSnapshotError(f"alias {name!r} target must be a string")
        if name in canonical_names or name in direct:
            raise PortfolioSnapshotError(f"alias collision: {name!r}")
        direct[name] = target
        rows.append({"name": name, "target": target, "version": version})

    known = canonical_names | set(direct)
    resolved: dict[str, str] = {}
    for name, target in direct.items():
        if target not in known:
            raise PortfolioSnapshotError(f"alias {name!r} has stale target {target!r}")
        visited = {name}
        while target in direct:
            if target in visited:
                raise PortfolioSnapshotError(f"alias cycle includes {name!r}")
            visited.add(target)
            target = direct[target]
        resolved[name] = target
    return sorted(rows, key=lambda row: row["name"]), resolved


def _binding_source(skill_root: Path, entry: SkillCatalogEntry, binding: str) -> Path:
    if binding == "core" or (entry.layer != "core" and binding == entry.binding):
        return skill_root / "SKILL.md"
    return skill_root / "bindings" / f"{binding}.md"


def _selected_bindings(
    entry: SkillCatalogEntry, portfolio: str, skill_root: Path
) -> tuple[str, ...]:
    if portfolio != "django" or entry.readiness not in READY_STATES:
        return (entry.binding,)
    if entry.layer != "core":
        return (entry.binding,)
    compatible = [
        binding
        for binding in entry.bindings
        if binding in {"core", "python", "django"}
        and _binding_source(skill_root, entry, binding).is_file()
    ]
    return tuple(compatible)


def _catalog_row(
    project_root: Path,
    entry: SkillCatalogEntry,
    portfolio: str,
    aliases_by_target: Mapping[str, Sequence[str]],
) -> tuple[dict[str, Any], bytes]:
    skill_root = project_root / Path(entry.path).parent
    canonical_path = skill_root / "SKILL.md"
    source = canonical_path.read_bytes()
    selected = _selected_bindings(entry, portfolio, skill_root)
    selected_sources: list[bytes] = []
    for binding in selected:
        path = _binding_source(skill_root, entry, binding)
        if not path.is_file():
            raise PortfolioSnapshotError(
                f"{portfolio}: {entry.name!r} selected missing binding source {path}"
            )
        content = path.read_bytes()
        selected_sources.append(content)
    rendered = _render_sources(selected_sources)
    return (
        {
            "aliases": sorted(aliases_by_target.get(entry.name, ())),
            "layer": entry.layer,
            "name": entry.name,
            "rendered_sha256": _sha256(rendered),
            "selected_bindings": list(selected),
            "source_path": entry.path,
            "source_sha256": _sha256(source),
        },
        rendered,
    )


def _framework_hits(
    rows_and_content: Sequence[tuple[dict[str, Any], bytes]],
    registry: CapabilityRegistry,
) -> list[dict[str, str]]:
    terms = sorted(
        {
            str(term).casefold()
            for framework, contract in registry.data["frameworks"].items()
            if framework not in {"any", "none"}
            for term in contract.get("core_leakage_terms", ())
        }
    )
    hits: list[dict[str, str]] = []
    for row, content in rows_and_content:
        text = content.decode("utf-8").casefold()
        for term in terms:
            if re.search(rf"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])", text):
                hits.append({"name": row["name"], "term": term})
    return hits


def _surface_projection(
    _surface: str,
    canonical: Sequence[str],
    public: Sequence[str],
    activation_records: Sequence[Mapping[str, str]],
    host_owned: Sequence[str],
    *,
    mode: str,
) -> dict[str, Any]:
    public_names = sorted(set(public))
    return {
        "activation_records": [dict(record) for record in activation_records],
        "canonical_procedures": sorted(set(canonical)),
        "host_owned_discovery": sorted(set(host_owned)),
        "mode": mode,
        "public_names": public_names,
    }


def _surface_states(
    surface: str,
    portfolio_names: Sequence[str],
    aliases: Mapping[str, str],
    host_owned: Sequence[str],
) -> dict[str, Any]:
    non_router = next(name for name in portfolio_names if name not in ROUTERS)
    router_only = _surface_projection(
        surface, ROUTERS, ROUTERS, (), host_owned, mode="router-only"
    )
    named_record = {"public_name": non_router, "canonical_target": non_router}
    named = _surface_projection(
        surface,
        (*ROUTERS, non_router),
        (*ROUTERS, non_router),
        (named_record,),
        host_owned,
        mode="router-only",
    )
    usable_aliases = sorted(
        (name, target)
        for name, target in aliases.items()
        if target in portfolio_names and target not in ROUTERS
    )
    if not aliases:
        alias_state: dict[str, Any] = {
            "available": False,
            "dependency": "aliases-v1 has no public alias rows",
        }
        cumulative_state = dict(alias_state)
    elif not usable_aliases:
        alias_state = {
            "available": False,
            "dependency": "aliases-v1 has no non-router alias rows for this portfolio",
        }
        cumulative_state = dict(alias_state)
    else:
        alias_name, target = usable_aliases[0]
        alias_record = {"public_name": alias_name, "canonical_target": target}
        alias_state = _surface_projection(
            surface,
            (*ROUTERS, target),
            (*ROUTERS, alias_name),
            (alias_record,),
            host_owned,
            mode="router-only",
        )
        canonical_record = {"public_name": target, "canonical_target": target}
        cumulative_state = _surface_projection(
            surface,
            (*ROUTERS, target),
            (*ROUTERS, target, alias_name),
            (canonical_record, alias_record),
            host_owned,
            mode="router-only",
        )
    portfolio_aliases = sorted(
        name for name, target in aliases.items() if target in portfolio_names
    )
    full = _surface_projection(
        surface,
        portfolio_names,
        (*portfolio_names, *portfolio_aliases),
        (),
        host_owned,
        mode="full-discovery",
    )
    return {
        "host_owned_discovery": sorted(set(host_owned)),
        "states": {
            "cumulative-canonical-alias": cumulative_state,
            "full-discovery": full,
            "named-alias": alias_state,
            "named-non-router": named,
            "router-only": router_only,
        },
    }


def build_portfolio_snapshots(
    project_root: Path | str,
    *,
    aliases: Sequence[Mapping[str, Any]] = (),
    host_owned_by_surface: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Build exact content and discovery snapshots for the three IM-13 portfolios."""
    # spec:portable-skill-layer-distribution::IM-13
    root = Path(project_root).resolve()
    registry = load_registry(root / ".claude/skills/_common/capability-registry.yml")
    catalog = load_catalog(
        root / ".claude/skills/_common/skill-catalog-inventory.yml",
        skills_dir=root / ".claude/skills",
        project_root=root,
        registry=registry,
    )
    canonical_names = {entry.name for entry in catalog.entries}
    alias_rows, resolved_aliases = _resolve_aliases(aliases, canonical_names)
    aliases_by_target: dict[str, list[str]] = {}
    for alias, target in resolved_aliases.items():
        aliases_by_target.setdefault(target, []).append(alias)

    host_sets = dict(host_owned_by_surface or {})
    unknown_surfaces = sorted(set(host_sets) - set(SURFACE_CONTRACTS))
    if unknown_surfaces:
        raise PortfolioSnapshotError(f"unknown host-owned surfaces: {unknown_surfaces}")
    portfolios: dict[str, Any] = {}
    for portfolio, entries, profile_stack, claim in (
        (
            "core-only",
            [entry for entry in catalog.entries if entry.readiness in READY_STATES],
            {"frameworks": [], "languages": []},
            "portable-core-content",
        ),
        (
            "typescript-react",
            [entry for entry in catalog.entries if entry.readiness in READY_STATES],
            {"frameworks": ["react"], "languages": ["typescript"]},
            "projection-and-binding-selection-only",
        ),
        (
            "django",
            list(catalog.entries),
            {"frameworks": ["django"], "languages": ["python"]},
            "ar1-current-applicable-catalog-preservation",
        ),
    ):
        rows_and_content = [
            _catalog_row(root, entry, portfolio, aliases_by_target)
            for entry in sorted(entries, key=lambda item: item.name)
        ]
        rows = [row for row, _content in rows_and_content]
        names = [row["name"] for row in rows]
        portfolio_alias_rows = [
            {
                "canonical_target": target,
                "public_name": name,
                "version": next(row["version"] for row in alias_rows if row["name"] == name),
            }
            for name, target in sorted(resolved_aliases.items())
            if target in names
        ]
        surface_snapshots = {
            surface: _surface_states(
                surface,
                names,
                resolved_aliases,
                host_sets.get(surface, ()),
            )
            for surface in sorted(SURFACE_CONTRACTS)
        }
        portfolio_row: dict[str, Any] = {
            "aliases": portfolio_alias_rows,
            "catalog": rows,
            "default_activation": list(ROUTERS),
            "framework_native_content_hits": _framework_hits(rows_and_content, registry),
            "non_discovered_catalog": names,
            "profile_stack": profile_stack,
            "selected_non_core_bindings": sorted(
                {
                    binding
                    for row in rows
                    for binding in row["selected_bindings"]
                    if binding != "core"
                }
            ),
            "selection_claim": claim,
            "surfaces": surface_snapshots,
        }
        if portfolio == "django":
            portfolio_row["ar1_applicable_names"] = names
            portfolio_row["ar1_names_sha256"] = _sha256(
                "".join(f"{name}\n" for name in names).encode("utf-8")
            )
        portfolios[portfolio] = portfolio_row

    return {
        "activation_modes": list(ACTIVATION_MODES),
        "alias_authority": alias_rows,
        "portfolios": portfolios,
        "schema_version": 1,
        "surface_contracts": SURFACE_CONTRACTS,
    }
