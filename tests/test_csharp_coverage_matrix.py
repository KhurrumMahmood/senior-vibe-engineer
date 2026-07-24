"""Truth sentinels for the bounded 20/22 C# publication checkpoint."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".claude/tasks/csharp-language-coverage.json"
PENDING = {"propose-boundary", "propose-folder-reorganization"}
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


def test_csharp_checkpoint_has_exactly_twenty_supported_and_two_pending() -> None:
    payload = _payload()
    rows = payload["skills"]
    by_name = {row["skill"]: row for row in rows}

    assert payload["phase"] == "p7-csharp-20-of-22-publication-checkpoint"
    assert len(rows) == len(by_name) == 22
    assert Counter(row["disposition"] for row in rows) == {
        "csharp-supported": 20,
        "csharp-pending-implementation": 2,
    }
    assert set(payload["current_assertions"]["pending_skills"]) == PENDING
    assert {
        skill
        for skill, row in by_name.items()
        if row["disposition"] == "csharp-pending-implementation"
    } == PENDING
    assert set(payload["current_assertions"]["supported_skills"]) == (
        set(by_name) - PENDING
    )
    for skill in PENDING:
        row = by_name[skill]
        assert "closure_mode" not in row
        assert row["reviewed_revision"] == payload["baseline_revision"]
        assert "no accepted C#" in row["native_check"][0]
        assert "Pending the separate structure lane" in row["limitation"]
    assert not (
        ROOT
        / ".claude/tasks/multilanguage-learnings/csharp-structure-proposals.md"
    ).exists()


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
        "propose-boundary",
        "propose-folder-reorganization",
        "no structure proposal or 22/22",
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
    for skill in PENDING:
        metadata, body = _skill(skill)
        assert "csharp" not in metadata["scans"], skill
        assert "C#" not in body and "csharp" not in body.lower(), skill
