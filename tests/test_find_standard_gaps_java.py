"""Java outcome, boundary, and copied-closure proof for standard gaps."""
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
SKILL = ROOT / ".claude" / "skills" / "find-standard-gaps"
FIXTURE = ROOT / "tests" / "fixtures" / "find-standard-gaps-java"


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


def _run(
    *args: str, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
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


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _scan(
    skill: Path,
    host: Path,
    env: dict[str, str],
    output: Path,
    *,
    isolated: bool = False,
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "scan_coverage.py"),
        "--ideas",
        str(host / "standards.json"),
        "--project-root",
        str(host),
        "--output-dir",
        str(output),
        cwd=host,
        env=env,
    )


def _finding(output: Path) -> dict:
    payload = json.loads((output / "coverage.json").read_text(encoding="utf-8"))
    assert len(payload["results"]) == 1
    return payload["results"][0]


def _assert_outcome(output: Path) -> None:
    finding = _finding(output)
    assert finding["status"] == "scanned"
    assert finding["scanned_files"] == 1
    assert finding["skipped_files"] == 0
    assert finding["situation_sites"] == 8
    assert [(gap["file"], gap["line"]) for gap in finding["gaps"]] == [
        ("src/main/java/example/JsonBoundary.java", 20),
        ("src/main/java/example/JsonBoundary.java", 39),
        ("src/main/java/example/JsonBoundary.java", 50),
        ("src/main/java/example/JsonBoundary.java", 56),
        ("src/main/java/example/JsonBoundary.java", 70),
        ("src/main/java/example/JsonBoundary.java", 72),
    ]
    assert finding["coverage"] == 0.25
    report = (output / "coverage.md").read_text(encoding="utf-8")
    assert "6 gap(s)" in report
    assert "src/main/java/example/JsonBoundary.java:50" in report


def test_java_try_standard_reaches_final_artifacts_without_source_changes(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    before = _fingerprints(host)
    output = host / "reports" / "java"

    result = _scan(SKILL, host, env, output)

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_outcome(output)
    assert _fingerprints(host) == before


def test_copied_java_closure_is_self_contained(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    copied = tmp_path / "on-demand" / "find-standard-gaps"
    shutil.copytree(SKILL, copied)
    output = host / "reports" / "copied"

    result = _scan(copied, host, env, output, isolated=True)

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_outcome(output)
    assert (copied / "scripts" / "detect_java_calls.java").is_file()


def test_java_boundaries_are_explicit_not_clean(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; class Broken { void bad( { } }\n", encoding="utf-8")
    broken_output = host / "reports" / "broken"

    malformed = _scan(SKILL, host, env, broken_output)

    assert malformed.returncode == 0, malformed.stdout + malformed.stderr
    finding = _finding(broken_output)
    assert finding["status"] == "partial"
    assert finding["skipped_files"] == 1
    assert finding["situation_sites"] == 8
    broken.unlink()

    unresolved = host / "src" / "main" / "java" / "example" / "Unresolved.java"
    unresolved.write_text(
        "package example; class Unresolved { String run(String value) { return MissingParser.decode(value); } }\n",
        encoding="utf-8",
    )
    ideas = json.loads((host / "standards.json").read_text(encoding="utf-8"))
    ideas["ideas"][0]["contract"]["detector"]["call_matches"] = r"^(Json|MissingParser)\.decode$"
    (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")
    unresolved_output = host / "reports" / "unresolved"
    unresolved_result = _scan(SKILL, host, env, unresolved_output)
    assert unresolved_result.returncode == 0, unresolved_result.stdout + unresolved_result.stderr
    unresolved_finding = _finding(unresolved_output)
    assert unresolved_finding["status"] == "scanned"
    assert unresolved_finding["situation_sites"] == 9
    assert any(gap["file"].endswith("Unresolved.java") for gap in unresolved_finding["gaps"])

    external = tmp_path / "External.java"
    external.write_text("class External {}\n", encoding="utf-8")
    (host / "src" / "main" / "java" / "example" / "External.java").symlink_to(external)

    detector = ideas["ideas"][0]["contract"]["detector"]
    detector["call_matches"] = r"^Json\.decode$"
    for name, target in (
        ("generated", "src/main/java/example/GeneratedBoundary.java"),
        ("test", "src/test/java/example/JsonBoundaryTest.java"),
        ("vendor", "vendor/example/VendorBoundary.java"),
        ("external", "src/main/java/example/External.java"),
    ):
        detector["paths"] = [target]
        (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")
        excluded_output = host / "reports" / name
        excluded = _scan(SKILL, host, env, excluded_output)
        assert excluded.returncode == 0, excluded.stdout + excluded.stderr
        assert _finding(excluded_output)["status"] == "no_files_matched"

    detector["paths"] = ["src/**/*.java"]
    detector["call_matches"] = r"^(Json|MissingParser)\.decode$"
    (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")

    detector.pop("enclosed_by")
    detector["requires_kwarg"] = "timeout"
    (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")
    unsupported_condition_output = host / "reports" / "unsupported-condition"
    unsupported_condition = _scan(SKILL, host, env, unsupported_condition_output)
    assert unsupported_condition.returncode == 0, unsupported_condition.stdout + unsupported_condition.stderr
    condition_finding = _finding(unsupported_condition_output)
    assert condition_finding["status"] == "language_unsupported"
    assert "enclosed_by: try" in condition_finding["error"]

    detector.pop("requires_kwarg")
    detector["enclosed_by"] = "try"
    kotlin = host / "src" / "main" / "kotlin" / "example" / "Ignored.kt"
    kotlin.parent.mkdir(parents=True)
    kotlin.write_text("package example\nfun ignored() = 1\n", encoding="utf-8")
    detector["paths"] = ["src/**/*"]
    (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")
    kotlin_output = host / "reports" / "kotlin"
    kotlin_result = _scan(SKILL, host, env, kotlin_output)
    assert kotlin_result.returncode == 0, kotlin_result.stdout + kotlin_result.stderr
    kotlin_finding = _finding(kotlin_output)
    assert kotlin_finding["status"] == "partial"
    assert kotlin_finding["unsupported_extensions"] == [".kt"]

    detector["paths"] = ["src/**/*.java"]
    (host / "standards.json").write_text(json.dumps(ideas), encoding="utf-8")
    missing_output = host / "reports" / "missing"
    missing = _scan(SKILL, host, _env(path=""), missing_output)
    assert missing.returncode == 0, missing.stdout + missing.stderr
    unsupported = _finding(missing_output)
    assert unsupported["status"] == "language_unsupported"
    assert "JDK" in unsupported["error"]

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for name, version in (("java", 'openjdk version "11.0.22"'), ("javac", "javac 11.0.22")):
        tool = fake_bin / name
        tool.write_text(f"#!/bin/sh\necho '{version}' >&2\n", encoding="utf-8")
        tool.chmod(0o755)
    old_output = host / "reports" / "old"
    old = _scan(SKILL, host, _env(path=str(fake_bin)), old_output)
    assert old.returncode == 0, old.stdout + old.stderr
    old_finding = _finding(old_output)
    assert old_finding["status"] == "language_unsupported"
    assert "JDK >= 17.0.0" in old_finding["error"]


def test_java_frontmatter_declares_narrow_support() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    scans = set(text.split("scans: [", 1)[1].split("]", 1)[0].split(", "))
    assert {"python", "javascript", "typescript", "go", "java", "rust"} <= scans
    assert "JDK 17" in text
    assert "does not resolve aliases, types, receivers, imports, or frameworks" in " ".join(text.split())
