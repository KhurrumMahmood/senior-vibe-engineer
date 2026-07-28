"""Go outcome, inventory, boundary, and copied-closure proof for folder topology."""
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
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "find-folder-topology-drift-go"
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


def _detect(
    skill: Path,
    host: Path,
    output: Path,
    env: dict[str, str],
    root: str,
) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--go-root",
        root,
        "--output",
        str(output),
        cwd=host,
        env=env,
    )


def test_go_cluster_reaches_final_report_with_complete_inventory_and_no_mutation(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    before = _hashes(host)
    output = host / "reports" / "topology" / "detections.jsonl"

    detected = _detect(SKILL, host, output, env, ".")
    assert detected.returncode == 0, detected.stdout + detected.stderr
    records = _records(output)
    assert len(records) == 1
    assert records[0]["language"] == "go"
    assert records[0]["pattern"] == "flat_prefix_cluster"
    assert records[0]["prefix"] == "billing"
    assert records[0]["files"] == [
        "internal/billing/billing_parser.go",
        "internal/billing/billing_types.go",
        "internal/billing/billing_validator.go",
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
        "go",
        cwd=host,
        env=env,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    go = findings["analysis"]["go"]
    assert findings["status"] == go["status"] == "complete"
    assert go["analyzer"] == "python-filesystem-names"
    inventory = {row["file"]: row for row in go["inventory"]}
    assert inventory["internal/billing/billing_parser.go"]["role"] == "eligible"
    assert inventory["internal/billing/billing_parser_test.go"]["reason"] == "test-file"
    assert inventory["internal/billing/billing_generated.go"]["reason"] == "generated-file"
    assert inventory["internal/generated/billing_extra.go"]["reason"] == "generated-tree"
    assert inventory["internal/tests/billing_alpha.go"]["reason"] == "test-tree"
    assert inventory["vendor/example.com/thirdparty/billing_alpha.go"]["reason"] == "vendor"
    assert "**Status:** `complete`" in report.read_text(encoding="utf-8")
    assert _hashes(host) == before


def test_go_folder_scan_is_filename_only_across_malformed_source(tmp_path: Path) -> None:
    host = tmp_path / "malformed"
    shutil.copytree(FIXTURE / "malformed", host)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    output = host / "reports" / "detections.jsonl"

    result = _detect(SKILL, host, output, env, ".")

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(output)
    assert len(records) == 1
    assert records[0]["prefix"] == "billing"
    scan = json.loads(output.with_name("scan.json").read_text())
    assert scan["status"] == "complete"
    assert scan["syntax_contract"] == "filename-only; Go parse validity is not inspected"


def test_go_folder_statuses_and_copied_skill_are_honest(tmp_path: Path) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "valid", host)
    installed = tmp_path / "installed" / "find-folder-topology-drift"
    shutil.copytree(SKILL, installed)
    env = {**os.environ, "GOCACHE": str(tmp_path / "go-cache")}
    output = host / "reports" / "copied" / "detections.jsonl"
    copied = _detect(installed, host, output, env, ".")
    assert copied.returncode == 0, copied.stdout + copied.stderr
    assert json.loads(output.with_name("scan.json").read_text())["status"] == "complete"

    (host / "internal" / "billing" / "billing_unreadable.go").write_bytes(
        b"package billing\n// \xff\n"
    )
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _detect(installed, host, partial_output, env, ".")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert json.loads(partial_output.with_name("scan.json").read_text())["status"] == "partial"
    partial_report = _run(
        sys.executable,
        "-I",
        "-S",
        str(installed / "scripts" / "report.py"),
        "--detections",
        str(partial_output),
        "--output-md",
        str(partial_output.with_name("report.md")),
        "--output-json",
        str(partial_output.with_name("findings.json")),
        "--target",
        ".",
        "--language",
        "go",
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
        "--detections",
        str(unsupported_output),
        "--output-md",
        str(unsupported_output.with_name("report.md")),
        "--output-json",
        str(unsupported_output.with_name("findings.json")),
        "--target",
        ".",
        "--language",
        "go",
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
    fake_go.write_text("#!/bin/sh\nexit 5\n", encoding="utf-8")
    fake_go.chmod(0o755)
    failed_output = host / "reports" / "failed" / "detections.jsonl"
    failed = _detect(installed, host, failed_output, {**env, "PATH": str(fake_bin)}, ".")
    assert failed.returncode == 1
    assert json.loads(failed_output.with_name("scan.json").read_text())["status"] == "failed"

    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (installed / "scripts").glob("*.py")
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
        "--typescript-root",
        "internal",
        "--output",
        str(output),
        cwd=host,
        env=env,
    )
    assert auto.returncode == 0, auto.stdout + auto.stderr
    assert not output.with_name("scan.json").exists()


def test_go_folder_docs_name_the_bounded_contract() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    scans = set(text.split("scans: [", 1)[1].split("]", 1)[0].split(", "))

    assert {"python", "javascript", "typescript", "go"} <= scans
    assert "Go >= 1.22.0" in text
    assert "python-filesystem-names" in text
    assert "_test.go" in text
