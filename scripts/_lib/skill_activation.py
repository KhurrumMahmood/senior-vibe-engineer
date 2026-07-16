"""One profile-derived skill activation decision for every routing surface.

Activation is applicability, not ranking.  The decision combines the canonical
host profile, registry-owned layer/binding compatibility, optional task
requirements, and the host manifest's explicit name-level opt-outs.  Routers
and manifests project this result instead of owning separate predicates.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from installer_selection import select_install

from .capability_registry import CapabilityRegistry, load_registry
from .host_profile import validate_host_profile
from .yaml_frontmatter import FrontmatterError, parse


class ActivationError(ValueError):
    """The activation input cannot produce a trustworthy decision."""


@dataclass(frozen=True)
class ActivationDecision:
    """Deterministic applicability result for one skill."""

    skill: str
    active: bool
    reasons: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]
    matched_roots: tuple[str, ...]
    layer: str
    binding: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "active": self.active,
            "reasons": list(self.reasons),
            "exclusion_reasons": list(self.exclusion_reasons),
            "matched_roots": list(self.matched_roots),
            "layer": self.layer,
            "binding": self.binding,
        }


def _read_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ActivationError(f"{label} {path} must contain a JSON object")
    return payload


def load_host_profile(
    project_root: Path | str,
    *,
    profile_path: Path | str | None = None,
    registry: CapabilityRegistry | None = None,
) -> dict[str, Any] | None:
    """Load and validate the canonical durable host profile, when present."""
    selected_registry = registry or load_registry()
    explicit = profile_path is not None
    path = (
        Path(profile_path)
        if explicit
        else Path(project_root) / ".engineering" / "project" / "host-profile.json"
    )
    if not path.is_file():
        if explicit:
            raise ActivationError(f"host profile does not exist: {path}")
        return None
    payload = _read_json_mapping(path, label="host profile")
    errors = validate_host_profile(payload, registry=selected_registry)
    if errors:
        raise ActivationError(f"invalid host profile {path}: {'; '.join(errors)}")
    return payload


def load_manifest(project_root: Path | str) -> dict[str, Any]:
    """Read the host manifest without treating malformed state as an opt-in."""
    path = Path(project_root) / ".engineering" / "manifest.json"
    if not path.is_file():
        return {}
    return _read_json_mapping(path, label="activation manifest")


def load_skill_metadata(skills_dir: Path | str) -> list[dict[str, Any]]:
    """Load flat-catalog skill metadata in deterministic name order."""
    rows: list[dict[str, Any]] = []
    for skill_md in sorted(Path(skills_dir).glob("*/SKILL.md")):
        try:
            metadata = parse(skill_md.read_text(encoding="utf-8"), path=skill_md).metadata
        except (OSError, UnicodeDecodeError, FrontmatterError) as exc:
            raise ActivationError(f"cannot load skill metadata {skill_md}: {exc}") from exc
        if not isinstance(metadata, dict) or not metadata.get("name"):
            raise ActivationError(f"skill metadata {skill_md} has no name")
        row = dict(metadata)
        row["_skill_dir"] = str(skill_md.parent)
        rows.append(row)
    return rows


def _reason_map(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(reason) for key, reason in value.items()}
    if isinstance(value, list):
        return {str(item): "" for item in value}
    return {}


def _manual_exclusion(manifest: dict[str, Any], skill: str) -> str | None:
    block = manifest.get("skills")
    if not isinstance(block, dict):
        return None
    default = block.get("default")
    if default not in {"active", "inactive"}:
        default = "active"
    active = _reason_map(block.get("active"))
    inactive = _reason_map(block.get("inactive"))
    if default == "inactive" and skill not in active:
        return "host activation manifest does not allowlist this skill"
    if default == "active" and skill in inactive:
        detail = inactive[skill].strip()
        return f"host activation manifest opt-out: {detail}" if detail else "host activation manifest opt-out"
    return None


def _infer_layer(metadata: dict[str, Any]) -> str:
    declared = metadata.get("layer")
    if isinstance(declared, str) and declared:
        return declared
    framework = str(metadata.get("framework", "any"))
    language = str(metadata.get("language", "any"))
    if framework not in {"any", "none", ""}:
        return "framework"
    if language not in {"any", ""}:
        return "language"
    return "core"


def _infer_binding(
    metadata: dict[str, Any],
    registry: CapabilityRegistry,
) -> tuple[str, str | None]:
    declared = metadata.get("binding")
    if isinstance(declared, str) and declared:
        return declared, None
    framework = str(metadata.get("framework", "any"))
    language = str(metadata.get("language", "any"))
    if framework not in {"any", "none", ""}:
        candidates = [
            identifier
            for identifier, entry in registry.data["bindings"].items()
            if entry.get("kind") == "framework"
            and framework in entry.get("frameworks", [])
        ]
    elif language not in {"any", ""}:
        candidates = [
            identifier
            for identifier, entry in registry.data["bindings"].items()
            if entry.get("kind") == "language"
            and language in entry.get("languages", [])
        ]
    else:
        candidates = ["core"]
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return "", f"no registered binding matches language={language!r}, framework={framework!r}"
    return "", f"ambiguous inferred bindings: {sorted(candidates)}"


def _root_selections(
    profile: dict[str, Any],
    manifest: dict[str, Any],
    registry: CapabilityRegistry,
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    explicit_block = manifest.get("capability_selection")
    explicit_bindings = (
        [str(item) for item in explicit_block.get("bindings", [])]
        if isinstance(explicit_block, dict) and isinstance(explicit_block.get("bindings"), list)
        else []
    )
    declared_layers = (
        {str(item) for item in explicit_block.get("layers", [])}
        if isinstance(explicit_block, dict) and isinstance(explicit_block.get("layers"), list)
        else set()
    )
    declared_bindings = set(explicit_bindings)
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for root in profile["roots"]:
        stack = {
            "languages": list(root.get("languages", [])),
            "frameworks": list(root.get("frameworks", [])),
            "tools": list(root.get("tools", [])),
        }
        try:
            selection = select_install(
                stack,
                registry=registry,
                explicit_bindings=explicit_bindings,
            )
        except ValueError as exc:
            raise ActivationError(
                f"cannot select activation for profile root {root.get('path', '?')!r}: {exc}"
            ) from exc
        if declared_layers:
            selection["layers"] = sorted(set(selection["layers"]) & declared_layers)
        if declared_bindings:
            selection["bindings"] = [
                value for value in selection["bindings"] if value in declared_bindings or value == "core"
            ]
        rows.append((str(root["path"]), stack, selection))
    return rows


# spec:portable-host-profile-routing::IM-5
def decide_skill_activation(
    metadata: dict[str, Any],
    *,
    project_root: Path | str,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    registry: CapabilityRegistry | None = None,
    required_capabilities: Iterable[str] = (),
    required_layers: Iterable[str] = (),
    required_bindings: Iterable[str] = (),
) -> ActivationDecision:
    """Return the canonical activation decision for one skill.

    A missing profile preserves the migration-era manual activation behavior;
    once the canonical profile exists, a skill must match at least one declared
    root's language/framework and selected layer/binding.  Manual activation
    can narrow that result but cannot make an incompatible skill applicable.
    """
    selected_registry = registry or load_registry()
    skill = str(metadata.get("name", "")).strip()
    if not skill:
        raise ActivationError("skill metadata has no name")
    selected_manifest = manifest if manifest is not None else load_manifest(project_root)
    selected_profile = profile if profile is not None else load_host_profile(
        project_root,
        registry=selected_registry,
    )
    layer = _infer_layer(metadata)
    binding, binding_error = _infer_binding(metadata, selected_registry)
    exclusions: list[str] = []
    reasons: list[str] = []
    matched_roots: list[str] = []

    manual = _manual_exclusion(selected_manifest, skill)
    if manual:
        exclusions.append(manual)
    else:
        reasons.append("host activation manifest permits this skill")

    if layer not in selected_registry.identifiers("layers"):
        exclusions.append(f"unregistered skill layer: {layer!r}")
    if binding_error:
        exclusions.append(binding_error)
    elif binding not in selected_registry.identifiers("bindings"):
        exclusions.append(f"unregistered skill binding: {binding!r}")

    language = str(metadata.get("language", "any"))
    framework = str(metadata.get("framework", "any"))
    if language not in selected_registry.identifiers("languages"):
        exclusions.append(f"unregistered skill language: {language!r}")
    if framework not in selected_registry.identifiers("frameworks"):
        exclusions.append(f"unregistered skill framework: {framework!r}")

    capabilities = {
        str(item) for item in metadata.get("capabilities", [])
        if isinstance(item, str)
    }
    requested_capabilities = {str(item) for item in required_capabilities}
    unknown_skill_capabilities = sorted(
        capabilities - selected_registry.capability_names()
    )
    if unknown_skill_capabilities:
        exclusions.append(
            f"skill declares unregistered capabilities: {unknown_skill_capabilities}"
        )
    unknown_capabilities = sorted(
        requested_capabilities - selected_registry.capability_names()
    )
    if unknown_capabilities:
        exclusions.append(f"requested capabilities are not registered: {unknown_capabilities}")
    missing_capabilities = sorted(requested_capabilities - capabilities)
    if missing_capabilities:
        exclusions.append(f"skill does not declare required capabilities: {missing_capabilities}")
    elif requested_capabilities:
        reasons.append(f"declares required capabilities: {sorted(requested_capabilities)}")

    requested_layers = {str(item) for item in required_layers}
    unknown_requested_layers = sorted(
        requested_layers - selected_registry.identifiers("layers")
    )
    if unknown_requested_layers:
        exclusions.append(f"requested layers are not registered: {unknown_requested_layers}")
    if requested_layers and layer not in requested_layers:
        exclusions.append(
            f"skill layer {layer!r} does not match required layers {sorted(requested_layers)}"
        )
    elif requested_layers:
        reasons.append(f"matches required layer: {layer}")

    available_bindings = {
        str(item) for item in metadata.get("bindings", [])
        if isinstance(item, str)
    }
    if binding:
        available_bindings.add(binding)
    unknown_available_bindings = sorted(
        available_bindings - selected_registry.identifiers("bindings")
    )
    if unknown_available_bindings:
        exclusions.append(
            f"skill advertises unregistered bindings: {unknown_available_bindings}"
        )
    requested_bindings = {str(item) for item in required_bindings}
    unknown_requested_bindings = sorted(
        requested_bindings - selected_registry.identifiers("bindings")
    )
    if unknown_requested_bindings:
        exclusions.append(
            f"requested bindings are not registered: {unknown_requested_bindings}"
        )
    if requested_bindings and not requested_bindings.intersection(available_bindings):
        exclusions.append(
            "skill bindings do not match required bindings: "
            f"skill={sorted(available_bindings)}, required={sorted(requested_bindings)}"
        )
    elif requested_bindings:
        reasons.append(
            f"matches required bindings: {sorted(requested_bindings.intersection(available_bindings))}"
        )

    if selected_profile is None:
        reasons.append("canonical host profile absent; using migration-era manual activation only")
    elif not binding_error and layer in selected_registry.identifiers("layers"):
        portable_subjects = {
            str(item) for item in metadata.get("portable_subjects", [])
            if isinstance(item, str)
        }
        unknown_subjects = sorted(
            portable_subjects
            - (selected_registry.identifiers("languages") - {"any"})
        )
        if unknown_subjects:
            exclusions.append(
                f"portable_subjects contains unregistered languages: {unknown_subjects}"
            )
        strict_any = metadata.get("capability_contract") is not None and language == "any"
        for root_name, stack, selection in _root_selections(
            selected_profile,
            selected_manifest,
            selected_registry,
        ):
            languages = set(stack["languages"])
            frameworks = set(stack["frameworks"])
            language_ok = (
                bool(languages.intersection(portable_subjects))
                if strict_any
                else language == "any" or language in languages
            )
            framework_ok = framework in {"any", "none"} or framework in frameworks
            layer_ok = layer in selection["layers"]
            binding_ok = binding in selection["bindings"]
            if language_ok and framework_ok and layer_ok and binding_ok:
                matched_roots.append(root_name)
        if matched_roots:
            reasons.append(
                f"profile-compatible on roots {sorted(matched_roots)} via layer={layer}, binding={binding}"
            )
        else:
            exclusions.append(
                "no profile root matches the skill's language/framework/layer/binding "
                f"(language={language}, framework={framework}, layer={layer}, binding={binding})"
            )

    unique_reasons = tuple(dict.fromkeys(reasons))
    unique_exclusions = tuple(dict.fromkeys(exclusions))
    return ActivationDecision(
        skill=skill,
        active=not unique_exclusions,
        reasons=unique_reasons,
        exclusion_reasons=unique_exclusions,
        matched_roots=tuple(sorted(set(matched_roots))),
        layer=layer,
        binding=binding,
    )


def decide_catalog_activation(
    skills: Iterable[dict[str, Any]],
    *,
    project_root: Path | str,
    profile: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    registry: CapabilityRegistry | None = None,
    required_capabilities: Iterable[str] = (),
    required_layers: Iterable[str] = (),
    required_bindings: Iterable[str] = (),
) -> dict[str, ActivationDecision]:
    """Resolve a catalog through exactly the same decision inputs."""
    selected_registry = registry or load_registry()
    selected_manifest = manifest if manifest is not None else load_manifest(project_root)
    selected_profile = profile if profile is not None else load_host_profile(
        project_root,
        registry=selected_registry,
    )
    decisions = [
        decide_skill_activation(
            metadata,
            project_root=project_root,
            profile=selected_profile,
            manifest=selected_manifest,
            registry=selected_registry,
            required_capabilities=required_capabilities,
            required_layers=required_layers,
            required_bindings=required_bindings,
        )
        for metadata in skills
    ]
    return {decision.skill: decision for decision in sorted(decisions, key=lambda item: item.skill)}
