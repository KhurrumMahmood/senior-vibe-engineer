"""Frozen Dart-only P7 spine, pubspec boundary, and pending-work truth."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "dart-pilot"
PROFILE = ROOT / "scripts" / "language_profiles" / "dart.json"
BASELINE = ROOT / ".claude" / "tasks" / "p7-baseline" / "dart-pilot-baseline.json"
COVERAGE = ROOT / ".claude" / "tasks" / "dart-language-coverage.json"
DOCTOR = ROOT / "scripts" / "language_doctor.py"
INVENTORY = ROOT / "scripts" / "source_inventory.py"

EXPECTED_SKILLS = {
    "adapt-project", "audit-decisions", "explain-code", "extract-enum",
    "find-comment-drift", "find-complexity-hotspots",
    "find-concept-divergence", "find-dormant", "find-duplication",
    "find-folder-topology-drift", "find-implicit-state",
    "find-incomplete-sweep", "find-omnibus", "find-semantic-duplication",
    "find-standard-gaps", "map-subsystem", "move-path",
    "prevent-regression", "propose-boundary",
    "propose-folder-reorganization", "rename-concept", "unify-shadows",
}


def _manifest(root: Path) -> tuple[str, int, list[str]]:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        content = path.read_bytes()
        rows.append(
            (path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content))
        )
    digest = hashlib.sha256()
    for path, file_digest, _size in rows:
        digest.update(path.encode() + b"\0" + file_digest.encode() + b"\n")
    return digest.hexdigest(), sum(row[2] for row in rows), [row[0] for row in rows]


def _tree_state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _fake_tool(path: Path, output: str, *, exit_code: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' {json.dumps(output)}\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _doctor(host: Path, *, path: str, script: Path = DOCTOR) -> dict[str, object]:
    completed = _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(host),
            "--language",
            "dart",
        ],
        host.parent,
        env={**os.environ, "PATH": path},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_dart_fixture_and_runtime_closure_match_frozen_manifests() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert _manifest(FIXTURE) == (
        baseline["fixture"]["manifest_sha256"],
        baseline["fixture"]["total_bytes"],
        baseline["fixture"]["files"],
    )

    closure = baseline["runtime_closure"]
    paths = [ROOT / path for path in closure["files"]]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    assert digest.hexdigest() == closure["manifest_sha256"]
    assert sum(path.stat().st_size for path in paths) == closure["total_bytes"]


def test_dart_profile_inventory_roles_pubspec_symlink_and_preservation(
    tmp_path: Path,
) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["suffixes"] == [".dart"]
    assert profile["project_markers"] == ["pubspec.yaml"]
    assert [row["id"] for row in profile["native_tools"]] == ["dart"]
    assert profile["native_tools"][0]["minimum_version"] == "3.12.0"
    assert [row["id"] for row in profile["verification_commands"]] == [
        "dart-analyze", "native-test", "format-check", "executable-smoke"
    ]
    limits = "\n".join(profile["explicit_limits"])
    for boundary in (
        "pubspec.yaml", "pubspec.lock", "package:test", "*.g.dart",
        "*.freezed.dart", ".dart_tool", "Analysis Server",
    ):
        assert boundary in limits

    pilot = tmp_path / "dart-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)
    completed = _run(
        [
            sys.executable, "-I", "-S", str(INVENTORY),
            "--project-root", str(host),
        ],
        tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _tree_state(host) == before
    payload = json.loads(completed.stdout)
    dart_files = {
        row["path"]: row for row in payload["files"] if row["language"] == "dart"
    }
    assert dart_files["lib/invoice_service.dart"]["role"] == "source"
    assert dart_files["bin/dart_pilot_smoke.dart"]["role"] == "tooling"
    assert dart_files["test/invoice_service_test.dart"]["role"] == "test"
    assert dart_files["generated/GeneratedInvoice.dart"]["role"] == "generated"
    assert "pubspec.yaml" not in dart_files
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded["build"] == "build"
    assert excluded["vendor"] == "vendor"
    assert excluded["linked-external"] == "symlink"
    assert not any(
        path.startswith(("build/", "vendor/", "linked-external/"))
        for path in dart_files
    )


def test_dart_native_copied_analyze_test_format_smoke_and_invalid_boundaries(
    tmp_path: Path,
) -> None:
    dart = shutil.which("dart")
    if dart is None:
        pytest.skip("Dart SDK unavailable; the profile doctor reports this boundary")
    host = tmp_path / "copied-host"
    shutil.copytree(FIXTURE / "host", host)
    before = _tree_state(host)

    for argv in (
        [dart, "analyze", "--fatal-infos", "--fatal-warnings", "."],
        [dart, "test/invoice_service_test.dart"],
        [dart, "format", "--output=none", "--set-exit-if-changed", "lib", "bin", "test"],
    ):
        completed = _run(argv, host)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    native = _run([dart, "test/invoice_service_test.dart"], host)
    assert native.stdout == "native-test:ok\n"
    smoke = _run([dart, "bin/dart_pilot_smoke.dart"], host)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:INV-42:125\n"
    assert _tree_state(host) == before
    assert not (host / ".dart_tool").exists()
    assert not (host / "pubspec.lock").exists()

    implicit_pub = tmp_path / "dart-run-is-not-read-only"
    shutil.copytree(FIXTURE / "host", implicit_pub)
    source_before = {
        path.relative_to(implicit_pub).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(implicit_pub.rglob("*.dart"))
    }
    auto_resolved = _run(
        [dart, "run", "test/invoice_service_test.dart"], implicit_pub
    )
    assert auto_resolved.returncode == 0, auto_resolved.stdout + auto_resolved.stderr
    assert (implicit_pub / ".dart_tool" / "package_config.json").is_file()
    assert (implicit_pub / ".dart_tool" / "package_graph.json").is_file()
    assert (implicit_pub / "pubspec.lock").is_file()
    assert source_before == {
        path.relative_to(implicit_pub).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(implicit_pub.rglob("*.dart"))
    }

    malformed = tmp_path / "malformed-source"
    shutil.copytree(FIXTURE / "host", malformed)
    shutil.copy2(FIXTURE / "malformed" / "Broken.dart", malformed / "lib" / "Broken.dart")
    malformed_before = _tree_state(malformed)
    rejected_source = _run(
        [dart, "analyze", "--fatal-infos", "--fatal-warnings", "."], malformed
    )
    assert rejected_source.returncode != 0
    assert "Broken.dart" in rejected_source.stdout + rejected_source.stderr
    assert _tree_state(malformed) == malformed_before

    bad_pubspec = tmp_path / "malformed-pubspec"
    shutil.copytree(FIXTURE / "host", bad_pubspec)
    (bad_pubspec / "pubspec.yaml").write_text(
        "name: [unterminated\nenvironment:\n  sdk: '>=3.12.0 <4.0.0'\n",
        encoding="utf-8",
    )
    pubspec_before = _tree_state(bad_pubspec)
    unvalidated_pubspec = _run(
        [dart, "analyze", "--fatal-infos", "--fatal-warnings", "."], bad_pubspec
    )
    assert unvalidated_pubspec.returncode == 0
    assert "No issues found" in unvalidated_pubspec.stdout
    assert _tree_state(bad_pubspec) == pubspec_before


def test_dart_doctor_project_local_system_missing_old_malformed_and_partial_states(
    tmp_path: Path,
) -> None:
    system_dart = shutil.which("dart")
    if system_dart is None:
        pytest.skip("Dart SDK unavailable; missing-state coverage remains active")
    real_host = tmp_path / "real-host"
    shutil.copytree(FIXTURE / "host", real_host)
    real = _doctor(real_host, path=os.environ.get("PATH", ""))
    real_tool = real["tools"][0]
    assert real["status"] == "available"
    assert real["project_markers"]["present"] == ["pubspec.yaml"]
    assert real_tool["status"] == "available"
    assert real_tool["version"] == "3.12.2"
    assert real_tool["provenance"] == "system"

    local = tmp_path / "local"
    local.mkdir()
    (local / "pubspec.yaml").write_text("name: local\n", encoding="utf-8")
    local_dart = _fake_tool(
        local / ".tools" / "dart-sdk" / "bin" / "dart",
        "Dart SDK version: 3.12.3 (stable)",
    )
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    _fake_tool(system_bin / "dart", "Dart SDK version: 9.0.0 (stable)")
    local_payload = _doctor(local, path=str(system_bin))
    assert local_payload["status"] == "available"
    assert local_payload["tools"][0]["path"] == str(local_dart.absolute())
    assert local_payload["tools"][0]["provenance"] == "project-local"
    assert local_payload["tools"][0]["version"] == "3.12.3"

    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "pubspec.yaml").write_text("name: missing\n", encoding="utf-8")
    missing_payload = _doctor(missing, path="")
    assert missing_payload["status"] == "unavailable"
    assert missing_payload["status_reasons"] == ["toolchain-unavailable"]
    assert missing_payload["tools"][0]["reason"] == "not-found"

    old = tmp_path / "old"
    old.mkdir()
    (old / "pubspec.yaml").write_text("name: old\n", encoding="utf-8")
    _fake_tool(
        old / ".tools" / "dart-sdk" / "bin" / "dart",
        "Dart SDK version: 3.11.9 (stable)",
    )
    old_payload = _doctor(old, path="")
    assert old_payload["status"] == "too-old"
    assert old_payload["status_reasons"] == ["toolchain-too-old"]
    assert old_payload["tools"][0]["reason"] == "below-minimum-version"

    malformed = tmp_path / "malformed-version"
    malformed.mkdir()
    (malformed / "pubspec.yaml").write_text("name: malformed\n", encoding="utf-8")
    _fake_tool(
        malformed / ".tools" / "dart-sdk" / "bin" / "dart",
        "Dart SDK version unavailable",
    )
    malformed_payload = _doctor(malformed, path="")
    assert malformed_payload["status"] == "unavailable"
    assert malformed_payload["tools"][0]["reason"] == "version-unrecognized"

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pubspec.yaml").write_text("name: broken\n", encoding="utf-8")
    _fake_tool(
        broken / ".tools" / "dart-sdk" / "bin" / "dart", "broken", exit_code=7
    )
    broken_payload = _doctor(broken, path="")
    assert broken_payload["status"] == "unavailable"
    assert broken_payload["tools"][0]["reason"] == "version-command-failed"

    no_metadata = tmp_path / "no-metadata"
    no_metadata.mkdir()
    _fake_tool(
        no_metadata / ".tools" / "dart-sdk" / "bin" / "dart",
        "Dart SDK version: 3.12.3 (stable)",
    )
    partial = _doctor(no_metadata, path="")
    assert partial["status"] == "limited"
    assert partial["status_reasons"] == ["project-metadata-unavailable"]

    lock_only = tmp_path / "lock-only"
    lock_only.mkdir()
    (lock_only / "pubspec.lock").write_text("packages: {}\n", encoding="utf-8")
    _fake_tool(
        lock_only / ".tools" / "dart-sdk" / "bin" / "dart",
        "Dart SDK version: 3.12.3 (stable)",
    )
    lock_only_payload = _doctor(lock_only, path="")
    assert lock_only_payload["status"] == "limited"
    assert lock_only_payload["status_reasons"] == ["project-metadata-unavailable"]


def test_dart_profile_doctor_inventory_execute_from_copied_runtime(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "copied-library"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    for relative in baseline["runtime_closure"]["files"]:
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    before = _tree_state(host)

    inventoried = _run(
        [
            sys.executable, "-I", "-S", str(copied / "scripts/source_inventory.py"),
            "--project-root", str(host),
        ],
        tmp_path,
    )
    assert inventoried.returncode == 0, inventoried.stdout + inventoried.stderr
    payload = json.loads(inventoried.stdout)
    assert any(row["language"] == "dart" for row in payload["files"])
    doctor = _doctor(
        host,
        path=os.environ.get("PATH", ""),
        script=copied / "scripts/language_doctor.py",
    )
    assert doctor["language"] == "dart"
    assert doctor["status"] == "available"
    assert _tree_state(host) == before


def test_dart_frozen_contracts_and_current_family_dispositions() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    contracts = baseline["pilot_contracts"]
    assert contracts["lexical"]["disposition"] == "dart-pending-implementation"
    assert contracts["semantic"]["disposition"] == "dart-pending-implementation"
    assert contracts["mutation"]["disposition"] == "dart-pending-implementation"
    assert baseline["generated_unit_boundary"] == {
        "classified_now": "generated directory or generic generated-name markers",
        "pending": ["*.g.dart", "*.freezed.dart"],
        "rule": "do not hardcode Dart filename exceptions into shared inventory; add profile-owned generated globs only with a reviewed schema extension",
    }
    assert baseline["mutation_performed"] is False

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    rows = coverage["skills"]
    assert coverage["decision"] == "expand"
    assert len(rows) == 22
    assert {row["skill"] for row in rows} == EXPECTED_SKILLS
    dispositions = {row["skill"]: row["disposition"] for row in rows}
    assert {skill for skill, value in dispositions.items() if value == "dart-supported"} == {
        "adapt-project",
        "audit-decisions",
        "find-comment-drift",
        "find-concept-divergence",
        "find-dormant",
        "find-folder-topology-drift",
        "find-standard-gaps",
        "rename-concept",
    }
    assert {skill for skill, value in dispositions.items() if value == "dart-partial"} == {
        "map-subsystem"
    }
    assert sum(value == "dart-pending-implementation" for value in dispositions.values()) == 13
    assert all(row["limitation"] and row["native_check"] for row in rows)
