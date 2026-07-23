"""Focused conformance for the bounded RBS-backed Ruby A3 family."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ruby-semantic-family"
HOST = FIXTURE / "host"
PYTHON = ROOT / ".venv" / "bin" / "python"
RUBY = shutil.which("ruby")
BUNDLE = shutil.which("bundle")
RBS = shutil.which("rbs")
PROVIDER = ROOT / ".claude" / "skills" / "_ruby-semantic" / "ruby_semantic_facts.py"
SCRIPTS = {
    "dormant": ROOT / ".claude" / "skills" / "find-dormant" / "scripts" / "detect_ruby_dormant.py",
    "state": ROOT / ".claude" / "skills" / "find-implicit-state" / "scripts" / "detect_ruby_state.py",
    "sweep": ROOT
    / ".claude"
    / "skills"
    / "find-incomplete-sweep"
    / "scripts"
    / "detect_ruby_incomplete_sweep.py",
    "duplication": ROOT
    / ".claude"
    / "skills"
    / "find-semantic-duplication"
    / "scripts"
    / "detect_ruby_semantic.py",
    "rename": ROOT / ".claude" / "skills" / "rename-concept" / "scripts" / "assess_ruby_rename.py",
}


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)


def _require_toolchain() -> None:
    if not (RUBY and BUNDLE and RBS):
        pytest.skip("Ruby, Bundler, and project-owned RBS command are required")
    probe = _run([RUBY, "--version"], ROOT)
    if probe.returncode or "ruby 3.4" not in probe.stdout:
        pytest.skip("frozen Ruby semantic fixture requires Ruby 3.4")


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "semantic-host"
    shutil.copytree(HOST, host, ignore=shutil.ignore_patterns("reports", ".agents"))
    return host


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and "reports" not in path.parts and ".agents" not in path.parts
    }


def _facts(host: Path, *, ruby: str | None = None, bundle: str | None = None, rbs: str | None = None) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            str(PYTHON),
            str(PROVIDER),
            "--project-root",
            str(host),
            "--target",
            "lib",
            "--output",
            "reports/ruby-semantic/facts.json",
            "--ruby",
            ruby or str(RUBY),
            "--bundler",
            bundle or str(BUNDLE),
            "--rbs",
            rbs or str(RBS),
            "--test",
            "test/semantic_test.rb",
            "--smoke",
            "bin/semantic-kit-smoke",
        ],
        host,
    )


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _consumer(host: Path, kind: str, *, facts: bool = True, verdict: Path | None = None) -> subprocess.CompletedProcess[str]:
    roots = {
        "dormant": "reports/find-dormant/ruby",
        "state": "reports/find-implicit-state/ruby",
        "sweep": "reports/find-incomplete-sweep/ruby",
        "duplication": "reports/semantic-duplication/ruby",
    }
    argv = [str(PYTHON), str(SCRIPTS[kind])]
    if kind == "rename":
        argv.extend(["LegacyInvoice", "InvoiceRecord"])
    argv.extend(["--project-root", str(host), "--target", "lib"])
    if kind == "rename":
        argv.extend(["--output", "reports/rename-concept/ruby/assessment.json"])
    else:
        argv.extend(["--output-dir", roots[kind]])
    if facts:
        argv.extend(["--facts", "reports/ruby-semantic/facts.json"])
    else:
        argv.extend(
            [
                "--ruby",
                str(RUBY),
                "--bundler",
                str(BUNDLE),
                "--rbs",
                str(RBS),
                "--test",
                "test/semantic_test.rb",
                "--smoke",
                "bin/semantic-kit-smoke",
            ]
        )
    if verdict:
        argv.extend(["--verdict", str(verdict)])
    return _run(argv, host)


def _result(host: Path, kind: str) -> dict:
    paths = {
        "dormant": host / "reports/find-dormant/ruby/findings.json",
        "state": host / "reports/find-implicit-state/ruby/findings.json",
        "sweep": host / "reports/find-incomplete-sweep/ruby/findings.json",
        "duplication": host / "reports/semantic-duplication/ruby/analysis.json",
        "rename": host / "reports/rename-concept/ruby/assessment.json",
    }
    return _payload(paths[kind])


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_ruby_rbs_semantic_family_reaches_five_distinct_read_only_outcomes(tmp_path: Path) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    before = _bytes(host)
    facts = _facts(host)
    assert facts.returncode == 0, facts.stderr
    pack = _payload(host / "reports/ruby-semantic/facts.json")
    assert pack["status"] == "complete"
    assert pack["semantic_authority"]["kind"] == "project_owned_rbs"
    assert pack["tools"]["native"]["bundle_check"]["returncode"] == 0
    assert pack["tools"]["native"]["test"]["stdout"] == "ruby-semantic-native-test:ok\n"
    assert pack["tools"]["native"]["smoke"]["stdout"] == "invoice:INV-7\n"
    assert [(row["owner"], row["name"]) for row in pack["source"]["dynamic"]] == [
        ("SemanticKit::DynamicBoundary", "public_send")
    ]

    for kind in SCRIPTS:
        result = _consumer(host, kind)
        assert result.returncode == 0, (kind, result.stderr)
    dormant = _result(host, "dormant")
    assert dormant["status"] == "complete"
    assert [(row["owner"], row["name"]) for row in dormant["candidates"]] == [
        ("SemanticKit::DormantPlan", "unused_helper")
    ]
    state = _result(host, "state")
    assert state["candidates"][0]["literals"] == ["done", "queued", "running"]
    assert state["human_verdict"]["state"] == "required"
    sweep = _result(host, "sweep")
    assert [(row["owner"], row["keyword"], row["group_size"]) for row in sweep["findings"]] == [
        ("SemanticKit::SweepOptions", "audit", 4)
    ]
    assert sweep["findings"][0]["straggler"]["line"] == 8
    duplication = _result(host, "duplication")
    assert duplication["leads"][0]["classification"] == "review_required_rbs_contract_shape_lead"
    assert all(row["direct_caller_contexts"] for row in duplication["leads"][0]["functions"])
    rename = _result(host, "rename")
    assert rename["status"] == "complete"
    assert rename["verdict"] == "HALF-APPLIED / INCOMPLETE"
    assert rename["old_source_declarations"][0]["name"] == "SemanticKit::LegacyInvoice"
    assert _bytes(host) == before


def test_ruby_semantic_verdicts_are_hash_bound_and_stale_facts_clear_findings(tmp_path: Path) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    assert _facts(host).returncode == 0
    assert _consumer(host, "state").returncode == 0
    state = _result(host, "state")
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"candidate_sha256": "not-current", "verdict": "accept"}), encoding="utf-8")
    assert _consumer(host, "state", verdict=stale).returncode == 2
    stale_result = _result(host, "state")
    assert stale_result["status"] == "partial"
    assert stale_result["human_verdict"]["state"] == "stale"
    bound = tmp_path / "bound.json"
    bound.write_text(json.dumps({"candidate_sha256": state["candidate_sha256"], "verdict": "defer"}), encoding="utf-8")
    assert _consumer(host, "state", verdict=bound).returncode == 0
    assert _result(host, "state")["human_verdict"] == {
        "candidate_sha256": state["candidate_sha256"],
        "state": "bound",
        "verdict": "defer",
    }
    assert _consumer(host, "duplication").returncode == 0
    duplication = _result(host, "duplication")
    duplication_verdict = tmp_path / "duplication-verdict.json"
    duplication_verdict.write_text(
        json.dumps({"candidate_sha256": duplication["candidate_sha256"], "verdict": "keep-separate"}),
        encoding="utf-8",
    )
    assert _consumer(host, "duplication", verdict=duplication_verdict).returncode == 0
    assert _result(host, "duplication")["human_verdict"]["state"] == "bound"
    source = host / "lib/semantic/job.rb"
    source.write_text(source.read_text(encoding="utf-8") + "\n# source changed\n", encoding="utf-8")
    assert _consumer(host, "state").returncode == 2
    cleared = _result(host, "state")
    assert cleared["status"] == "partial"
    assert cleared["candidates"] == []
    assert cleared["deferred"] == [{"reason": "ruby_semantic_fact_pack_stale"}]


def test_ruby_semantic_clean_surface_stays_complete_without_promoting_empty_claims(tmp_path: Path) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    dormant = host / "lib/semantic/dormant_plan.rb"
    dormant.write_text(dormant.read_text(encoding="utf-8").replace('def active = "active"', "def active = unused_helper"), encoding="utf-8")
    state_rbs = host / "sig/semantic_kit.rbs"
    state_rbs.write_text(state_rbs.read_text(encoding="utf-8").replace("attr_accessor phase: String", "attr_accessor phase: Symbol"), encoding="utf-8")
    sweep = host / "lib/semantic/sweep_runner.rb"
    sweep.write_text(sweep.read_text(encoding="utf-8").replace("def straggler = SweepOptions.new", "def straggler = SweepOptions.new(audit: true)"), encoding="utf-8")
    beta = host / "lib/semantic/duplicate_beta.rb"
    beta.write_text(beta.read_text(encoding="utf-8").replace('"receipt:#{amount}"', '"beta:#{amount}"'), encoding="utf-8")
    (host / "lib/semantic_kit.rb").write_text(
        (host / "lib/semantic_kit.rb").read_text(encoding="utf-8").replace('require_relative "semantic/legacy_invoice"\n', ""),
        encoding="utf-8",
    )
    (host / "lib/semantic/legacy_invoice.rb").unlink()
    assert _facts(host).returncode == 0
    for kind in SCRIPTS:
        assert _consumer(host, kind).returncode == 0
    assert _result(host, "dormant")["candidates"] == []
    assert _result(host, "state")["candidates"] == []
    assert _result(host, "sweep")["findings"] == []
    assert _result(host, "duplication")["leads"] == []
    assert _result(host, "rename")["verdict"] == "CANDIDATE COMPLETE — EXTERNAL API REVIEW REQUIRED"


@pytest.mark.parametrize("kind", ["dormant", "state", "sweep", "duplication", "rename"])
def test_ruby_semantic_consumers_replace_same_destination_on_malformed_rbs(tmp_path: Path, kind: str) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    assert _facts(host).returncode == 0
    assert _consumer(host, kind).returncode == 0
    shutil.copy2(FIXTURE / "malformed/Broken.rbs", host / "sig/broken.rbs")
    result = _consumer(host, kind, facts=False)
    assert result.returncode == 2
    payload = _result(host, kind)
    assert payload["status"] == "partial"
    assert payload.get("fact_pack_sha256") is not None
    assert "project_rbs_validation_failed" in json.dumps(payload)


@pytest.mark.parametrize(
    ("tool_case", "expected"),
    [
        ("missing", "rbs_missing"),
        ("old", "rbs_version_too_old"),
        ("failing", "project_rbs_validation_failed"),
    ],
)
def test_ruby_semantic_rbs_tool_failures_are_distinct_and_source_preserving(
    tmp_path: Path, tool_case: str, expected: str
) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    before = _bytes(host)
    if tool_case == "missing":
        rbs = str(tmp_path / "missing-rbs")
    elif tool_case == "old":
        rbs = str(_fake_tool(tmp_path / "old-rbs", "echo 'rbs 3.3.9'"))
    else:
        rbs = str(
            _fake_tool(
                tmp_path / "failing-rbs",
                "if [ \"$1\" = \"--version\" ]; then echo 'rbs 3.4.0'; exit 0; fi\necho broken >&2\nexit 9",
            )
        )
    result = _facts(host, rbs=rbs)
    assert result.returncode == 2
    payload = _payload(host / "reports/ruby-semantic/facts.json")
    assert payload["status"] == "partial"
    assert payload["failure_kind"] == expected
    assert _bytes(host) == before


@pytest.mark.parametrize(
    ("tool", "expected"),
    [("ruby", "ruby_missing"), ("bundler", "bundler_version_too_old")],
)
def test_ruby_semantic_primary_tool_boundaries_are_not_rbs_fallbacks(
    tmp_path: Path, tool: str, expected: str
) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    ruby = str(tmp_path / "missing-ruby") if tool == "ruby" else None
    bundle = str(_fake_tool(tmp_path / "old-bundle", "echo 'Bundler version 2.5.9'")) if tool == "bundler" else None
    result = _facts(host, ruby=ruby, bundle=bundle)
    assert result.returncode == 2
    payload = _payload(host / "reports/ruby-semantic/facts.json")
    assert payload["failure_kind"] == expected


def test_ruby_semantic_missing_signatures_bundle_failure_roles_symlink_and_copy_closure(tmp_path: Path) -> None:
    _require_toolchain()
    host = _host(tmp_path)
    link = host / "linked-external"
    link.symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
    assert _facts(host).returncode == 0
    pack = _payload(host / "reports/ruby-semantic/facts.json")
    roles = {row["path"]: row["role"] for row in pack["source_inventory"]}
    assert roles["generated/GeneratedDecoy.rb"] == "generated"
    assert roles["vendor/ExternalLibrary.rb"] == "vendor"
    assert roles["build/BuildDecoy.rb"] == "build"
    assert roles["linked-external"] == "symlink"
    assert "vendor/ExternalLibrary.rb" not in json.dumps(_result_after(host, "dormant"))

    no_sig = _host(tmp_path / "no-sig")
    shutil.rmtree(no_sig / "sig")
    assert _facts(no_sig).returncode == 2
    assert _payload(no_sig / "reports/ruby-semantic/facts.json")["failure_kind"] == "project_rbs_signatures_missing"
    broken_bundle = _host(tmp_path / "broken-bundle")
    (broken_bundle / "Gemfile.lock").write_text("not a lockfile\n", encoding="utf-8")
    assert _facts(broken_bundle).returncode == 1
    assert _payload(broken_bundle / "reports/ruby-semantic/facts.json")["failure_kind"] == "frozen_bundle_check_failed"

    install = tmp_path / "installed" / ".agents" / "skills"
    shutil.copytree(PROVIDER.parent, install / "_ruby-semantic")
    for kind, script in SCRIPTS.items():
        destination = install / {"dormant": "find-dormant", "state": "find-implicit-state", "sweep": "find-incomplete-sweep", "duplication": "find-semantic-duplication", "rename": "rename-concept"}[kind] / "scripts"
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, destination / script.name)
    copied = _host(tmp_path / "copied-host")
    copied_provider = install / "_ruby-semantic" / PROVIDER.name
    result = _run(
        [
            str(PYTHON),
            "-I",
            "-S",
            str(copied_provider),
            "--project-root",
            str(copied),
            "--target",
            "lib",
            "--output",
            "reports/ruby-semantic/facts.json",
            "--ruby",
            str(RUBY),
            "--bundler",
            str(BUNDLE),
            "--rbs",
            str(RBS),
            "--test",
            "test/semantic_test.rb",
            "--smoke",
            "bin/semantic-kit-smoke",
        ],
        copied,
    )
    assert result.returncode == 0, result.stderr
    copied_dormant = install / "find-dormant/scripts" / SCRIPTS["dormant"].name
    result = _run(
        [
            str(PYTHON),
            "-I",
            "-S",
            str(copied_dormant),
            "--project-root",
            str(copied),
            "--target",
            "lib",
            "--facts",
            "reports/ruby-semantic/facts.json",
            "--output-dir",
            "reports/find-dormant/ruby",
        ],
        copied,
    )
    assert result.returncode == 0, result.stderr
    assert _payload(copied / "reports/find-dormant/ruby/findings.json")["candidates"][0]["name"] == "unused_helper"


def _result_after(host: Path, kind: str) -> dict:
    result = _consumer(host, kind)
    assert result.returncode == 0, result.stderr
    return _result(host, kind)
