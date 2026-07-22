"""Java 17 authority, lexical boundary, and copied-closure proof for rename-concept."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
SKILL = ROOT / ".claude" / "skills" / "rename-concept"
DETECTOR = ROOT / ".claude" / "skills" / "find-concept-divergence"
FIXTURE = ROOT / "tests" / "fixtures" / "rename-concept-java" / "host"
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(
    JAVA is None or JAVAC is None, reason="JDK 17 is required"
)


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    assert _run("git", "init", "--quiet", cwd=host).returncode == 0
    assert _run("git", "add", "-A", cwd=host).returncode == 0
    return host


def _installed(tmp_path: Path) -> Path:
    root = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(SKILL, root / "rename-concept")
    shutil.copytree(DETECTOR, root / "find-concept-divergence")
    return root / "rename-concept"


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts
    }


def _native_compile(host: Path) -> None:
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    classes = host / ".classes"
    result = _run(
        JAVAC,
        "--release",
        "17",
        "-proc:none",
        "-d",
        str(classes),
        *sources,
        cwd=host,
    )
    shutil.rmtree(classes, ignore_errors=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _assess(
    skill: Path,
    host: Path,
    name: str,
    *,
    env: dict[str, str] | None = None,
    strict_candidate: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / "reports" / "rename-concept" / f"{name}.json"
    report = output.with_suffix(".md")
    args = [
        str(PYTHON),
        "-I",
        "-S",
        str(skill / "scripts" / "assess.py"),
        "legacy-status",
        "canonical-status",
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--report",
        str(report),
    ]
    if strict_candidate:
        args.extend(["--strict-candidate", str(host / "strict-candidate.jsonl")])
    return _run(*args, cwd=host, env=env), output, report


def _documented_command(skill: Path) -> str:
    text = (skill / "knowledge" / "java-v1.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:java-assessment:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:java-assessment:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_java_candidate_reaches_final_impact_artifacts_without_source_mutation(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    installed = _installed(tmp_path)
    _native_compile(host)
    before = _fingerprints(host)

    result, output, report = _assess(installed, host, "dirty")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = json.loads(output.read_text(encoding="utf-8"))
    evidence = payload["java_identifier_evidence"]
    assert evidence["status"] == "resolved"
    assert evidence["authority_status"] == "resolved"
    assert {item["name"] for item in evidence["declarations"]["old"]} == {"LegacyStatus"}
    assert {item["name"] for item in evidence["declarations"]["new"]} == {"CanonicalStatus"}
    assert {item["classification"] for item in evidence["occurrences"]} >= {
        "old_concept_symbol",
        "new_concept_symbol",
        "shadowed_or_unrelated_symbol",
    }
    assert {item["kind"] for item in evidence["deferred_references"]} >= {
        "reflection_string_reference",
        "framework_annotation_reference",
        "generated_source_reference",
        "test_source_reference",
        "vendor_source_reference",
        "build_source_reference",
    }
    assert payload["strict_candidate_inputs"] == ["strict-candidate.jsonl"]
    assert payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
    rendered = report.read_text(encoding="utf-8")
    assert "Compiler-resolved Java impact" in rendered
    assert "TypeElement" in rendered
    assert "Reflection and dynamic references are deferred" in rendered
    assert "no source edits" in rendered


def test_java_clean_rename_can_complete_with_public_new_authority(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = _installed(tmp_path)
    (host / "src/main/java/example/status/LegacyStatus.java").unlink()
    transition = host / "src/main/java/example/app/Transition.java"
    transition.write_text(
        "package example.app;\n\n"
        "import example.status.CanonicalStatus;\n\n"
        "public final class Transition {\n"
        "    public CanonicalStatus convert(CanonicalStatus input) { return input; }\n"
        "}\n",
        encoding="utf-8",
    )
    (host / "src/main/java/example/app/ReflectionLookup.java").unlink()
    shutil.rmtree(host / "src/test")
    shutil.rmtree(host / "generated")
    shutil.rmtree(host / "vendor")
    shutil.rmtree(host / "build")
    (host / "strict-candidate.jsonl").unlink()
    assert _run("git", "add", "-A", cwd=host).returncode == 0
    _native_compile(host)
    before = _fingerprints(host)

    result, output, _ = _assess(
        installed, host, "clean", strict_candidate=False
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    evidence = payload["java_identifier_evidence"]
    assert evidence["authority_status"] == "resolved"
    assert evidence["declarations"]["old"] == []
    assert len(evidence["declarations"]["new"]) == 1
    assert evidence["deferred_references"] == []
    assert payload["verdict"] in {"COMPLETE", "LIKELY COMPLETE"}
    assert _fingerprints(host) == before


def test_java_malformed_nonpublic_ambiguous_missing_and_old_jdk_are_not_clean(
    tmp_path: Path,
) -> None:
    malformed = _host(tmp_path / "malformed")
    installed = _installed(tmp_path / "malformed-install")
    (malformed / "src/main/java/example/app/Broken.java").write_text(
        "package example.app; public final class Broken {",
        encoding="utf-8",
    )
    result, output, _ = _assess(installed, malformed, "malformed")
    assert result.returncode == 0
    malformed_payload = json.loads(output.read_text(encoding="utf-8"))
    assert malformed_payload["java_identifier_evidence"]["status"] == "failed"
    assert malformed_payload["verdict"] == "HALF-APPLIED / INCOMPLETE"

    nonpublic = _host(tmp_path / "nonpublic")
    canonical = nonpublic / "src/main/java/example/status/CanonicalStatus.java"
    canonical.write_text(
        canonical.read_text(encoding="utf-8").replace(
            "public final class CanonicalStatus", "final class CanonicalStatus"
        ),
        encoding="utf-8",
    )
    (nonpublic / "src/main/java/example/app/Transition.java").write_text(
        "package example.app; public final class Transition {}\n",
        encoding="utf-8",
    )
    result, output, _ = _assess(installed, nonpublic, "nonpublic")
    assert result.returncode == 0
    nonpublic_payload = json.loads(output.read_text(encoding="utf-8"))
    assert nonpublic_payload["java_identifier_evidence"]["authority_status"] == "missing_new_authority"
    assert nonpublic_payload["verdict"] == "HALF-APPLIED / INCOMPLETE"

    ambiguous = _host(tmp_path / "ambiguous")
    duplicate = ambiguous / "src/main/java/other/status/CanonicalStatus.java"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(
        "package other.status; public final class CanonicalStatus {}\n",
        encoding="utf-8",
    )
    result, output, _ = _assess(installed, ambiguous, "ambiguous")
    assert result.returncode == 0
    ambiguous_payload = json.loads(output.read_text(encoding="utf-8"))
    assert ambiguous_payload["java_identifier_evidence"]["authority_status"] == "ambiguous_new_authority"
    assert ambiguous_payload["verdict"] == "HALF-APPLIED / INCOMPLETE"

    missing = _host(tmp_path / "missing")
    missing_bin = tmp_path / "missing-bin"
    missing_bin.mkdir()
    missing_env = {**os.environ, "PATH": str(missing_bin)}
    result, output, _ = _assess(installed, missing, "missing", env=missing_env)
    assert result.returncode == 0
    missing_payload = json.loads(output.read_text(encoding="utf-8"))
    assert missing_payload["java_identifier_evidence"]["status"] == "unavailable"
    assert missing_payload["verdict"] == "INCONCLUSIVE"

    old = _host(tmp_path / "old")
    fake_bin = tmp_path / "old-bin"
    fake_bin.mkdir()
    fake_java = fake_bin / "java"
    fake_java.write_text("#!/bin/sh\nprintf '%s\\n' 'openjdk version \"11.0.22\"' >&2\n", encoding="utf-8")
    fake_java.chmod(0o755)
    fake_javac = fake_bin / "javac"
    fake_javac.write_text("#!/bin/sh\nprintf '%s\\n' 'javac 11.0.22' >&2\n", encoding="utf-8")
    fake_javac.chmod(0o755)
    old_env = {**os.environ, "PATH": f"{fake_bin}:/usr/bin:/bin"}
    result, output, _ = _assess(installed, old, "old", env=old_env)
    assert result.returncode == 0
    old_payload = json.loads(output.read_text(encoding="utf-8"))
    assert old_payload["java_identifier_evidence"]["status"] == "unsupported"
    assert "JDK 17" in old_payload["java_identifier_evidence"]["reason"]
    assert old_payload["verdict"] == "INCONCLUSIVE"


def test_java_documented_copied_command_runs_without_repository_dependencies(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    installed = host / ".agents" / "skills"
    shutil.copytree(SKILL, installed / "rename-concept")
    shutil.copytree(DETECTOR, installed / "find-concept-divergence")
    _native_compile(host)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed / "rename-concept"),
        cwd=host,
        env={
            **os.environ,
            "OLD_CONCEPT": "legacy-status",
            "NEW_CONCEPT": "canonical-status",
            "RENAME_STRICT_CANDIDATE": "strict-candidate.jsonl",
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = host / "reports/rename-concept/java-assessment.json"
    report = output.with_suffix(".md")
    assert output.is_file() and report.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["java_identifier_evidence"]["status"] == "resolved"
    assert (installed / "rename-concept/scripts/java_identifier_evidence.java").is_file()
    closure = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (installed / "rename-concept").rglob("*")
        if path.is_file()
    )
    assert str(ROOT) not in closure
    assert "scripts/_lib" not in closure
