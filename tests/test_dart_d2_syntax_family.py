"""Final-outcome contract for Dart D2 comments and declared-policy syntax."""
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
FIXTURE = ROOT / "tests/fixtures/dart-d2-syntax"
PROVIDER = ROOT / ".claude/skills/_dart/scripts/dart_syntax_facts.py"
TOOL = ROOT / ".claude/skills/_dart/tool"
ADAPTERS = {
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_dart.py",
    "comment": ROOT / ".claude/skills/find-comment-drift/scripts/analyze_comments_dart.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_dart.py",
}
DART = Path("/opt/homebrew/bin/dart")
pytestmark = pytest.mark.skipif(not DART.is_file(), reason="Dart 3.12 SDK unavailable")


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _copy_host(tmp_path: Path, name: str = "fixture") -> Path:
    copied = tmp_path / name
    shutil.copytree(FIXTURE, copied)
    host = copied / "host"
    (host / "linked-external").symlink_to(copied / "symlink-target", target_is_directory=True)
    return host


def _state(root: Path, *, include_outputs: bool = False) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    output_roots = {
        "reports/audit-decisions",
        "reports/find-comment-drift",
        "reports/standard-gaps",
    }
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if not include_outputs and any(
            relative == output or relative.startswith(output + "/") for output in output_roots
        ):
            continue
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _common(host: Path) -> list[str]:
    return [
        "--project-root",
        str(host),
        "--target",
        ".",
        "--dart",
        str(DART),
        "--native-test",
        "tool/d2_native_test.dart",
        "--smoke",
        "bin/d2_smoke.dart",
        "--smoke-stdout",
        "dart-d2:125:ok\n",
    ]


def _output(host: Path, kind: str) -> Path:
    roots = {
        "audit": "audit-decisions",
        "comment": "find-comment-drift",
        "standards": "standard-gaps",
    }
    return host / "reports" / roots[kind] / "dart-scan"


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    cwd: Path | None = None,
    extra: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        "-I",
        "-S",
        str(adapter or ADAPTERS[kind]),
        *_common(host),
        "--output-dir",
        str(_output(host, kind)),
    ]
    if kind == "standards":
        argv.extend(["--ideas", str(host / "standards-dart.json")])
    argv.extend(extra)
    return _run(*argv, cwd=cwd or host)


