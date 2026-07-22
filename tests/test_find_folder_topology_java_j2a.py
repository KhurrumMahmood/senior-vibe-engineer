"""Java filename-topology outcome and copied-closure proof."""
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
SKILL = REPO_ROOT / ".claude" / "skills" / "find-folder-topology-drift"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-folder-topology-java-j2a"
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(JAVAC is None, reason="JDK is required for fixture validation")


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    sources = [str(path) for path in sorted(host.rglob("*.java"))]
    native = _run(
        JAVAC,
        "--release",
        "17",
        "-proc:none",
        "-d",
        str(tmp_path / "classes"),
        *sources,
        cwd=host,
    )
    assert native.returncode == 0, native.stdout + native.stderr
    return host


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(root).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _detect(skill: Path, host: Path, output: Path, root: str = ".") -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--java-root",
        root,
        "--output",
        str(output),
        cwd=host,
        env={**os.environ, "PATH": ""},
    )


def test_java_cluster_reaches_final_report_with_inventory_and_no_mutation(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "topology" / "detections.jsonl"

    detected = _detect(SKILL, host, output)

    assert detected.returncode == 0, detected.stdout + detected.stderr
    records = _records(output)
    assert len(records) == 1
    assert records[0]["language"] == "java"
    assert records[0]["pattern"] == "flat_prefix_cluster"
    assert records[0]["prefix"] == "billing"
    assert records[0]["files"] == [
        "src/main/java/example/billing/BillingParser.java",
        "src/main/java/example/billing/BillingTypes.java",
        "src/main/java/example/billing/BillingValidator.java",
    ]

    report = output.with_name("report.md")
    findings_path = output.with_name("findings.json")
    rendered = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "report.py"),
        "--detections",
        str(output),
        "--output-md",
        str(report),
        "--output-json",
        str(findings_path),
        "--target",
        ".",
        "--language",
        "java",
        cwd=host,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    java = findings["analysis"]["java"]
    assert findings["status"] == java["status"] == "complete"
    assert java["analyzer"] == "python-filesystem-names"
    inventory = {row["file"]: row for row in java["inventory"]}
    assert inventory["src/main/java/example/billing/BillingParser.java"]["role"] == "eligible"
    assert inventory["src/test/java/example/billing/BillingTest.java"]["reason"] == "test-tree"
    assert inventory["src/generated/java/example/billing/BillingAdapter.java"]["reason"] == "generated-tree"
    assert inventory["src/main/java/example/billing/BillingWire.java"]["reason"] == "generated-marker"
    assert inventory["vendor/example/thirdparty/BillingClient.java"]["reason"] == "vendor"
    assert "**Status:** `complete`" in report.read_text(encoding="utf-8")
    assert _hashes(host) == before


def test_java_folder_scan_is_filename_only_across_malformed_source(tmp_path: Path) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    output = host / "reports" / "detections.jsonl"

    result = _detect(SKILL, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    assert [row["prefix"] for row in _records(output)] == ["billing"]
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "filename-only; Java parse validity is not inspected"


def test_java_folder_statuses_paths_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host = _host(tmp_path)
    linked = host / "src/main/java/example/billing/BillingLinked.java"
    linked.symlink_to(host / "src/main/java/example/billing/BillingParser.java")
    installed = tmp_path / "installed" / "find-folder-topology-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "copied" / "detections.jsonl"

    copied = _detect(installed, host, output)

    assert copied.returncode == 0, copied.stdout + copied.stderr
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    inventory = {row["file"]: row for row in scan["inventory"]}
    assert inventory["src/main/java/example/billing/BillingLinked.java"]["reason"] == "symlink"

    unreadable = host / "src/main/java/example/billing/BillingUnreadable.java"
    unreadable.write_bytes(b"class BillingUnreadable { // \xff\n}")
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _detect(installed, host, partial_output)
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert json.loads(partial_output.with_name("scan.json").read_text())["status"] == "partial"

    empty = tmp_path / "empty"
    empty.mkdir()
    unsupported_output = empty / "reports" / "detections.jsonl"
    unsupported = _detect(installed, empty, unsupported_output)
    assert unsupported.returncode == 2
    unsupported_scan = json.loads(unsupported_output.with_name("scan.json").read_text())
    assert unsupported_scan["status"] == "unsupported"
    assert unsupported_scan["failure_kind"] == "no-java-files"

    missing_output = host / "reports" / "missing" / "detections.jsonl"
    missing = _detect(installed, host, missing_output, "missing")
    assert missing.returncode == 2
    assert not missing_output.exists()

    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").glob("*.py")
    )
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure


def test_java_rerun_invalidates_prior_complete_artifacts(tmp_path: Path) -> None:
    host = _host(tmp_path)
    output = host / "reports" / "lifecycle" / "detections.jsonl"
    report = output.with_name("report.md")
    findings = output.with_name("findings.json")

    initial = _detect(SKILL, host, output)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    rendered = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "report.py"),
        "--detections",
        str(output),
        "--output-md",
        str(report),
        "--output-json",
        str(findings),
        "--target",
        ".",
        "--language",
        "java",
        cwd=host,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert all(path.is_file() for path in (output, output.with_name("scan.json"), report, findings))

    missing = _detect(SKILL, host, output, "missing")
    assert missing.returncode == 2
    assert all(not path.exists() for path in (output, output.with_name("scan.json"), report, findings))

    restored = _detect(SKILL, host, output)
    assert restored.returncode == 0, restored.stdout + restored.stderr
    rerendered = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "report.py"),
        "--detections",
        str(output),
        "--output-md",
        str(report),
        "--output-json",
        str(findings),
        "--target",
        ".",
        "--language",
        "java",
        cwd=host,
    )
    assert rerendered.returncode == 0, rerendered.stdout + rerendered.stderr

    unreadable = host / "src/main/java/example/billing/BillingUnreadable.java"
    unreadable.write_bytes(b"class BillingUnreadable { // \xff\n}")
    partial = _detect(SKILL, host, output)
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))["status"] == "partial"
    assert not report.exists()
    assert not findings.exists()


def test_java_folder_docs_are_lazy_and_name_native_boundary() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    java = (SKILL / "references" / "java.md").read_text(encoding="utf-8")

    assert len(text.splitlines()) < 500
    assert "references/java.md" in text
    assert "--java-root" in java
    assert "python-filesystem-names" in java
    assert "javac --release 17 -proc:none" in java
    assert "does not require a JDK" in java
    assert "Kotlin" in java
