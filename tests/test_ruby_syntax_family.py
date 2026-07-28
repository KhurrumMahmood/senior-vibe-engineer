"""Final-outcome contract for the four Ruby A2 syntax-family consumers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ruby-syntax-family"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen F2 runtime
)
RUBY = Path.home() / ".local" / "bin" / "ruby"
BUNDLER = Path.home() / ".local" / "bin" / "bundle"
PROVIDER = ROOT / ".claude" / "skills" / "_ruby-syntax" / "ruby_syntax_facts.py"
ADAPTERS = {
    "audit": ROOT / ".claude" / "skills" / "audit-decisions" / "scripts" / "audit_ruby.py",
    "complexity": ROOT
    / ".claude"
    / "skills"
    / "find-complexity-hotspots"
    / "scripts"
    / "run_ruby.py",
    "omnibus": ROOT / ".claude" / "skills" / "find-omnibus" / "scripts" / "run_ruby.py",
    "standards": ROOT
    / ".claude"
    / "skills"
    / "find-standard-gaps"
    / "scripts"
    / "scan_coverage_ruby.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, RUBY, BUNDLER)),
    reason="Ruby 3.4.1, Bundler 2.6.2, and frozen product Python are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
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
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return state


def _output(host: Path, kind: str) -> Path:
    roots = {
        "audit": "audit-decisions",
        "complexity": "find-complexity-hotspots",
        "omnibus": "omnibus",
        "standards": "standard-gaps",
    }
    return host / "reports" / roots[kind] / "ruby-scan"


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    ruby: Path = RUBY,
    bundler: Path = BUNDLER,
    extra: tuple[str, ...] = (),
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [
        str(PYTHON),
        "-I",
        "-S",
        str(adapter or ADAPTERS[kind]),
        "--project-root",
        str(host),
        "--target",
        "." if kind == "audit" else "lib",
        "--output-dir",
        str(_output(host, kind)),
        "--ruby",
        str(ruby),
        "--bundler",
        str(bundler),
        "--test",
        "test/syntax_native_test.rb",
        "--smoke",
        "bin/ruby-syntax-smoke",
    ]
    if kind == "omnibus":
        argv.extend(["--scout-dir", str(host / "ruby-scouts")])
    if kind == "standards":
        argv.extend(["--ideas", str(host / "standards-ruby.json")])
    argv.extend(extra)
    return _run(*argv, cwd=cwd or host)


def _provider(host: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON),
        "-I",
        "-S",
        str(PROVIDER),
        "--project-root",
        str(host),
        "--target",
        ".",
        "--ruby",
        str(RUBY),
        "--bundler",
        str(BUNDLER),
        "--test",
        "test/syntax_native_test.rb",
        "--smoke",
        "bin/ruby-syntax-smoke",
        *extra,
        "--json",
        cwd=host,
    )


def _final(host: Path, kind: str) -> dict:
    names = {
        "audit": "raw-drift.json",
        "complexity": "findings.json",
        "omnibus": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def _fake_ruby(path: Path, *, version: str | None = None, exit_code: int = 9) -> Path:
    body = (
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        + (f"  printf '%s\\n' 'ruby {version} (fixture)'\n  exit 0\n" if version else f"  exit {exit_code}\n")
        + "fi\n"
        + f"exit {exit_code}\n"
    )
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _fake_bundler(path: Path, *, check_exit: int = 9) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        "  printf '%s\\n' 'Bundler version 2.6.2'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {check_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _copy_closures(tmp_path: Path) -> dict[str, Path]:
    installed = tmp_path / "installed" / ".agents" / "skills"
    installed.mkdir(parents=True)
    shutil.copytree(PROVIDER.parent, installed / "_ruby-syntax")
    copied: dict[str, Path] = {}
    for kind, source in ADAPTERS.items():
        skill = source.parents[1].name
        scripts = installed / skill / "scripts"
        scripts.mkdir(parents=True)
        destination = scripts / source.name
        shutil.copy2(source, destination)
        if kind == "audit":
            shutil.copy2(source.with_name("audit.py"), scripts / "audit.py")
        copied[kind] = destination
    return copied


def _copy_duplicate_closures(tmp_path: Path) -> dict[str, Path]:
    copied: dict[str, Path] = {}
    for kind, source in ADAPTERS.items():
        installed = tmp_path / f"duplicate-{kind}" / ".agents" / "skills"
        shutil.copytree(PROVIDER.parent, installed / "_ruby-syntax")
        scripts = installed / source.parents[1].name / "scripts"
        scripts.mkdir(parents=True)
        destination = scripts / source.name
        shutil.copy2(source, destination)
        if kind == "audit":
            shutil.copy2(source.with_name("audit.py"), scripts / "audit.py")
        copied[kind] = destination
    return copied


def _nonblank_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def test_ruby_syntax_facts_are_native_complete_role_aware_and_source_preserving(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _provider(host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert (payload["status"], payload["failure_kind"]) == ("complete", "none")
    assert payload["analyzer"] == "ruby-syntax-prism-v1"
    assert payload["source_manifest"]["preserved"] is True
    assert _state(host) == before
    assert payload["prism"]["version"] == "1.2.0"
    assert payload["bundle_check"]["returncode"] == 0
    assert payload["native"]["test"]["stdout"] == "ruby-syntax-native-test:ok\n"
    assert payload["native"]["smoke"]["stdout"] == "ruby-syntax-smoke:7\n"

    inventory = {row["file"]: row for row in payload["inventory"]}
    assert inventory["test/syntax_native_test.rb"]["role"] == "test"
    assert inventory["generated/decoy.rb"]["reason"] == "generated"
    assert inventory["vendor/decoy.rb"]["reason"] == "vendor"
    assert inventory["build/decoy.rb"]["reason"] == "build"
    assert inventory["reports/decoys/decoy.rb"]["reason"] == "report"
    assert inventory["linked-external"]["reason"] == "symlink"

    facts = {row["file"]: row for row in payload["files"]}
    assert "generated/decoy.rb" not in facts
    assert "vendor/decoy.rb" not in facts
    assert "build/decoy.rb" not in facts
    assert "reports/decoys/decoy.rb" not in facts
    complexity = next(
        row for row in facts["lib/syntax_family/complexity.rb"]["functions"] if row["name"] == "route_invoice"
    )
    decoy = next(
        row for row in facts["lib/syntax_family/complexity.rb"]["functions"] if row["name"] == "block_decoy"
    )
    assert complexity["branch_score"] == 9
    assert decoy["branch_score"] == 0
    comments = [row["text"] for row in facts["lib/syntax_family/decisions.rb"]["comments"]]
    assert any("decision:0001" in row for row in comments)
    assert not any("decision:7777" in row for row in comments)
    calls = facts["lib/syntax_family/standards.rb"]["calls"]
    assert {(row["spelling"], tuple(row["enclosures"])) for row in calls if row["spelling"] == "parse_invoice"} == {
        ("parse_invoice", ("rescue",)),
        ("parse_invoice", ()),
    }
    assert "runtime identity" in payload["claim_boundary"]
    assert "refactor authority" in payload["claim_boundary"]


def test_audit_decisions_ruby_writes_resolved_orphan_and_registry_value(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "audit")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final(host, "audit")
    assert report["status"] == "complete"
    assert report["analysis"]["ruby"]["status"] == "complete"
    references = {(row["id"], row["resolved"], row["language"]) for row in report["references"]}
    assert ("0001", True, "ruby") in references
    assert ("9999", False, "ruby") in references
    assert not any(identifier in {"7000", "6000", "5000", "4000", "7777"} for identifier, _, _ in references)
    assert {row["symptom"] for row in report["drift"]} >= {"code-ref-orphan", "unreferenced-decision"}
    assert {path.name for path in _output(host, "audit").iterdir()} == {
        "drift.md",
        "raw-drift.json",
        "registry-audit.json",
        "link-check.txt",
    }
    assert _state(host) == before


def test_complexity_ruby_reports_only_direct_method_branch_value(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "complexity")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final(host, "complexity")
    assert (report["status"], report["verdict"]) == ("complete", "measure-first")
    assert [(row["function"], row["branch_score"]) for row in report["findings"]] == [
        ("route_invoice", 9)
    ]
    assert report["findings"][0]["analyzer"] == "ruby-syntax-prism-v1"
    assert "block_decoy" not in json.dumps(report["findings"])
    assert "generated_complexity" not in json.dumps(report["findings"])
    assert {path.name for path in _output(host, "complexity").iterdir()} == {
        "detections.jsonl",
        "findings.json",
        "report.md",
    }
    assert _state(host) == before


def test_omnibus_ruby_reaches_scout_graded_decomposition_report(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "omnibus")

    assert result.returncode == 0, result.stdout + result.stderr
    report = _final(host, "omnibus")
    assert report["status"] == "complete"
    assert report["summary"] == {"confirmed_omnibus": 1}
    assert report["findings"][0]["file"] == "lib/syntax_family/omnibus.rb"
    assert report["findings"][0]["bucket"] == "confirmed_omnibus"
    assert report["findings"][0]["recommendation"].startswith("/refactor-subsystem")
    assert "clean.rb" not in json.dumps(report["findings"])
    assert "generated/decoy.rb" not in json.dumps(report["findings"])
    assert {path.name for path in _output(host, "omnibus").iterdir()} == {
        "omnibus.jsonl",
        "candidates.jsonl",
        "findings.json",
        "report.md",
        "scan.json",
    }
    assert _state(host) == before


def test_standard_gaps_ruby_reports_positive_coverage_cell_and_exact_gap(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    result = _invoke(host, "standards")

    assert result.returncode == 1, result.stdout + result.stderr
    report = _final(host, "standards")
    assert report["status"] == "complete"
    standard = report["standards"][0]
    assert (standard["id"], standard["status"]) == ("ruby-rescue-parse", "scanned")
    assert (standard["situation_sites"], standard["gap_count"], standard["coverage_percent"]) == (2, 1, 50.0)
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("lib/syntax_family/standards.rb", "unhandled_parse")
    ]
    assert {path.name for path in _output(host, "standards").iterdir()} == {
        "coverage.json",
        "coverage.md",
    }
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_consumer_valid_failed_valid_clears_stale_and_recovers(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    copied = _copy_closures(tmp_path)
    valid = _invoke(host, kind, adapter=copied[kind])
    assert valid.returncode in {0, 1}, valid.stdout + valid.stderr
    assert _final(host, kind)["status"] == "complete"

    failing = _fake_bundler(tmp_path / f"failing-bundle-{kind}")
    failed = _invoke(host, kind, adapter=copied[kind], bundler=failing)
    terminal = _final(host, kind)
    if kind == "complexity":
        assert failed.returncode == 2
        assert (terminal["status"], terminal["failure_kind"]) == (
            "partial",
            "bundle-check-failed",
        )
        assert terminal["verdict"] == "safe-defer-incomplete"
        assert terminal["findings"]
    else:
        assert failed.returncode == 1
        assert (terminal["status"], terminal["failure_kind"]) == (
            "failed",
            "bundle-check-failed",
        )
    if kind == "audit":
        assert terminal["references"] == [] and terminal["drift"] == []
    elif kind == "complexity":
        pass
    elif kind == "omnibus":
        assert terminal["findings"] == [] and terminal["missing_scouts"] == []
    else:
        assert not any(row["status"] == "scanned" for row in terminal["standards"])

    recovered = _invoke(host, kind, adapter=copied[kind])
    assert recovered.returncode in {0, 1}, recovered.stdout + recovered.stderr
    assert _final(host, kind)["status"] == "complete"


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_consumer_missing_old_and_malformed_sources_are_partial_exit_two(
    tmp_path: Path, kind: str
) -> None:
    host = _copy_host(tmp_path, kind)
    copied = _copy_closures(tmp_path)

    missing = _invoke(host, kind, adapter=copied[kind], ruby=tmp_path / "missing-ruby")
    assert missing.returncode == 2
    assert _final(host, kind)["status"] == "partial"

    old = _fake_ruby(tmp_path / f"old-ruby-{kind}", version="3.2.9")
    old_result = _invoke(host, kind, adapter=copied[kind], ruby=old)
    assert old_result.returncode == 2
    assert _final(host, kind)["failure_kind"] == "ruby-version-too-old"

    shutil.copy2(FIXTURE / "malformed" / "broken.rb", host / "lib" / "syntax_family" / "broken.rb")
    before = _state(host)
    malformed = _invoke(host, kind, adapter=copied[kind])
    assert malformed.returncode == 2, malformed.stdout + malformed.stderr
    assert _final(host, kind)["status"] == "partial"
    assert _state(host) == before


def test_complexity_incomplete_project_is_not_presented_as_no_hotspots(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, "missing-lock")
    (host / "Gemfile.lock").unlink()

    result = _invoke(host, "complexity")

    assert result.returncode == 2, result.stdout + result.stderr
    report = _final(host, "complexity")
    assert report["status"] == "partial"
    assert report["verdict"] == "safe-defer-incomplete"
    assert report["verdict"] != "no-hotspots"
    assert [(row["function"], row["branch_score"]) for row in report["findings"]] == [
        ("route_invoice", 9)
    ]


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_each_consumer_safe_defers_dynamic_dispatch_and_framework_loader(tmp_path: Path, kind: str) -> None:
    host = _copy_host(tmp_path, kind)
    copied = _copy_closures(tmp_path)
    (host / "lib" / "syntax_family" / "dynamic.rb").write_text(
        "module SyntaxFamily\n  def self.dynamic_dispatch\n    send(:parse_invoice)\n  end\nend\n",
        encoding="utf-8",
    )
    (host / "config").mkdir()
    (host / "config" / "application.rb").write_text('require "rails/all"\n', encoding="utf-8")

    result = _invoke(host, kind, adapter=copied[kind])

    assert result.returncode == 2, result.stdout + result.stderr
    report = _final(host, kind)
    assert report["status"] == "partial"
    ambiguities = report["analysis"]["ruby"]["ambiguities"]
    assert {row["kind"] for row in ambiguities} >= {
        "ruby_dynamic_dispatch_ambiguity",
        "ruby_framework_loader_ambiguity",
    }


def test_shared_producer_economics_and_deletion_fallback(tmp_path: Path) -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    adapter_text = {kind: path.read_text(encoding="utf-8") for kind, path in ADAPTERS.items()}
    test_text = Path(__file__).read_text(encoding="utf-8")
    provider_loc = _nonblank_lines(provider)
    consumer_loc = sum(_nonblank_lines(text) for text in adapter_text.values()) + _nonblank_lines(test_text)
    shared = provider_loc + consumer_loc
    duplicated = 4 * provider_loc + consumer_loc
    assert 100 * (duplicated - shared) / duplicated >= 25.0

    copied = _copy_closures(tmp_path)
    provider_bytes = PROVIDER.stat().st_size
    for _kind, adapter in copied.items():
        assert provider_bytes == (adapter.parents[2] / "_ruby-syntax" / PROVIDER.name).stat().st_size
        source = adapter.read_text(encoding="utf-8")
        assert "ruby_syntax_facts" in source
        assert "Prism::" not in source
        assert "bundle check" not in source

    host = _copy_host(tmp_path, "deleted")
    shutil.rmtree(tmp_path / "installed" / ".agents" / "skills" / "_ruby-syntax")
    result = _invoke(host, "complexity", adapter=copied["complexity"])
    assert result.returncode == 2
    report = _final(host, "complexity")
    assert (report["status"], report["failure_kind"]) == (
        "partial",
        "ruby_syntax_fact_producer_missing",
    )


def test_copied_closures_execute_outside_checkout_and_measure_warm_latency(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    copied = _copy_closures(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    shared_runs: list[float] = []
    for _ in range(3):
        started = time.monotonic()
        results = [_invoke(host, kind, adapter=adapter, cwd=outside) for kind, adapter in copied.items()]
        shared_runs.append(time.monotonic() - started)
        assert all(result.returncode in {0, 1} for result in results)

    duplicated_runs: list[float] = []
    for index in range(3):
        duplicate_root = tmp_path / f"duplicate-{index}"
        duplicate_host = _copy_host(duplicate_root)
        duplicate = _copy_duplicate_closures(duplicate_root)
        started = time.monotonic()
        results = [_invoke(duplicate_host, kind, adapter=adapter, cwd=outside) for kind, adapter in duplicate.items()]
        duplicated_runs.append(time.monotonic() - started)
        assert all(result.returncode in {0, 1} for result in results)

    assert all(_final(host, kind)["status"] == "complete" for kind in copied)
    assert statistics.median(shared_runs) > 0
    assert statistics.median(duplicated_runs) > 0
