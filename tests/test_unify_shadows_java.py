"""Java semantic-finding proposal consumer and approval-boundary proof."""
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
DETECTOR = ROOT / ".claude/skills/find-semantic-duplication"
SKILL = ROOT / ".claude/skills/unify-shadows"
FIXTURE = ROOT / "tests/fixtures/find-semantic-duplication-java/host"
PYTHON = Path(sys.executable)
FINDING_ID = "JAVA-SD-0001"
SHAPES = (
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
)


def _jdk() -> Path:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        pytest.skip("JDK is unavailable")
    version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
    rendered = version.stdout + version.stderr
    if version.returncode or "javac " not in rendered or int(rendered.split("javac ", 1)[1].split(".", 1)[0]) < 17:
        pytest.skip("JDK 17+ is unavailable")
    return Path(javac).parent


def _run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _host(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    env = {**os.environ, "PATH": f"{_jdk()}{os.pathsep}{os.environ.get('PATH', '')}"}
    classes = tmp_path / "classes"
    sources = sorted(str(path) for path in (host / "src/main/java").rglob("*.java"))
    tests = sorted(str(path) for path in (host / "src/test/java").rglob("*.java"))
    compiled = _run("javac", "--release", "17", "-d", str(classes), *sources, *tests, cwd=host, env=env)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    native = _run("java", "-cp", str(classes), "example.SemanticFixtureTest", cwd=host, env=env)
    assert native.returncode == 0, native.stdout + native.stderr
    findings = host / "reports/semantic-duplication/java/findings.json"
    scan = _run(
        str(PYTHON), "-I", "-S", str(DETECTOR / "scripts/detect_java_semantic.py"),
        "--target", "src/main/java", "--project-root", str(host),
        "--report-dir", str(findings.parent), cwd=host, env=env,
    )
    assert scan.returncode == 0, scan.stdout + scan.stderr
    return host, env, findings


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*.java"))
        if "reports" not in path.relative_to(host).parts and not path.is_symlink()
    }


def _consumer_fingerprint(skill: Path) -> str:
    return f"sha256:{hashlib.sha256((skill / 'scripts/propose_java.py').read_bytes()).hexdigest()}"


def _propose(skill: Path, host: Path, env: dict[str, str], findings: Path, *, name: str = FINDING_ID, isolated: bool = False) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / "reports/unify-shadows" / name
    proposal = output / "proposal.md"
    evidence = output / "evidence.json"
    prefix = (str(PYTHON), "-I", "-S") if isolated else (str(PYTHON),)
    result = _run(
        *prefix, str(skill / "scripts/propose_java.py"),
        "--findings", str(findings), "--finding-id", FINDING_ID,
        "--project-root", str(host), "--proposal", str(proposal),
        "--evidence", str(evidence), cwd=host, env=env,
    )
    return result, proposal, evidence


def test_java_confirmed_finding_reaches_read_only_proposal(tmp_path: Path) -> None:
    host, env, findings = _host(tmp_path)
    before = _hashes(host)
    result, proposal, evidence = _propose(SKILL, host, env, findings)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = proposal.read_text(encoding="utf-8")
    for heading in (
        "## Members and source impact", "## Accepted upstream evidence",
        "## Proposed action", "## Caller impact", "## Native Java test matrix",
        "## Stop condition", "## Authorization and handoff",
    ):
        assert heading in rendered
    assert "not behavioral equivalence" in rendered
    assert "Human approval is required" in rendered
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    upstream = json.loads(findings.read_text(encoding="utf-8"))
    assert payload["status"] == "proposal_ready_for_human_review"
    assert payload["language"] == "java"
    assert payload["finding_id"] == FINDING_ID
    assert payload["upstream_source_fingerprint"] == upstream["source_fingerprint"]
    assert payload["consumer_source_fingerprint"] == _consumer_fingerprint(SKILL)
    assert len(payload["source_evidence"]) == 2
    assert len(payload["caller_evidence"]) == 3
    assert json.loads((proposal.parent / "scope.json").read_text(encoding="utf-8"))["paths"] == [
        "src/main/java/example/SemanticConsumer.java",
        "src/main/java/example/SemanticFixture.java",
    ]
    assert _hashes(host) == before


@pytest.mark.parametrize("shape", SHAPES)
def test_java_consumer_preserves_each_accepted_shape(tmp_path: Path, shape: str) -> None:
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
        assert "consolidat" not in action.lower()


def test_java_consumer_rejects_unaccepted_or_stale_evidence_and_copies(tmp_path: Path) -> None:
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

    payload = json.loads(findings.read_text(encoding="utf-8"))
    payload["status"] = "partial"
    partial = findings.parent / "partial.json"
    partial.write_text(json.dumps(payload), encoding="utf-8")
    failed, proposal, _ = _propose(SKILL, host, env, partial, name="partial")
    assert failed.returncode == 2
    assert "refresh complete evidence" in failed.stderr
    assert not proposal.parent.exists()

    source = host / payload["confirmed"][0]["members"][0]["file"]
    source.write_text(source.read_text(encoding="utf-8").replace("summarizeByIndex", "renamedIndex"), encoding="utf-8")
    stale, proposal, _ = _propose(SKILL, host, env, findings, name="stale")
    assert stale.returncode == 2
    assert "source span does not contain" in stale.stderr
    assert not proposal.parent.exists()

    shutil.copytree(FIXTURE, host, dirs_exist_ok=True)
    copied = tmp_path / "on-demand/unify-shadows"
    shutil.copytree(SKILL, copied)
    passed, proposal, evidence = _propose(copied, host, env, findings, name="copied", isolated=True)
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert proposal.is_file()
    assert json.loads(evidence.read_text(encoding="utf-8"))["consumer_source_fingerprint"] == _consumer_fingerprint(copied)
    runtime = (copied / "scripts/propose_java.py").read_text(encoding="utf-8")
    assert "detect_java_semantic" not in runtime
    assert "scripts/_lib" not in runtime
