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
PROPOSE_PYTHON = SKILL_ROOT / "scripts" / "propose_python.py"
REPLAY = REPO_ROOT / "scripts" / "wp3_slice4_replay.py"
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
    assert "scripts/propose_python.py" in python_binding
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
    proposal_text = proposal.read_text(encoding="utf-8")
    assert "class JobStatus(models.TextChoices)" in proposal_text
    for section in (
        "## Field change",
        "## Pre-deploy distinct-value audit",
        "## Schema migration",
        "## Data-normalization migration",
        "## Characterization tests",
        "## Subsystem tests",
    ):
        assert section in proposal_text
    assert "choices=JobStatus.choices" in proposal_text
    assert "default=JobStatus.PENDING" in proposal_text
    assert ".values_list('status', flat=True).distinct()" in proposal_text
    assert "makemigrations" in proposal_text
    assert "migrate" in proposal_text
    assert "PENDING = 'pending', 'Pending'" in proposal_text
    wrong_renderer = _run(
        str(PROPOSE_PYTHON),
        "--targets",
        str(targets),
        "--output",
        str(tmp_path / "wrong.py"),
        "--semantic-output",
        str(tmp_path / "wrong.json"),
    )
    assert wrong_renderer.returncode == 2
    assert "plain-Python renderer requires carrier_kind" in wrong_renderer.stderr
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


def test_ar8_normalizes_only_typed_path_roots_and_preserves_target_identity():
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
        actual_root="/tmp/run-root",
        expected_root="/tmp/oracle-root",
    ) == []

    actual["target"]["field_file"] = "/tmp/run-root/app/renamed.py"
    assert module.compare_semantics(
        actual,
        expected,
        actual_root="/tmp/run-root",
        expected_root="/tmp/oracle-root",
    )
    actual["target"]["field_file"] = "/tmp/run-root/app/models.py"

    actual["target"]["target"] = "/tmp/run-root/app/models.py::phase::Job"
    expected["target"]["target"] = "/tmp/oracle-root/app/models.py::status::Job"
    assert module.compare_semantics(
        actual,
        expected,
        actual_root="/tmp/run-root",
        expected_root="/tmp/oracle-root",
    )
    actual["target"]["target"] = "/tmp/run-root/app/models.py::status::Task"
    assert module.compare_semantics(
        actual,
        expected,
        actual_root="/tmp/run-root",
        expected_root="/tmp/oracle-root",
    )

    actual["literals"][0]["value"] = "/tmp/run-root/pending"
    expected["literals"][0]["value"] = "/tmp/oracle-root/pending"
    assert module.compare_semantics(
        actual,
        expected,
        actual_root="/tmp/run-root",
        expected_root="/tmp/oracle-root",
    )


def test_ar8_cli_requires_typed_actual_and_expected_roots_together(tmp_path):
    result = _run(
        str(PROPOSE),
        "--compare",
        str(AR7_ORACLE),
        "--oracle",
        str(AR7_ORACLE),
        "--actual-root",
        "/tmp/run-root",
    )

    assert result.returncode == 2
    assert "--actual-root and --expected-root must be provided together" in result.stderr


