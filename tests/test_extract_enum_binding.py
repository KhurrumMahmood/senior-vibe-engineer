from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from _lib.capability_registry import load_registry

import importlib.util


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / ".claude" / "skills" / "extract-enum"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "wp3" / "extract-enum"
COLLECT = SKILL_ROOT / "scripts" / "collect.py"
PROPOSE = SKILL_ROOT / "scripts" / "propose.py"
AR7_ORACLE = FIXTURE_ROOT / "ar7-semantic-oracle.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


# spec:portable-skill-layer-distribution::IM-8
def test_core_is_neutral_and_declared_bindings_hold_stack_mechanics():
    core_artifacts = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "agents" / "enum-profiler.md",
        SKILL_ROOT / "knowledge" / "risk-context.md",
    ]
    framework_terms = {
        term.casefold()
        for framework in load_registry().data["frameworks"].values()
        for term in framework.get("core_leakage_terms", [])
    }

    for artifact in core_artifacts:
        lowered = artifact.read_text(encoding="utf-8").casefold()
        assert not {term for term in framework_terms if term in lowered}, artifact

    core = core_artifacts[0].read_text(encoding="utf-8")

    assert "language: any" in core
    assert "framework: any" in core
    python_binding = (SKILL_ROOT / "bindings" / "python.md").read_text(encoding="utf-8")
    assert "python" in python_binding.casefold()
    assert "scripts/collect.py" in python_binding
    django = (SKILL_ROOT / "bindings" / "django.md").read_text(encoding="utf-8").casefold()
    assert "textchoices" in django
    assert "migration" in django
    assert "scripts/propose.py" in django

    leakage = _run("scripts/lint/no_core_framework_leakage.py", "--all")
    assert leakage.returncode == 0, leakage.stdout + leakage.stderr
    assert "16 migrated core skill" in leakage.stdout


# spec:portable-skill-layer-distribution::IM-9
def test_django_fixture_reaches_final_proposal_and_matches_ar7_semantics(tmp_path):
    project = FIXTURE_ROOT / "django"
    targets = tmp_path / "targets.json"
    proposal = tmp_path / "proposal.md"
    semantic = tmp_path / "semantic.json"
    normalization = tmp_path / "normalization.json"

    collected = _run(
        str(COLLECT),
        "--target",
        "app/models.py::status::Job",
        "--project-root",
        str(project),
        "--output",
        str(targets),
    )
    assert collected.returncode == 0, collected.stderr

    proposed = _run(
        str(PROPOSE),
        "--targets",
        str(targets),
        "--output",
        str(proposal),
        "--semantic-output",
        str(semantic),
        "--oracle",
        str(AR7_ORACLE),
        "--normalization-report",
        str(normalization),
    )

    assert proposed.returncode == 0, proposed.stderr
    assert json.loads(semantic.read_text(encoding="utf-8")) == json.loads(
        AR7_ORACLE.read_text(encoding="utf-8")
    )
    assert "class JobStatus(models.TextChoices)" in proposal.read_text(encoding="utf-8")
    assert json.loads(normalization.read_text(encoding="utf-8")) == {
        "allowed": [
            "temporary_absolute_roots",
            "timestamps_and_scan_ids",
            "markdown_whitespace",
            "semantically_irrelevant_table_order",
        ],
        "applied": [],
        "equivalent": True,
    }


def test_ar8_does_not_normalize_missing_literals_or_changed_wire_values(tmp_path):
    payload = json.loads(AR7_ORACLE.read_text(encoding="utf-8"))
    payload["literals"] = payload["literals"][1:]
    payload["members"][0]["wire_value"] = "queued"
    bad = tmp_path / "bad-oracle.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    actual = tmp_path / "actual.json"
    actual.write_text(AR7_ORACLE.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run(str(PROPOSE), "--compare", str(actual), "--oracle", str(bad))

    assert result.returncode == 2
    assert "literals" in result.stderr
    assert "wire_value" in result.stderr


def test_ar8_normalizes_only_an_explicit_temporary_root_prefix():
    spec = importlib.util.spec_from_file_location("extract_enum_propose", PROPOSE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    expected = json.loads(AR7_ORACLE.read_text(encoding="utf-8"))
    actual = json.loads(AR7_ORACLE.read_text(encoding="utf-8"))
    expected["target"]["field_file"] = "/tmp/oracle-root/app/models.py"
    actual["target"]["field_file"] = "/tmp/run-root/app/models.py"

    assert module.compare_semantics(
        actual,
        expected,
        temporary_roots=("/tmp/oracle-root", "/tmp/run-root"),
    ) == []

    actual["literals"][0]["value"] = "/tmp/run-root/pending"
    expected["literals"][0]["value"] = "/tmp/oracle-root/pending"
    assert module.compare_semantics(
        actual,
        expected,
        temporary_roots=("/tmp/oracle-root", "/tmp/run-root"),
    )


def test_existing_form_a_invalid_routing_remains_rejected(tmp_path):
    result = _run(
        str(COLLECT),
        "--from-finding",
        "implicit-state:implicit-state-0001",
        "--findings",
        str(FIXTURE_ROOT / "invalid-findings.json"),
        "--project-root",
        str(FIXTURE_ROOT / "django"),
        "--output",
        str(tmp_path / "targets.json"),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "error: finding implicit-state-0001 is introduce_fk_candidate; "
        "run /introduce-fk instead of /extract-enum\n"
    )
    assert not (tmp_path / "targets.json").exists()


def test_characterization_input_hashes_remain_pinned():
    assert hashlib.sha256((FIXTURE_ROOT / "django/app/models.py").read_bytes()).hexdigest() == (
        "abcedb51dab2814f7b8d9b3c99c10d5c9c74efd782f8352397dd25ef5eb1a3bd"
    )
    assert hashlib.sha256((FIXTURE_ROOT / "django/app/services.py").read_bytes()).hexdigest() == (
        "6bbea6f11b8036fa1730d8c957da195ca374ec2a128b9eef8ea206cb3ef7e93b"
    )
