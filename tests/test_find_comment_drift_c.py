"""C lexical comment evidence and final-outcome lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "find-comment-drift"
HELPER = SKILL / "scripts" / "analyze_comments_c.py"
FIXTURE = ROOT / "tests" / "fixtures" / "c-pilot"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
CLANG = shutil.which("clang")
MAKE = shutil.which("make")
pytestmark = pytest.mark.skipif(
    CLANG is None or MAKE is None, reason="Clang 21 and Make are required"
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=False, timeout=30
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    return host


def _materialize_database(host: Path) -> None:
    result = _run(str(MAKE), "clean", "compile-db", f"CC={CLANG}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr


def _source_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.casefold() in {".c", ".i", ".h", ".inc"}
    }


def _analyze(
    helper: Path, host: Path, destination: Path, *targets: str, clang: str | None = None
) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON),
        "-I",
        "-S",
        str(helper),
        "--project-root",
        str(host),
        "--clang",
        clang or str(CLANG),
        "--output",
        str(destination),
        *(targets or (".",)),
        cwd=host,
    )


def _payload(output: Path) -> dict:
    return json.loads(output.with_name("findings.json").read_text(encoding="utf-8"))


def _records(output: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_c_positive_exact_raw_token_span_copied_closure_and_preservation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    candidate = host / "src" / "comment_candidate.c"
    source = "int candidate(void)\n{\n    // Return invoice label.\n    return 1;\n}\n"
    candidate.write_text(source, encoding="utf-8")
    before = _source_hashes(host)
    installed = tmp_path / "installed" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "find-comment-drift" / "positive" / "detections.jsonl"

    result = _analyze(
        installed / "scripts" / "analyze_comments_c.py",
        host,
        output,
        "src/comment_candidate.c",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = _payload(output)
    assert report["status"] == "complete"
    assert report["outcome"] == "advisory-findings"
    assert report["analysis"]["c"]["analyzer"] == "clang-raw-tokens"
    assert report["analysis"]["c"]["lexical_only"] is True
    records = _records(output)
    assert len(records) == 1
    finding = records[0]
    assert finding["pattern"] == "obvious_narration_comment"
    assert finding["file"] == "src/comment_candidate.c"
    assert finding["lineno"] == 3
    assert finding["source_span"]["start"] == {"line": 3, "column": 5}
    spelling = "// Return invoice label."
    start = source.encode().index(spelling.encode())
    assert finding["source_span"]["start_byte"] == start
    assert finding["source_span"]["end_byte"] == start + len(spelling.encode())
    assert finding["source_span"]["end"] == {"line": 3, "column": 29}
    assert report["analysis"]["c"]["source_preserved"] is True
    assert _source_hashes(host) == before
    helper_text = (installed / "scripts" / "analyze_comments_c.py").read_text()
    assert "scripts/_lib" not in helper_text
    assert str(ROOT) not in helper_text


def test_c_clean_complete_owns_only_compile_dependency_headers_and_builds_c17(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    _materialize_database(host)
    built = _run(str(MAKE), "clean", "test", f"CC={CLANG}", cwd=host)
    assert built.returncode == 0, built.stdout + built.stderr
    _materialize_database(host)
    before = _source_hashes(host)
    output = host / "reports" / "find-comment-drift" / "clean" / "detections.jsonl"

    result = _analyze(HELPER, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _records(output) == []
    report = _payload(output)
    c = report["analysis"]["c"]
    assert report["status"] == c["status"] == "complete"
    assert report["outcome"] == c["outcome"] == "clean-within-complete"
    assert c["compile_database"]["status"] == "valid"
    assert c["syntax_standard"] == "c17"
    inventory = {row["file"]: row for row in c["inventory"]}
    for path in (
        "src/invoice.c",
        "src/main.c",
        "include/cpilot/invoice.h",
        "src/invoice_internal.h",
        "src/pilot_mode.inc",
    ):
        assert inventory[path]["role"] == "eligible"
        assert inventory[path]["source_sha256"] == before[path]
    assert inventory["include/orphan.h"]["reason"] == "ambiguous-header"
    assert inventory["include/orphan.inc"]["reason"] == "ambiguous-header"
    assert inventory["generated/GeneratedInvoice.c"]["reason"] == "generated-tree"
    assert inventory["vendor/VendorInvoice.c"]["reason"] == "vendor"
    assert inventory["tests/invoice_test.c"]["reason"] == "test-tree"
    assert inventory["build/BuildSentinel.c"]["reason"] == "build-tree"
    assert c["source_preserved"] is True
    assert _source_hashes(host) == before


def test_c_malformed_is_partial_and_zero_findings_are_not_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    broken = host / "src" / "Broken.c"
    shutil.copyfile(FIXTURE / "malformed" / "Broken.c", broken)
    before = _source_hashes(host)
    output = host / "reports" / "find-comment-drift" / "partial" / "detections.jsonl"

    result = _analyze(HELPER, host, output, "src/Broken.c")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _records(output) == []
    report = _payload(output)
    assert report["status"] == "partial"
    assert report["outcome"] == "incomplete"
    row = report["analysis"]["c"]["inventory"][0]
    assert row["role"] == "failed"
    assert row["reason"] == "syntax-error"
    assert report["analysis"]["c"]["summary"]["failed"] == 1
    assert _source_hashes(host) == before


@pytest.mark.parametrize(
    ("state", "expected"),
    (("missing", "missing"), ("malformed", "malformed"), ("incomplete", "incomplete"), ("stale", "stale")),
)
def test_c_compile_database_states_keep_headers_ambiguous(
    tmp_path: Path, state: str, expected: str
) -> None:
    host = _copy_host(tmp_path)
    database = host / "compile_commands.json"
    if state != "missing":
        _materialize_database(host)
    if state == "malformed":
        database.write_text("{", encoding="utf-8")
    elif state == "incomplete":
        rows = json.loads(database.read_text(encoding="utf-8"))
        database.write_text(json.dumps(rows[:1]), encoding="utf-8")
    elif state == "stale":
        newer = database.stat().st_mtime_ns + 2_000_000_000
        os.utime(host / "src" / "main.c", ns=(newer, newer))
    output = host / "reports" / state / "detections.jsonl"

    _analyze(HELPER, host, output, "include")

    report = _payload(output)
    c = report["analysis"]["c"]
    assert c["compile_database"]["status"] == expected
    assert report["status"] == "unsupported"
    assert report["outcome"] == "unsupported"
    assert {row["reason"] for row in c["inventory"]} == {"ambiguous-header"}


def _fake_clang(path: Path, version: str, analysis_exit: int = 0) -> None:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        f"  printf '%s\\n' 'Apple clang version {version}'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {analysis_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_c_tool_states_and_same_destination_replace_stale_outputs(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    candidate = host / "src" / "comment_candidate.c"
    candidate.write_text(
        "int candidate(void)\n{\n    // Return invoice label.\n    return 1;\n}\n",
        encoding="utf-8",
    )
    output = host / "reports" / "lifecycle" / "detections.jsonl"
    missing = _analyze(HELPER, host, output, "src/comment_candidate.c", clang=str(tmp_path / "missing"))
    assert missing.returncode == 2
    assert _payload(output)["status"] == "unsupported"
    assert _payload(output)["analysis"]["c"]["failure_kind"] == "clang-tool-missing"

    old = tmp_path / "old-clang"
    _fake_clang(old, "20.0.0")
    too_old = _analyze(HELPER, host, output, "src/comment_candidate.c", clang=str(old))
    assert too_old.returncode == 2
    assert _payload(output)["analysis"]["c"]["failure_kind"] == "clang-version-too-old"

    valid = _analyze(HELPER, host, output, "src/comment_candidate.c")
    assert valid.returncode == 0
    assert _payload(output)["status"] == "complete"
    assert _payload(output)["outcome"] == "advisory-findings"
    assert len(_records(output)) == 1

    failing = tmp_path / "failing-clang"
    _fake_clang(failing, "21.0.0", analysis_exit=9)
    failed = _analyze(HELPER, host, output, "src/comment_candidate.c", clang=str(failing))
    assert failed.returncode == 1
    assert _records(output) == []
    report = _payload(output)
    assert report["status"] == "failed"
    assert report["outcome"] == "failed"
    assert report["analysis"]["c"]["failure_kind"] == "clang-analysis-failed"
    assert "advisory-findings" not in output.with_name("report.md").read_text()


def test_c_helper_names_lexical_limits_without_other_language_claims() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert "macro expansion" in text
    assert "inactive branches" in text
    assert "comment-to-symbol" in text
    assert "Objective-C" in text
    assert "C++" in text
