"""Accepted Rust semantic-lead to read-only shadow-proposal proof."""

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
SKILL = ROOT / ".claude/skills/unify-shadows"
SCRIPT = SKILL / "scripts/propose_rust.py"
FACTS_SCRIPT = ROOT / ".claude/skills/map-subsystem/scripts/rust_semantic_facts.py"
DETECTOR = ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_rust_semantic.py"
FIXTURE = ROOT / "tests/fixtures/rust-semantic-family/host"
PYTHON = Path(sys.executable)
FINDING_ID = "RSD-01"
QUERIES = [
    "summarize_invoice",
    "build_statement",
    "wrapper_decoy",
    "policy_decoy",
    "unsafe_dormant",
]
SHAPES = (
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
)
CARGO = shutil.which("cargo")
RUSTC = shutil.which("rustc")
RUST_ANALYZER = shutil.which("rust-analyzer")
CLIPPY = shutil.which("cargo-clippy")
RUSTFMT = shutil.which("rustfmt")
pytestmark = pytest.mark.skipif(
    any(tool is None for tool in (CARGO, RUSTC, RUST_ANALYZER, CLIPPY, RUSTFMT)),
    reason="Rust 1.85+, Cargo, rust-analyzer, Clippy, and rustfmt are required",
)


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _native(host: Path, target: Path) -> None:
    env = {**os.environ, "CARGO_NET_OFFLINE": "true", "CARGO_TARGET_DIR": str(target)}
    commands = (
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
    )
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
        "semantic-smoke",
        cwd=host,
        env=env,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout == "33\n"


