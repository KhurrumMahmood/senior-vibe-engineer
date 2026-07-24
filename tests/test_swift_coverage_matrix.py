"""Truth sentinels for the bounded 22/22 Swift publication."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / ".claude/tasks/swift-language-coverage.json"
A3_REVISION = "c5addab9dd4cfd5e16cbc1719d6e104c706ab84f"
STATE_REVISION = "f03cf8a9b93ff637011cf4d20cb5cdad47282b1e"
SEMANTIC_UNIFY_REVISION = "2d411cb6feb0c4d5acc49ef547f61c81ec3f6f61"
STRUCTURE_REVISION = "50dfd13aafd2b721a3555b96cb688941b8d917b0"
SEMANTIC_SKILLS = {
    "find-dormant",
    "find-implicit-state",
    "find-incomplete-sweep",
    "rename-concept",
}
STATE_SKILLS = {"extract-enum", "prevent-regression"}
STRUCTURE_SKILLS = {"propose-boundary", "propose-folder-reorganization"}
PUBLISHED_SKILLS = {
    *SEMANTIC_SKILLS,
    *STATE_SKILLS,
    *STRUCTURE_SKILLS,
    "find-semantic-duplication",
    "unify-shadows",
}
ENTRYPOINTS = {
    "extract-enum": "scripts/collect_swift_state.py",
    "find-dormant": "scripts/detect_swift_dormant.py",
    "find-implicit-state": "scripts/detect_swift_state.py",
    "find-incomplete-sweep": "scripts/detect_swift_incomplete_sweep.py",
    "find-semantic-duplication": "scripts/detect_swift_semantic.py",
    "prevent-regression": "scripts/stage_swift_state_guard.py",
    "propose-boundary": "scripts/propose_swift.py",
    "propose-folder-reorganization": "scripts/propose_swift.py",
    "rename-concept": "scripts/swift_identifier_evidence.py",
    "unify-shadows": "scripts/propose_swift.py",
}
PROVIDER = ".claude/skills/_swift-semantic-readonly/swift_semantic_facts.py"
ACCEPTED = ".claude/skills/_swift-semantic-readonly/swift_accepted_evidence.py"
STRUCTURE = ".claude/skills/_swift-semantic-readonly/swift_structure_proposals.py"


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


def test_swift_full_publication_has_exactly_twenty_two_supported() -> None:
    payload = _payload()
    rows = payload["skills"]
    by_name = {row["skill"]: row for row in rows}

    assert payload["phase"] == "p7-swift-full-publication"
    assert len(rows) == len(by_name) == 22
    assert Counter(row["disposition"] for row in rows) == {"swift-supported": 22}
    assert payload["current_assertions"] == {
        "swift-supported": 22,
        "swift-pending-implementation": 0,
        "supported_skills": list(by_name),
        "pending_skills": [],
    }
    assert Counter(row["closure_mode"] for row in rows) == {
        "external-library": 19,
        "stock-selected-install": 3,
    }
    assert {
        skill
        for skill, row in by_name.items()
        if row["closure_mode"] == "stock-selected-install"
    } == {"find-omnibus", "map-subsystem", "move-path"}


def test_new_swift_rows_bind_exact_evidence_revisions_and_limits() -> None:
    by_name = {row["skill"]: row for row in _payload()["skills"]}

    for skill in SEMANTIC_SKILLS:
        row = by_name[skill]
        assert row["reviewed_revision"] == A3_REVISION
        assert row["evidence_path"].endswith("swift-semantic-a3.md")
    for skill in STATE_SKILLS:
        row = by_name[skill]
        assert row["reviewed_revision"] == STATE_REVISION
        assert row["evidence_path"].endswith("swift-state-proposal-guard.md")
    for skill in STRUCTURE_SKILLS:
        row = by_name[skill]
        assert row["reviewed_revision"] == STRUCTURE_REVISION
        assert row["evidence_path"].endswith("swift-structure-proposals.md")
        assert "disposable" in " ".join(row["native_check"])
    semantic = by_name["find-semantic-duplication"]
    assert semantic["reviewed_revision"] == SEMANTIC_UNIFY_REVISION
    assert semantic["evidence_path"].endswith("swift-semantic-a3.md")
    unify = by_name["unify-shadows"]
    assert unify["reviewed_revision"] == SEMANTIC_UNIFY_REVISION
    assert unify["evidence_path"].endswith("swift-unify-shadows.md")

    for skill in PUBLISHED_SKILLS:
        row = by_name[skill]
        assert row["disposition"] == "swift-supported"
        assert row["closure_mode"] == "external-library"
        assert (ROOT / row["evidence_path"]).is_file(), skill
        assert row["native_check"], skill
        assert row["limitation"], skill


def test_swift_semantic_authority_and_global_nonclaims_are_exact() -> None:
    payload = _payload()
    authority = payload["semantic_authority"]
    assert authority == {
        "boundary": (
            "Apple Swift 6.3.3 swiftc compiler-AST facts over one exact "
            "dependency-free SwiftPM selected target"
        ),
        "schema_version": "swift-semantic-facts-v2",
        "swift_version": "6.3.3",
        "swift_format_version": "6.3.0",
        "provider_sha256": _sha256(ROOT / PROVIDER),
        "accepted_evidence_sha256": _sha256(ROOT / ACCEPTED),
        "structure_proposals_sha256": _sha256(ROOT / STRUCTURE),
    }
    limits = " ".join(payload["global_limits"]).lower()
    for boundary in (
        "selected target",
        "conditional compilation",
        "macro",
        "generated",
        "reflection",
        "objective-c",
        "protocol",
        "external callers",
        "xcode",
        "framework",
        "runtime",
        "abi",
        "mutation authority",
    ):
        assert boundary in limits


def test_published_swift_skills_declare_scan_entrypoint_and_helper_closure() -> None:
    matrix = json.loads(
        (ROOT / ".claude/tasks/multilanguage-skill-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    matrix_by_name = {row["skill"]: row for row in matrix["skills"]}

    for skill, entrypoint in ENTRYPOINTS.items():
        metadata, body = _skill(skill)
        assert "swift" in metadata["scans"], skill
        assert entrypoint in body, skill
        assert "Swift" in body, skill
        assert (ROOT / ".claude/skills" / skill / entrypoint).is_file(), skill

        helpers = matrix_by_name[skill]["on_demand_closure"]["language_helpers"]
        expected = [PROVIDER]
        if skill in STATE_SKILLS:
            expected.append(ACCEPTED)
        if skill in STRUCTURE_SKILLS:
            expected.append(STRUCTURE)
        assert helpers == {"swift": expected}
        assert all((ROOT / path).is_file() for path in helpers["swift"])
