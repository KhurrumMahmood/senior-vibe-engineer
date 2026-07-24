#!/usr/bin/env python3
"""Provide bounded Kotlin/JVM path roles and build-evidence validation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


KOTLIN_SOURCE_SUFFIXES = frozenset({".kt"})
KOTLIN_SCRIPT_SUFFIXES = frozenset({".kts"})
KOTLIN_CONFIGURATION_SCRIPTS = frozenset(
    {"build.gradle.kts", "settings.gradle.kts"}
)
JVM_TARGET = "17"
EVIDENCE_SCHEMA_VERSION = 1
SHA256_LENGTH = 64


@dataclass(frozen=True)
class KotlinBuildEvidenceResult:
    """A fail-closed evidence state plus the trusted document when valid."""

    state: str
    evidence: dict[str, Any] | None = None


def kotlin_suffix_role(path: Path) -> str | None:
    """Classify exact lowercase Kotlin paths without promoting arbitrary scripts."""
    if path.suffix in KOTLIN_SOURCE_SUFFIXES:
        return "source"
    if path.suffix in KOTLIN_SCRIPT_SUFFIXES:
        if path.name in KOTLIN_CONFIGURATION_SCRIPTS:
            return "configuration"
        return "unsupported-script"
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_paths(project_root: Path, paths: Iterable[Path]) -> tuple[str, ...] | None:
    rendered: list[str] = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(project_root).as_posix()
        except (OSError, RuntimeError, ValueError):
            return None
        if relative in rendered:
            return None
        rendered.append(relative)
    return tuple(rendered)


def _safe_relative(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw in {".", ""}:
        return None
    return raw


def _valid_digest(raw: object) -> bool:
    return (
        isinstance(raw, str)
        and len(raw) == SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in raw)
    )


def _expected_commands(
    root: Path,
    *,
    kotlinc: Path,
    java: Path,
    sources: tuple[str, ...],
    tests: tuple[str, ...],
    test_main: str,
) -> dict[str, list[str]]:
    build = root / ".native-build"
    source_paths = [str(root / relative) for relative in sources]
    test_paths = [str(root / relative) for relative in tests]
    common = [str(kotlinc), "-jvm-target", JVM_TARGET, "-Werror", "-include-runtime"]
    return {
        "compile": [*common, "-d", str(build / "kotlin-pilot.jar"), *source_paths],
        "compile-tests": [
            *common,
            "-d",
            str(build / "kotlin-pilot-tests.jar"),
            *source_paths,
            *test_paths,
        ],
        "test": [
            str(java),
            "-cp",
            str(build / "kotlin-pilot-tests.jar"),
            test_main,
        ],
        "smoke": [str(java), "-jar", str(build / "kotlin-pilot.jar")],
    }


def validate_kotlin_build_evidence(
    project_root: Path,
    *,
    expected_sources: Iterable[Path],
    expected_tests: Iterable[Path],
    expected_kotlinc: Path,
    expected_java: Path,
    expected_test_main: str,
    expected_smoke_output: str,
) -> KotlinBuildEvidenceResult:
    """Validate current inputs, exact tools/commands, outputs, tests, and smoke."""
    try:
        root = project_root.resolve(strict=True)
        kotlinc = expected_kotlinc.resolve(strict=True)
        java = expected_java.resolve(strict=True)
    except (OSError, RuntimeError):
        return KotlinBuildEvidenceResult("malformed")
    if not root.is_dir() or root.is_symlink():
        return KotlinBuildEvidenceResult("malformed")
    sources = _relative_paths(root, expected_sources)
    tests = _relative_paths(root, expected_tests)
    if sources is None or tests is None or not sources or not tests:
        return KotlinBuildEvidenceResult("malformed")

    evidence_path = root / ".native-build" / "kotlin-build-evidence.json"
    if not evidence_path.is_file() or evidence_path.is_symlink():
        return KotlinBuildEvidenceResult("missing")
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return KotlinBuildEvidenceResult("malformed")
    expected_keys = {
        "schema_version",
        "status",
        "project_root",
        "jvm_target",
        "tools",
        "inputs",
        "commands",
        "outputs",
        "checks",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        return KotlinBuildEvidenceResult("malformed")
    if (
        payload["schema_version"] != EVIDENCE_SCHEMA_VERSION
        or payload["status"] != "complete"
        or payload["jvm_target"] != JVM_TARGET
    ):
        return KotlinBuildEvidenceResult("malformed")
    if payload["project_root"] != str(root):
        return KotlinBuildEvidenceResult("mismatched-root")
    if payload["tools"] != {"kotlinc": str(kotlinc), "java": str(java)}:
        return KotlinBuildEvidenceResult("tool-mismatch")

    rows = payload["inputs"]
    if not isinstance(rows, list):
        return KotlinBuildEvidenceResult("malformed")
    actual_inputs: dict[str, tuple[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "role", "sha256"}:
            return KotlinBuildEvidenceResult("malformed")
        relative = _safe_relative(row["path"])
        if (
            relative is None
            or row["role"] not in {"source", "test"}
            or not _valid_digest(row["sha256"])
            or relative in actual_inputs
        ):
            return KotlinBuildEvidenceResult("malformed")
        actual_inputs[relative] = (row["role"], row["sha256"])
    expected_inputs = {
        **{relative: "source" for relative in sources},
        **{relative: "test" for relative in tests},
    }
    if set(actual_inputs) != set(expected_inputs) or any(
        actual_inputs[relative][0] != role
        for relative, role in expected_inputs.items()
    ):
        return KotlinBuildEvidenceResult("incomplete")
    for relative, (_role, digest) in actual_inputs.items():
        path = root / relative
        if (
            path.suffix != ".kt"
            or not path.is_file()
            or path.is_symlink()
        ):
            return KotlinBuildEvidenceResult("malformed")
        if _sha256(path) != digest:
            return KotlinBuildEvidenceResult("stale")

    expected_commands = _expected_commands(
        root,
        kotlinc=kotlinc,
        java=java,
        sources=sources,
        tests=tests,
        test_main=expected_test_main,
    )
    if payload["commands"] != expected_commands:
        return KotlinBuildEvidenceResult("wrong-command")

    outputs = payload["outputs"]
    if not isinstance(outputs, list):
        return KotlinBuildEvidenceResult("malformed")
    expected_outputs = {
        ".native-build/kotlin-pilot.jar",
        ".native-build/kotlin-pilot-tests.jar",
    }
    actual_outputs: dict[str, str] = {}
    for row in outputs:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            return KotlinBuildEvidenceResult("malformed")
        relative = _safe_relative(row["path"])
        if (
            relative is None
            or not _valid_digest(row["sha256"])
            or relative in actual_outputs
        ):
            return KotlinBuildEvidenceResult("malformed")
        actual_outputs[relative] = row["sha256"]
    if set(actual_outputs) != expected_outputs:
        return KotlinBuildEvidenceResult("incomplete")
    for relative, digest in actual_outputs.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            return KotlinBuildEvidenceResult("missing-output")
        if _sha256(path) != digest:
            return KotlinBuildEvidenceResult("output-mismatch")

    checks = payload["checks"]
    if not isinstance(checks, dict) or set(checks) != {"test", "smoke"}:
        return KotlinBuildEvidenceResult("malformed")
    for name in ("test", "smoke"):
        check = checks[name]
        if (
            not isinstance(check, dict)
            or set(check) != {"returncode", "stdout", "stderr"}
            or not isinstance(check["returncode"], int)
            or not isinstance(check["stdout"], str)
            or not isinstance(check["stderr"], str)
        ):
            return KotlinBuildEvidenceResult("malformed")
        if check["returncode"] != 0:
            return KotlinBuildEvidenceResult("native-check-failure")
    if checks["smoke"]["stdout"] != expected_smoke_output:
        return KotlinBuildEvidenceResult("native-check-failure")
    return KotlinBuildEvidenceResult("valid", payload)
