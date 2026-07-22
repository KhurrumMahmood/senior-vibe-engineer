"""C++20 lexical-comment outcomes, lifecycle, and copied-closure proof."""
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
HELPER = SKILL / "scripts" / "analyze_comments_cpp.py"
FIXTURE = ROOT / "tests" / "fixtures" / "find-comment-drift-cpp"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
CLANG = shutil.which("clang")
CXX = shutil.which("clang++")
MAKE = shutil.which("make")
pytestmark = pytest.mark.skipif(
    CLANG is None or CXX is None or MAKE is None,
    reason="Apple Clang 21, clang++, and Make are required",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=False, timeout=30
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "external-library"
    shutil.copytree(FIXTURE / "host", host)
    return host


def _materialize_database(host: Path) -> None:
    result = _run(str(MAKE), "clean", "compile-db", f"CXX={CXX}", cwd=host)
    assert result.returncode == 0, result.stdout + result.stderr


def _source_hashes(host: Path) -> dict[str, str]:
    suffixes = {
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".hh",
        ".hxx",
        ".h",
        ".inc",
        ".ipp",
        ".inl",
        ".tpp",
    }
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and not path.is_symlink() and path.suffix in suffixes
    }


def _analyze(
    helper: Path,
    host: Path,
    destination: Path,
    *targets: str,
    clang: str | None = None,
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


def _verify(helper: Path, host: Path, artifact: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON),
        "-I",
        "-S",
        str(helper),
        "--project-root",
        str(host),
        "--verify-artifact",
        str(artifact),
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


def test_cpp_real_drift_reaches_final_artifact_copied_closure_and_native_boundary(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    native = _run(str(MAKE), "clean", "test", f"CXX={CXX}", cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    _materialize_database(host)
    before = _source_hashes(host)
    installed = tmp_path / "installed" / "on-demand" / "find-comment-drift"
    shutil.copytree(SKILL, installed)
    output = host / "reports" / "find-comment-drift" / "cpp" / "detections.jsonl"

    result = _analyze(installed / "scripts" / "analyze_comments_cpp.py", host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    records = _records(output)
    assert len(records) == 1
    finding = records[0]
    assert finding["pattern"] == "obvious_narration_comment"
    assert finding["file"] == "src/invoice.cpp"
    assert finding["language"] == "cpp"
    assert finding["lineno"] == 11
    assert finding["source_sha256"] == before["src/invoice.cpp"]
    assert finding["source_span"]["start"] == {"line": 11, "column": 5}
    assert finding["evidence_kind"] == "clang-raw-comment-token"

    report = _payload(output)
    cpp = report["analysis"]["cpp"]
    assert report["status"] == cpp["status"] == "complete"
    assert report["outcome"] == cpp["outcome"] == "advisory-findings"
    assert cpp["analyzer"] == "clang-raw-tokens"
    assert cpp["syntax_standard"] == "c++20"
    assert cpp["lexical_only"] is True
    assert cpp["source_preserved"] is True
    assert cpp["source_manifest_sha256"]
    assert _verify(installed / "scripts" / "analyze_comments_cpp.py", host, output.with_name("findings.json")).returncode == 0
    assert _source_hashes(host) == before
    assert "scripts/_lib" not in (installed / "scripts" / "analyze_comments_cpp.py").read_text()
    assert str(ROOT) not in (installed / "scripts" / "analyze_comments_cpp.py").read_text()


def test_cpp_inventory_owns_compile_dependencies_and_preserves_role_boundaries(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    (host / "linked.cpp").symlink_to(host / "src" / "invoice.cpp")
    _materialize_database(host)
    before = _source_hashes(host)
    output = host / "reports" / "inventory" / "detections.jsonl"

    result = _analyze(HELPER, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    cpp = _payload(output)["analysis"]["cpp"]
    inventory = {row["file"]: row for row in cpp["inventory"]}
    for path in (
        "src/invoice.cpp",
        "src/common.h",
        "src/format_support.inl",
        "src/roles.cc",
        "src/ledger.cxx",
        "include/cpppilot/invoice.hpp",
        "include/cpppilot/roles.hh",
        "include/cpppilot/ledger.hxx",
        "include/cpppilot/identity.tpp",
        "src/invoice_detail.hpp",
        "src/invoice_format.ipp",
    ):
        assert inventory[path]["role"] == "eligible"
        assert inventory[path]["source_sha256"] == before[path]
    assert inventory["include/orphan.h"]["reason"] == "ambiguous-header"
    assert inventory["include/orphan.hpp"]["reason"] == "ambiguous-header"
    assert inventory["generated/GeneratedInvoice.cpp"]["reason"] == "generated-tree"
    assert inventory["src/wire_generated.cpp"]["reason"] == "generated-marker"
    assert inventory["vendor/example/VendorInvoice.cpp"]["reason"] == "vendor"
    assert inventory["tests/invoice_test.cpp"]["reason"] == "test-tree"
    assert inventory["build/BuildSentinel.cpp"]["reason"] == "build-tree"
    assert inventory["linked.cpp"]["reason"] == "symlink"
    assert "foreign/Foreign.c" not in inventory
    assert "foreign/Foreign.mm" not in inventory
    assert "foreign/Upper.CPP" not in inventory
    assert cpp["compile_database"]["status"] == "valid"
    assert _source_hashes(host) == before


def test_cpp_additional_translation_unit_suffixes_are_real_source_roles(
    tmp_path: Path,
) -> None:
    host = tmp_path / "source-roles"
    host.mkdir()
    for name in ("adapter.c++", "bridge.C", "preprocessed.ii"):
        source = host / name
        source.write_text(
            "// Keep this rationale because the role fixture must stay clean.\n"
            f"int role_{len(name)}() {{ return {len(name)}; }}\n",
            encoding="utf-8",
        )
        native = _run(str(CXX), "-std=c++20", "-fsyntax-only", str(source), cwd=host)
        assert native.returncode == 0, native.stdout + native.stderr
    output = host / "reports" / "roles" / "detections.jsonl"

    result = _analyze(HELPER, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _records(output) == []
    report = _payload(output)
    assert report["status"] == "complete"
    assert report["outcome"] == "clean-within-complete"
    assert {
        row["file"]
        for row in report["analysis"]["cpp"]["inventory"]
        if row["role"] == "eligible"
    } == {"adapter.c++", "bridge.C", "preprocessed.ii"}


def test_cpp_clean_decoys_do_not_fire_and_malformed_is_not_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _materialize_database(host)
    clean_output = host / "reports" / "clean" / "detections.jsonl"

    clean = _analyze(HELPER, host, clean_output, "src/main.cpp", "src/invoice_detail.hpp")

    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert _records(clean_output) == []
    clean_report = _payload(clean_output)
    assert clean_report["status"] == "complete"
    assert clean_report["outcome"] == "clean-within-complete"

    broken = host / "src" / "Broken.cpp"
    shutil.copyfile(FIXTURE / "malformed" / "Broken.cpp", broken)
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _analyze(HELPER, host, partial_output, "src/Broken.cpp")

    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert _records(partial_output) == []
    partial_report = _payload(partial_output)
    assert partial_report["status"] == "partial"
    assert partial_report["outcome"] == "incomplete"
    row = partial_report["analysis"]["cpp"]["inventory"][0]
    assert row["role"] == "failed"
    assert row["reason"] == "syntax-error"


@pytest.mark.parametrize("state", ("missing", "malformed", "incomplete", "stale"))
def test_cpp_compile_database_states_keep_headers_ambiguous(
    tmp_path: Path, state: str
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
        os.utime(host / "src" / "main.cpp", ns=(newer, newer))
    output = host / "reports" / state / "detections.jsonl"

    result = _analyze(HELPER, host, output, "include")

    assert result.returncode == 2
    report = _payload(output)
    cpp = report["analysis"]["cpp"]
    assert cpp["compile_database"]["status"] == state
    assert report["status"] == "unsupported"
    assert {row["reason"] for row in cpp["inventory"]} == {"ambiguous-header"}


def _fake_clang(path: Path, version: str, raw_mode: str) -> None:
    raw = {
        "failed": "exit 9",
        "malformed": "printf '%s\\n' 'not clang token output'",
        "incomplete": "printf '%s\\n' \"raw_identifier 'int' Loc=<fake.cpp:1:1>\"",
    }[raw_mode]
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        f"  printf '%s\\n' 'Apple clang version {version}'\n"
        "  exit 0\n"
        "fi\n"
        "case \"$*\" in\n"
        f"  *-dump-raw-tokens*) {raw} ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_cpp_tool_and_provider_states_replace_stale_success(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _materialize_database(host)
    output = host / "reports" / "lifecycle" / "detections.jsonl"
    target = "src/invoice.cpp"

    missing = _analyze(HELPER, host, output, target, clang=str(tmp_path / "missing"))
    assert missing.returncode == 2
    assert _payload(output)["analysis"]["cpp"]["failure_kind"] == "clang-tool-missing"

    old = tmp_path / "old-clang"
    _fake_clang(old, "20.0.0", "failed")
    too_old = _analyze(HELPER, host, output, target, clang=str(old))
    assert too_old.returncode == 2
    assert _payload(output)["analysis"]["cpp"]["failure_kind"] == "clang-version-too-old"

    valid = _analyze(HELPER, host, output, target)
    assert valid.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"

    for mode, failure_kind in (
        ("failed", "clang-analysis-failed"),
        ("malformed", "clang-output-malformed"),
        ("incomplete", "clang-output-incomplete"),
    ):
        fake = tmp_path / f"{mode}-clang"
        _fake_clang(fake, "21.0.0", mode)
        result = _analyze(HELPER, host, output, target, clang=str(fake))
        assert result.returncode == 1
        assert _records(output) == []
        report = _payload(output)
        assert report["status"] == "failed"
        assert report["outcome"] == "failed"
        assert report["analysis"]["cpp"]["failure_kind"] == failure_kind
        assert "advisory-findings" not in output.with_name("report.md").read_text()


def test_cpp_artifact_verifier_rejects_stale_source_and_tampered_hash(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    _materialize_database(host)
    output = host / "reports" / "verify" / "detections.jsonl"
    assert _analyze(HELPER, host, output, "src/invoice.cpp").returncode == 0
    artifact = output.with_name("findings.json")
    assert _payload(output)["outcome"] == "advisory-findings"
    assert _verify(HELPER, host, artifact).returncode == 0

    source = host / "src" / "invoice.cpp"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    stale = _verify(HELPER, host, artifact)
    assert stale.returncode == 2
    assert "source hash mismatch: src/invoice.cpp" in stale.stderr
    source.write_text(original, encoding="utf-8")

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["findings"][0]["source_sha256"] = "0" * 64
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    tampered = _verify(HELPER, host, artifact)
    assert tampered.returncode == 2
    assert "finding source hash mismatch: src/invoice.cpp" in tampered.stderr


def test_cpp_docs_name_lexical_limits_and_exact_copied_command() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "C++20" in text
    assert "analyze_comments_cpp.py" in text
    assert "--verify-artifact" in text
    assert "macro expansion" in text
    assert "inactive branches" in text
    assert "comment-to-symbol" in text
    assert "Objective-C++" in text
