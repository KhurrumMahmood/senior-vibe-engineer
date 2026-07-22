"""Stock-install and final-output proof for neutral orchestration skills.

The selected skills are prompt-led.  This test therefore installs their exact
copied directories into one locked TypeScript host, validates the durable
results of natural tasks, and makes absent repository-owned helpers explicit.
It does not pretend that captured agent judgment is an installed executable.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = Path(sys.executable)
FIXTURE_ROOT = (
    REPO_ROOT / "tests" / "fixtures" / "validated-neutral-typescript" / "orchestration"
)
RAW_HOST = FIXTURE_ROOT / "host"
TASKS = FIXTURE_ROOT / "tasks"
ARTIFACTS = FIXTURE_ROOT / "artifacts"
SKILL_NAMES = (
    "converge",
    "harvest-learnings",
    "organize-project-structure",
    "orient",
    "project-interview",
)


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


def _selected_source_fingerprint() -> str:
    digest = hashlib.sha256()
    for name in SKILL_NAMES:
        root = REPO_ROOT / ".claude" / "skills" / name
        digest.update(name.encode())
        digest.update(_tree_fingerprint(root).encode())
    return digest.hexdigest()


def _materialize_result(host: Path, skill: str) -> None:
    shutil.copytree(ARTIFACTS / skill, host, dirs_exist_ok=True)


def _assert_converge(host: Path) -> None:
    scan = host / "reports" / "converge" / "scan-20260719-160000"
    verdict = json.loads((scan / "verdict.json").read_text(encoding="utf-8"))
    assert set(verdict) == {
        "phase_status",
        "strongest_nodes",
        "weakest_nodes",
        "next_step",
        "why_this_step",
        "success_gate",
        "stop_condition",
        "do_not_do_next",
    }
    assert verdict["phase_status"] == "repair"
    assert any("No behavior test" in node for node in verdict["weakest_nodes"])
    assert "one native behavior test" in verdict["next_step"]
    assert len(verdict["do_not_do_next"]) >= 2
    note = (scan / "verdict.md").read_text(encoding="utf-8")
    assert "effectiveness record was not logged" in note
    assert "scripts/log_effectiveness.py" in note


def _assert_harvest(host: Path) -> None:
    scan = host / "reports" / "harvest" / "scan-20260719-160100"
    payload = json.loads((scan / "harvest.json").read_text(encoding="utf-8"))
    items = payload["items"]
    assert payload["counts"] == {"generative_only": 1, "ported": 3, "stayed_home": 1}
    assert len(items) == 4
    verdicts = {item["portability"]["verdict"] for item in items}
    assert "stays-home" in verdicts
    assert "ports" in verdicts
    assert "principle-ports-mechanism-stays" in verdicts
    for item in items:
        assert item["origin_handle"]
        assert item["exemplar"]["what_bit"]
        assert item["exemplar"]["back_link"]
        assert item["portability"]["translation_test"]
        assert item["portability"]["confidence"] == "single-constraint-set"
        if item["portability"]["verdict"] != "stays-home":
            assert "activation" in item
    report = (scan / "harvest.md").read_text(encoding="utf-8")
    assert "N=1" in report
    assert "Proposal only" in report


def _assert_organize(host: Path) -> None:
    plan = (
        host
        / "reports"
        / "organize-project-structure"
        / "scan-20260719-160200"
        / "topology-plan.md"
    ).read_text(encoding="utf-8")
    for heading in (
        "## Folder value inventory",
        "## Abstraction ladder",
        "## Ideal topology",
        "## Constrained target topology",
        "## Naming-context decisions",
        "## Deterministic moves",
        "## Judgment and manual follow-up",
        "## Validation and stop condition",
        "## Installed-closure disclosure",
    ):
        assert heading in plan
    assert "inputs-1" in plan
    assert "source-materials/webhook-fixtures" in plan
    assert "outputs" in plan
    assert "evals/run-records" in plan
    assert "No moves were applied" in plan
    assert "structural-design-principles.md" in plan


def _assert_orient(host: Path) -> None:
    state_path = host / ".engineering" / "project-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert list(state) == ["maturity", "stakes", "declared_by", "declared_at", "notes"]
    assert state["maturity"] == "first-users"
    assert state["stakes"] == "external"
    assert state["declared_by"] == "orient"
    assert state["declared_at"].endswith("Z")
    assert "pilot" in state["notes"]


def _assert_project_interview(host: Path) -> None:
    scan = host / "reports" / "project-interview" / "scan-20260719-160400"
    for name in ("profile.yml", "profile.md", "open-questions.md", "evidence.json"):
        assert (scan / name).is_file()
    profile = (scan / "profile.yml").read_text(encoding="utf-8")
    assert "user_approved: true" in profile
    assert "signature acceptance" in profile
    assert "unbounded retry attempts" in profile
    assert "do_not_canonize_by_frequency: true" in profile
    open_questions = (scan / "open-questions.md").read_text(encoding="utf-8")
    assert "retention period" in open_questions
    manifest = json.loads((scan / "evidence.json").read_text(encoding="utf-8"))
    assert manifest["evidence"] == {
        "open_questions": "open-questions.md",
        "profile": "profile.yml",
        "profile_summary": "profile.md",
    }
    for relative in manifest["evidence"].values():
        assert (scan / relative).is_file()
    closure = (scan / "installed-closure.md").read_text(encoding="utf-8")
    assert "scripts/project_interview.py" in closure
    assert "scripts/evidence_gate.py" in closure
    assert "OK: 3/3 required evidence shapes present." in closure


ARTIFACT_ORACLES = {
    "converge": _assert_converge,
    "harvest-learnings": _assert_harvest,
    "organize-project-structure": _assert_organize,
    "orient": _assert_orient,
    "project-interview": _assert_project_interview,
}


def test_stock_installed_neutral_orchestration_reaches_final_typescript_outputs(
    tmp_path: Path,
) -> None:
    host = tmp_path / "typescript-orchestration-host"
    shutil.copytree(RAW_HOST, host)
    source_before = _tree_fingerprint(host / "src")
    selected_sources_before = _selected_source_fingerprint()

    native_install = _run("npm", "ci", "--offline", "--ignore-scripts", cwd=host)
    assert native_install.returncode == 0, native_install.stdout + native_install.stderr
    for command in (("npm", "run", "typecheck"), ("npm", "test")):
        result = _run(*command, cwd=host)
        assert result.returncode == 0, result.stdout + result.stderr

    install = _run(
        "npx",
        "--yes",
        "skills@1.5.19",
        "add",
        str(REPO_ROOT),
        *[item for name in SKILL_NAMES for item in ("--skill", name)],
        "--agent",
        "codex",
        "--copy",
        "-y",
        cwd=host,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    assert _tree_fingerprint(host / "src") == source_before
    assert _selected_source_fingerprint() == selected_sources_before

    installed_root = host / ".agents" / "skills"
    assert {path.name for path in installed_root.iterdir()} == set(SKILL_NAMES)
    for name in SKILL_NAMES:
        skill = installed_root / name
        assert (skill / "SKILL.md").is_file()
        assert "language: any" in (skill / "SKILL.md").read_text(encoding="utf-8")
        assert "framework: any" in (skill / "SKILL.md").read_text(encoding="utf-8")
        assert not skill.resolve().is_relative_to(REPO_ROOT.resolve())

    assert (installed_root / "harvest-learnings" / "knowledge" / "output-schema.md").is_file()
    assert (installed_root / "orient" / "scripts" / "infer_state_signals.py").is_file()
    assert (installed_root / "orient" / "knowledge" / "inference-heuristics.md").is_file()
    interview_skill = installed_root / "project-interview"
    interview_helper = interview_skill / "scripts" / "project_interview.py"
    evidence_helper = interview_skill / "scripts" / "evidence_gate.py"
    assert interview_helper.is_file()
    assert evidence_helper.is_file()

    installed_artifacts = tmp_path / "installed-project-interview-artifacts"
    draft = _run(
        str(VENV_PYTHON),
        "-I",
        "-S",
        str(interview_helper),
        "draft",
        "--project-root",
        str(host),
        "--artifact-root",
        str(installed_artifacts),
        "--timestamp",
        "installed-project-interview",
        "--no-host-write",
        cwd=host,
    )
    assert draft.returncode == 0, draft.stdout + draft.stderr
    installed_scan = (
        installed_artifacts
        / "reports"
        / "project-interview"
        / "scan-installed-project-interview"
    )
    assert draft.stdout.strip() == str(installed_scan)
    draft_profile = (installed_scan / "profile.yml").read_text(encoding="utf-8")
    assert "user_approved: false" in draft_profile
    assert "languages: [typescript]" in draft_profile
    assert "pilot customers" not in draft_profile
    assert "unbounded retry attempts" not in draft_profile
    assert not (host / ".engineering" / "project").exists()

    refused_apply = _run(
        str(VENV_PYTHON),
        "-I",
        "-S",
        str(interview_helper),
        "apply",
        "--project-root",
        str(host),
        "--scan-dir",
        str(installed_scan),
        cwd=host,
    )
    assert refused_apply.returncode == 1
    assert "user_approved is not true" in refused_apply.stderr
    assert not (host / ".engineering" / "project").exists()

    profile_summary = installed_scan / "profile.md"
    hidden_summary = installed_scan / "profile.md.missing"
    profile_summary.rename(hidden_summary)
    failed_gate = _run(
        str(VENV_PYTHON),
        "-I",
        "-S",
        str(evidence_helper),
        "check",
        "--scan-dir",
        str(installed_scan),
        cwd=host,
    )
    assert failed_gate.returncode == 1
    assert "FAIL: 2/3 required evidence shapes present." in failed_gate.stdout
    hidden_summary.rename(profile_summary)

    passed_gate = _run(
        str(VENV_PYTHON),
        "-I",
        "-S",
        str(evidence_helper),
        "check",
        "--scan-dir",
        str(installed_scan),
        cwd=host,
    )
    assert passed_gate.returncode == 0, passed_gate.stdout + passed_gate.stderr
    assert passed_gate.stdout.rstrip().endswith("OK: 3/3 required evidence shapes present.")
    assert _tree_fingerprint(host / "src") == source_before

    # These repository-level paths remain absent: project-interview now uses
    # only its installed skill-local helpers.
    assert not (installed_root / "_common" / "structural-design-principles.md").exists()
    assert not (host / "scripts" / "log_effectiveness.py").exists()
    assert not (host / "scripts" / "project_adapt.py").exists()
    assert not (host / "scripts" / "evidence_gate.py").exists()

    forbidden_answer_markers = {
        "converge": ("phase_status: repair",),
        "harvest-learnings": ("stays-home", "single-constraint-set"),
        "organize-project-structure": ("source-materials/webhook-fixtures", "evals/run-records"),
        "orient": ("first-users", "stakes: external"),
        "project-interview": ("user_approved: true", "retention period"),
    }
    for name, oracle in ARTIFACT_ORACLES.items():
        task = (TASKS / f"{name}.md").read_text(encoding="utf-8")
        assert "Expected artifact" not in task
        for marker in forbidden_answer_markers[name]:
            assert marker not in task
        _materialize_result(host, name)
        oracle(host)
        if name == "project-interview":
            captured_scan = host / "reports" / "project-interview" / "scan-20260719-160400"
            captured_gate = _run(
                str(VENV_PYTHON),
                "-I",
                "-S",
                str(evidence_helper),
                "check",
                "--skill",
                "project-interview",
                "--scan-dir",
                str(captured_scan),
                cwd=host,
            )
            assert captured_gate.returncode == 0, captured_gate.stdout + captured_gate.stderr
            assert captured_gate.stdout.rstrip().endswith(
                "OK: 3/3 required evidence shapes present."
            )
        assert _tree_fingerprint(host / "src") == source_before

    final_typecheck = _run("npm", "run", "typecheck", cwd=host)
    assert final_typecheck.returncode == 0, final_typecheck.stdout + final_typecheck.stderr