def test_python_fixture_collects_plain_carrier_and_renders_executable_strenum(tmp_path):
    project = FIXTURE_ROOT / "python"
    fixture_run = _run(str(project / "app.py"))
    assert fixture_run.returncode == 0, fixture_run.stderr

    targets = tmp_path / "targets.json"
    collected = _run(
        str(COLLECT),
        "--target",
        "app.py::status::Job",
        "--project-root",
        str(project),
        "--output",
        str(targets),
    )
    assert collected.returncode == 0, collected.stderr
    target_payload = json.loads(targets.read_text(encoding="utf-8"))
    assert target_payload["carrier_kind"] == "python-attribute"
    assert target_payload["field_symbol"] == "Job.status"
    assert target_payload["declared_choices"] == [
        {"label": "pending", "wire_value": "pending"},
        {"label": "running", "wire_value": "running"},
    ]
    assert {item["kind"] for item in target_payload["site_classifications"]} == {
        "assignment",
        "bridge",
        "confirmed",
    }

    enum_module = tmp_path / "job_status.py"
    semantic = tmp_path / "python-semantic.json"
    proposed = _run(
        str(PROPOSE_PYTHON),
        "--targets",
        str(targets),
        "--output",
        str(enum_module),
        "--semantic-output",
        str(semantic),
    )
    assert proposed.returncode == 0, proposed.stderr
    rendered = enum_module.read_text(encoding="utf-8")
    assert "from enum import StrEnum" in rendered
    assert "class JobStatus(StrEnum):" in rendered
    assert "PENDING = 'pending'" in rendered
    assert "RUNNING = 'running'" in rendered
    assert "vendor_queued" not in rendered
    executable = _run(str(enum_module))
    assert executable.returncode == 0, executable.stderr
    semantic_payload = json.loads(semantic.read_text(encoding="utf-8"))
    assert [member["wire_value"] for member in semantic_payload["members"]] == [
        "pending",
        "running",
    ]
    assert semantic_payload["bridge_sites"][0]["literal"] == "vendor_queued"
    wrong_renderer = _run(
        str(PROPOSE),
        "--targets",
        str(targets),
        "--output",
        str(tmp_path / "wrong.md"),
        "--semantic-output",
        str(tmp_path / "wrong-semantic.json"),
    )
    assert wrong_renderer.returncode == 2
    assert "Django renderer requires carrier_kind" in wrong_renderer.stderr


def test_python_renderer_fails_closed_on_missing_or_dynamic_site_classification(tmp_path):
    project = FIXTURE_ROOT / "python"
    targets = tmp_path / "targets.json"
    collected = _run(
        str(COLLECT),
        "--target",
        "app.py::status::Job",
        "--project-root",
        str(project),
        "--output",
        str(targets),
    )
    assert collected.returncode == 0, collected.stderr
    payload = json.loads(targets.read_text(encoding="utf-8"))

    payload["site_classifications"] = payload["site_classifications"][:-1]
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(
        str(PROPOSE_PYTHON),
        "--targets",
        str(missing),
        "--output",
        str(tmp_path / "missing.py"),
        "--semantic-output",
        str(tmp_path / "missing-semantic.json"),
    )
    assert result.returncode == 2
    assert "exhaustive site classifications" in result.stderr

    payload = json.loads(targets.read_text(encoding="utf-8"))
    payload["site_classifications"][0]["kind"] = "dynamic"
    dynamic = tmp_path / "dynamic.json"
    dynamic.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(
        str(PROPOSE_PYTHON),
        "--targets",
        str(dynamic),
        "--output",
        str(tmp_path / "dynamic.py"),
        "--semantic-output",
        str(tmp_path / "dynamic-semantic.json"),
    )
    assert result.returncode == 2
    assert "unresolved dynamic ownership" in result.stderr

    payload = json.loads(targets.read_text(encoding="utf-8"))
    comparison = next(
        item
        for item in payload["site_classifications"]
        if item["site_type"] == "comparison" and item["kind"] == "confirmed"
    )
    comparison["kind"] = "assignment"
    incompatible = tmp_path / "incompatible.json"
    incompatible.write_text(json.dumps(payload), encoding="utf-8")
    result = _run(
        str(PROPOSE_PYTHON),
        "--targets",
        str(incompatible),
        "--output",
        str(tmp_path / "incompatible.py"),
        "--semantic-output",
        str(tmp_path / "incompatible-semantic.json"),
    )
    assert result.returncode == 2
    assert "comparison site has incompatible classification" in result.stderr


