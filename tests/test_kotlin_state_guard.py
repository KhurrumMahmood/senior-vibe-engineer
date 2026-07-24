"""Accepted Kotlin String-state proposal and staged exact-type guard."""

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
BASE = ROOT / "tests/fixtures/kotlin-semantic-family/host"
OVERLAY = ROOT / "tests/fixtures/kotlin-state-guard/migrated"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_kotlin-semantic/kotlin_semantic_facts.py"
DETECTOR = SKILLS / "find-implicit-state/scripts/detect_kotlin_state.py"
HELPER = SKILLS / "_kotlin-semantic/kotlin_accepted_evidence.py"
EXTRACT = SKILLS / "extract-enum/scripts/collect_kotlin_state.py"
GUARD = SKILLS / "prevent-regression/scripts/stage_kotlin_state_guard.py"
KOTLINC = Path("/opt/homebrew/bin/kotlinc")
JAVA = Path("/usr/bin/java")
STATE_GATES = {
    "closed_domain": "accepted",
    "serialization": "accepted_wire_values",
    "java_callers": "none",
    "framework_registration": "none",
    "external_callers": "none",
    "jvm_abi": "accepted_change",
    "reflection": "none",
    "delegated_property": "none",
    "generated_kapt_ksp": "none",
    "gradle_variants": "none",
    "overload_ambiguity": "none",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or not KOTLINC.is_file() or not JAVA.is_file(),
    reason="product Python and pinned Kotlin/JVM toolchain are required",
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


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "reports" not in path.parts and ".native-build" not in path.parts
    }


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(BASE, host, ignore=shutil.ignore_patterns("reports"))
    return host


def _produce(host: Path) -> tuple[Path, Path]:
    facts = host / "reports/kotlin-semantic/facts.json"
    findings = host / "reports/find-implicit-state/kotlin/findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        PROVIDER,
        "--project-root",
        host,
        "--manifest",
        "kotlin-semantic-project.json",
        "--output",
        "reports/kotlin-semantic/facts.json",
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        cwd=host,
    )
    _run(
        PYTHON,
        "-I",
        "-S",
        DETECTOR,
        "--project-root",
        host,
        "--facts",
        facts,
        cwd=host,
    )
    return facts, findings


