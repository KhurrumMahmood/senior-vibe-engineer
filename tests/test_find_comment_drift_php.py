"""PHP lexical-comment outcomes, lifecycle, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "find-comment-drift"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "php-pilot"
PHP_PATH = shutil.which("php")
PHP = Path(PHP_PATH) if PHP_PATH else Path("php-unavailable")
pytestmark = pytest.mark.skipif(PHP_PATH is None, reason="PHP pilot binary is required")


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    for script in ("tests/lint.php", "tests/smoke.php"):
        native = _run(str(PHP), script, cwd=host)
        assert native.returncode == 0, native.stdout + native.stderr
    return host


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.relative_to(root).parts
    }


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _detect(
    skill: Path,
    host: Path,
    output: Path,
    *targets: str,
    php_bin: Path = PHP,
) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "detect.py"),
        "--project-root",
        str(host),
        "--language",
        "php",
        "--php-bin",
        str(php_bin),
        "--output",
        str(output),
        *targets,
        cwd=host,
    )


def _render(skill: Path, host: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(skill / "scripts" / "report.py"),
        str(output),
        "--output",
        str(output.with_name("report.md")),
        "--output-json",
        str(output.with_name("report.json")),
        "--target",
        ".",
        cwd=host,
    )


def test_php_pilot_reaches_final_report_with_inventory_and_no_mutation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    (host / "linked.php").symlink_to(host / "src/Billing/InvoiceService.php")
    before = _hashes(host)
    installed = tmp_path / "installed" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "find-comment-drift" / "php-pilot" / "detections.jsonl"

    detected = _detect(installed, host, output, ".")

    assert detected.returncode == 0, detected.stdout + detected.stderr
    records = _records(output)
    assert len(records) == 1
    assert records[0]["file"] == "src/Billing/InvoiceService.php"
    assert records[0]["lineno"] == 15
    assert records[0]["pattern"] == "obvious_narration_comment"
    assert records[0]["language"] == "php"

    rendered = _render(installed, host, output)
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    report_path = output.with_name("report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    php = report["analysis"]["php"]
    assert report["status"] == php["status"] == "complete"
    assert report["outcome"] == php["outcome"] == "advisory-findings"
    assert php["analyzer"] == "php-token-get-all"
    assert php["minimum_php_version"] == "8.1.0"
    inventory = {row["file"]: row for row in php["inventory"]}
    for source in (
        "src/Billing/InvoiceService.php",
        "src/Shared/Clock.php",
        "src/Shared/FixedClock.php",
        "src/Shipping/ShipmentService.php",
    ):
        assert inventory[source]["role"] == "eligible"
    assert inventory["tests/Billing/InvoiceServiceTest.php"]["reason"] == "test-tree"
    assert inventory["tests/lint.php"]["reason"] == "test-tree"
    assert inventory["generated/GeneratedProxy.php"]["reason"] == "generated-tree"
    assert inventory["vendor/example/package/VendorService.php"]["reason"] == "vendor"
    assert inventory["build/CompiledContainer.php"]["reason"] == "build-tree"
    assert inventory["linked.php"]["reason"] == "symlink"
    assert report_path.is_file()
    assert _hashes(host) == before


def test_php_clean_within_complete_and_malformed_partial_are_distinct(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _hashes(host)
    clean_output = host / "reports" / "find-comment-drift" / "clean" / "detections.jsonl"

    clean = _detect(SKILL, host, clean_output, "src/Shared")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert _records(clean_output) == []
    clean_render = _render(SKILL, host, clean_output)
    assert clean_render.returncode == 0, clean_render.stdout + clean_render.stderr
    clean_report = json.loads(clean_output.with_name("report.json").read_text())
    assert clean_report["status"] == "complete"
    assert clean_report["outcome"] == "clean-within-complete"

    broken = host / "src" / "Broken.php"
    shutil.copyfile(FIXTURE / "malformed" / "Broken.php", broken)
    malformed_before = _hashes(host)
    partial_output = host / "reports" / "find-comment-drift" / "partial" / "detections.jsonl"
    partial = _detect(SKILL, host, partial_output, "src")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    partial_render = _render(SKILL, host, partial_output)
    assert partial_render.returncode == 0, partial_render.stdout + partial_render.stderr
    partial_report = json.loads(partial_output.with_name("report.json").read_text())
    php = partial_report["analysis"]["php"]
    assert partial_report["status"] == php["status"] == "partial"
    assert partial_report["outcome"] == php["outcome"] == "incomplete"
    broken_row = next(row for row in php["inventory"] if row["file"] == "src/Broken.php")
    assert broken_row["role"] == "failed"
    assert broken_row["reason"] == "syntax-error"
    assert php["summary"]["failed"] == 1
    assert "src/Broken.php" in "\n".join(php["errors"])
    assert _hashes(host) == malformed_before
    broken.unlink()
    assert _hashes(host) == before


def _fake_php(path: Path, version: str, provider_exit: int = 0) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        f"  printf '%s\\n' 'PHP {version} (cli)'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {provider_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_php_tool_boundaries_and_same_destination_lifecycle(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _hashes(host)

    excluded_output = host / "reports" / "find-comment-drift" / "excluded" / "detections.jsonl"
    excluded = _detect(SKILL, host, excluded_output, "vendor")
    assert excluded.returncode == 2
    excluded_scan = json.loads(excluded_output.with_name("scan.json").read_text())
    assert excluded_scan["failure_kind"] == "no-eligible-php-files"

    missing_output = host / "reports" / "find-comment-drift" / "missing" / "detections.jsonl"
    missing = _detect(SKILL, host, missing_output, "src", php_bin=tmp_path / "missing-php")
    assert missing.returncode == 2
    missing_scan = json.loads(missing_output.with_name("scan.json").read_text())
    assert missing_scan["status"] == "unsupported"
    assert missing_scan["failure_kind"] == "php-tool-missing"
    assert _render(SKILL, host, missing_output).returncode == 0
    assert json.loads(missing_output.with_name("report.json").read_text())["status"] == "unsupported"

    old_php = tmp_path / "old-php"
    _fake_php(old_php, "8.0.30")
    old_output = host / "reports" / "find-comment-drift" / "old" / "detections.jsonl"
    old = _detect(SKILL, host, old_output, "src", php_bin=old_php)
    assert old.returncode == 2
    old_scan = json.loads(old_output.with_name("scan.json").read_text())
    assert old_scan["status"] == "unsupported"
    assert old_scan["failure_kind"] == "php-version-too-old"

    output = host / "reports" / "find-comment-drift" / "lifecycle" / "detections.jsonl"
    valid = _detect(SKILL, host, output, "src")
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _render(SKILL, host, output).returncode == 0
    assert json.loads(output.with_name("report.json").read_text())["status"] == "complete"

    failing_php = tmp_path / "failing-php"
    _fake_php(failing_php, "8.4.2", provider_exit=9)
    failed = _detect(SKILL, host, output, "src", php_bin=failing_php)
    assert failed.returncode == 1
    assert not output.with_name("report.json").exists()
    assert _records(output) == []
    failed_scan = json.loads(output.with_name("scan.json").read_text())
    assert failed_scan["status"] == "failed"
    assert failed_scan["failure_kind"] == "php-provider-failed"
    assert _render(SKILL, host, output).returncode == 0
    assert json.loads(output.with_name("report.json").read_text())["status"] == "failed"

    recovered = _detect(SKILL, host, output, "src")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert not output.with_name("report.json").exists()
    assert _render(SKILL, host, output).returncode == 0
    recovered_report = json.loads(output.with_name("report.json").read_text())
    assert recovered_report["status"] == "complete"
    assert recovered_report["outcome"] == "advisory-findings"
    assert _hashes(host) == before


def test_php_docs_and_copied_closure_name_the_bounded_contract() -> None:
    skill = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8")
    helper = SKILL.joinpath("scripts", "php_comments.php").read_text(encoding="utf-8")
    closure = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SKILL.joinpath("scripts").iterdir()
        if path.is_file()
    )

    assert "PHP >= 8.1.0" in skill
    assert "token_get_all" in skill
    assert "php -l" in skill
    assert "--output-json" in skill
    assert "TOKEN_PARSE" in helper
    assert "scripts/_lib" not in closure
    assert str(REPO_ROOT) not in closure
