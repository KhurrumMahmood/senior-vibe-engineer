"""Canonical stack, capability, support, and completion-floor registry.

Consumers query this module instead of owning language/framework/tool enums.
The YAML document is the only place where identifiers are registered; adding a
future identifier does not require validator changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

import yaml

from _lib.support_evidence import (
    attested_paths,
    canonical_evidence_hash,
    validate_file_attestations,
    validate_support_evidence,
)


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
        scan_implementations = metadata.get("scan_implementations", {})
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
        evidence_root = skill_dir or REPO_ROOT
        capability_test_paths_by_subject: dict[str, set[Path]] = {}
        if not isinstance(evidence, dict) or not evidence:
            errors.append("capability_evidence must be a non-empty subject-to-evidence mapping")
            evidence = {}
        else:
            unknown_subjects = sorted(set(evidence) - (self.identifiers("languages") - {"any"}) - {"procedure"})
            if unknown_subjects:
                errors.append(f"capability_evidence has unregistered subjects: {unknown_subjects}")
            for subject, entries in evidence.items():
                errors.extend(
                    validate_file_attestations(
                        entries,
                        root=evidence_root,
                        field=f"capability_evidence.{subject}",
                        required_kinds={"test"},
                    )
                )
                capability_test_paths_by_subject[subject] = attested_paths(
                    entries, root=evidence_root, kind="test"
                )

        if support in states:
            evaluated, reasons = self.evaluate_support(
                {"state": support, "evidence": support_evidence},
                root=evidence_root,
                execute=False,
                expected_claim=(
                    {"kind": "skill", "id": skill_dir.name}
                    if skill_dir is not None
                    else None
                ),
                required_test_paths_by_subject=capability_test_paths_by_subject,
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
        if not isinstance(scan_implementations, dict):
            errors.append("scan_implementations must be a target-to-attestation mapping")
            scan_implementations = {}
        unknown_implementations = sorted(set(scan_implementations) - set(scans))
        if unknown_implementations:
            errors.append(
                f"scan_implementations names undeclared scan targets: {unknown_implementations}"
            )
        for target in sorted(set(scans) - set(scan_implementations)):
            errors.append(
                f"scans target {target!r} requires an explicit scan_implementations "
                "attestation for its executable skill script"
            )
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
            implementation = scan_implementations.get(target)
            if isinstance(implementation, dict):
                mechanism = entry.get("adapter") or entry.get("shim")
                if implementation.get("mechanism") != mechanism:
                    errors.append(
                        f"scan_implementations.{target}.mechanism must be {mechanism!r}"
                    )
                attestation = {
                    "kind": "script",
                    "path": implementation.get("path"),
                    "sha256": implementation.get("sha256"),
                }
                errors.extend(
                    validate_file_attestations(
                        [attestation],
                        root=evidence_root,
                        field=f"scan_implementations.{target}",
                        required_kinds={"script"},
                    )
                )
                script_path = implementation.get("path")
                if not isinstance(script_path, str) or not Path(script_path).parts or Path(script_path).parts[0] != "scripts":
                    errors.append(
                        f"scan_implementations.{target}.path must be under the skill scripts directory"
                    )
                elif Path(script_path).suffix not in {
                    ".py",
                    ".sh",
                    ".js",
                    ".mjs",
                    ".ts",
                }:
                    errors.append(
                        f"scan_implementations.{target}.path must use an executable script suffix"
                    )
                implementation_paths = attested_paths(
                    [attestation], root=evidence_root, kind="script"
                )
                target_test_paths = capability_test_paths_by_subject.get(target, set())
                if implementation_paths != target_test_paths:
                    errors.append(
                        f"scan_implementations.{target} must itself be the distinct "
                        "capability test executed for that scan target"
                    )
                support_artifacts = (
                    support_evidence.get("artifacts")
                    if isinstance(support_evidence, dict)
                    else None
                )
                if (
                    not isinstance(support_artifacts, list)
                    or attestation not in support_artifacts
                ):
                    errors.append(
                        f"scan_implementations.{target} must be identically attested as a support artifact"
                    )
            if support in states:
                requested_rank = states[support]["rank"]
                ceiling_rank = states[entry["support"]]["rank"]
                if requested_rank > ceiling_rank:
                    errors.append(
                        f"scans target {target!r} support ceiling is {entry['support']!r}, "
                        f"not requested {support!r}"
                    )

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
                declared_paths = [
                    next(iter(capability_test_paths_by_subject.get(subject, set())), None)
                    for subject in declared
                ]
                if None not in declared_paths and len(declared_paths) != len(set(declared_paths)):
                    errors.append(
                        "language 'any' requires a distinct executable integration test per portable subject"
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

    def evaluate_support(
        self,
        claim: dict[str, Any],
        *,
        root: Path | None = None,
        execute: bool = True,
        ceiling: str | None = None,
        expected_claim: dict[str, str] | None = None,
        required_test_paths_by_subject: dict[str, set[Path]] | None = None,
    ) -> tuple[str, list[str]]:
        """Mechanically demote a support claim when required evidence is stale/missing."""
        requested = claim.get("state", "unsupported")
        states = self.data["support"]["states"]
        if requested not in states:
            return "unsupported", [f"unregistered support state: {requested!r}"]
        if requested == "unsupported":
            return requested, []
        if ceiling not in (None, *states):
            return "unsupported", [f"unregistered support ceiling: {ceiling!r}"]
        if ceiling is not None and states[requested]["rank"] > states[ceiling]["rank"]:
            return "unsupported", [f"support_ceiling:{ceiling}"]
        reasons = validate_support_evidence(
            claim.get("evidence"),
            root=(root or REPO_ROOT).resolve(),
            execute=execute,
            tool_policies=self.data["evidence_tools"],
            expected_claim=expected_claim,
            required_test_paths_by_subject=required_test_paths_by_subject,
            verification_issuer=self.data["support"]["verification_issuer"],
            require_verified_issuer=requested == "verified",
        )
        if reasons:
            return "unsupported", reasons
        return requested, []

    def transition_support(
        self,
        current: str,
        evidence: dict[str, Any],
        *,
        root: Path | None = None,
        ceiling: str | None = None,
    ) -> tuple[str, list[str]]:
        """Promote at most one state, or demote immediately when evidence is stale."""
        states = self.data["support"]["states"]
        if current not in states:
            return "unsupported", [f"unregistered support state: {current!r}"]
        current_state, current_reasons = self.evaluate_support(
            {"state": current, "evidence": evidence},
            root=root,
            execute=True,
            ceiling=ceiling,
        )
        if current != "unsupported" and current_state == "unsupported":
            return "unsupported", current_reasons
        next_state = self.data["support"]["transitions"]["promote"].get(current)
        if next_state is None:
            return current, []
        evaluated, reasons = self.evaluate_support(
            {"state": next_state, "evidence": evidence},
            root=root,
            execute=True,
            ceiling=ceiling,
        )
        return (next_state, []) if evaluated == next_state else (current, reasons)

    def validate_completion_claims(
        self,
        claims: dict[str, Any],
        *,
        evidence_root: Path | None = None,
        execute_evidence: bool = True,
    ) -> list[str]:
        """Required floor cells must exist and be verified, never unsupported."""
        errors: list[str] = []
        root = (evidence_root or REPO_ROOT).resolve()
        evidence_cache: dict[tuple[str, str], tuple[str, list[str]]] = {}
        evidence_digest_owners: dict[str, str] = {}

        def register_unique_test_evidence(
            claim: dict[str, Any], claim_id: str
        ) -> None:
            evidence = claim.get("evidence")
            artifacts = evidence.get("artifacts") if isinstance(evidence, dict) else None
            digests = (
                {
                    item.get("sha256")
                    for item in artifacts
                    if isinstance(item, dict) and item.get("kind") == "test"
                }
                if isinstance(artifacts, list)
                else set()
            )
            digests.discard(None)
            if len(digests) != 1:
                errors.append(
                    f"{claim_id} must carry exactly one capability-specific test digest"
                )
                return
            digest = next(iter(digests))
            owner = evidence_digest_owners.get(str(digest))
            if owner is not None and owner != claim_id:
                errors.append(
                    f"{claim_id} reuses generic test evidence from {owner}: {digest}"
                )
            else:
                evidence_digest_owners[str(digest)] = claim_id

        def evaluate_verified(
            claim: dict[str, Any], expected_claim: dict[str, str]
        ) -> tuple[str, list[str]]:
            evidence = claim.get("evidence")
            cache_hash = (
                canonical_evidence_hash(evidence)
                if isinstance(evidence, dict)
                else repr(evidence)
            )
            key = (str(claim.get("state")), f"{expected_claim!r}:{cache_hash}")
            if key not in evidence_cache:
                evidence_cache[key] = self.evaluate_support(
                    claim,
                    root=root,
                    execute=execute_evidence,
                    ceiling="verified",
                    expected_claim=expected_claim,
                )
            return evidence_cache[key]
        floor_data = self.data["completion_floor"]
        stacks = floor_data["stacks"]
        stack_matrix = claims.get("stacks", {}) if isinstance(claims.get("stacks"), dict) else {}
        for stack_id, floor in stacks.items():
            stack_claims = stack_matrix.get(stack_id, {})
            for capability in floor["required"]:
                claim = stack_claims.get(capability)
                if not isinstance(claim, dict):
                    errors.append(f"{stack_id}.{capability} must be an evidence-backed claim, got {claim!r}")
                    continue
                claim_id = f"{stack_id}.{capability}"
                register_unique_test_evidence(claim, claim_id)
                state, reasons = evaluate_verified(
                    claim,
                    {"kind": "stack-capability", "id": claim_id},
                )
                if state != "verified":
                    errors.append(
                        f"{stack_id}.{capability} must be verified with valid evidence, "
                        f"got {claim.get('state')!r}: {reasons}"
                    )
        surface_claims = claims.get("agent_surfaces", {}) if isinstance(claims.get("agent_surfaces"), dict) else {}
        for surface in floor_data["required_agent_surfaces"]:
            claim = surface_claims.get(surface)
            if not isinstance(claim, dict):
                errors.append(f"agent_surfaces.{surface} must be an evidence-backed claim, got {claim!r}")
                continue
            minimum = str(self.data["agent_surfaces"][surface]["minimum_surface_version"])
            actual = str(claim.get("surface_version", ""))
            if not _surface_version_satisfies(actual, minimum):
                errors.append(
                    f"agent_surfaces.{surface} version {actual!r} does not satisfy pinned minimum {minimum!r}"
                )
            claim_id = f"{surface}@{actual}"
            register_unique_test_evidence(claim, f"agent_surfaces.{claim_id}")
            state, reasons = evaluate_verified(
                claim,
                {"kind": "agent-surface", "id": claim_id},
            )
            if state != "verified":
                errors.append(
                    f"agent_surfaces.{surface} must be verified with valid evidence, "
                    f"got {claim.get('state')!r}: {reasons}"
                )
        return errors


def _surface_version_satisfies(actual: str, minimum: str) -> bool:
    numeric = re.compile(r"^\d+(?:\.\d+)*$")
    if numeric.fullmatch(actual) and numeric.fullmatch(minimum):
        actual_parts = tuple(int(part) for part in actual.split("."))
        minimum_parts = tuple(int(part) for part in minimum.split("."))
        width = max(len(actual_parts), len(minimum_parts))
        return actual_parts + (0,) * (width - len(actual_parts)) >= minimum_parts + (0,) * (width - len(minimum_parts))
    return actual == minimum


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
        "schemas", "runtime", "evidence_tools", "languages", "frameworks", "tools", "project_root", "layers",
        "bindings", "capabilities", "scan_targets", "sweep_targets", "sweep_providers",
        "support", "agent_surfaces", "completion_capabilities", "completion_floor",
    ):
        _require_mapping(data, key)

    language_ids = set(data["languages"])
    framework_ids = set(data["frameworks"])
    layer_ids = set(data["layers"])
    for tool, policy in data["evidence_tools"].items():
        pattern = policy.get("version_pattern") if isinstance(policy, dict) else None
        if not isinstance(pattern, str):
            raise RegistryError(f"evidence_tools.{tool} requires a version_pattern")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise RegistryError(f"evidence_tools.{tool} has invalid version_pattern: {exc}") from exc
        argv_tail = policy.get("argv_tail")
        if (
            not isinstance(argv_tail, list)
            or any(not isinstance(value, str) for value in argv_tail)
        ):
            raise RegistryError(f"evidence_tools.{tool}.argv_tail must be a list of strings")
        executable = policy.get("executable")
        if executable != "current-python" and (
            not isinstance(executable, list)
            or not executable
            or any(not isinstance(value, str) or not value for value in executable)
        ):
            raise RegistryError(
                f"evidence_tools.{tool}.executable must be current-python or a non-empty name list"
            )
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
    issuer = data["support"].get("verification_issuer")
    if not isinstance(issuer, dict) or issuer.get("status") not in {
        "unavailable",
        "verified",
    }:
        raise RegistryError(
            "support.verification_issuer must declare unavailable or verified status"
        )
    if not all(str(issuer.get(field, "")).strip() for field in ("id", "owner_wp", "path")):
        raise RegistryError(
            "support.verification_issuer requires id, owner_wp, and path"
        )
    if issuer["status"] == "verified" and not (
        isinstance(issuer.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", issuer["sha256"])
    ):
        raise RegistryError(
            "verified support.verification_issuer requires a lowercase SHA-256"
        )
    for target, entry in data["scan_targets"].items():
        if target not in language_ids:
            raise RegistryError(f"scan_targets.{target} is not a registered language")
        if not isinstance(entry, dict) or not (entry.get("adapter") or entry.get("shim")):
            raise RegistryError(f"scan_targets.{target} requires an adapter or shim")
        if entry.get("support") not in support_states:
            raise RegistryError(f"scan_targets.{target} names unknown support state")
    provider_ids = set(data["sweep_providers"])
    for provider, entry in data["sweep_providers"].items():
        prefix = f"sweep_providers.{provider}"
        if not isinstance(entry, dict):
            raise RegistryError(f"{prefix} must be a mapping")
        languages = entry.get("languages")
        if (
            not isinstance(languages, list)
            or not languages
            or any(language not in language_ids for language in languages)
        ):
            raise RegistryError(f"{prefix}.languages must name registered languages")
        for field in ("executable", "argv", "version_argv"):
            values = entry.get(field)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
            ):
                raise RegistryError(f"{prefix}.{field} must be a non-empty string list")
        pattern = entry.get("version_pattern")
        if not isinstance(pattern, str):
            raise RegistryError(f"{prefix}.version_pattern must be a string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise RegistryError(f"{prefix}.version_pattern is invalid: {exc}") from exc
        if entry.get("provider_kind") != "native":
            raise RegistryError(f"{prefix}.provider_kind must be 'native'")
        if entry.get("output_stream") not in {"stdout", "stderr", "stdout-or-stderr"}:
            raise RegistryError(f"{prefix}.output_stream is not recognized")
        if not isinstance(entry.get("output_format"), str) or not entry["output_format"]:
            raise RegistryError(f"{prefix}.output_format must be a non-empty string")
        for field in ("timeout_seconds", "output_byte_limit", "semantic_rule_version"):
            value = entry.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise RegistryError(f"{prefix}.{field} must be positive")
        for field in ("clean_exit_codes", "diagnostic_exit_codes"):
            values = entry.get(field)
            if (
                not isinstance(values, list)
                or any(type(value) is not int or value < 0 for value in values)
                or len(values) != len(set(values))
            ):
                raise RegistryError(f"{prefix}.{field} must be unique non-negative integers")
        if set(entry["clean_exit_codes"]) & set(entry["diagnostic_exit_codes"]):
            raise RegistryError(f"{prefix} exit classifications must be disjoint")
    for language, providers in data["sweep_targets"].items():
        if language not in language_ids:
            raise RegistryError(f"sweep_targets.{language} is not a registered language")
        if (
            not isinstance(providers, list)
            or not providers
            or any(provider not in provider_ids for provider in providers)
            or len(providers) != len(set(providers))
        ):
            raise RegistryError(
                f"sweep_targets.{language} must name unique registered providers"
            )
        incompatible = [
            provider
            for provider in providers
            if language not in data["sweep_providers"][provider]["languages"]
        ]
        if incompatible:
            raise RegistryError(
                f"sweep_targets.{language} names incompatible providers: {incompatible}"
            )
    for surface, entry in data["agent_surfaces"].items():
        if not isinstance(entry, dict) or not str(entry.get("minimum_surface_version", "")).strip():
            raise RegistryError(f"agent_surfaces.{surface} requires a pinned minimum surface version")
        if not str(entry.get("discovery", "")).strip():
            raise RegistryError(f"agent_surfaces.{surface} requires a discovery contract")
    completion_ids = set(data["completion_capabilities"])
    for stack, floor in data["completion_floor"]["stacks"].items():
        referenced = set(floor.get("required", [])) | set(floor.get("experimental_allowed", []))
        unknown = sorted(referenced - completion_ids)
        if unknown:
            raise RegistryError(f"completion_floor.stacks.{stack} names undefined outcomes: {unknown}")
    unknown_surfaces = sorted(
        set(data["completion_floor"]["required_agent_surfaces"])
        - set(data["agent_surfaces"])
    )
    if unknown_surfaces:
        raise RegistryError(f"completion_floor names undefined agent surfaces: {unknown_surfaces}")
    return CapabilityRegistry(data=data, path=registry_path)


def registry_values(section: str, *, registry: CapabilityRegistry | None = None) -> frozenset[str]:
    return (registry or load_registry()).identifiers(section)


def sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))