def test_django_preserves_safe_kwargs_and_declared_labels_at_final_boundary(tmp_path):
    project = FIXTURE_ROOT / "django-options"
    targets = tmp_path / "targets.json"
    proposal = tmp_path / "proposal.md"
    semantic = tmp_path / "semantic.json"
    collected = _run(
        str(COLLECT),
        "--target",
        "app/models.py::state::Ticket",
        "--project-root",
        str(project),
        "--output",
        str(targets),
    )
    assert collected.returncode == 0, collected.stderr
    payload = json.loads(targets.read_text(encoding="utf-8"))
    assert payload["current_kwargs"] == {
        "blank": True,
        "choices_ref": "STATE_CHOICES",
        "db_index": True,
        "default": "pending",
        "help_text": "Workflow state",
        "max_length": 32,
        "null": True,
    }

    proposed = _run(
        str(PROPOSE),
        "--targets",
        str(targets),
        "--output",
        str(proposal),
        "--semantic-output",
        str(semantic),
    )
    assert proposed.returncode == 0, proposed.stderr
    semantics = json.loads(semantic.read_text(encoding="utf-8"))
    assert semantics["members"] == [
        {"label": "Awaiting triage", "name": "PENDING", "wire_value": "pending"},
        {"label": "In progress", "name": "RUNNING", "wire_value": "running"},
    ]
    text = proposal.read_text(encoding="utf-8")
    assert "PENDING = 'pending', 'Awaiting triage'" in text
    assert "RUNNING = 'running', 'In progress'" in text
    for option in (
        "null=True",
        "blank=True",
        "db_index=True",
        "help_text='Workflow state'",
    ):
        assert option in text


def test_django_collector_fails_closed_on_dynamic_or_unsupported_field_kwargs(tmp_path):
    project = tmp_path / "project"
    models = project / "app" / "models.py"
    models.parent.mkdir(parents=True)
    models.write_text(
        "from django.db import models\n"
        "CHOICES = ((\"pending\", \"Pending\"),)\n"
        "def label(): return \"dynamic\"\n"
        "class Job(models.Model):\n"
        "    status = models.CharField(max_length=16, default=\"pending\", "
        "choices=CHOICES, help_text=label())\n",
        encoding="utf-8",
    )
    (project / "app" / "services.py").write_text(
        "def check(job): return job.status == \"pending\"\n",
        encoding="utf-8",
    )
    output = tmp_path / "targets.json"

    result = _run(
        str(COLLECT),
        "--target",
        "app/models.py::status::Job",
        "--project-root",
        str(project),
        "--output",
        str(output),
    )

    assert result.returncode == 2
    assert "unsupported or dynamic field keyword 'help_text'" in result.stderr
    assert not output.exists()


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


def test_slice4_full_manifest_replay_is_byte_deterministic(tmp_path):
    output_root = tmp_path / "replay"
    manifest = tmp_path / "manifest.json"
    first = _run(
        str(REPLAY),
        "record",
        "--output-root",
        str(output_root),
        "--manifest",
        str(manifest),
        "--reviewed-revision",
        "0" * 40,
        "--reviewed-tree",
        "1" * 40,
    )
    assert first.returncode == 0, first.stderr
    first_bytes = manifest.read_bytes()

    verified = _run(str(REPLAY), "verify", "--manifest", str(manifest))
    assert verified.returncode == 0, verified.stderr
    second = _run(
        str(REPLAY),
        "record",
        "--output-root",
        str(output_root),
        "--manifest",
        str(manifest),
        "--reviewed-revision",
        "0" * 40,
        "--reviewed-tree",
        "1" * 40,
    )
    assert second.returncode == 0, second.stderr
    assert manifest.read_bytes() == first_bytes


def test_collector_rejects_nondeterministic_scope_clock_before_writing(tmp_path):
    output = tmp_path / "targets.json"
    result = _run(
        str(COLLECT),
        "--target",
        "app.py::status::Job",
        "--project-root",
        str(FIXTURE_ROOT / "python"),
        "--output",
        str(output),
        "--scope-written-at",
        "2000-01-01T00:00:00",
    )

    assert result.returncode == 2
    assert "--scope-written-at must include a UTC offset" in result.stderr
    assert not output.exists()
