"""Per-root skill binding selection, rendering, and execution evidence.

Selection consumes the canonical host profile and capability registry.  Every
profile root is evaluated independently; aggregate stack data and filesystem
order are never used as selection tiebreakers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .capability_registry import CapabilityRegistry, load_registry
from .host_profile import validate_host_profile
from .skill_catalog import SkillCatalogEntry


KIND_PRECEDENCE = ("none", "language", "framework", "domain", "host")
_BINDING_ID = re.compile(r"^[a-z][a-z0-9-]*$")


class BindingLoadError(ValueError):
    """A skill/profile pair cannot be composed without guessing."""


@dataclass(frozen=True)
class BindingRender:
    """One root's deterministic composed procedure and evidence."""

    root: str
    selected_bindings: tuple[str, ...]
    content: str
    evidence: dict[str, Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def _binding_metadata(
    identifier: str,
    registry: CapabilityRegistry,
) -> dict[str, Any]:
    if not _BINDING_ID.fullmatch(identifier):
        raise BindingLoadError(f"invalid binding identifier: {identifier!r}")
    entry = registry.data.get("bindings", {}).get(identifier)
    if not isinstance(entry, dict):
        raise BindingLoadError(f"binding is not registered: {identifier!r}")
    required = {"kind", "layer", "languages", "frameworks"}
    missing = sorted(required - set(entry))
    if missing:
        raise BindingLoadError(f"binding {identifier!r} is missing registry fields: {missing}")
    kind = entry.get("kind")
    if kind not in KIND_PRECEDENCE:
        raise BindingLoadError(f"binding {identifier!r} has invalid kind {kind!r}")
    layer = entry.get("layer")
    layer_entry = registry.data.get("layers", {}).get(layer)
    if not isinstance(layer_entry, dict):
        raise BindingLoadError(f"binding {identifier!r} names unregistered layer {layer!r}")
    allowed_kinds = layer_entry.get("binding_kinds")
    if not isinstance(allowed_kinds, list) or kind not in allowed_kinds:
        raise BindingLoadError(
            f"binding {identifier!r} kind {kind!r} is not allowed by layer {layer!r}"
        )
    for field, section in (("languages", "languages"), ("frameworks", "frameworks")):
        values = entry.get(field)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise BindingLoadError(f"binding {identifier!r} {field} must be a list of strings")
        unknown = sorted(set(values) - registry.identifiers(section))
        if unknown:
            raise BindingLoadError(
                f"binding {identifier!r} {field} contains unregistered identifiers: {unknown}"
            )
    return entry


def _compatible(entry: Mapping[str, Any], root: Mapping[str, Any]) -> bool:
    kind = entry["kind"]
    if kind == "none":
        return True
    root_languages = set(root.get("languages", ()))
    root_frameworks = set(root.get("frameworks", ()))
    languages = set(entry.get("languages", ()))
    frameworks = set(entry.get("frameworks", ()))
    language_match = "any" in languages or bool(root_languages & languages)
    if kind == "language":
        return language_match
    framework_match = "any" in frameworks or bool(root_frameworks & frameworks)
    return language_match and framework_match


def _read_source(skill_root: Path, identifier: str) -> tuple[str, str, str]:
    relative = Path("SKILL.md") if identifier == "core" else Path("bindings") / f"{identifier}.md"
    path = (skill_root / relative).resolve()
    try:
        path.relative_to(skill_root.resolve())
    except ValueError as exc:
        raise BindingLoadError(f"binding path escapes skill root: {relative.as_posix()}") from exc
    if not path.is_file():
        raise BindingLoadError(
            f"selected binding {identifier!r} has no readable source {relative.as_posix()}"
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BindingLoadError(f"cannot read binding source {relative.as_posix()}: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BindingLoadError(f"binding source is not UTF-8: {relative.as_posix()}") from exc
    return relative.as_posix(), text, _sha256(data)


def _markdown_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n[ \t]*\n", text.strip()) if block.strip()]


def _normalized_block(block: str) -> str:
    return re.sub(r"\s+", " ", block).strip().casefold()


def _render(sources: Sequence[tuple[str, str, str, str]]) -> tuple[str, list[str]]:
    blocks: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for _identifier, _path, text, _digest in sources:
        for block in _markdown_blocks(text):
            normalized = _normalized_block(block)
            digest = _sha256(normalized.encode("utf-8"))
            if normalized in seen:
                duplicates.append(digest)
                continue
            seen.add(normalized)
            blocks.append(block)
    return "\n\n".join(blocks) + "\n", duplicates


def _validate_declared_bindings(
    entry: SkillCatalogEntry,
    registry: CapabilityRegistry,
) -> dict[str, dict[str, Any]]:
    declared = entry.bindings
    if not declared or declared[0] != "core" or entry.binding != "core":
        raise BindingLoadError(
            f"skill {entry.name!r} must declare primary binding 'core' first"
        )
    if len(declared) != len(set(declared)):
        raise BindingLoadError(f"skill {entry.name!r} declares duplicate bindings")
    metadata = {identifier: _binding_metadata(identifier, registry) for identifier in declared}
    core = metadata["core"]
    if core["kind"] != "none" or core["layer"] != "core":
        raise BindingLoadError("registry binding 'core' must be kind 'none' in layer 'core'")
    return metadata


def _select_for_root(
    entry: SkillCatalogEntry,
    root: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Any]],
    explicit: Sequence[str],
    registry: CapabilityRegistry,
) -> tuple[str, ...]:
    root_name = str(root.get("path", "?"))
    if len(explicit) != len(set(explicit)):
        raise BindingLoadError(f"profile root {root_name!r} repeats an explicit binding")
    unknown = sorted(set(explicit) - registry.identifiers("bindings"))
    if unknown:
        raise BindingLoadError(
            f"profile root {root_name!r} names unregistered explicit bindings: {unknown}"
        )
    undeclared = sorted(set(explicit) - set(entry.bindings))
    if undeclared:
        raise BindingLoadError(
            f"profile root {root_name!r} explicitly selects bindings not declared by "
            f"skill {entry.name!r}: {undeclared}"
        )
    for identifier in explicit:
        if identifier != "core" and not _compatible(metadata[identifier], root):
            raise BindingLoadError(
                f"profile root {root_name!r} has incompatible explicit binding {identifier!r}"
            )

    selected = ["core"]
    explicit_set = set(explicit)
    for kind in KIND_PRECEDENCE[1:]:
        candidates = sorted(
            identifier
            for identifier in entry.bindings
            if metadata[identifier]["kind"] == kind and _compatible(metadata[identifier], root)
        )
        if not candidates:
            continue
        if len(candidates) == 1:
            selected.append(candidates[0])
            continue
        chosen = sorted(explicit_set & set(candidates))
        if len(chosen) != 1:
            raise BindingLoadError(
                f"profile root {root_name!r} has ambiguous {kind} bindings {candidates}; "
                "select exactly one explicitly for that root"
            )
        selected.append(chosen[0])

    required_subjects = {
        language
        for language in root.get("languages", ())
        if registry.data["languages"].get(language, {}).get("binding_required") is True
    }
    covered_subjects: set[str] = set()
    for identifier in selected[1:]:
        binding_languages = set(metadata[identifier].get("languages", ()))
        if "any" in binding_languages:
            covered_subjects.update(required_subjects)
        else:
            covered_subjects.update(required_subjects & binding_languages)
    missing_subjects = sorted(required_subjects - covered_subjects)
    if len(entry.bindings) > 1 and required_subjects and len(selected) == 1:
        raise BindingLoadError(
            f"profile root {root_name!r} has zero compatible non-core bindings for "
            f"skill {entry.name!r} and subjects {sorted(required_subjects)}"
        )
    if len(entry.bindings) > 1 and missing_subjects:
        raise BindingLoadError(
            f"profile root {root_name!r} has subjects without compatible bindings for "
            f"skill {entry.name!r}: {missing_subjects}"
        )
    return tuple(selected)


# spec:portable-skill-layer-distribution::IM-7
def compose_skill_bindings(
    skill_root: Path | str,
    entry: SkillCatalogEntry,
    host_profile: dict[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
    explicit_bindings_by_root: Mapping[str, Sequence[str]] | None = None,
) -> tuple[BindingRender, ...]:
    """Compose one evidence-bearing procedure independently for every root."""
    selected_registry = registry or load_registry()
    profile_errors = validate_host_profile(host_profile, registry=selected_registry)
    if profile_errors:
        raise BindingLoadError(f"invalid canonical host profile: {'; '.join(profile_errors)}")
    metadata = _validate_declared_bindings(entry, selected_registry)
    root_path = Path(skill_root).resolve()
    choices = dict(explicit_bindings_by_root or {})
    for root_name, values in choices.items():
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or any(
            not isinstance(value, str) for value in values
        ):
            raise BindingLoadError(
                f"explicit bindings for profile root {root_name!r} must be a list of strings"
            )
    profile_root_names = {str(root["path"]) for root in host_profile["roots"]}
    unknown_roots = sorted(set(choices) - profile_root_names)
    if unknown_roots:
        raise BindingLoadError(f"explicit binding choices name unknown profile roots: {unknown_roots}")

    registry_hash = _canonical_hash(selected_registry.data)
    declared_hash = _canonical_hash(
        {"name": entry.name, "path": entry.path, "bindings": list(entry.bindings)}
    )
    renders: list[BindingRender] = []
    for root in host_profile["roots"]:
        root_name = str(root["path"])
        selected = _select_for_root(
            entry,
            root,
            metadata,
            tuple(choices.get(root_name, ())),
            selected_registry,
        )
        sources: list[tuple[str, str, str, str]] = []
        source_evidence: list[dict[str, Any]] = []
        for identifier in selected:
            relative, text, digest = _read_source(root_path, identifier)
            sources.append((identifier, relative, text, digest))
            binding = metadata[identifier]
            source_evidence.append(
                {
                    "binding": identifier,
                    "kind": binding["kind"],
                    "layer": binding["layer"],
                    "path": relative,
                    "precedence": KIND_PRECEDENCE.index(binding["kind"]),
                    "sha256": digest,
                }
            )
        rendered, duplicate_hashes = _render(sources)
        evidence = {
            "schema_version": 1,
            "skill": entry.name,
            "skill_path": entry.path,
            "root": root_name,
            "profile_sha256": host_profile["profile_sha256"],
            "registry_sha256": registry_hash,
            "declaration_sha256": declared_hash,
            "stack": {
                category: list(root.get(category, ()))
                for category in ("languages", "frameworks", "tools")
            },
            "explicit_bindings": list(choices.get(root_name, ())),
            "selected_bindings": list(selected),
            "sources": source_evidence,
            "deduplicated_block_sha256": duplicate_hashes,
            "rendered_sha256": _sha256(rendered.encode("utf-8")),
        }
        renders.append(
            BindingRender(
                root=root_name,
                selected_bindings=selected,
                content=rendered,
                evidence=evidence,
            )
        )
    return tuple(renders)
