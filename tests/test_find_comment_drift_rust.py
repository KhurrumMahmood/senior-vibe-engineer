"""Rust lexical comment-drift evidence, roles, lifecycle, and copied closure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".claude" / "skills" / "find-comment-drift" / "scripts" / "analyze_comments_rust.py"
FIXTURE = ROOT / "tests" / "fixtures" / "rust-pilot"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
RUSTC = Path.home() / ".local" / "bin" / "rustc"
CARGO = Path.home() / ".local" / "bin" / "cargo"
RUSTFMT = Path.home() / ".local" / "bin" / "rustfmt"
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (RUSTC, CARGO, RUSTFMT)),
    reason="Rust 1.97.1 pilot toolchain is required",
)


def _run(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
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
    rustc: Path = RUSTC,
    cargo: Path = CARGO,
    rustfmt: Path = RUSTFMT,
) -> subprocess.CompletedProcess[str]:
    return _run(
        str(PYTHON),
        "-I",
        "-S",
        str(helper),
        "--project-root",
        str(host),
        "--rustc",
        str(rustc),
        "--cargo",
        str(cargo),
        "--rustfmt",
        str(rustfmt),
        "--output",
        str(output),
        *(targets or (".",)),
        cwd=host,
    )


def _payload(output: Path) -> dict:
    return json.loads(output.with_name("findings.json").read_text(encoding="utf-8"))


def _records(output: Path) -> list[dict]:
    return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line]


def _cargo_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        CARGO_NET_OFFLINE="true",
        CARGO_TARGET_DIR=str(tmp_path / "native-target"),
        CARGO_HOME=str(tmp_path / "native-cargo-home"),
    )
    return env


def _native_boundaries(host: Path, tmp_path: Path) -> None:
    env = _cargo_env(tmp_path)
    for command in (
        ("check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"),
        ("test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"),
        ("fmt", "--all", "--", "--check"),
    ):
        result = _run(str(CARGO), *command, cwd=host, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(
        str(CARGO),
        "run",
        "--quiet",
        "--locked",
        "--offline",
        "-p",
        "rust-pilot-smoke",
        cwd=host,
        env=env,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:INV-42:125\n"


def test_rust_positive_machine_evidence_roles_copy_and_native_boundaries(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _native_boundaries(host, tmp_path)
    (host / "linked-external").symlink_to(FIXTURE / "symlink-target", target_is_directory=True)
    before = _hashes(host)
    installed = tmp_path / "external-library" / "find-comment-drift"
    installed.joinpath("scripts").mkdir(parents=True)
    shutil.copy2(HELPER, installed / "scripts" / HELPER.name)
    copied_helper = installed / "scripts" / HELPER.name
    output = host / "reports" / "find-comment-drift" / "rust" / "detections.jsonl"

    result = _analyze(copied_helper, host, output)

    assert result.returncode == 0, result.stdout + result.stderr
    report = _payload(output)
    rust = report["analysis"]["rust"]
    assert report["status"] == rust["status"] == "complete"
    assert report["outcome"] == rust["outcome"] == "advisory-findings"
    assert rust["analyzer"] == "rust-byte-lexer+cargo+rustfmt"
    assert rust["tools"]["rustc"]["version"] == "1.97.1"
    assert rust["tools"]["cargo"]["version"] == "1.97.1"
    assert rust["cargo_check"]["returncode"] == 0
    assert rust["cargo_check"]["all_targets"] is True
    assert rust["cargo_check"]["all_features"] is True
    assert rust["source_preserved"] is True

    records = _records(output)
    assert len(records) == 1
    finding = records[0]
    assert finding["pattern"] == "behavior_drift_comment"
    assert finding["file"] == "crates/billing-core/src/invoice/service.rs"
    assert finding["lineno"] == 5
    assert finding["summary"] == "Calculates a percentage fee from the invoice amount."
    evidence = finding["evidence"]
    assert evidence["comment_kind"] == "outer-doc-line"
    assert evidence["claim_kind"] == "parameter-derived-percentage"
    assert evidence["code_fact"] == "fixed-numeric-literal-return"
    assert evidence["function"]["function_name"] == "fee_cents"
    assert evidence["function"]["parameters"] == ["_amount_cents"]
    assert evidence["function"]["returned_literal"] == "125"
    source = (host / finding["file"]).read_bytes()
    comment_span = evidence["comment_span"]
    assert source[comment_span["start_byte"] : comment_span["end_byte"]] == (
        b"/// Calculates a percentage fee from the invoice amount."
    )
    function_span = evidence["function"]["span"]
    function_bytes = source[function_span["start_byte"] : function_span["end_byte"]]
    assert b"pub const fn fee_cents" in function_bytes
    assert b"125" in function_bytes
    assert hashlib.sha256(function_bytes).hexdigest() == evidence["function"]["spelling_sha256"]

    inventory = {row["file"]: row for row in rust["inventory"]}
    assert inventory["crates/billing-core/src/invoice/service.rs"]["role"] == "eligible"
    assert inventory["crates/billing-core/src/invoice/service.rs"]["comment_count"] == 2
    assert inventory["crates/billing-core/src/macro_boundary.rs"]["role"] == "eligible"
    assert inventory["crates/billing-core/tests/invoice_service.rs"]["reason"] == "test"
    assert (
        inventory["crates/billing-core/examples/invoice_example.rs"]["reason"] == "auxiliary-target"
    )
    assert inventory["crates/billing-core/benches/invoice_bench.rs"]["reason"] == "auxiliary-target"
    assert inventory["crates/billing-core/build.rs"]["reason"] == "configuration"
    assert inventory["generated/GeneratedInvoice.rs"]["reason"] == "generated-tree"
    assert inventory["vendor/VendorInvoice.rs"]["reason"] == "vendor"
    assert inventory["target/TargetSentinel.rs"]["reason"] == "build-tree"
    assert inventory["linked-external"]["reason"] == "symlink"
    assert report["source_manifest_sha256"] == rust["source_manifest_sha256"]
    assert report["detections_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert _hashes(host) == before
    assert not list(output.parent.glob(".*.tmp"))
    helper_text = copied_helper.read_text(encoding="utf-8")
    assert "scripts/_lib" not in helper_text
    assert str(ROOT) not in helper_text


def test_rust_lexical_decoys_attributes_cfg_and_clean_complete(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source = host / "crates" / "billing-core" / "src" / "lexical_decoys.rs"
    source.write_text(
        r"""#[doc = "Calculates a percentage fee from the invoice amount."]
