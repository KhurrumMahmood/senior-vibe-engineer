"""Tests for the status projection (scripts/status.py, ADR 0037).

Covers the plan §2 success criteria that belong to the producer:
schema-valid output with per-section degradation (every source removed →
section absent, exit 0), pending-approvals detection/dismissal/closure,
digest-tier sweep consumption (no raw findings), and input-drift
staleness via the suite's first tmp-path git fixture.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sweep.manifest import FindingInput, build_manifest
from sweep.pipeline import build_judgment, render_judged_digest
from sweep.serialization import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


status_mod = _load("status_mod", "scripts/status.py")
status_schema = _load("status_schema_mod", "scripts/_lib/status_schema.py")
artifact_scope = _load("artifact_scope_mod", "scripts/_lib/artifact_scope.py")


def build(root: Path, **kwargs) -> dict:
    return status_mod.build_status(root, **kwargs)


# --- envelope + degradation (IM-1 / IM-2) -----------------------------------


def test_empty_root_every_section_absent_schema_valid(tmp_path):
    doc = build(tmp_path)
    assert status_schema.validate(doc) == []
    assert doc["schema_version"] == status_schema.SCHEMA_VERSION
    for name in status_schema.SECTIONS:
        section = doc["sections"][name]
        assert section["available"] is False, name
        assert section["reason"], name


def test_cli_exit_zero_on_empty_root(tmp_path):
    out = tmp_path / "status.json"
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "status.py"),
         "--root", str(tmp_path), "--out", str(out)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(out.read_text())
    assert status_schema.validate(doc) == []


def test_each_source_lights_only_its_section(tmp_path):
    (tmp_path / "ai-docs" / "plans").mkdir(parents=True)
    (tmp_path / "ai-docs" / "plans" / "x.md").write_text(
        "---\nname: x\nstatus: scoped\n---\n\n# x\n"
    )
    doc = build(tmp_path)
    assert doc["sections"]["in_flight"]["available"] is True
    assert doc["sections"]["in_flight"]["active_plans"] == ["x"]
    # everything else still absent
    for name in ("lifecycle", "structural_health", "pending_approvals", "queue", "goals"):
        assert doc["sections"][name]["available"] is False, name


def test_ideas_projection_reuses_ideas_lib(tmp_path):
    ledger = tmp_path / ".claude" / "ideas" / "log.jsonl"
    ledger.parent.mkdir(parents=True)
    rows = [
        {"record_kind": "intake", "id": "idea-a", "title": "A", "state": "proposed",
         "created_at": "2026-06-01T00:00:00+00:00", "origin": "convo",
         "subsystem_kind": "infra", "summary": "s"},
        {"record_kind": "event", "id": "idea-a", "event_kind": "transition",
         "to_state": "in-flight", "event_at": "2026-06-02T00:00:00+00:00"},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    ideas = build(tmp_path)["sections"]["in_flight"]["ideas"]
    assert ideas["available"] is True
    assert ideas["in_flight"] == ["idea-a"]
    assert ideas["by_state"] == {"in-flight": 1}


def test_validate_flags_missing_section():
    doc = {"schema_version": 1, "generated_at": "x", "root": "y", "sections": {}}
    errors = status_schema.validate(doc)
    assert any("missing section" in e for e in errors)


# --- structural health: digest tier only (AR-6) ------------------------------


def _judged_dashboard_digest() -> dict:
    empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    finding = FindingInput(
        provider="ruff", language="python", native_rule_id="F401",
        rule_semantic_key="F401:v1", path="src/x.py", semantic_anchor="module",
        native_severity="warning", severity=2, message="unused import",
        summary="unused import", metrics={}, observation_index=0, line=1,
    )
    provider = {
        "schema_version": 1, "provider": "ruff", "language": "python",
        "provider_kind": "native",
        "command": {"executable": "/tool/ruff", "argv": ["check", "."],
                    "timeout_seconds": 30, "output_format": "json",
                    "output_byte_limit": 1_048_576},
        "tool_version": "ruff 0.9.9", "exit": {"code": 0, "classification": "diagnostics"},
        "raw": {"stdout_sha256": empty_hash, "stderr_sha256": empty_hash,
                "stdout_bytes": 0, "stderr_bytes": 0},
        "status": "completed", "failure": None,
    }
    manifest = build_manifest(
        capability_registry_version=1, paths=["src"], case_sensitive=True,
        roots=["src"], exclusions=[],
        source={"revision": "a" * 40, "dirty": False, "dirty_state_hash": empty_hash},
        providers=[provider], findings=[finding],
    )
    identifier = manifest["findings"][0]["id"]
    judgment = build_judgment(
        manifest, judge_identity="fixture", judge_version="1",
        outcomes=[{"finding_id": identifier, "outcome": "actionable",
                   "reason": "real", "evidence": "fixture:evidence"}],
    )
    return render_judged_digest(manifest, judgment, purpose="dashboard")


def test_sweep_digest_has_judgment_hashes_ids_and_counts_but_no_raw_findings(tmp_path):
    digest_path = tmp_path / "digest.json"
    digest = _judged_dashboard_digest()
    digest_path.write_bytes(canonical_json_bytes(digest))
    section = build(tmp_path, sweep_digest=digest_path)["sections"]["structural_health"]
    assert section["available"] is True
    assert section["total_actionable"] == 1
    assert section["counts"] == {"ruff": 1}
    assert section["finding_ids"] == digest["finding_ids"]
    assert section["manifest_hash"] == digest["manifest_hash"]
    assert section["judgment_hash"] == digest["judgment_hash"]
    blob = json.dumps(section)
    assert "src/x.py" not in blob and "long line" not in blob  # digest tier only


def test_structural_health_rejects_raw_or_tampered_digest_and_has_no_prototype_fallback(tmp_path):
    raw = tmp_path / "manifest.json"
    raw.write_text(json.dumps({"findings": [], "total": 0}))
    section = build(tmp_path, sweep_digest=raw)["sections"]["structural_health"]
    assert section["available"] is False
    assert "invalid" in section["reason"]

    digest = _judged_dashboard_digest()
    digest["total_actionable"] = 99
    raw.write_bytes(canonical_json_bytes(digest))
    section = build(tmp_path, sweep_digest=raw)["sections"]["structural_health"]
    assert section["available"] is False
    assert "invalid" in section["reason"]

    prototype = tmp_path / ".claude" / "tasks" / "sweep-prototype" / "manifest.json"
    prototype.parent.mkdir(parents=True)
    prototype.write_text(json.dumps({"findings": []}))
    assert build(tmp_path)["sections"]["structural_health"]["available"] is False


# --- pending approvals (IM-3, AR-11) -----------------------------------------


def _seed_proposal(root: Path, skill: str, pid: str, body: str = "p") -> Path:
    d = root / "reports" / skill / pid
    d.mkdir(parents=True)
    (d / "proposal.md").write_text(body)
    return d


def test_proposal_detected_pending_with_age(tmp_path):
    _seed_proposal(tmp_path, "unify-shadows", "f-1")
    section = build(tmp_path)["sections"]["pending_approvals"]
    assert section["pending_count"] == 1
    item = section["items"][0]
    assert item["chain"] == "unify-shadows"
    assert item["status"] == "pending"
    assert item["closure_detectable"] is False
    assert item["age_days"] >= 0


def test_dismissal_marker_clears_pending(tmp_path):
    d = _seed_proposal(tmp_path, "extract-enum", "e-1")
    (d / "DISMISSED").write_text("not worth it")
    section = build(tmp_path)["sections"]["pending_approvals"]
    assert section["pending_count"] == 0
    assert section["items"][0]["status"] == "dismissed"


def test_prevent_regression_closes_on_installed_lint(tmp_path):
    _seed_proposal(tmp_path, "prevent-regression", "r-1",
                   body="ships `scripts/lint/foo_rule.py` as the guard")
    assert build(tmp_path)["sections"]["pending_approvals"]["items"][0]["status"] == "pending"
    (tmp_path / "scripts" / "lint").mkdir(parents=True)
    (tmp_path / "scripts" / "lint" / "foo_rule.py").write_text("# rule\n")
    item = build(tmp_path)["sections"]["pending_approvals"]["items"][0]
    assert item["status"] == "closed"
    assert item["closure_detectable"] is True


def test_propose_boundary_closes_on_spec_link(tmp_path):
    _seed_proposal(tmp_path, "propose-boundary", "b-1",
                   body="promoted into ai-docs/specs/some-boundary.md")
    assert build(tmp_path)["sections"]["pending_approvals"]["items"][0]["status"] == "pending"
    (tmp_path / "ai-docs" / "specs").mkdir(parents=True)
    (tmp_path / "ai-docs" / "specs" / "some-boundary.md").write_text("---\nid: x\n---\n")
    assert build(tmp_path)["sections"]["pending_approvals"]["items"][0]["status"] == "closed"


# --- input-drift staleness (IM-6) --------------------------------------------


GIT_ENV_BASE = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(root: Path, *args: str, date: str | None = None):
    import os
    env = {**os.environ, **GIT_ENV_BASE}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "-C", str(root), *args],
                   check=True, capture_output=True, env=env)


@pytest.fixture
def git_repo(tmp_path):
    _git(tmp_path, "init", "-q")
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.py").write_text("a = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base", date="2026-01-01T00:00:00+00:00")
    return tmp_path


def test_artifact_stale_when_scoped_path_touched_later(git_repo):
    artifact = git_repo / "reports" / "find-omnibus" / "scan-1"
    artifact_scope.write_scope(artifact, ["src/x.py"])  # written_at = now
    # commit dated in the future relative to the sidecar write
    (git_repo / "src" / "x.py").write_text("a = 2\n")
    _git(git_repo, "add", ".")
    _git(git_repo, "commit", "-qm", "drift", date="2036-01-01T00:00:00+00:00")
    section = build(git_repo)["sections"]["staleness"]
    assert section["available"] is True
    assert section["stale_count"] == 1
    assert section["artifacts"][0]["state"] == "stale"


def test_artifact_fresh_when_inputs_untouched(git_repo):
    artifact = git_repo / "reports" / "find-omnibus" / "scan-1"
    artifact_scope.write_scope(artifact, ["src/x.py"])  # last commit predates the write
    section = build(git_repo)["sections"]["staleness"]
    assert section["stale_count"] == 0
    assert section["artifacts"][0]["state"] == "fresh"


def test_scope_sidecar_roundtrip(tmp_path):
    d = tmp_path / "artifact"
    artifact_scope.write_scope(d, ["b.py", "a.py", "a.py"], note="n")
    payload = artifact_scope.read_scope(d)
    assert payload["paths"] == ["a.py", "b.py"]
    assert payload["version"] == 1
    assert payload["note"] == "n"
    assert artifact_scope.read_scope(tmp_path / "nope") is None


# --- queue (read side) --------------------------------------------------------


def test_queue_section_counts_items(tmp_path):
    qdir = tmp_path / ".engineering" / "local" / "queue"
    qdir.mkdir(parents=True)
    (qdir / "item-1.json").write_text(json.dumps(
        {"status": "staged", "staged_at": "2026-06-12T00:00:00+00:00"}))
    section = build(tmp_path)["sections"]["queue"]
    assert section == {
        "available": True, "count": 1,
        "items": [{"id": "item-1", "status": "staged",
                   "staged_at": "2026-06-12T00:00:00+00:00"}],
    }
