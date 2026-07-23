"""Rust folder proposals preserve the review boundary and prove feasibility."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/propose-folder-reorganization"
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
    skill: Path, host: Path, prefix: str, name: str, judgment: str = "split"
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    report = host / "reports/propose-folder-reorganization" / name
    result = _run(
        sys.executable,
        str(skill / "scripts/propose_rust.py"),
        "--project-root",
        str(host),
        "--parent",
        "crates/billing-core/src",
        "--prefix",
        prefix,
        "--cluster-judgment",
        judgment,
        "--project-convention",
        "allow-module-group",
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


def _apply_plan(host: Path, payload: dict) -> None:
    for row in payload["cluster_files"]:
        source = host / row["current_path"]
        destination = host / row["new_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    for edit in payload["exact_source_edits"]:
        path = host / edit["path"]
        text = path.read_text(encoding="utf-8")
        assert edit["before"] in text
        path.write_text(text.replace(edit["before"], edit["after"], 1), encoding="utf-8")
    module = payload["new_module_file"]
    path = host / module["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(module["contents"], encoding="utf-8")


def test_positive_folder_proposal_is_distinct_source_preserving_and_executable(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    before = _hashes(host)
    result, inspection, proposal = _propose(SKILL, host, "billing", "positive")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _hashes(host) == before
    payload = _load(inspection)
    assert payload["status"] == "ready_for_human_review"
    assert payload["recommendation"] == "review_folder_plan"
    assert payload["human_review_required"] is True
    assert len(payload["cluster_files"]) == 3
    assert payload["new_module_file"]["path"] == "crates/billing-core/src/billing/mod.rs"
    assert payload["public_compatibility"]["claim"] == "not_proved"
    assert not any(
        row["path"].endswith("cohesive/shipping.rs") for row in payload["exact_source_edits"]
    )
    assert payload["native_verification"]["status"] == "passed"
    assert "## Exact move and edit plan" in proposal.read_text(encoding="utf-8")

    _apply_plan(host, payload)
    for command in (
        ("cargo", "metadata", "--locked", "--offline", "--format-version", "1"),
        (
            "cargo",
            "check",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
        ),
        (
            "cargo",
            "test",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
        ),
        (
            "cargo",
            "clippy",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
            "--",
            "-D",
            "warnings",
        ),
        ("cargo", "fmt", "--all", "--", "--check"),
    ):
        native = _run(*command, cwd=host)
        assert native.returncode == 0, native.stdout + native.stderr
    smoke = _run(
        "cargo", "run", "-p", "billing-smoke", "--locked", "--offline", "--quiet", cwd=host
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout.strip() == "42:valid:40"


def test_clean_cohesive_and_unsupported_shapes_never_emit_move_plan(tmp_path: Path) -> None:
    host = _host(tmp_path)
    result, inspection, _ = _propose(SKILL, host, "missing", "below")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(inspection)["recommendation"] == "defer_cluster_below_threshold"

    result, inspection, _ = _propose(SKILL, host, "billing", "cohesive", judgment="cohesive")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(inspection)["cluster_files"] == []

    source = host / "crates/billing-core/src/billing_parser.rs"
    source.write_text(
        'include!("generated.rs");\n' + source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    result, inspection, _ = _propose(SKILL, host, "billing", "include")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _load(inspection)
    assert payload["status"] == "partial"
    assert payload["cluster_files"] == []
    assert "include_macro" in payload["defer_signals"]


def test_failure_replaces_stale_plan_and_copied_layout_preserves_closure(tmp_path: Path) -> None:
    host = _host(tmp_path)
    result, inspection, proposal = _propose(SKILL, host, "billing", "lifecycle")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _load(inspection)["cluster_files"]

    (host / "Cargo.toml").write_text("[workspace\n", encoding="utf-8")
    result, inspection, proposal = _propose(SKILL, host, "billing", "lifecycle")
    assert result.returncode == 2
    assert _load(inspection)["cluster_files"] == []
    assert "Exact move and edit plan" not in proposal.read_text(encoding="utf-8")

    copied_host = _host(tmp_path, "copied-host")
    installed = copied_host / ".agents/skills/propose-folder-reorganization"
    shutil.copytree(SKILL, installed)
    shutil.copy2(COMMON, installed / "scripts/rust_project_evidence.py")
    replay, copied_json, _ = _propose(installed, copied_host, "billing", "copied")
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert _load(copied_json)["status"] == "ready_for_human_review"
    assert str(ROOT) not in (installed / "scripts/propose_rust.py").read_text(encoding="utf-8")
