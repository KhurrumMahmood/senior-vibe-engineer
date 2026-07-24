"""Truth sentinels for the bounded 22/22 C# publication."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".claude/tasks/csharp-language-coverage.json"
STRUCTURE = {"propose-boundary", "propose-folder-reorganization"}
LEXICAL = {
    "adapt-project",
    "audit-decisions",
    "explain-code",
    "find-complexity-hotspots",
    "find-concept-divergence",
    "find-duplication",
    "find-folder-topology-drift",
    "find-omnibus",
    "find-standard-gaps",
}
SEMANTIC = {
    "find-dormant",
    "find-implicit-state",
    "find-incomplete-sweep",
    "find-semantic-duplication",
    "rename-concept",
}
ENTRYPOINTS = {
    "adapt-project": "scripts/discover_csharp.py",
    "audit-decisions": "scripts/audit_csharp.py",
    "explain-code": "scripts/explain_csharp.py",
    "extract-enum": "scripts/collect_csharp_state.py",
    "find-comment-drift": "scripts/analyze_comments_csharp.py",
    "find-complexity-hotspots": "scripts/run_csharp.py",
    "find-concept-divergence": "scripts/scan_csharp.py",
    "find-dormant": "scripts/detect_csharp_dormant.py",
    "find-duplication": "scripts/run_csharp.py",
    "find-folder-topology-drift": "scripts/detect_csharp.py",
    "find-implicit-state": "scripts/detect_csharp_state.py",
    "find-incomplete-sweep": "scripts/detect_csharp_incomplete_sweep.py",
    "find-omnibus": "scripts/run_csharp.py",
    "find-semantic-duplication": "scripts/detect_csharp_semantic.py",
    "find-standard-gaps": "scripts/scan_coverage_csharp.py",
    "map-subsystem": "scripts/map_csharp.py",
    "move-path": "scripts/csharp_source_move.py",
    "prevent-regression": "scripts/stage_csharp_state_guard.py",
    "propose-boundary": "scripts/propose_csharp.py",
    "propose-folder-reorganization": "scripts/propose_csharp.py",
    "rename-concept": "scripts/assess_csharp_rename.py",
    "unify-shadows": "scripts/propose_csharp.py",
}


def _payload() -> dict:
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _skill(skill: str) -> tuple[dict, str]:
    text = (ROOT / ".claude/skills" / skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    _, raw, body = text.split("---", 2)
    return yaml.safe_load(raw), body


def test_csharp_publication_has_exactly_twenty_two_supported() -> None:
    payload = _payload()
    rows = payload["skills"]
    by_name = {row["skill"]: row for row in rows}

    assert payload["phase"] == "p7-csharp-full-publication"
    assert len(rows) == len(by_name) == 22
    assert Counter(row["disposition"] for row in rows) == {
        "csharp-supported": 22,
    }
    assert payload["current_assertions"]["pending_skills"] == []
    assert set(payload["current_assertions"]["supported_skills"]) == set(by_name)
    assert all(row["closure_mode"] for row in rows)
    assert (
        ROOT
        / ".claude/tasks/multilanguage-learnings/csharp-structure-proposals.md"
    ).is_file()


def test_csharp_supported_rows_bind_exact_cohort_evidence_and_closures() -> None:
    payload = _payload()
    by_name = {row["skill"]: row for row in payload["skills"]}

    for skill in LEXICAL:
        row = by_name[skill]
        assert row["reviewed_revision"].startswith("dc65da6")
        assert row["evidence_path"].endswith("csharp-lexical-syntax-cohort.md")
        assert row["closure_mode"] == "external-library"
    for skill in SEMANTIC:
        row = by_name[skill]
        assert row["reviewed_revision"].startswith("7d5669c")
        assert row["evidence_path"].endswith("csharp-semantic-family.md")
        assert row["closure_mode"] == "external-library"
    for skill in {"extract-enum", "prevent-regression", "unify-shadows"}:
        row = by_name[skill]
        assert row["reviewed_revision"].startswith("e050407")
        assert row["closure_mode"] == "external-library"
    assert by_name["find-comment-drift"]["reviewed_revision"].startswith("e184263")
    assert by_name["map-subsystem"]["reviewed_revision"].startswith("915f605")
    assert by_name["move-path"]["reviewed_revision"].startswith("d02bb80")
    assert by_name["move-path"]["closure_mode"] == "stock-selected-install"
    for skill in STRUCTURE:
        row = by_name[skill]
        assert row["reviewed_revision"] == (
            "9d44eeaeeae8537f8717c30449cb1c7d2a08b06f"
        )
        assert row["evidence_path"].endswith("csharp-structure-proposals.md")
        assert row["closure_mode"] == "external-library"
        assert "independently applied disposable after-tree" in row["native_check"][1]
    for skill, row in by_name.items():
        assert (ROOT / row["evidence_path"]).is_file(), skill
        assert row["native_check"], skill
        assert row["limitation"], skill


def test_csharp_authority_and_nonclaims_are_pinned() -> None:
    payload = _payload()
    authority = payload["semantic_authority"]
    assert authority["sdk_version"] == "10.0.302"
    assert authority["runtime_version"] == "10.0.10"
    assert authority["lexical_helper_sha256"] == _sha256(
        ROOT / ".claude/skills/_csharp/CSharpSyntaxFacts.cs"
    )
    assert authority["semantic_helper_sha256"] == _sha256(
        ROOT / ".claude/skills/_csharp-semantic/CSharpSemanticFacts.cs"
    )
    assert authority["structure_helper_sha256"] == _sha256(
        ROOT / ".claude/skills/_csharp-semantic/csharp_structure_proposals.py"
    )
    assert authority["reference_pack_assembly_count"] == 167
    limits = " ".join(payload["global_limits"]).lower()
    for boundary in (
        "runtime reachability",
        "override",
        "interface dispatch",
        "delegates",
        "reflection",
        "generated",
        "project/solution graphs",
        "framework registration",
        "structure proposals",
        "host mutation",
        "abi/release compatibility",
    ):
        assert boundary in limits


def test_each_supported_csharp_skill_documents_entrypoint_and_limits() -> None:
    payload = _payload()
    by_name = {row["skill"]: row for row in payload["skills"]}
    for skill, entrypoint in ENTRYPOINTS.items():
        metadata, body = _skill(skill)
        assert "csharp" in metadata["scans"], skill
        assert "C#" in body or "csharp" in body.lower(), skill
        assert entrypoint in body, skill
        assert (ROOT / ".claude/skills" / skill / entrypoint).is_file(), skill
        assert by_name[skill]["disposition"] == "csharp-supported"


def test_structure_promotion_requires_final_implementation_evidence() -> None:
    payload = _payload()
    by_name = {row["skill"]: row for row in payload["skills"]}
    assert (ROOT / "tests/test_csharp_structure_proposals.py").is_file()
    for skill in STRUCTURE:
        metadata, body = _skill(skill)
        row = by_name[skill]
        assert "csharp" in metadata["scans"]
        assert "csharp-structure-acceptance-v1" in body
        assert row["disposition"] == "csharp-supported"
        assert row["closure_mode"] == "external-library"
        assert (ROOT / ".claude/skills" / skill / "scripts/propose_csharp.py").is_file()
