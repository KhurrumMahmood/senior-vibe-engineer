"""Final-outcome contract for the four Rust syntax-family consumers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/rust-syntax-family"
SHARED = ROOT / ".claude/skills/_rust-syntax/scripts/rust_syntax_facts.py"
ADAPTERS = {
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_rust.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_rust.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_rust.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_rust.py",
}
TOOLS = {
    name: shutil.which(name)
    for name in ("cargo", "rustc", "rustfmt", "cargo-clippy")
}
pytestmark = pytest.mark.skipif(
    not all(TOOLS.values()), reason="frozen Rust syntax toolchain is unavailable"
)


def _run(*argv: str, cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    return host


def _state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "reports":
            continue
        if path.is_symlink():
            state[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative.as_posix()] = (
                "file", hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return state


def _tool_args() -> list[str]:
    return [
        "--cargo", str(TOOLS["cargo"]),
        "--rustc", str(TOOLS["rustc"]),
        "--rustfmt", str(TOOLS["rustfmt"]),
        "--clippy", str(TOOLS["cargo-clippy"]),
    ]


def _shared(host: Path, *extra: str, script: Path = SHARED) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable, "-I", "-S", str(script),
        "--project-root", str(host), "--target", ".", *_tool_args(), *extra,
        "--json", cwd=host,
    )


def _output(host: Path, kind: str) -> Path:
    roots = {
        "audit": "audit-decisions",
        "complexity": "find-complexity-hotspots",
        "omnibus": "omnibus",
        "standards": "standard-gaps",
    }
    return host / "reports" / roots[kind] / "rust-scan"


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    extra: tuple[str, ...] = (),
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable, "-I", "-S", str(adapter or ADAPTERS[kind]),
        "--project-root", str(host),
        "--target", "." if kind == "audit" else "crates/syntax-core/src",
        "--output-dir", str(_output(host, kind)),
        *_tool_args(),
    ]
    if kind == "standards":
        argv.extend(["--ideas", str(host / "standards-rust.json")])
    if kind == "omnibus":
        argv.extend(["--scout-dir", str(host / "rust-scouts")])
    argv.extend(extra)
    return _run(*argv, cwd=cwd or host)


def _final_json(host: Path, kind: str) -> dict:
    names = {
        "audit": "raw-drift.json",
        "complexity": "findings.json",
        "omnibus": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def _fake(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_shared_rust_facts_are_native_complete_role_aware_and_source_preserving(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _shared(host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "complete"
    assert payload["analyzer"] == "rust-syntax-facts-v1"
    assert payload["source_manifest"]["before_sha256"] == payload["source_manifest"]["after_sha256"]
    assert _state(host) == before
    native = payload["native"]
    assert all(native[name]["passed"] for name in (
        "cargo_metadata", "cargo_check", "cargo_test", "cargo_clippy", "cargo_fmt"
    ))
    inventory = {row["file"]: row for row in payload["inventory"]}
    assert inventory["crates/syntax-core/src/complexity.rs"]["role"] == "source"
    assert inventory["crates/syntax-core/tests/excluded_test.rs"]["role"] == "test"
    assert inventory["crates/syntax-core/build.rs"]["role"] == "configuration"
    assert inventory["crates/syntax-core/examples/excluded_example.rs"]["role"] == "auxiliary"
    assert inventory["generated/Generated.rs"]["role"] == "generated"
    assert inventory["vendor/Vendor.rs"]["role"] == "vendor"
    assert inventory["target/Target.rs"]["role"] == "build"
    facts = {row["file"]: row for row in payload["files"]}
    high = next(row for row in facts["crates/syntax-core/src/complexity.rs"]["functions"] if row["name"] == "route_invoice")
    decoy = next(row for row in facts["crates/syntax-core/src/complexity.rs"]["functions"] if row["name"] == "closure_decoy")
    assert high["branch_score"] == 9
    assert decoy["branch_score"] == 0
    references = [comment["text"] for comment in facts["crates/syntax-core/src/decisions.rs"]["comments"]]
    assert any("decision:0001" in text for text in references)
    assert not any("decision:7777" in text or "decision:8888" in text for text in references)


def test_audit_decisions_rust_writes_resolved_orphan_and_registry_value(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "audit")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final_json(host, "audit")
    assert report["status"] == "complete"
    rust = report["analysis"]["rust"]
    assert rust["status"] == "complete"
    references = {(row["id"], row["resolved"], row["language"]) for row in report["references"]}
    assert ("0001", True, "rust") in references
    assert ("9999", False, "rust") in references
    assert not any(identifier in {"7000", "6000", "5000", "7777", "8888"} for identifier, _, _ in references)
    assert {row["symptom"] for row in report["drift"]} >= {"code-ref-orphan", "unreferenced-decision"}
    output = _output(host, "audit")
    assert {path.name for path in output.iterdir()} == {
        "drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt"
    }
    assert _state(host) == before


def test_complexity_rust_reports_only_direct_function_branch_value(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "complexity")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "complexity")
    assert report["status"] == "complete"
    assert report["verdict"] == "measure-first"
    findings = report["findings"]
    assert [(row["function"], row["branch_score"]) for row in findings] == [("route_invoice", 9)]
    assert findings[0]["analyzer"] == "rust-syntax-facts-v1"
    assert "closure_decoy" not in json.dumps(findings)
    assert {path.name for path in _output(host, "complexity").iterdir()} == {
        "detections.jsonl", "findings.json", "report.md"
    }
    assert _state(host) == before


def test_omnibus_rust_reaches_scout_graded_decomposition_report(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "omnibus")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "omnibus")
    assert report["status"] == "complete"
    assert report["summary"] == {"confirmed_omnibus": 1}
    assert report["findings"][0]["file"] == "crates/syntax-core/src/omnibus.rs"
    assert report["findings"][0]["bucket"] == "confirmed_omnibus"
    assert report["findings"][0]["recommendation"].startswith("/refactor-subsystem")
    assert "clean.rs" not in json.dumps(report["findings"])
    assert {path.name for path in _output(host, "omnibus").iterdir()} == {
        "omnibus.jsonl", "candidates.jsonl", "findings.json", "report.md", "scan.json"
    }
    assert _state(host) == before


def test_standard_gaps_rust_reports_positive_coverage_cell_and_exact_gap(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "standards")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final_json(host, "standards")
    assert report["status"] == "complete"
    standard = report["standards"][0]
    assert standard["id"] == "rust-result-match"
    assert standard["status"] == "scanned"
    assert standard["situation_sites"] == 2
    assert standard["gap_count"] == 1
    assert standard["coverage_percent"] == 50.0
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("crates/syntax-core/src/standards.rs", "unhandled_parse")
    ]
    assert {path.name for path in _output(host, "standards").iterdir()} == {
        "coverage.json", "coverage.md"
    }
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_consumer_replaces_stale_success_with_failed_malformed_state(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    first = _invoke(host, kind)
    assert first.returncode in {0, 1}, first.stdout + first.stderr
    before_text = json.dumps(_final_json(host, kind), sort_keys=True)
    service = host / "crates/syntax-core/src/clean.rs"
    service.write_text("pub fn broken( {\n", encoding="utf-8")
    before = _state(host)

    failed = _invoke(host, kind)

    assert failed.returncode == 2
    report = _final_json(host, kind)
    assert report["status"] == "failed"
    assert report["failure_kind"] in {"cargo_check_failed", "rustfmt_parse_failed"}
    assert json.dumps(report, sort_keys=True) != before_text
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_consumer_reports_missing_tool_and_cfg_as_partial_not_unsupported(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    missing = host / "missing-cargo"
    result = _invoke(host, kind, extra=("--cargo", str(missing)))
    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, kind)
    assert report["status"] == "partial"
    assert report["status"] != "unsupported"
    assert report["failure_kind"] == "cargo_tool_missing"

    source = host / "crates/syntax-core/src/clean.rs"
    source.write_text(source.read_text(encoding="utf-8") + "\n#[cfg(unix)]\npub fn selected_only() {}\n", encoding="utf-8")
    result = _invoke(host, kind)
    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, kind)
    assert report["status"] == "partial"
    assert report["failure_kind"] == "rust_cfg_ambiguity"


@pytest.mark.parametrize(
    ("case", "body", "expected"),
    [
        ("old", "echo 'cargo 1.84.1 (fixture)'\n", "cargo_tool_too_old"),
        ("broken", "echo probe-failed >&2\nexit 9\n", "cargo_tool_probe_failed"),
    ],
)
def test_shared_tool_old_and_failing_states_are_honest(
    tmp_path: Path, case: str, body: str, expected: str
) -> None:
    host = _copy_host(tmp_path, case)
    fake = _fake(host / f"cargo-{case}", body)
    result = _shared(host, "--cargo", str(fake))
    payload = json.loads(result.stdout)
    assert payload["status"] == ("partial" if case == "old" else "failed")
    assert payload["failure_kind"] == expected
    assert payload["status"] != "unsupported"


def test_missing_offline_dependency_cache_keeps_syntax_leads_as_partial(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, "offline-cache")
    fake = _fake(
        host / "cargo-offline-cache",
        """
