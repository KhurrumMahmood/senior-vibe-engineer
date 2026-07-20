"""Go outcome, inventory, and copied-closure proof for concept divergence."""
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
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-concept-divergence-go"
GO = shutil.which("go")
pytestmark = pytest.mark.skipif(GO is None, reason="Go toolchain is required")


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(root).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _scan(
    skill: Path,
    host: Path,
    output: Path,
    env: dict[str, str],
    *targets: str,
) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "scan.py"),
        "--project-root",
        str(host),
        "--language",
        "go",
        "--output",
        str(output),
        "--report",
        str(output.with_name("report.md")),
        *targets,
        cwd=host,
        env=env,
    )


def test_go_concepts_reach_final_report_with_complete_inventory_and_no_mutation(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    before = _hashes(host)
    output = host / "reports" / "concept" / "findings.jsonl"

    result = _scan(SKILL, host, output, env, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(output)
    assert len(records) == 4
    assert {record["file"] for record in records} == {"src/checkout.go"}
    assert {record["band"] for record in records} == {
        "avoid_term_hit",
        "competing_term_coexistence",
        "superseded_co_occurrence",
    }
    assert {record["language"] for record in records} == {"go"}
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["analyzer"] == "python-strict-text"
    assert scan["minimum_go_version"] == "1.22.0"
    inventory = {row["file"]: row for row in scan["inventory"]}
    assert inventory["src/checkout.go"]["role"] == "eligible"
    assert inventory["src/clean.go"]["role"] == "eligible"
    assert inventory["src/checkout_test.go"]["reason"] == "test-file"
    assert inventory["src/generated/ignored.go"]["reason"] == "generated-tree"
    assert inventory["src/wire_generated.go"]["reason"] == "generated-file"
    assert inventory["vendor/example.com/thirdparty/ignored.go"]["reason"] == "vendor"
    report = output.with_name("report.md").read_text(encoding="utf-8")
    assert "**Status:** `complete`" in report
    assert "**Language:** `go`" in report
    assert _hashes(host) == before


def test_go_concept_scan_is_textual_across_malformed_go(tmp_path: Path) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    output = host / "reports" / "findings.jsonl"

    result = _scan(SKILL, host, output, env, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    assert [(row["file"], row["term"]) for row in _records(output)] == [
        ("broken.go", "legacy checkout")
    ]
    scan = json.loads(output.with_name("scan.json").read_text())
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "strict-text; Go parse validity is not inspected"


def test_go_concept_statuses_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    installed = tmp_path / "installed" / "find-concept-divergence"
    shutil.copytree(SKILL, installed)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    output = host / "reports" / "copied" / "findings.jsonl"
    copied = _scan(installed, host, output, env, ".")
    assert copied.returncode == 0, copied.stdout + copied.stderr
    assert json.loads(output.with_name("scan.json").read_text())["status"] == "complete"

    (host / "src" / "unreadable.go").write_bytes(b"package checkout\n// \xff\n")
    partial_output = host / "reports" / "partial" / "findings.jsonl"
    partial = _scan(installed, host, partial_output, env, ".")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert json.loads(partial_output.with_name("scan.json").read_text())["status"] == "partial"

    unsupported_output = host / "reports" / "unsupported" / "findings.jsonl"
    unsupported = _scan(installed, host, unsupported_output, {**env, "PATH": ""}, ".")
    assert unsupported.returncode == 2
    unsupported_scan = json.loads(unsupported_output.with_name("scan.json").read_text())
    assert unsupported_scan["status"] == "unsupported"
    assert unsupported_scan["failure_kind"] == "go-tool-missing"
    unsupported_report = unsupported_output.with_name("report.md").read_text()
    assert "**Status:** `unsupported`" in unsupported_report
    assert "no absence-of-drift conclusion is available" in unsupported_report
    assert "No drift detected" not in unsupported_report

    old_bin = tmp_path / "old-bin"
    old_bin.mkdir()
    old_go = old_bin / "go"
    old_go.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'go version go1.21.9 darwin/arm64'\n",
        encoding="utf-8",
    )
    old_go.chmod(0o755)
    old_output = host / "reports" / "old" / "findings.jsonl"
    old = _scan(installed, host, old_output, {**env, "PATH": str(old_bin)}, ".")
    assert old.returncode == 2
    assert json.loads(old_output.with_name("scan.json").read_text())["failure_kind"] == "go-version-too-old"

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    fake_go.chmod(0o755)
    failed_output = host / "reports" / "failed" / "findings.jsonl"
    failed = _scan(installed, host, failed_output, {**env, "PATH": str(fake_bin)}, ".")
    assert failed.returncode == 1
    assert json.loads(failed_output.with_name("scan.json").read_text())["status"] == "failed"
    failed_report = failed_output.with_name("report.md").read_text()
    assert "no absence-of-drift conclusion is available" in failed_report
    assert "No drift detected" not in failed_report

    closure = (installed / "scripts" / "scan.py").read_text(encoding="utf-8")
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure

    auto = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "scan.py"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--report",
        str(output.with_name("report.md")),
        "src",
        cwd=host,
        env=env,
    )
    assert auto.returncode == 0, auto.stdout + auto.stderr
    assert not output.with_name("scan.json").exists()


def test_go_concept_docs_name_the_bounded_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "scans: [python, javascript, typescript, go, markdown, templates]" in text
    assert "Go >= 1.22.0" in text
    assert "python-strict-text" in text
    assert "_test.go" in text
