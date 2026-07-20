"""Go outcome, inventory, boundary, and copied-closure proof for comment drift."""
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
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-comment-drift-go"
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


def _copy_host(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    return host, env


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(root).parts
    }


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _detect(
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
        str(skill / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--language",
        "go",
        "--output",
        str(output),
        *targets,
        cwd=host,
        env=env,
    )


def test_go_comments_reach_final_report_with_complete_inventory_and_no_mutation(
    tmp_path: Path,
) -> None:
    host, env = _copy_host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "comment" / "detections.jsonl"

    detected = _detect(SKILL, host, output, env, ".")
    assert detected.returncode == 0, detected.stdout + detected.stderr
    records = _records(output)
    assert {record["file"] for record in records} == {"src/checkout.go"}
    assert {record["pattern"] for record in records} == {
        "detached_section_banner",
        "malformed_doc_reference",
        "obvious_narration_comment",
        "stale_comment_term",
    }
    assert {record["language"] for record in records} == {"go"}

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
        env=env,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    findings = json.loads(report.with_name("findings.json").read_text(encoding="utf-8"))
    go = findings["analysis"]["go"]
    assert findings["status"] == go["status"] == "complete"
    assert go["analyzer"] == "python-go-comment-lexer"
    assert go["minimum_go_version"] == "1.22.0"
    inventory = {row["file"]: row for row in go["inventory"]}
    assert inventory["src/checkout.go"]["role"] == "eligible"
    assert inventory["src/clean.go"]["role"] == "eligible"
    assert inventory["src/checkout_test.go"]["reason"] == "test-file"
    assert inventory["src/generated/ignored.go"]["reason"] == "generated-tree"
    assert inventory["src/wire_generated.go"]["reason"] == "generated-file"
    assert inventory["vendor/example.com/thirdparty/ignored.go"]["reason"] == "vendor"
    assert go["summary"] == {
        "discovered": 6,
        "eligible": 2,
        "excluded": 4,
        "failed": 0,
    }
    assert "**Status:** `complete`" in report.read_text(encoding="utf-8")
    assert _hashes(host) == before


def test_go_comment_lexer_ignores_strings_and_keeps_syntax_malformed_text_lexical(
    tmp_path: Path,
) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    output = host / "reports" / "detections.jsonl"

    result = _detect(SKILL, host, output, env, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(output)
    assert {record["pattern"] for record in records} == {
        "obvious_narration_comment",
        "stale_comment_term",
    }
    assert {record["lineno"] for record in records} == {6}
    scan = json.loads(output.with_name("scan.json").read_text(encoding="utf-8"))
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "lexical-only; Go parse validity is not inspected"


def test_go_comment_statuses_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host, env = _copy_host(tmp_path)
    installed = tmp_path / "installed" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "copied" / "detections.jsonl"
    copied = _detect(installed, host, output, env, ".")
    assert copied.returncode == 0, copied.stdout + copied.stderr
    assert json.loads(output.with_name("scan.json").read_text())["status"] == "complete"

    unreadable = host / "src" / "unreadable.go"
    unreadable.write_bytes(b"package checkout\n// \xff\n")
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _detect(installed, host, partial_output, env, ".")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_scan = json.loads(partial_output.with_name("scan.json").read_text())
    assert partial_scan["status"] == "partial"
    assert partial_scan["summary"]["failed"] == 1
    partial_report = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        str(partial_output),
        "--output",
        str(partial_output.with_name("report.md")),
        cwd=host,
        env=env,
    )
    assert partial_report.returncode == 0, partial_report.stdout + partial_report.stderr
    assert json.loads(partial_output.with_name("findings.json").read_text())["status"] == "partial"

    unsupported_output = host / "reports" / "unsupported" / "detections.jsonl"
    unsupported = _detect(installed, host, unsupported_output, {**env, "PATH": ""}, ".")
    assert unsupported.returncode == 2
    unsupported_scan = json.loads(unsupported_output.with_name("scan.json").read_text())
    assert unsupported_scan["status"] == "unsupported"
    assert unsupported_scan["failure_kind"] == "go-tool-missing"
    unsupported_report = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        str(unsupported_output),
        "--output",
        str(unsupported_output.with_name("report.md")),
        cwd=host,
        env=env,
    )
    assert unsupported_report.returncode == 0
    assert json.loads(unsupported_output.with_name("findings.json").read_text())["status"] == "unsupported"

    old_bin = tmp_path / "old-bin"
    old_bin.mkdir()
    old_go = old_bin / "go"
    old_go.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'go version go1.21.9 darwin/arm64'\n",
        encoding="utf-8",
    )
    old_go.chmod(0o755)
    old_output = host / "reports" / "old" / "detections.jsonl"
    old = _detect(installed, host, old_output, {**env, "PATH": str(old_bin)}, ".")
    assert old.returncode == 2
    assert json.loads(old_output.with_name("scan.json").read_text())["failure_kind"] == "go-version-too-old"

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_go = fake_bin / "go"
    fake_go.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
    fake_go.chmod(0o755)
    failed_output = host / "reports" / "failed" / "detections.jsonl"
    failed = _detect(installed, host, failed_output, {**env, "PATH": str(fake_bin)}, ".")
    assert failed.returncode == 1
    failed_scan = json.loads(failed_output.with_name("scan.json").read_text())
    assert failed_scan["status"] == "failed"
    assert failed_scan["failure_kind"] == "go-version-failed"

    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").iterdir()
        if path.is_file() and path.suffix == ".py"
    )
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure

    auto = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--output",
        str(output),
        "src",
        cwd=host,
        env=env,
    )
    assert auto.returncode == 0, auto.stdout + auto.stderr
    assert not output.with_name("scan.json").exists()


def test_go_comment_docs_name_the_bounded_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "scans: [python, javascript, typescript, go, templates]" in text
    assert "Go >= 1.22.0" in text
    assert "python-go-comment-lexer" in text
    assert "_test.go" in text
