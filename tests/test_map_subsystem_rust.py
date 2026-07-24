"""Final-artifact proof for the Cargo-backed Rust subsystem mapper."""

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
SCRIPT = SKILL / "scripts" / "map_rust.py"
FIXTURE = ROOT / "tests" / "fixtures" / "map-subsystem-rust" / "host"
CARGO = shutil.which("cargo")
RUSTC = shutil.which("rustc")
RUST_ANALYZER = shutil.which("rust-analyzer")
CLIPPY = shutil.which("cargo-clippy")
RUSTFMT = shutil.which("rustfmt")
pytestmark = pytest.mark.skipif(
    any(tool is None for tool in (CARGO, RUSTC, RUST_ANALYZER, CLIPPY, RUSTFMT)),
    reason="Rust 1.85+ with Cargo, rust-analyzer, Clippy, and rustfmt is required",
)


def _run(
    *argv: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 240,
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


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _cargo_env(tmp_path: Path, name: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "CARGO_NET_OFFLINE": "true",
            "CARGO_TARGET_DIR": str(tmp_path / f"cargo-target-{name}"),
        }
    )
    return env


def _native(host: Path, tmp_path: Path, name: str) -> None:
    env = _cargo_env(tmp_path, name)
    commands = [
        (str(CARGO), "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"),
        (
            str(CARGO),
            "check",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ),
        (
            str(CARGO),
            "test",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ),
        (
            str(CARGO),
            "clippy",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--",
            "-D",
            "warnings",
        ),
        (str(CARGO), "fmt", "--all", "--", "--check"),
    ]
    for command in commands:
        result = _run(*command, cwd=host, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(
        str(CARGO),
        "run",
        "--quiet",
        "--locked",
        "--offline",
        "-p",
        "rust-map-smoke",
        cwd=host,
        env=env,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "4600\n"


def _source_bytes(host: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(
            part in {".agents", ".claude", ".engineering", "reports", "target"}
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _map(
    host: Path,
    tmp_path: Path,
    *,
    script: Path = SCRIPT,
    name: str = "billing",
    cargo: str | None = None,
    rustc: str | None = None,
    rust_analyzer: str | None = None,
    verify: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / ".engineering" / "docs" / "subsystems" / f"{name}.md"
    evidence = host / "reports" / "map" / name / "rust-map.json"
    argv = [
        sys.executable,
        str(script),
        "--name",
        name,
        "--target",
        "billing-core",
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--evidence",
        str(evidence),
        "--cargo",
        cargo or str(CARGO),
        "--rustc",
        rustc or str(RUSTC),
        "--rust-analyzer",
        rust_analyzer or str(RUST_ANALYZER),
        "--cargo-target-dir",
        str(tmp_path / f"mapper-target-{name}"),
    ]
    if verify:
        argv.append("--verify-artifacts")
    return _run(*argv, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_rust_map_copied_closure_produces_useful_verified_artifacts_and_native_smoke(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    _native(host, tmp_path, "before")
    installed_root = host / ".agents" / "skills" / "on-demand" / "map-subsystem"
    shutil.copytree(SKILL, installed_root)
    before = _source_bytes(host)

    result, output, evidence = _map(
        host,
        tmp_path,
        script=installed_root / "scripts" / "map_rust.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _source_bytes(host) == before
    payload = _payload(evidence)
    markdown = output.read_text(encoding="utf-8")
    assert payload["schema_version"] == "rust-map-v1"
    assert payload["status"] == "partial"
    assert payload["diagnostic_state"] == "clean"
    assert payload["analyzer"] == "cargo-metadata+compiler-json+rust-analyzer-lsp"
    assert payload["workspace"]["members"] == ["billing-core", "rust-map-smoke"]
    assert payload["compiler"]["state"] == "clean"

    package_edges = {
        (edge["source"], edge["target"], edge["kind"])
        for edge in payload["package_dependency_edges"]
    }
    assert ("rust-map-smoke", "billing-core", "normal") in package_edges
    targets = {(row["package"], row["kind"]) for row in payload["cargo_targets"]}
    assert {
        ("billing-core", "lib"),
        ("billing-core", "custom-build"),
        ("billing-core", "test"),
        ("billing-core", "example"),
        ("billing-core", "bench"),
        ("rust-map-smoke", "bin"),
    } <= targets

    module_edges = {(row["source"], row["target"]) for row in payload["module_edges"]}
    assert ("billing-core/src/lib.rs", "billing-core/src/invoice/mod.rs") in module_edges
    assert (
        "billing-core/src/invoice/mod.rs",
        "billing-core/src/invoice/service.rs",
    ) in module_edges
    reexports = {
        (row["source"], row["path"], row["resolved_to"]) for row in payload["public_reexports"]
    }
    assert (
        "billing-core/src/invoice/mod.rs",
        "service::InvoiceService",
        "billing-core/src/invoice/service.rs::InvoiceService",
    ) in reexports

    roles = {row["path"]: (row["role"], row["included"]) for row in payload["source_inventory"]}
    assert roles["billing-core/tests/invoice_service.rs"] == ("test", False)
    assert roles["billing-core/examples/invoice_example.rs"] == ("example", False)
    assert roles["billing-core/benches/invoice_bench.rs"] == ("bench", False)
    assert roles["billing-core/build.rs"] == ("custom-build", False)
    assert roles["billing-core/src/unreachable.rs"] == ("unreachable-source", False)
    assert roles["generated/Generated.rs"] == ("generated", False)
    assert roles["vendor/Vendor.rs"] == ("vendor", False)
    assert roles["target/Target.rs"] == ("target-output", False)

    assert payload["build_scripts"][0]["package"] == "billing-core"
    assert "fixture_build" in payload["build_scripts"][0]["cfgs"]
    assert payload["build_scripts"][0]["generated_contents_inspected"] is False
    assert any(row["expression"] == 'feature = "experimental"' for row in payload["cfg_boundaries"])
    assert any(row["name"] == "define_currency" for row in payload["macro_boundaries"])
    assert any(row["trait"] == "RuntimeLabel" for row in payload["trait_dispatch_boundaries"])
    assert payload["semantic_analysis"]["protocol"] == "LSP"
    assert payload["semantic_analysis"]["state"] == "complete"
    assert payload["semantic_analysis"]["workspace_symbol_ready"] is True
    assert payload["semantic_analysis"]["unstable_cli_used"] is False
    assert any(
        row["name"] == "InvoiceService" and row["source"] == "billing-core/src/invoice/service.rs"
        for row in payload["document_symbols"]
    )
    inbound_definitions = {
        (row["source"], row["symbol"], row["declaration"], row["evidence"])
        for row in payload["reference_edges"]
    }
    assert (
        "rust-map-smoke/src/main.rs",
        "InvoiceService",
        "billing-core/src/invoice/service.rs",
        "textDocument/definition",
    ) in inbound_definitions
    assert (
        "billing-core/tests/invoice_service.rs",
        "InvoiceService",
        "billing-core/src/invoice/service.rs",
        "textDocument/definition",
    ) in inbound_definitions
    assert payload["completeness"]["macro_expansion"] == "unresolved"
    assert payload["completeness"]["generated_build_output_contents"] == "unresolved"
    assert payload["completeness"]["runtime_trait_dispatch"] == "unresolved"
    assert payload["completeness"]["unselected_cfg_and_target_variants"] == "unresolved"
    assert "Status: **partial**" in markdown
    assert "InvoiceService" in markdown
    assert "stable LSP" in markdown

    verified, _, _ = _map(
        host,
        tmp_path,
        script=installed_root / "scripts" / "map_rust.py",
        verify=True,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "verified" in verified.stdout
    _native(host, tmp_path, "after")


def test_rust_map_verifier_rejects_tampered_artifacts_and_changed_source(tmp_path: Path) -> None:
    host = _host(tmp_path)
    mapped, output, evidence = _map(host, tmp_path)
    assert mapped.returncode == 0, mapped.stdout + mapped.stderr
    original_output = output.read_text(encoding="utf-8")
    original_evidence = evidence.read_text(encoding="utf-8")

    payload = json.loads(original_evidence)
    payload["name"] = "tampered"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    stale_evidence, _, _ = _map(host, tmp_path, verify=True)
    assert stale_evidence.returncode == 2
    assert '"evidence_payload": false' in stale_evidence.stderr
    evidence.write_text(original_evidence, encoding="utf-8")

    output.write_text(original_output + "tampered\n", encoding="utf-8")
    stale_markdown, _, _ = _map(host, tmp_path, verify=True)
    assert stale_markdown.returncode == 2
    assert '"markdown": false' in stale_markdown.stderr
    output.write_text(original_output, encoding="utf-8")

    source = host / "billing-core" / "src" / "invoice" / "service.rs"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale_source, _, _ = _map(host, tmp_path, verify=True)
    assert stale_source.returncode == 2
    assert '"source_snapshot": false' in stale_source.stderr


def test_rust_map_replaces_partial_failed_and_recovered_artifacts_at_same_paths(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    first, output, evidence = _map(host, tmp_path, name="transition")
    assert first.returncode == 0, first.stdout + first.stderr
    assert _payload(evidence)["status"] == "partial"
    first_markdown = output.read_text(encoding="utf-8")

    source = host / "billing-core" / "src" / "invoice" / "service.rs"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\npub fn broken( {\n", encoding="utf-8")
    failed, _, _ = _map(host, tmp_path, name="transition")
    assert failed.returncode == 2
    failed_payload = _payload(evidence)
    assert failed_payload["status"] == "failed"
    assert failed_payload["failure_kind"] == "cargo_check_failed"
    assert output.read_text(encoding="utf-8") != first_markdown
    assert "Status: **failed**" in output.read_text(encoding="utf-8")

    source.write_text(original, encoding="utf-8")
    recovered, _, _ = _map(host, tmp_path, name="transition")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _payload(evidence)["status"] == "partial"
    verified, _, _ = _map(host, tmp_path, name="transition", verify=True)
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_rust_map_malformed_manifest_and_stale_lock_are_failed_terminal_states(
    tmp_path: Path,
) -> None:
    malformed = _host(tmp_path, "malformed")
    manifest = malformed / "billing-core" / "Cargo.toml"
    manifest.write_text("[package\n", encoding="utf-8")
    result, output, evidence = _map(malformed, tmp_path, name="malformed")
    assert result.returncode == 2
    assert _payload(evidence)["failure_kind"] == "cargo_metadata_failed"
    assert "Status: **failed**" in output.read_text(encoding="utf-8")

    stale = _host(tmp_path, "stale")
    smoke_manifest = stale / "rust-map-smoke" / "Cargo.toml"
    smoke_manifest.write_text(
        smoke_manifest.read_text(encoding="utf-8").replace(
            'version = "0.1.0"', 'version = "0.2.0"'
        ),
        encoding="utf-8",
    )
    result, _, evidence = _map(stale, tmp_path, name="stale")
    assert result.returncode == 2
    assert _payload(evidence)["failure_kind"] in {"cargo_metadata_failed", "cargo_check_failed"}


def test_rust_map_missing_optional_or_required_tools_remains_bounded_partial(
    tmp_path: Path,
) -> None:
    analyzer_host = _host(tmp_path, "analyzer-host")
    missing_analyzer, _, analyzer_evidence = _map(
        analyzer_host,
        tmp_path,
        name="missing-analyzer",
        rust_analyzer=str(tmp_path / "missing-rust-analyzer"),
    )
    assert missing_analyzer.returncode == 0, missing_analyzer.stdout + missing_analyzer.stderr
    analyzer_payload = _payload(analyzer_evidence)
    assert analyzer_payload["status"] == "partial"
    assert analyzer_payload["compiler"]["state"] == "clean"
    assert analyzer_payload["semantic_analysis"]["state"] == "tool-missing"
    assert analyzer_payload["failure_kind"] == "rust_analyzer_missing"

    cargo_host = _host(tmp_path, "cargo-host")
    missing_cargo, _, cargo_evidence = _map(
        cargo_host,
        tmp_path,
        name="missing-cargo",
        cargo=str(tmp_path / "missing-cargo"),
    )
    assert missing_cargo.returncode == 0
    cargo_payload = _payload(cargo_evidence)
    assert cargo_payload["status"] == "partial"
    assert cargo_payload["failure_kind"] == "cargo_missing"
    assert cargo_payload["diagnostic_state"] == "unavailable"
    assert cargo_payload["workspace"]["members"] == []
    assert cargo_payload["completeness"]["cargo_project_model"] == "unresolved"


def test_rust_map_excludes_symlinked_source_and_rejects_unsafe_artifact_paths(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    outside = tmp_path / "outside.rs"
    outside.write_text("pub const OUTSIDE: bool = true;\n", encoding="utf-8")
    outside_tree = tmp_path / "outside-tree"
    outside_tree.mkdir()
    (outside_tree / "not_first_party.rs").write_text(
        "pub const DIRECTORY_SYMLINK_OUTSIDE: bool = true;\n", encoding="utf-8"
    )
    (host / "linked-external").symlink_to(outside_tree, target_is_directory=True)
    link = host / "billing-core" / "src" / "external_link.rs"
    link.symlink_to(outside)
    lib = host / "billing-core" / "src" / "lib.rs"
    lib.write_text(lib.read_text(encoding="utf-8") + "\npub mod external_link;\n", encoding="utf-8")

    result, _, evidence = _map(host, tmp_path, name="symlink")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(evidence)
    roles = {row["path"]: (row["role"], row["included"]) for row in payload["source_inventory"]}
    assert roles["linked-external"] == ("symlink-excluded", False)
    assert "linked-external/not_first_party.rs" not in roles
    assert roles["billing-core/src/external_link.rs"] == ("symlink-excluded", False)
    assert not any(row["target"].endswith("external_link.rs") for row in payload["module_edges"])

    unsafe_output = tmp_path / "outside.md"
    result = _run(
        sys.executable,
        str(SCRIPT),
        "--name",
        "unsafe",
        "--target",
        "billing-core",
        "--project-root",
        str(host),
        "--output",
        str(unsafe_output),
        "--evidence",
        str(host / "reports" / "map" / "unsafe" / "rust-map.json"),
        cwd=host,
    )
    assert result.returncode == 2
    assert not unsafe_output.exists()