def _state_acceptance(host: Path, facts: Path, findings: Path) -> Path:
    fact_payload = _json(facts)
    finding_payload = _json(findings)
    candidate = finding_payload["candidates"][0]
    payload = {
        "schema_version": "kotlin-state-acceptance-v1",
        "language": "kotlin",
        "status": "accepted",
        "producer": "find-implicit-state",
        "decision": "accept-enum",
        "artifact": findings.relative_to(host).as_posix(),
        "artifact_sha256": _hash(findings),
        "fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "candidate_sha256": finding_payload["candidate_sha256"],
        "selection_fq_name": candidate["fq_name"],
        "boundary_verdicts": STATE_GATES,
        "reviewer": "fixture-reviewer",
        "notes": "Reviewed exact direct property, state domain, callers, wire values, and JVM boundary.",
    }
    return _write(
        findings.with_name("accepted-state.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _install(tmp_path: Path) -> tuple[Path, Path]:
    installed = tmp_path / "outside-checkout/.agents/skills"
    helper = installed / "_kotlin-semantic/kotlin_accepted_evidence.py"
    helper.parent.mkdir(parents=True)
    shutil.copy2(HELPER, helper)
    scripts = []
    for skill, source in (("extract-enum", EXTRACT), ("prevent-regression", GUARD)):
        destination = installed / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        scripts.append(destination)
    return scripts[0], scripts[1]


def _extract(
    host: Path,
    facts: Path,
    findings: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/extract-enum/kotlin/job-phase"
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


def _apply_overlay(host: Path) -> list[dict[str, str]]:
    edits = []
    for source in sorted(OVERLAY.rglob("*.kt")):
        relative = source.relative_to(OVERLAY)
        destination = host / relative
        original = destination.read_text(encoding="utf-8")
        migrated = source.read_text(encoding="utf-8")
        destination.write_text(migrated, encoding="utf-8")
        edits.append(
            {"path": relative.as_posix(), "migrated": migrated, "reverted": original}
        )
    return edits


def _inventory(host: Path) -> list[dict[str, str]]:
    manifest = _json(host / "kotlin-semantic-project.json")
    return [
        {"path": relative, "role": role, "sha256": _hash(host / relative)}
        for role, values in (("source", manifest["sources"]), ("test", manifest["tests"]))
        for relative in values
    ]


def _migration_acceptance(host: Path, targets: Path, edits: list[dict[str, str]]) -> Path:
    proposal = _json(targets)
    payload = {
        "schema_version": "kotlin-enum-migration-acceptance-v1",
        "language": "kotlin",
        "status": "accepted",
        "decision": "approve-exact-type-guard",
        "targets_sha256": _hash(targets),
        "authority": proposal["target"]["authority"],
        "enum": proposal["proposed_enum"],
        "boundary_verdicts": STATE_GATES,
        "migrated_source_inventory": _inventory(host),
        "reversion_edits": edits,
        "reviewer": "fixture-migration-reviewer",
        "notes": "Accepted exact enum migration, complete buildable String reversion, and exact type guard.",
    }
    return _write(
        targets.with_name("accepted-migration.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _stage_guard(
    host: Path,
    targets: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/prevent-regression/kotlin/job-phase"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--targets",
        targets,
        "--accepted-migration",
        acceptance,
        "--output-dir",
        output,
        "--kotlinc",
        KOTLINC,
        "--java",
        JAVA,
        cwd=host,
        expected=expected,
    )
    return output


def test_accepted_kotlin_enum_proposal_guard_and_copied_lifecycle(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _tree(host)
    facts, findings = _produce(host)
    acceptance = _state_acceptance(host, facts, findings)
    copied_extract, copied_guard = _install(tmp_path)

    extract = _extract(host, facts, findings, acceptance, copied_extract)
    targets = extract / "targets.json"
    proposal = _json(targets)
    assert proposal["outcome"] == "proposal_ready"
    assert proposal["source_mutations"] == 0
    assert proposal["target"]["authority"]["fq_name"] == "kotlinsemantic.Job.phase"
    assert [row["wire_value"] for row in proposal["proposed_enum"]["variants"]] == [
        "done",
        "queued",
        "running",
    ]
    assert proposal["target"]["writes"]
    assert proposal["target"]["references"]
    assert proposal["target"]["caller_contexts"]
    assert proposal["native_checks"]["test"]["stdout"] == (
        "kotlin-semantic-native-test:ok\n"
    )
    assert proposal["native_checks"]["smoke"]["stdout"] == (
        "receipt:7:receipt:8:queued\n"
    )
    assert _tree(host) == before

    accepted_payload = _json(acceptance)
    rejected_payload = dict(accepted_payload)
    rejected_payload["boundary_verdicts"] = {
        **STATE_GATES,
        "java_callers": "unknown",
    }
    _write(acceptance, _canonical(rejected_payload, "acceptance_sha256"))
    _extract(host, facts, findings, acceptance, copied_extract, expected=2)
    assert _json(targets)["failure_kind"] == "acceptance_invalid"
    _write(acceptance, accepted_payload)
    _extract(host, facts, findings, acceptance, copied_extract)
    assert _json(targets)["outcome"] == "proposal_ready"

    source = host / "src/main/kotlin/kotlinsemantic/Semantics.kt"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    _extract(host, facts, findings, acceptance, copied_extract, expected=2)
    assert _json(targets)["failure_kind"] == "evidence_stale"
    source.write_text(original, encoding="utf-8")
    _extract(host, facts, findings, acceptance, copied_extract)

    edits = _apply_overlay(host)
    migrated_before = _tree(host)
    migration = _migration_acceptance(host, targets, edits)
    guard = _stage_guard(host, targets, migration, copied_guard)
    guard_evidence = _json(guard / "evidence.json")
    assert guard_evidence["outcome"] == "guard_staged"
    assert guard_evidence["installed"] is False
    assert guard_evidence["verification"]["migrated_native"]["passed"] is True
    assert guard_evidence["verification"]["migrated_guard"]["returncode"] == 0
    assert guard_evidence["verification"]["reverted_native_without_guard"]["passed"] is True
    assert guard_evidence["verification"]["reverted_guard"]["returncode"] != 0
    assert _tree(host) == migrated_before

    migration_payload = _json(migration)
    invalid_migration = dict(migration_payload)
    invalid_migration["targets_sha256"] = "0" * 64
    _write(migration, _canonical(invalid_migration, "acceptance_sha256"))
    _stage_guard(host, targets, migration, copied_guard, expected=2)
    assert _json(guard / "evidence.json")["failure_kind"] == (
        "migration_acceptance_invalid"
    )
    assert not (guard / "ExactStateGuard.kt").exists()
    _write(migration, migration_payload)
    _stage_guard(host, targets, migration, copied_guard)
    assert _json(guard / "evidence.json")["outcome"] == "guard_staged"
    assert _tree(host) == migrated_before


def test_kotlin_state_proposal_refuses_unresolved_boundaries(tmp_path: Path) -> None:
    host = _host(tmp_path)
    facts, findings = _produce(host)
    acceptance = _state_acceptance(host, facts, findings)
    accepted = _json(acceptance)
    for boundary in (
        "reflection",
        "delegated_property",
        "generated_kapt_ksp",
        "gradle_variants",
    ):
        payload = dict(accepted)
        payload["boundary_verdicts"] = {**STATE_GATES, boundary: "unknown"}
        _write(acceptance, _canonical(payload, "acceptance_sha256"))
        output = _extract(host, facts, findings, acceptance, EXTRACT, expected=2)
        assert _json(output / "targets.json")["failure_kind"] == "acceptance_invalid"
