"""Accepted-evidence-only C shadow-unification proposal outcomes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen cohort runtime
)
PROPOSER = ROOT / ".claude/skills/unify-shadows/scripts/propose_c.py"
CLANG = shutil.which("clang")
MAKE = shutil.which("make")
SHAPES = {
    "keep_separate_document_why",
    "share_utilities",
    "complete_migration",
    "merge_at_workflow",
}

_SEMANTIC_SPEC = importlib.util.spec_from_file_location(
    "c_semantic_family", ROOT / "tests/test_c_semantic_family.py"
)
assert _SEMANTIC_SPEC and _SEMANTIC_SPEC.loader
SEMANTIC = importlib.util.module_from_spec(_SEMANTIC_SPEC)
_SEMANTIC_SPEC.loader.exec_module(SEMANTIC)

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or CLANG is None or MAKE is None,
    reason="product Python, Clang 21, and Make are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot(host: Path) -> dict[str, str]:
    return {
        path: digest
        for path, digest in SEMANTIC._snapshot(host).items()
        if not path.startswith("reviews/")
    }


def _write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _citation_contract(analysis: dict, facts: dict) -> tuple[list[dict], list[dict]]:
    lead = analysis["leads"][0]
    hashes = {row["path"]: row["sha256"] for row in facts["source_files"]}
    source_citations = [
        {
            "function": member["name"],
            "path": member["file"],
            "line": member["line"],
            "sha256": hashes[member["file"]],
        }
        for member in lead["functions"]
    ]
    caller_citations = []
    for member in lead["functions"]:
        for caller in member["direct_callers"]:
            matches = [
                row
                for row in facts["direct_references"]
                if row["context"] == "direct_call"
                and row["name"] == member["name"]
                and row["function"] == caller
            ]
            caller_citations.extend(
                {
                    "callee": member["name"],
                    "caller": caller,
                    "path": row["file"],
                    "line": row["line"],
                    "sha256": hashes[row["file"]],
                }
                for row in matches
            )
    return source_citations, caller_citations


def _acceptance(host: Path, shape: str, *, status: str = "accepted") -> Path:
    analysis_path = host / "reports/semantic-duplication/c/analysis.json"
    facts_path = host / "reports/c-semantic/facts.json"
    analysis = _json(analysis_path)
    facts = _json(facts_path)
    source_citations, caller_citations = _citation_contract(analysis, facts)
    payload = {
        "schema_version": "c-unify-shadows-acceptance-v1",
        "language": "c",
        "producer": "find-semantic-duplication",
        "consumer": "unify-shadows",
        "status": status,
        "analysis_sha256": _sha(analysis_path),
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "finding_id": "C-SD-0001",
        "finding_sha256": _canonical_hash(analysis["leads"][0]),
        "decision": shape,
        "rationale": "Human selected this proposal shape after reviewing the exact C source and direct callers.",
        "source_citations": source_citations,
        "caller_citations": caller_citations,
        "accepted_limits": analysis["limits"],
        "native": {
            "compile_database": f"make clean compile-db CC={CLANG}",
            "test": f"make test CC={CLANG}",
            "smoke": ".native-build/c-semantic-smoke",
            "smoke_stdout": "semantic:running:us:112:1:legacy_status",
        },
    }
    payload["acceptance_sha256"] = _canonical_hash(payload)
    return _write_json(host / "reviews/C-SD-0001.json", payload)


def _prepared(tmp_path: Path) -> tuple[Path, Path]:
    host = SEMANTIC._host(tmp_path)
    SEMANTIC._native(host)
    collected = SEMANTIC._collect(host)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    detected = SEMANTIC._consume(host, "duplicate")
    assert detected.returncode == 0, detected.stdout + detected.stderr
    return host, _acceptance(host, "keep_separate_document_why")


def _invoke(
    host: Path,
    acceptance: Path,
    output_name: str,
    *,
    proposer: Path = PROPOSER,
    analysis: str = "reports/semantic-duplication/c/analysis.json",
    facts: str = "reports/c-semantic/facts.json",
) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON,
        "-I",
        "-S",
        proposer,
        "--project-root",
        host,
        "--analysis",
        analysis,
        "--facts",
        facts,
        "--acceptance",
        acceptance,
        "--output-dir",
        f"reports/unify-shadows/c/{output_name}",
        cwd=host,
    )


def test_all_human_selected_shapes_emit_cited_read_only_three_artifact_outcomes(
    tmp_path: Path,
) -> None:
    host, _ = _prepared(tmp_path)
    before = _source_snapshot(host)
    for shape in sorted(SHAPES):
        acceptance = _acceptance(host, shape)
        result = _invoke(host, acceptance, shape)
        assert result.returncode == 0, result.stdout + result.stderr
        output = host / f"reports/unify-shadows/c/{shape}"
        assert sorted(path.name for path in output.iterdir()) == [
            "evidence.json",
            "proposal.md",
            "scope.json",
        ]
        evidence = _json(output / "evidence.json")
        scope = _json(output / "scope.json")
        proposal = (output / "proposal.md").read_text(encoding="utf-8")
        assert evidence["status"] == "complete"
        assert evidence["shape"] == shape
        assert evidence["behavioral_equivalence_claimed"] is False
        assert scope["mutation_authorized"] is False
        assert {row["citation"] for row in scope["members"]} == {
            "src/semantic.c:59",
            "src/semantic.c:64",
        }
        assert {row["citation"] for row in scope["direct_callers"]} == {
            "src/main.c:10",
            "src/main.c:11",
            "src/semantic.c:72",
            "src/semantic.c:78",
        }
        assert all(len(row["sha256"]) == 64 for row in scope["members"])
        assert all(len(row["sha256"]) == 64 for row in scope["direct_callers"])
        assert scope["native_test_matrix"] == _json(acceptance)["native"]
        for term in (
            "ABI",
            "external consumers",
            "side effects",
            "undefined behavior",
            "Human approval",
        ):
            assert term in proposal
    keep = (
        host
        / "reports/unify-shadows/c/keep_separate_document_why/proposal.md"
    ).read_text(encoding="utf-8")
    assert "No shared implementation or caller move is proposed" in keep
    assert "migration sequence" not in keep.lower()
    assert _source_snapshot(host) == before
    SEMANTIC._native(host)


def test_stale_tampered_and_missing_human_authority_replace_ready_output_with_refusal(
    tmp_path: Path,
) -> None:
    host, acceptance = _prepared(tmp_path)
    output = host / "reports/unify-shadows/c/reused"
    assert _invoke(host, acceptance, "reused").returncode == 0
    (output / "stale-ready.txt").write_text("old\n", encoding="utf-8")

    pending = _json(acceptance)
    pending["status"] = "pending"
    pending.pop("acceptance_sha256")
    pending["acceptance_sha256"] = _canonical_hash(pending)
    pending_path = _write_json(host / "reviews/pending.json", pending)
    refused = _invoke(host, pending_path, "reused")
    assert refused.returncode == 2
    assert _json(output / "evidence.json")["failure_kind"] == (
        "human_acceptance_required"
    )
    assert not (output / "stale-ready.txt").exists()
    assert sorted(path.name for path in output.iterdir()) == [
        "evidence.json",
        "proposal.md",
        "scope.json",
    ]

    analysis_path = host / "reports/semantic-duplication/c/analysis.json"
    analysis_bytes = analysis_path.read_bytes()
    analysis_payload = _json(analysis_path)
    analysis_payload["summary"]["static_review_leads"] = 99
    _write_json(analysis_path, analysis_payload)
    artifact_tamper = _invoke(host, acceptance, "reused")
    assert artifact_tamper.returncode == 2
    assert _json(output / "evidence.json")["failure_kind"] == (
        "invalid_accepted_evidence"
    )
    analysis_path.write_bytes(analysis_bytes)

    acceptance_payload = _json(acceptance)
    acceptance_payload["analysis_sha256"] = "0" * 64
    acceptance_payload.pop("acceptance_sha256")
    acceptance_payload["acceptance_sha256"] = _canonical_hash(acceptance_payload)
    tampered_path = _write_json(host / "reviews/tampered.json", acceptance_payload)
    tampered = _invoke(host, tampered_path, "reused")
    assert tampered.returncode == 2
    assert _json(output / "evidence.json")["failure_kind"] == (
        "invalid_accepted_evidence"
    )

    source = host / "src/semantic.c"
    original = source.read_bytes()
    source.write_bytes(original + b"\n")
    stale = _invoke(host, acceptance, "reused")
    assert stale.returncode == 2
    assert _json(output / "evidence.json")["failure_kind"] == (
        "stale_accepted_evidence"
    )
    source.write_bytes(original)

    missing = _invoke(host, host / "reviews/missing.json", "reused")
    assert missing.returncode == 2
    assert _json(output / "evidence.json")["failure_kind"] == (
        "evidence_unavailable"
    )


def test_exact_copied_standalone_consumer_preserves_source_and_native_smoke(
    tmp_path: Path,
) -> None:
    host, acceptance = _prepared(tmp_path)
    before = _source_snapshot(host)
    copied = tmp_path / "library/.agents/skills/unify-shadows/scripts/propose_c.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(PROPOSER, copied)
    result = _invoke(host, acceptance, "copied", proposer=copied)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _json(host / "reports/unify-shadows/c/copied/evidence.json")["status"] == (
        "complete"
    )
    assert str(ROOT) not in copied.read_text(encoding="utf-8")
    assert "c_semantic_facts" not in copied.read_text(encoding="utf-8")
    assert "subprocess" not in copied.read_text(encoding="utf-8")
    assert _source_snapshot(host) == before
    SEMANTIC._native(host)
