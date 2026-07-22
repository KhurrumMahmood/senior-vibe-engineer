"""Structured Go semantic-finding proposal handoff proof."""
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
DETECTOR = ROOT / ".claude" / "skills" / "find-semantic-duplication"
SKILL = ROOT / ".claude" / "skills" / "unify-shadows"
FIXTURE = ROOT / "tests" / "fixtures" / "find-semantic-duplication-go"
PYTHON = Path(sys.executable)
FINDING_ID = "GO-SD-0001"
SHAPES = (
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
)


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    go = shutil.which("go")
    if not go:
        pytest.skip("Go toolchain is unavailable")
    env = {
        **os.environ,
        "PATH": f"{Path(go).parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GOCACHE": str(tmp_path / "go-cache"),
        "GOTOOLCHAIN": "local",
    }
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    findings = host / "reports" / "semantic-duplication" / "go" / "findings.json"
    scan = _run(
        str(PYTHON),
        str(DETECTOR / "scripts" / "detect_go_semantic.py"),
        "--target", ".", "--project-root", str(host),
        "--report-dir", str(findings.parent), cwd=host, env=env,
    )
    assert scan.returncode == 0, scan.stdout + scan.stderr
    return host, env, findings


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.go"))
        if "reports" not in path.relative_to(host).parts
    }


def _propose(
    skill: Path,
    host: Path,
    env: dict[str, str],
    findings: Path,
    *,
    name: str = FINDING_ID,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / "reports" / "unify-shadows" / name
    proposal = output / "proposal.md"
    evidence = output / "evidence.json"
    result = _run(
        str(PYTHON), str(skill / "scripts" / "propose_go.py"),
        "--findings", str(findings), "--finding-id", FINDING_ID,
        "--project-root", str(host), "--proposal", str(proposal),
        "--evidence", str(evidence), cwd=host, env=env,
    )
    return result, proposal, evidence


def test_confirmed_go_finding_reaches_read_only_proposal(tmp_path: Path) -> None:
    host, env, findings = _host(tmp_path)
    before = _hashes(host)

    result, proposal, evidence = _propose(SKILL, host, env, findings)

    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    for heading in (
        "## Members and source impact",
        "## Evidence",
        "## Proposed action",
        "## Caller impact",
        "## Native Go test matrix",
        "## Stop condition",
        "## Authorization and handoff",
    ):
        assert heading in rendered
    assert "go test ./..." in rendered
    assert "Human approval is required" in rendered
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["status"] == "proposal_ready_for_human_review"
    assert payload["language"] == "go"
    assert payload["finding_id"] == FINDING_ID
    assert len(payload["source_evidence"]) == 2
    assert json.loads((proposal.parent / "scope.json").read_text(encoding="utf-8"))["paths"] == [
        "semantic.go"
    ]
    assert _hashes(host) == before
    native = _run("go", "test", "./...", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr


def test_go_proposal_rejects_unconfirmed_and_copied_closure_runs(tmp_path: Path) -> None:
    host, env, findings = _host(tmp_path)
    payload = json.loads(findings.read_text(encoding="utf-8"))
    item = payload["confirmed"].pop()
    payload["findings"] = []
    item["investigation_status"] = "uncertain"
    payload["uncertain"].append(item)
    unconfirmed = findings.parent / "unconfirmed.json"
    unconfirmed.write_text(json.dumps(payload), encoding="utf-8")
    failed, proposal, _ = _propose(SKILL, host, env, unconfirmed, name="unconfirmed")
    assert failed.returncode == 2
    assert "is not confirmed" in failed.stderr
    assert not proposal.parent.exists()

    copied = tmp_path / "on-demand" / "unify-shadows"
    shutil.copytree(SKILL, copied)
    passed, proposal, _ = _propose(copied, host, env, findings, name="copied")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert proposal.is_file()
    assert (copied / "scripts" / "propose_go.py").is_file()


@pytest.mark.parametrize("shape", SHAPES)
def test_go_proposal_preserves_each_supported_shape(tmp_path: Path, shape: str) -> None:
    host, env, findings = _host(tmp_path)
    payload = json.loads(findings.read_text(encoding="utf-8"))
    payload["confirmed"][0]["consolidation_shape"] = shape
    payload["findings"][0]["consolidation_shape"] = shape
    shaped = findings.parent / f"{shape}.json"
    shaped.write_text(json.dumps(payload), encoding="utf-8")

    result, proposal, evidence = _propose(SKILL, host, env, shaped, name=shape)

    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    action = rendered.split("## Proposed action\n", 1)[1].split("\n## Caller impact", 1)[0]
    assert f"Template: `{shape}`" in action
    assert json.loads(evidence.read_text(encoding="utf-8"))["shape"] == shape
    if shape == "keep_separate_document_why":
        assert "merge" not in action.lower()
        assert "migrat" not in action.lower()


def test_go_proposal_refuses_partial_upstream_evidence(tmp_path: Path) -> None:
    host, env, findings = _host(tmp_path)
    payload = json.loads(findings.read_text(encoding="utf-8"))
    payload["status"] = "partial"
    partial = findings.parent / "partial.json"
    partial.write_text(json.dumps(payload), encoding="utf-8")

    result, proposal, _ = _propose(SKILL, host, env, partial, name="partial")

    assert result.returncode == 2
    assert "refresh complete evidence" in result.stderr
    assert not proposal.parent.exists()


def test_go_proposal_rejects_symlinked_output_path(tmp_path: Path) -> None:
    host, env, findings = _host(tmp_path)
    output_root = host / "reports" / "unify-shadows"
    output_root.mkdir(parents=True)
    os.symlink(host, output_root / "linked")

    result, proposal, _ = _propose(SKILL, host, env, findings, name="linked")

    assert result.returncode == 2
    assert "symbolic link" in result.stderr
    assert not proposal.exists()
