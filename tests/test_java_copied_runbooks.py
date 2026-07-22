"""Copied Java runbooks must resolve their own selected skill closure."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
STOCK_LAYOUTS = (
    ".agents/skills/on-demand",
    ".agents/skills",
    ".claude/skills",
)
JAVA_RUNBOOKS = (
    (
        "find-comment-drift",
        "references/java.md",
        "java-comment-scan",
        ROOT / "tests" / "fixtures" / "find-comment-drift-java-j2a" / "valid",
        "reports/find-comment-drift/scan-java/findings.json",
    ),
    (
        "find-concept-divergence",
        "references/java.md",
        "java-concept-scan",
        ROOT / "tests" / "fixtures" / "find-concept-divergence-java-j2a" / "valid",
        "reports/find-concept-divergence/scan-java/report.md",
    ),
    (
        "find-folder-topology-drift",
        "references/java.md",
        "java-folder-topology-scan",
        ROOT / "tests" / "fixtures" / "find-folder-topology-java-j2a" / "valid",
        "reports/find-folder-topology-drift/scan-java/findings.json",
    ),
)
JAVA_MULTI_COMMAND_RUNBOOKS = (
    (
        "find-comment-drift",
        "references/java.md",
        "java-comment-scan",
        ".",
        "reports/find-comment-drift/scan-java",
    ),
    (
        "find-folder-topology-drift",
        "references/java.md",
        "java-folder-topology-scan",
        "src/main/java",
        "reports/find-folder-topology-drift/scan-java",
    ),
)


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_skill(host: Path, layout: str, name: str) -> Path:
    installed = host / layout / name
    installed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILLS / name, installed)
    return installed


def _documented_block(document: Path, name: str) -> str:
    text = document.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- installed-command:{re.escape(name)}:start -->\n```bash\n(.*?)\n```\n"
        rf"<!-- installed-command:{re.escape(name)}:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None, f"missing documented {name} command in {document}"
    return match.group(1)


@pytest.mark.parametrize("layout", STOCK_LAYOUTS)
@pytest.mark.parametrize(
    ("skill_name", "document_relative", "command_name", "fixture", "artifact_relative"),
    JAVA_RUNBOOKS,
)
def test_java_audit_runbooks_execute_from_each_stock_copied_layout(
    tmp_path: Path,
    layout: str,
    skill_name: str,
    document_relative: str,
    command_name: str,
    fixture: Path,
    artifact_relative: str,
) -> None:
    host = tmp_path / skill_name
    shutil.copytree(fixture, host)
    installed = _copy_skill(host, layout, skill_name)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_block(installed / document_relative, command_name),
        cwd=host,
        env=os.environ.copy(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    artifact = host / artifact_relative
    assert artifact.is_file()
    if artifact.suffix == ".json":
        assert json.loads(artifact.read_text(encoding="utf-8"))["status"] == "complete"


@pytest.mark.parametrize(
    ("skill_name", "document_relative", "command_name", "java_root", "scan_relative"),
    JAVA_MULTI_COMMAND_RUNBOOKS,
)
def test_java_multi_command_runbooks_preserve_unsupported_detector_exit(
    tmp_path: Path,
    skill_name: str,
    document_relative: str,
    command_name: str,
    java_root: str,
    scan_relative: str,
) -> None:
    host = tmp_path / skill_name
    (host / java_root).mkdir(parents=True)
    installed = _copy_skill(host, ".claude/skills", skill_name)

    result = _run(
        "/bin/bash",
        "-c",
        _documented_block(installed / document_relative, command_name),
        cwd=host,
        env=os.environ.copy(),
    )

    scan = host / scan_relative
    assert result.returncode == 2, result.stdout + result.stderr
    assert json.loads((scan / "scan.json").read_text(encoding="utf-8"))["status"] == "unsupported"
    assert not (scan / "report.md").exists()
    assert not (scan / "findings.json").exists()


def _require_jdk17() -> None:
    javac = shutil.which("javac")
    if javac is None:
        pytest.skip("JDK 17 is required for Java state runbook verification")
    version = _run(javac, "-version", cwd=ROOT)
    if version.returncode or not (version.stdout + version.stderr).startswith("javac 17"):
        pytest.skip("JDK 17 is required for Java state runbook verification")


@pytest.mark.parametrize("layout", STOCK_LAYOUTS)
def test_java_state_runbooks_execute_from_each_stock_copied_layout(
    tmp_path: Path,
    layout: str,
) -> None:
    _require_jdk17()
    host = tmp_path / "host"
    shutil.copytree(ROOT / "tests" / "fixtures" / "find-implicit-state-java", host)
    detector = _copy_skill(host, layout, "find-implicit-state")
    extractor = _copy_skill(host, layout, "extract-enum")
    guard = _copy_skill(host, layout, "prevent-regression")
    extract_command = _documented_block(extractor / "SKILL.md", "java-state-proposal")
    guard_command = _documented_block(guard / "SKILL.md", "java-state-guard")
    scan = host / "reports" / "implicit-state" / "java-state"

    detected = _run(
        sys.executable,
        "-I",
        "-S",
        str(detector / "scripts" / "detect_java_state.py"),
        "--target",
        str(host / "src"),
        "--project-root",
        str(host),
        "--output",
        str(scan / "hits.jsonl"),
        "--findings",
        str(scan / "findings.json"),
        "--report",
        str(scan / "report.md"),
        "--scan-id",
        "java-state",
        cwd=host,
        env=os.environ.copy(),
    )
    assert detected.returncode == 0, detected.stdout + detected.stderr

    extracted = _run(
        "/bin/bash",
        "-c",
        extract_command,
        cwd=host,
        env={**os.environ, "JAVA_SCAN": "java-state"},
    )
    assert extracted.returncode == 0, extracted.stdout + extracted.stderr
    targets = host / "reports" / "extract-enum" / "java-job-status" / "targets.json"
    assert json.loads(targets.read_text(encoding="utf-8"))["status"] == "review_required"

    staged = _run(
        "/bin/bash",
        "-c",
        guard_command,
        cwd=host,
        env=os.environ.copy(),
    )
    assert staged.returncode == 0, staged.stdout + staged.stderr
    assert "PASS: BAD_RC=1, GOOD_RC=0, native Java fixtures compile" in staged.stdout
