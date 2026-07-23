"""Bounded Rust boundary proposals reach honest final artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/propose-boundary"
COMMON = ROOT / ".claude/skills/_common/scripts/rust_proposal_evidence.py"
FIXTURE = ROOT / "tests/fixtures/rust-proposals/host"
REQUIRED = ("cargo", "rustc", "rustfmt")
pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in REQUIRED),
    reason="stable Rust tools are required",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and (path.suffix == ".rs" or path.name in {"Cargo.toml", "Cargo.lock"})
    }


def _propose(
    skill: Path, host: Path, target: str, name: str
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    report = host / "reports/propose-boundary" / name
    result = _run(
        sys.executable,
        str(skill / "scripts/propose_rust.py"),
        "--project-root",
        str(host),
        "--target",
        target,
        "--inspection",
        str(report / "inspection.json"),
        "--proposal",
        str(report / "proposal.md"),
        "--smoke-package",
        "billing-smoke",
        "--smoke-expected",
        "42:valid:40",
        cwd=host,
    )
    return result, report / "inspection.json", report / "proposal.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_positive_boundary_proposal_is_source_preserving_and_native_checked(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _hashes(host)
    result, inspection, proposal = _propose(
        SKILL, host, "crates/billing-core/src/legacy", "positive"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _hashes(host) == before
    payload = _load(inspection)
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "review_boundary"
    assert payload["language"] == "rust"
    assert payload["human_review_required"] is True
    assert payload["candidate_seams"][0]["cluster_id"] == "quote"
    assert "normalize" not in payload["candidate_seams"][0]["proposed_public_api"]
    assert not any(
        row["file"].endswith("path_decoy.rs")
        for row in payload["caller_impact"]
    )
    assert payload["native_verification"]["status"] == "passed"
    assert payload["native_verification"]["smoke"]["stdout"] == "42:valid:40"
    assert all(
        "--locked" in command or command.startswith("cargo fmt")
        for command in payload["native_verification"]["commands"]
    )
    rendered = proposal.read_text(encoding="utf-8")
    assert "## Human review boundary" in rendered
    assert "## Explicit non-claims" in rendered
    assert "macros" in rendered and "traits" in rendered and "FFI" in rendered


def test_clean_and_must_not_fire_inputs_do_not_invent_a_seam(tmp_path: Path) -> None:
    host = _host(tmp_path)
    result, inspection, _ = _propose(SKILL, host, "crates/billing-core/src/cohesive", "clean")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(inspection)
    assert payload["status"] == "complete"
    assert payload["recommendation"] == "defer_no_seam"
    assert payload["candidate_seams"] == []

    result, inspection, _ = _propose(
        SKILL, host, "crates/billing-core/src/legacy/generated_decoy.rs", "generated"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(inspection)["recommendation"] == "defer_excluded_target"


def test_partial_failure_and_stale_artifacts_fail_closed(tmp_path: Path) -> None:
    host = _host(tmp_path)
    quote = host / "crates/billing-core/src/legacy/quote.rs"
    quote.write_text("#[cfg(any())]\n" + quote.read_text(encoding="utf-8"), encoding="utf-8")
    result, inspection, _ = _propose(SKILL, host, "crates/billing-core/src/legacy", "lifecycle")
    assert result.returncode == 0, result.stdout + result.stderr
    partial = _load(inspection)
    assert partial["status"] == "partial"
    assert partial["candidate_seams"] == []
    assert "cfg_variants" in partial["defer_signals"]

    quote.write_text("pub fn broken( {\n", encoding="utf-8")
    result, inspection, proposal = _propose(
        SKILL, host, "crates/billing-core/src/legacy", "lifecycle"
    )
    assert result.returncode == 2
    failed = _load(inspection)
    assert failed["status"] == "failed"
    assert failed["candidate_seams"] == []
    assert "review_boundary" not in proposal.read_text(encoding="utf-8")


def test_copied_layout_runs_with_only_declared_common_evidence_dependency(tmp_path: Path) -> None:
    host = _host(tmp_path)
    installed = host / ".agents/skills/propose-boundary"
    shutil.copytree(SKILL, installed)
    shutil.copy2(COMMON, installed / "scripts/rust_project_evidence.py")
    assert not installed.resolve().is_relative_to(ROOT.resolve())

    result, inspection, _ = _propose(installed, host, "crates/billing-core/src/legacy", "copied")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(inspection)["recommendation"] == "review_boundary"
    assert str(ROOT) not in (installed / "scripts/propose_rust.py").read_text(encoding="utf-8")
