"""Pinned Kotlin/JVM semantic facts and five distinct read-only outcomes."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "tests" / "fixtures" / "kotlin-semantic-family" / "host"
COMMON = ROOT / ".claude" / "skills" / "_kotlin-semantic"
PROVIDER = COMMON / "kotlin_semantic_facts.py"
KOTLINC = Path("/opt/homebrew/bin/kotlinc")
JAVA = Path("/usr/bin/java")
SCRIPTS = {
    "dormant": ROOT
    / ".claude"
    / "skills"
    / "find-dormant"
    / "scripts"
    / "detect_kotlin_dormant.py",
    "state": ROOT
    / ".claude"
    / "skills"
    / "find-implicit-state"
    / "scripts"
    / "detect_kotlin_state.py",
    "sweep": ROOT
    / ".claude"
    / "skills"
    / "find-incomplete-sweep"
    / "scripts"
    / "detect_kotlin_incomplete_sweep.py",
    "duplication": ROOT
    / ".claude"
    / "skills"
    / "find-semantic-duplication"
    / "scripts"
    / "detect_kotlin_semantic.py",
    "rename": ROOT
    / ".claude"
    / "skills"
    / "rename-concept"
    / "scripts"
    / "assess_kotlin_rename.py",
}
ARTIFACTS = {
    "dormant": "reports/find-dormant/kotlin/findings.json",
    "state": "reports/find-implicit-state/kotlin/findings.json",
    "sweep": "reports/find-incomplete-sweep/kotlin/manifest.json",
    "duplication": "reports/semantic-duplication/kotlin/analysis.json",
    "rename": "reports/rename-concept/kotlin/assessment.json",
}


def _run(argv: list[str], cwd: Path, *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
        timeout=timeout,
    )


def _require_toolchain() -> None:
    if not KOTLINC.is_file() or not JAVA.is_file():
        pytest.skip("pinned Kotlin/JVM toolchain is unavailable")
    version = _run([str(KOTLINC), "-version"], ROOT)
    if version.returncode or "kotlinc-jvm 2.4.10" not in version.stdout + version.stderr:
        pytest.skip("test requires pinned Kotlin/JVM 2.4.10")
    compiler_jar = Path("/opt/homebrew/Cellar/kotlin/2.4.10/libexec/lib/kotlin-compiler.jar")
    if not compiler_jar.is_file():
        pytest.skip("pinned Kotlin compiler distribution is unavailable")
    assert hashlib.sha256(compiler_jar.read_bytes()).hexdigest() == (
        "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "kotlin-semantic-host"
    shutil.copytree(HOST, host, ignore=shutil.ignore_patterns("reports"))
    return host


def _source_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "reports" not in path.parts
    }


def _payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _provider(host: Path, provider: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(provider),
            "--project-root",
            str(host),
            "--manifest",
            "kotlin-semantic-project.json",
            "--output",
            "reports/kotlin-semantic/facts.json",
            "--kotlinc",
            str(KOTLINC),
            "--java",
            str(JAVA),
        ],
        host,
    )


def _consumer(host: Path, kind: str, script: Path) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, "-I", "-S", str(script)]
    if kind == "rename":
        argv.extend(["LegacyStatus", "CanonicalStatus"])
    argv.extend(
        [
            "--project-root",
            str(host),
            "--facts",
            "reports/kotlin-semantic/facts.json",
        ]
    )
    return _run(argv, host)


def test_kotlin_semantic_family_reaches_five_copied_read_only_outcomes(
    tmp_path: Path,
) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    before = _source_bytes(host)
    install = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(COMMON, install / "_kotlin-semantic")
    copied_scripts: dict[str, Path] = {}
    names = {
        "dormant": "find-dormant",
        "state": "find-implicit-state",
        "sweep": "find-incomplete-sweep",
        "duplication": "find-semantic-duplication",
        "rename": "rename-concept",
    }
    for kind, source in SCRIPTS.items():
        destination = install / names[kind] / "scripts" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_scripts[kind] = destination

    collected = _provider(host, install / "_kotlin-semantic" / PROVIDER.name)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    facts = _payload(host / "reports/kotlin-semantic/facts.json")
    assert facts["status"] == "complete"
    assert facts["semantic_authority"]["kotlin_version"] == "2.4.10"
    assert facts["tools"]["compiler_jar"]["sha256"] == (
        "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
    )
    assert facts["commands"]["compile"]["returncode"] == 0
    assert facts["commands"]["compile_tests"]["returncode"] == 0
    assert facts["commands"]["test"]["stdout"] == "kotlin-semantic-native-test:ok\n"
    assert facts["commands"]["smoke"]["stdout"] == "receipt:7:receipt:8:queued\n"
    assert facts["diagnostics"] == []
    assert any(row["override"] and row["overrides"] for row in facts["declarations"])
    assert any(row["extension_receiver"] == "kotlin.String" for row in facts["declarations"])
    assert any(
        row["target_kind"] == "constructor"
        and row["target_fq_name"] == "kotlinsemantic.SweepOptions.<init>"
        for row in facts["calls"]
    )
    overloads = {
        row["target_signature"]
        for row in facts["calls"]
        if row["callee"] == "overloaded" and row["resolved"]
    }
    assert len(overloads) == 2

    for kind, script in copied_scripts.items():
        result = _consumer(host, kind, script)
        assert result.returncode == 0, (kind, result.stdout, result.stderr)
    dormant = _payload(host / ARTIFACTS["dormant"])
    assert [row["fq_name"] for row in dormant["candidates"]] == ["kotlinsemantic.unusedHelper"]
    state = _payload(host / ARTIFACTS["state"])
    assert state["candidates"][0]["literals"] == ["done", "queued", "running"]
    sweep = _payload(host / ARTIFACTS["sweep"])
    assert [(row["parameter"], row["group_size"]) for row in sweep["findings"]] == [("audit", 3)]
    duplication = _payload(host / ARTIFACTS["duplication"])
    assert [
        [function["fq_name"] for function in row["functions"]] for row in duplication["leads"]
    ] == [["kotlinsemantic.summarizeAlpha", "kotlinsemantic.summarizeBeta"]]
    rename = _payload(host / ARTIFACTS["rename"])
    assert rename["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert rename["old_resolved_references"]
    assert rename["new_resolved_references"]
    assert _source_bytes(host) == before


def test_kotlin_consumers_clear_claims_when_fact_pack_is_stale(tmp_path: Path) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    collected = _provider(host, PROVIDER)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    source = host / "src/main/kotlin/kotlinsemantic/Semantics.kt"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = _consumer(host, "dormant", SCRIPTS["dormant"])
    assert result.returncode == 2
    payload = _payload(host / ARTIFACTS["dormant"])
    assert payload["status"] == "partial"
    assert payload["candidates"] == []
    assert payload["deferred"] == [{"reason": "fact-pack-stale"}]
