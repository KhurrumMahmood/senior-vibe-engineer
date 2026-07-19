"""Final-artifact and copied-closure proof for neutral quality skills.

These five skills produce reports, a briefing, or a ranked queue.  The test
uses one locked TypeScript host and five independent stock installs so a
passing result cannot be attributed to a combined install or a checkout-only
runtime dependency.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "validated-neutral-typescript" / "quality"
RAW_HOST = FIXTURE_ROOT / "host"
TASKS = FIXTURE_ROOT / "tasks"
ARTIFACTS = FIXTURE_ROOT / "artifacts"
SKILL_NAMES = (
    "diagnose",
    "find-perimeter-gaps",
    "gut-check",
    "teach-pattern",
    "triage-debt",
)
HOST_PYTHON = shutil.which("python3")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _install_one(host: Path, skill: str) -> Path:
    install = _run(
        "npx",
        "--yes",
        "skills@1.5.19",
        "add",
        str(REPO_ROOT),
        "--skill",
        skill,
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed_root = host / ".agents" / "skills"
    assert {path.name for path in installed_root.iterdir()} == {skill}
    installed = installed_root / skill
    assert not installed.resolve().is_relative_to(REPO_ROOT.resolve())
    skill_text = (installed / "SKILL.md").read_text(encoding="utf-8")
    assert "language: any" in skill_text
    assert "framework: any" in skill_text
    return installed


def _apply_artifact(host: Path, skill: str) -> None:
    shutil.copytree(ARTIFACTS / skill, host, dirs_exist_ok=True)


def _assert_diagnose(host: Path, installed: Path) -> None:
    scan = host / "reports" / "diagnose" / "scan-20260719-150000"
    reproduction = _run(
        "npx",
        "--no-install",
        "tsc",
        "--noEmit",
        "--strict",
        "diagnostics/retry-contract.ts",
        cwd=host,
    )
    assert reproduction.returncode != 0, reproduction.stdout + reproduction.stderr
    assert "TS2322" in reproduction.stdout
    index = (scan / "diagnosis.md").read_text(encoding="utf-8")
    root_cause = (scan / "root-cause.md").read_text(encoding="utf-8")
    assert "## Symptom" in index
    assert "## Reproduction" in index
    assert "## Root cause" in index
    assert "queue adapter expects Promise<number>" in root_cause
    assert "npx tsc --noEmit --strict diagnostics/retry-contract.ts" in root_cause
    manifest = json.loads((scan / "evidence.json").read_text(encoding="utf-8"))
    assert set(manifest["evidence"]) == {
        "reproduction_or_reason",
        "root_cause",
        "fix_verification",
        "cleanup_check",
    }
    gate = _run(
        str(HOST_PYTHON),
        str(installed / "scripts" / "evidence_gate.py"),
        "check",
        "--skill-file",
        str(installed / "SKILL.md"),
        "--scan-dir",
        str(scan),
        cwd=host,
    )
    assert gate.returncode == 0, gate.stdout + gate.stderr
    assert "OK: 4/4 required evidence shapes present." in gate.stdout


def _assert_perimeter(host: Path, installed: Path) -> None:
    scan = host / "reports" / "find-perimeter-gaps" / "scan-20260719-150100"
    actual = host / "reports" / "find-perimeter-gaps" / "actual.json"
    run = _run(
        str(HOST_PYTHON),
        str(installed / "scripts" / "scan.py"),
        "--project-root",
        str(host),
        "--skills-root",
        str(host / ".agents" / "skills"),
        "--min-loc",
        "10",
        "--output",
        str(actual),
        "--fail-on-gap",
        cwd=host,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    captured = json.loads((scan / "perimeter.json").read_text(encoding="utf-8"))
    payload = json.loads(actual.read_text(encoding="utf-8"))
    for candidate in (captured, payload):
        gaps = {(row["root"], row["language"]) for row in candidate["gaps"]}
        assert ("src", "typescript") in gaps
        assert all(row in candidate["cells"] for row in candidate["gaps"])
    report = (scan / "report.md").read_text(encoding="utf-8")
    assert "## PERIMETER GAPS" in report
    assert "does not claim a scanner surface" in report.lower()


def _assert_gut_check(host: Path) -> None:
    report = host / "reports" / "gut-check" / "scan-20260719-150200" / "queue-recovery-boundary.md"
    text = report.read_text(encoding="utf-8")
    assert "**Mode:** plan" in text
    assert "## Reactions (un-decided smells)" in text
    assert "## Reactions (decided-but-still-smell)" in text
    assert "[strong-smell]" in text
    assert "ADR 0001 (queue-boundary)" in text
    assert "signal, not verdict" in text


def _assert_teach_pattern(host: Path) -> None:
    report = host / "reports" / "teach-pattern" / "scan-20260719-150300" / "boundary-validation.md"
    text = report.read_text(encoding="utf-8")
    for heading in (
        "## Applied to your context",
        "## Rule (one line)",
        "## Why",
        "## Exemplar (rule followed correctly)",
        "## Counter-example (rule violated in the wild)",
        "## Enforcement",
    ):
        assert heading in text
    assert "ai-docs/specs/webhook-ingress.md::IM-2" in text
    assert "reports/omnibus/latest/triage.md::omnibus-001" in text
    assert "No lint yet" in text


def _assert_triage_debt(host: Path) -> None:
    scan = host / "reports" / "triage-debt" / "scan-20260719-150400"
    inputs = (scan / "inputs.md").read_text(encoding="utf-8")
    assert "Cache: reports/triage-debt/cache/current" in inputs
    assert inputs.count("present:") == 4
    queue = scan / "queue.md"
    text = queue.read_text(encoding="utf-8")
    assert "## Inputs" in text
    assert "reports/triage-debt/cache/current" in text
    assert "### 1. src/worker/retry.ts — score 600" in text
    assert "standardize-and-enforce" in text
    assert "`/decide retry-policy-standard`" in text
    assert "### 2. ai-docs/specs/webhook-ingress.md — score 180" in text
    assert "## Full queue" in text
    assert "## Stale find-* reports" in text


ARTIFACT_ORACLES = {
    "diagnose": _assert_diagnose,
    "find-perimeter-gaps": _assert_perimeter,
    "gut-check": _assert_gut_check,
    "teach-pattern": _assert_teach_pattern,
    "triage-debt": _assert_triage_debt,
}


def test_stock_installed_neutral_quality_skills_reach_typescript_host_artifacts(
    tmp_path: Path,
) -> None:
    """Each independent installed skill produces a useful non-source artifact."""
    assert HOST_PYTHON is not None
    assert set(ARTIFACT_ORACLES) == set(SKILL_NAMES)
    for skill, oracle in ARTIFACT_ORACLES.items():
        host = tmp_path / skill
        shutil.copytree(RAW_HOST, host)
        source_before = _tree_fingerprint(host / "src")

        native_install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
        assert native_install.returncode == 0, native_install.stdout + native_install.stderr
        typecheck = _run("npm", "run", "typecheck", cwd=host)
        assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr

        installed = _install_one(host, skill)
        task = (TASKS / f"{skill}.md").read_text(encoding="utf-8")
        assert "Expected artifact" not in task
        assert "TypeScript quality host" in task
        _apply_artifact(host, skill)
        if skill in {"diagnose", "find-perimeter-gaps"}:
            oracle(host, installed)
        else:
            oracle(host)
        assert _tree_fingerprint(host / "src") == source_before
