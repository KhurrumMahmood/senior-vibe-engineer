"""End-to-end wrapper for the skill-comply conformance harness.

Black-box via subprocess, matching the suite's convention for script-backed
gates (see test_run_skill_smokes.py): invoke scripts/skill_comply/validate.py,
which seeds a throwaway mini-host git repo per fixture, installs each of the
six proposal fixtures (conformant / defective / over-broad / poisoned-good /
wrong-name / under-broad), scores by side-effect, and asserts every expected
verdict.

Also covers oracle_proposer_completeness.py — the first Bucket-B oracle —
against the seed's planted-instance ground truth: a complete findings report
passes (exit 0), a report that misses an instance and pads a phantom finding
fails (exit 1) with the miss and the false positive named by stable ID.

Marked slow where a run is a fresh `git init` + several subprocess
invocations. Deselect with `-m 'not slow'`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_COMPLY = PROJECT_ROOT / "scripts" / "skill_comply"
VALIDATE = SKILL_COMPLY / "validate.py"
SEED = SKILL_COMPLY / "seed_fixture.py"
ORACLE = SKILL_COMPLY / "oracle_proposer_completeness.py"

ALL_FIXTURES = (
    "conformant", "defective", "over-broad", "poisoned-good", "wrong-name", "under-broad",
)


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300, **kw
    )


@pytest.mark.slow
def test_validate_all_six_fixtures_pass():
    proc = _run([sys.executable, str(VALIDATE)])
    assert proc.returncode == 0, (
        f"validate.py exited {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "OVERALL: PASS" in proc.stdout
    for name in ALL_FIXTURES:
        assert f"[{name}] VALIDATED" in proc.stdout


@pytest.mark.slow
def test_under_broad_fixture_fails_only_recall():
    """The recall fixture's whole point: C3/C4/C8 pass, only C9 fails."""
    proc = _run([sys.executable, str(VALIDATE), "--only", "under-broad"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    card = json.loads(
        (SKILL_COMPLY / "fixtures" / "under-broad" / "conformance.json").read_text()
    )
    assert card["verdict"] == "fail"
    fails = [c["id"] for c in card["checks"] if c["consequential"] and not c["pass"]]
    assert fails == ["C9"]


# ---------------------------------------------------------------------------
# oracle_proposer_completeness.py
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded_manifest(tmp_path_factory) -> dict:
    """Seed one mini-host repo for the oracle tests; clean up the repo after."""
    proc = _run([sys.executable, str(SEED)])
    assert proc.returncode == 0, proc.stderr
    manifest = json.loads(proc.stdout)
    base = tmp_path_factory.mktemp("oracle")
    manifest_path = base / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    manifest["_manifest_path"] = str(manifest_path)
    yield manifest
    shutil.rmtree(manifest["repo"], ignore_errors=True)


def _write_report(dirpath: Path, findings: list[dict]) -> Path:
    dirpath.mkdir()
    (dirpath / "findings.json").write_text(json.dumps({"findings": findings}))
    return dirpath


def test_oracle_complete_report_passes(seeded_manifest, tmp_path):
    findings = [
        {"id": f"F{i + 1}", "file": inst["file"], "line": inst["line"]}
        for i, inst in enumerate(seeded_manifest["planted_instances"])
    ]
    report = _write_report(tmp_path / "report", findings)
    proc = _run([
        sys.executable, str(ORACLE),
        "--report", str(report),
        "--ground-truth", seeded_manifest["_manifest_path"],
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads((report / "oracle.json").read_text())
    assert result["verdict"] == "pass"
    assert result["missed"] == []
    assert result["false_positives"] == []
    assert result["recall"] == 1.0 and result["precision"] == 1.0


def test_oracle_miss_and_false_positive_fail(seeded_manifest, tmp_path):
    instances = seeded_manifest["planted_instances"]
    kept, dropped = instances[0], instances[1]
    findings = [
        {"id": "F1", "file": kept["file"], "line": kept["line"]},
        # phantom finding — the benign decoy file holds no planted instance
        {"id": "F2", "file": "app/services/cart.py", "line": 6},
    ]
    report = _write_report(tmp_path / "report", findings)
    proc = _run([
        sys.executable, str(ORACLE),
        "--report", str(report),
        "--ground-truth", seeded_manifest["_manifest_path"],
    ])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads((report / "oracle.json").read_text())
    assert result["verdict"] == "fail"
    assert dropped["id"] in result["missed"]
    assert result["false_positives"] == ["F2"]
    assert result["found"] == [{"instance_id": kept["id"], "finding_id": "F1"}]
