"""Final-outcome tests for Dart D6 accepted state consumers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/dart-d6"
VALIDATOR = ROOT / ".claude/skills/_dart/dart_accepted_evidence.py"
COLLECTOR = ROOT / ".claude/skills/extract-enum/scripts/collect_dart_state.py"
GENERATOR = ROOT / ".claude/skills/prevent-regression/scripts/generate_dart_state_guard.py"
VERIFIER = ROOT / ".claude/skills/prevent-regression/scripts/verify_dart_state_guard.py"
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
PRODUCT_PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)

pytestmark = pytest.mark.skipif(
    not DART.is_file() or not PRODUCT_PYTHON.is_file(),
    reason="the frozen Dart 3.12 SDK and product Python are required",
)


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host)
    return host


def _snapshot(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if "reports" in relative.parts:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = _sha256(path)
    return rows


def _span(source: Path, snippet: str, *, occurrence: int = 1) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    start = -1
    for _ in range(occurrence):
        start = text.index(snippet, start + 1)
    end = start + len(snippet)
    before = text[:start]
    before_end = text[:end]
    return {
        "path": source.as_posix(),
        "start_line": before.count("\n") + 1,
        "start_column": start - before.rfind("\n"),
        "end_line": before_end.count("\n") + 1,
        "end_column": end - before_end.rfind("\n"),
        "sha256": hashlib.sha256(snippet.encode()).hexdigest(),
    }


def _relative_span(host: Path, source: Path, snippet: str, *, occurrence: int = 1) -> dict[str, Any]:
    row = _span(source, snippet, occurrence=occurrence)
    row["path"] = source.relative_to(host).as_posix()
    return row


def _source_rows(host: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(host.rglob("*.dart")):
        relative = path.relative_to(host)
        if "reports" in relative.parts:
            continue
        role = "production"
        if relative.parts[0] == "test":
            role = "test"
        elif relative.parts[0] == "bin":
            role = "executable"
        elif relative.parts[0] == "generated" or path.name.endswith(".g.dart"):
            role = "generated"
        rows.append({"path": relative.as_posix(), "sha256": _sha256(path), "role": role})
    return rows


def _native_obligations(package: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "analyze",
            "argv": ["dart", "analyze", "--fatal-infos", "--fatal-warnings", "."],
            "expected_returncode": 0,
        },
        {
            "name": "format",
            "argv": [
                "dart",
                "format",
                "--output=none",
                "--set-exit-if-changed",
                "lib",
                "bin",
                "test",
            ],
            "expected_returncode": 0,
        },
        {
            "name": "direct_test",
            "argv": ["dart", "test/native_test.dart"],
            "expected_returncode": 0,
        },
        {
            "name": "smoke",
            "argv": ["dart", "bin/smoke.dart"],
            "expected_returncode": 0,
            "expected_stdout": "42",
            "package": package,
        },
    ]


def _reseal_acceptance(evidence: Path, envelope: dict[str, Any]) -> Path:
    for artifact in envelope["artifacts"]:
        artifact["sha256"] = _sha256(evidence / artifact["path"])
    envelope.pop("acceptance_hash", None)
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    return _write_json(evidence / "acceptance.json", envelope)


def _accepted_d5(host: Path, mode: str) -> tuple[Path, Path]:
    evidence = host / "reports/implicit-state/dart"
    evidence.mkdir(parents=True)
    source_rows = _source_rows(host)
    config = host / ".dart_tool/package_config.json"
    facts: dict[str, Any] = {
        "schema_version": "dart-lsp-facts-v1",
        "language": "dart",
        "status": "complete",
        "failure_kind": None,
        "target": "lib",
        "source_hashes": source_rows,
        "source_inventory": [
            {"path": row["path"], "role": row["role"], "sha256": row["sha256"]}
            for row in source_rows
        ],
        "package_config": {
            "state": "present",
            "path": str(config),
            "sha256": _sha256(config),
        },
        "query_plan": {"queries": ["state"], "requests": ["textDocument/definition"]},
        "query_plan_sha256": _canonical_hash(
            {"queries": ["state"], "requests": ["textDocument/definition"]}
        ),
        "native_obligations": _native_obligations(host.name.replace("-", "_")),
    }
    facts["fact_pack_sha256"] = _canonical_hash(facts)
    _write_json(evidence / "facts.json", facts)

    if mode in {"positive", "refusal"}:
        source = next(
            path
            for path in sorted((host / "lib").glob("*.dart"))
            if "String state" in path.read_text(encoding="utf-8")
        )
        owner = "Job" if mode == "positive" else "_ExternalJob"
        text = source.read_text(encoding="utf-8")
        field_line = text[: text.index("String state")].count("\n") + 1
        field_column = text.splitlines()[field_line - 1].index("state") + 1
        operation_specs = [
            ("assignment", "state = 'queued'", "queued"),
            ("assignment", "state = 'running'", "running"),
            ("comparison", "state == 'done'", "done"),
        ]
        operations = []
        for kind, syntax, literal in operation_specs:
            offset = text.index(syntax)
            line = text[:offset].count("\n") + 1
            column = text.splitlines()[line - 1].index("state") + 1
            operations.append(
                {
                    "kind": kind,
                    "literal": literal,
                    "syntax": syntax,
                    "file": source.relative_to(host).as_posix(),
                    "line": line,
                    "column": column,
                    "definition_targets": [
                        {
                            "path": source.relative_to(host).as_posix(),
                            "line": field_line,
                            "column": field_column,
                        }
                    ],
                }
            )
        candidate: dict[str, Any] = {
            "candidate_id": "dart-implicit-state-0001",
            "owner": owner,
            "field": "state",
            "type": "String",
            "file": source.relative_to(host).as_posix(),
            "line": field_line,
            "column": field_column,
            "pattern": "stringly_compare",
            "literals": ["done", "queued", "running"],
            "operations": operations,
            "human_verdict": "required",
            "boundary": "candidate only; the value domain is not proven closed",
            "fact_pack_sha256": facts["fact_pack_sha256"],
        }
        candidate["candidate_sha256"] = _canonical_hash(candidate)
        candidates_text = json.dumps(candidate, sort_keys=True) + "\n"
        (evidence / "candidates.jsonl").write_text(candidates_text, encoding="utf-8")
        review = {
            "schema_version": "dart-implicit-state-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "bucket": "extract_enum_candidate",
            "confidence": "high",
            "human_verdict": "accepted",
            "notes": "The identity-resolved candidate is accepted for explicit boundary review.",
        }
        _write_json(evidence / "scout/dart-implicit-state-0001.json", review)
        finding = {
            **candidate,
            "bucket": "extract_enum_candidate",
            "confidence": "high",
            "human_verdict": "accepted",
            "review_notes": review["notes"],
        }
        findings = [finding]
        classifications: list[dict[str, Any]] = []
        selection_kind = "extract_enum_candidate"
        selection_pointer = "/findings/0"
        selection_row = finding
        if mode == "positive":
            boundaries = {
                "domain": {
                    "closed_for_proposal": True,
                    "unknown_value_policy": "reject",
                },
                "serialization": {
                    "reviewed": True,
                    "observed": True,
                    "strategy": "preserve_wire_values",
                    "syntax": "{'state': state}",
                    "replacement": "{'state': state.wireValue}",
                },
                "public_compatibility": {
                    "reviewed": True,
                    "impact": "breaking_field_type",
                    "migration": "coordinated_callers",
                },
                "reflection": {"reviewed": True, "uncertain": False},
                "external_api": {"owned_elsewhere": False},
                "generated_owner": False,
                "ambiguous_authority": False,
                "enum": {
                    "type_name": "JobState",
                    "variants": [
                        {"name": "done", "wire_value": "done"},
                        {"name": "queued", "wire_value": "queued"},
                        {"name": "running", "wire_value": "running"},
                    ],
                },
            }
        else:
            boundaries = {
                "domain": {"closed_for_proposal": False},
                "serialization": {"reviewed": False, "observed": True},
                "public_compatibility": {"reviewed": False},
                "reflection": {"reviewed": False, "uncertain": True},
                "external_api": {"owned_elsewhere": True},
                "generated_owner": False,
                "ambiguous_authority": False,
                "enum": {"type_name": "ExternalJobState", "variants": []},
            }
        cited = [
            _relative_span(host, source, "String state"),
            *[_relative_span(host, source, syntax) for _, syntax, _ in operation_specs],
        ]
        if mode == "positive":
            cited.append(_relative_span(host, source, "{'state': state}"))
    else:
        source = host / "lib/state.dart"
        text = source.read_text(encoding="utf-8")
        field_offset = text.index("JobState state")
        field_line = text[:field_offset].count("\n") + 1
        field_column = text.splitlines()[field_line - 1].index("state") + 1
        candidate = None
        candidates_text = ""
        (evidence / "candidates.jsonl").write_text(candidates_text, encoding="utf-8")
        findings = []
        classifications = [
            {
                "owner": "Job",
                "field": "state",
                "type": "JobState",
                "file": "lib/state.dart",
                "line": field_line,
                "column": field_column,
                "classification": "typed_state_authority",
            }
        ]
        selection_kind = "enum_already_owned"
        selection_pointer = "/classifications/0"
        selection_row = classifications[0]
        boundaries = {
            "already_typed": True,
            "type_name": "JobState",
            "public_compatibility": {"reviewed": True, "impact": "none"},
        }
        cited = [_relative_span(host, source, "JobState state")]

    findings_payload = {
        "schema_version": "dart-implicit-state-v1",
        "language": "dart",
        "read_only": True,
        "status": "complete",
        "failure_kind": None,
        "target": "lib",
        "analyzer": "dart-sdk-lsp-field-definition-operations",
        "findings": findings,
        "classifications": classifications,
        "deferred": [],
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "query_plan_sha256": facts["query_plan_sha256"],
        "source_hashes": source_rows,
    }
    findings_path = _write_json(evidence / "findings.json", findings_payload)
    scan = {
        "schema_version": "dart-implicit-state-scan-v1",
        "status": "complete",
        "failure_kind": None,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "candidate_count": 1 if candidate else 0,
        "accepted_count": len(findings),
        "candidates_sha256": hashlib.sha256(candidates_text.encode()).hexdigest(),
        "findings_sha256": _sha256(findings_path),
    }
    _write_json(evidence / "scan.json", scan)
    artifacts = [
        {"path": path.relative_to(evidence).as_posix(), "sha256": _sha256(path)}
        for path in sorted(evidence.rglob("*"))
        if path.is_file()
    ]
    envelope: dict[str, Any] = {
        "schema_version": "dart-accepted-evidence-v1",
        "producer": {
            "skill": "find-implicit-state",
            "version": "dart-d5-v1",
            "schema_version": "dart-implicit-state-v1",
            "terminal_status": "complete",
            "artifact": "findings.json",
        },
        "selection": {
            "kind": selection_kind,
            "id": "dart-implicit-state-0001" if candidate else "Job.state",
            "artifact": "findings.json",
            "json_pointer": selection_pointer,
            "sha256": _canonical_hash(selection_row),
        },
        "artifacts": artifacts,
        "source_hashes": source_rows,
        "configuration_hashes": [
            {"path": "pubspec.yaml", "sha256": _sha256(host / "pubspec.yaml"), "kind": "pubspec"},
            {
                "path": ".dart_tool/package_config.json",
                "sha256": _sha256(config),
                "kind": "dart_package_config",
            },
        ],
        "cited_spans": cited,
        "human_verdict": {
            "status": "accepted",
            "reviewer": "fixture-owner",
            "notes": "The exact selected evidence and boundaries were reviewed.",
        },
        "reviewed_boundaries": boundaries,
        "native_obligations": _native_obligations(host.name.replace("-", "_")),
    }
    acceptance = _reseal_acceptance(evidence, envelope)
    return evidence, acceptance


def _collect(
    host: Path,
    evidence: Path,
    acceptance: Path,
    *,
    output: str = "reports/extract-enum/dart-state",
    expected: int = 0,
    script: Path = COLLECTOR,
) -> Path:
    _run(
        PRODUCT_PYTHON,
        script,
        "--project-root",
        host,
        "--evidence-dir",
        evidence,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        cwd=host,
        expected=expected,
    )
    return host / output


def _apply_proposal(host: Path, targets: dict[str, Any]) -> None:
    for edit in targets["rewrite_plan"]["edits"]:
        path = host / edit["file"]
        text = path.read_text(encoding="utf-8")
        assert text.count(edit["old"]) == 1
        path.write_text(text.replace(edit["old"], edit["new"]), encoding="utf-8")
    validation = targets["disposable_validation_test"]
    destination = host / validation["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(validation["content"], encoding="utf-8")


def _native_matrix(host: Path, *, value_test: bool = False) -> None:
    _run(DART, "analyze", "--fatal-infos", "--fatal-warnings", ".", cwd=host)
    roots = [name for name in ("lib", "bin", "tool", "test") if (host / name).is_dir()]
    _run(DART, "format", "--output=none", "--set-exit-if-changed", *roots, cwd=host)
    _run(DART, "test/native_test.dart", cwd=host)
    if value_test:
        _run(DART, "test/dart_d6_enum_values.dart", cwd=host)
    smoke = _run(DART, "bin/smoke.dart", cwd=host)
    assert smoke.stdout.strip() == "42"


def test_dart_d6_fixture_native_baselines() -> None:
    for name in ("positive", "clean", "refusal"):
        _native_matrix(FIXTURE / name)


def test_extract_enum_builds_an_implementation_ready_proposal_and_native_after_tree(
    tmp_path: Path,
) -> None:
    host = _copy_fixture(tmp_path, "positive")
    evidence, acceptance = _accepted_d5(host, "positive")
    before = _snapshot(host)

    output = _collect(host, evidence, acceptance)

    targets = json.loads((output / "targets.json").read_text())
    assert targets["status"] == "complete"
    assert targets["outcome"] == "proposal_ready"
    assert targets["accepted_evidence_hash"] == json.loads(acceptance.read_text())[
        "acceptance_hash"
    ]
    assert targets["authority"] == {
        "owner": "Job",
        "field": "state",
        "current_type": "String",
        "declaration_file": "lib/state.dart",
        "declaration_line": 2,
        "source_sha256": _sha256(host / "lib/state.dart"),
        "visibility": "public",
    }
    assert [row["wire_value"] for row in targets["proposed_enum"]["variants"]] == [
        "done",
        "queued",
        "running",
    ]
    assert targets["boundaries"]["serialization"]["strategy"] == "preserve_wire_values"
    assert targets["boundaries"]["public_compatibility"]["impact"] == "breaking_field_type"
    assert len(targets["rewrite_plan"]["edits"]) == 6
    assert "This proposal does not edit source" in (output / "profile.md").read_text()
    proposal = (output / "proposal.md").read_text()
    assert "enum JobState" in proposal
    assert "JobState fromWire" in proposal
    assert "breaking field-type change" in proposal
    assert _snapshot(host) == before

    after = tmp_path / "disposable-after"
    shutil.copytree(host, after, ignore=shutil.ignore_patterns("reports"))
    _apply_proposal(after, targets)
    _native_matrix(after, value_test=True)


def test_extract_enum_clean_typed_state_is_an_explicit_no_proposal(tmp_path: Path) -> None:
    host = _copy_fixture(tmp_path, "clean")
    evidence, acceptance = _accepted_d5(host, "clean")
    before = _snapshot(host)

    output = _collect(host, evidence, acceptance)
    targets = json.loads((output / "targets.json").read_text())

    assert targets["status"] == "complete"
    assert targets["outcome"] == "no_proposal_already_typed"
    assert targets["rewrite_plan"]["edits"] == []
    assert "No enum proposal is needed" in (output / "proposal.md").read_text()
    assert _snapshot(host) == before


@pytest.mark.parametrize(
    "refusal",
    [
        "partial",
        "unaccepted",
        "stale",
        "open_domain",
        "serialization_uncertain",
        "external_owner",
        "reflection_uncertain",
        "ambiguous_authority",
        "generated_owner",
        "invalid_fact_pack",
        "missing_evidence",
    ],
)
def test_extract_enum_refusals_replace_stale_proposals(
    tmp_path: Path, refusal: str
) -> None:
    fixture = "refusal" if refusal == "external_owner" else "positive"
    mode = "refusal" if fixture == "refusal" else "positive"
    host = _copy_fixture(tmp_path, fixture)
    evidence, acceptance = _accepted_d5(host, mode)
    envelope = json.loads(acceptance.read_text())
    if refusal == "partial":
        findings = json.loads((evidence / "findings.json").read_text())
        findings["status"] = "partial"
        findings["failure_kind"] = "semantic_boundary"
        _write_json(evidence / "findings.json", findings)
        envelope["producer"]["terminal_status"] = "partial"
    elif refusal == "unaccepted":
        envelope["human_verdict"]["status"] = "pending"
    elif refusal == "stale":
        source = host / envelope["source_hashes"][0]["path"]
        source.write_text(source.read_text() + "// stale\n", encoding="utf-8")
    elif refusal == "invalid_fact_pack":
        facts = json.loads((evidence / "facts.json").read_text())
        facts["fact_pack_sha256"] = "0" * 64
        _write_json(evidence / "facts.json", facts)
    elif refusal == "missing_evidence":
        (evidence / "facts.json").unlink()
    else:
        boundaries = envelope["reviewed_boundaries"]
        if refusal == "open_domain":
            boundaries["domain"]["closed_for_proposal"] = False
        elif refusal == "serialization_uncertain":
            boundaries["serialization"]["reviewed"] = False
        elif refusal == "reflection_uncertain":
            boundaries["reflection"]["uncertain"] = True
        elif refusal == "ambiguous_authority":
            boundaries["ambiguous_authority"] = True
        elif refusal == "generated_owner":
            boundaries["generated_owner"] = True
    if refusal != "missing_evidence":
        acceptance = _reseal_acceptance(evidence, envelope)
    output = host / "reports/extract-enum/reuse"
    output.mkdir(parents=True)
    (output / "proposal.md").write_text("stale proposal\n", encoding="utf-8")

    _collect(host, evidence, acceptance, output="reports/extract-enum/reuse", expected=2)

    terminal = json.loads((output / "targets.json").read_text())
    assert terminal["status"] in {"partial", "failed"}
    assert terminal["outcome"] == "refused"
    assert not (output / "proposal.md").exists()
    assert "refused" in (output / "profile.md").read_text().lower()


def test_extract_enum_valid_partial_valid_lifecycle_and_copied_closure(
    tmp_path: Path,
) -> None:
    host = _copy_fixture(tmp_path, "positive")
    evidence, acceptance = _accepted_d5(host, "positive")
    output = _collect(host, evidence, acceptance, output="reports/extract-enum/reuse")
    assert (output / "proposal.md").is_file()
    envelope = json.loads(acceptance.read_text())
    envelope["human_verdict"]["status"] = "pending"
    acceptance = _reseal_acceptance(evidence, envelope)
    _collect(
        host,
        evidence,
        acceptance,
        output="reports/extract-enum/reuse",
        expected=2,
    )
    assert not (output / "proposal.md").exists()
    envelope["human_verdict"]["status"] = "accepted"
    acceptance = _reseal_acceptance(evidence, envelope)
    _collect(host, evidence, acceptance, output="reports/extract-enum/reuse")
    assert (output / "proposal.md").is_file()

    closure = tmp_path / "installed/.agents/skills/on-demand"
    copied_collector = closure / "extract-enum/scripts/collect_dart_state.py"
    copied_validator = closure / "_dart/dart_accepted_evidence.py"
    copied_collector.parent.mkdir(parents=True)
    copied_validator.parent.mkdir(parents=True)
    shutil.copy2(COLLECTOR, copied_collector)
    shutil.copy2(VALIDATOR, copied_validator)
    copied = _collect(
        host,
        evidence,
        acceptance,
        output="reports/extract-enum/copied",
        script=copied_collector,
    )
    assert json.loads((copied / "targets.json").read_text())["outcome"] == "proposal_ready"
    text = COLLECTOR.read_text() + VALIDATOR.read_text()
    assert "language-server" not in text
    assert "package:analyzer" not in text


def _migrated_flow(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, Any]]:
    before = _copy_fixture(tmp_path, "positive")
    evidence, acceptance = _accepted_d5(before, "positive")
    proposal_dir = _collect(before, evidence, acceptance)
    targets = json.loads((proposal_dir / "targets.json").read_text())
    migrated = tmp_path / "migrated"
    shutil.copytree(before, migrated)
    _apply_proposal(migrated, targets)
    migrated_evidence = migrated / evidence.relative_to(before)
    migrated_acceptance = migrated / acceptance.relative_to(before)
    migrated_proposal = migrated / proposal_dir.relative_to(before)
    return migrated, migrated_evidence, migrated_acceptance, migrated_proposal, targets


def _accepted_proposal(
    host: Path,
    proposal_dir: Path,
    targets: dict[str, Any],
    *,
    mutate: str | None = None,
) -> Path:
    source = host / targets["authority"]["declaration_file"]
    lines = source.read_text(encoding="utf-8").splitlines()
    field_line = next(
        index
        for index, line in enumerate(lines, 1)
        if re.search(r"\blate\s+JobState\s+state\s*;", line)
    )
    review: dict[str, Any] = {
        "schema_version": "dart-enum-proposal-review-v1",
        "language": "dart",
        "status": "accepted",
        "targets_sha256": _sha256(proposal_dir / "targets.json"),
        "accepted_evidence_hash": targets["accepted_evidence_hash"],
        "candidate_id": targets["candidate_id"],
        "authority": {
            "owner": "Job",
            "field": "state",
            "declaration_file": "lib/state.dart",
            "declaration_line": field_line,
            "source_sha256": _sha256(source),
            "expected_type": "JobState",
            "visibility": "public",
            "generated": False,
            "external_owner": False,
        },
        "enum": targets["proposed_enum"],
        "guard": {
            "kind": "dependency_free_direct_type_guard",
            "tool_destination": "tool/job_state_guard.dart",
            "test_destination": "test/job_state_guard_test.dart",
            "import_uri": "../lib/state.dart",
            "expected_stdout": "dart-state-guard-ok",
        },
        "native_obligations": targets["native_obligations"],
        "accepted_nonclaims": targets["nonclaims"],
        "human_verdict": {
            "reviewer": "fixture-owner",
            "notes": "The migrated exact field and project-owned guard destinations are accepted.",
        },
    }
    if mutate == "unaccepted":
        review["status"] = "pending"
    elif mutate == "private":
        review["authority"]["visibility"] = "private"
    elif mutate == "generated":
        review["authority"]["generated"] = True
    elif mutate == "external":
        review["authority"]["external_owner"] = True
    elif mutate == "unavailable_guard":
        review["guard"]["kind"] = "dynamic_runtime_probe"
    elif mutate == "unrelated":
        review["candidate_id"] = "dart-implicit-state-unrelated"
    review["acceptance_hash"] = _canonical_hash(review)
    return _write_json(proposal_dir / "accepted-review.json", review)


def _generate_guard(
    host: Path,
    evidence: Path,
    acceptance: Path,
    proposal_dir: Path,
    review: Path,
    *,
    output: str = "reports/prevent-regression/dart-state",
    expected: int = 0,
    script: Path = GENERATOR,
) -> Path:
    _run(
        PRODUCT_PYTHON,
        script,
        "--project-root",
        host,
        "--evidence-dir",
        evidence,
        "--acceptance",
        acceptance,
        "--targets",
        proposal_dir / "targets.json",
        "--accepted-review",
        review,
        "--output-root",
        output,
        cwd=host,
        expected=expected,
    )
    return host / output


def _verify_guard(
    host: Path,
    stage: Path,
    *,
    expected: int = 0,
    script: Path = VERIFIER,
) -> dict[str, Any]:
    _run(
        PRODUCT_PYTHON,
        script,
        "--project-root",
        host,
        "--stage",
        stage,
        "--dart",
        DART,
        cwd=host,
        expected=expected,
        timeout=180,
    )
    return json.loads((stage / "verification.json").read_text())


def test_prevent_regression_stages_and_proves_exact_native_guard_without_host_install(
    tmp_path: Path,
) -> None:
    host, evidence, acceptance, proposal_dir, targets = _migrated_flow(tmp_path)
    review = _accepted_proposal(host, proposal_dir, targets)
    before = _snapshot(host)

    stage = _generate_guard(host, evidence, acceptance, proposal_dir, review)

    expected_files = {
        "authority.json",
        "host-wiring.diff",
        "pattern.md",
        "proposal.md",
        "staged/test/job_state_guard_test.dart",
        "staged/tool/job_state_guard.dart",
        "verification.json",
    }
    assert {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file()
    } == expected_files
    pending = json.loads((stage / "verification.json").read_text())
    assert pending["status"] == "partial"
    assert pending["failure_kind"] == "native_verification_required"
    assert "never installs" in (stage / "proposal.md").read_text()
    assert "copy staged/tool/job_state_guard.dart" in (stage / "host-wiring.diff").read_text()
    assert not (host / "tool/job_state_guard.dart").exists()
    assert not (host / "test/job_state_guard_test.dart").exists()
    assert _snapshot(host) == before

    verification = _verify_guard(host, stage)

    assert verification["status"] == "complete"
    assert verification["outcome"] == "guard_proved"
    assert verification["source_preserved"] is True
    assert verification["audited_host_writes"] == []
    assert all(row["returncode"] == 0 for row in verification["good_native"].values())
    assert all(
        row["returncode"] == 0
        for row in verification["seeded_regression"]["without_guard"].values()
    )
    assert verification["seeded_regression"]["with_guard"]["returncode"] != 0
    assert verification["seeded_regression"]["caught_by_guard"] is True
    assert verification["native_values"] == {
        "done": "done",
        "queued": "queued",
        "running": "running",
    }
    assert _snapshot(host) == before


def test_prevent_regression_detects_existing_equivalent_guard_without_duplicate_stage(
    tmp_path: Path,
) -> None:
    host, evidence, acceptance, proposal_dir, targets = _migrated_flow(tmp_path)
    review = _accepted_proposal(host, proposal_dir, targets)
    first = _generate_guard(host, evidence, acceptance, proposal_dir, review, output="reports/prevent-regression/first")
    for relative in ("tool/job_state_guard.dart", "test/job_state_guard_test.dart"):
        destination = host / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(first / "staged" / relative, destination)

    existing = _generate_guard(
        host,
        evidence,
        acceptance,
        proposal_dir,
        review,
        output="reports/prevent-regression/existing",
    )
    authority = json.loads((existing / "authority.json").read_text())
    verification = json.loads((existing / "verification.json").read_text())
    assert authority["outcome"] == "equivalent_guard_exists"
    assert verification["status"] == "complete"
    assert verification["outcome"] == "equivalent_guard_exists"
    assert not (existing / "staged").exists()


@pytest.mark.parametrize(
    "refusal",
    [
        "unaccepted",
        "private",
        "generated",
        "external",
        "unavailable_guard",
        "unrelated",
        "stale_targets",
        "stale_source",
        "stale_evidence",
        "missing_evidence",
    ],
)
def test_prevent_regression_refuses_unaccepted_stale_or_unsupported_authority(
    tmp_path: Path, refusal: str
) -> None:
    host, evidence, acceptance, proposal_dir, targets = _migrated_flow(tmp_path)
    review_mutation = refusal if refusal in {
        "unaccepted",
        "private",
        "generated",
        "external",
        "unavailable_guard",
        "unrelated",
    } else None
    review = _accepted_proposal(host, proposal_dir, targets, mutate=review_mutation)
    if refusal == "stale_targets":
        targets_payload = json.loads((proposal_dir / "targets.json").read_text())
        targets_payload["next_step"] = "changed after review"
        _write_json(proposal_dir / "targets.json", targets_payload)
    elif refusal == "stale_source":
        source = host / targets["authority"]["declaration_file"]
        source.write_text(source.read_text() + "// changed after proposal review\n", encoding="utf-8")
    elif refusal == "stale_evidence":
        (evidence / "facts.json").write_text("{}\n", encoding="utf-8")
    elif refusal == "missing_evidence":
        (evidence / "facts.json").unlink()
    output = host / "reports/prevent-regression/reuse"
    output.mkdir(parents=True)
    (output / "staged").mkdir()
    (output / "staged/old.dart").write_text("stale\n", encoding="utf-8")

    _generate_guard(
        host,
        evidence,
        acceptance,
        proposal_dir,
        review,
        output="reports/prevent-regression/reuse",
        expected=2,
    )

    verification = json.loads((output / "verification.json").read_text())
    assert verification["status"] in {"partial", "failed"}
    assert verification["outcome"] == "refused"
    assert not (output / "staged").exists()
    assert not (output / "host-wiring.diff").exists()
    assert not (output / "proposal.md").exists()


def test_prevent_regression_staged_refused_staged_lifecycle_and_copied_closure(
    tmp_path: Path,
) -> None:
    host, evidence, acceptance, proposal_dir, targets = _migrated_flow(tmp_path)
    review = _accepted_proposal(host, proposal_dir, targets)
    output = _generate_guard(
        host, evidence, acceptance, proposal_dir, review, output="reports/prevent-regression/reuse"
    )
    assert (output / "staged/tool/job_state_guard.dart").is_file()
    review_payload = json.loads(review.read_text())
    review_payload["status"] = "pending"
    review_payload.pop("acceptance_hash")
    review_payload["acceptance_hash"] = _canonical_hash(review_payload)
    _write_json(review, review_payload)
    _generate_guard(
        host,
        evidence,
        acceptance,
        proposal_dir,
        review,
        output="reports/prevent-regression/reuse",
        expected=2,
    )
    assert not (output / "staged").exists()
    review_payload["status"] = "accepted"
    review_payload.pop("acceptance_hash")
    review_payload["acceptance_hash"] = _canonical_hash(review_payload)
    _write_json(review, review_payload)
    restored = _generate_guard(
        host,
        evidence,
        acceptance,
        proposal_dir,
        review,
        output="reports/prevent-regression/reuse",
    )
    assert (restored / "staged/tool/job_state_guard.dart").is_file()

    closure = tmp_path / "installed/.agents/skills/on-demand"
    copied_generator = closure / "prevent-regression/scripts/generate_dart_state_guard.py"
    copied_verifier = closure / "prevent-regression/scripts/verify_dart_state_guard.py"
    copied_validator = closure / "_dart/dart_accepted_evidence.py"
    copied_generator.parent.mkdir(parents=True)
    copied_validator.parent.mkdir(parents=True)
    for source, destination in (
        (GENERATOR, copied_generator),
        (VERIFIER, copied_verifier),
        (VALIDATOR, copied_validator),
    ):
        shutil.copy2(source, destination)
    copied = _generate_guard(
        host,
        evidence,
        acceptance,
        proposal_dir,
        review,
        output="reports/prevent-regression/copied",
        script=copied_generator,
    )
    verification = _verify_guard(host, copied, script=copied_verifier)
    assert verification["status"] == "complete"
    text = GENERATOR.read_text() + VERIFIER.read_text() + VALIDATOR.read_text()
    assert "language-server" not in text
    assert "package:analyzer" not in text
