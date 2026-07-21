"""Completeness and freshness checks for the multi-language expansion matrix."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json"
TRANSFER_GUIDE = (
    REPO_ROOT / ".claude" / "tasks" / "multilanguage-typescript-transfer-guide.md"
)
CATALOG = REPO_ROOT / ".claude" / "skills" / "which-skill" / "catalog.json"
TYPESCRIPT_COVERAGE = (
    REPO_ROOT / ".claude" / "tasks" / "typescript-skill-coverage.json"
)
JAVASCRIPT_COVERAGE = (
    REPO_ROOT / ".claude" / "tasks" / "javascript-language-coverage.json"
)
GO_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "go-language-coverage.json"
JAVA_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "java-language-coverage.json"
BUILDER = REPO_ROOT / "scripts" / "build_multilanguage_matrix.py"

EXPECTED_COUNTS = {
    "validated-neutral": 19,
    "ecosystem-runtime": 13,
    "language-level": 22,
    "framework-bound": 22,
}
EXPECTED_JAVASCRIPT_COUNTS = {
    "javascript-supported": 22,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_JAVASCRIPT_COHORT_COUNTS = {
    "lexical-filesystem": 6,
    "syntax": 4,
    "semantic-read-only": 6,
    "proposal-mutation-guard": 6,
}
EXPECTED_GO_COUNTS = {
    "pending-validation": 2,
    "go-supported": 20,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_JAVA_COUNTS = {
    "pending-validation": 19,
    "java-supported": 3,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
FACT_LEVELS = {
    "neutral",
    "ecosystem-runtime",
    "lexical-filesystem",
    "syntax",
    "semantic-project",
    "framework",
}
OUTCOME_CLASSES = {
    "not-applicable",
    "read-only-report",
    "proposal-only",
    "configuration-output",
    "source-mutation",
    "guard-generation",
    "framework-specific",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_multilanguage_matrix_is_current_complete_and_traceable() -> None:
    check = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr or check.stdout

    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = payload["skills"]
    names = [row["skill"] for row in rows]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["skills"]
    catalog_names = {row["name"] for row in catalog}

    assert payload["schema_version"] == 2
    assert len(rows) == 76
    assert len(names) == len(set(names))
    assert set(names) == catalog_names
    assert Counter(row["expansion_disposition"] for row in rows) == EXPECTED_COUNTS
    assert payload["counts"] == EXPECTED_COUNTS
    assert Counter(row["javascript_disposition"] for row in rows) == (
        EXPECTED_JAVASCRIPT_COUNTS
    )
    assert Counter(row["go_disposition"] for row in rows) == EXPECTED_GO_COUNTS
    assert Counter(row["java_disposition"] for row in rows) == EXPECTED_JAVA_COUNTS
    assert Counter(row["optional_install"]["status"] for row in rows) == {
        "passed": 41,
        "deferred-named-stack": 22,
        "not-host-language-variant": 13,
    }

    source_by_path = {row["path"]: row["sha256"] for row in payload["sources"]}
    for source in (
        CATALOG,
        TYPESCRIPT_COVERAGE,
        JAVASCRIPT_COVERAGE,
        GO_COVERAGE,
        JAVA_COVERAGE,
    ):
        relative = str(source.relative_to(REPO_ROOT))
        assert source_by_path[relative] == _sha256(source)

    language_rows = []
    framework_rows = []
    for row in rows:
        assert row["fact_level"] in FACT_LEVELS, row
        assert row["outcome_class"] in OUTCOME_CLASSES, row
        assert (REPO_ROOT / row["typescript_evidence_path"]).is_file(), row
        for packet in row["learning_packets"]:
            assert (REPO_ROOT / packet).is_file(), row

        closure = row["on_demand_closure"]
        companions = row["catalog"]["install_with"]
        assert closure["mode"] == "on-demand-library"
        assert closure["closure_skills"] == [row["skill"], *companions]
        assert len(closure["closure_skills"]) == len(set(closure["closure_skills"]))
        assert set(closure["closure_skills"]) <= catalog_names
        assert [guide["skill"] for guide in closure["guides"]] == closure[
            "closure_skills"
        ]
        for guide in closure["guides"]:
            assert (REPO_ROOT / guide["skill_root"]).is_dir(), row
            assert (REPO_ROOT / guide["guide"]).is_file(), row
            if guide["bundled_tooling"] is not None:
                assert (REPO_ROOT / guide["bundled_tooling"]).is_dir(), row
        for shared in ("shared_tooling", "common_guidance", "shared_guidance"):
            assert (REPO_ROOT / closure[shared]).is_dir(), row

        optional_install = row["optional_install"]
        assert optional_install["role"] == "secondary-explicit-user-choice"
        assert optional_install["evidence_basis"] == "historical-stock-selected-install"
        assert optional_install["command"]

        if row["expansion_disposition"] == "language-level":
            language_rows.append(row)
            assert row["fact_level"] in {
                "lexical-filesystem",
                "syntax",
                "semantic-project",
            }
            assert row["learning_packets"], row
            assert row["framework_family"] is None
            assert optional_install["status"] == "passed"
            if row["java_disposition"] == "pending-validation":
                assert row["java_evidence_path"] is None
                assert row["java_native_check"] is None
                assert row["java_reviewed_revision"] is None
            else:
                assert row["java_disposition"] == "java-supported"
                assert (REPO_ROOT / row["java_evidence_path"]).is_file()
                assert row["java_native_check"]
                assert row["java_reviewed_revision"]
            if row["javascript_disposition"] == "pending-validation":
                assert row["javascript_evidence_modes"] == ["pending"]
                assert row["javascript_evidence_path"] is None
                assert row["javascript_native_check"] is None
                assert row["javascript_reviewed_revision"] is None
            else:
                assert row["javascript_disposition"] in {
                    "javascript-supported",
                    "javascript-limited",
                }
                assert "pending" not in row["javascript_evidence_modes"]
                assert (REPO_ROOT / row["javascript_evidence_path"]).is_file()
                assert row["javascript_native_check"]
                assert row["javascript_reviewed_revision"]
            if row["javascript_disposition"] != "javascript-limited":
                assert row["javascript_limitation"] is None
            if row["go_disposition"] == "pending-validation":
                assert row["go_evidence_path"] is None
                assert row["go_native_check"] is None
                assert row["go_reviewed_revision"] is None
            else:
                assert row["go_disposition"] == "go-supported"
                assert (REPO_ROOT / row["go_evidence_path"]).is_file()
                assert row["go_native_check"]
                assert row["go_reviewed_revision"]
        elif row["expansion_disposition"] == "framework-bound":
            framework_rows.append(row)
            assert row["fact_level"] == "framework"
            assert row["outcome_class"] == "framework-specific"
            assert row["framework_family"]
            assert row["javascript_disposition"] == "stack-bound"
            assert row["go_disposition"] == "stack-bound"
            assert row["java_disposition"] == "stack-bound"
        elif row["expansion_disposition"] == "validated-neutral":
            assert row["fact_level"] == "neutral"
            assert row["outcome_class"] == "not-applicable"
            assert row["javascript_disposition"] == "validated-neutral"
            assert row["go_disposition"] == "validated-neutral"
            assert row["java_disposition"] == "validated-neutral"
        else:
            assert row["fact_level"] == "ecosystem-runtime"
            assert row["outcome_class"] == "not-applicable"
            assert row["javascript_disposition"] == "ecosystem-runtime"
            assert row["go_disposition"] == "ecosystem-runtime"
            assert row["java_disposition"] == "ecosystem-runtime"

        if row["expansion_disposition"] != "language-level":
            assert row["go_evidence_path"] is None
            assert row["go_native_check"] is None
            assert row["go_reviewed_revision"] is None
            assert row["java_evidence_path"] is None
            assert row["java_native_check"] is None
            assert row["java_reviewed_revision"] is None

        if row["expansion_disposition"] != "language-level":
            assert row["javascript_cohort"] is None
            assert row["javascript_evidence_modes"] == ["not-applicable"]
            assert row["javascript_evidence_path"] is None
            assert row["javascript_native_check"] is None
            assert row["javascript_reviewed_revision"] is None
            assert row["javascript_limitation"] is None

    assert len(language_rows) == 22
    assert Counter(row["javascript_cohort"] for row in language_rows) == (
        EXPECTED_JAVASCRIPT_COHORT_COUNTS
    )
    assert len(framework_rows) == 22
    assert {row["outcome_class"] for row in language_rows} >= {
        "read-only-report",
        "proposal-only",
        "configuration-output",
        "source-mutation",
        "guard-generation",
    }
    rename = next(row for row in language_rows if row["skill"] == "rename-concept")
    assert rename["on_demand_closure"]["closure_skills"] == [
        "rename-concept",
        "find-concept-divergence",
    ]

    language_names = {row["skill"] for row in language_rows}
    primitives = payload["typescript_shared_primitives"]
    assert primitives
    for primitive in primitives:
        consumers = primitive["consumers"]
        assert len(consumers) == len(set(consumers)) >= 2, primitive
        assert set(consumers) <= language_names, primitive
        assert primitive["p1_decision"] in {
            "contract-only",
            "deferred-until-real-repair",
            "shared-contract",
        }
        assert primitive["boundary"]

    guide = TRANSFER_GUIDE.read_text(encoding="utf-8")
    for skill in sorted(language_names):
        assert f"| `{skill}` |" in guide
    guide_rows = {
        line.split("`")[1]
        for line in guide.splitlines()
        if line.startswith("| `")
    }
    assert guide_rows == language_names
