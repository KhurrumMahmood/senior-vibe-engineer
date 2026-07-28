"""Value and copied-closure contract for the bounded C++20 lexical/syntax cohort."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/cpp-lexical-syntax/host"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
CLANGXX = Path(shutil.which("clang++") or "")
MAKE = Path(shutil.which("make") or "")
PROVIDER = ROOT / ".claude/skills/_cpp/cpp_facts.py"
SCRIPTS = {
    "adapt": ROOT / ".claude/skills/adapt-project/scripts/discover_cpp.py",
    "explain": ROOT / ".claude/skills/explain-code/scripts/explain_cpp.py",
    "concept": ROOT / ".claude/skills/find-concept-divergence/scripts/scan_cpp.py",
    "duplication": ROOT / ".claude/skills/find-duplication/scripts/run_cpp.py",
    "folder": ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_cpp.py",
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_cpp.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_cpp.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_cpp.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_cpp.py",
}


def _clang_21() -> bool:
    if not CLANGXX.is_file():
        return False
    result = subprocess.run(
        [str(CLANGXX), "--version"], capture_output=True, text=True, check=False
    )
    match = re.search(r"(?:Apple )?clang version (\d+)\.(\d+)\.(\d+)", result.stdout)
    return bool(match and tuple(map(int, match.groups())) >= (21, 0, 0))


pytestmark = pytest.mark.skipif(
    not (_clang_21() and MAKE.is_file() and PYTHON.is_file()),
    reason="Clang++ 21, Make, and frozen product Python are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    native = _run(
        str(MAKE), "clean", "test", "compile-db", f"CXX={CLANGXX}", cwd=host
    )
    assert native.returncode == 0, native.stdout + native.stderr
    assert "cpp-native-test:ok\n" in native.stdout
    smoke = _run(str(host / ".native-build/cpp-cohort-smoke"), cwd=host)
    assert smoke.returncode == 0
    assert smoke.stdout == "cpp-cohort:10:6\n"
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


def _provider(host: Path, *, script: Path = PROVIDER, clangxx: Path = CLANGXX):
    return _run(
        str(PYTHON), "-I", "-S", str(script),
        "--project-root", str(host), "--target", ".",
        "--clangxx", str(clangxx), "--json", cwd=host,
    )


def _output(host: Path, kind: str) -> Path:
    return host / "reports" / kind


def _invoke(
    host: Path,
    kind: str,
    *,
    script: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    selected = script or SCRIPTS[kind]
    base = [
        str(PYTHON), "-I", "-S", str(selected),
        "--project-root", str(host), "--clangxx", str(CLANGXX),
    ]
    output = _output(host, kind)
    if kind == "adapt":
        base.extend(["--output-dir", str(output), "."])
    elif kind == "explain":
        base.extend(["--target", ".", "--output", str(output / "cpp.md")])
    elif kind == "concept":
        base.extend([
            "--glossary", str(host / ".claude/contracts/concepts.json"),
            "--output", str(output / "findings.jsonl"),
            "--report", str(output / "report.md"), ".",
        ])
    elif kind == "duplication":
        base.extend(["--target", "src", "--output-dir", str(output)])
    elif kind == "folder":
        base.extend([
            "--cpp-root", "src", "--min-cluster-size", "3",
            "--output", str(output / "detections.jsonl"),
        ])
    elif kind in {"audit", "complexity"}:
        base.extend([
            "--target", "." if kind == "audit" else "src",
            "--output-dir", str(output),
        ])
    elif kind == "omnibus":
        base.extend([
            "--target", "src", "--output-dir", str(output),
            "--scout-dir", str(host / "cpp-scouts"),
        ])
    elif kind == "standards":
        base.extend([
            "--target", "src", "--output-dir", str(output),
            "--ideas", str(host / "standards-cpp.json"),
        ])
    return _run(*base, cwd=cwd or host)


def _artifact(host: Path, kind: str) -> dict:
    names = {
        "adapt": "adapter.json",
        "explain": "cpp/targets.json",
        "concept": "findings.json",
        "duplication": "findings.json",
        "folder": "findings.json",
        "audit": "raw-drift.json",
        "complexity": "findings.json",
        "omnibus": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def test_cpp_provider_represents_cpp_identity_and_compile_owned_headers(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _provider(host)

    assert result.returncode == 0, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["status"] == "complete"
    assert facts["language"] == "cpp"
    assert facts["syntax_standard"] == "c++20"
    assert facts["analyzer"] == "clang++-c++20-raw-tokens+recursive-ast-json"
    assert facts["compile_database"]["state"] == "valid-current-complete-c++20-mode"
    assert facts["compile_database"]["translation_units"] == [
        "src/billing_parser.cpp", "src/billing_types.cc",
        "src/billing_validator.cxx", "src/main.cpp", "src/omnibus.cpp",
        "src/syntax.cpp",
    ]
    assert set(facts["compile_database"]["owned_headers"]) == {
        "include/cohort/billing.hpp", "include/cohort/detail.tpp", "src/internal.h"
    }
    inventory = {row["file"]: row for row in facts["inventory"]}
    assert inventory["include/cohort/billing.hpp"]["role"] == "header"
    assert inventory["include/orphan.hpp"]["role"] == "ambiguous-header"
    assert inventory["tests/decoy_test.cpp"]["role"] == "test"
    assert inventory["generated/Generated.cpp"]["role"] == "generated"
    assert inventory["vendor/Vendor.cc"]["role"] == "vendor"
    assert inventory["build/Build.cxx"]["role"] == "build"
    assert "foreign/Foreign.c" not in inventory
    declarations = [item for file in facts["files"] for item in file["declarations"]]
    overloads = [
        row for row in declarations if row["qualified_name"] == "cohort::Ledger::total"
    ]
    assert len({row["signature"] for row in overloads}) == 2
    assert any(row["qualified_name"] == "cohort::Ledger::operator[]" and row["operator"] for row in declarations)
    assert any(row["qualified_name"] == "cohort::operator==" and row["operator"] for row in declarations)
    assert any(row["qualified_name"] == "cohort::label_for" and row["template"] for row in declarations)
    assert facts["boundaries"]["header_ownership"] == "compile-command dependency closure only"
    assert facts["boundaries"]["odr"] == "not proven"
    assert facts["boundaries"]["abi"] == "not analyzed"
    assert any("virtual and dynamic dispatch" in limit for limit in facts["limits"])
    assert facts["source_manifest"]["preserved"] is True
    assert _state(host) == before


def test_cpp_complexity_writes_useful_artifacts_outside_host(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    output = tmp_path / "external-artifacts" / "complexity"

    result = _run(
        str(PYTHON), "-I", "-S", str(SCRIPTS["complexity"]),
        "--project-root", str(host), "--clangxx", str(CLANGXX),
        "--target", "src", "--output-dir", str(output), "--no-host-write",
        cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((output / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert [(row["qualified_name"], row["branch_score"]) for row in payload["findings"]] == [
        ("cohort::route_invoice", 8)
    ]
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "Findings: 1" in report
    assert "cohort::route_invoice" in report
    assert _state(host) == before


def test_nine_cpp_consumers_produce_bounded_value_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    results = {kind: _invoke(host, kind) for kind in SCRIPTS}

    assert {kind: result.returncode for kind, result in results.items()} == {
        "adapt": 0, "explain": 0, "concept": 0, "duplication": 0,
        "folder": 0, "audit": 1, "complexity": 0, "omnibus": 0,
        "standards": 1,
    }, {kind: result.stdout + result.stderr for kind, result in results.items()}
    adapter = _artifact(host, "adapt")
    assert adapter["status"] == "complete"
    assert adapter["stack"]["languages"] == ["cpp"]
    assert adapter["source_roots"][0]["cpp_translation_units"] == 6
    assert adapter["source_roots"][0]["compiler_owned_headers"] == 3

    explained = _artifact(host, "explain")
    selected = {(row["qualified_name"], row["signature"]) for row in explained["selected"]}
    assert len({signature for name, signature in selected if name == "cohort::Ledger::total"}) == 2
    assert any(name == "cohort::Ledger::operator[]" for name, _ in selected)
    assert any(row["template"] for row in explained["selected"] if row["qualified_name"] == "cohort::label_for")

    concept = _artifact(host, "concept")
    assert concept["outcome"] == "drift-found"
    assert [(row["file"], row["term"]) for row in concept["findings"]] == [
        ("src/billing_parser.cpp", "cancelled_order")
    ]

    duplication = _artifact(host, "duplication")
    assert len(duplication["findings"]) == 1
    assert {site["qualified_name"] for site in duplication["findings"][0]["sites"]} == {
        "cohort::billing_pending_total", "cohort::billing_queued_total"
    }

    folder = _artifact(host, "folder")
    assert folder["outcome"] == "drift-found"
    assert folder["findings"][0]["files"] == [
        "src/billing_parser.cpp", "src/billing_types.cc", "src/billing_validator.cxx"
    ]

    audit = _artifact(host, "audit")
    references = {(row["id"], row["resolved"]) for row in audit["references"]}
    assert {( "0001", True), ("9999", False)} <= references
    assert "code-ref-orphan" in {row["symptom"] for row in audit["drift"]}

    complexity = _artifact(host, "complexity")
    assert [(row["qualified_name"], row["branch_score"]) for row in complexity["findings"]] == [
        ("cohort::route_invoice", 8)
    ]

    omnibus = _artifact(host, "omnibus")
    assert omnibus["status"] == "complete"
    assert omnibus["summary"] == {"confirmed_omnibus": 1}
    assert omnibus["findings"][0]["file"] == "src/omnibus.cpp"
    assert omnibus["findings"][0]["scout_verdict"] == "explicit"

    standards = _artifact(host, "standards")
    standard = standards["standards"][0]
    assert (standard["situation_sites"], standard["gap_count"], standard["coverage_percent"]) == (2, 1, 50.0)
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("src/syntax.cpp", "cohort::unhandled_parse")
    ]
    analyses = [
        adapter["analysis"]["cpp"], explained["analysis"]["cpp"],
        concept["analysis"]["cpp"], duplication["analysis"]["cpp"],
        folder["analysis"]["cpp"], audit["analysis"]["cpp"],
        complexity["analysis"]["cpp"], omnibus["analysis"]["cpp"],
        standards["analysis"]["cpp"],
    ]
    assert len({row["source_manifest"]["before_sha256"] for row in analyses}) == 1
    assert all(row["source_manifest"]["preserved"] for row in analyses)
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(SCRIPTS))
def test_each_cpp_consumer_runs_from_exact_copied_closure(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    installed = host / ".agents/skills"
    shutil.copytree(PROVIDER.parent, installed / "_cpp")
    copied_skill = installed / SCRIPTS[kind].parents[1].name
    shutil.copytree(SCRIPTS[kind].parents[1], copied_skill)
    copied = copied_skill / "scripts" / SCRIPTS[kind].name
    outside = tmp_path / f"outside-{kind}"
    outside.mkdir()

    result = _invoke(host, kind, script=copied, cwd=outside)

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    assert _artifact(host, kind)["status"] == "complete"
    assert str(ROOT) not in copied.read_text(encoding="utf-8")


def test_cpp_terminal_states_never_claim_clean_and_replace_artifacts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    first = _invoke(host, "complexity")
    assert first.returncode == 0
    assert _artifact(host, "complexity")["status"] == "complete"

    (host / "src/syntax.cpp").write_text("int broken( {\n", encoding="utf-8")
    refreshed = _run(str(MAKE), "compile-db", f"CXX={CLANGXX}", cwd=host)
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    failed = _invoke(host, "complexity")
    assert failed.returncode == 2
    payload = _artifact(host, "complexity")
    assert payload["status"] == "failed"
    assert payload["findings"] == []
    assert payload["failure_kind"] in {"clang_dependency_failed", "clang_ast_failed"}

    missing = _provider(host, clangxx=host / "missing-clang++")
    missing_payload = json.loads(missing.stdout)
    assert missing.returncode == 0
    assert missing_payload["status"] == "unsupported"
    assert missing_payload["failure_kind"] == "clangxx_tool_missing"