pub fn attribute_is_not_a_comment(_amount: u64) -> u64 { 125 }

const QUOTED: &str = "/// Calculates a percentage fee from the amount.";
const RAW: &str = r###"/* SiteConfig at invoice.rs:99 */"###;
const BYTE: &[u8] = b"// SECTION 12";
const CHARACTER: char = '/';
fn lifetime<'a>(value: &'a str) -> &'a str { value }

/* outer /* nested */ block with durable rationale */
#[cfg(feature = "not-selected")]
/// Calculates a percentage fee from the invoice amount.
pub fn inactive_cfg(_amount: u64) -> u64 { 125 }
""",
        encoding="utf-8",
    )
    before = _hashes(host)
    output = host / "reports" / "clean" / "detections.jsonl"

    clean = _analyze(
        HELPER,
        host,
        output,
        "crates/billing-core/src/lexical_decoys.rs",
    )

    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert _records(output) == []
    report = _payload(output)
    assert report["status"] == "complete"
    assert report["outcome"] == "clean-within-complete"
    row = report["analysis"]["rust"]["inventory"][0]
    assert row["comment_count"] == 2
    assert _hashes(host) == before


def test_rust_malformed_source_is_partial_not_clean_or_unsupported(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    broken = host / "orphan_broken.rs"
    shutil.copy2(FIXTURE / "malformed" / "Broken.rs", broken)
    before = _hashes(host)
    output = host / "reports" / "partial" / "detections.jsonl"

    result = _analyze(
        HELPER,
        host,
        output,
        "crates/billing-core/src/macro_boundary.rs",
        "orphan_broken.rs",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = _payload(output)
    rust = report["analysis"]["rust"]
    assert report["status"] == rust["status"] == "partial"
    assert report["outcome"] == rust["outcome"] == "incomplete"
    assert report["status"] != "unsupported"
    assert _records(output) == []
    broken_row = next(row for row in rust["inventory"] if row["file"] == "orphan_broken.rs")
    assert broken_row["role"] == "failed"
    assert broken_row["reason"] == "syntax-error"
    assert rust["summary"]["failed"] == 1
    assert _hashes(host) == before


def _fake_cargo(
    path: Path, version: str = "1.97.1", *, version_exit: int = 0, check_exit: int = 0
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'cargo {version} (fixture)'\n"
        f"  exit {version_exit}\n"
        "fi\n"
        f"exit {check_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_rust_missing_old_probe_failure_native_failure_and_lifecycle(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _hashes(host)
    output = host / "reports" / "lifecycle" / "detections.jsonl"
    target = "crates/billing-core/src/invoice/service.rs"

    missing = _analyze(HELPER, host, output, target, cargo=tmp_path / "missing-cargo")
    assert missing.returncode == 2
    missing_report = _payload(output)
    assert missing_report["status"] == "partial"
    assert missing_report["status"] != "unsupported"
    assert missing_report["analysis"]["rust"]["failure_kind"] == "cargo-tool-missing"

    old = _fake_cargo(tmp_path / "old-cargo", "1.84.9")
    too_old = _analyze(HELPER, host, output, target, cargo=old)
    assert too_old.returncode == 2
    assert _payload(output)["analysis"]["rust"]["failure_kind"] == "cargo-version-too-old"
    assert _payload(output)["status"] == "partial"

    broken_probe = _fake_cargo(tmp_path / "broken-probe", version_exit=7)
    probe_failure = _analyze(HELPER, host, output, target, cargo=broken_probe)
    assert probe_failure.returncode == 1
    assert _payload(output)["analysis"]["rust"]["failure_kind"] == "cargo-version-failed"

    valid = _analyze(HELPER, host, output, target)
    assert valid.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    assert len(_records(output)) == 1

    failing = _fake_cargo(tmp_path / "failing-check", check_exit=9)
    failed = _analyze(HELPER, host, output, target, cargo=failing)
    assert failed.returncode == 1
    failed_report = _payload(output)
    assert failed_report["status"] == "failed"
    assert failed_report["outcome"] == "failed"
    assert failed_report["analysis"]["rust"]["failure_kind"] == "cargo-check-failed"
    assert _records(output) == []
    assert "advisory-findings" not in output.with_name("report.md").read_text(encoding="utf-8")

    recovered = _analyze(HELPER, host, output, target)
    assert recovered.returncode == 0
    assert _payload(output)["outcome"] == "advisory-findings"
    assert len(_records(output)) == 1
    assert _hashes(host) == before


def test_rust_source_and_artifact_hashes_refresh_at_same_destination(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source_path = host / "crates" / "billing-core" / "src" / "invoice" / "service.rs"
    output = host / "reports" / "hash-refresh" / "detections.jsonl"
    first = _analyze(HELPER, host, output, "crates/billing-core/src/invoice/service.rs")
    assert first.returncode == 0
    first_report = _payload(output)
    first_source_hash = _records(output)[0]["source_sha256"]
    first_manifest = first_report["source_manifest_sha256"]

    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace("        125\n", "        250\n"),
        encoding="utf-8",
    )
    for artifact in (
        output,
        output.with_name("scan.json"),
        output.with_name("findings.json"),
        output.with_name("report.md"),
    ):
        artifact.write_text("STALE-ARTIFACT\n", encoding="utf-8")

    refreshed = _analyze(HELPER, host, output, "crates/billing-core/src/invoice/service.rs")

    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    report = _payload(output)
    finding = _records(output)[0]
    assert finding["evidence"]["function"]["returned_literal"] == "250"
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


def test_rust_helper_names_semantic_nonclaims() -> None:
    text = HELPER.read_text(encoding="utf-8")
    for boundary in (
        "macro_rules",
        "procedural-macro",
        "build.rs output",
        "OUT_DIR",
        "include!",
        "cfg-gated",
        "trait",
        "runtime-dispatch",
    ):
        assert boundary in text
