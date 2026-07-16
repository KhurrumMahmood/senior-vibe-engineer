"""Validate and execute deterministic evidence for capability support claims."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


KNOWN_SYSTEMS = {"Darwin", "Linux", "Windows"}
HEX_256_RE = re.compile(r"^[0-9a-f]{64}$")
TRUSTED_STARTUP_PATH = os.environ.get("PATH", "")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_evidence_hash(evidence: dict[str, Any]) -> str:
    payload = {key: value for key, value in evidence.items() if key != "evidence_hash"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def _safe_relative_path(value: object, root: Path, *, field: str) -> tuple[Path | None, list[str]]:
    if not isinstance(value, str) or not value.strip():
        return None, [f"{field} must be a non-empty repository-relative path"]
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None, [f"{field} must stay inside the evidence root"]
    resolved_root = root.resolve()
    resolved = (resolved_root / path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        return None, [f"{field} resolves outside the evidence root"]
    return resolved, []


def _validate_command(value: object, *, field: str, root: Path) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or not value or any(
        not isinstance(part, str) or not part.strip() for part in value
    ):
        return [], [f"{field} must be a non-empty argv list of strings"]
    executable = value[0]
    if Path(executable).is_absolute():
        if not Path(executable).is_file():
            return [], [f"{field} executable does not exist: {executable}"]
    elif "/" in executable or "\\" in executable:
        if not (root / executable).is_file():
            return [], [f"{field} executable does not exist under evidence root: {executable}"]
        value = [str((root / executable).resolve()), *value[1:]]
    else:
        discovered = shutil.which(executable)
        if discovered is None:
            return [], [f"{field} executable is not available on PATH: {executable}"]
        value = [str(Path(discovered).resolve()), *value[1:]]
    return list(value), []


def validate_file_attestations(
    attestations: object,
    *,
    root: Path,
    field: str,
    required_kinds: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(attestations, list) or not attestations:
        return [f"{field} must be a non-empty list of file attestations"]
    seen_kinds: set[str] = set()
    for index, attestation in enumerate(attestations):
        prefix = f"{field}[{index}]"
        if not isinstance(attestation, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        kind = attestation.get("kind")
        if kind not in {"test", "script", "report", "fixture"}:
            errors.append(f"{prefix}.kind is invalid: {kind!r}")
        else:
            seen_kinds.add(kind)
        path, path_errors = _safe_relative_path(attestation.get("path"), root, field=f"{prefix}.path")
        errors.extend(path_errors)
        digest = attestation.get("sha256")
        if not isinstance(digest, str) or not HEX_256_RE.fullmatch(digest):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")
        if path is None:
            continue
        if not path.is_file():
            errors.append(f"{prefix}.path does not exist: {attestation.get('path')}")
            continue
        if path.stat().st_size == 0 and kind in {"test", "script", "fixture"}:
            errors.append(f"{prefix}.path must not be an empty executable evidence file")
        if isinstance(digest, str) and HEX_256_RE.fullmatch(digest):
            actual = sha256_file(path)
            if actual != digest:
                errors.append(f"{prefix}.sha256 mismatch: expected {digest}, got {actual}")
    missing = sorted((required_kinds or set()) - seen_kinds)
    if missing:
        errors.append(f"{field} is missing required evidence kinds: {missing}")
    return errors


def attested_paths(
    attestations: object,
    *,
    root: Path,
    kind: str,
) -> set[Path]:
    """Return contained, existing paths of one attestation kind."""
    paths: set[Path] = set()
    if not isinstance(attestations, list):
        return paths
    for item in attestations:
        if not isinstance(item, dict) or item.get("kind") != kind:
            continue
        path, errors = _safe_relative_path(
            item.get("path"), root, field="attestation.path"
        )
        if path is not None and not errors and path.is_file():
            paths.add(path)
    return paths


def validate_support_evidence(
    evidence: object,
    *,
    root: Path,
    execute: bool,
    tool_policies: dict[str, Any],
    expected_claim: dict[str, str] | None = None,
    required_test_paths_by_subject: dict[str, set[Path]] | None = None,
    verification_issuer: dict[str, Any] | None = None,
    require_verified_issuer: bool = False,
) -> list[str]:
    """Validate an evidence envelope and optionally rerun all probes."""
    if not isinstance(evidence, dict):
        return ["support_evidence must be a mapping"]
    errors: list[str] = []
    claim = evidence.get("claim")
    if (
        not isinstance(claim, dict)
        or set(claim) != {"kind", "id"}
        or not all(isinstance(claim.get(key), str) and claim[key].strip() for key in ("kind", "id"))
    ):
        errors.append("support_evidence.claim must contain non-empty kind and id strings only")
    elif expected_claim is not None and claim != expected_claim:
        errors.append(
            f"support_evidence.claim must be bound to {expected_claim!r}, got {claim!r}"
        )
    if require_verified_issuer:
        if (
            not isinstance(verification_issuer, dict)
            or verification_issuer.get("status") != "verified"
        ):
            owner = (
                verification_issuer.get("owner_wp")
                if isinstance(verification_issuer, dict)
                else "unknown"
            )
            errors.append(
                "verified support is unavailable until the registry-pinned "
                f"conformance issuer is verified by {owner}"
            )
        else:
            expected_issuer = {
                "id": verification_issuer.get("id"),
                "path": verification_issuer.get("path"),
                "sha256": verification_issuer.get("sha256"),
            }
            if evidence.get("issuer") != expected_issuer:
                errors.append(
                    f"support_evidence.issuer must equal registry-pinned {expected_issuer!r}"
                )
            errors.extend(
                validate_file_attestations(
                    [
                        {
                            "kind": "script",
                            "path": expected_issuer["path"],
                            "sha256": expected_issuer["sha256"],
                        }
                    ],
                    root=root,
                    field="support_evidence.issuer",
                    required_kinds={"script"},
                )
            )

    artifacts = evidence.get("artifacts")
    errors.extend(
        validate_file_attestations(
            artifacts, root=root, field="support_evidence.artifacts", required_kinds={"test"}
        )
    )
    attested_tests = attested_paths(artifacts, root=root, kind="test")
    fixtures = evidence.get("fixtures")
    fixture_runs: list[tuple[str, dict[str, Any], list[str], Path, bytes]] = []
    seen_fixture_subjects: set[str] = set()
    executed_tests_by_subject: dict[str, Path] = {}
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("support_evidence.fixtures must be a non-empty list")
    else:
        for index, fixture in enumerate(fixtures):
            prefix = f"support_evidence.fixtures[{index}]"
            if not isinstance(fixture, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            subject = fixture.get("subject")
            if not isinstance(subject, str) or not subject.strip():
                errors.append(f"{prefix}.subject must be a non-empty string")
                subject = f"invalid-{index}"
            elif subject in seen_fixture_subjects:
                errors.append(f"{prefix}.subject is duplicated: {subject!r}")
            seen_fixture_subjects.add(subject)
            command, command_errors = _validate_command(
                fixture.get("command"), field=f"{prefix}.command", root=root
            )
            errors.extend(command_errors)
            fixture_cwd = root
            cwd_path, cwd_errors = _safe_relative_path(
                fixture.get("cwd", "."), root, field=f"{prefix}.cwd"
            )
            errors.extend(cwd_errors)
            if cwd_path is not None:
                fixture_cwd = cwd_path
                if not fixture_cwd.is_dir():
                    errors.append(f"{prefix}.cwd does not exist or is not a directory")
            timeout = fixture.get("timeout_seconds", 30)
            if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 300:
                errors.append(f"{prefix}.timeout_seconds must be an integer from 1 to 300")
            expected_observation = fixture.get("expected_observation")
            required_observation = {
                "claim": claim,
                "result": "pass",
                "subject": subject,
            }
            if expected_observation != required_observation:
                errors.append(
                    f"{prefix}.expected_observation must equal {required_observation!r}"
                )
            expected_bytes = (
                json.dumps(
                    required_observation, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                + b"\n"
            )
            expected_stdout = fixture.get("expected_stdout_sha256")
            expected_hash = sha256_bytes(expected_bytes)
            if expected_stdout != expected_hash:
                errors.append(
                    f"{prefix}.expected_stdout_sha256 must equal the canonical observation "
                    f"digest {expected_hash}"
                )
            executed_test: Path | None = None
            if command and fixture_cwd.is_dir():
                executable_path = Path(command[0]).resolve()
                if len(command) == 1 and executable_path in attested_tests:
                    executed_test = executable_path
                elif len(command) == 2:
                    candidate = (fixture_cwd / command[1]).resolve()
                    if candidate in attested_tests:
                        executed_test = candidate
            if executed_test is None:
                errors.append(
                    f"{prefix}.command must directly execute exactly one attested test "
                    "artifact; use a test wrapper for multi-file suites"
                )
            else:
                executed_tests_by_subject[subject] = executed_test
            fixture_runs.append((subject, fixture, command, fixture_cwd, expected_bytes))

    expected_subjects = (
        set(required_test_paths_by_subject)
        if required_test_paths_by_subject is not None
        else (
            {str(expected_claim.get("id"))}
            if isinstance(expected_claim, dict)
            else set(seen_fixture_subjects)
        )
    )
    if seen_fixture_subjects != expected_subjects:
        errors.append(
            "support_evidence fixture subjects must exactly match claim subjects: "
            f"expected {sorted(expected_subjects)}, got {sorted(seen_fixture_subjects)}"
        )
    if required_test_paths_by_subject is not None:
        all_required_paths: list[Path] = []
        for subject, paths in required_test_paths_by_subject.items():
            all_required_paths.extend(paths)
            if len(paths) != 1:
                errors.append(
                    f"capability_evidence.{subject} must attest exactly one integration test"
                )
                continue
            if executed_tests_by_subject.get(subject) not in paths:
                expected = sorted(str(path.relative_to(root.resolve())) for path in paths)
                errors.append(
                    f"support_evidence fixture for {subject!r} does not execute its "
                    f"capability evidence test: {expected}"
                )
        if len(all_required_paths) != len(set(all_required_paths)):
            errors.append(
                "capability subjects must use distinct integration-test artifacts; "
                "shared generic evidence is not portable coverage"
            )

    tools = evidence.get("tools")
    tool_commands: list[tuple[list[str], str, str]] = []
    if not isinstance(tools, list) or not tools:
        errors.append("support_evidence.tools must be a non-empty list")
    else:
        for index, tool in enumerate(tools):
            prefix = f"support_evidence.tools[{index}]"
            if not isinstance(tool, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            name = tool.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{prefix}.name must be a non-empty string")
                name = f"tool-{index}"
            command, command_errors = _validate_command(
                tool.get("command"), field=f"{prefix}.command", root=root
            )
            errors.extend(command_errors)
            if "version_pattern" in tool:
                errors.append(
                    f"{prefix}.version_pattern is registry-owned and must not be supplied by a claim"
                )
            policy = tool_policies.get(name) if isinstance(name, str) else None
            pattern = policy.get("version_pattern") if isinstance(policy, dict) else None
            if not isinstance(pattern, str) or not pattern.strip():
                errors.append(f"{prefix}.name has no registry-owned version policy: {name!r}")
                pattern = "(?!)"
            else:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{prefix}.version_pattern is invalid: {exc}")
            argv_tail = policy.get("argv_tail") if isinstance(policy, dict) else None
            if not isinstance(argv_tail, list) or command[1:] != argv_tail:
                errors.append(
                    f"{prefix}.command arguments must match registry-owned argv tail {argv_tail!r}"
                )
            executable_policy = policy.get("executable") if isinstance(policy, dict) else None
            resolved_executable = Path(command[0]).resolve() if command else None
            if executable_policy == "current-python":
                if resolved_executable is None or resolved_executable != Path(sys.executable).resolve():
                    errors.append(
                        f"{prefix}.command must use the current Python runtime {sys.executable!r}"
                    )
            elif isinstance(executable_policy, list):
                discovered_paths = {
                    Path(discovered).resolve()
                    for executable_name in executable_policy
                    for discovered in [
                        shutil.which(executable_name, path=TRUSTED_STARTUP_PATH)
                    ]
                    if discovered is not None
                }
                if not command or resolved_executable not in discovered_paths:
                    errors.append(
                        f"{prefix}.command executable must resolve to a registry-discovered "
                        f"tool named by {executable_policy!r}"
                    )
            else:
                errors.append(f"{prefix}.name has no registry-owned executable policy: {name!r}")
            tool_commands.append((command, pattern, str(name)))

    platforms = evidence.get("platforms")
    platform_matches = False
    if not isinstance(platforms, list) or not platforms:
        errors.append("support_evidence.platforms must be a non-empty list")
    else:
        for index, item in enumerate(platforms):
            prefix = f"support_evidence.platforms[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            system = item.get("system")
            machine = item.get("machine")
            if system not in KNOWN_SYSTEMS:
                errors.append(f"{prefix}.system is not a supported platform name: {system!r}")
            if not isinstance(machine, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", machine):
                errors.append(f"{prefix}.machine is invalid: {machine!r}")
            if system == platform.system() and machine == platform.machine():
                platform_matches = True

    declared_hash = evidence.get("evidence_hash")
    if not isinstance(declared_hash, str) or not HEX_256_RE.fullmatch(declared_hash):
        errors.append("support_evidence.evidence_hash must be a lowercase SHA-256 digest")
    else:
        actual_hash = canonical_evidence_hash(evidence)
        if declared_hash != actual_hash:
            errors.append(
                f"support_evidence.evidence_hash mismatch: expected {declared_hash}, got {actual_hash}"
            )

    if not execute or errors:
        return errors
    if not platform_matches:
        errors.append(
            f"support_evidence has no attestation for current platform {platform.system()}/{platform.machine()}"
        )
        return errors

    for subject, fixture, command, fixture_cwd, expected_bytes in fixture_runs:
        try:
            fixture_result = subprocess.run(
                command,
                cwd=fixture_cwd,
                text=False,
                capture_output=True,
                check=False,
                timeout=fixture.get("timeout_seconds", 30),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"support fixture {subject!r} could not complete: {exc}")
            continue
        if fixture_result.returncode != 0:
            errors.append(f"support fixture {subject!r} exited {fixture_result.returncode}")
        if fixture_result.stdout != expected_bytes:
            errors.append(
                f"support fixture {subject!r} observation mismatch: expected "
                f"{expected_bytes!r}, got {fixture_result.stdout!r}"
            )

    for command, pattern, name in tool_commands:
        try:
            result = subprocess.run(
                command,
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"tool probe {name!r} could not complete: {exc}")
            continue
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            errors.append(f"tool probe {name!r} exited {result.returncode}")
        elif re.search(pattern, output) is None:
            errors.append(f"tool probe {name!r} output does not match {pattern!r}: {output!r}")
    return errors
