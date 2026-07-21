"""Java static record-construction semantic leads and copied closure."""
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
SKILL = ROOT / ".claude/skills/find-semantic-duplication"
FIXTURE = ROOT / "tests/fixtures/find-semantic-duplication-java/host"
PYTHON = Path(sys.executable)


def _jdk() -> Path:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        pytest.skip("JDK is unavailable")
    version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = version.stdout + version.stderr
    if version.returncode or "javac " not in rendered or int(rendered.split("javac ", 1)[1].split(".", 1)[0]) < 17:
        pytest.skip("JDK 17+ is unavailable")
    return Path(javac).parent


def _env() -> dict[str, str]:
    return {**os.environ, "PATH": f"{_jdk()}{os.pathsep}{os.environ.get('PATH', '')}"}


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env()
    classes = tmp_path / "classes"
    sources = sorted(str(path) for path in (host / "src/main/java").rglob("*.java"))
    tests = sorted(str(path) for path in (host / "src/test/java").rglob("*.java"))
    compiled = _run("javac", "--release", "17", "-d", str(classes), *sources, *tests, cwd=host, env=env)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    native = _run("java", "-cp", str(classes), "example.SemanticFixtureTest", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts and not path.is_symlink()
    }


def _fingerprint(skill: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_java_semantic.py", "detect_java_semantic.java"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((skill / "scripts" / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _scan(skill: Path, host: Path, env: dict[str, str], *, name: str = "java", target: str = "src/main/java", isolated: bool = False, java: str | None = None, javac: str | None = None) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports/semantic-duplication" / name
    prefix = (str(PYTHON), "-I", "-S") if isolated else (str(PYTHON),)
    args = [*prefix, str(skill / "scripts/detect_java_semantic.py"), "--target", target, "--project-root", str(host), "--report-dir", str(report)]
    if java is not None:
        args.extend(("--java-executable", java))
    if javac is not None:
        args.extend(("--javac-executable", javac))
    return _run(*args, cwd=host, env=env), report


def test_java_semantic_lead_has_record_fields_and_direct_callers(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)
    result, report = _scan(SKILL, host, env)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["language"] == "java"
    assert payload["analyzer"] == "jdk-compiler-tree-static-record-returns"
    assert payload["status"] == "complete"
    assert payload["source_fingerprint"] == _fingerprint(SKILL)
    assert [item["finding_id"] for item in payload["confirmed"]] == ["JAVA-SD-0001"]
    finding = payload["confirmed"][0]
    assert finding["static_return_type"] == "example.SemanticFixture.Summary"
    assert finding["return_fields"] == ["label", "total"]
    assert finding["investigation_status"] == "confirmed"
    assert "not behavioral equivalence" in finding["notes"]
    assert {member["qualified_name"] for member in finding["members"]} == {
        "example.SemanticFixture.summarizeByIndex",
        "example.SemanticFixture.summarizeByRange",
    }
    assert {member["caller_count"] for member in finding["members"]} == {1, 2}
    assert {caller["symbol"] for member in finding["members"] for caller in member["direct_callers"]} == {
        "example.SemanticConsumer.useIndex",
        "example.SemanticConsumer.useRange",
        "example.SemanticFixture.wrapper",
    }
    assert "example.SemanticFixture.wrapper" not in {
        member["qualified_name"] for member in finding["members"]
    }
    matrix = (report / finding["matrix_path"]).read_text(encoding="utf-8")
    for row in ("Static record return type", "Returned record components", "Resolved direct call relationship", "Resolved direct callers"):
        assert row in matrix
    triage = (report / "triage.md").read_text(encoding="utf-8")
    assert "Conservative static review leads" in triage
    assert "never behavioral equivalence" in triage
    assert _hashes(host) == before


def test_java_semantic_exclusions_failures_and_copied_closure(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)
    for index, target in enumerate(("src/test", "src/generated", "vendor")):
        result, report = _scan(SKILL, host, env, name=f"excluded-{index}", target=target)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((report / "findings.json").read_text(encoding="utf-8"))["confirmed"] == []

    broken = host / "src/main/java/example/Broken.java"
    broken.write_text("package example; public class Broken { void bad( { } }\n", encoding="utf-8")
    malformed, report = _scan(SKILL, host, env, name="malformed")
    assert malformed.returncode == 2
    assert "syntax-error" in malformed.stderr
    assert not report.exists()
    broken.unlink()

    fake = tmp_path / "old-jdk"
    fake.mkdir()
    for tool, output in (("java", "openjdk 11.0.22 2024-01-01"), ("javac", "javac 11.0.22")):
        path = fake / tool
        path.write_text(f"#!/bin/sh\necho '{output}'\n", encoding="utf-8")
        path.chmod(0o755)
    old, report = _scan(SKILL, host, env, name="old", java=str(fake / "java"), javac=str(fake / "javac"))
    assert old.returncode == 2
    assert "requires JDK >= 17" in old.stderr
    assert not report.exists()
    missing, report = _scan(SKILL, host, env, name="missing", java=str(tmp_path / "missing-java"), javac=str(tmp_path / "missing-javac"))
    assert missing.returncode == 2
    assert "unavailable" in missing.stderr
    assert not report.exists()

    copied = tmp_path / "on-demand/find-semantic-duplication"
    shutil.copytree(SKILL, copied)
    copied_result, copied_report = _scan(copied, host, env, name="copied", isolated=True)
    assert copied_result.returncode == 0, copied_result.stdout + copied_result.stderr
    copied_payload = json.loads((copied_report / "findings.json").read_text(encoding="utf-8"))
    assert copied_payload["source_fingerprint"] == _fingerprint(copied)
    assert (copied_report / copied_payload["confirmed"][0]["matrix_path"]).is_file()
    assert "scripts/_lib" not in "\n".join(path.read_text(encoding="utf-8") for path in (copied / "scripts").iterdir() if path.is_file())
    assert _hashes(host) == before


def test_java_semantic_requires_resolved_production_callers(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    (host / "src/main/java/example/SemanticConsumer.java").unlink()
    result, report = _scan(SKILL, host, env, name="no-callers")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert payload["confirmed"] == []
    assert payload["counts"]["deferred"] >= 2
    assert "no_resolved_production_caller" in {item["reason"] for item in payload["deferred"]}
