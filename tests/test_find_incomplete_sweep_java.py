"""Java record-constructor incomplete-sweep outcome and copied closure."""
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
SKILL = ROOT / ".claude/skills/find-incomplete-sweep"
FIXTURE = ROOT / "tests/fixtures/find-incomplete-sweep-java/host"
PYTHON = Path(sys.executable)


def _jdk() -> Path:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        pytest.skip("JDK is unavailable")
    version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = version.stdout + version.stderr
    if version.returncode or "javac " not in rendered or int(rendered.split("javac ", 1)[1].split(".", 1)[0]) < 17:
        pytest.skip("JDK 17+ is unavailable")
    return Path(javac).parent


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _env(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, "PATH": f"{_jdk()}{os.pathsep}{os.environ.get('PATH', '')}"}


def _prepare_git(host: Path, env: dict[str, str]) -> None:
    source = host / "src/main/java/example/SweepFixture.java"
    current = source.read_text(encoding="utf-8")
    old = current.replace(" // swept", "")
    source.write_text(old, encoding="utf-8")
    for command in (("git", "init"), ("git", "config", "user.email", "fixture@example.test"), ("git", "config", "user.name", "Fixture"), ("git", "add", ".")):
        assert _run(*command, cwd=host, env=env).returncode == 0
    first = _run(
        "git", "commit", "-m", "old constructor shapes", cwd=host,
        env={**env, "GIT_AUTHOR_DATE": "2025-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2025-01-01T00:00:00Z"},
    )
    assert first.returncode == 0, first.stdout + first.stderr
    source.write_text(current, encoding="utf-8")
    assert _run("git", "add", source.relative_to(host).as_posix(), cwd=host, env=env).returncode == 0
    second = _run(
        "git", "commit", "-m", "sweep region constructor", cwd=host,
        env={**env, "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"},
    )
    assert second.returncode == 0, second.stdout + second.stderr


def _host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _env(tmp_path)
    classes = tmp_path / "classes"
    sources = sorted(str(path) for path in (host / "src/main/java").rglob("*.java"))
    tests = sorted(str(path) for path in (host / "src/test/java").rglob("*.java"))
    compiled = _run("javac", "--release", "17", "-d", str(classes), *sources, *tests, cwd=host, env=env)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    native = _run("java", "-cp", str(classes), "example.SweepFixtureTest", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    _prepare_git(host, env)
    return host, env


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts and not path.is_symlink()
    }


def _fingerprint(skill: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_java_incomplete_sweep.py", "detect_java_incomplete_sweep.java"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((skill / "scripts" / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _scan(skill: Path, host: Path, env: dict[str, str], *, name: str = "java", target: str = "src/main/java", isolated: bool = False, java: str | None = None, javac: str | None = None) -> tuple[subprocess.CompletedProcess[str], Path]:
    report = host / "reports/find-incomplete-sweep" / name
    prefix = (str(PYTHON), "-I", "-S") if isolated else (str(PYTHON),)
    args = [*prefix, str(skill / "scripts/detect_java_incomplete_sweep.py"), "--target", target, "--project-root", str(host), "--report-dir", str(report)]
    if java is not None:
        args.extend(("--java-executable", java))
    if javac is not None:
        args.extend(("--javac-executable", javac))
    return _run(*args, cwd=host, env=env), report


def _finish(skill: Path, report: Path, host: Path, env: dict[str, str], *, isolated: bool = False) -> None:
    prefix = (str(PYTHON), "-I", "-S") if isolated else (str(PYTHON),)
    scout = _run(*prefix, str(skill / "scripts/scout.py"), "--scan-dir", str(report), "--project-root", str(host), cwd=host, env=env)
    assert scout.returncode == 0, scout.stdout + scout.stderr
    packets = json.loads((report / "scout_packets.json").read_text(encoding="utf-8"))
    assert packets["packet_count"] == 1
    (report / "scout_verdicts.json").write_text(json.dumps({"verdicts": [{
        "id": packets["packets"][0]["id"], "verdict": "forgotten",
        "rationale": "The three newer direct record constructions consistently pass the region.",
        "completion": "use the canonical RequestOptions constructor with region us",
    }]}), encoding="utf-8")
    triage = _run(*prefix, str(skill / "scripts/triage.py"), "--scan-dir", str(report), cwd=host, env=env)
    assert triage.returncode == 0, triage.stdout + triage.stderr


def test_java_record_constructor_lead_reaches_human_triage(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)
    result, report = _scan(SKILL, host, env)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert payload["language"] == "java"
    assert payload["analyzer"] == "jdk-compiler-tree-direct-record-constructors"
    assert payload["status"] == "complete"
    assert payload["source_fingerprint"] == _fingerprint(SKILL)
    assert payload["findings"] == [{
        "callee": "example.SweepFixture.RequestOptions",
        "kwarg": "region",
        "option_position": 1,
        "group_size": 4,
        "present_count": 3,
        "majority_frac": 0.75,
        "straggler": "src/main/java/example/SweepFixture.java:29",
        "present_sites": [
            {"file": "src/main/java/example/SweepFixture.java", "line": 17},
            {"file": "src/main/java/example/SweepFixture.java", "line": 21},
            {"file": "src/main/java/example/SweepFixture.java", "line": 25},
        ],
        "gated_in": True,
        "value": "java.lang.String:us",
        "default_value": "java.lang.String:global",
        "trajectory": "3/3 option-present sites touched AFTER the straggler — consistent with a sweep that missed it",
    }]
    assert {item["reason"] for item in payload["deferred"]} >= {"present_value_equals_constructor_default"}
    _finish(SKILL, report, host, env)
    assert "## Forgotten (1)" in (report / "triaged.md").read_text(encoding="utf-8")
    assert _hashes(host) == before


def test_java_boundaries_and_copied_isolated_closure(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _hashes(host)
    for index, target in enumerate(("src/test", "src/generated", "vendor")):
        result, report = _scan(SKILL, host, env, name=f"excluded-{index}", target=target)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((report / "manifest.json").read_text(encoding="utf-8"))["findings"] == []

    broken = host / "src/main/java/example/Broken.java"
    broken.write_text("package example; public class Broken { void bad( { } }\n", encoding="utf-8")
    malformed, report = _scan(SKILL, host, env, name="malformed")
    assert malformed.returncode == 2
    assert "syntax-error" in malformed.stderr
    assert not report.exists()
    broken.unlink()

    fake = tmp_path / "old-jdk"
    fake.mkdir()
    for tool, output in (("java", 'openjdk 11.0.22 2024-01-01'), ("javac", "javac 11.0.22")):
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

    copied = tmp_path / "on-demand/find-incomplete-sweep"
    shutil.copytree(SKILL, copied)
    copied_result, copied_report = _scan(copied, host, env, name="copied", isolated=True)
    assert copied_result.returncode == 0, copied_result.stdout + copied_result.stderr
    _finish(copied, copied_report, host, env, isolated=True)
    assert json.loads((copied_report / "manifest.json").read_text(encoding="utf-8"))["source_fingerprint"] == _fingerprint(copied)
    assert "scripts/_lib" not in "\n".join(path.read_text(encoding="utf-8") for path in (copied / "scripts").iterdir() if path.is_file())
    assert _hashes(host) == before


def test_java_git_evidence_is_mandatory(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    shutil.rmtree(host / ".git")
    result, report = _scan(SKILL, host, env, name="no-git")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((report / "manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["project_resolution"]["git_evidence"] == "insufficient"
    assert payload["findings"] == []
    assert "insufficient_git_evidence" in {item["reason"] for item in payload["deferred"]}
