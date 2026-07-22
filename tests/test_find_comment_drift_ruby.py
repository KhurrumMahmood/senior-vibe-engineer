"""Ruby Prism comment-drift evidence, roles, lifecycle, and copied closure."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".claude" / "skills" / "find-comment-drift" / "scripts" / "analyze_comments_ruby.py"
FIXTURE = ROOT / "tests" / "fixtures" / "find-comment-drift-ruby"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
RUBY = Path.home() / ".local" / "bin" / "ruby"
pytestmark = pytest.mark.skipif(not RUBY.is_file(), reason="Ruby 3.4.1 pilot binary is required")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    (host / "bin" / "invoice-smoke").chmod(0o755)
    return host


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.relative_to(host).parts
    }


def _analyze(
    helper: Path,
    host: Path,
    output: Path,
    *targets: str,
    ruby: Path = RUBY,
) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON),
        "-I",
        "-S",
        str(helper),
        "--project-root",
        str(host),
        "--ruby",
        str(ruby),
        "--output",
        str(output),
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


def _native_boundaries(host: Path) -> None:
    selected = sorted(
        path
        for path in host.rglob("*.rb")
        if not ({"generated", "vendor", "build"} & set(path.relative_to(host).parts))
    )
    for source in selected:
        syntax = _run(str(RUBY), "--disable-gems", "-c", str(source), cwd=host)
        assert syntax.returncode == 0, syntax.stdout + syntax.stderr
        assert syntax.stdout == "Syntax OK\n"
    native = _run(
        str(RUBY),
        "--disable-gems",
        f"-I{host / 'lib'}",
        str(host / "test" / "invoice_service_test.rb"),
        cwd=host,
    )
    assert native.returncode == 0, native.stdout + native.stderr
    assert native.stdout == "ruby-test:ok\n"
    executable = _run(str(host / "bin" / "invoice-smoke"), cwd=host)
    assert executable.returncode == 0, executable.stdout + executable.stderr
    assert executable.stdout == "fee:125\n"


def test_ruby_positive_machine_evidence_roles_decoys_copy_and_native_boundaries(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    _native_boundaries(host)
    (host / "linked.rb").symlink_to(FIXTURE / "symlink-target" / "external.rb")
    before = _hashes(host)
    installed = tmp_path / "external-library" / "find-comment-drift"
    installed.joinpath("scripts").mkdir(parents=True)
    shutil.copy2(HELPER, installed / "scripts" / HELPER.name)
    copied_helper = installed / "scripts" / HELPER.name
    output = host / "reports" / "find-comment-drift" / "ruby" / "detections.jsonl"

    result = _analyze(copied_helper, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    report = _payload(output)
    ruby = report["analysis"]["ruby"]
    assert report["status"] == ruby["status"] == "complete"
    assert report["outcome"] == ruby["outcome"] == "advisory-findings"
    assert ruby["analyzer"] == "ruby-prism-comments"
    assert ruby["ruby_version"] == "3.4.1"
    assert ruby["prism_versions"] == ["1.2.0"]
    assert ruby["source_preserved"] is True
    records = _records(output)
    assert len(records) == 1
    finding = records[0]
    assert finding["pattern"] == "behavior_drift_comment"
    assert finding["file"] == "lib/billing/invoice_service.rb"
    assert finding["lineno"] == 5
    assert finding["summary"] == "Calculates a percentage fee from the invoice amount."
    evidence = finding["evidence"]
    assert evidence["claim_kind"] == "parameter-derived-percentage"
    assert evidence["code_fact"] == "fixed-numeric-literal-return"
    assert evidence["method"]["method_name"] == "fee_cents"
    assert evidence["method"]["parameters"] == ["amount_cents"]
    assert evidence["method"]["returned_literal"] == "125"
    source = (host / finding["file"]).read_bytes()
    comment_span = evidence["comment_span"]
    assert source[comment_span["start_byte"] : comment_span["end_byte"]] == (
        b"# Calculates a percentage fee from the invoice amount."
    )
    method_span = evidence["method"]["span"]
    method_bytes = source[method_span["start_byte"] : method_span["end_byte"]]
    assert b"def fee_cents(amount_cents)" in method_bytes
    assert b"125" in method_bytes
    assert hashlib.sha256(method_bytes).hexdigest() == evidence["method"]["spelling_sha256"]

    inventory = {row["file"]: row for row in ruby["inventory"]}
    assert inventory["lib/billing/invoice_service.rb"]["role"] == "eligible"
    assert inventory["lib/billing/invoice_registry.rb"]["role"] == "eligible"
    assert inventory["lib/billing/comment_decoys.rb"]["comment_count"] == 2
    assert inventory["bin/invoice-smoke"]["role"] == "eligible"
    assert inventory["bin/invoice-smoke"]["input_kind"] == "ruby-executable"
    assert inventory["test/invoice_service_test.rb"]["reason"] == "test"
    assert inventory["test/test_comment_decoy.rb"]["reason"] == "test"
    assert inventory["generated/generated_invoice.rb"]["reason"] == "generated-tree"
    assert inventory["lib/billing/generated_marker.rb"]["reason"] == "generated-marker"
    assert inventory["vendor/example/vendor_invoice.rb"]["reason"] == "vendor"
    assert inventory["build/build_invoice.rb"]["reason"] == "build-tree"
    assert inventory["linked.rb"]["reason"] == "symlink"
    assert report["source_manifest_sha256"] == ruby["source_manifest_sha256"]
    assert report["detections_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert _hashes(host) == before
    assert not list(output.parent.glob(".*.tmp"))
    helper_text = copied_helper.read_text(encoding="utf-8")
    assert "scripts/_lib" not in helper_text
    assert str(ROOT) not in helper_text


def test_ruby_clean_complete_and_syntax_malformed_partial_are_distinct(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _hashes(host)
    clean_output = host / "reports" / "clean" / "detections.jsonl"
    clean = _analyze(
        HELPER,
        host,
        clean_output,
        "lib/billing/invoice_registry.rb",
        "lib/billing/comment_decoys.rb",
        "bin/invoice-smoke",
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert _records(clean_output) == []
    clean_report = _payload(clean_output)
    assert clean_report["status"] == "complete"
    assert clean_report["outcome"] == "clean-within-complete"

    broken = host / "lib" / "billing" / "broken.rb"
    shutil.copy2(FIXTURE / "malformed" / "broken.rb", broken)
    malformed_before = _hashes(host)
    partial_output = host / "reports" / "partial" / "detections.jsonl"
    partial = _analyze(
        HELPER,
        host,
        partial_output,
        "lib/billing/invoice_registry.rb",
        "lib/billing/broken.rb",
    )
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert _records(partial_output) == []
    partial_report = _payload(partial_output)
    ruby = partial_report["analysis"]["ruby"]
    assert partial_report["status"] == ruby["status"] == "partial"
    assert partial_report["outcome"] == ruby["outcome"] == "incomplete"
    broken_row = next(row for row in ruby["inventory"] if row["file"].endswith("broken.rb"))
    assert broken_row["role"] == "failed"
    assert broken_row["reason"] == "syntax-error"
    assert ruby["summary"]["failed"] == 1
    assert _hashes(host) == malformed_before
    broken.unlink()
    assert _hashes(host) == before


def _fake_ruby(
    path: Path,
    version: str = "3.4.1",
    *,
    version_exit: int = 0,
    provider_exit: int = 0,
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        f"  printf '%s\\n' 'ruby {version} (fixture)'\n"
        f"  exit {version_exit}\n"
        "fi\n"
        "case \" $* \" in\n"
        "  *\" -c \"*) printf '%s\\n' 'Syntax OK'; exit 0 ;;\n"
        "esac\n"
        f"exit {provider_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_ruby_missing_old_probe_failure_provider_failure_and_lifecycle(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "lifecycle" / "detections.jsonl"
    target = "lib/billing/invoice_service.rb"

    missing = _analyze(HELPER, host, output, target, ruby=tmp_path / "missing-ruby")
    assert missing.returncode == 2
    assert _payload(output)["analysis"]["ruby"]["failure_kind"] == "ruby-tool-missing"

    old = _fake_ruby(tmp_path / "old-ruby", "3.2.9")
    too_old = _analyze(HELPER, host, output, target, ruby=old)
    assert too_old.returncode == 2
    assert _payload(output)["analysis"]["ruby"]["failure_kind"] == "ruby-version-too-old"

    broken_probe = _fake_ruby(tmp_path / "broken-probe", version_exit=7)
    probe_failure = _analyze(HELPER, host, output, target, ruby=broken_probe)
    assert probe_failure.returncode == 1
    assert _payload(output)["analysis"]["ruby"]["failure_kind"] == "ruby-version-failed"

    valid = _analyze(HELPER, host, output, target)
    assert valid.returncode == 0
    valid_report = _payload(output)
    assert valid_report["status"] == "complete"
    assert valid_report["outcome"] == "advisory-findings"
    assert len(_records(output)) == 1

    failing = _fake_ruby(tmp_path / "failing-provider", provider_exit=9)
    failed = _analyze(HELPER, host, output, target, ruby=failing)
    assert failed.returncode == 1
    failed_report = _payload(output)
    assert failed_report["status"] == "failed"
    assert failed_report["outcome"] == "failed"
    assert failed_report["analysis"]["ruby"]["failure_kind"] == "ruby-provider-failed"
    assert _records(output) == []
    assert "advisory-findings" not in output.with_name("report.md").read_text()

    recovered = _analyze(HELPER, host, output, target)
    assert recovered.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    assert len(_records(output)) == 1
    assert _hashes(host) == before


def test_ruby_source_and_artifact_hashes_refresh_at_same_destination(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    source_path = host / "lib" / "billing" / "invoice_service.rb"
    output = host / "reports" / "hash-refresh" / "detections.jsonl"
    first = _analyze(HELPER, host, output, "lib/billing/invoice_service.rb")
    assert first.returncode == 0
    first_report = _payload(output)
    first_source_hash = _records(output)[0]["source_sha256"]
    first_manifest = first_report["source_manifest_sha256"]

    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace("      125\n", "      250\n"),
        encoding="utf-8",
    )
    for artifact in (
        output,
        output.with_name("scan.json"),
        output.with_name("findings.json"),
        output.with_name("report.md"),
    ):
        artifact.write_text("STALE-ARTIFACT\n", encoding="utf-8")

    refreshed = _analyze(HELPER, host, output, "lib/billing/invoice_service.rb")

    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    report = _payload(output)
    finding = _records(output)[0]
    assert finding["evidence"]["method"]["returned_literal"] == "250"
    assert finding["source_sha256"] != first_source_hash
    assert report["source_manifest_sha256"] != first_manifest
    assert report["detections_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert all(
        "STALE-ARTIFACT" not in artifact.read_text(encoding="utf-8")
        for artifact in (
            output,
            output.with_name("scan.json"),
            output.with_name("findings.json"),
            output.with_name("report.md"),
        )
    )
    assert not any(path.name.startswith(".") for path in output.parent.iterdir())


def test_ruby_helper_names_dynamic_nonclaims() -> None:
    text = HELPER.read_text(encoding="utf-8")
    for boundary in (
        "dynamic require/load/autoload",
        "send/public_send",
        "const_get",
        "method_missing",
        "define_method",
        "class/module reopening",
        "Rails",
        "Zeitwerk",
    ):
        assert boundary in text
