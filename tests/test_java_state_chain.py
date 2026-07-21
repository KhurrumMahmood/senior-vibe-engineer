"""Locked Java 17 outcome proof for the state-maintenance chain."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "find-implicit-state-java"
FIND = ROOT / ".claude" / "skills" / "find-implicit-state"


def _jdk() -> Path:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        pytest.skip("JDK 17 is unavailable")
    result = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = result.stdout + result.stderr
    if result.returncode or not rendered.startswith("javac 17"):
        pytest.skip("JDK 17 is unavailable")
    return Path(java).parent


def _env(*, path: str | None = None) -> dict[str, str]:
    jdk = _jdk()
    return {**os.environ, "PATH": path if path is not None else f"{jdk}{os.pathsep}{os.environ.get('PATH', '')}"}


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    sources = sorted(str(path.relative_to(host)) for path in host.rglob("*.java"))
    native = _run(
        "javac", "--release", "17", "-proc:none", "-d", str(host / "classes"), *sources,
        cwd=host, env=_env(),
    )
    assert native.returncode == 0, native.stdout + native.stderr
    shutil.rmtree(host / "classes")
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _detect(skill: Path, host: Path, output: Path, *, isolated: bool = False, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "detect_java_state.py"),
        "--target", str(host),
        "--project-root", str(host),
        "--output", str(output / "hits.jsonl"),
        "--findings", str(output / "findings.json"),
        "--report", str(output / "report.md"),
        "--scan-id", "java-state-fixture",
        cwd=host,
        env=env or _env(),
    )


def test_java_state_detector_reaches_final_review_artifacts_from_copied_closure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = tmp_path / "installed" / "find-implicit-state"
    shutil.copytree(FIND, installed)
    before = _fingerprints(host)
    report = host / "reports" / "implicit-state" / "java-state"

    result = _detect(installed, host, report, isolated=True)

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(report / "hits.jsonl")
    status = records[0]
    assert status == {
        "record_kind": "analysis_status",
        "status": "complete",
        "analyzer": "jdk-compiler-tree-type-api",
        "unavailable_files": [],
    }
    candidate_operations = [row for row in records if row.get("classification") == "first_party_state_operation"]
    assert len(candidate_operations) == 4
    assert {row["literal"] for row in candidate_operations} == {"queued", "running", "done"}
    assert {row["operation"] for row in candidate_operations} == {"assignment", "string_equals", "objects_equals"}
    assert {row["field_owner"] for row in candidate_operations} == {"example.Job"}
    unsafe = [row for row in records if row.get("classification") == "unsafe_string_comparison"]
    assert len(unsafe) == 1
    assert unsafe[0]["field_owner"] == "example.UnsafeJob"
    assert unsafe[0]["evidence_strength"] == "correctness_finding_not_enum_evidence"
    assert {row["role"] for row in records if row["record_kind"] == "source_inventory"} >= {
        "excluded_generated", "excluded_test", "excluded_vendor", "first_party",
    }
    assert any(row.get("field_owner") == "example.VendorJobPayload" and row.get("classification") == "vendor_wire_boundary" for row in records)
    assert any(row.get("field_owner") == "example.OneShot" and row.get("classification") == "insufficient_closed_state_evidence" for row in records)
    assert any(row.get("field_owner") == "example.Label" and row.get("classification") == "unrelated_string_field" for row in records)
    assert not any(row.get("field_owner") == "example.CleanJob" for row in records)

    findings = json.loads((report / "findings.json").read_text(encoding="utf-8"))
    assert findings["status"] == "complete"
    assert findings["analysis"]["analyzer"] == "jdk-compiler-tree-type-api"
    accepted = [row for row in findings["findings"] if row["bucket"] == "extract_enum_candidate"]
    assert len(accepted) == 1
    assert accepted[0]["finding_id"] == "java-implicit-state-0001"
    assert accepted[0]["authority"]["qualified_owner"] == "example.Job"
    assert accepted[0]["authority"]["field"] == "status"
    unsafe_findings = [row for row in findings["findings"] if row["bucket"] == "unsafe_string_comparison"]
    assert len(unsafe_findings) == 1
    assert unsafe_findings[0]["not_enum_evidence"] is True
    rendered = (report / "report.md").read_text(encoding="utf-8")
    assert "Accepted enum-review candidates" in rendered
    assert "not evidence that an enum is appropriate" in rendered
    assert before == _fingerprints(host)


def test_java_state_detector_rejects_malformed_and_missing_or_old_jdk_without_artifacts(tmp_path: Path) -> None:
    host = _host(tmp_path)
    output = host / "reports" / "implicit-state" / "broken"
    (host / "src" / "main" / "java" / "example" / "Broken.java").write_text(
        "package example; public final class Broken { void bad( { }\n", encoding="utf-8"
    )
    malformed = _detect(FIND, host, output)
    assert malformed.returncode == 2
    assert "syntax error" in malformed.stderr.lower()
    assert not output.exists()
    (host / "src" / "main" / "java" / "example" / "Broken.java").unlink()

    missing = _detect(FIND, host, output, env=_env(path=""))
    assert missing.returncode == 2
    assert "jdk is unavailable" in missing.stderr.lower()
    assert not output.exists()

    fake = tmp_path / "old-java"
    fake.write_text("#!/bin/sh\necho 'openjdk version \"11.0.22\"' >&2\n", encoding="utf-8")
    fake.chmod(0o755)
    old = _run(
        sys.executable, str(FIND / "scripts" / "detect_java_state.py"),
        "--target", str(host), "--project-root", str(host),
        "--output", str(output / "hits.jsonl"), "--findings", str(output / "findings.json"),
        "--report", str(output / "report.md"), "--java-executable", str(fake),
        "--javac-executable", shutil.which("javac") or "javac", cwd=host, env=_env(),
    )
    assert old.returncode == 2
    assert "requires jdk >= 17" in old.stderr.lower()
    assert not output.exists()
