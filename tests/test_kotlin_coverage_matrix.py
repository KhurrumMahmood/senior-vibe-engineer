"""Honest full-publication contract for bounded Kotlin/JVM outcomes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".claude" / "tasks" / "kotlin-language-coverage.json"
SPINE_REVISION = "c7c9b55686cf1b0738c052021329224a5ab2bf93"
LEXICAL_REVISION = "28a49e8cb6af3bac81dc776e84b6be9a68a01d0e"
SEMANTIC_REVISION = "bc08603b63e944d4dbf6e558553e2141d3d9275d"
MOVE_REVISION = "5c4a97be223019e3b6ada967e904ed1ffacc9646"
STATE_REVISION = "3d4751cef6aa620a4d9724f1d8070c6828064fa6"
COMMENT_REVISION = "5c33e9383c969814805898590c1cb281ac88bcb5"
MAP_REVISION = "49abe099528688996a502f0bf6479334a94b7960"
UNIFY_REVISION = "b4c13fd1a92865a933869c356bd6565035c44928"
STRUCTURE_REVISION = "2c35b98d9ff9f6e2ee86495e81ecae1a47effb4f"
LEXICAL_SKILLS = {
    "adapt-project",
    "audit-decisions",
    "explain-code",
    "find-comment-drift",
    "find-complexity-hotspots",
    "find-concept-divergence",
    "find-duplication",
    "find-folder-topology-drift",
    "find-omnibus",
    "find-standard-gaps",
}
SEMANTIC_SKILLS = {
    "find-dormant",
    "find-implicit-state",
    "find-incomplete-sweep",
    "find-semantic-duplication",
    "rename-concept",
}
ACCEPTED_EVIDENCE_SKILLS = {"extract-enum", "prevent-regression"}
STRUCTURE_SKILLS = {"propose-boundary", "propose-folder-reorganization"}
PENDING_SKILLS: set[str] = set()
ENTRYPOINTS = {
    "adapt-project": "scripts/discover_kotlin.py",
    "audit-decisions": "scripts/audit_kotlin.py",
    "explain-code": "scripts/explain_kotlin.py",
    "extract-enum": "scripts/collect_kotlin_state.py",
    "find-comment-drift": "scripts/analyze_comments_kotlin.py",
    "find-complexity-hotspots": "scripts/run_kotlin.py",
    "find-concept-divergence": "scripts/scan_kotlin.py",
    "find-dormant": "scripts/detect_kotlin_dormant.py",
    "find-duplication": "scripts/run_kotlin.py",
    "find-folder-topology-drift": "scripts/detect_kotlin.py",
    "find-implicit-state": "scripts/detect_kotlin_state.py",
    "find-incomplete-sweep": "scripts/detect_kotlin_incomplete_sweep.py",
    "find-omnibus": "scripts/run_kotlin.py",
    "find-semantic-duplication": "scripts/detect_kotlin_semantic.py",
    "find-standard-gaps": "scripts/scan_coverage_kotlin.py",
    "map-subsystem": "scripts/map_kotlin.py",
    "move-path": "scripts/kotlin_source_move.py",
    "prevent-regression": "scripts/stage_kotlin_state_guard.py",
    "propose-boundary": "scripts/propose_kotlin.py",
    "propose-folder-reorganization": "scripts/propose_kotlin.py",
    "rename-concept": "scripts/assess_kotlin_rename.py",
    "unify-shadows": "scripts/propose_kotlin.py",
}


def _payload() -> dict:
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _skill(skill: str) -> tuple[dict, str]:
    text = (ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    _, raw, body = text.split("---", 2)
    return yaml.safe_load(raw), body


def test_kotlin_full_publication_has_all_bounded_outcomes_supported() -> None:
    payload = _payload()
    rows = payload["skills"]
    by_name = {row["skill"]: row for row in rows}

    assert payload["phase"] == "p8-kotlin-full-publication"
    assert payload["minimum_kotlin_version"] == "2.4.10"
    assert payload["minimum_jdk_version"] == "17.0.0"
    assert len(rows) == len(by_name) == 22
    assert Counter(row["disposition"] for row in rows) == {
        "kotlin-supported": 22,
    }
    assert set(payload["current_assertions"]["supported_skills"]) == (
        LEXICAL_SKILLS
        | SEMANTIC_SKILLS
        | ACCEPTED_EVIDENCE_SKILLS
        | STRUCTURE_SKILLS
        | {"map-subsystem", "move-path", "unify-shadows"}
    )
    assert set(payload["current_assertions"]["pending_skills"]) == PENDING_SKILLS
    assert {
        skill
        for skill, row in by_name.items()
        if row["disposition"] == "kotlin-pending-implementation"
    } == PENDING_SKILLS

    for skill in LEXICAL_SKILLS:
        row = by_name[skill]
        assert row["disposition"] == "kotlin-supported"
        assert row["closure_mode"] == "external-library"
        if skill == "find-comment-drift":
            assert row["evidence_path"].endswith("kotlin-find-comment-drift.md")
            assert row["reviewed_revision"] == COMMENT_REVISION
        else:
            assert row["evidence_path"].endswith("kotlin-lexical-syntax-cohort.md")
            assert row["reviewed_revision"] == LEXICAL_REVISION
    for skill in SEMANTIC_SKILLS:
        row = by_name[skill]
        assert row["disposition"] == "kotlin-supported"
        assert row["closure_mode"] == "external-library"
        assert row["evidence_path"].endswith("kotlin-semantic-read-only.md")
        assert row["reviewed_revision"] == SEMANTIC_REVISION
        assert "K1" in " ".join(row["native_check"])
    for skill in ACCEPTED_EVIDENCE_SKILLS:
        row = by_name[skill]
        assert row["disposition"] == "kotlin-supported"
        assert row["closure_mode"] == "external-library"
        assert row["evidence_path"].endswith("kotlin-state-proposal-guard.md")
        assert row["reviewed_revision"] == STATE_REVISION
    move = by_name["move-path"]
    assert move["closure_mode"] == "stock-selected-install"
    assert move["evidence_path"].endswith("kotlin-move-path.md")
    assert move["reviewed_revision"] == MOVE_REVISION
    subsystem_map = by_name["map-subsystem"]
    assert subsystem_map["closure_mode"] == "external-library"
    assert subsystem_map["evidence_path"].endswith("kotlin-comment-map.md")
    assert subsystem_map["reviewed_revision"] == MAP_REVISION
    unify = by_name["unify-shadows"]
    assert unify["closure_mode"] == "external-library"
    assert unify["evidence_path"].endswith("kotlin-unify-shadows.md")
    assert unify["reviewed_revision"] == UNIFY_REVISION
    for skill in STRUCTURE_SKILLS:
        row = by_name[skill]
        assert row["closure_mode"] == "external-library"
        assert row["evidence_path"].endswith("kotlin-structure-proposals.md")
        assert row["reviewed_revision"] == STRUCTURE_REVISION
        assert "disposable" in " ".join(row["native_check"])

    for row in rows:
        assert (ROOT / row["evidence_path"]).is_file(), row
        assert row["native_check"], row
        assert row["limitation"], row


def test_kotlin_spine_remains_an_explicit_historical_22_pending_baseline() -> None:
    payload = _payload()
    baseline = payload["historical_spine_baseline"]
    current_names = [row["skill"] for row in payload["skills"]]

    assert payload["baseline_revision"] == SPINE_REVISION
    assert baseline == {
        "revision": SPINE_REVISION,
        "evidence_path": ".claude/tasks/multilanguage-learnings/kotlin-spine.md",
        "disposition": "kotlin-pending-implementation",
        "skill_count": 22,
        "skills": current_names,
    }


def test_kotlin_semantic_authority_and_global_nonclaims_are_exact() -> None:
    payload = _payload()
    authority = payload["semantic_authority"]
    common = ROOT / ".claude" / "skills" / "_kotlin-semantic"

    assert authority == {
        "boundary": (
            "deprecated K1 compiler API pinned to the observed Kotlin 2.4.10 "
            "distribution; not the stable Analysis API"
        ),
        "kotlin_version": "2.4.10",
        "jdk_version": "17.0.12",
        "compiler_jar_sha256": (
            "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
        ),
        "stdlib_jar_sha256": (
            "4ec0293bc3751423b203f1d8493251c57c42e73eb6377a6b8560d0974ff0a6df"
        ),
        "helper_source_sha256": _sha256(common / "KotlinSemanticFacts.kt"),
        "provider_sha256": _sha256(common / "kotlin_semantic_facts.py"),
    }
    limits = " ".join(payload["global_limits"]).lower()
    for required in (
        "k1 bindingcontext",
        "reflection",
        "override",
        "delegat",
        "generated/kapt/ksp",
        "gradle variants",
        "java sources and callers",
        "runtime reachability",
        "manifest-selected",
        "test main",
        "smoke main",
    ):
        assert required in limits


def test_each_published_kotlin_skill_declares_trigger_entrypoint_and_limits() -> None:
    lexical_guide = ROOT / ".claude" / "skills" / "_kotlin" / "GUIDE.md"
    semantic_guide = (
        ROOT / ".claude" / "skills" / "_kotlin-semantic" / "GUIDE.md"
    )
    assert lexical_guide.is_file()
    assert semantic_guide.is_file()

    for skill, entrypoint in ENTRYPOINTS.items():
        metadata, body = _skill(skill)
        assert "kotlin" in metadata["scans"], skill
        assert entrypoint in body, skill
        assert "Trigger this" in body, skill
        assert "remain" in body, skill
        if skill in LEXICAL_SKILLS:
            assert "../_kotlin/GUIDE.md" in body, skill
            assert entrypoint in lexical_guide.read_text(encoding="utf-8"), skill
        elif skill in SEMANTIC_SKILLS:
            assert "../_kotlin-semantic/GUIDE.md" in body, skill
            assert entrypoint in semantic_guide.read_text(encoding="utf-8"), skill
            assert "K1" in body, skill
        elif skill in ACCEPTED_EVIDENCE_SKILLS:
            assert "../_kotlin-semantic/GUIDE.md" in body, skill
            assert entrypoint in semantic_guide.read_text(encoding="utf-8"), skill
        elif skill == "map-subsystem":
            assert "../_kotlin/GUIDE.md" in body, skill
            assert "../_kotlin-semantic/GUIDE.md" in body, skill
            assert entrypoint in lexical_guide.read_text(encoding="utf-8"), skill
            assert entrypoint in semantic_guide.read_text(encoding="utf-8"), skill
        elif skill == "unify-shadows" or skill in STRUCTURE_SKILLS:
            assert "../_kotlin-semantic/GUIDE.md" in body, skill
            assert entrypoint in semantic_guide.read_text(encoding="utf-8"), skill
        else:
            assert skill == "move-path"
            assert "content-addressed evidence" in body
