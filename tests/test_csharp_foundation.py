"""Minimal C# inventory, doctor, project-evidence, and native fact spine."""
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
PYTHON = Path(sys.executable)
FIXTURE = ROOT / "tests" / "fixtures" / "csharp-foundation"
PROFILE = ROOT / "scripts" / "language_profiles" / "csharp.json"
INVENTORY = ROOT / "scripts" / "source_inventory.py"
DOCTOR = ROOT / "scripts" / "language_doctor.py"
PROVIDER = ROOT / "scripts" / "csharp_language_provider.py"
PACKET = ROOT / ".claude" / "tasks" / "multilanguage-learnings" / "csharp-foundation.md"
RUNTIME_CLOSURE = (
    "scripts/csharp_language_provider.py",
    "scripts/source_inventory.py",
    "scripts/_lib/language_support/profile.py",
    "scripts/_lib/language_support/lifecycle.py",
    "scripts/language_profiles/csharp.json",
)


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 180,
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


def _tree_state(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _fake_dotnet(path: Path, output: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' {json.dumps(output)}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _doctor(host: Path, *, path: str, script: Path = DOCTOR) -> dict[str, object]:
    completed = _run(
        [
            str(PYTHON),
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(host),
            "--language",
            "csharp",
        ],
        host.parent,
        env={**os.environ, "PATH": path},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _provider(
    script: Path,
    host: Path,
    output: Path,
    dotnet: Path,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            str(PYTHON),
            "-I",
            "-S",
            str(script),
            "--project-root",
            str(host),
            "--dotnet",
            str(dotnet),
            "--output",
            str(output),
        ],
        host.parent,
        env={
            **os.environ,
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        },
    )


def test_csharp_profile_inventory_roles_and_preservation(tmp_path: Path) -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["suffixes"] == [".cs"]
    assert profile["project_markers"] == [
        "*.csproj",
        "csharp-project.json",
        "csharp-semantic-project.json",
        "global.json",
        "NuGet.Config",
    ]
    assert profile["fact_tiers"] == [
        "lexical-filesystem",
        "syntax",
        "semantic-project",
    ]
    assert profile["native_tools"] == [
        {
            "id": "dotnet",
            "project_paths": [".dotnet/dotnet", "dotnet/dotnet"],
            "system_commands": ["dotnet"],
            "version_argv": ["{tool}", "--version"],
            "minimum_version": "10.0.302",
            "required": True,
        }
    ]
    commands = {row["id"]: row["argv"] for row in profile["verification_commands"]}
    assert "--no-restore" in commands["build"]
    assert "--no-restore" in commands["native-test"]
    assert "--no-restore" in commands["smoke"]
    assert "--no-build" in commands["native-test"]
    assert "--no-build" in commands["smoke"]

    pilot = tmp_path / "csharp-foundation"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "linked-external").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    before = _tree_state(host)
    completed = _run(
        [
            str(PYTHON),
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
    files = {
        row["path"]: row for row in payload["files"] if row["language"] == "csharp"
    }
    assert files["src/Invoice.cs"]["role"] == "source"
    assert files["src/Program.cs"]["role"] == "source"
    assert files["tests/FoundationTests.cs"]["role"] == "test"
    assert files["generated/GeneratedInvoice.cs"]["role"] == "generated"
    assert files["tools/Tooling.cs"]["role"] == "tooling"
    assert "vendor/VendorInvoice.cs" not in files
    assert "build/BuildSentinel.cs" not in files
    excluded = {row["path"]: row["role"] for row in payload["excluded_roots"]}
    assert excluded == {
        "build": "build",
        "linked-external": "symlink",
        "vendor": "vendor",
    }


def test_csharp_doctor_reports_glob_evidence_and_capability_boundaries(
    tmp_path: Path,
) -> None:
    real_dotnet = shutil.which("dotnet")
    if real_dotnet is None:
        pytest.skip(".NET SDK unavailable; missing-tool state remains covered")
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    real = _doctor(host, path=str(Path(real_dotnet).parent))
    assert real["status"] == "available"
    assert real["fact_tiers"] == [
        "lexical-filesystem",
        "syntax",
        "semantic-project",
    ]
    assert real["project_markers"] == {
        "declared": [
            "*.csproj",
            "csharp-project.json",
            "csharp-semantic-project.json",
            "global.json",
            "NuGet.Config",
        ],
        "present": ["global.json", "NuGet.Config"],
        "matches": {"*.csproj": ["CSharpFoundation.csproj"]},
    }
    assert real["tools"][0]["status"] == "available"
    assert real["tools"][0]["version"] == "10.0.302"

    missing_tool = _doctor(host, path="")
    assert missing_tool["status"] == "unavailable"
    assert missing_tool["status_reasons"] == ["toolchain-unavailable"]
    assert missing_tool["tools"][0]["reason"] == "not-found"

    project_missing = tmp_path / "project-missing"
    fake = _fake_dotnet(project_missing / ".dotnet" / "dotnet", "10.0.302")
    partial = _doctor(project_missing, path="")
    assert partial["status"] == "limited"
    assert partial["status_reasons"] == ["project-metadata-unavailable"]
    assert partial["project_markers"]["present"] == []
    assert partial["project_markers"]["matches"] == {"*.csproj": []}
    assert partial["tools"][0]["path"] == str(fake.absolute())

    old = tmp_path / "old"
    old.mkdir()
    (old / "Old.csproj").write_text("<Project />\n", encoding="utf-8")
    _fake_dotnet(old / ".dotnet" / "dotnet", "9.0.999")
    too_old = _doctor(old, path="")
    assert too_old["status"] == "too-old"
    assert too_old["status_reasons"] == ["toolchain-too-old"]
    assert too_old["tools"][0]["reason"] == "below-minimum-version"


def test_csharp_provider_copied_offline_lifecycle_and_exact_project_evidence(
    tmp_path: Path,
) -> None:
    raw_dotnet = shutil.which("dotnet")
    if raw_dotnet is None:
        pytest.skip(".NET SDK unavailable; provider tool-missing state remains covered")
    dotnet = Path(raw_dotnet).resolve()
    copied = tmp_path / "copied-runtime"
    for relative in RUNTIME_CLOSURE:
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    output = host / "reports" / "csharp-foundation.json"
    before = _tree_state(host)

    complete = _provider(
        copied / "scripts" / "csharp_language_provider.py", host, output, dotnet
    )
    assert complete.returncode == 0, complete.stdout + complete.stderr
    assert complete.stdout == ""
    assert complete.stderr == ""
    assert _tree_state(host) == before
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["outcome"] == "complete"
    assert payload["failure_kind"] == "none"
    assert payload["source_manifest"]["preserved"] is True
    assert payload["project_evidence"]["status"] == "valid"
    assert payload["project_evidence"]["path"] == "CSharpFoundation.csproj"
    assert payload["project_evidence"]["sdk"] == "Microsoft.NET.Sdk"
    assert payload["project_evidence"]["target_framework"] == "net10.0"
    assert payload["project_evidence"]["compile_items"] == [
        "src/Invoice.cs",
        "src/Program.cs",
        "tests/FoundationTests.cs",
    ]
    assert payload["project_evidence"]["global_json"]["sdk_version"] == "10.0.302"
    assert payload["project_evidence"]["nuget_config"]["package_sources"] == "cleared"
    assert payload["native"]["restore"]["status"] == "passed"
    assert payload["native"]["build"]["status"] == "passed"
    assert payload["native"]["test"]["stdout"] == "csharp-foundation-tests:ok\n"
    assert payload["native"]["smoke"]["stdout"] == (
        "invoice:INV-42:125:csharp\n"
    )
    for name in ("build", "test", "smoke"):
        assert "--no-restore" in payload["native"][name]["argv"]
    for name in ("test", "smoke"):
        assert "--no-build" in payload["native"][name]["argv"]
    assert payload["capabilities"] == {
        "inventory": "available",
        "project_compilation": "available",
        "syntax_facts": "unavailable",
        "semantic_facts": "unavailable",
        "rewrite": "unavailable",
    }
    assert not (host / "obj").exists()
    assert not (host / "bin").exists()
    assert [path.name for path in (host / "reports").iterdir()] == [
        "csharp-foundation.json"
    ]

    pristine_invoice = (host / "src" / "Invoice.cs").read_text(encoding="utf-8")
    (host / "src" / "Invoice.cs").write_text(
        (FIXTURE / "malformed" / "Broken.cs").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    malformed = _provider(
        copied / "scripts" / "csharp_language_provider.py", host, output, dotnet
    )
    assert malformed.returncode == 2
    failed = json.loads(output.read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["outcome"] == "syntax-error"
    assert failed["failure_kind"] == "dotnet-build-failed"
    assert failed["native"]["build"]["status"] == "failed"
    assert "error CS" in failed["native"]["build"]["stdout"] + failed["native"]["build"]["stderr"]
    assert failed["source_manifest"]["preserved"] is True

    (host / "src" / "Invoice.cs").write_text(pristine_invoice, encoding="utf-8")
    recovered = _provider(
        copied / "scripts" / "csharp_language_provider.py", host, output, dotnet
    )
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "complete"
    assert _tree_state(host) == before


def test_csharp_provider_tool_project_and_malformed_project_boundaries(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    output = host / "reports" / "facts.json"
    missing_tool = _provider(PROVIDER, host, output, tmp_path / "missing-dotnet")
    assert missing_tool.returncode == 0
    unsupported = json.loads(output.read_text(encoding="utf-8"))
    assert unsupported["status"] == "unsupported"
    assert unsupported["outcome"] == "tool-missing"
    assert unsupported["failure_kind"] == "dotnet-tool-missing"
    assert unsupported["capabilities"]["project_compilation"] == "unavailable"

    old_dotnet = _fake_dotnet(tmp_path / "old-dotnet", "9.0.999")
    too_old_tool = _provider(PROVIDER, host, output, old_dotnet)
    assert too_old_tool.returncode == 0
    too_old = json.loads(output.read_text(encoding="utf-8"))
    assert too_old["status"] == "unsupported"
    assert too_old["outcome"] == "unsupported"
    assert too_old["failure_kind"] == "dotnet-tool-too-old"

    raw_dotnet = shutil.which("dotnet")
    if raw_dotnet is None:
        return
    dotnet = Path(raw_dotnet).resolve()
    (host / "CSharpFoundation.csproj").unlink()
    project_missing = _provider(PROVIDER, host, output, dotnet)
    assert project_missing.returncode == 0
    partial = json.loads(output.read_text(encoding="utf-8"))
    assert partial["status"] == "partial"
    assert partial["outcome"] == "partial"
    assert partial["failure_kind"] == "csharp-project-missing"
    assert partial["capabilities"]["project_compilation"] == "unavailable"

    shutil.copy2(
        FIXTURE / "host" / "CSharpFoundation.csproj",
        host / "CSharpFoundation.csproj",
    )
    (host / "CSharpFoundation.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><Compile Include="**/*.cs" /></ItemGroup></Project>\n',
        encoding="utf-8",
    )
    malformed_project = _provider(PROVIDER, host, output, dotnet)
    assert malformed_project.returncode == 2
    malformed = json.loads(output.read_text(encoding="utf-8"))
    assert malformed["status"] == "failed"
    assert malformed["outcome"] == "native-check-failure"
    assert malformed["failure_kind"] == "csharp-project-invalid"
    assert malformed["capabilities"]["project_compilation"] == "unavailable"
    assert "exact relative paths" in malformed["detail"]


def test_csharp_foundation_learning_packet_states_reusable_and_honest_limits() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    for phrase in (
        ".NET SDK 10.0.302",
        "dotnet build --no-restore",
        "ephemeral project copy",
        "SDK-bundled Roslyn compiler",
        "no reusable Roslyn syntax or semantic API",
        "single root SDK-style .csproj",
        "next cohort",
    ):
        assert phrase in " ".join(packet.split())
