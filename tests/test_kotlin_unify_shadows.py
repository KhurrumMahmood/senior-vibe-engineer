"""Accepted Kotlin semantic-duplication proposal lifecycle."""

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
FIXTURE = ROOT / "tests/fixtures/kotlin-semantic-family/host"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_kotlin-semantic/kotlin_semantic_facts.py"
DETECTOR = SKILLS / "find-semantic-duplication/scripts/detect_kotlin_semantic.py"
HELPER = SKILLS / "_kotlin-semantic/kotlin_accepted_evidence.py"
PROPOSER = SKILLS / "unify-shadows/scripts/propose_kotlin.py"
KOTLINC = Path("/opt/homebrew/bin/kotlinc")
JAVA = Path("/usr/bin/java")
DUPLICATION_GATES = {
    "overload_ambiguity": "none",
    "reflection": "none",
    "callable_references": "none",
    "delegated_property": "none",
    "generated_kapt_ksp": "none",
    "gradle_variants": "none",
    "java_callers": "none",
    "external_callers": "none",
    "runtime_equivalence": "not_established_no_mutation_authority",
    "behavioral_equivalence": "not_established_no_mutation_authority",
    "jvm_abi": "separate_approval_required",
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


def _produce(host: Path) -> tuple[Path, Path]:
    facts = host / "reports/kotlin-semantic/facts.json"
    analysis = host / "reports/semantic-duplication/kotlin/analysis.json"
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
        facts,
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
    return facts, analysis


def _acceptance(host: Path, facts: Path, analysis: Path, decision: str) -> Path:
    fact_payload = _json(facts)
    analysis_payload = _json(analysis)
    payload = {
        "schema_version": "kotlin-duplication-acceptance-v1",
        "language": "kotlin",
        "status": "accepted",
        "producer": "find-semantic-duplication",
        "decision": decision,
        "artifact": analysis.relative_to(host).as_posix(),
        "artifact_sha256": _hash(analysis),
        "fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "candidate_sha256": analysis_payload["candidate_sha256"],
        "selection_id": analysis_payload["leads"][0]["id"],
        "boundary_verdicts": DUPLICATION_GATES,
        "reviewer": "fixture-reviewer",
        "notes": "Reviewed exact definitions, resolved callers, non-equivalence, and stop conditions.",
    }
    return _write(
        analysis.with_name("accepted-duplication.json"),
        _canonical(payload, "acceptance_sha256"),
    )


def _propose(
    host: Path,
    facts: Path,
    analysis: Path,
    acceptance: Path,
    script: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/unify-shadows/kotlin/KSD-01"
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


def test_kotlin_unify_shadows_copied_complete_keep_refuse_recover(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns("reports"))
    before = _tree(host)
    facts, analysis = _produce(host)
    acceptance = _acceptance(host, facts, analysis, "share_utilities")
    installed = tmp_path / "outside-checkout/.agents/skills"
    copied_helper = installed / "_kotlin-semantic/kotlin_accepted_evidence.py"
    copied_proposer = installed / "unify-shadows/scripts/propose_kotlin.py"
    copied_helper.parent.mkdir(parents=True)
    copied_proposer.parent.mkdir(parents=True)
    shutil.copy2(HELPER, copied_helper)
    shutil.copy2(PROPOSER, copied_proposer)

    output = _propose(host, facts, analysis, acceptance, copied_proposer)
    assert {path.name for path in output.iterdir()} == {
        "proposal.md",
        "evidence.json",
        "scope.json",
    }
    evidence = _json(output / "evidence.json")
    scope = _json(output / "scope.json")
    assert evidence["outcome"] == "proposal_ready"
    assert evidence["consolidation_shape"] == "share_utilities"
    assert evidence["source_inventory"] == _json(facts)["source_inventory"]
    assert evidence["native_checks"]["test"]["stdout"] == (
        "kotlin-semantic-native-test:ok\n"
    )
    assert evidence["native_checks"]["smoke"]["stdout"] == (
        "receipt:7:receipt:8:queued\n"
    )
    assert len(scope["members"]) == 2
    assert len({row["definition"]["signature"] for row in scope["members"]}) == 2
    callers = [
        {call["caller"]["fq_name"] for call in row["resolved_callers"]}
        for row in scope["members"]
    ]
    assert callers[0]
    assert callers[1]
    assert callers[0].isdisjoint(callers[1])
    assert _tree(host) == before

    _acceptance(host, facts, analysis, "keep_separate_document_why")
    _propose(host, facts, analysis, acceptance, copied_proposer)
    evidence = _json(output / "evidence.json")
    assert evidence["outcome"] == "keep_separate_documented"
    assert "No consolidation" in (output / "proposal.md").read_text(encoding="utf-8")

    accepted = _json(acceptance)
    for boundary in DUPLICATION_GATES:
        refused = dict(accepted)
        refused["boundary_verdicts"] = {
            **DUPLICATION_GATES,
            boundary: "unknown",
        }
        _write(acceptance, _canonical(refused, "acceptance_sha256"))
        _propose(host, facts, analysis, acceptance, copied_proposer, expected=2)
        assert _json(output / "evidence.json")["failure_kind"] == (
            "acceptance_invalid"
        )
        assert _json(output / "scope.json")["outcome"] == "refused"
    _write(acceptance, accepted)
    _propose(host, facts, analysis, acceptance, copied_proposer)
    assert _json(output / "evidence.json")["outcome"] == "keep_separate_documented"

    source = host / "src/main/kotlin/kotlinsemantic/Semantics.kt"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    _propose(host, facts, analysis, acceptance, copied_proposer, expected=2)
    assert _json(output / "evidence.json")["failure_kind"] == "evidence_stale"
    source.write_text(original, encoding="utf-8")
    _propose(host, facts, analysis, acceptance, copied_proposer)
    assert _json(output / "evidence.json")["outcome"] == "keep_separate_documented"
    assert _tree(host) == before
