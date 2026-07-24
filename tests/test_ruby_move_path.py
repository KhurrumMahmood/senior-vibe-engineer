"""Final mutation-boundary proof for the bounded Ruby move-path cohort."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/move-path/scripts/ruby_module_move.py"
FIXTURE = ROOT / "tests/fixtures/ruby-pilot/host"
RUBY = Path("/opt/homebrew/opt/ruby/bin/ruby")
BUNDLER = Path("/opt/homebrew/opt/ruby/bin/bundle")

pytestmark = pytest.mark.skipif(
    not RUBY.is_file() or not BUNDLER.is_file(),
    reason="Ruby 3.4.1 and Bundler 2.6.2 are required for the frozen cohort",
)


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _plan(
    host: Path,
    *,
    ruby: Path = RUBY,
    bundler: Path = BUNDLER,
    source: str = "lib/billing/invoice_registry.rb",
    destination: str = "lib/invoicing/invoice_registry.rb",
) -> Path:
    plan = host / "ruby-move.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [
                    {"from": source, "to": destination, "mode": "file"}
                ],
                "rewrite": {"code_imports": "update-ruby"},
                "ruby": {
                    "binary": str(ruby),
                    "bundler": str(bundler),
                    "constant_before": "Billing::InvoiceRegistry",
                    "constant_after": "Invoicing::InvoiceRegistry",
                    "native_test": "test/invoice_service_test.rb",
                    "native_test_expected_stdout": "native-test:ok\n",
                    "smoke": "bin/ruby-pilot-smoke",
                    "smoke_expected_stdout": "invoice:INV-42:125\n",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan


def _tree(host: Path) -> dict[str, tuple[str, bytes | str, int]]:
    rows: dict[str, tuple[str, bytes | str, int]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts[:2] == ("reports", "move-path"):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("link", os.readlink(path), 0)
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
    return rows


def _invoke(
    host: Path,
    plan: Path,
    mode: str,
    *,
    script: Path = SCRIPT,
    cwd: Path | None = None,
    evidence: Path | None = None,
    approval: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    report_dir = host / "reports/move-path"
    argv = [
        str(Path(sys.executable).resolve()),
        "-I",
        "-S",
        str(script),
        "--plan",
        str(plan),
        "--project-root",
        str(host),
        "--report-dir",
        str(report_dir),
        f"--{mode}",
        "--json",
    ]
    if evidence is not None:
        argv.extend(["--evidence", str(evidence)])
    if approval is not None:
        argv.extend(["--approve-evidence-sha256", approval])
    result = subprocess.run(
        argv,
        cwd=cwd or host,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    report_path = report_dir / "report.json"
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    return result, report, report_dir


def _preview(
    host: Path,
    plan: Path,
    *,
    script: Path = SCRIPT,
    cwd: Path | None = None,
) -> tuple[dict, Path, dict]:
    result, report, report_dir = _invoke(
        host, plan, "dry-run", script=script, cwd=cwd
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert report["ruby"]["evidence_sha256"] == evidence["evidence_sha256"]
    return report, evidence_path, evidence


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_ruby_preview_authorized_apply_check_exact_changes_and_native_outcome(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)
    protected = {
        path: hashlib.sha256((host / path).read_bytes()).hexdigest()
        for path in (
            "Gemfile.lock",
            "ruby_pilot.gemspec",
            "lib/billing/dynamic_features.rb",
            "test/invoice_service_test.rb",
            "bin/ruby-pilot-smoke",
            "generated/GeneratedInvoice.rb",
            "vendor/VendorInvoice.rb",
            "build/BuildSentinel.rb",
        )
    }

    preview, evidence_path, evidence = _preview(host, plan)

    ruby = preview["ruby"]
    assert ruby["status"] == "complete"
    assert ruby["mode"] == "dry-run"
    assert ruby["source_tree_sha256"] == evidence["source_tree_sha256"]
    assert _tree(host) == before
    assert {
        (row["file_before"], row["kind"], row["old"], row["new"])
        for row in ruby["exact_changes"]
    } == {
        (
            "lib/billing/invoice_registry.rb",
            "ruby_module_namespace",
            "Billing",
            "Invoicing",
        ),
        (
            "lib/billing/invoice_service.rb",
            "ruby_require_relative",
            "invoice_registry",
            "../invoicing/invoice_registry",
        ),
        (
            "lib/billing/invoice_service.rb",
            "ruby_constant_reference",
            "InvoiceRegistry",
            "Invoicing::InvoiceRegistry",
        ),
    }
    assert ruby["native_preflight"]["bundle_check"]["passed"] is True
    assert all(
        row["passed"] for row in ruby["native_preflight"]["syntax_checks"]
    )
    assert ruby["native_preflight"]["native_test"]["stdout"] == "native-test:ok\n"
    assert ruby["native_preflight"]["smoke"]["stdout"] == "invoice:INV-42:125\n"

    result, applied, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert applied["ruby"]["status"] == "complete"
    assert applied["ruby"]["rolled_back"] is False
    assert applied["ruby"]["exact_after_tree"]["passed"] is True
    assert (
        applied["ruby"]["exact_after_tree"]["actual_fingerprint"]
        == evidence["expected_after_tree_sha256"]
    )
    assert not (host / "lib/billing/invoice_registry.rb").exists()
    moved = host / "lib/invoicing/invoice_registry.rb"
    assert moved.is_file()
    assert "module Invoicing" in moved.read_text(encoding="utf-8")
    consumer = (host / "lib/billing/invoice_service.rb").read_text(encoding="utf-8")
    assert 'require_relative "../invoicing/invoice_registry"' in consumer
    assert "Invoicing::InvoiceRegistry.new" in consumer
    assert all(
        hashlib.sha256((host / path).read_bytes()).hexdigest() == digest
        for path, digest in protected.items()
    )

    checked, check_report, _ = _invoke(
        host, plan, "check", evidence=evidence_path
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert check_report["ruby"]["status"] == "complete"
    assert check_report["ruby"]["old_identity_remaining"] == []
    assert check_report["ruby"]["further_edits"] == []


def test_ruby_moved_referrer_and_direct_test_require_relative_impacts_are_exact(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    registry = host / "lib/billing/invoice_registry.rb"
    registry.write_text(
        'require_relative "registry_support"\n\n' + registry.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write(
        host / "lib/billing/registry_support.rb",
        "module Billing\n  module RegistrySupport\n  end\nend\n",
    )
    _write(
        host / "test/registry_direct_test.rb",
        'require_relative "../lib/billing/invoice_registry"\n'
        "Billing::InvoiceRegistry.new\n",
    )
    plan = _plan(host)

    preview, evidence_path, evidence = _preview(host, plan)
    changes = {
        (row["file_before"], row["kind"], row["old"], row["new"])
        for row in preview["ruby"]["exact_changes"]
    }
    assert (
        "lib/billing/invoice_registry.rb",
        "ruby_require_relative",
        "registry_support",
        "../billing/registry_support",
    ) in changes
    assert (
        "test/registry_direct_test.rb",
        "ruby_require_relative",
        "../lib/billing/invoice_registry",
        "../lib/invoicing/invoice_registry",
    ) in changes
    assert (
        "test/registry_direct_test.rb",
        "ruby_constant_reference",
        "Billing::InvoiceRegistry",
        "Invoicing::InvoiceRegistry",
    ) in changes

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["ruby"]["exact_after_tree"]["passed"] is True
    moved = (host / "lib/invoicing/invoice_registry.rb").read_text(encoding="utf-8")
    assert 'require_relative "../billing/registry_support"' in moved


def test_ruby_complete_failed_complete_lifecycle_clears_mutation_authority(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    first, evidence_path, _ = _preview(host, plan)
    assert first["ruby"]["status"] == "complete"

    source = host / "lib/billing/invoice_registry.rb"
    original = source.read_bytes()
    source.write_text("module Broken\n  def call(\nend\n", encoding="utf-8")
    failed, report, _ = _invoke(host, plan, "dry-run")
    assert failed.returncode == 2
    assert report["ruby"]["status"] == "failed"
    assert report["ruby"]["failure_kind"] == "ruby_syntax_failed"
    assert not evidence_path.exists()

    source.write_bytes(original)
    recovered, recovered_evidence, _ = _preview(host, plan)
    assert recovered["ruby"]["status"] == "complete"
    assert recovered_evidence.is_file()


@pytest.mark.parametrize(
    ("boundary", "expected_kind"),
    [
        ("dynamic", "ruby_dynamic_load_identity"),
        ("autoload", "ruby_autoload_identity"),
        ("reflection", "ruby_reflective_constant_identity"),
        ("reopening", "ruby_constant_reopened"),
        ("framework", "ruby_framework_loader_unsupported"),
        ("symlink", "ruby_symlink_boundary"),
        ("excluded", "ruby_excluded_old_identity"),
    ],
)
def test_ruby_relevant_dynamic_framework_reopening_symlink_and_excluded_identity_refuse(
    tmp_path: Path, boundary: str, expected_kind: str
) -> None:
    host = _host(tmp_path, boundary)
    if boundary == "dynamic":
        _write(
            host / "lib/billing/moved_loader.rb",
            'path = "billing/invoice_registry"\nrequire(path)\n',
        )
    elif boundary == "autoload":
        _write(
            host / "lib/billing/moved_loader.rb",
            'Billing.autoload :InvoiceRegistry, "billing/invoice_registry"\n',
        )
    elif boundary == "reflection":
        _write(
            host / "lib/billing/moved_loader.rb",
            "Billing.const_get(:InvoiceRegistry)\n",
        )
    elif boundary == "reopening":
        _write(
            host / "lib/billing/reopened_registry.rb",
            "module Billing\n  class InvoiceRegistry\n  end\nend\n",
        )
    elif boundary == "framework":
        _write(host / "config/application.rb", "class Application < Rails::Application; end\n")
    elif boundary == "symlink":
        source = host / "lib/billing/invoice_registry.rb"
        external = tmp_path / "external-registry.rb"
        external.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(external)
    else:
        _write(
            host / "generated/OldRegistry.rb",
            "Billing::InvoiceRegistry\n",
        )
    plan = _plan(host)
    before = _tree(host)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["ruby"]["status"] == "partial"
    assert expected_kind in {row["kind"] for row in report["ruby"]["blocked"]}
    assert not (report_dir / "evidence.json").exists()
    assert _tree(host) == before
    apply, _, _ = _invoke(host, plan, "apply")
    assert apply.returncode == 2
    assert _tree(host) == before


@pytest.mark.parametrize("operation", ["require", "load"])
def test_ruby_literal_require_or_load_to_moved_file_is_not_guessed(
    tmp_path: Path, operation: str
) -> None:
    host = _host(tmp_path, operation)
    _write(
        host / "lib/billing/alternate_loader.rb",
        f'{operation} "billing/invoice_registry"\n',
    )
    plan = _plan(host)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["ruby"]["status"] == "partial"
    assert "ruby_non_relative_load_impact" in {
        row["kind"] for row in report["ruby"]["blocked"]
    }


def test_ruby_stale_or_missing_authority_refuses_without_writes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)

    missing, _, _ = _invoke(host, plan, "apply")
    assert missing.returncode == 2
    assert _tree(host) == before

    _, evidence_path, evidence = _preview(host, plan)
    wrong, _, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval="0" * 64,
    )
    assert wrong.returncode == 2
    assert _tree(host) == before

    consumer = host / "lib/billing/invoice_service.rb"
    consumer.chmod(0o600)
    stale_before = _tree(host)
    stale, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert stale.returncode == 2
    assert report["ruby"]["failure_kind"] == "stale_move_evidence"
    assert report["ruby"]["rolled_back"] is False
    assert _tree(host) == stale_before


@pytest.mark.parametrize("failure", ["native", "unexpected-mutation"])
def test_ruby_native_failure_and_unexpected_mutation_roll_back_exact_tree(
    tmp_path: Path, failure: str
) -> None:
    host = _host(tmp_path, failure)
    real_ruby = json.dumps(str(RUBY))
    real_bundle = json.dumps(str(BUNDLER))
    if failure == "native":
        ruby = _fake_tool(
            host / "ruby-wrapper",
            "if [ -f lib/invoicing/invoice_registry.rb ]; then\n"
            "  echo forced-postflight-failure >&2\n"
            "  exit 9\n"
            "fi\n"
            f"exec {real_ruby} \"$@\"\n",
        )
        bundler = BUNDLER
    else:
        ruby = RUBY
        marker = json.dumps(str(host / "generated/GeneratedInvoice.rb"))
        bundler = _fake_tool(
            host / "bundle-wrapper",
            "if [ \"${1:-}\" = --version ]; then\n"
            f"  exec {real_bundle} \"$@\"\n"
            "fi\n"
            "if [ -f lib/invoicing/invoice_registry.rb ]; then\n"
            f"  printf '%s\\n' '# unexpected' >> {marker}\n"
            "fi\n"
            f"exec {real_bundle} \"$@\"\n",
        )
    plan = _plan(host, ruby=ruby, bundler=bundler)
    _, evidence_path, evidence = _preview(host, plan)
    before = _tree(host)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["ruby"]["status"] == "failed"
    assert report["ruby"]["rolled_back"] is True
    assert report["ruby"]["rollback_exact"]["passed"] is True
    assert _tree(host) == before
    assert (host / "lib/billing/invoice_registry.rb").is_file()
    assert not (host / "lib/invoicing/invoice_registry.rb").exists()


@pytest.mark.parametrize(
    ("tool_state", "expected_status", "expected_kind"),
    [
        ("missing-ruby", "partial", "ruby_tool_missing"),
        ("old-ruby", "partial", "ruby_tool_too_old"),
        ("bundle-failure", "failed", "frozen_bundle_check_failed"),
    ],
)
def test_ruby_missing_old_and_unsatisfied_bundle_are_honest(
    tmp_path: Path, tool_state: str, expected_status: str, expected_kind: str
) -> None:
    host = _host(tmp_path, tool_state)
    ruby = RUBY
    bundler = BUNDLER
    if tool_state == "missing-ruby":
        ruby = host / "missing-ruby"
    elif tool_state == "old-ruby":
        ruby = _fake_tool(host / "old-ruby", "echo 'ruby 3.2.9p0'\n")
    else:
        real_bundle = json.dumps(str(BUNDLER))
        bundler = _fake_tool(
            host / "failing-bundle",
            "if [ \"${1:-}\" = --version ]; then\n"
            "  echo 'Bundler version 2.6.2'\n"
            "  exit 0\n"
            "fi\n"
            "echo unsatisfied-frozen-lock >&2\n"
            "exit 7\n"
            f"exec {real_bundle} \"$@\"\n",
        )
    plan = _plan(host, ruby=ruby, bundler=bundler)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["ruby"]["status"] == expected_status
    assert report["ruby"]["failure_kind"] == expected_kind
    assert not (report_dir / "evidence.json").exists()
    assert (host / "lib/billing/invoice_registry.rb").is_file()


def test_ruby_copied_stock_closure_runs_outside_repository(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    copied = tmp_path / "installed/move-path/scripts/ruby_module_move.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied)
    outside = tmp_path / "outside"
    outside.mkdir()

    _, evidence_path, evidence = _preview(host, plan, script=copied, cwd=outside)
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        script=copied,
        cwd=outside,
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert report["ruby"]["status"] == "complete"
    assert report["ruby"]["exact_after_tree"]["passed"] is True
    source = copied.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "map_ruby" not in source
    assert "ruby_project_lexical_facts" not in source
