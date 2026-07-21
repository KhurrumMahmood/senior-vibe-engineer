"""Java lexical-comment outcome and copied-closure proof for comment drift."""
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
SKILL = REPO_ROOT / ".claude" / "skills" / "find-comment-drift"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-comment-drift-java-j2a"
JAVAC = shutil.which("javac")
pytestmark = pytest.mark.skipif(JAVAC is None, reason="JDK is required for fixture validation")


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    classes = tmp_path / "classes"
    sources = [str(path) for path in sorted(host.rglob("*.java"))]
    native = _run(
        JAVAC,
        "--release",
        "17",
        "-proc:none",
        "-d",
        str(classes),
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


def _detect(skill: Path, host: Path, output: Path, *targets: str) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--language",
        "java",
        "--output",
        str(output),
        *targets,
        cwd=host,
        env={**os.environ, "PATH": ""},
    )


def test_java_comments_reach_final_report_with_inventory_and_no_mutation(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "comment" / "detections.jsonl"

    detected = _detect(SKILL, host, output, ".")

    assert detected.returncode == 0, detected.stdout + detected.stderr
    records = _records(output)
    assert {record["file"] for record in records} == {"src/main/java/example/Checkout.java"}
    assert {record["pattern"] for record in records} == {
        "detached_section_banner",
        "malformed_doc_reference",
        "obvious_narration_comment",
        "stale_comment_term",
    }
    assert {record["language"] for record in records} == {"java"}

    report = output.with_name("report.md")
    rendered = _run(
        sys.executable,
        "-I",
        "-S",
        str(SKILL / "scripts" / "report.py"),
        str(output),
        "--output",
        str(report),
        "--target",
        ".",
        cwd=host,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    findings = json.loads(report.with_name("findings.json").read_text(encoding="utf-8"))
    java = findings["analysis"]["java"]
    assert findings["status"] == java["status"] == "complete"
    assert java["analyzer"] == "python-java-comment-lexer"
    inventory = {row["file"]: row for row in java["inventory"]}
    assert inventory["src/main/java/example/Checkout.java"]["role"] == "eligible"
    assert inventory["src/main/java/example/CleanCheckout.java"]["role"] == "eligible"
    assert inventory["src/test/java/example/CheckoutTest.java"]["reason"] == "test-tree"
    assert inventory["src/generated/java/example/GeneratedCheckout.java"]["reason"] == "generated-tree"
    assert inventory["src/main/java/example/WireGenerated.java"]["reason"] == "generated-marker"
    assert inventory["vendor/example/thirdparty/VendorCheckout.java"]["reason"] == "vendor"
    assert "**Status:** `complete`" in report.read_text(encoding="utf-8")
    assert _hashes(host) == before


def test_java_comment_lexer_ignores_literals_and_accepts_syntax_malformed_text(tmp_path: Path) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    output = host / "reports" / "detections.jsonl"

    result = _detect(SKILL, host, output, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    assert {(row["pattern"], row["lineno"]) for row in _records(output)} == {
        ("obvious_narration_comment", 7),
        ("stale_comment_term", 7),
    }
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "lexical-only; Java parse validity is not inspected"


def test_java_comment_statuses_symlink_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host = _host(tmp_path)
    (host / "linked.java").symlink_to(host / "src/main/java/example/Checkout.java")
    installed = tmp_path / "installed" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "copied" / "detections.jsonl"

    copied = _detect(installed, host, output, ".")

    assert copied.returncode == 0, copied.stdout + copied.stderr
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    inventory = {row["file"]: row for row in scan["inventory"]}
    assert inventory["linked.java"]["reason"] == "symlink"

    (host / "src/main/java/example/Unreadable.java").write_bytes(b"class Unreadable { // \xff\n}")
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _detect(installed, host, partial_output, ".")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert json.loads(partial_output.with_name("scan.json").read_text())["status"] == "partial"

    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").glob("*.py")
    )
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure


def test_java_comment_docs_are_lazy_and_name_native_boundary() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    java = (SKILL / "references" / "java.md").read_text(encoding="utf-8")

    assert len(text.splitlines()) < 500
    assert "references/java.md" in text
    assert "python-java-comment-lexer" in java
    assert "javac --release 17 -proc:none" in java
    assert "does not require a JDK" in java
    assert "Kotlin" in java
