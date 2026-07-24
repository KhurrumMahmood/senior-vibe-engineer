"""Accepted C# enum, exact-type guard, and semantic-shadow dispositions."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
DOTNET = Path(shutil.which("dotnet") or "")
BASE = ROOT / "tests/fixtures/csharp-semantic-family/host"
MIGRATED = ROOT / "tests/fixtures/csharp-state-guard/migrated"
REVERTED = ROOT / "tests/fixtures/csharp-state-guard/reverted"
SKILLS = ROOT / ".claude/skills"
COMMON = SKILLS / "_csharp-semantic"
PROVIDER = COMMON / "csharp_semantic_facts.py"
STATE = SKILLS / "find-implicit-state/scripts/detect_csharp_state.py"
DUPLICATION = SKILLS / "find-semantic-duplication/scripts/detect_csharp_semantic.py"
EXTRACT = SKILLS / "extract-enum/scripts/collect_csharp_state.py"
GUARD = SKILLS / "prevent-regression/scripts/stage_csharp_state_guard.py"
UNIFY = SKILLS / "unify-shadows/scripts/propose_csharp.py"

STATE_GATES = {
    "closed_domain": "accepted",
    "serialization_wire_values": "accepted_exact_strings",
    "external_callers": "none",
    "framework_registration": "none",
    "reflection_runtime_names": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "partial_declarations": "none_selected",
    "override_interface_dispatch": "none_selected",
    "delegates_dynamic_dispatch": "none_selected",
    "conditional_build_variants": "none",
    "binary_compatibility": "accepted_change_for_proposal_only",
}

DUPLICATION_GATES = {
    "resolved_callers": "accepted_exact",
    "behavioral_equivalence": "not_established_no_mutation_authority",
    "runtime_equivalence": "not_established_no_mutation_authority",
    "overload_ambiguity": "none_selected",
    "override_interface_dispatch": "none_selected",
    "delegates_dynamic_reflection": "none_selected",
    "partial_declarations": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "binary_compatibility": "separate_approval_required",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or not DOTNET.is_file(),
    reason="product Python and the pinned .NET SDK are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 240,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(payload: dict[str, Any], field: str) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    rendered = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload[field] = hashlib.sha256(rendered.encode()).hexdigest()
    return payload


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "reports" not in path.relative_to(root).parts
        and "__pycache__" not in path.relative_to(root).parts
    }


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(BASE, host, ignore=shutil.ignore_patterns("reports"))
    return host


def _install(tmp_path: Path) -> dict[str, Path]:
    installed = tmp_path / "outside-checkout/.agents/skills"
    shutil.copytree(COMMON, installed / "_csharp-semantic")
    sources = {
        "state": STATE,
        "duplication": DUPLICATION,
        "extract": EXTRACT,
        "guard": GUARD,
        "unify": UNIFY,
    }
    copied: dict[str, Path] = {
        "provider": installed / "_csharp-semantic/csharp_semantic_facts.py"
    }
    for name, source in sources.items():
        destination = installed / source.parents[1].name / "scripts" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied[name] = destination
    return copied


def _produce(
    host: Path,
    scripts: dict[str, Path],
    *,
    state: bool = True,
    duplication: bool = True,
) -> tuple[Path, Path, Path]:
    facts = host / "reports/csharp-semantic/facts.json"
    findings = host / "reports/find-implicit-state/csharp/findings.json"
    analysis = host / "reports/semantic-duplication/csharp/analysis.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        scripts["provider"],
        "--project-root",
        host,
        "--manifest",
        "csharp-semantic-project.json",
        "--output",
        facts,
        "--dotnet",
        DOTNET,
        cwd=host,
    )
    if state:
        _run(
            PYTHON,
            "-I",
            "-S",
            scripts["state"],
            "--project-root",
            host,
            "--facts",
            facts,
            cwd=host,
        )
    if duplication:
        _run(
            PYTHON,
            "-I",
            "-S",
            scripts["duplication"],
            "--project-root",
            host,
            "--facts",
            facts,
            cwd=host,
        )
    return facts, findings, analysis


def _state_acceptance(host: Path, facts: Path, findings: Path) -> Path:
    fact_payload, finding_payload = _json(facts), _json(findings)
    payload = {
        "schema_version": "csharp-state-acceptance-v1",
        "language": "csharp",
        "status": "accepted",
        "producer": "find-implicit-state",
        "decision": "accept-enum",
        "artifact": findings.relative_to(host).as_posix(),
        "artifact_sha256": _hash(findings),
        "fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "candidate_sha256": finding_payload["candidate_sha256"],
        "selection_symbol_id": "P:CSharpSemantic.Job.Status",
        "enum": {
            "namespace": "CSharpSemantic",
            "type_name": "JobStatus",
            "members": [
                {"name": "Done", "wire_value": "done"},
                {"name": "Queued", "wire_value": "queued"},
                {"name": "Running", "wire_value": "running"},
            ],
        },
        "boundary_verdicts": STATE_GATES,
        "reviewer": "fixture-state-reviewer",
        "notes": "Reviewed exact property, closed domain, wire strings, and all C# boundaries.",
    }
    return _write(
        findings.with_name("accepted-state.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _duplication_acceptance(
    host: Path, facts: Path, analysis: Path, decision: str
) -> Path:
    fact_payload, analysis_payload = _json(facts), _json(analysis)
    payload = {
        "schema_version": "csharp-duplication-acceptance-v1",
        "language": "csharp",
        "status": "accepted",
        "producer": "find-semantic-duplication",
        "decision": decision,
        "artifact": analysis.relative_to(host).as_posix(),
        "artifact_sha256": _hash(analysis),
        "fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "candidate_sha256": analysis_payload["candidate_sha256"],
        "selection_id": "CSD-01",
        "boundary_verdicts": DUPLICATION_GATES,
        "reviewer": "fixture-duplication-reviewer",
        "notes": "Reviewed exact pair, resolved callers, non-equivalence, and boundary disposition.",
    }
    return _write(
        analysis.with_name("accepted-duplication.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _extract(
    host: Path,
    facts: Path,
    findings: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/extract-enum/csharp/job-status"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--facts",
        facts,
        "--findings",
        findings,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        cwd=host,
        expected=expected,
    )
    return output


def _unify(
    host: Path,
    facts: Path,
    analysis: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/unify-shadows/csharp/CSD-01"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--facts",
        facts,
        "--analysis",
        analysis,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        cwd=host,
        expected=expected,
    )
    return output


def _apply_migration(host: Path) -> list[dict[str, str]]:
    edits = []
    for migrated in sorted(MIGRATED.rglob("*.cs")):
        relative = migrated.relative_to(MIGRATED)
        reverted = REVERTED / relative
        destination = host / relative
        destination.write_text(migrated.read_text(encoding="utf-8"), encoding="utf-8")
        edits.append(
            {
                "path": relative.as_posix(),
                "migrated": migrated.read_text(encoding="utf-8"),
                "reverted": reverted.read_text(encoding="utf-8"),
            }
        )
    return edits


def _migration_acceptance(
    host: Path,
    facts: Path,
    targets: Path,
    edits: list[dict[str, str]],
) -> Path:
    fact_payload, proposal = _json(facts), _json(targets)
    payload = {
        "schema_version": "csharp-enum-migration-acceptance-v1",
        "language": "csharp",
        "status": "accepted",
        "decision": "approve-exact-property-type-guard",
        "targets": targets.relative_to(host).as_posix(),
        "targets_sha256": _hash(targets),
        "migrated_facts": facts.relative_to(host).as_posix(),
        "migrated_facts_sha256": _hash(facts),
        "migrated_fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "migrated_source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "migrated_source_inventory": fact_payload["source_inventory"],
        "authority": proposal["target"]["authority"],
        "enum": proposal["proposed_enum"],
        "migrated_signature": "CSharpSemantic.JobStatus CSharpSemantic.Job.Status",
        "boundary_verdicts": STATE_GATES,
        "reversion_edits": edits,
        "reviewer": "fixture-migration-reviewer",
        "notes": "Accepted exact migrated tree, complete buildable String reversion, and staged type guard.",
    }
    return _write(
        targets.with_name("accepted-migration.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _stage_guard(
    host: Path,
    facts: Path,
    targets: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/prevent-regression/csharp/job-status"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--facts",
        facts,
        "--targets",
        targets,
        "--accepted-migration",
        acceptance,
        "--output-dir",
        output,
        cwd=host,
        expected=expected,
    )
    return output


def test_csharp_accepted_outcomes_copied_refuse_recover_and_preserve_sources(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    copied = _install(tmp_path)
    original = _snapshot(host)
    facts, findings, analysis = _produce(host, copied)
    state_acceptance = _state_acceptance(host, facts, findings)
    duplication_acceptance = _duplication_acceptance(
        host, facts, analysis, "share_utilities"
    )

    extract = _extract(host, facts, findings, state_acceptance, copied["extract"])
    targets_path = extract / "targets.json"
    targets = _json(targets_path)
    assert set(path.name for path in extract.iterdir()) == {"targets.json", "proposal.md"}
    assert targets["outcome"] == "proposal_ready"
    assert targets["source_mutations"] == 0
    assert targets["target"]["authority"]["symbol_id"] == "P:CSharpSemantic.Job.Status"
    assert [row["wire_value"] for row in targets["proposed_enum"]["members"]] == [
        "done",
        "queued",
        "running",
    ]
    assert targets["target"]["resolved_write_callers"]
    assert targets["native_checks"]["test"]["stdout"] == "csharp-semantic-native-test:ok\n"
    assert targets["native_checks"]["smoke"]["stdout"] == "receipt:7:receipt:8:queued\n"
    unsigned_targets = dict(targets)
    claimed = unsigned_targets.pop("artifact_sha256")
    assert claimed == hashlib.sha256(
        json.dumps(unsigned_targets, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    unify = _unify(
        host, facts, analysis, duplication_acceptance, copied["unify"]
    )
    assert set(path.name for path in unify.iterdir()) == {
        "proposal.md",
        "evidence.json",
        "scope.json",
    }
    evidence, scope = _json(unify / "evidence.json"), _json(unify / "scope.json")
    assert evidence["outcome"] == "proposal_ready"
    assert evidence["consolidation_shape"] == "share_utilities"
    assert len(scope["members"]) == 2
    assert {
        row["definition"]["symbol_id"] for row in scope["members"]
    } == {
        "M:CSharpSemantic.SemanticCases.SummarizeAlpha(System.Int32)",
        "M:CSharpSemantic.SemanticCases.SummarizeBeta(System.Int32)",
    }
    caller_sets = [
        {call["caller"]["symbol_id"] for call in row["resolved_callers"]}
        for row in scope["members"]
    ]
    assert caller_sets[0] and caller_sets[1] and caller_sets[0].isdisjoint(caller_sets[1])
    assert _snapshot(host) == original

    accepted_state = _json(state_acceptance)
    invalid_state = dict(accepted_state)
    invalid_state["boundary_verdicts"] = {
        **STATE_GATES,
        "reflection_runtime_names": "unknown",
    }
    _write(state_acceptance, _canonical(invalid_state, "acceptance_sha256"))
    _extract(host, facts, findings, state_acceptance, copied["extract"], expected=2)
    assert _json(targets_path)["failure_kind"] == "acceptance_invalid"
    _write(state_acceptance, accepted_state)
    _extract(host, facts, findings, state_acceptance, copied["extract"])
    assert _json(targets_path)["outcome"] == "proposal_ready"

    manifest = host / "csharp-semantic-project.json"
    manifest_text = manifest.read_text(encoding="utf-8")
    manifest.write_text(manifest_text + "\n", encoding="utf-8")
    _extract(host, facts, findings, state_acceptance, copied["extract"], expected=2)
    assert _json(targets_path)["failure_kind"] == "project_contract_stale"
    manifest.write_text(manifest_text, encoding="utf-8")
    helper = copied["provider"].with_name("CSharpSemanticFacts.cs")
    helper_text = helper.read_text(encoding="utf-8")
    helper.write_text(helper_text + "\n", encoding="utf-8")
    _extract(host, facts, findings, state_acceptance, copied["extract"], expected=2)
    assert _json(targets_path)["failure_kind"] == "semantic_authority_stale"
    helper.write_text(helper_text, encoding="utf-8")
    _extract(host, facts, findings, state_acceptance, copied["extract"])

    _duplication_acceptance(host, facts, analysis, "keep_separate_document_why")
    _unify(host, facts, analysis, duplication_acceptance, copied["unify"])
    assert _json(unify / "evidence.json")["outcome"] == "keep_separate_documented"
    accepted_duplication = _json(duplication_acceptance)
    invalid_duplication = dict(accepted_duplication)
    invalid_duplication["boundary_verdicts"] = {
        **DUPLICATION_GATES,
        "runtime_equivalence": "unknown",
    }
    _write(
        duplication_acceptance,
        _canonical(invalid_duplication, "acceptance_sha256"),
    )
    _unify(
        host,
        facts,
        analysis,
        duplication_acceptance,
        copied["unify"],
        expected=2,
    )
    assert _json(unify / "evidence.json")["failure_kind"] == "acceptance_invalid"
    assert _json(unify / "scope.json")["outcome"] == "refused"
    _write(duplication_acceptance, accepted_duplication)
    _unify(host, facts, analysis, duplication_acceptance, copied["unify"])
    assert _json(unify / "evidence.json")["outcome"] == "keep_separate_documented"
    assert _snapshot(host) == original

    edits = _apply_migration(host)
    migrated_facts, _unused_findings, _unused_analysis = _produce(
        host, copied, state=False, duplication=False
    )
    migrated = _json(migrated_facts)
    property_rows = [
        row
        for row in migrated["declarations"]
        if row.get("symbol_id") == "P:CSharpSemantic.Job.Status"
    ]
    assert [(row["type"], row["signature"]) for row in property_rows] == [
        (
            "CSharpSemantic.JobStatus",
            "CSharpSemantic.JobStatus CSharpSemantic.Job.Status",
        )
    ]
    migrated_snapshot = _snapshot(host)
    migration_acceptance = _migration_acceptance(
        host, migrated_facts, targets_path, edits
    )
    guard = _stage_guard(
        host,
        migrated_facts,
        targets_path,
        migration_acceptance,
        copied["guard"],
    )
    assert set(path.name for path in guard.iterdir()) == {
        "ExactAcceptedStateGuard.cs",
        "evidence.json",
        "proposal.md",
    }
    guard_evidence = _json(guard / "evidence.json")
    assert guard_evidence["outcome"] == "guard_staged"
    assert guard_evidence["installed"] is False
    assert guard_evidence["verification"]["migrated_native"]["passed"] is True
    assert guard_evidence["verification"]["migrated_guard"]["returncode"] == 0
    assert guard_evidence["verification"]["reverted_native_without_guard"]["passed"] is True
    assert guard_evidence["verification"]["reverted_guard"]["returncode"] != 0
    reverted_diagnostics = (
        guard_evidence["verification"]["reverted_guard"]["stdout"]
        + guard_evidence["verification"]["reverted_guard"]["stderr"]
    )
    assert "CS1503" in reverted_diagnostics
    assert "cannot convert from 'string' to 'CSharpSemantic.JobStatus'" in reverted_diagnostics
    assert guard_evidence["verification"]["buildable_string_reversion"] is True
    assert guard_evidence["verification"]["regression_rejected"] is True
    assert _snapshot(host) == migrated_snapshot

    accepted_migration = _json(migration_acceptance)
    invalid_migration = dict(accepted_migration)
    invalid_migration["targets_sha256"] = "0" * 64
    _write(
        migration_acceptance,
        _canonical(invalid_migration, "acceptance_sha256"),
    )
    _stage_guard(
        host,
        migrated_facts,
        targets_path,
        migration_acceptance,
        copied["guard"],
        expected=2,
    )
    assert _json(guard / "evidence.json")["failure_kind"] == "migration_acceptance_invalid"
    assert not (guard / "ExactAcceptedStateGuard.cs").exists()
    _write(migration_acceptance, accepted_migration)
    _stage_guard(
        host,
        migrated_facts,
        targets_path,
        migration_acceptance,
        copied["guard"],
    )
    assert _json(guard / "evidence.json")["outcome"] == "guard_staged"
    assert _snapshot(host) == migrated_snapshot
