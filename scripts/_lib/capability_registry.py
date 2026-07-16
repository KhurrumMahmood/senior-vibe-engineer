"""Canonical stack, capability, support, and completion-floor registry.

Consumers query this module instead of owning language/framework/tool enums.
The YAML document is the only place where identifiers are registered; adding a
future identifier does not require validator changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    REPO_ROOT / ".claude" / "skills" / "_common" / "capability-registry.yml"
)


class RegistryError(ValueError):
    """The registry or a payload using it violates the contract."""


@dataclass(frozen=True)
class CapabilityRegistry:
    data: dict[str, Any]
    path: Path

    @property
    def schema_version(self) -> int:
        return int(self.data["schema_version"])

    @property
    def contract_version(self) -> int:
        return int(self.data["contract_version"])

    def identifiers(self, section: str) -> frozenset[str]:
        block = self.data.get(section, {})
        return frozenset(block) if isinstance(block, dict) else frozenset()

    def language_for_extension(self, suffix: str) -> str | None:
        normalized = suffix.lower()
        for identifier, entry in self.data["languages"].items():
            if normalized in entry.get("extensions", []):
                return identifier
        return None

    def capability_names(self) -> frozenset[str]:
        names: set[str] = set()
        for family, values in self.data["capabilities"].items():
            names.update(f"{family}.{value}" for value in values)
        return frozenset(names)

    def validate_stack(self, stack: dict[str, Any], *, prefix: str = "stack") -> list[str]:
        errors: list[str] = []
        for field, section in (("languages", "languages"), ("frameworks", "frameworks"), ("tools", "tools")):
            values = stack.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                errors.append(f"{prefix}.{field} must be a list of strings")
                continue
            unknown = sorted(set(values) - self.identifiers(section))
            if unknown:
                errors.append(f"{prefix}.{field} contains unregistered identifiers: {unknown}")
        languages = set(stack.get("languages", []))
        for framework in stack.get("frameworks", []):
            if framework in {"any", "none"} or framework not in self.data["frameworks"]:
                continue
            allowed = set(self.data["frameworks"][framework].get("languages", []))
            if languages and not languages.intersection(allowed):
                errors.append(
                    f"{prefix}.frameworks contains {framework!r}, which requires one of {sorted(allowed)}"
                )
        return errors

    def validate_skill_contract(
        self,
        metadata: dict[str, Any],
        *,
        skill_dir: Path | None = None,
    ) -> list[str]:
        """Validate versioned capability fields; legacy metadata stays readable."""
        if "capability_contract" not in metadata:
            return []
        errors: list[str] = []
        version = metadata.get("capability_contract")
        if version != self.contract_version:
            errors.append(
                f"capability_contract must be {self.contract_version}, got {version!r}"
            )

        language = metadata.get("language")
        framework = metadata.get("framework")
        layer = metadata.get("layer")
        binding = metadata.get("binding")
        available_bindings = metadata.get("bindings", [])
        support = metadata.get("support")
        evidence = metadata.get("capability_evidence")
        support_evidence = metadata.get("support_evidence")
        scans = metadata.get("scans", [])
        capabilities = metadata.get("capabilities", [])

        if language not in self.identifiers("languages"):
            errors.append(f"language is not registered: {language!r}")
        if framework not in self.identifiers("frameworks"):
            errors.append(f"framework is not registered: {framework!r}")
        if layer not in self.identifiers("layers"):
            errors.append(f"layer is not registered: {layer!r}")
        if binding not in self.identifiers("bindings"):
            errors.append(f"binding is not registered: {binding!r}")
        elif layer in self.identifiers("layers"):
            binding_entry = self.data["bindings"][binding]
            if binding_entry.get("layer") != layer:
                errors.append(
                    f"binding {binding!r} belongs to layer {binding_entry.get('layer')!r}, not {layer!r}"
                )
            binding_languages = set(binding_entry.get("languages", []))
            if "any" not in binding_languages and language not in binding_languages:
                errors.append(f"binding {binding!r} does not support language {language!r}")
            binding_frameworks = set(binding_entry.get("frameworks", []))
            if "any" not in binding_frameworks and framework not in binding_frameworks:
                errors.append(f"binding {binding!r} does not support framework {framework!r}")

        states = self.data["support"]["states"]
        if support not in states:
            errors.append(f"support is not registered: {support!r}")
        if not isinstance(evidence, dict) or not evidence:
            errors.append("capability_evidence must be a non-empty subject-to-evidence mapping")
            evidence = {}
        else:
            unknown_subjects = sorted(set(evidence) - (self.identifiers("languages") - {"any"}) - {"procedure"})
            if unknown_subjects:
                errors.append(f"capability_evidence has unregistered subjects: {unknown_subjects}")
            for subject, entries in evidence.items():
                if not isinstance(entries, list) or not entries or any(
                    not isinstance(item, str) or not item.strip() for item in entries
                ):
                    errors.append(f"capability_evidence.{subject} must be a non-empty list of strings")

        if support in states:
            evaluated, reasons = self.evaluate_support(
                {"state": support, "evidence": support_evidence}
            )
            if evaluated != support:
                errors.append(
                    f"support {support!r} lacks required mechanical evidence: {reasons}"
                )

        if not isinstance(capabilities, list) or any(not isinstance(v, str) for v in capabilities):
            errors.append("capabilities must be a list of strings")
        else:
            unknown = sorted(set(capabilities) - self.capability_names())
            if unknown:
                errors.append(f"capabilities contains invalid names: {unknown}")

        if not isinstance(scans, list) or any(not isinstance(v, str) for v in scans):
            errors.append("scans must be a list of strings")
            scans = []
        for target in scans:
            entry = self.data["scan_targets"].get(target)
            if not entry:
                errors.append(f"scans target {target!r} has no registered adapter or shim")
                continue
            if not entry.get("adapter") and not entry.get("shim"):
                errors.append(f"scans target {target!r} has no adapter or shim")
            if not entry.get("evidence_contract"):
                errors.append(f"scans target {target!r} has no evidence contract")
            if target not in evidence:
                errors.append(f"scans target {target!r} has no matching capability_evidence entry")

        if scans and skill_dir is not None:
            scripts = skill_dir / "scripts"
            executable = scripts.is_dir() and any(
                path.is_file() and path.suffix in {".py", ".sh", ".js", ".mjs", ".ts"}
                for path in scripts.rglob("*")
            )
            if not executable:
                errors.append("scans claims require an executable skill script")

        if language == "any":
            declared = metadata.get("portable_subjects")
            if not isinstance(declared, list) or not declared:
                errors.append("language 'any' requires non-empty portable_subjects")
            else:
                unknown = sorted(set(declared) - (self.identifiers("languages") - {"any"}))
                if unknown:
                    errors.append(f"portable_subjects contains unregistered languages: {unknown}")
                missing_evidence = sorted(set(declared) - set(evidence))
                if missing_evidence:
                    errors.append(
                        "language 'any' requires capability_evidence entries for every portable subject: "
                        f"{missing_evidence}"
                    )
        if not isinstance(available_bindings, list) or any(
            not isinstance(value, str) for value in available_bindings
        ):
            errors.append("bindings must be a list of strings")
        else:
            unknown_bindings = sorted(set(available_bindings) - self.identifiers("bindings"))
            if unknown_bindings:
                errors.append(f"bindings contains unregistered identifiers: {unknown_bindings}")
        return errors

    def evaluate_support(self, claim: dict[str, Any]) -> tuple[str, list[str]]:
        """Mechanically demote a support claim when required evidence is stale/missing."""
        requested = claim.get("state", "unsupported")
        states = self.data["support"]["states"]
        if requested not in states:
            return "unsupported", [f"unregistered support state: {requested!r}"]
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        missing = [key for key in states[requested]["required_evidence"] if not evidence.get(key)]
        failures = []
        if evidence.get("fixture_results") not in (None, "pass"):
            failures.append("fixture_failure")
        if evidence.get("tool_version_in_range") is False:
            failures.append("tool_version_outside_verified_range")
        if evidence.get("platform_supported") is False:
            failures.append("unsupported_platform")
        reasons = [f"missing_required_evidence:{key}" for key in missing] + failures
        if reasons:
            return "unsupported", reasons
        return requested, []

    def transition_support(
        self,
        current: str,
        evidence: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """Promote at most one state, or demote immediately when evidence is stale."""
        states = self.data["support"]["states"]
        if current not in states:
            return "unsupported", [f"unregistered support state: {current!r}"]
        current_state, current_reasons = self.evaluate_support(
            {"state": current, "evidence": evidence}
        )
        if current != "unsupported" and current_state == "unsupported":
            return "unsupported", current_reasons
        next_state = self.data["support"]["transitions"]["promote"].get(current)
        if next_state is None:
            return current, []
        evaluated, reasons = self.evaluate_support(
            {"state": next_state, "evidence": evidence}
        )
        return (next_state, []) if evaluated == next_state else (current, reasons)

    def validate_completion_claims(self, claims: dict[str, Any]) -> list[str]:
        """Required floor cells must exist and be verified, never unsupported."""
        errors: list[str] = []
        floor_data = self.data["completion_floor"]
        stacks = floor_data["stacks"]
        stack_matrix = claims.get("stacks", {}) if isinstance(claims.get("stacks"), dict) else {}
        for stack_id, floor in stacks.items():
            stack_claims = stack_matrix.get(stack_id, {})
            for capability in floor["required"]:
                state = stack_claims.get(capability)
                if state != "verified":
                    errors.append(f"{stack_id}.{capability} must be verified, got {state!r}")
        surface_claims = claims.get("agent_surfaces", {}) if isinstance(claims.get("agent_surfaces"), dict) else {}
        for surface in floor_data["required_agent_surfaces"]:
            state = surface_claims.get(surface)
            if state != "verified":
                errors.append(f"agent_surfaces.{surface} must be verified, got {state!r}")
        return errors


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict) or not value:
        raise RegistryError(f"registry.{key} must be a non-empty mapping")
    return value


def load_registry(path: Path | None = None) -> CapabilityRegistry:
    registry_path = (path or DEFAULT_REGISTRY_PATH).resolve()
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"cannot load capability registry {registry_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError("capability registry must be a YAML mapping")
    if data.get("schema_version") != 1 or data.get("contract_version") != 1:
        raise RegistryError("unsupported capability registry or contract version")
    for key in (
        "schemas", "runtime", "languages", "frameworks", "tools", "project_root", "layers",
        "bindings", "capabilities", "scan_targets", "support", "agent_surfaces",
        "completion_floor",
    ):
        _require_mapping(data, key)

    language_ids = set(data["languages"])
    framework_ids = set(data["frameworks"])
    layer_ids = set(data["layers"])
    for binding, entry in data["bindings"].items():
        if not isinstance(entry, dict):
            raise RegistryError(f"bindings.{binding} must be a mapping")
        if entry.get("layer") not in layer_ids:
            raise RegistryError(f"bindings.{binding} names unknown layer")
        if not set(entry.get("languages", [])).issubset(language_ids):
            raise RegistryError(f"bindings.{binding} names unknown languages")
        if not set(entry.get("frameworks", [])).issubset(framework_ids):
            raise RegistryError(f"bindings.{binding} names unknown frameworks")
    support_states = set(data["support"]["states"])
    for target, entry in data["scan_targets"].items():
        if target not in language_ids:
            raise RegistryError(f"scan_targets.{target} is not a registered language")
        if not isinstance(entry, dict) or not (entry.get("adapter") or entry.get("shim")):
            raise RegistryError(f"scan_targets.{target} requires an adapter or shim")
        if entry.get("support") not in support_states:
            raise RegistryError(f"scan_targets.{target} names unknown support state")
    for surface, entry in data["agent_surfaces"].items():
        if not isinstance(entry, dict) or not str(entry.get("minimum_surface_version", "")).strip():
            raise RegistryError(f"agent_surfaces.{surface} requires a pinned minimum surface version")
        if not str(entry.get("discovery", "")).strip():
            raise RegistryError(f"agent_surfaces.{surface} requires a discovery contract")
    return CapabilityRegistry(data=data, path=registry_path)


def registry_values(section: str, *, registry: CapabilityRegistry | None = None) -> frozenset[str]:
    return (registry or load_registry()).identifiers(section)


def sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))
