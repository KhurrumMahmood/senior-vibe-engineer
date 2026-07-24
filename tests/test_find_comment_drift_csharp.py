"""C# Roslyn comment-drift outcomes, lifecycle, and copied-closure proof."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/find-comment-drift"
HELPER = SKILL / "scripts/analyze_comments_csharp.py"
PROVIDER = ROOT / ".claude/skills/_csharp"
FIXTURE = ROOT / "tests/fixtures/find-comment-drift-csharp"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
DOTNET = Path(shutil.which("dotnet") or "/nonexistent/dotnet").resolve()


pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and DOTNET.is_file()),
    reason="the pinned product Python and .NET SDK 10.0.302 are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False,
        shell=False, timeout=timeout,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
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
                "file", hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return rows


def _analyze(
    host: Path, *, helper: Path = HELPER, run: str = "csharp",
    target: str = "src", dotnet: Path = DOTNET, cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = host / "reports/find-comment-drift" / run
    result = _run(
        str(PYTHON), "-I", "-S", str(helper),
        "--project-root", str(host), "--target", target,
        "--output-dir", str(output), "--dotnet", str(dotnet),
        cwd=cwd or host,
    )
    return result, output


def _payload(output: Path) -> dict:
    return json.loads((output / "findings.json").read_text(encoding="utf-8"))


def _records(output: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (output / "detections.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def test_csharp_comment_findings_use_exact_roslyn_trivia_and_copied_closure(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    (host / "linked-external").symlink_to(
        FIXTURE / "symlink-target", target_is_directory=True
    )
    installed = host / ".agents/skills"
    shutil.copytree(PROVIDER, installed / "_csharp")
    shutil.copytree(SKILL, installed / "find-comment-drift")
    helper = installed / "find-comment-drift/scripts/analyze_comments_csharp.py"
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _state(host)

    result, output = _analyze(host, helper=helper, cwd=outside)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(output)
    assert payload["status"] == "complete"
    assert payload["outcome"] == "advisory-findings"
    assert payload["finding_count"] == 4
    assert payload["claim_boundary"] == (
        "lexical C# Roslyn comment trivia only; no comment-to-declaration "
        "association, semantic drift, control-flow, or runtime claim"
    )
    assert set(payload["pattern_contracts"]) == {
        "stale_terminology", "brittle_doc_reference",
        "detached_section_banner", "narration_comment",
    }
    records = _records(output)
    assert {(row["pattern"], row["lineno"]) for row in records} == {
        ("stale_terminology", 7),
        ("brittle_doc_reference", 7),
        ("detached_section_banner", 8),
        ("narration_comment", 9),
    }
    assert {row["file"] for row in records} == {
        "src/CSharpComment/CommentEvidence.cs"
    }
    forms = {row["pattern"]: row["evidence"]["comment_form"] for row in records}
    assert forms == {
        "brittle_doc_reference": "line",
        "stale_terminology": "line",
        "detached_section_banner": "block",
        "narration_comment": "documentation-line",
    }

    source_path = host / "src/CSharpComment/CommentEvidence.cs"
    source = source_path.read_text(encoding="utf-8")
    spellings = {
        "stale_terminology": "// SiteConfig still lives at BillingParser.cs:42.",
        "brittle_doc_reference": "// SiteConfig still lives at BillingParser.cs:42.",
        "detached_section_banner": "/* SECTION 12 BILLING PARSERS */",
        # Roslyn structured documentation trivia excludes the exterior `///`
        # from SyntaxTrivia.Span while retaining it in ToFullString().
        "narration_comment": " Parse the invoice state.\n",
    }
    for row in records:
        spelling = spellings[row["pattern"]]
        start_index = source.index(spelling)
        span = row["evidence"]["roslyn_comment_span"]
        assert span == {
            "start": _utf16_units(source[:start_index]),
            "end": _utf16_units(source[: start_index + len(spelling)]),
            "unit": "utf16-code-unit",
            "interval": "half-open",
        }
        assert row["evidence"]["comment_spelling_sha256"] == hashlib.sha256(
            spelling.encode()
        ).hexdigest()
    line_span = next(
        row["evidence"]["roslyn_comment_span"]
        for row in records if row["pattern"] == "stale_terminology"
    )
    line_start = source.index(spellings["stale_terminology"])
    assert line_span["start"] != len(source[:line_start].encode("utf-8"))

    facts = payload["analysis"]["csharp"]
    assert facts["native_evidence"]["state"] == "valid-current-and-replayed"
    assert facts["native_evidence"]["test_stdout"] == "csharp-comment-tests:ok\n"
    assert facts["native_evidence"]["smoke_stdout"] == "csharp-comment:queued:1\n"
    inventory = {row["file"]: row for row in facts["inventory"]}
    assert inventory["src/CSharpComment/CommentEvidence.cs"]["role"] == "source"
    assert inventory["tests/CSharpCommentTests.cs"]["role"] == "test"
    assert inventory["generated/Generated.cs"]["role"] == "generated"
    assert inventory["vendor/Vendor.cs"]["role"] == "vendor"
    assert inventory["build/Build.cs"]["role"] == "build"
    assert inventory["tools/Tooling.cs"]["role"] == "tooling"
    assert "linked-external/External.cs" not in inventory
    assert facts["source_manifest"]["preserved"] is True
    assert (output / "scan.json").is_file()
    assert (output / "report.md").is_file()
    assert "runtime claim" in (output / "report.md").read_text(encoding="utf-8")
    assert str(ROOT) not in helper.read_text(encoding="utf-8")
    assert _state(host) == before


def test_csharp_comment_clean_source_keeps_strings_and_directives_out(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result, output = _analyze(
        host, run="clean", target="src/CSharpComment/CleanEvidence.cs"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(output)
    assert payload["status"] == "complete"
    assert payload["outcome"] == "clean-within-complete"
    assert payload["findings"] == []
    assert (output / "detections.jsonl").read_text(encoding="utf-8") == ""
    comments = payload["analysis"]["csharp"]["files"][0]["comments"]
    assert [comment["text"].strip() for comment in comments] == [
        "Preserve this value because fixture stability is part of the contract."
    ]
    assert _state(host) == before


def test_csharp_comment_terminal_replacement_tool_project_and_recovery(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    source = host / "src/CSharpComment/CommentEvidence.cs"
    pristine_source = source.read_text(encoding="utf-8")
    manifest = host / "csharp-project.json"
    pristine_manifest = manifest.read_text(encoding="utf-8")

    valid, output = _analyze(host, run="lifecycle")
    assert valid.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    for artifact in ("detections.jsonl", "scan.json", "findings.json", "report.md"):
        (output / artifact).write_text("STALE-ARTIFACT\n", encoding="utf-8")

    source.write_bytes((FIXTURE / "malformed/Broken.cs").read_bytes())
    failed, _ = _analyze(host, run="lifecycle")
    failed_payload = _payload(output)
    assert failed.returncode == 2
    assert failed_payload["status"] == "failed"
    assert failed_payload["failure_kind"] == "csharp_compiler_diagnostic_failed"
    assert failed_payload["outcome"] == "incomplete"
    assert failed_payload["findings"] == []
    assert _records(output) == []
    assert "STALE-ARTIFACT" not in (output / "report.md").read_text(encoding="utf-8")
    assert "advisory-findings" not in (output / "report.md").read_text(encoding="utf-8")

    source.write_text(pristine_source, encoding="utf-8")
    unsupported, _ = _analyze(
        host, run="lifecycle", dotnet=host / "missing-dotnet"
    )
    unsupported_payload = _payload(output)
    assert unsupported.returncode == 0
    assert unsupported_payload["status"] == "unsupported"
    assert unsupported_payload["failure_kind"] == "dotnet_tool_missing"
    assert unsupported_payload["outcome"] == "incomplete"
    assert unsupported_payload["findings"] == []

    recovered, _ = _analyze(host, run="lifecycle")
    assert recovered.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    assert len(_records(output)) == 4

    manifest.write_text("{}\n", encoding="utf-8")
    project_failed, _ = _analyze(host, run="lifecycle")
    project_payload = _payload(output)
    assert project_failed.returncode == 2
    assert project_payload["status"] == "failed"
    assert project_payload["failure_kind"] == "csharp_project_manifest_invalid"
    assert project_payload["outcome"] == "incomplete"
    assert project_payload["findings"] == []

    manifest.write_text(pristine_manifest, encoding="utf-8")
    final, _ = _analyze(host, run="lifecycle")
    assert final.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    assert _state(host) == before


def test_csharp_comment_docs_state_explicit_nonclaims() -> None:
    docs = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    normalized_docs = " ".join(docs.split())
    helper = HELPER.read_text(encoding="utf-8")
    for phrase in (
        "UTF-16 code units",
        "Strings, directives",
        "does not attach prose to a declaration",
        "runtime reachability",
        "XML-doc completeness",
    ):
        assert phrase in normalized_docs
    for phrase in (
        "comment-to-declaration",
        "semantic drift",
        "not proof that the comment merely narrates code",
        "not byte offsets",
    ):
        assert phrase in helper
