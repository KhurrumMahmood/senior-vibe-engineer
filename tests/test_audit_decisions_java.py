"""Java comment-reference, failure, source-safety, and copied-closure proof."""
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
SKILL = ROOT / ".claude" / "skills" / "audit-decisions"
FIXTURE = ROOT / "tests" / "fixtures" / "audit-decisions-java"


def _jdk_bin() -> Path:
    executable = shutil.which("javac")
    if executable:
        return Path(executable)
    pytest.skip("JDK 17 compiler is unavailable")


def _env(*, path: str | None = None) -> dict[str, str]:
    javac = _jdk_bin()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{javac.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(root).parts
    }


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env()
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    native = _run(
        "javac", "--release", "17", "-d", str(host / "classes"), *sources, cwd=host, env=env
    )
    assert native.returncode == 0, native.stdout + native.stderr
    shutil.rmtree(host / "classes")
    return host, env


def _audit(
    skill: Path, host: Path, output: Path, env: dict[str, str], *extra: str, isolated: bool = True
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "audit.py"),
        "--project-root",
        str(host),
        "--output-dir",
        str(output),
        *extra,
        cwd=host,
        env=env,
    )


def _raw(output: Path) -> dict:
    return json.loads((output / "raw-drift.json").read_text(encoding="utf-8"))


def _assert_outcome(output: Path) -> None:
    raw = _raw(output)
    java_refs = [item for item in raw["references"] if item["language"] == "java"]
    assert raw["status"] == "complete"
    assert raw["analysis"]["java"] == {
        "status": "complete",
        "analyzer": "jdk-compiler-tree-api",
        "minimum_jdk_version": "17.0.0",
    }
    assert {(item["id"], item["comment_form"], item["resolved"]) for item in java_refs} == {
        ("0001", "line", True),
        ("0002", "block", True),
        ("9999", "line", False),
    }
    assert sum(item["id"] == "0001" for item in java_refs) == 2
    assert [row["adr_id"] for row in raw["drift"] if row["symptom"] == "code-ref-orphan"] == ["9999"]
    report = (output / "drift.md").read_text(encoding="utf-8")
    assert "Java comment references: 4 total" in report
    assert (output / "registry-audit.json").is_file()
    assert (output / "link-check.txt").is_file()


def test_java_comments_reach_final_drift_and_source_is_read_only(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)
    output = host / "reports" / "audit-decisions" / "java-final"

    result = _audit(SKILL, host, output, env)

    assert result.returncode == 1, result.stdout + result.stderr
    _assert_outcome(output)
    assert _fingerprints(host) == before


def test_java_strings_exclusions_unresolved_and_external_symlink_are_honest(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    unresolved = host / "src" / "main" / "java" / "refs" / "Unresolved.java"
    unresolved.write_text(
        "package refs; class Unresolved { MissingType value; // decision:0001\n}\n",
        encoding="utf-8",
    )
    outside = tmp_path / "Outside.java"
    outside.write_text("// decision:9010\nclass Outside {}\n", encoding="utf-8")
    (host / "src" / "main" / "java" / "refs" / "Outside.java").symlink_to(outside)
    output = host / "reports" / "audit-decisions" / "java-boundaries"

    result = _audit(SKILL, host, output, env)

    assert result.returncode == 1, result.stdout + result.stderr
    raw = _raw(output)
    references = raw["references"]
    assert any(item["path"].endswith("Unresolved.java") and item["id"] == "0001" for item in references)
    assert {item["id"] for item in references}.isdisjoint(
        {"9001", "9002", "9003", "9004", "9005", "9006", "9007", "9008", "9009", "9010"}
    )


def test_java_malformed_and_tool_failures_publish_no_partial_audit(tmp_path: Path) -> None:
    malformed, env = _host(tmp_path / "malformed")
    (malformed / "src" / "main" / "java" / "refs" / "Broken.java").write_text(
        "package refs; class Broken { void bad( { // decision:0001\n", encoding="utf-8"
    )
    malformed_output = malformed / "reports" / "audit-decisions" / "malformed"

    malformed_result = _audit(SKILL, malformed, malformed_output, env)

    assert malformed_result.returncode == 2
    assert "status=failed" in malformed_result.stderr
    assert "syntax" in malformed_result.stderr.lower()
    assert not malformed_output.exists()

    missing, _ = _host(tmp_path / "missing")
    missing_output = missing / "reports" / "audit-decisions" / "missing"
    missing_result = _audit(SKILL, missing, missing_output, _env(path=""))
    assert missing_result.returncode == 2
    assert "status=unsupported" in missing_result.stderr
    assert "Java JDK is unavailable" in missing_result.stderr
    assert not missing_output.exists()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for name, version in (("java", 'openjdk version "11.0.22"'), ("javac", "javac 11.0.22")):
        tool = fake_bin / name
        tool.write_text(f"#!/bin/sh\necho '{version}' >&2\n", encoding="utf-8")
        tool.chmod(0o755)
    old_output = missing / "reports" / "audit-decisions" / "old"
    old_result = _audit(SKILL, missing, old_output, _env(path=str(fake_bin)))
    assert old_result.returncode == 2
    assert "status=unsupported" in old_result.stderr
    assert "JDK >= 17.0.0" in old_result.stderr
    assert not old_output.exists()


def test_copied_java_audit_closure_runs_outside_source_checkout(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    installed = tmp_path / "installed" / "audit-decisions"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "audit-decisions" / "copied"

    result = _audit(installed, host, output, env)

    assert result.returncode == 1, result.stdout + result.stderr
    _assert_outcome(output)
    assert (installed / "scripts" / "detect_java_comments.java").is_file()
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert str(ROOT) not in closure


def test_java_audit_contract_declares_atomic_status_semantics() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "Java comments v1" in text
    assert "JDK 17" in text
    assert "Compiler Tree API" in text
    assert "complete" in text
    assert "unsupported" in text
    assert "failed" in text