def _bytes(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".agents", ".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


@pytest.fixture(scope="module")
def accepted_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("rust-unify-accepted")
    host = base / "host"
    shutil.copytree(FIXTURE, host)
    (host / "semantic-core/src/linked.rs").symlink_to("dormant.rs")
    facts = host / "reports/rust-semantic-facts/unify-shadows.json"
    command = [
        str(PYTHON),
        "-I",
        "-S",
        str(FACTS_SCRIPT),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output",
        str(facts),
        "--cargo-target-dir",
        str(base / "facts-target"),
    ]
    for query in QUERIES:
        command.extend(("--query", query))
    produced = _run(*command, cwd=host)
    assert produced.returncode == 0, produced.stdout + produced.stderr
    assert json.loads(facts.read_text(encoding="utf-8"))["status"] == "complete"
    analysis_dir = host / "reports/semantic-duplication/rust"
    detected = _run(
        str(PYTHON),
        "-I",
        "-S",
        str(DETECTOR),
        "--project-root",
        str(host),
        "--target",
        "semantic-core",
        "--output-dir",
        str(analysis_dir),
        "--facts",
        str(facts),
        cwd=host,
    )
    assert detected.returncode == 0, detected.stdout + detected.stderr
    analysis = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["status"] == "complete"
    assert [row["id"] for row in analysis["confirmed"]] == [FINDING_ID]
    assert any(row.get("function") == "unsafe_dormant" for row in analysis["uncertain"])
    return host


def _host(bundle: Path, tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(bundle, host, symlinks=True)
    return host


def _propose(
    skill: Path,
    host: Path,
    *,
    shape: str = "share_utilities",
    name: str = FINDING_ID,
    analysis: Path | None = None,
    facts: Path | None = None,
    isolated: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    analysis = analysis or host / "reports/semantic-duplication/rust/analysis.json"
    facts = facts or host / "reports/rust-semantic-facts/unify-shadows.json"
    output = host / "reports/unify-shadows" / name
    proposal = output / "proposal.md"
    evidence = output / "evidence.json"
    prefix = (str(PYTHON), "-I", "-S") if isolated else (str(PYTHON),)
    result = _run(
        *prefix,
        str(skill / "scripts/propose_rust.py"),
        "--analysis",
        str(analysis),
        "--facts",
        str(facts),
        "--finding-id",
        FINDING_ID,
        "--shape",
        shape,
        "--project-root",
        str(host),
        "--proposal",
        str(proposal),
        "--evidence",
        str(evidence),
        cwd=host,
    )
    return result, proposal, evidence


def _write_analysis(host: Path, name: str, transform) -> Path:
    source = host / "reports/semantic-duplication/rust/analysis.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    transform(payload)
    path = source.parent / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_rust_confirmed_lead_reaches_read_only_proposal_with_native_proof(
    accepted_bundle: Path,
    tmp_path: Path,
) -> None:
    host = _host(accepted_bundle, tmp_path)
    assert 'edition = "2024"' in (host / "semantic-core/Cargo.toml").read_text()
    before = _bytes(host)
    _native(host, tmp_path / "native-before")
    result, proposal, evidence = _propose(SKILL, host)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    for heading in (
        "## Members and bounded impact",
        "## Accepted static evidence",
        "## Proposed action",
        "## Caller impact",
        "## Native Rust test matrix",
        "## Explicit non-claims",
        "## Stop condition",
        "## Authorization and handoff",
    ):
        assert heading in rendered
    for phrase in (
        "traits and blanket implementations",
        "generics",
        "macro expansion",
        "cfg",
        "unsafe or FFI",
        "runtime behavior",
        "external API",
        "semver compatibility",
    ):
        assert phrase in rendered
    assert "not behavioral equivalence" in rendered
    assert "Human approval is required" in rendered
    assert f"/fix-workflow semantic:{FINDING_ID}" in rendered
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["status"] == "proposal_ready_for_human_review"
    assert payload["language"] == "rust"
    assert payload["shape_source"] == "explicit_operator_input_for_read_only_draft"
    assert payload["authorization"] == "human_review_required"
    assert payload["source_mutations"] == 0
    assert len(payload["source_evidence"]) == 2
    assert len(payload["caller_evidence"]) == 5
    scope = json.loads((proposal.parent / "scope.json").read_text(encoding="utf-8"))
    assert scope["paths"] == [
        "semantic-core/src/duplication/caller_a.rs",
        "semantic-core/src/duplication/caller_b.rs",
        "semantic-core/src/duplication/mod.rs",
    ]
    assert _bytes(host) == before
    _native(host, tmp_path / "native-after")


@pytest.mark.parametrize("shape", SHAPES)
def test_rust_shapes_remain_drafts_and_never_static_authorization(
    accepted_bundle: Path,
    tmp_path: Path,
    shape: str,
) -> None:
    host = _host(accepted_bundle, tmp_path, shape)
    result, proposal, evidence = _propose(SKILL, host, shape=shape, name=shape)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    action = rendered.split("## Proposed action\n", 1)[1].split("\n## Caller impact", 1)[0]
    assert f"Template: `{shape}`" in action
    assert "not authorization" in action.lower()
    assert json.loads(evidence.read_text(encoding="utf-8"))["shape"] == shape
    if shape == "keep_separate_document_why":
        lowered = action.lower()
        assert "merge" not in lowered
        assert "migrat" not in lowered
        assert "consolidat" not in lowered


def test_rust_clean_and_boundary_only_evidence_must_not_fire(
    accepted_bundle: Path,
    tmp_path: Path,
) -> None:
    host = _host(accepted_bundle, tmp_path)
    clean = _write_analysis(
        host,
        "clean",
        lambda payload: (
            payload.__setitem__("confirmed", []),
            payload.__setitem__("summary", {**payload["summary"], "review_required_leads": 0}),
        ),
    )
    clean_result, clean_proposal, _ = _propose(
        SKILL,
        host,
        analysis=clean,
        name="clean",
    )
    assert clean_result.returncode == 2
    assert "missing from confirmed" in clean_result.stderr
    assert not clean_proposal.parent.exists()

    boundary = _write_analysis(
        host,
        "boundary",
        lambda payload: payload["confirmed"][0]["functions"][0].update(scope="nested_or_impl"),
    )
    boundary_result, boundary_proposal, _ = _propose(
        SKILL,
        host,
        analysis=boundary,
        name="boundary",
    )
    assert boundary_result.returncode == 2
    assert "top-level free functions" in boundary_result.stderr
    assert not boundary_proposal.parent.exists()


@pytest.mark.parametrize("status", ("partial", "failed"))
def test_rust_partial_or_failed_upstream_is_not_a_proposal(
    accepted_bundle: Path,
    tmp_path: Path,
    status: str,
) -> None:
    host = _host(accepted_bundle, tmp_path, status)
    analysis = _write_analysis(
        host,
        status,
        lambda payload: payload.__setitem__("status", status),
    )
    result, proposal, _ = _propose(
        SKILL,
        host,
        analysis=analysis,
        name=status,
    )
    assert result.returncode == 2
    assert "requires complete Rust semantic evidence" in result.stderr
    assert not proposal.parent.exists()


def test_rust_stale_source_rejects_without_replacing_prior_proposal(
    accepted_bundle: Path,
    tmp_path: Path,
) -> None:
    host = _host(accepted_bundle, tmp_path)
    passed, proposal, evidence = _propose(SKILL, host, name="stale")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    prior = {path.name: path.read_bytes() for path in proposal.parent.iterdir()}
    source = host / "semantic-core/src/duplication/mod.rs"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    failed, _, _ = _propose(SKILL, host, name="stale")
    assert failed.returncode == 2
    assert "stale" in failed.stderr
    assert {path.name: path.read_bytes() for path in proposal.parent.iterdir()} == prior
    assert evidence.is_file()


def test_rust_copied_layout_is_stdlib_only_and_independently_runnable(
    accepted_bundle: Path,
    tmp_path: Path,
) -> None:
    host = _host(accepted_bundle, tmp_path)
    copied = tmp_path / "installed/.agents/skills/unify-shadows"
    shutil.copytree(SKILL, copied)
    result, proposal, evidence = _propose(
        copied,
        host,
        name="copied",
        isolated=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert proposal.is_file() and evidence.is_file()
    runtime = (copied / "scripts/propose_rust.py").read_text(encoding="utf-8")
    assert "rust_semantic_facts" not in runtime
    assert "detect_rust_semantic" not in runtime
    assert "scripts/_lib" not in runtime


def test_rust_consumer_rejects_unsafe_output_and_preserves_sources(
    accepted_bundle: Path,
    tmp_path: Path,
) -> None:
    host = _host(accepted_bundle, tmp_path)
    before = _bytes(host)
    output_root = host / "reports/unify-shadows"
    output_root.mkdir(parents=True)
    (output_root / "linked").symlink_to(host, target_is_directory=True)
    result, proposal, _ = _propose(SKILL, host, name="linked")
    assert result.returncode == 2
    assert "symbolic link" in result.stderr
    assert not proposal.exists()
    assert _bytes(host) == before


def test_rust_consumer_reuses_provider_instead_of_copying_semantic_analysis() -> None:
    adapter_lines = len(SCRIPT.read_text(encoding="utf-8").splitlines())
    provider_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in (FACTS_SCRIPT, DETECTOR)
    )
    duplicated = adapter_lines + provider_lines
    reused = adapter_lines
    assert (duplicated - reused) / duplicated >= 0.40
