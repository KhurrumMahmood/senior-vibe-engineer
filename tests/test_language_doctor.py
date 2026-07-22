"""Read-only capability tests for the profile-driven language doctor."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import language_doctor
from scripts._lib.language_support.profile import load_profiles


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "scripts" / "language_doctor.py"
PROFILE_ROOT = ROOT / "scripts" / "language_profiles"


def _fake_tool(path: Path, output: str, *, stderr: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = "sys.stderr" if stderr else "sys.stdout"
    path.write_text(
        f"#!{sys.executable}\nimport sys\nprint({output!r}, file={stream})\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _run_doctor(
    project: Path,
    language: str,
    *,
    system_bin: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(DOCTOR),
            "--profiles-root",
            str(PROFILE_ROOT),
            "--project-root",
            str(project),
            "--language",
            language,
        ],
        cwd=ROOT,
        env={**os.environ, "PATH": str(system_bin)},
        capture_output=True,
        text=True,
        check=False,
    )


def _manifest(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_mode,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _tool(payload: dict, tool_id: str) -> dict:
    return next(tool for tool in payload["tools"] if tool["id"] == tool_id)


def test_typescript_prefers_project_local_tools_and_is_read_only(tmp_path: Path) -> None:
    project = tmp_path / "host"
    (project / "node_modules" / ".bin").mkdir(parents=True)
    (project / "package.json").write_text("{}\n", encoding="utf-8")
    (project / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    local_node = _fake_tool(project / "node_modules" / ".bin" / "node", "v20.11.1")
    local_tsc = _fake_tool(
        project / "node_modules" / ".bin" / "tsc", "Version 5.6.3"
    )
    system_bin = tmp_path / "system-bin"
    _fake_tool(system_bin / "node", "v99.0.0")
    _fake_tool(system_bin / "tsc", "Version 99.0.0")
    before = _manifest(project)

    first = _run_doctor(project, "typescript", system_bin=system_bin)
    second = _run_doctor(project, "typescript", system_bin=system_bin)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert first.stdout == second.stdout
    assert first.stderr == ""
    assert _manifest(project) == before
    payload = json.loads(first.stdout)
    assert payload["schema_version"] == 1
    assert payload["profile_schema_version"] == 1
    assert payload["language"] == "typescript"
    assert payload["project_root"] == str(project.resolve())
    assert payload["status"] == "available"
    assert payload["status_reasons"] == []
    assert payload["project_markers"] == {
        "declared": ["package.json", "tsconfig.json"],
        "present": ["package.json", "tsconfig.json"],
    }
    assert payload["fact_tiers"] == [
        "lexical-filesystem",
        "syntax",
        "semantic-project",
    ]
    assert payload["explicit_limits"] == [
        "A TypeScript profile does not imply React, Angular, Vue, or other framework support.",
        "Semantic facts require the audited project's own compiler package and tsconfig.",
    ]
    assert _tool(payload, "node") == {
        "id": "node",
        "minimum_version": "18.0.0",
        "path": str(local_node),
        "provenance": "project-local",
        "reason": None,
        "required": True,
        "status": "available",
        "version": "20.11.1",
        "version_command": [str(local_node), "--version"],
    }
    assert _tool(payload, "tsc") == {
        "id": "tsc",
        "minimum_version": "5.0.0",
        "path": str(local_tsc),
        "provenance": "project-local",
        "reason": None,
        "required": True,
        "status": "available",
        "version": "5.6.3",
        "version_command": [str(local_tsc), "--version"],
    }


def test_java_uses_system_tools_and_parses_stderr_versions(tmp_path: Path) -> None:
    project = tmp_path / "host"
    project.mkdir()
    (project / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    system_bin = tmp_path / "system-bin"
    java = _fake_tool(
        system_bin / "java", 'openjdk version "17.0.20" 2025-07-15', stderr=True
    )
    javac = _fake_tool(system_bin / "javac", "javac 17.0.20", stderr=True)

    completed = _run_doctor(project, "java", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["project_markers"]["present"] == ["pom.xml"]
    assert [tool["id"] for tool in payload["tools"]] == ["java", "javac"]
    assert _tool(payload, "java") == {
        "id": "java",
        "minimum_version": "17.0.0",
        "path": str(java),
        "provenance": "system",
        "reason": None,
        "required": True,
        "status": "available",
        "version": "17.0.20",
        "version_command": [str(java), "-version"],
    }
    assert _tool(payload, "javac")["version"] == "17.0.20"
    assert payload["explicit_limits"] == [
        "A Java profile does not imply Spring, Android, Kotlin, annotation-processor, or build-plugin support.",
        "Project-wide type resolution requires a consumer-specific classpath or build-tool integration.",
    ]


def test_php_prefers_project_local_runtime_and_composer(tmp_path: Path) -> None:
    project = tmp_path / "host"
    (project / ".tools" / "php" / "bin").mkdir(parents=True)
    (project / "composer.json").write_text("{}\n", encoding="utf-8")
    local_php = _fake_tool(
        project / ".tools" / "php" / "bin" / "php",
        "PHP 8.3.12 (cli)",
    )
    local_composer = _fake_tool(
        project / ".tools" / "composer",
        "Composer version 2.7.9 2024-09-04 14:43:28",
    )
    system_bin = tmp_path / "system-bin"
    _fake_tool(system_bin / "php", "PHP 9.0.0 (cli)")
    _fake_tool(system_bin / "composer", "Composer version 9.0.0")
    before = _manifest(project)

    completed = _run_doctor(project, "php", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _manifest(project) == before
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["project_markers"]["present"] == ["composer.json"]
    assert _tool(payload, "php")["path"] == str(local_php)
    assert _tool(payload, "php")["provenance"] == "project-local"
    assert _tool(payload, "php")["version"] == "8.3.12"
    assert _tool(payload, "composer")["path"] == str(local_composer)
    assert _tool(payload, "composer")["provenance"] == "project-local"
    assert _tool(payload, "composer")["version"] == "2.7.9"


def test_swift_prefers_project_local_compiler_tools_and_is_swiftpm_limited(
    tmp_path: Path,
) -> None:
    project = tmp_path / "host"
    (project / ".tools" / "swift" / "bin").mkdir(parents=True)
    (project / "Package.swift").write_text("// swift-tools-version: 6.0\n", encoding="utf-8")
    local_swift = _fake_tool(
        project / ".tools" / "swift" / "bin" / "swift",
        "Swift version 6.1.2 (swift-6.1.2-RELEASE)",
    )
    local_swiftc = _fake_tool(
        project / ".tools" / "swift" / "bin" / "swiftc",
        "Swift version 6.1.2 (swift-6.1.2-RELEASE)",
    )
    system_bin = tmp_path / "system-bin"
    _fake_tool(system_bin / "swift", "Swift version 9.0.0")
    _fake_tool(system_bin / "swiftc", "Swift version 9.0.0")
    before = _manifest(project)

    completed = _run_doctor(project, "swift", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _manifest(project) == before
    payload = json.loads(completed.stdout)
    assert payload["status"] == "available"
    assert payload["project_markers"] == {
        "declared": ["Package.swift"],
        "present": ["Package.swift"],
    }
    assert _tool(payload, "swift")["path"] == str(local_swift)
    assert _tool(payload, "swift")["provenance"] == "project-local"
    assert _tool(payload, "swift")["version"] == "6.1.2"
    assert _tool(payload, "swiftc")["path"] == str(local_swiftc)
    assert _tool(payload, "swiftc")["provenance"] == "project-local"
    assert _tool(payload, "swiftc")["version"] == "6.1.2"
    limits = "\n".join(payload["explicit_limits"])
    assert "SwiftPM-only" in limits
    assert "SwiftSyntax is not bundled" in limits
    assert "SourceKit-LSP has no usable version probe" in limits
    assert "XCTest and Testing modules" in limits
    assert "SwiftUI" in limits


def test_old_project_local_tool_is_not_replaced_by_newer_system_tool(
    tmp_path: Path,
) -> None:
    project = tmp_path / "host"
    (project / "node_modules" / ".bin").mkdir(parents=True)
    (project / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    local_node = _fake_tool(project / "node_modules" / ".bin" / "node", "v16.20.2")
    local_tsc = _fake_tool(
        project / "node_modules" / ".bin" / "tsc", "Version 4.9.5"
    )
    system_bin = tmp_path / "system-bin"
    _fake_tool(system_bin / "node", "v22.0.0")
    _fake_tool(system_bin / "tsc", "Version 5.9.3")

    completed = _run_doctor(project, "typescript", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "too-old"
    assert _tool(payload, "node")["path"] == str(local_node)
    assert _tool(payload, "node")["provenance"] == "project-local"
    assert _tool(payload, "tsc")["path"] == str(local_tsc)
    assert _tool(payload, "tsc")["provenance"] == "project-local"


@pytest.mark.parametrize(
    ("node_version", "tsc_version", "expected_status", "expected_reasons"),
    [
        ("v16.20.2", "Version 4.9.5", "too-old", ["toolchain-too-old"]),
        (None, None, "unavailable", ["toolchain-unavailable"]),
        ("v20.11.1", None, "limited", ["partial-toolchain"]),
    ],
)
def test_typescript_reports_old_missing_and_partial_toolchains(
    tmp_path: Path,
    node_version: str | None,
    tsc_version: str | None,
    expected_status: str,
    expected_reasons: list[str],
) -> None:
    project = tmp_path / "host"
    project.mkdir()
    (project / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    if node_version is not None:
        _fake_tool(system_bin / "node", node_version)
    if tsc_version is not None:
        _fake_tool(system_bin / "tsc", tsc_version)

    completed = _run_doctor(project, "typescript", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == expected_status
    assert payload["status_reasons"] == expected_reasons
    assert {
        tool["id"]: tool["status"] for tool in payload["tools"]
    } == {
        "node": "unavailable" if node_version is None else (
            "too-old" if node_version.startswith("v16") else "available"
        ),
        "tsc": "unavailable" if tsc_version is None else (
            "too-old" if "4.9" in tsc_version else "available"
        ),
    }


def test_supported_tools_without_project_metadata_report_limited(tmp_path: Path) -> None:
    project = tmp_path / "host"
    project.mkdir()
    system_bin = tmp_path / "system-bin"
    _fake_tool(system_bin / "java", 'openjdk version "21.0.2"', stderr=True)
    _fake_tool(system_bin / "javac", "javac 21.0.2")

    completed = _run_doctor(project, "java", system_bin=system_bin)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "limited"
    assert payload["status_reasons"] == ["project-metadata-unavailable"]
    assert payload["project_markers"]["present"] == []
    assert {tool["status"] for tool in payload["tools"]} == {"available"}


def test_version_probe_uses_literal_argv_no_shell_and_a_bounded_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "host"
    tool = project / ".tools" / "go" / "bin" / "go"
    _fake_tool(tool, "unused")
    (project / "go.mod").write_text("module example.test/doctor\n", encoding="utf-8")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def timeout(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(language_doctor.subprocess, "run", timeout)
    profile = load_profiles(PROFILE_ROOT)["go"]

    payload = language_doctor.inspect_language(
        profile, project, timeout_seconds=0.25
    )

    assert calls == [
        (
            [str(tool), "version"],
            {
                "cwd": project.resolve(),
                "capture_output": True,
                "encoding": "utf-8",
                "errors": "replace",
                "check": False,
                "shell": False,
                "timeout": 0.25,
            },
        )
    ]
    assert payload["status"] == "unavailable"
    assert payload["tools"][0]["reason"] == "version-command-timeout"
