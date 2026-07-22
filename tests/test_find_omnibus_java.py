"""Java final-outcome, boundary, and copied-closure proof for find-omnibus."""
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
SKILL = ROOT / ".claude" / "skills" / "find-omnibus"
FIXTURE = ROOT / "tests" / "fixtures" / "find-omnibus-java"


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


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _detect(
    skill: Path,
    host: Path,
    output: Path,
    env: dict[str, str],
    target: Path,
    *,
    isolated: bool = False,
    language: str | None = "java",
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    command = [
        *prefix,
        str(skill / "scripts" / "detect.py"),
        "--target",
        str(target),
        "--project-root",
        str(host),
        "--output",
        str(output),
    ]
    if language is not None:
        command.extend(("--language", language))
    return _run(*command, cwd=host, env=env)


def _pipeline(
    skill: Path, host: Path, env: dict[str, str], output: Path, *, isolated: bool = False
) -> tuple[list[dict], dict]:
    detections = output / "omnibus.jsonl"
    detect = _detect(skill, host, detections, env, host, isolated=isolated)
    assert detect.returncode == 0, detect.stdout + detect.stderr
    candidates = output / "candidates.jsonl"
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    collapse = _run(
        *prefix,
        str(skill / "scripts" / "collapse.py"),
        "--detections",
        str(detections),
        "--output",
        str(candidates),
        cwd=host,
        env=env,
    )
    assert collapse.returncode == 0, collapse.stdout + collapse.stderr
    candidate = _records(candidates)[0]
    scout = output / "scout"
    scout.mkdir()
    (scout / f"{candidate['candidate_id']}.json").write_text(
        json.dumps({
            "candidate_id": candidate["candidate_id"],
            "file": candidate["file"],
            "bucket": "confirmed_omnibus",
            "domains_confirmed": ["invoice", "shipment", "customer", "inventory"],
            "facets_collapsed": [],
            "srp_rewrite": "This Java class handles four independent record domains.",
            "decomposition_sketch": [],
            "decomposition_depth_note": "Each domain has a separate public surface.",
            "false_positive_reason": None,
            "notes": "Locked Java outcome fixture.",
            "recommendation": "decompose",
        }),
        encoding="utf-8",
    )
    report = _run(
        *prefix,
        str(skill / "scripts" / "report.py"),
        "--candidates",
        str(candidates),
        "--scout-dir",
        str(scout),
        "--output-md",
        str(output / "report.md"),
        "--output-json",
        str(output / "findings.json"),
        "--scan-id",
        "j3-java",
        "--target",
        ".",
        cwd=host,
        env=env,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    return _records(detections), json.loads((output / "findings.json").read_text(encoding="utf-8"))


def _assert_outcome(records: list[dict], findings: dict) -> None:
    assert [record["file"] for record in records] == ["src/main/java/example/OmnibusService.java"]
    record = records[0]
    assert record["language"] == "java"
    assert record["analyzer"] == "jdk-compiler-tree-api"
    assert record["and_count"] == 3
    clusters = {cluster["name"]: cluster["symbols"] for cluster in record["clusters"]}
    assert set(clusters) == {"invoice", "shipment", "customer", "inventory"}
    assert "OmnibusService.saveInvoiceRecord" in clusters["invoice"]
    assert findings["status"] == "complete"
    assert findings["analysis"]["java"]["status"] == "complete"
    assert findings["analysis"]["java"]["analyzer"] == "jdk-compiler-tree-api"
    assert findings["analysis"]["java"]["minimum_jdk_version"] == "17.0.0"
    assert findings["summary"]["bucket_counts"]["confirmed_omnibus"] == 1


def test_java_pipeline_reaches_final_report_without_source_changes(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    before = _fingerprints(host)

    records, findings = _pipeline(SKILL, host, env, host / "reports" / "java")

    _assert_outcome(records, findings)
    report = (host / "reports" / "java" / "report.md").read_text(encoding="utf-8")
    assert "**Status:** `complete`" in report
    assert "jdk-compiler-tree-api" in report
    assert _fingerprints(host) == before


def test_copied_java_closure_is_self_contained(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    copied = tmp_path / "on-demand" / "find-omnibus"
    shutil.copytree(SKILL, copied)

    records, findings = _pipeline(copied, host, env, host / "reports" / "copied", isolated=True)

    _assert_outcome(records, findings)
    assert (copied / "scripts" / "detect_java_symbols.java").is_file()


def test_java_boundaries_and_tool_failures_are_explicit(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; class Broken { void bad( { } }\n", encoding="utf-8")
    broken_output = host / "broken.jsonl"

    syntax = _detect(SKILL, host, broken_output, env, host / "src")
    assert syntax.returncode == 2
    assert "syntax error" in syntax.stderr.lower()
    assert not broken_output.exists()
    broken.unlink()

    unresolved = host / "src" / "main" / "java" / "example" / "Unresolved.java"
    unresolved.write_text(
        "package example; class Unresolved { MissingType missing; "
        "static void saveInvoiceRecord() {} static void loadInvoiceRecord() {} "
        "static void createShipmentLabel() {} static void cancelShipmentLabel() {} "
        "static void getCustomerProfile() {} static void listCustomerProfile() {} "
        "static void getInventoryItem() {} static void listInventoryItem() {} }\n",
        encoding="utf-8",
    )
    unresolved_output = host / "unresolved.jsonl"
    unresolved_result = _detect(SKILL, host, unresolved_output, env, host / "src")
    assert unresolved_result.returncode == 0, unresolved_result.stdout + unresolved_result.stderr
    assert any(record["file"].endswith("Unresolved.java") for record in _records(unresolved_output))

    outside = tmp_path / "Outside.java"
    outside.write_text("class Outside {}\n", encoding="utf-8")
    (host / "src" / "main" / "java" / "example" / "Outside.java").symlink_to(outside)
    filtered_output = host / "filtered.jsonl"
    filtered = _detect(SKILL, host, filtered_output, env, host)
    assert filtered.returncode == 0, filtered.stdout + filtered.stderr
    assert all(not record["file"].endswith("Outside.java") for record in _records(filtered_output))

    missing_output = host / "missing.jsonl"
    missing = _detect(SKILL, host, missing_output, _env(path=""), host / "src")
    assert missing.returncode == 2
    assert "JDK is unavailable" in missing.stderr
    assert not missing_output.exists()

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for name, version in (("java", 'openjdk version "11.0.22"'), ("javac", "javac 11.0.22")):
        tool = fake_bin / name
        tool.write_text(f"#!/bin/sh\necho '{version}' >&2\n", encoding="utf-8")
        tool.chmod(0o755)
    old_output = host / "old.jsonl"
    old = _detect(SKILL, host, old_output, _env(path=str(fake_bin)), host / "src")
    assert old.returncode == 2
    assert "JDK >= 17.0.0" in old.stderr
    assert not old_output.exists()


def test_java_failure_rerun_invalidates_prior_pipeline_output(tmp_path: Path) -> None:
    host, env = _host(tmp_path)
    report_dir = host / "reports" / "lifecycle"
    output = report_dir / "omnibus.jsonl"
    _pipeline(SKILL, host, env, report_dir)
    artifacts = (
        output,
        report_dir / "scan.json",
        report_dir / "candidates.jsonl",
        report_dir / "report.md",
        report_dir / "findings.json",
        report_dir / "scout",
    )
    assert all(path.exists() for path in artifacts)

    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; class Broken { void bad( { } }\n", encoding="utf-8")
    syntax = _detect(SKILL, host, output, env, host / "src")
    assert syntax.returncode == 2
    assert "syntax error" in syntax.stderr.lower()
    assert all(not path.exists() for path in artifacts)

    broken.unlink()
    _pipeline(SKILL, host, env, report_dir)
    missing = _detect(SKILL, host, output, _env(path=""), host / "src")
    assert missing.returncode == 2
    assert "JDK is unavailable" in missing.stderr
    assert all(not path.exists() for path in artifacts)


def test_documented_generic_java_scan_is_terminal_and_invalidates_stale_output(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    report_dir = host / "reports" / "omnibus" / "scan-generic"
    output = report_dir / "omnibus.jsonl"

    detected = _detect(SKILL, host, output, env, host, language=None)
    assert detected.returncode == 0, detected.stdout + detected.stderr
    assert _records(output)
    scan = json.loads((report_dir / "scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["language"] == "java"

    candidates = report_dir / "candidates.jsonl"
    collapsed = _run(
        sys.executable,
        str(SKILL / "scripts" / "collapse.py"),
        "--detections",
        str(output),
        "--output",
        str(candidates),
        cwd=host,
        env=env,
    )
    assert collapsed.returncode == 0, collapsed.stdout + collapsed.stderr
    assert _records(candidates)

    broken = host / "src" / "main" / "java" / "example" / "Broken.java"
    broken.write_text("package example; class Broken { void bad( { } }\n", encoding="utf-8")
    malformed = _detect(SKILL, host, output, env, host, language=None)

    assert malformed.returncode == 2
    assert "syntax error" in malformed.stderr.lower()
    assert not output.exists()
    assert not (report_dir / "scan.json").exists()
    assert not candidates.exists()


def test_documented_generic_empty_target_in_java_project_is_unsupported(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    target = host / "empty"
    target.mkdir()
    report_dir = host / "reports" / "omnibus" / "scan-empty"
    output = report_dir / "omnibus.jsonl"

    unsupported = _detect(SKILL, host, output, env, target, language=None)

    assert unsupported.returncode == 2
    assert output.read_bytes() == b""
    scan = json.loads((report_dir / "scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "unsupported"
    assert scan["language"] == "java"
    assert scan["failure_kind"] == "no-java-files"
    assert scan["summary"] == {"discovered": 0, "eligible": 0, "excluded": 0}


def test_generic_mixed_language_target_preserves_legacy_multilanguage_mode(
    tmp_path: Path,
) -> None:
    host, env = _host(tmp_path)
    (host / "cohesive.py").write_text("def load_invoice():\n    return 1\n", encoding="utf-8")
    report_dir = host / "reports" / "omnibus" / "scan-mixed"
    output = report_dir / "omnibus.jsonl"

    detected = _detect(SKILL, host, output, env, host, language=None)

    assert detected.returncode == 0, detected.stdout + detected.stderr
    assert {record["language"] for record in _records(output)} == {"java"}
    assert not (report_dir / "scan.json").exists()


@pytest.mark.parametrize("target_name", ("vendor", "src/test", "empty"))
def test_java_no_eligible_target_is_unsupported_and_final_output_is_honest(
    tmp_path: Path, target_name: str
) -> None:
    host, env = _host(tmp_path)
    target = host / target_name
    if target_name == "empty":
        target.mkdir()
    report_dir = host / "reports" / target_name.replace("/", "-")
    output = report_dir / "omnibus.jsonl"

    unsupported = _detect(SKILL, host, output, env, target)

    assert unsupported.returncode == 2
    assert _records(output) == []
    scan = json.loads((report_dir / "scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "unsupported"
    assert scan["analyzer"] == "jdk-compiler-tree-api"
    assert scan["summary"]["eligible"] == 0

    candidates = report_dir / "candidates.jsonl"
    collapsed = _run(
        sys.executable,
        str(SKILL / "scripts" / "collapse.py"),
        "--detections",
        str(output),
        "--output",
        str(candidates),
        cwd=host,
        env=env,
    )
    assert collapsed.returncode == 0, collapsed.stdout + collapsed.stderr
    report = _run(
        sys.executable,
        str(SKILL / "scripts" / "report.py"),
        "--candidates",
        str(candidates),
        "--scout-dir",
        str(report_dir / "scout"),
        "--output-md",
        str(report_dir / "report.md"),
        "--output-json",
        str(report_dir / "findings.json"),
        "--scan-id",
        "no-eligible-java",
        "--target",
        target_name,
        cwd=host,
        env=env,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    findings = json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))
    rendered = (report_dir / "report.md").read_text(encoding="utf-8")
    assert findings["status"] == "unsupported"
    assert findings["analysis"]["java"] == scan
    assert "not a clean omnibus result" in rendered

    kotlin = host / "kotlin"
    kotlin.mkdir()
    (kotlin / "Ignored.kt").write_text("package example\nfun ignored() = 1\n", encoding="utf-8")
    kotlin_output = host / "kotlin.jsonl"
    unsupported = _detect(SKILL, host, kotlin_output, env, kotlin)
    assert unsupported.returncode == 2
    assert "Kotlin source is unsupported" in unsupported.stderr
    assert not kotlin_output.exists()


def test_java_frontmatter_declares_narrow_support() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "scans: [python, javascript, typescript, go, java]" in text
    assert "--language python|javascript|typescript|go|java" in text
    assert "JDK 17" in text
    assert "does not resolve imports, types, aliases, overloads, receivers, or frameworks" in " ".join(text.split())