case "${1:-}" in
  --version) echo 'cargo 1.97.1 (fixture)' ;;
  metadata) exit 0 ;;
  check) echo "error: no matching package named 'example-dependency' found" >&2; exit 101 ;;
  *) exit 0 ;;
esac
""",
    )

    result = _invoke(host, "complexity", extra=("--cargo", str(fake)))

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "complexity")
    assert (report["status"], report["failure_kind"]) == (
        "partial",
        "cargo_dependency_cache_unavailable",
    )
    assert report["verdict"] == "safe-defer-incomplete"
    assert [(row["function"], row["branch_score"]) for row in report["findings"]] == [
        ("route_invoice", 9)
    ]


def test_incomplete_project_symlink_macro_and_build_output_are_not_clean(tmp_path: Path) -> None:
    missing = _copy_host(tmp_path, "missing-project")
    (missing / "Cargo.lock").unlink()
    result = _shared(missing)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "partial"
    assert payload["failure_kind"] == "cargo_lock_missing"

    complexity = _invoke(missing, "complexity")
    assert complexity.returncode == 0, complexity.stdout + complexity.stderr
    complexity_payload = _final_json(missing, "complexity")
    assert complexity_payload["status"] == "partial"
    assert complexity_payload["verdict"] == "safe-defer-incomplete"
    assert complexity_payload["verdict"] != "no-hotspots"

    ambiguous = _copy_host(tmp_path, "ambiguous")
    os.symlink(FIXTURE / "symlink-target/External.rs", ambiguous / "crates/syntax-core/src/external.rs")
    source = ambiguous / "crates/syntax-core/src/clean.rs"
    source.write_text(
        source.read_text(encoding="utf-8")
        + "\nmacro_rules! generated_item {\n"
        + "    () => {\n"
        + "        fn hidden() {}\n"
        + "    };\n"
        + "}\n"
        + "generated_item!();\n",
        encoding="utf-8",
    )
    result = _shared(ambiguous)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "partial"
    kinds = {row["kind"] for row in payload["ambiguities"]}
    assert {"rust_macro_ambiguity", "rust_symlink_boundary"} <= kinds

    build_output = _copy_host(tmp_path, "build-output")
    (build_output / "crates/syntax-core/build.rs").write_text(
        'fn main() {\n    let _ = std::env::var("OUT_DIR");\n}\n',
        encoding="utf-8",
    )
    result = _shared(build_output)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "partial"
    assert any(
        row["kind"] == "rust_build_output_ambiguity"
        for row in payload["ambiguities"]
    )


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_exact_copied_skill_plus_shared_producer_executes_outside_repo(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    installed_skills = host / ".agents/skills"
    copied_skill = installed_skills / ADAPTERS[kind].parents[1].name
    shutil.copytree(ADAPTERS[kind].parents[1], copied_skill)
    shutil.copytree(SHARED.parents[1], installed_skills / "_rust-syntax")
    copied_adapter = copied_skill / "scripts" / ADAPTERS[kind].name
    outside = tmp_path / f"outside-{kind}"
    outside.mkdir()

    result = _invoke(host, kind, adapter=copied_adapter, cwd=outside)

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    assert _final_json(host, kind)["status"] == "complete"
    assert str(ROOT) not in copied_adapter.read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_deleting_shared_producer_fails_closed_without_consumer_rust_knowledge(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    installed_skills = host / ".agents/skills"
    copied_skill = installed_skills / ADAPTERS[kind].parents[1].name
    shutil.copytree(ADAPTERS[kind].parents[1], copied_skill)
    copied_adapter = copied_skill / "scripts" / ADAPTERS[kind].name

    result = _invoke(host, kind, adapter=copied_adapter)

    assert result.returncode == 0
    report = _final_json(host, kind)
    assert report["status"] == "partial"
    assert report["failure_kind"] == "rust_fact_producer_missing"
    source = copied_adapter.read_text(encoding="utf-8")
    assert "macro_rules" not in source
    assert "cargo metadata" not in source
    assert "_raw_string_end" not in source
    assert "cargo_check" not in source
