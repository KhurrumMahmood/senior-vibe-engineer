"""Final-outcome proof for the bounded plain-Ruby/gem subsystem map."""
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
SKILL = ROOT / ".claude" / "skills" / "map-subsystem"
SCRIPT = SKILL / "scripts" / "map_ruby.py"
FIXTURE = ROOT / "tests" / "fixtures" / "map-subsystem-ruby"
RUBY = shutil.which("ruby")
BUNDLE = shutil.which("bundle")


def _run(
    *argv: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _usable_toolchain() -> bool:
    if RUBY is None or BUNDLE is None:
        return False
    ruby = _run(RUBY, "--version", cwd=ROOT)
    prism = _run(
        RUBY,
        "--disable-gems",
        "-rprism",
        "-e",
        "puts Prism::VERSION",
        cwd=ROOT,
    )
    bundle = _run(BUNDLE, "--version", cwd=ROOT)
    return ruby.returncode == prism.returncode == bundle.returncode == 0


pytestmark = pytest.mark.skipif(
    not _usable_toolchain(),
    reason="Ruby 3.3+, bundled Prism, and Bundler 2.6+ are required",
)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    (host / "bin" / "invoice-kit-smoke").chmod(0o755)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".agents", ".claude", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _map(
    host: Path,
    *,
    script: Path = SCRIPT,
    name: str = "billing",
    targets: tuple[str, ...] = ("lib/billing",),
    ruby: str | None = None,
    bundle: str | None = None,
    minimum_ruby: str | None = None,
    minimum_bundler: str | None = None,
    output: Path | None = None,
    evidence: Path | None = None,
    expected_source_sha256: str | None = None,
    run_native: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".claude" / "docs" / "subsystems" / f"{name}.md"
    evidence = evidence or host / "reports" / "map" / name / "ruby-map.json"
    argv = [
        sys.executable,
        str(script),
        "--name", name,
        "--project-root", str(host),
        "--output", str(output),
        "--evidence", str(evidence),
        "--ruby", ruby or str(RUBY),
        "--bundle", bundle or str(BUNDLE),
    ]
    for target in targets:
        argv.extend(["--target", target])
    if run_native:
        argv.extend([
            "--test", "test/invoice_service_test.rb",
            "--smoke", "bin/invoice-kit-smoke",
        ])
    if minimum_ruby:
        argv.extend(["--minimum-ruby", minimum_ruby])
    if minimum_bundler:
        argv.extend(["--minimum-bundler", minimum_bundler])
    if expected_source_sha256:
        argv.extend(["--expected-source-sha256", expected_source_sha256])
    return (
        _run(*argv, cwd=host, timeout=90),
        output,
        evidence,
    )


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_ruby_map_reaches_static_value_native_boundary_and_preserves_source(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "linked.rb").write_text("module NeverTraverse; end\n", encoding="utf-8")
    os.symlink(external / "linked.rb", host / "lib" / "billing" / "linked.rb")
    before = _fingerprints(host)

    result, output, evidence = _map(host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "partial"
    assert payload["analyzer"] == "ruby-3.3+-syntax+prism-ast+literal-load-layout"
    assert payload["lifecycle"] == {
        "artifact_pair": "complete",
        "bounded_static_map": "complete",
        "semantic_reachability": "partial",
        "run": "partial",
    }
    assert payload["source_fingerprints"]["unchanged"] is True
    assert payload["source_fingerprints"]["before"] == payload["source_fingerprints"]["after"]
    assert len(payload["source_fingerprints"]["before"]) == 64

    inventory = {row["path"]: row for row in payload["source_inventory"]}
    assert inventory["lib/billing/invoice_service.rb"]["role"] == "source"
    assert inventory["test/invoice_service_test.rb"]["role"] == "test"
    assert inventory["spec/decoy_spec.rb"]["role"] == "test"
    assert inventory["bin/invoice-kit-smoke"]["role"] == "entrypoint"
    assert inventory["generated/GeneratedInvoice.rb"]["role"] == "generated"
    assert inventory["vendor/VendorInvoice.rb"]["role"] == "vendor"
    assert inventory["build/BuildInvoice.rb"]["role"] == "build"
    assert inventory["lib/billing/linked.rb"]["role"] == "symlink"
    assert inventory["sig/invoice_kit.rbs"]["role"] == "signature"
    assert all(row["sha256"] for row in inventory.values() if row["role"] != "symlink")
    assert not inventory["lib/billing/linked.rb"]["included"]

    declarations = {(row["kind"], row["qualified_name"]) for row in payload["declarations"]}
    assert ("module", "Billing") in declarations
    assert ("class", "Billing::InvoiceService") in declarations
    assert ("class", "Billing::InvoiceRegistry") in declarations
    assert ("module", "Billing::Formatting") in declarations
    methods = {(row["owner"], row["name"], row["singleton"]) for row in payload["methods"]}
    assert ("Billing::InvoiceService", "initialize", False) in methods
    assert ("Billing::InvoiceService", "render", False) in methods
    assert ("Billing::FactoryMethods", "build", False) in methods

    namespace = {
        row["qualified_name"]: row for row in payload["namespace_and_reopening_evidence"]
    }
    assert namespace["Billing::InvoiceService"]["statically_reopened"] is True
    assert namespace["Billing::InvoiceService"]["definition_count"] == 2
    assert {row["operation"] for row in payload["mixins"]} == {
        "include", "extend", "prepend"
    }
    assert {row["target_spelling"] for row in payload["mixins"]} == {
        "Formatting", "FactoryMethods", "Audited"
    }

    edges = {
        (row["caller"], row["operation"], row["specifier"]): row
        for row in payload["literal_load_edges"]
    }
    assert edges[(
        "lib/billing/invoice_service.rb", "require_relative", "invoice_registry"
    )]["resolved_path"] == "lib/billing/invoice_registry.rb"
    assert edges[(
        "lib/invoice_kit.rb", "require", "billing/invoice_service"
    )]["resolved_path"] == "lib/billing/invoice_service.rb"
    assert edges[(
        "lib/billing/config_loader.rb", "load", "billing/configuration.rb"
    )]["resolved_path"] == "lib/billing/configuration.rb"
    assert edges[("lib/billing/invoice_service.rb", "require", "json")][
        "resolution"
    ] == "external-or-standard-library"

    constant_edges = {
        (row["owner"], row["spelling"], row.get("candidate_declaration"))
        for row in payload["syntactic_constant_references"]
    }
    assert (
        "Billing::InvoiceService", "InvoiceRegistry", "Billing::InvoiceRegistry"
    ) in constant_edges
    assert all("runtime" in row["resolution"] for row in payload["syntactic_constant_references"])

    assert {row["kind"] for row in payload["entrypoints"]} == {"test", "executable"}
    native = payload["native_evidence"]
    assert native["bundle_check"]["status"] == "passed"
    assert native["test"]["stdout"] == "native-test:ok\n"
    assert native["smoke"]["stdout"] == '{"label":"registered:SMOKE-1"}\n'
    assert all(row["status"] == "passed" for row in native["syntax_checks"])
    assert {signal["kind"] for signal in payload["dynamic_signals"]} >= {
        "dynamic-require", "const-get", "dynamic-send", "method-missing",
        "define-method", "class-eval",
    }
    assert payload["completeness"]["source_inventory"] == "complete"
    assert payload["completeness"]["literal_load_edges"] == "complete"
    assert payload["completeness"]["runtime_symbol_identity"] == "partial"
    assert "Status: **partial**" in rendered
    assert "Billing::InvoiceService" in rendered
    assert "Dynamic require" in rendered


def test_ruby_map_replaces_same_destination_across_partial_failed_and_recovered(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    source = host / "lib" / "billing" / "invoice_service.rb"
    original = source.read_text(encoding="utf-8")

    valid, output, evidence = _map(host, name="transition")
    assert valid.returncode == 0
    valid_doc = output.read_text(encoding="utf-8")

    source.write_text(original + "\ndef malformed(\n", encoding="utf-8")
    failed, _, _ = _map(host, name="transition")
    assert failed.returncode == 2
    failed_payload = _payload(evidence)
    assert failed_payload["status"] == "failed"
    assert failed_payload["failure_kind"] == "ruby_syntax_failed"
    assert failed_payload["lifecycle"]["bounded_static_map"] == "failed"
    assert "Status: **failed**" in output.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") != valid_doc

    source.write_text(original, encoding="utf-8")
    recovered, _, _ = _map(host, name="transition")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    recovered_payload = _payload(evidence)
    assert recovered_payload["status"] == "partial"
    assert recovered_payload["failure_kind"] == "none"
    assert not recovered_payload.get("syntax_errors")
    assert "Status: **partial**" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("missing-ruby", "ruby_missing"),
        ("old-ruby", "ruby_version_too_old"),
        ("broken-ruby", "ruby_version_unavailable"),
        ("missing-bundle", "bundler_missing"),
        ("old-bundle", "bundler_version_too_old"),
        ("broken-bundle", "bundler_version_unavailable"),
    ],
)
def test_ruby_map_tool_terminal_states(
    tmp_path: Path, case: str, expected_kind: str
) -> None:
    host = _copy_host(tmp_path, case)
    ruby = str(RUBY)
    bundle = str(BUNDLE)
    if case == "missing-ruby":
        ruby = str(host / "missing-ruby")
    elif case == "old-ruby":
        ruby = str(_fake_tool(host / "old-ruby", "echo 'ruby 3.2.9'\n"))
    elif case == "broken-ruby":
        ruby = str(_fake_tool(host / "broken-ruby", "echo broken >&2\nexit 7\n"))
    elif case == "missing-bundle":
        bundle = str(host / "missing-bundle")
    elif case == "old-bundle":
        bundle = str(_fake_tool(host / "old-bundle", "echo 'Bundler version 2.5.9'\n"))
    elif case == "broken-bundle":
        bundle = str(_fake_tool(host / "broken-bundle", "echo broken >&2\nexit 7\n"))

    result, output, evidence = _map(host, ruby=ruby, bundle=bundle)

    assert result.returncode == 0
    payload = _payload(evidence)
    assert payload["status"] == "unsupported"
    assert payload["failure_kind"] == expected_kind
    assert payload["lifecycle"]["bounded_static_map"] == "not-run"
    assert "Status: **unsupported**" in output.read_text(encoding="utf-8")


def test_ruby_map_project_bundle_and_native_failures_are_explicit(tmp_path: Path) -> None:
    missing = _copy_host(tmp_path, "missing-project")
    (missing / "Gemfile.lock").unlink()
    result, _, evidence = _map(missing)
    assert result.returncode == 0
    assert _payload(evidence)["failure_kind"] == "project_metadata_missing"

    malformed = _copy_host(tmp_path, "malformed-gemfile")
    (malformed / "Gemfile").write_text("gemspec(\n", encoding="utf-8")
    result, _, evidence = _map(malformed)
    assert result.returncode == 2
    assert _payload(evidence)["failure_kind"] == "bundle_check_failed"

    failing_test = _copy_host(tmp_path, "failing-test")
    (failing_test / "test" / "invoice_service_test.rb").write_text(
        'raise "native failure"\n', encoding="utf-8"
    )
    result, _, evidence = _map(failing_test)
    assert result.returncode == 2
    assert _payload(evidence)["failure_kind"] == "native_test_failed"

    failing_smoke = _copy_host(tmp_path, "failing-smoke")
    (failing_smoke / "bin" / "invoice-kit-smoke").write_text(
        'raise "smoke failure"\n', encoding="utf-8"
    )
    result, _, evidence = _map(failing_smoke)
    assert result.returncode == 2
    assert _payload(evidence)["failure_kind"] == "native_smoke_failed"


def test_ruby_map_mixed_targets_roles_and_symlink_boundaries(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    mixed, _, evidence = _map(
        host,
        name="mixed",
        targets=("lib/billing", "unsupported/widget.py", "generated"),
    )
    assert mixed.returncode == 0, mixed.stdout + mixed.stderr
    payload = _payload(evidence)
    assert payload["status"] == "partial"
    assert [row["status"] for row in payload["target_results"]] == [
        "complete", "unsupported", "unsupported"
    ]
    assert payload["selected_source_files"]

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.rb").write_text("module Outside; end\n", encoding="utf-8")
    os.symlink(outside, host / "linked-target")
    linked, _, linked_evidence = _map(
        host, name="linked", targets=("linked-target",), run_native=False
    )
    assert linked.returncode == 0
    linked_payload = _payload(linked_evidence)
    assert linked_payload["status"] == "unsupported"
    assert linked_payload["target_results"][0]["reason"] == "unsafe-symlink-target"
    assert not any("Outside" in json.dumps(row) for row in linked_payload.get("declarations", []))


def test_ruby_map_rejects_unsafe_paths_without_touching_source(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    victim = host / "lib" / "billing" / "invoice_service.rb"
    before = victim.read_bytes()
    unsafe_output, _, _ = _map(host, name="unsafe-output", output=victim)
    assert unsafe_output.returncode == 2
    assert "output must stay" in unsafe_output.stderr
    assert victim.read_bytes() == before

    unsafe_target, _, _ = _map(host, name="unsafe-target", targets=("../outside",))
    assert unsafe_target.returncode == 2
    assert "target must stay" in unsafe_target.stderr
    assert victim.read_bytes() == before

    (host / "reports").mkdir()
    (host / "reports").rmdir()
    os.symlink(host / "lib", host / "reports")
    artifact_link, _, _ = _map(host, name="artifact-link")
    assert artifact_link.returncode == 2
    assert "symbolic link" in artifact_link.stderr
    assert victim.read_bytes() == before


def test_ruby_map_rejects_stale_snapshot_and_detects_source_mutation(tmp_path: Path) -> None:
    host = _copy_host(tmp_path, "stale")
    result, _, evidence = _map(host, expected_source_sha256="0" * 64)
    assert result.returncode == 2
    stale = _payload(evidence)
    assert stale["status"] == "failed"
    assert stale["failure_kind"] == "stale_source_snapshot"

    mutated = _copy_host(tmp_path, "mutated")
    marker = mutated / "lib" / "billing" / "configuration.rb"
    wrapper = _fake_tool(
        mutated / "mutating-ruby",
        "if [ \"${1:-}\" = \"--disable-gems\" ] && [ \"${2:-}\" = \"-c\" ]; then\n"
        f"  printf '%s\\n' '# changed during analysis' >> {json.dumps(str(marker))}\n"
        "fi\n"
        f"exec {json.dumps(str(RUBY))} \"$@\"\n",
    )
    result, _, evidence = _map(mutated, ruby=str(wrapper), run_native=False)
    assert result.returncode == 2
    changed = _payload(evidence)
    assert changed["status"] == "failed"
    assert changed["failure_kind"] == "source_mutated"
    assert changed["source_fingerprints"]["unchanged"] is False


def test_ruby_map_copied_single_file_closure_has_no_checkout_dependency(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    installed = host / ".agents" / "skills" / "map-subsystem" / "scripts"
    installed.mkdir(parents=True)
    copied = installed / "map_ruby.py"
    shutil.copy2(SCRIPT, copied)
    before = _fingerprints(host)

    result, _, evidence = _map(host, script=copied, name="copied")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _payload(evidence)["status"] == "partial"
    assert _fingerprints(host) == before
    source = copied.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "tree_sitter" not in source
    assert "pip install" not in source
    assert "gem install" not in source
