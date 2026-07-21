"""Java outcome, boundary, and copied-closure proof for complexity hotspots."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-complexity-hotspots"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-complexity-hotspots-java"


def _jdk_bin() -> Path:
    found = shutil.which("javac")
    if found:
        return Path(found)
    pytest.skip("JDK 17 compiler is unavailable")


def _java_env(*, path: str | None = None) -> dict[str, str]:
    javac = _jdk_bin()
    return {
        **os.environ,
        "PATH": path if path is not None else f"{javac.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _copy_host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = _java_env()
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    compiled = _run(
        "javac",
        "--release",
        "17",
        "-d",
        str(host / "classes"),
        *sources,
        cwd=host,
        env=env,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    shutil.rmtree(host / "classes")
    return host, env


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_pipeline(
    skill: Path,
    host: Path,
    env: dict[str, str],
    *,
    isolated: bool = False,
) -> tuple[dict, list[dict]]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    result = _run(
        *prefix,
        str(skill / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "java",
        "--skip-effectiveness-log",
        "src",
        cwd=host,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    payload = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    return payload, _records(report_dir / "detections.jsonl")


def _assert_java_outcome(payload: dict, records: list[dict]) -> None:
    assert payload["status"] == "complete"
    assert payload["summary"]["findings_total"] == 2
    assert payload["analysis"]["java"]["status"] == "complete"
    assert payload["analysis"]["java"]["analyzer"] == "jdk-compiler-tree-api"
    assert payload["analysis"]["java"]["minimum_jdk_version"] == "17.0.0"
    assert {record["file"] for record in records} == {
        "src/main/java/example/ComplexityService.java"
    }
    assert {record["symbol"] for record in records} == {
        "ComplexityService.ComplexityService",
        "ComplexityService.declaredHotspot",
    }
    assert {record["kind"] for record in records} == {"constructor", "method"}
    assert {record["language"] for record in records} == {"java"}
    assert {record["analyzer"] for record in records} == {"jdk-compiler-tree-api"}
    assert {record["branch_score"] for record in records} == {18}
    for record in records:
        source = (FIXTURE / record["file"]).read_text(encoding="utf-8").splitlines()
        assert record["symbol"].split(".")[-1] in source[record["lineno"] - 1]
        assert source[record["end_lineno"] - 1].strip() == "}"


def test_java_outcome_reaches_final_report_with_provenance_and_no_source_mutation(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    before = _fingerprints(host)

    payload, records = _run_pipeline(SKILL, host, env)

    _assert_java_outcome(payload, records)
    assert _fingerprints(host) == before
    report = (host / "reports" / "find-complexity-hotspots" / "latest" / "report.md").read_text(
        encoding="utf-8"
    )
    assert "**Status:** complete" in report
    assert "jdk-compiler-tree-api" in report


def test_java_direct_exclusions_and_nested_lambda_do_not_fire(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    linked = host / "src" / "main" / "java" / "example" / "Linked.java"
    linked.symlink_to("ComplexityService.java")
    linked_tree = host / "src" / "linked-java"
    linked_tree.symlink_to("main/java", target_is_directory=True)
    excluded_source = (
        host / "vendor" / "example" / "thirdparty" / "VendorHotspot.java"
    ).read_text(encoding="utf-8")
    integration = host / "src" / "integrationTest" / "java" / "example" / "IntegrationOnly.java"
    integration.parent.mkdir(parents=True)
    integration.write_text(
        excluded_source.replace("package example.thirdparty;", "package example;")
        .replace("VendorHotspot", "IntegrationOnly"),
        encoding="utf-8",
    )
    test_fixture = host / "src" / "testFixtures" / "java" / "example" / "FixtureOnly.java"
    test_fixture.parent.mkdir(parents=True)
    test_fixture.write_text(
        excluded_source.replace("package example.thirdparty;", "package example;")
        .replace("VendorHotspot", "FixtureOnly"),
        encoding="utf-8",
    )
    targets = (
        "src/main/java/example/CleanService.java",
        "src/main/java/example/NestedLambda.java",
        "src/main/java/example/GeneratedService.java",
        "src/test/java/example/ComplexityServiceTest.java",
        "vendor/example/thirdparty/VendorHotspot.java",
        "src/main/java/example/Linked.java",
        "src/linked-java/example/ComplexityService.java",
        "src/integrationTest/java/example/IntegrationOnly.java",
        "src/testFixtures/java/example/FixtureOnly.java",
    )
    for index, target in enumerate(targets):
        output = host / f"excluded-{index}.jsonl"
        result = _run(
            sys.executable,
            str(SKILL / "scripts" / "detect.py"),
            "--project-root",
            str(host),
            "--output",
            str(output),
            "--language",
            "java",
            target,
            cwd=host,
            env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert _records(output) == [], target

    payload, _records_after_exclusions = _run_pipeline(SKILL, host, env)
    assert {
        (row["file"], row["reason"])
        for row in payload["analysis"]["java"]["exclusions"]
    } >= {("src/main/java/example/Linked.java", "symlink_boundary")}


@pytest.mark.parametrize(
    ("target", "eligible"),
    (
        ("vendor/example/thirdparty/VendorHotspot.java", 0),
        ("src/main/java/example/GeneratedService.java", 1),
    ),
)
def test_java_exclusion_only_run_is_partial_and_visible_in_report(
    tmp_path: Path, target: str, eligible: int
) -> None:
    host, env = _copy_host(tmp_path)
    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "java",
        "--skip-effectiveness-log",
        target,
        cwd=host,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report_dir = (host / "reports" / "find-complexity-hotspots" / "latest").resolve()
    payload = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    report = (report_dir / "report.md").read_text(encoding="utf-8")
    assert payload["status"] == "partial"
    assert payload["analysis"]["java"]["files"]["eligible"] == eligible
    assert "0 analyzed, 1 excluded" in report
    assert target in report
    assert "no eligible Java source" in report


def test_java_syntax_and_tool_failures_are_explicit_and_not_clean(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; public class Broken { void bad( { } }\n", encoding="utf-8")
    syntax = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "broken.jsonl"),
        "--language",
        "java",
        "src/main/java/example/Broken.java",
        cwd=host,
        env=env,
    )
    assert syntax.returncode == 2
    assert "Broken.java" in syntax.stderr
    assert "line 1" in syntax.stderr.lower()

    missing = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "missing.jsonl"),
        "--language",
        "java",
        "src/main/java/example/ComplexityService.java",
        cwd=host,
        env=_java_env(path=""),
    )
    assert missing.returncode == 2
    assert "jdk" in missing.stderr.lower()
    assert "unavailable" in missing.stderr.lower()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_javac = fake_bin / "javac"
    fake_javac.write_text(
        "#!/bin/sh\nif [ \"$1\" = \"-version\" ]; then echo 'javac 17.0.12'; exit 0; fi\nexit 99\n",
        encoding="utf-8",
    )
    fake_javac.chmod(0o755)
    fake_java = fake_bin / "java"
    fake_java.write_text(
        "#!/bin/sh\nif [ \"$1\" = \"-version\" ]; then echo 'Picked up JAVA_TOOL_OPTIONS: -XX:MaxRAMPercentage=75.0' >&2; echo 'openjdk version \"11.0.22\"' >&2; exit 0; fi\nexit 99\n",
        encoding="utf-8",
    )
    fake_java.chmod(0o755)
    old = _run(
        sys.executable,
        str(SKILL / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(host / "old.jsonl"),
        "--language",
        "java",
        "src/main/java/example/ComplexityService.java",
        cwd=host,
        env=_java_env(path=str(fake_bin)),
    )
    assert old.returncode == 2
    assert "requires jdk >= 17.0.0" in old.stderr.lower()


def test_malformed_java_rerun_invalidates_latest_report(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    _run_pipeline(SKILL, host, env)
    latest = host / "reports" / "find-complexity-hotspots" / "latest"
    previous_report = latest.resolve()
    (host / "src" / "main" / "java" / "example" / "Broken.java").write_text(
        "package example; public class Broken { void bad( { } }\n", encoding="utf-8"
    )

    result = _run(
        sys.executable,
        str(SKILL / "scripts" / "run.py"),
        "--project-root",
        str(host),
        "--language",
        "java",
        "--skip-effectiveness-log",
        "src",
        cwd=host,
        env=env,
    )

    assert result.returncode == 2
    assert "Broken.java" in result.stderr
    assert "line 1" in result.stderr.lower()
    assert not latest.exists()
    assert not latest.is_symlink()
    assert (previous_report / "findings.json").is_file()


def test_mixed_kotlin_evidence_is_partial_and_explicitly_unsupported(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    kotlin = host / "src" / "main" / "kotlin" / "example" / "Ignored.kt"
    kotlin.parent.mkdir(parents=True)
    kotlin.write_text("package example\nfun ignored() = 1\n", encoding="utf-8")

    payload, records = _run_pipeline(SKILL, host, env)

    assert payload["status"] == "partial"
    assert payload["analysis"]["java"]["status"] == "partial"
    assert payload["analysis"]["java"]["unsupported"] == [
        {
            "file": "src/main/kotlin/example/Ignored.kt",
            "reason": "kotlin_source_present",
        }
    ]
    assert {record["language"] for record in records} == {"java"}
    assert {record["branch_score"] for record in records} == {18}


def test_copied_skill_runs_without_toolkit_or_sibling_runtime(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-complexity-hotspots"
    shutil.copytree(SKILL, installed)

    payload, records = _run_pipeline(installed, host, env, isolated=True)

    _assert_java_outcome(payload, records)
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file()
    )
    assert "scripts/_lib" not in closure
    assert "/_common" not in closure
