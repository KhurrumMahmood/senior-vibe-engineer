"""Final-outcome contract for the bounded four-skill C17 syntax cohort."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/c-syntax-cohort"
SHARED = ROOT / ".claude/skills/_c-syntax/scripts/c_syntax_facts.py"
ADAPTERS = {
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_c.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_c.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_c.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_c.py",
}
CLANG = shutil.which("clang")
MAKE = shutil.which("make")


def _clang_21() -> bool:
    if CLANG is None:
        return False
    result = subprocess.run(
        [CLANG, "--version"], capture_output=True, text=True, check=False
    )
    match = re.search(r"(?:Apple )?clang version (\d+)\.(\d+)\.(\d+)", result.stdout)
    return bool(match and tuple(map(int, match.groups())) >= (21, 0, 0))


pytestmark = pytest.mark.skipif(
    not (_clang_21() and MAKE), reason="Clang 21+ and Make are required"
)


def _run(*argv: str, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    native = _run(
        MAKE or "make", "clean", "test", "compile-db", f"CC={CLANG}", cwd=host
    )
    assert native.returncode == 0, native.stdout + native.stderr
    smoke = _run(str(host / ".native-build/c-syntax-smoke"), cwd=host)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "c-syntax:7\n"
    return host


def _state(root: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"reports", ".native-build"}:
            continue
        if path.is_symlink():
            state[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative.as_posix()] = (
                "file", hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return state


def _shared(host: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(SHARED),
        "--project-root",
        str(host),
        "--target",
        ".",
        "--clang",
        CLANG or "clang",
        *extra,
        "--json",
        cwd=host,
    )


def _output(host: Path, kind: str) -> Path:
    roots = {
        "audit": "audit-decisions",
        "complexity": "find-complexity-hotspots",
        "omnibus": "omnibus",
        "standards": "standard-gaps",
    }
    return host / "reports" / roots[kind] / "c-scan"


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    target: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        "-I",
        "-S",
        str(adapter or ADAPTERS[kind]),
        "--project-root",
        str(host),
        "--target",
        target or ("." if kind == "audit" else "src"),
        "--output-dir",
        str(_output(host, kind)),
        "--clang",
        CLANG or "clang",
    ]
    if kind == "standards":
        argv.extend(["--ideas", str(host / "standards-c.json")])
    if kind == "omnibus":
        argv.extend(["--scout-dir", str(host / "c-scouts")])
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


def test_shared_c_facts_use_compile_db_raw_tokens_ast_and_preserve_source(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _shared(host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "complete"
    assert payload["analyzer"] == "clang-c17-raw-tokens+ast-json"
    assert payload["compile_database"]["state"] == "valid-current-complete-c-mode"
    assert payload["compile_database"]["entries"] == 6
    assert payload["source_manifest"]["preserved"] is True
    assert _state(host) == before
    inventory = {row["file"]: row["role"] for row in payload["inventory"]}
    assert inventory["src/clean.c"] == "source"
    assert inventory["tests/excluded_test.c"] == "test"
    assert inventory["generated/Generated.c"] == "generated"
    assert inventory["vendor/Vendor.c"] == "vendor"

    files = {row["file"]: row for row in payload["files"]}
    route = next(
        row for row in files["src/complexity.c"]["functions"]
        if row["name"] == "route_invoice"
    )
    wrapper = next(
        row for row in files["src/complexity.c"]["functions"]
        if row["name"] == "route_invoice_wrapper"
    )
    assert route["branch_score"] == 8
    assert route["macro_nodes_omitted"] > 0
    assert wrapper["branch_score"] == 0
    comments = [
        comment["text"]
        for file in payload["files"]
        for comment in file["comments"]
    ]
    assert any("decision:0001" in text for text in comments)
    assert any("decision:9999" in text for text in comments)
    assert not any("decision:7777" in text or "decision:8888" in text for text in comments)
    calls = [
        call for call in files["src/standards.c"]["calls"]
        if call["spelling"] == "parse_invoice"
    ]
    assert len(calls) == 2
    assert sorted("if" in call["enclosures"] for call in calls) == [False, True]


def test_c_complexity_accepts_standard_external_compilation_database(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    original = json.loads((host / "compile_commands.json").read_text(encoding="utf-8"))
    source = (host / "src/complexity.c").resolve()
    row = next(item for item in original if Path(item["file"]) == source)
    external = tmp_path / "external"
    external.mkdir()
    database = external / "compile_commands.json"
    database.write_text(
        json.dumps([{
            "directory": str(external),
            "command": shlex.join(row["arguments"]),
            "file": str(source),
            "output": "complexity.o",
        }]),
        encoding="utf-8",
    )
    output = external / "artifacts"

    result = _run(
        sys.executable, "-I", "-S", str(ADAPTERS["complexity"]),
        "--project-root", str(host), "--target", "src/complexity.c",
        "--output-dir", str(output), "--compile-database", str(database),
        "--clang", CLANG or "clang", "--no-host-write", cwd=host,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((output / "findings.json").read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert [(row["function"], row["branch_score"]) for row in payload["findings"]] == [
        ("route_invoice", 8)
    ]
    assert payload["analysis"]["c"]["compile_database"]["path"] == str(database)
    assert _state(host) == before


def test_audit_decisions_c_reaches_real_resolved_and_orphan_comment_refs(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "audit")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final_json(host, "audit")
    assert report["status"] == "complete"
    references = {(row["id"], row["resolved"], row["language"]) for row in report["references"]}
    assert ("0001", True, "c") in references
    assert ("9999", False, "c") in references
    assert not any(identifier in {"5000", "6000", "7000", "7777", "8888"} for identifier, _, _ in references)
    assert {row["symptom"] for row in report["drift"]} >= {
        "code-ref-orphan", "unreferenced-decision"
    }
    assert {path.name for path in _output(host, "audit").iterdir()} == {
        "drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt"
    }
    assert _state(host) == before


def test_complexity_c_reports_direct_body_score_without_macro_or_callee_inflation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "complexity")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "complexity")
    assert report["status"] == "complete"
    assert report["verdict"] == "measure-first"
    assert [(row["function"], row["branch_score"]) for row in report["findings"]] == [
        ("route_invoice", 8)
    ]
    assert report["findings"][0]["evidence_scope"] == "direct-body-syntax-only"
    assert "route_invoice_wrapper" not in json.dumps(report["findings"])
    assert _state(host) == before


def test_complexity_c_clean_target_names_a_bounded_clean_result(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)

    result = _invoke(host, "complexity", target="src/clean.c")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "complexity")
    assert report["status"] == "complete"
    assert report["verdict"] == "no-hotspots"
    assert report["findings"] == []


def test_omnibus_c_requires_and_carries_explicit_scout_verdict(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "omnibus")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final_json(host, "omnibus")
    assert report["status"] == "complete"
    assert report["summary"] == {"confirmed_omnibus": 1}
    finding = report["findings"][0]
    assert finding["file"] == "src/omnibus.c"
    assert finding["bucket"] == "confirmed_omnibus"
    assert finding["scout_verdict"] == "explicit"
    assert finding["recommendation"].startswith("/refactor-subsystem")
    assert "clean.c" not in json.dumps(report["findings"])
    assert _state(host) == before


def test_standard_gaps_c_reports_configured_two_site_one_gap_census(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "standards")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final_json(host, "standards")
    assert report["status"] == "complete"
    standard = report["standards"][0]
    assert standard["id"] == "c-parse-if"
    assert standard["status"] == "scanned"
    assert standard["situation_sites"] == 2
    assert standard["gap_count"] == 1
    assert standard["coverage_percent"] == 50.0
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("src/standards.c", "unhandled_parse")
    ]
    assert standard["claim_boundary"] == "direct-call spelling and if enclosure syntax only"
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_c_consumer_replaces_stale_success_with_malformed_failure(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    first = _invoke(host, kind)
    assert first.returncode in {0, 1}, first.stdout + first.stderr
    before_text = json.dumps(_final_json(host, kind), sort_keys=True)
    (host / "src/clean.c").write_text("int broken( {\n", encoding="utf-8")
    refreshed = _run(MAKE or "make", "compile-db", f"CC={CLANG}", cwd=host)
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    before = _state(host)

    failed = _invoke(host, kind)

    assert failed.returncode == 2
    report = _final_json(host, kind)
    assert report["status"] == "failed"
    assert report["failure_kind"] in {"clang_dependency_failed", "clang_ast_failed"}
    assert json.dumps(report, sort_keys=True) != before_text
    assert _state(host) == before


@pytest.mark.parametrize(
    ("case", "body", "expected_status", "expected_kind"),
    [
        ("old", "echo 'clang version 20.0.0'\n", "unsupported", "clang_version_too_old"),
        ("broken", "echo probe-failed >&2\nexit 9\n", "failed", "clang_version_probe_failed"),
    ],
)
def test_c_tool_states_are_explicit(
    tmp_path: Path,
    case: str,
    body: str,
    expected_status: str,
    expected_kind: str,
) -> None:
    host = _copy_host(tmp_path, case)
    fake = _fake(host / f"clang-{case}", body)

    result = _shared(host, "--clang", str(fake))

    payload = json.loads(result.stdout)
    assert payload["status"] == expected_status
    assert payload["failure_kind"] == expected_kind
    assert result.returncode == (2 if expected_status == "failed" else 0)


def test_missing_c_tool_is_unsupported_not_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)

    result = _shared(host, "--clang", str(host / "missing-clang"))

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == "clang_tool_missing"


def test_c_compile_database_malformed_incomplete_and_stale_states_are_not_clean(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    database = host / "compile_commands.json"
    valid = database.read_text(encoding="utf-8")

    database.write_text("{", encoding="utf-8")
    malformed = _shared(host)
    malformed_payload = json.loads(malformed.stdout)
    assert malformed.returncode == 2
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "compile_database_malformed"

    database.write_text(json.dumps(json.loads(valid)[:1]), encoding="utf-8")
    incomplete = _shared(host)
    incomplete_payload = json.loads(incomplete.stdout)
    assert incomplete.returncode == 0
    assert incomplete_payload["status"] == "partial"
    assert incomplete_payload["failure_kind"] == "compile_database_incomplete"

    database.write_text(valid, encoding="utf-8")
    newer = database.stat().st_mtime_ns + 2_000_000_000
    os.utime(host / "src/clean.c", ns=(newer, newer))
    stale = _shared(host)
    stale_payload = json.loads(stale.stdout)
    assert stale.returncode == 0
    assert stale_payload["status"] == "partial"
    assert stale_payload["failure_kind"] == "compile_database_stale"


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_exact_copied_skill_plus_c_fact_producer_executes_outside_repo(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    installed = host / ".agents/skills"
    copied_skill = installed / ADAPTERS[kind].parents[1].name
    shutil.copytree(ADAPTERS[kind].parents[1], copied_skill)
    shutil.copytree(SHARED.parents[1], installed / "_c-syntax")
    copied_adapter = copied_skill / "scripts" / ADAPTERS[kind].name
    outside = tmp_path / f"outside-{kind}"
    outside.mkdir()

    result = _invoke(host, kind, adapter=copied_adapter, cwd=outside)

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    assert _final_json(host, kind)["status"] == "complete"
    assert str(ROOT) not in copied_adapter.read_text(encoding="utf-8")
