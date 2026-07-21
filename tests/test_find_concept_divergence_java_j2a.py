"""Java strict-text outcome and copied-closure proof for concept divergence."""
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
SKILL = REPO_ROOT / ".claude" / "skills" / "find-concept-divergence"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-concept-divergence-java-j2a"
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


def _scan(skill: Path, host: Path, output: Path, *targets: str) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "scan.py"),
        "--project-root",
        str(host),
        "--language",
        "java",
        "--output",
        str(output),
        "--report",
        str(output.with_name("report.md")),
        *targets,
        cwd=host,
        env={**os.environ, "PATH": ""},
    )


def test_java_concepts_reach_final_report_with_inventory_and_no_mutation(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "concept" / "findings.jsonl"

    result = _scan(SKILL, host, output, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(output)
    assert len(records) == 4
    assert {record["file"] for record in records} == {"src/main/java/example/Checkout.java"}
    assert {record["band"] for record in records} == {
        "avoid_term_hit",
        "competing_term_coexistence",
        "superseded_co_occurrence",
    }
    assert {record["language"] for record in records} == {"java"}
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["analyzer"] == "python-strict-text"
    inventory = {row["file"]: row for row in scan["inventory"]}
    assert inventory["src/main/java/example/Checkout.java"]["role"] == "eligible"
    assert inventory["src/main/java/example/CleanCheckout.java"]["role"] == "eligible"
    assert inventory["src/test/java/example/CheckoutTest.java"]["reason"] == "test-tree"
    assert inventory["src/generated/java/example/GeneratedCheckout.java"]["reason"] == "generated-tree"
    assert inventory["src/main/java/example/WireGenerated.java"]["reason"] == "generated-marker"
    assert inventory["vendor/example/thirdparty/VendorCheckout.java"]["reason"] == "vendor"
    report = output.with_name("report.md").read_text(encoding="utf-8")
    assert "**Status:** `complete`" in report
    assert "**Language:** `java`" in report
    assert _hashes(host) == before


def test_java_concept_scan_is_textual_across_malformed_java(tmp_path: Path) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    output = host / "reports" / "findings.jsonl"

    result = _scan(SKILL, host, output, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    assert [(row["file"], row["term"]) for row in _records(output)] == [
        ("Broken.java", "legacy checkout")
    ]
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "strict-text; Java parse validity is not inspected"


def test_java_concept_statuses_symlink_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host = _host(tmp_path)
    (host / "linked.java").symlink_to(host / "src/main/java/example/Checkout.java")
    installed = tmp_path / "installed" / "find-concept-divergence"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "copied" / "findings.jsonl"

    copied = _scan(installed, host, output, ".")

    assert copied.returncode == 0, copied.stdout + copied.stderr
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    inventory = {row["file"]: row for row in scan["inventory"]}
    assert inventory["linked.java"]["reason"] == "symlink"

    (host / "src/main/java/example/Unreadable.java").write_bytes(b"class Unreadable { // \xff\n}")
    partial_output = host / "reports" / "partial" / "findings.jsonl"
    partial = _scan(installed, host, partial_output, ".")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_scan = json.loads(partial_output.with_name("scan.json").read_text())
    assert partial_scan["status"] == "partial"
    assert "**Status:** `partial`" in partial_output.with_name("report.md").read_text()

    closure = (installed / "scripts" / "scan.py").read_text(encoding="utf-8")
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure


def test_java_concept_docs_are_lazy_and_name_native_boundary() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    java = (SKILL / "references" / "java.md").read_text(encoding="utf-8")

    assert len(text.splitlines()) < 500
    assert "references/java.md" in text
    assert "python-strict-text" in java
    assert "javac --release 17 -proc:none" in java
    assert "does not require a JDK" in java
    assert "Kotlin" in java