def _final(host: Path, kind: str) -> dict:
    names = {
        "audit": "raw-drift.json",
        "comment": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def _provider(host: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        "-I",
        "-S",
        str(PROVIDER),
        *_common(host),
        *extra,
        "--json",
        cwd=host,
    )


def _replace(path: Path, old: str, new: str, *, count: int = -1) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def _manifest(paths: list[Path], base: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    for path in sorted(paths):
        content = path.read_bytes()
        relative = path.relative_to(base).as_posix()
        digest.update(relative.encode() + b"\0" + hashlib.sha256(content).hexdigest().encode() + b"\n")
        total += len(content)
    return digest.hexdigest(), total


def test_dart_locked_public_analyzer_facts_roles_native_and_zero_write(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host, include_outputs=True)
    result = _provider(host)
    assert result.returncode == 0, result.stdout + result.stderr
    facts = json.loads(result.stdout)
    assert facts["status"] == "complete"
    assert facts["analyzer_package"] == "14.1.0"
    assert facts["tools"]["dart"]["version"] == "3.12.2"
    assert facts["source_manifest"]["preserved"] is True
    assert _state(host, include_outputs=True) == before
    assert not (host / ".dart_tool").exists()
    assert not (host / "pubspec.lock").exists()
    assert all(
        facts["native"][name]["passed"]
        for name in ("dart_analyze", "dart_format", "direct_test", "smoke")
    )
    native_argv = [row["argv"] for row in facts["native"].values()]
    assert not any(argv[1] in {"pub", "run", "test"} for argv in native_argv)
    setup = facts["tool_package"]["setup"]
    assert setup["argv"][1:] == ["pub", "get", "--offline", "--enforce-lockfile"]
    assert facts["tool_package"]["setup_mode"] == "offline-enforce-lockfile"

    inventory = {row["file"]: row for row in facts["inventory"]}
    assert inventory["lib/d2_cases.dart"]["role"] == "source"
    assert inventory["test/excluded_test.dart"]["role"] == "test"
    assert inventory["example/excluded_example.dart"]["role"] == "example"
    assert inventory["generated/excluded.g.dart"]["role"] == "generated"
    assert inventory["vendor/excluded_vendor.dart"]["role"] == "vendor"
    assert inventory["build/excluded_build.dart"]["role"] == "build"
    assert inventory["reports/seed/excluded_report.dart"]["role"] == "build"
    assert inventory["linked-external"]["role"] == "symlink"
    selected = {row["file"]: row for row in facts["files"]}
    assert set(selected) == {"bin/d2_smoke.dart", "lib/d2_cases.dart"}
    source = selected["lib/d2_cases.dart"]
    comment_ids = {
        match
        for comment in source["comments"]
        for match in __import__("re").findall(r"decision:(\d{4})", comment["text"])
    }
    assert {"0001", "9999"} <= comment_ids
    assert not comment_ids & {"7000", "7001", "7002", "7003", "7004"}
    assert {row["form"] for row in source["comments"] if "decision:0001" in row["text"]} == {
        "line",
        "block",
        "doc",
    }
    assert [row["name"] for row in source["functions"]] == ["invoiceRate", "matchingRate"]
    parse_calls = [row for row in source["calls"] if row["spelling"] == "parseInvoice"]
    assert [row["in_try"] for row in parse_calls] == [True, False]
    assert "Flutter" in facts["claim_boundary"]


def test_dart_tool_package_lock_and_public_api_surface_are_exact(tmp_path: Path) -> None:
    pubspec = (TOOL / "pubspec.yaml").read_text(encoding="utf-8")
    lock = (TOOL / "pubspec.lock").read_text(encoding="utf-8")
    source = (TOOL / "bin/dart_syntax_facts.dart").read_text(encoding="utf-8")
    assert "analyzer: 14.1.0" in pubspec
    assert 'sdk: ">=3.12.0 <3.13.0"' in pubspec
    assert 'version: "14.1.0"' in lock
    assert 'dependency: "direct main"' in lock
    assert "package:analyzer/src/" not in source
    assert "package:analyzer/dart/analysis/utilities.dart" in source

    copied = tmp_path / "tool"
    shutil.copytree(TOOL, copied)
    setup = _run(
        str(DART),
        "pub",
        "get",
        "--offline",
        "--enforce-lockfile",
        cwd=copied,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    assert (copied / ".dart_tool/package_config.json").is_file()
    assert not (TOOL / ".dart_tool").exists()


def test_audit_decisions_dart_final_value_strings_exclusions_and_clean(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    result = _invoke(host, "audit")
    assert result.returncode == 1, result.stdout + result.stderr
    report = _final(host, "audit")
    assert report["status"] == "complete"
    references = {(row["id"], row["resolved"], row["comment_form"]) for row in report["references"]}
    assert ("9999", False, "line") in references
    assert {(identifier, form) for identifier, resolved, form in references if resolved} >= {
        ("0001", "line"),
        ("0001", "block"),
        ("0001", "doc"),
    }
    assert not {"6000", "6001", "6002", "6003", "6004", "6005", "6006", "7000", "7001", "7002", "7003", "7004"} & {
        row["id"] for row in report["references"]
    }
    assert {row["symptom"] for row in report["drift"]} >= {
        "code-ref-orphan",
        "unreferenced-decision",
    }
    assert {path.name for path in _output(host, "audit").iterdir()} == {
        "drift.md",
        "raw-drift.json",
        "registry-audit.json",
        "link-check.txt",
    }
    assert _state(host) == before

    source = host / "lib/d2_cases.dart"
    _replace(source, "decision:9999", "decision:0002", count=1)
    clean = _invoke(host, "audit")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_report = _final(host, "audit")
    assert clean_report["status"] == "complete"
    assert clean_report["drift"] == []


def test_find_comment_drift_dart_final_value_clean_and_must_not_fire(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    result = _invoke(host, "comment")
    assert result.returncode == 0, result.stdout + result.stderr
    report = _final(host, "comment")
    assert report["status"] == "complete"
    assert report["outcome"] == "advisory-findings"
    assert [(row["file"], row["function"]) for row in report["findings"]] == [
        ("lib/d2_cases.dart", "invoiceRate")
    ]
    assert report["findings"][0]["claimed_value"] == 10.0
    assert report["findings"][0]["returned_literal"] == 125
    serialized = json.dumps(report["findings"])
    for decoy in (
        "matchingRate",
        "computedRate",
        "closureRate",
        "detachedRate",
        "mixinRate",
        "extensionRate",
        "localRate",
        "excluded",
    ):
        assert decoy not in serialized
    assert {path.name for path in _output(host, "comment").iterdir()} == {
        "detections.jsonl",
        "report.md",
        "findings.json",
        "scan.json",
    }
    assert _state(host) == before

    _replace(
        host / "lib/d2_cases.dart",
        "Returns a 10 percent rate based on the invoice amount.",
        "Returns the fixed 125 rate.",
        count=1,
    )
    clean = _invoke(host, "comment")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_report = _final(host, "comment")
    assert clean_report["outcome"] == "clean-within-complete"
    assert clean_report["findings"] == []


def test_find_standard_gaps_dart_final_value_clean_direct_body_and_invalid(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    result = _invoke(host, "standards")
    assert result.returncode == 1, result.stdout + result.stderr
    report = _final(host, "standards")
    assert report["status"] == "complete"
    row = report["standards"][0]
    assert (row["status"], row["situation_sites"], row["gap_count"], row["coverage_percent"]) == (
        "scanned",
        2,
        1,
        50.0,
    )
    assert row["gaps"][0]["file"] == "lib/d2_cases.dart"
    assert {path.name for path in _output(host, "standards").iterdir()} == {
        "coverage.md",
        "coverage.json",
        "scan.json",
    }
    assert _state(host) == before

    source = host / "lib/d2_cases.dart"
    _replace(
        source,
        "  parseInvoice('gap');",
        "  try {\n    parseInvoice('gap');\n  } catch (_) {}",
    )
    clean = _invoke(host, "standards")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_row = _final(host, "standards")["standards"][0]
    assert (clean_row["situation_sites"], clean_row["gap_count"], clean_row["coverage_percent"]) == (
        2,
        0,
        100.0,
    )

    _replace(
        source,
        "  final tearOff = parseInvoice;",
        "  try {\n    final callback = () {\n      parseInvoice('nested');\n    };\n    callback();\n  } catch (_) {}\n\n  final tearOff = parseInvoice;",
    )
    nested = _invoke(host, "standards")
    assert nested.returncode == 1, nested.stdout + nested.stderr
    nested_row = _final(host, "standards")["standards"][0]
    assert (nested_row["situation_sites"], nested_row["gap_count"]) == (3, 1)
    assert nested_row["gaps"][0]["in_try"] is False

    invalid = host / "invalid-standards.json"
    invalid.write_text('{"ideas": [', encoding="utf-8")
    failed = _invoke(
        host,
        "standards",
        extra=("--ideas", str(invalid), "--dart", str(host / "missing-dart")),
    )
    assert failed.returncode == 2
    invalid_report = _final(host, "standards")
    assert (invalid_report["status"], invalid_report["failure_kind"]) == (
        "failed",
        "invalid_standards",
    )
    assert invalid_report["standards"] == []


@pytest.mark.parametrize("kind", ["audit", "comment", "standards"])
def test_dart_d2_same_destination_valid_failed_valid_clears_stale(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path)
    valid = _invoke(host, kind)
    assert valid.returncode in {0, 1}, valid.stdout + valid.stderr
    initial = _final(host, kind)
    assert initial["status"] == "complete"

    source = host / "lib/d2_cases.dart"
    original = source.read_bytes()
    source.write_bytes(original + b"\nvoid malformed( {\n")
    failed = _invoke(host, kind)
    assert failed.returncode == 2, failed.stdout + failed.stderr
    terminal = _final(host, kind)
    assert (terminal["status"], terminal["failure_kind"]) == (
        "failed",
        "dart_parse_diagnostics",
    )
    if kind == "audit":
        assert terminal["references"] == [] and terminal["drift"] == []
    elif kind == "comment":
        assert terminal["findings"] == []
    else:
        assert not any(row["status"] == "scanned" for row in terminal["standards"])

    source.write_bytes(original)
    recovered = _invoke(host, kind)
    assert recovered.returncode in {0, 1}, recovered.stdout + recovered.stderr
    assert _final(host, kind)["status"] == "complete"


def test_dart_dependency_tool_and_malformed_source_boundaries(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    empty_cache = tmp_path / "empty-pub-cache"
    empty_cache.mkdir()
    cold = _provider(host, "--pub-cache", str(empty_cache))
    assert cold.returncode == 2
    cold_facts = json.loads(cold.stdout)
    assert (cold_facts["status"], cold_facts["failure_kind"]) == (
        "partial",
        "tool_dependency_unavailable",
    )
    assert not (host / ".dart_tool").exists()

    missing_package = _provider(host, "--tool-root", str(tmp_path / "missing-tool"))
    assert missing_package.returncode == 2
    missing_facts = json.loads(missing_package.stdout)
    assert (missing_facts["status"], missing_facts["failure_kind"]) == (
        "partial",
        "tool_dependency_unavailable",
    )

    broken_dart = tmp_path / "broken-dart"
    broken_dart.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    broken_dart.chmod(0o755)
    broken = _provider(host, "--dart", str(broken_dart))
    assert broken.returncode == 2
    broken_facts = json.loads(broken.stdout)
    assert (broken_facts["status"], broken_facts["failure_kind"]) == (
        "failed",
        "dart_tool_probe_failed",
    )

    shutil.copy2(FIXTURE / "malformed.dart", host / "lib/malformed.dart")
    malformed = _provider(host)
    assert malformed.returncode == 2
    malformed_facts = json.loads(malformed.stdout)
    assert (malformed_facts["status"], malformed_facts["failure_kind"]) == (
        "failed",
        "dart_parse_diagnostics",
    )


@pytest.mark.parametrize("kind", ["audit", "comment", "standards"])
def test_dart_d2_rejects_symlinked_report_roots_before_writes(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path)
    external = tmp_path / "external-output"
    external.mkdir()
    report_names = {
        "audit": "audit-decisions",
        "comment": "find-comment-drift",
        "standards": "standard-gaps",
    }
    configured = host / "reports" / report_names[kind]
    configured.parent.mkdir(exist_ok=True)
    configured.symlink_to(external, target_is_directory=True)
    result = _invoke(host, kind)
    assert result.returncode == 2
    assert not list(external.iterdir())


@pytest.mark.parametrize("kind", ["audit", "comment", "standards"])
def test_dart_d2_copied_closure_runs_outside_checkout(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path, f"fixture-{kind}")
    installed = tmp_path / "installed" / ".agents" / "skills"
    installed.mkdir(parents=True)
    skill_names = {
        "audit": "audit-decisions",
        "comment": "find-comment-drift",
        "standards": "find-standard-gaps",
    }
    skill_name = skill_names[kind]
    shutil.copytree(ROOT / ".claude/skills" / skill_name, installed / skill_name)
    shutil.copytree(ROOT / ".claude/skills/_dart", installed / "_dart")
    copied_adapter = installed / skill_name / "scripts" / ADAPTERS[kind].name
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    result = _invoke(host, kind, adapter=copied_adapter, cwd=unrelated)
    assert result.returncode in {0, 1}, result.stdout + result.stderr
    report = _final(host, kind)
    assert report["status"] == "complete"
    assert report["analysis"]["dart"]["source_manifest"]["preserved"] is True


def test_dart_d2_owned_closure_and_fixture_hashes_are_frozen() -> None:
    owned = [
        PROVIDER,
        TOOL / "pubspec.yaml",
        TOOL / "pubspec.lock",
        TOOL / "bin/dart_syntax_facts.dart",
        *ADAPTERS.values(),
    ]
    fixture_files = [path for path in FIXTURE.rglob("*") if path.is_file()]
    assert _manifest(owned, ROOT) == (
        "8bb34a1c1c57a08a69ed5cd38fa3dc5f3d78c4f23e9f71507435796bae104944",
        53682,
    )
    assert _manifest(fixture_files, FIXTURE) == (
        "f122c7d992591cdc09bdd913e96ffc225b9484e42b942d4d386795b7264d2b14",
        3968,
    )
