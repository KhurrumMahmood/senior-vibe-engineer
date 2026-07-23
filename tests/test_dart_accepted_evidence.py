"""Contract tests for the consumer-independent Dart acceptance envelope."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".claude/skills/_dart/dart_accepted_evidence.py"
PRODUCT_PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module(path: Path = VALIDATOR):
    spec = importlib.util.spec_from_file_location("test_dart_accepted_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _write_json(path: Path, value: object) -> Path:
    return _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _accepted_fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    root = tmp_path / "host"
    source = _write(
        root / "lib/state.dart",
        "class Job {\n  late String state;\n}\n",
    )
    config = _write(
        root / ".dart_tool/package_config.json",
        '{"configVersion":2,"packages":[]}\n',
    )
    evidence = root / "reports/implicit-state/dart"
    finding = {
        "candidate_id": "dart-implicit-state-0001",
        "candidate_sha256": "1" * 64,
        "bucket": "extract_enum_candidate",
        "human_verdict": "accepted",
        "owner": "Job",
        "field": "state",
        "file": "lib/state.dart",
        "line": 2,
        "column": 15,
    }
    findings = {
        "schema_version": "dart-implicit-state-v1",
        "language": "dart",
        "status": "complete",
        "read_only": True,
        "findings": [finding],
    }
    _write_json(evidence / "findings.json", findings)
    _write_json(evidence / "facts.json", {"schema_version": "dart-lsp-facts-v1"})
    _write_json(evidence / "scan.json", {"status": "complete"})
    _write_json(
        evidence / "scout/dart-implicit-state-0001.json",
        {"human_verdict": "accepted", "candidate_sha256": "1" * 64},
    )
    artifacts = [
        {
            "path": path.relative_to(evidence).as_posix(),
            "sha256": _sha256(path),
        }
        for path in sorted(evidence.rglob("*.json"))
    ]
    envelope = {
        "schema_version": "dart-accepted-evidence-v1",
        "producer": {
            "skill": "find-implicit-state",
            "version": "dart-d5-v1",
            "schema_version": "dart-implicit-state-v1",
            "terminal_status": "complete",
            "artifact": "findings.json",
        },
        "selection": {
            "kind": "extract_enum_candidate",
            "id": "dart-implicit-state-0001",
            "artifact": "findings.json",
            "json_pointer": "/findings/0",
            "sha256": _canonical_hash(finding),
        },
        "artifacts": artifacts,
        "source_hashes": [
            {"path": "lib/state.dart", "sha256": _sha256(source), "role": "production"}
        ],
        "configuration_hashes": [
            {
                "path": ".dart_tool/package_config.json",
                "sha256": _sha256(config),
                "kind": "dart_package_config",
            }
        ],
        "cited_spans": [
            {
                "path": "lib/state.dart",
                "start_line": 2,
                "start_column": 8,
                "end_line": 2,
                "end_column": 20,
                "sha256": hashlib.sha256(b"String state").hexdigest(),
            }
        ],
        "human_verdict": {
            "status": "accepted",
            "reviewer": "fixture-owner",
            "notes": "Bounded evidence accepted for one exact field.",
        },
        "reviewed_boundaries": {
            "domain": "bounded",
            "external_ownership": False,
        },
        "native_obligations": [
            {
                "name": "analyze",
                "argv": ["dart", "analyze", "--fatal-infos", "--fatal-warnings", "."],
                "expected_returncode": 0,
            }
        ],
    }
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    acceptance = _write_json(evidence / "acceptance.json", envelope)
    return root, evidence, acceptance, envelope


def test_acceptance_envelope_verifies_artifacts_selection_snapshot_and_span(
    tmp_path: Path,
) -> None:
    root, evidence, acceptance, envelope = _accepted_fixture(tmp_path)
    validator = _module()

    result = validator.validate_accepted_evidence(
        root,
        evidence,
        acceptance,
        expected_producer="find-implicit-state",
        expected_kind="extract_enum_candidate",
    )

    assert result["envelope"]["acceptance_hash"] == envelope["acceptance_hash"]
    assert result["selected_evidence"]["owner"] == "Job"
    assert result["current_snapshot_verified"] is True
    assert set(result["verified_artifacts"]) == {
        "facts.json",
        "findings.json",
        "scan.json",
        "scout/dart-implicit-state-0001.json",
    }


@pytest.mark.parametrize(
    ("mutate", "status", "failure_kind"),
    [
        (
            lambda payload: payload["producer"].update(terminal_status="partial"),
            "partial",
            "upstream_not_complete",
        ),
        (
            lambda payload: payload["human_verdict"].update(status="pending"),
            "partial",
            "human_acceptance_required",
        ),
        (
            lambda payload: payload["selection"].update(sha256="0" * 64),
            "failed",
            "invalid_accepted_evidence",
        ),
    ],
)
def test_partial_unaccepted_and_mismatched_selection_stop_honestly(
    tmp_path: Path, mutate, status: str, failure_kind: str
) -> None:
    root, evidence, acceptance, _ = _accepted_fixture(tmp_path)
    payload = json.loads(acceptance.read_text())
    mutate(payload)
    payload.pop("acceptance_hash")
    payload["acceptance_hash"] = _canonical_hash(payload)
    _write_json(acceptance, payload)
    validator = _module()

    with pytest.raises(validator.AcceptedEvidenceError) as raised:
        validator.validate_accepted_evidence(
            root,
            evidence,
            acceptance,
            expected_producer="find-implicit-state",
        )

    assert raised.value.status == status
    assert raised.value.failure_kind == failure_kind


def test_artifact_and_source_staleness_are_distinct_and_artifacts_always_verify(
    tmp_path: Path,
) -> None:
    root, evidence, acceptance, _ = _accepted_fixture(tmp_path)
    validator = _module()
    source = root / "lib/state.dart"
    source.write_text(source.read_text() + "// intentional migration\n", encoding="utf-8")

    with pytest.raises(validator.AcceptedEvidenceError) as stale:
        validator.validate_accepted_evidence(
            root,
            evidence,
            acceptance,
            expected_producer="find-implicit-state",
        )
    assert stale.value.status == "failed"
    assert stale.value.failure_kind == "stale_accepted_evidence"

    transitioned = validator.validate_accepted_evidence(
        root,
        evidence,
        acceptance,
        expected_producer="find-implicit-state",
        verify_current_sources=False,
    )
    assert transitioned["current_snapshot_verified"] is False

    (evidence / "facts.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(validator.AcceptedEvidenceError) as tampered:
        validator.validate_accepted_evidence(
            root,
            evidence,
            acceptance,
            expected_producer="find-implicit-state",
            verify_current_sources=False,
        )
    assert tampered.value.failure_kind == "invalid_accepted_evidence"


def test_acceptance_hash_configuration_and_span_freshness_are_mandatory(
    tmp_path: Path,
) -> None:
    validator = _module()
    root, evidence, acceptance, _ = _accepted_fixture(tmp_path / "acceptance")
    payload = json.loads(acceptance.read_text())
    payload["human_verdict"]["notes"] = "Changed after acceptance."
    _write_json(acceptance, payload)
    with pytest.raises(validator.AcceptedEvidenceError) as bad_acceptance:
        validator.validate_accepted_evidence(
            root, evidence, acceptance, expected_producer="find-implicit-state"
        )
    assert bad_acceptance.value.failure_kind == "invalid_accepted_evidence"

    root, evidence, acceptance, _ = _accepted_fixture(tmp_path / "configuration")
    (root / ".dart_tool/package_config.json").write_text(
        '{"configVersion":2,"packages":[{"name":"changed"}]}\n', encoding="utf-8"
    )
    with pytest.raises(validator.AcceptedEvidenceError) as stale_configuration:
        validator.validate_accepted_evidence(
            root, evidence, acceptance, expected_producer="find-implicit-state"
        )
    assert stale_configuration.value.failure_kind == "stale_accepted_evidence"

    root, evidence, acceptance, _ = _accepted_fixture(tmp_path / "span")
    payload = json.loads(acceptance.read_text())
    payload["cited_spans"][0]["start_column"] = 9
    payload.pop("acceptance_hash")
    payload["acceptance_hash"] = _canonical_hash(payload)
    _write_json(acceptance, payload)
    with pytest.raises(validator.AcceptedEvidenceError) as stale_span:
        validator.validate_accepted_evidence(
            root, evidence, acceptance, expected_producer="find-implicit-state"
        )
    assert stale_span.value.failure_kind == "stale_accepted_evidence"


def test_missing_and_unsafe_evidence_stop_without_path_escape(tmp_path: Path) -> None:
    root, evidence, acceptance, _ = _accepted_fixture(tmp_path)
    validator = _module()
    (evidence / "scan.json").unlink()
    with pytest.raises(validator.AcceptedEvidenceError) as missing:
        validator.validate_accepted_evidence(
            root,
            evidence,
            acceptance,
            expected_producer="find-implicit-state",
        )
    assert missing.value.status == "partial"
    assert missing.value.failure_kind == "evidence_unavailable"

    root, evidence, acceptance, _ = _accepted_fixture(tmp_path / "unsafe")
    outside = _write(tmp_path / "outside.json", "{}\n")
    linked = evidence / "facts.json"
    linked.unlink()
    linked.symlink_to(outside)
    with pytest.raises(validator.AcceptedEvidenceError) as unsafe:
        validator.validate_accepted_evidence(
            root,
            evidence,
            acceptance,
            expected_producer="find-implicit-state",
        )
    assert unsafe.value.status == "failed"
    assert unsafe.value.failure_kind == "invalid_accepted_evidence"


def test_copied_validator_cli_runs_outside_repository(tmp_path: Path) -> None:
    root, evidence, acceptance, envelope = _accepted_fixture(tmp_path)
    installed = tmp_path / "installed/.agents/skills/on-demand/_dart"
    installed.mkdir(parents=True)
    copied = installed / VALIDATOR.name
    shutil.copy2(VALIDATOR, copied)

    result = subprocess.run(
        [
            str(PRODUCT_PYTHON),
            str(copied),
            "--project-root",
            str(root),
            "--evidence-dir",
            str(evidence),
            "--acceptance",
            str(acceptance),
            "--expected-producer",
            "find-implicit-state",
            "--expected-kind",
            "extract_enum_candidate",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["acceptance_hash"] == envelope["acceptance_hash"]
    assert payload["current_snapshot_verified"] is True
