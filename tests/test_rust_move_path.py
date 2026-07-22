"""Final mutation-boundary proof for the bounded Rust move-path cohort."""
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
SCRIPT = ROOT / ".claude" / "skills" / "move-path" / "scripts" / "rust_module_move.py"
FIXTURE = ROOT / "tests" / "fixtures" / "move-path-rust"
CARGO = shutil.which("cargo")
RUSTC = shutil.which("rustc")
CLIPPY = shutil.which("cargo-clippy")
RUSTFMT = shutil.which("rustfmt")
TOOLS_AVAILABLE = all((CARGO, RUSTC, CLIPPY, RUSTFMT))


pytestmark = pytest.mark.skipif(
    not TOOLS_AVAILABLE,
    reason="Rust/Cargo, Clippy, and rustfmt are required for the frozen mutation cohort",
)


def _run(
    *argv: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 180,
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


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    return host


def _tree_state(host: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts and relative.parts[0] == "reports":
            continue
        if path.is_symlink():
            state[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative.as_posix()] = (
                "file", hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return state


def _cargo_env(state: Path) -> dict[str, str]:
    path_parts = {
        str(Path(tool).parent)
        for tool in (str(CARGO), str(RUSTC), str(CLIPPY), str(RUSTFMT))
    }
    return {
        **os.environ,
        "CARGO_HOME": str(state / "cargo-home"),
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": str(state / "target"),
        "RUSTC": str(RUSTC),
        "PATH": os.pathsep.join([*sorted(path_parts), os.environ.get("PATH", "")]),
        "ALL_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }


def _native(host: Path, state: Path) -> None:
    environment = _cargo_env(state)
    for argv in (
        [str(CARGO), "metadata", "--format-version", "1", "--locked", "--offline", "--no-deps"],
        [str(CARGO), "check", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
        [str(CARGO), "test", "--locked", "--offline", "--workspace", "--all-targets", "--all-features"],
        [str(CARGO), "clippy", "--locked", "--offline", "--workspace", "--all-targets", "--all-features", "--", "-D", "warnings"],
        [str(CARGO), "fmt", "--all", "--", "--check"],
    ):
        result = _run(*argv, cwd=host, env=environment)
        assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(
        str(CARGO), "run", "--quiet", "--locked", "--offline",
        "-p", "rust-move-smoke", cwd=host, env=environment,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "invoice:SMOKE-1:125\n"


def _plan(
    host: Path,
    *,
    source: str = "crates/billing-core/src/invoice/service.rs",
    destination: str = "crates/billing-core/src/invoice/invoice_service.rs",
    mode: str = "file",
    cargo: str | None = None,
    rustc: str | None = None,
    clippy: str | None = None,
    rustfmt: str | None = None,
    moves: list[dict] | None = None,
) -> Path:
    plan = host / "rust-move.json"
    payload = {
        "version": 1,
        "moves": moves or [{"from": source, "to": destination, "mode": mode}],
        "rewrite": {"code_imports": "update-rust"},
        "rust": {
            "cargo": cargo or str(CARGO),
            "rustc": rustc or str(RUSTC),
            "cargo_clippy": clippy or str(CLIPPY),
            "rustfmt": rustfmt or str(RUSTFMT),
            "smoke_package": "rust-move-smoke",
            "smoke_expected_stdout": "invoice:SMOKE-1:125\n",
        },
    }
    plan.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return plan


def _invoke(
    host: Path,
    plan: Path,
    mode: str,
    *,
    script: Path = SCRIPT,
    expected_source_sha256: str | None = None,
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    report_dir = host / "reports" / "move-path"
    argv = [
        sys.executable,
        "-I",
        "-S",
        str(script),
        "--plan", str(plan),
        "--project-root", str(host),
        "--report-dir", str(report_dir),
        f"--{mode}",
        "--json",
    ]
    if expected_source_sha256:
        argv.extend(["--expected-source-sha256", expected_source_sha256])
    result = _run(*argv, cwd=cwd or host)
    report_path = report_dir / "report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    return result, payload, report_dir


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_rust_file_preview_apply_check_exact_edits_and_native_boundary(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    plan = _plan(host)
    _native(host, tmp_path / "native-before")
    before = _tree_state(host)
    protected = {
        path: (host / path).read_bytes()
        for path in (
            "Cargo.toml", "Cargo.lock", "crates/billing-core/Cargo.toml",
            "crates/billing-core/build.rs",
            "crates/billing-core/src/macro_boundary.rs",
            "generated/GeneratedInvoice.rs", "vendor/VendorInvoice.rs",
            "target/TargetSentinel.rs",
        )
    }

    preview_result, preview, report_dir = _invoke(host, plan, "dry-run")

    assert preview_result.returncode == 0, preview_result.stdout + preview_result.stderr
    assert _tree_state(host) == before
    rust = preview["rust"]
    assert rust["status"] == "complete"
    assert rust["source"] == "crates/billing-core/src/invoice/service.rs"
    assert rust["destination"] == "crates/billing-core/src/invoice/invoice_service.rs"
    assert rust["module_before"] == "billing_core::invoice::service"
    assert rust["module_after"] == "billing_core::invoice::invoice_service"
    assert rust["public_reexport_preserved"] is True
    assert rust["source_manifest"]["before_fingerprint"]
    assert rust["source_manifest"]["actual_fingerprint"] == rust["source_manifest"]["before_fingerprint"]
    assert "rename crates/billing-core/src/invoice/service.rs" in rust["review_diff"]
    changes = {
        (row["file_before"], row["kind"], row["old"], row["new"])
        for row in rust["exact_changes"]
    }
    assert (
        "crates/billing-core/src/invoice/mod.rs", "module-declaration",
        "service", "invoice_service",
    ) in changes
    assert (
        "crates/billing-core/src/lib.rs", "resolved-module-path",
        "service", "invoice_service",
    ) in changes
    assert (
        "crates/billing-core/src/invoice/consumer.rs", "resolved-module-path",
        "service", "invoice_service",
    ) in changes
    assert (
        "crates/billing-core/tests/invoice_service.rs", "resolved-module-path",
        "service", "invoice_service",
    ) in changes
    assert all(row["passed"] for row in rust["native_preflight"].values())
    assert "Status: `complete`" in (report_dir / "report.md").read_text(encoding="utf-8")

    expected = rust["source_manifest"]["before_fingerprint"]
    apply_result, applied, _ = _invoke(
        host, plan, "apply", expected_source_sha256=expected
    )

    assert apply_result.returncode == 0, apply_result.stdout + apply_result.stderr
    moved = host / "crates/billing-core/src/invoice/invoice_service.rs"
    assert moved.is_file()
    assert not (host / "crates/billing-core/src/invoice/service.rs").exists()
    parent = (host / "crates/billing-core/src/invoice/mod.rs").read_text(encoding="utf-8")
    assert "pub mod invoice_service;" in parent
    assert "pub use invoice_service::InvoiceService;" in parent
    assert "invoice_service::InvoiceService" in parent
    assert "crate::invoice::invoice_service::InvoiceService" in (
        host / "crates/billing-core/src/lib.rs"
    ).read_text(encoding="utf-8")
    assert "super::invoice_service::InvoiceService" in (
        host / "crates/billing-core/src/invoice/consumer.rs"
    ).read_text(encoding="utf-8")
    test_text = (host / "crates/billing-core/tests/invoice_service.rs").read_text(encoding="utf-8")
    assert "billing_core::invoice::invoice_service::InvoiceService" in test_text
    assert "billing_core::invoice::InvoiceService" in test_text
    assert applied["rust"]["status"] == "complete"
    assert applied["rust"]["rolled_back"] is False
    assert applied["rust"]["native_postflight"]["exact_diff"]["passed"] is True
    assert all(contents == (host / path).read_bytes() for path, contents in protected.items())
    _native(host, tmp_path / "native-after")

    check_result, checked, _ = _invoke(host, plan, "check")
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert checked["rust"]["status"] == "complete"
    assert checked["rust"]["old_identity_remaining"] == []
    assert all(row["passed"] for row in checked["rust"]["native_postflight"].values())


def test_rust_leaf_directory_module_move_is_bounded_and_native(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source_file = host / "crates/billing-core/src/invoice/service.rs"
    source_dir = source_file.parent / "service"
    source_dir.mkdir()
    source_file.rename(source_dir / "mod.rs")
    plan = _plan(
        host,
        source="crates/billing-core/src/invoice/service",
        destination="crates/billing-core/src/invoice/invoice_service",
        mode="directory",
    )

    preview_result, preview, _ = _invoke(host, plan, "dry-run")
    assert preview_result.returncode == 0, preview_result.stdout + preview_result.stderr
    assert preview["rust"]["status"] == "complete"
    assert preview["rust"]["move_shape"] == "leaf-directory-module"

    applied_result, applied, _ = _invoke(host, plan, "apply")
    assert applied_result.returncode == 0, applied_result.stdout + applied_result.stderr
    assert not source_dir.exists()
    assert (source_dir.parent / "invoice_service/mod.rs").is_file()
    assert applied["rust"]["native_postflight"]["exact_diff"]["passed"] is True
    _native(host, tmp_path / "native-directory")


def test_rust_same_destination_lifecycle_clears_stale_success_and_recovers(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    plan = _plan(host)
    success, report, report_dir = _invoke(host, plan, "dry-run")
    assert success.returncode == 0
    successful_markdown = (report_dir / "report.md").read_text(encoding="utf-8")
    assert report["rust"]["status"] == "complete"

    source = host / "crates/billing-core/src/invoice/service.rs"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\npub fn malformed( {\n", encoding="utf-8")
    failed, failed_report, _ = _invoke(host, plan, "dry-run")
    assert failed.returncode == 2
    assert failed_report["rust"]["status"] == "failed"
    assert failed_report["rust"]["failure_kind"] == "cargo_check_failed"
    assert (report_dir / "report.md").read_text(encoding="utf-8") != successful_markdown
    assert "Status: `failed`" in (report_dir / "report.md").read_text(encoding="utf-8")

    source.write_text(original, encoding="utf-8")
    recovered, recovered_report, _ = _invoke(host, plan, "dry-run")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert recovered_report["rust"]["status"] == "complete"
    assert recovered_report["rust"]["failure_kind"] == "none"
    assert not recovered_report["rust"].get("native_error")


@pytest.mark.parametrize(
    ("case", "path", "content", "expected_kind"),
    [
        (
            "include",
            "crates/billing-core/src/invoice/consumer.rs",
            'include!("generated.rs");\n',
            "rust_include_macro_ambiguity",
        ),
        (
            "path-attribute",
            "crates/billing-core/src/invoice/mod.rs",
            '#[path = "service.rs"]\npub mod service;\n',
            "rust_path_attribute_ambiguity",
        ),
        (
            "cfg-module",
            "crates/billing-core/src/invoice/mod.rs",
            '#[cfg(unix)]\npub mod service;\npub use service::InvoiceService;\n',
            "rust_cfg_module_ambiguity",
        ),
        (
            "macro-generated",
            "crates/billing-core/src/invoice/mod.rs",
            'macro_rules! declare { ($name:ident) => { mod $name; } }\ndeclare!(service);\n',
            "rust_macro_module_ambiguity",
        ),
        (
            "reflective-text",
            "crates/billing-core/src/invoice/consumer.rs",
            'pub const MODULE: &str = "crate::invoice::service";\n',
            "rust_unproved_textual_reference",
        ),
        (
            "build-output",
            "crates/billing-core/build.rs",
            'fn main() { std::fs::write(std::env::var("OUT_DIR").unwrap(), "service").unwrap(); }\n',
            "rust_build_output_ambiguity",
        ),
    ],
)
def test_rust_refuses_unproved_macro_cfg_include_path_build_and_text_shapes(
    tmp_path: Path,
    case: str,
    path: str,
    content: str,
    expected_kind: str,
) -> None:
    host = _copy_host(tmp_path, case)
    plan = _plan(host)
    target = host / path
    if case in {"path-attribute", "cfg-module", "macro-generated"}:
        target.write_text(content, encoding="utf-8")
    else:
        target.write_text(target.read_text(encoding="utf-8") + content, encoding="utf-8")
    before = _tree_state(host)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    assert report["rust"]["status"] == "partial"
    assert any(row["kind"] == expected_kind for row in report["rust"]["blocked"])
    assert _tree_state(host) == before
    apply, _, _ = _invoke(host, plan, "apply")
    assert apply.returncode == 2
    assert _tree_state(host) == before


def test_rust_refuses_excluded_symlink_unsafe_and_ambiguous_move_shapes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    generated = _plan(
        host,
        source="generated/GeneratedInvoice.rs",
        destination="generated/RenamedInvoice.rs",
    )
    result, report, _ = _invoke(host, generated, "dry-run")
    assert result.returncode == 0
    assert report["rust"]["status"] == "partial"
    assert any(row["kind"] == "rust_excluded_move_path" for row in report["rust"]["blocked"])

    host = _copy_host(tmp_path, "symlink")
    source = host / "crates/billing-core/src/invoice/service.rs"
    source.unlink()
    os.symlink(FIXTURE / "symlink-target/External.rs", source)
    plan = _plan(host)
    result, report, _ = _invoke(host, plan, "dry-run")
    assert result.returncode == 0
    assert report["rust"]["status"] == "partial"
    assert any(row["kind"] == "rust_symlink_boundary" for row in report["rust"]["blocked"])

    host = _copy_host(tmp_path, "multi")
    plan = _plan(
        host,
        moves=[
            {
                "from": "crates/billing-core/src/invoice/service.rs",
                "to": "crates/billing-core/src/invoice/invoice_service.rs",
                "mode": "file",
            },
            {
                "from": "crates/billing-core/src/invoice/consumer.rs",
                "to": "crates/billing-core/src/invoice/invoice_consumer.rs",
                "mode": "file",
            },
        ],
    )
    result, report, _ = _invoke(host, plan, "dry-run")
    assert result.returncode == 0
    assert report["rust"]["status"] == "partial"
    assert any(row["kind"] == "rust_move_count_ambiguous" for row in report["rust"]["blocked"])

    host = _copy_host(tmp_path, "unsafe")
    plan = _plan(host, source="../outside.rs", destination="crates/outside.rs")
    result, report, report_dir = _invoke(host, plan, "dry-run")
    assert result.returncode == 2
    assert report == {}
    assert not report_dir.exists()


@pytest.mark.parametrize(
    ("case", "tool", "body", "expected_kind"),
    [
        ("missing", "cargo", None, "rust_tool_missing"),
        ("old", "cargo", "echo 'cargo 1.84.1 (fixture)'\n", "rust_tool_too_old"),
        ("broken", "cargo", "echo broken >&2\nexit 7\n", "rust_tool_probe_failed"),
        ("missing-clippy", "clippy", None, "rust_optional_native_tool_missing"),
        ("missing-rustfmt", "rustfmt", None, "rust_optional_native_tool_missing"),
    ],
)
def test_rust_missing_old_broken_and_optional_tools_are_partial_not_permanent_unsupported(
    tmp_path: Path,
    case: str,
    tool: str,
    body: str | None,
    expected_kind: str,
) -> None:
    host = _copy_host(tmp_path, case)
    value = str(host / f"{case}-tool")
    if body is not None:
        _fake_tool(Path(value), body)
    overrides = {
        "cargo": str(CARGO), "rustc": str(RUSTC),
        "clippy": str(CLIPPY), "rustfmt": str(RUSTFMT),
    }
    overrides[tool] = value
    plan = _plan(host, **overrides)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 0
    assert report["rust"]["status"] == "partial"
    assert report["rust"]["status"] != "unsupported"
    assert any(row["kind"] == expected_kind for row in report["rust"]["blocked"])


def test_rust_malformed_manifest_source_and_stale_lock_are_failed(tmp_path: Path) -> None:
    cases = []
    malformed_manifest = _copy_host(tmp_path, "manifest")
    (malformed_manifest / "Cargo.toml").write_text("[workspace\n", encoding="utf-8")
    cases.append((malformed_manifest, "cargo_metadata_failed"))

    malformed_source = _copy_host(tmp_path, "source")
    shutil.copy2(
        FIXTURE / "malformed/Broken.rs",
        malformed_source / "crates/billing-core/src/invoice/service.rs",
    )
    cases.append((malformed_source, "cargo_check_failed"))

    stale = _copy_host(tmp_path, "lock")
    lock = stale / "Cargo.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace(
            '\n[[package]]\nname = "rust-move-smoke"\nversion = "0.1.0"\n'
            'dependencies = [\n "billing-core",\n]\n',
            "",
        ),
        encoding="utf-8",
    )
    cases.append((stale, "cargo_check_failed"))

    for host, expected in cases:
        plan = _plan(host)
        before = _tree_state(host)
        result, report, _ = _invoke(host, plan, "dry-run")
        assert result.returncode == 2
        assert report["rust"]["status"] == "failed"
        assert report["rust"]["failure_kind"] == expected
        assert _tree_state(host) == before


def test_rust_native_and_unexpected_mutation_failures_roll_back_everything(tmp_path: Path) -> None:
    for case in ("native", "mutation"):
        host = _copy_host(tmp_path, case)
        real = json.dumps(str(CARGO))
        if case == "native":
            body = (
                "if [ -f crates/billing-core/src/invoice/invoice_service.rs ] "
                "&& [ \"${1:-}\" = check ]; then echo forced >&2; exit 9; fi\n"
                f"exec {real} \"$@\"\n"
            )
        else:
            marker = json.dumps(str(host / "generated/GeneratedInvoice.rs"))
            body = (
                "if [ -f crates/billing-core/src/invoice/invoice_service.rs ] "
                "&& [ \"${1:-}\" = fmt ]; then "
                f"printf '%s\\n' '// unexpected' >> {marker}; fi\n"
                f"exec {real} \"$@\"\n"
            )
        wrapper = _fake_tool(host / f"cargo-{case}", body)
        plan = _plan(host, cargo=str(wrapper))
        before = _tree_state(host)

        result, report, _ = _invoke(host, plan, "apply")

        assert result.returncode == 2
        assert report["rust"]["status"] == "failed"
        assert report["rust"]["rolled_back"] is True
        assert report["rust"]["failure_kind"] in {
            "cargo_check_failed", "exact_diff_failed"
        }
        assert _tree_state(host) == before
        assert (host / "crates/billing-core/src/invoice/service.rs").is_file()
        assert not (host / "crates/billing-core/src/invoice/invoice_service.rs").exists()


def test_rust_stale_source_fingerprint_rejected_and_copied_closure_runs(tmp_path: Path) -> None:
    stale_host = _copy_host(tmp_path, "stale")
    stale_plan = _plan(stale_host)
    before = _tree_state(stale_host)
    result, report, _ = _invoke(
        stale_host, stale_plan, "apply", expected_source_sha256="0" * 64
    )
    assert result.returncode == 2
    assert report["rust"]["status"] == "failed"
    assert report["rust"]["failure_kind"] == "stale_source_snapshot"
    assert _tree_state(stale_host) == before

    host = _copy_host(tmp_path, "copied")
    plan = _plan(host)
    installed = host / ".agents/skills/move-path/scripts"
    installed.mkdir(parents=True)
    copied = installed / "rust_module_move.py"
    shutil.copy2(SCRIPT, copied)
    outside = tmp_path / "outside"
    outside.mkdir()

    result, report, _ = _invoke(host, plan, "apply", script=copied, cwd=outside)

    assert result.returncode == 0, result.stdout + result.stderr
    assert report["rust"]["status"] == "complete"
    assert report["rust"]["native_postflight"]["exact_diff"]["passed"] is True
    assert (host / "crates/billing-core/src/invoice/invoice_service.rs").is_file()
    source = copied.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "tree_sitter" not in source
    assert "private rustc" not in source
    assert "cargo install" not in source
