"""Java filesystem discovery, final artifacts, and copied-closure proof."""
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
SKILL = ROOT / ".claude" / "skills" / "adapt-project"
FIXTURE = ROOT / "tests" / "fixtures" / "adapt-project-java-j2a"


def _jdk() -> Path:
    javac = shutil.which("javac")
    if javac is None:
        pytest.skip("JDK 17 compiler is unavailable")
    return Path(javac)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    javac = _jdk()
    env = {
        **os.environ,
        "PATH": f"{javac.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    native = subprocess.run(
        ["javac", "--release", "17", "-proc:none", "-d", str(host / "classes"), *sources],
        cwd=host,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert native.returncode == 0, native.stdout + native.stderr
    shutil.rmtree(host / "classes")
    return host, env


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(host).parts
    }


def _discover(skill: Path, host: Path, artifacts: Path, env: dict[str, str]) -> tuple[dict, Path]:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(skill / "scripts" / "discover.py"),
            "--project-root",
            str(host),
            "--artifact-root",
            str(artifacts),
            "--no-host-write",
            "--timestamp",
            "java-j2a",
        ],
        cwd=host,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    scan = Path(result.stdout.strip())
    return json.loads((scan / "adapter.json").read_text(encoding="utf-8")), scan


def test_java_discovery_reaches_final_artifacts_and_preserves_source(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)

    adapter, scan = _discover(SKILL, host, tmp_path / "artifacts", env)

    source = next(row for row in adapter["source_roots"] if row["path"] == "src")
    assert adapter["status"] == "complete"
    assert adapter["analysis"]["java"] == {
        "status": "complete",
        "analyzer": "filesystem-source-inventory",
    }
    assert source["java_files"] == 2
    assert source["source_languages"] == ["java"]
    assert adapter["stack"]["languages"] == ["java"]
    assert adapter["stack"]["frameworks"] == []
    assert adapter["stack"]["package_managers"] == ["maven"]
    assert "pom.xml" in adapter["stack"]["markers"]
    assert adapter["commands"]["test"] == ["mvn test"]
    assert "Java: 2" in (scan / "report.md").read_text(encoding="utf-8")
    assert (scan / "adapter.yml").is_file()
    assert (scan / "evidence.json").is_file()
    assert _hashes(host) == before


def test_java_discovery_is_filesystem_only_and_excludes_non_source_roles(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    broken = host / "src/main/java/example/Broken.java"
    broken.write_text("package example; public class Broken { void nope( { }\n", encoding="utf-8")
    linked = host / "src/main/java/example/Linked.java"
    linked.symlink_to("BillingParser.java")

    adapter, _scan = _discover(SKILL, host, tmp_path / "artifacts", {**env, "PATH": ""})

    source = next(row for row in adapter["source_roots"] if row["path"] == "src")
    assert source["java_files"] == 3
    assert adapter["analysis"]["java"]["status"] == "complete"
    rendered = json.dumps(adapter)
    assert "BillingParserTest.java" not in rendered
    assert "GeneratedBilling.java" not in rendered
    assert "WireGenerated.java" not in rendered
    assert "VendorBilling.java" not in rendered


def test_copied_java_adapter_closure_is_self_contained(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    installed = tmp_path / "installed" / "adapt-project"
    shutil.copytree(SKILL, installed)

    adapter, scan = _discover(installed, host, tmp_path / "artifacts", env)
    gate = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(installed / "scripts" / "check_evidence.py"),
            "--scan-dir",
            str(scan),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert gate.returncode == 0, gate.stdout + gate.stderr
    assert adapter["analysis"]["java"]["status"] == "complete"
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert str(ROOT) not in closure


def test_java_adapter_contract_is_lazy_and_bounded() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "references/java.md" in skill
    assert len(skill.splitlines()) < 500
    java = (SKILL / "references" / "java.md").read_text(encoding="utf-8")
    assert "filesystem-source-inventory" in java
    assert "javac --release 17 -proc:none" in java
    assert "Kotlin" in java
