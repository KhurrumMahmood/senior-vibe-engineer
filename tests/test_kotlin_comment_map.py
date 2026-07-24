"""Kotlin comment-token drift final outcomes over the copied lexical provider."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE_FIXTURE = ROOT / "tests/fixtures/kotlin-lexical-syntax"
OVERLAY = ROOT / "tests/fixtures/kotlin-comment-map/overlay"
BUILDER = BASE_FIXTURE / "kotlin_fixture_build.py"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
KOTLINC = Path("/opt/homebrew/bin/kotlinc").resolve()
JAVA = Path("/usr/bin/java").resolve()
COMMENT = ROOT / ".claude/skills/find-comment-drift/scripts/analyze_comments_kotlin.py"
LEXICAL = ROOT / ".claude/skills/_kotlin"


pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and KOTLINC.is_file() and JAVA.is_file()),
    reason="the pinned product Python, Kotlin/JVM 2.4.10, and JDK 17 are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=timeout,
    )


def _build(host: Path, cwd: Path) -> None:
    result = _run(
        str(PYTHON),
        "-I",
        "-S",
        str(BUILDER),
        "--project-root",
        str(host),
        "--kotlinc",
        str(KOTLINC),
        "--java",
        str(JAVA),
        cwd=cwd,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(BASE_FIXTURE / "host", host)
    shutil.copytree(OVERLAY, host, dirs_exist_ok=True)
    _build(host, tmp_path)
    return host


def _state(host: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts and relative.parts[0] in {"reports", ".native-build"}:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return rows


def _comment(
    host: Path,
    *,
    script: Path = COMMENT,
    output_name: str = "kotlin",
    target: str = "src/main/kotlin/cohort/comments",
    kotlinc: Path = KOTLINC,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = host / "reports/find-comment-drift" / output_name
    result = _run(
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        "--target",
        target,
        "--output-dir",
        str(output),
        "--kotlinc",
        str(kotlinc),
        "--java",
        str(JAVA),
        cwd=cwd or host,
    )
    return result, output


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_copied_kotlin_comment_outcome_is_useful_and_read_only(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _state(host)
    installed = tmp_path / "installed/.agents/skills"
    shutil.copytree(LEXICAL, installed / "_kotlin")
    copied = installed / "find-comment-drift/scripts" / COMMENT.name
    copied.parent.mkdir(parents=True)
    shutil.copy2(COMMENT, copied)
    outside = tmp_path / "outside"
    outside.mkdir()

    result, output = _comment(host, script=copied, cwd=outside)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(output / "findings.json")
    assert payload["status"] == "complete"
    assert payload["outcome"] == "advisory-findings"
    assert {(row["pattern"], row["file"]) for row in payload["findings"]} == {
        ("brittle_doc_reference", "src/main/kotlin/cohort/comments/CommentEvidence.kt"),
        ("detached_section_banner", "src/main/kotlin/cohort/comments/CommentEvidence.kt"),
        ("narration_comment", "src/main/kotlin/cohort/comments/CommentEvidence.kt"),
        ("stale_terminology", "src/main/kotlin/cohort/comments/CommentEvidence.kt"),
    }
    inventory = {row["file"]: row for row in payload["analysis"]["kotlin"]["inventory"]}
    assert inventory["generated/Generated.kt"]["role"] == "generated"
    assert inventory["vendor/Vendor.kt"]["role"] == "vendor"
    assert payload["claim_boundary"] == (
        "lexical Kotlin comment tokens only; no comment-to-declaration association or semantic drift claim"
    )
    assert (output / "detections.jsonl").is_file()
    assert (output / "scan.json").is_file()
    assert (output / "report.md").is_file()
    assert _state(host) == before
    assert str(ROOT) not in copied.read_text(encoding="utf-8")


def test_kotlin_comment_clean_target_retains_role_and_string_decoys(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _state(host)

    result, output = _comment(
        host,
        output_name="clean",
        target="src/main/kotlin/cohort/BillingValidator.kt",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(output / "findings.json")
    assert payload["status"] == "complete"
    assert payload["outcome"] == "clean-within-complete"
    assert payload["findings"] == []
    assert (output / "detections.jsonl").read_text(encoding="utf-8") == ""
    assert _state(host) == before


def test_kotlin_comment_replaces_terminal_artifacts_and_recovers(tmp_path: Path) -> None:
    host = _host(tmp_path)
    source = host / "src/main/kotlin/cohort/comments/CommentEvidence.kt"
    pristine = source.read_text(encoding="utf-8")
    result, output = _comment(host, output_name="lifecycle")
    assert result.returncode == 0
    assert _payload(output / "findings.json")["findings"]

    source.write_text(pristine + "\n", encoding="utf-8")
    stale, _ = _comment(host, output_name="lifecycle")
    stale_payload = _payload(output / "findings.json")
    assert stale.returncode == 2
    assert stale_payload["status"] == "failed"
    assert stale_payload["findings"] == []
    assert stale_payload["failure_kind"] == "kotlin_build_evidence_stale_or_incomplete_inputs"

    source.write_text("package cohort.comments\nfun broken( {\n", encoding="utf-8")
    malformed, _ = _comment(host, output_name="lifecycle")
    malformed_payload = _payload(output / "findings.json")
    assert malformed.returncode == 2
    assert malformed_payload["failure_kind"] == "kotlinc_diagnostic_failed"
    assert malformed_payload["outcome"] == "incomplete"

    missing, _ = _comment(
        host,
        output_name="lifecycle",
        kotlinc=host / "missing-kotlinc",
    )
    missing_payload = _payload(output / "findings.json")
    assert missing.returncode == 0
    assert missing_payload["status"] == "unsupported"
    assert missing_payload["outcome"] == "incomplete"
    assert missing_payload["findings"] == []

    source.write_text(pristine, encoding="utf-8")
    _build(host, tmp_path)
    recovered, _ = _comment(host, output_name="lifecycle")
    assert recovered.returncode == 0
    assert _payload(output / "findings.json")["outcome"] == "advisory-findings"
