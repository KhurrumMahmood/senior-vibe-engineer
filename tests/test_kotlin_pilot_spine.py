"""Bounded Kotlin/JVM spine, direct build gate, and promotion history."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.kotlin_language_provider import (
    KOTLIN_CONFIGURATION_SCRIPTS,
    KOTLIN_SCRIPT_SUFFIXES,
    KOTLIN_SOURCE_SUFFIXES,
    kotlin_suffix_role,
    validate_kotlin_build_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "kotlin-pilot"
BUILDER = FIXTURE / "kotlin_fixture_build.py"
COVERAGE = ROOT / ".claude" / "tasks" / "kotlin-language-coverage.json"
PACKET = (
    ROOT / ".claude" / "tasks" / "multilanguage-learnings" / "kotlin-spine.md"
)
DOCTOR = ROOT / "scripts" / "language_doctor.py"
INVENTORY = ROOT / "scripts" / "source_inventory.py"
EXPECTED_SKILLS = {
    "adapt-project",
    "audit-decisions",
    "explain-code",
    "extract-enum",
    "find-comment-drift",
    "find-complexity-hotspots",
    "find-concept-divergence",
    "find-dormant",
    "find-duplication",
    "find-folder-topology-drift",
    "find-implicit-state",
    "find-incomplete-sweep",
    "find-omnibus",
    "find-semantic-duplication",
    "find-standard-gaps",
    "map-subsystem",
    "move-path",
    "prevent-regression",
    "propose-boundary",
    "propose-folder-reorganization",
    "rename-concept",
    "unify-shadows",
}


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=timeout,
    )


def _tree_state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        if ".native-build" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file() and path.suffix in {".kt", ".kts", ".json"}:
            state[relative] = (
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return state


def _manifest_paths(host: Path) -> tuple[list[Path], list[Path], dict[str, object]]:
    manifest = json.loads((host / "kotlin-project.json").read_text(encoding="utf-8"))
    sources = [host / relative for relative in manifest["sources"]]
    tests = [host / relative for relative in manifest["tests"]]
    return sources, tests, manifest


def _validate(host: Path, kotlinc: Path, java: Path):
    sources, tests, manifest = _manifest_paths(host)
    return validate_kotlin_build_evidence(
        host,
        expected_sources=sources,
        expected_tests=tests,
        expected_kotlinc=kotlinc,
        expected_java=java,
        expected_test_main=manifest["test_main"],
        expected_smoke_output=manifest["smoke_output"],
    )


def test_kotlin_profile_inventory_roles_scripts_symlink_and_preservation(
    tmp_path: Path,
) -> None:
    profile = json.loads(
        (ROOT / "scripts" / "language_profiles" / "kotlin.json").read_text(
            encoding="utf-8"
        )
    )
    assert profile["suffixes"] == [".kt"]
    assert profile["fact_tiers"] == ["lexical-filesystem", "syntax"]
    assert KOTLIN_SOURCE_SUFFIXES == {".kt"}
    assert KOTLIN_SCRIPT_SUFFIXES == {".kts"}
    assert KOTLIN_CONFIGURATION_SCRIPTS == {
        "build.gradle.kts",
        "settings.gradle.kts",
    }
    assert kotlin_suffix_role(Path("Source.kt")) == "source"
    assert kotlin_suffix_role(Path("Source.KT")) is None
    assert kotlin_suffix_role(Path("build.gradle.kts")) == "configuration"
    assert kotlin_suffix_role(Path("settings.gradle.kts")) == "configuration"
    assert kotlin_suffix_role(Path("Seed.kts")) == "unsupported-script"
    assert kotlin_suffix_role(Path("Foreign.java")) is None

    pilot = tmp_path / "kotlin-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(INVENTORY),
            "--project-root",
            str(host),
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    kotlin = {
        row["path"]: row for row in payload["files"] if row["language"] == "kotlin"
    }
    assert kotlin["src/main/kotlin/kotlinpilot/Invoice.kt"]["role"] == "source"
    assert kotlin["src/main/kotlin/kotlinpilot/Main.kt"]["role"] == "source"
    assert kotlin["tests/kotlinpilot/InvoiceTest.kt"]["role"] == "test"
    assert kotlin["generated/GeneratedInvoice.kt"]["role"] == "generated"
    assert kotlin["scripts/Tooling.kt"]["role"] == "tooling"
    assert kotlin["scripts/Seed.kts"] == {
        "path": "scripts/Seed.kts",
        "language": "kotlin",
        "suffix": ".kts",
        "role": "tooling",
        "classification": "unsupported",
        "reason": "language_not_enabled",
    }
    assert kotlin["build.gradle.kts"]["classification"] == "unsupported"
    assert "vendor/VendorInvoice.kt" not in kotlin
    assert "build/BuildSentinel.kt" not in kotlin
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"


def test_kotlin_direct_native_build_and_fail_closed_evidence(tmp_path: Path) -> None:
    raw_kotlinc = shutil.which("kotlinc")
    raw_java = shutil.which("java")
    if raw_kotlinc is None or raw_java is None:
        pytest.skip("kotlinc/Java unavailable; doctor boundaries are covered separately")
    kotlinc = Path(raw_kotlinc).resolve()
    java = Path(raw_java).resolve()
    pilot = tmp_path / "copied-kotlin-closure"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    before = _tree_state(host)
    assert _validate(host, kotlinc, java).state == "missing"
    offline = {
        **os.environ,
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "GRADLE_USER_HOME": str(tmp_path / "empty-gradle-home"),
    }
    built = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(pilot / "kotlin_fixture_build.py"),
            "--project-root",
            str(host),
            "--kotlinc",
            str(kotlinc),
            "--java",
            str(java),
        ],
        tmp_path,
        env=offline,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assert _tree_state(host) == before
    valid = _validate(host, kotlinc, java)
    assert valid.state == "valid"
    assert valid.evidence is not None
    assert valid.evidence["checks"]["test"]["stdout"] == "kotlin-pilot-tests:ok\n"
    assert valid.evidence["checks"]["smoke"]["stdout"] == (
        "invoice:INV-42:pending:kotlin\n"
    )
    assert "gradle" not in json.dumps(valid.evidence["commands"]).lower()

    malformed_compile = _run(
        [
            str(kotlinc),
            "-jvm-target",
            "17",
            "-Werror",
            "-d",
            str(tmp_path / "broken.jar"),
            str(FIXTURE / "malformed" / "Broken.kt"),
        ],
        host,
    )
    assert malformed_compile.returncode != 0
    assert "error:" in malformed_compile.stderr

    missing_tool = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(pilot / "kotlin_fixture_build.py"),
            "--project-root",
            str(host),
            "--kotlinc",
            str(tmp_path / "missing-kotlinc"),
            "--java",
            str(java),
        ],
        tmp_path,
    )
    assert missing_tool.returncode == 2
    assert "kotlinc path is unavailable" in missing_tool.stderr

    evidence_path = host / ".native-build" / "kotlin-build-evidence.json"
    pristine = evidence_path.read_text(encoding="utf-8")
    payload = json.loads(pristine)
    evidence_path.write_text("{", encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "malformed"
    evidence_path.write_text(pristine, encoding="utf-8")

    incomplete = json.loads(pristine)
    incomplete["inputs"] = incomplete["inputs"][:-1]
    evidence_path.write_text(json.dumps(incomplete), encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "incomplete"
    evidence_path.write_text(pristine, encoding="utf-8")

    assert _validate(host, java, java).state == "tool-mismatch"
    wrong_command = json.loads(pristine)
    wrong_command["commands"]["compile"].remove("-Werror")
    evidence_path.write_text(json.dumps(wrong_command), encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "wrong-command"
    evidence_path.write_text(pristine, encoding="utf-8")

    stale_source = host / "src" / "main" / "kotlin" / "kotlinpilot" / "Invoice.kt"
    original_source = stale_source.read_text(encoding="utf-8")
    stale_source.write_text(original_source + "\n", encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "stale"
    stale_source.write_text(original_source, encoding="utf-8")
    evidence_path.write_text(pristine, encoding="utf-8")

    output_mismatch = json.loads(pristine)
    output_mismatch["outputs"][0]["sha256"] = "0" * 64
    evidence_path.write_text(json.dumps(output_mismatch), encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "output-mismatch"
    native_failure = json.loads(pristine)
    native_failure["checks"]["smoke"]["stdout"] = "wrong\n"
    evidence_path.write_text(json.dumps(native_failure), encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "native-check-failure"
    evidence_path.write_text(pristine, encoding="utf-8")
    assert _validate(host, kotlinc, java).state == "valid"
    assert _tree_state(host) == before


def test_kotlin_doctor_reports_exact_tools_missing_old_and_malformed(
    tmp_path: Path,
) -> None:
    raw_kotlinc = shutil.which("kotlinc")
    raw_java = shutil.which("java")
    if raw_kotlinc is None or raw_java is None:
        pytest.skip("kotlinc/Java unavailable; missing state is covered below")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(host),
            "--language",
            "kotlin",
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["fact_tiers"] == ["lexical-filesystem", "syntax"]
    assert payload["project_markers"]["present"] == [
        "kotlin-project.json",
        "build.gradle.kts",
    ]
    tools = {row["id"]: row for row in payload["tools"]}
    assert set(tools) == {"kotlinc", "java"}
    assert all(row["status"] == "available" for row in tools.values())
    assert Path(tools["kotlinc"]["path"]).is_absolute()
    assert Path(tools["java"]["path"]).is_absolute()

    missing_host = tmp_path / "missing"
    missing_host.mkdir()
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(missing_host),
            "--language",
            "kotlin",
        ],
        tmp_path,
        env={**os.environ, "PATH": ""},
    )
    missing = json.loads(completed.stdout)
    assert missing["status"] == "unavailable"
    assert set(missing["status_reasons"]) == {
        "toolchain-unavailable",
        "project-metadata-unavailable",
    }
    assert all(row["reason"] == "not-found" for row in missing["tools"])

    old_host = tmp_path / "old"
    (old_host / ".tools").mkdir(parents=True)
    (old_host / ".jdk" / "bin").mkdir(parents=True)
    (old_host / "kotlin-project.json").write_text("{}\n", encoding="utf-8")
    old_tools = {
        old_host / ".tools" / "kotlinc": "info: kotlinc-jvm 2.3.99 (JRE 17.0.12)",
        old_host / ".jdk" / "bin" / "java": 'openjdk version "16.0.2"',
    }
    for path, version in old_tools.items():
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
        path.chmod(0o755)
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(old_host),
            "--language",
            "kotlin",
        ],
        tmp_path,
        env={**os.environ, "PATH": ""},
    )
    old = json.loads(completed.stdout)
    assert old["status"] == "too-old"
    assert old["status_reasons"] == ["toolchain-too-old"]
    assert all(row["reason"] == "below-minimum-version" for row in old["tools"])

    malformed_host = tmp_path / "malformed"
    (malformed_host / ".tools").mkdir(parents=True)
    (malformed_host / ".jdk" / "bin").mkdir(parents=True)
    (malformed_host / "kotlin-project.json").write_text("{}\n", encoding="utf-8")
    for path in (
        malformed_host / ".tools" / "kotlinc",
        malformed_host / ".jdk" / "bin" / "java",
    ):
        path.write_text("#!/bin/sh\nprintf '%s\\n' 'unknown'\n", encoding="utf-8")
        path.chmod(0o755)
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--project-root",
            str(malformed_host),
            "--language",
            "kotlin",
        ],
        tmp_path,
        env={**os.environ, "PATH": ""},
    )
    malformed = json.loads(completed.stdout)
    assert malformed["status"] == "unavailable"
    assert all(
        row["reason"] == "version-unrecognized" for row in malformed["tools"]
    )


def test_kotlin_feasibility_packet_and_all_22_promotions() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    assert "Kotlin/JVM 2.4.10" in packet
    assert "JDK 17.0.12" in packet
    assert "Gradle 7.5.1" in packet
    assert "no standalone Analysis API" in packet
    assert "semantic-project facts remain unproven" in " ".join(packet.split())

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    baseline = coverage["historical_spine_baseline"]
    assert baseline["disposition"] == "kotlin-pending-implementation"
    assert baseline["skill_count"] == 22
    assert set(baseline["skills"]) == EXPECTED_SKILLS
    assert all(row["disposition"] == "kotlin-supported" for row in rows)
    assert set(coverage["current_assertions"]["supported_skills"]) == EXPECTED_SKILLS
    assert coverage["current_assertions"]["pending_skills"] == []
    assert all(
        row["evidence_path"]
        and row["native_check"]
        and row["reviewed_revision"]
        and row["limitation"]
        for row in rows
    )
