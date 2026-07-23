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
PHP_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "php-language-coverage.json"
SWIFT_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "swift-language-coverage.json"
C_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "c-language-coverage.json"
CPP_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "cpp-language-coverage.json"
RUBY_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "ruby-language-coverage.json"
RUST_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "rust-language-coverage.json"
DART_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "dart-language-coverage.json"
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
    "go-supported": 22,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_JAVA_COUNTS = {
    "java-supported": 22,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_PHP_COUNTS = {
    "php-supported": 3,
    "php-pending-implementation": 19,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_SWIFT_COUNTS = {
    "swift-supported": 3,
    "swift-pending-implementation": 19,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_C_COUNTS = {
    "c-supported": 2,
    "c-pending-implementation": 20,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_CPP_COUNTS = {
    "cpp-supported": 2,
    "cpp-pending-implementation": 20,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_RUBY_COUNTS = {
    "ruby-supported": 1,
    "ruby-partial": 1,
    "ruby-pending-implementation": 20,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_RUST_COUNTS = {
    "rust-supported": 21,
    "rust-partial": 1,
    "validated-neutral": 19,
    "stack-bound": 22,
    "ecosystem-runtime": 13,
}
EXPECTED_DART_COUNTS = {
    "dart-supported": 21,
    "dart-partial": 1,
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


def _run_with_php_coverage(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILDER), "--php-coverage", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_unfinished_language_work_cannot_be_labeled_unsupported(tmp_path: Path) -> None:
    payload = json.loads(PHP_COVERAGE.read_text(encoding="utf-8"))
    row = next(item for item in payload["skills"] if item["skill"] == "adapt-project")
    row["disposition"] = "php-unsupported"
    candidate = tmp_path / "php-language-coverage.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_with_php_coverage(candidate)

    assert result.returncode == 2
    assert "lacks a valid basis" in result.stderr


def test_permanent_unsupported_requires_a_proven_native_alternative(
    tmp_path: Path,
) -> None:
    payload = json.loads(PHP_COVERAGE.read_text(encoding="utf-8"))
    row = next(item for item in payload["skills"] if item["skill"] == "adapt-project")
    row.update(
        {
            "disposition": "php-unsupported",
            "unsupported_basis": "conceptually-inapplicable",
            "alternative_skill": "adapt-php-project",
            "independent_review": "fresh language-native review",
            "language_reference": "PHP and Composer project conventions",
        }
    )
    candidate = tmp_path / "php-language-coverage.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_with_php_coverage(candidate)

    assert result.returncode == 2
    assert "lacks alternative_evidence_path" in result.stderr


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

    assert payload["schema_version"] == 5
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
    assert Counter(row["php_disposition"] for row in rows) == EXPECTED_PHP_COUNTS
    assert Counter(row["swift_disposition"] for row in rows) == EXPECTED_SWIFT_COUNTS
    assert Counter(row["c_disposition"] for row in rows) == EXPECTED_C_COUNTS
    assert Counter(row["cpp_disposition"] for row in rows) == EXPECTED_CPP_COUNTS
    assert Counter(row["ruby_disposition"] for row in rows) == EXPECTED_RUBY_COUNTS
    assert Counter(row["rust_disposition"] for row in rows) == EXPECTED_RUST_COUNTS
    assert Counter(row["dart_disposition"] for row in rows) == EXPECTED_DART_COUNTS
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
        PHP_COVERAGE,
        SWIFT_COVERAGE,
        C_COVERAGE,
        CPP_COVERAGE,
        RUBY_COVERAGE,
        RUST_COVERAGE,
        DART_COVERAGE,
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
            if row["php_disposition"] == "pending-validation":
                assert row["php_evidence_path"] is None
                assert row["php_native_check"] is None
                assert row["php_reviewed_revision"] is None
            else:
                assert row["php_disposition"] in {
                    "php-supported",
                    "php-partial",
                    "php-pending-implementation",
                }
                assert (REPO_ROOT / row["php_evidence_path"]).is_file()
                assert row["php_native_check"]
                assert row["php_reviewed_revision"]
            if row["php_disposition"] in {"php-partial", "php-pending-implementation"}:
                assert row["php_limitation"]
            if row["swift_disposition"] == "pending-validation":
                assert row["swift_evidence_path"] is None
                assert row["swift_native_check"] is None
                assert row["swift_reviewed_revision"] is None
            else:
                assert row["swift_disposition"] in {
                    "swift-supported",
                    "swift-partial",
                    "swift-pending-implementation",
                }
                assert (REPO_ROOT / row["swift_evidence_path"]).is_file()
                assert row["swift_native_check"]
                assert row["swift_reviewed_revision"]
            if row["swift_disposition"] in {"swift-partial", "swift-pending-implementation"}:
                assert row["swift_limitation"]
            if row["c_disposition"] == "pending-validation":
                assert row["c_evidence_path"] is None
                assert row["c_native_check"] is None
                assert row["c_reviewed_revision"] is None
            else:
                assert row["c_disposition"] in {
                    "c-supported",
                    "c-partial",
                    "c-pending-implementation",
                }
                assert (REPO_ROOT / row["c_evidence_path"]).is_file()
                assert row["c_native_check"]
                assert row["c_reviewed_revision"]
            if row["c_disposition"] in {"c-partial", "c-pending-implementation"}:
                assert row["c_limitation"]
            if row["cpp_disposition"] == "pending-validation":
                assert row["cpp_evidence_path"] is None
                assert row["cpp_native_check"] is None
                assert row["cpp_reviewed_revision"] is None
            else:
                assert row["cpp_disposition"] in {
                    "cpp-supported",
                    "cpp-partial",
                    "cpp-pending-implementation",
                }
                assert (REPO_ROOT / row["cpp_evidence_path"]).is_file()
                assert row["cpp_native_check"]
                assert row["cpp_reviewed_revision"]
            if row["cpp_disposition"] in {
                "cpp-partial",
                "cpp-pending-implementation",
            }:
                assert row["cpp_limitation"]
            if row["ruby_disposition"] == "pending-validation":
                assert row["ruby_evidence_path"] is None
                assert row["ruby_native_check"] is None
                assert row["ruby_reviewed_revision"] is None
            else:
                assert row["ruby_disposition"] in {
                    "ruby-supported",
                    "ruby-partial",
                    "ruby-pending-implementation",
                }
                assert (REPO_ROOT / row["ruby_evidence_path"]).is_file()
                assert row["ruby_native_check"]
                assert row["ruby_reviewed_revision"]
            if row["ruby_disposition"] in {
                "ruby-partial",
                "ruby-pending-implementation",
            }:
                assert row["ruby_limitation"]
            if row["rust_disposition"] == "pending-validation":
                assert row["rust_evidence_path"] is None
                assert row["rust_native_check"] is None
                assert row["rust_reviewed_revision"] is None
            else:
                assert row["rust_disposition"] in {
                    "rust-supported",
                    "rust-partial",
                    "rust-pending-implementation",
                }
                assert (REPO_ROOT / row["rust_evidence_path"]).is_file()
                assert row["rust_native_check"]
                assert row["rust_reviewed_revision"]
            if row["rust_disposition"] in {
                "rust-partial",
                "rust-pending-implementation",
            }:
                assert row["rust_limitation"]
            if row["dart_disposition"] == "pending-validation":
                assert row["dart_evidence_path"] is None
                assert row["dart_native_check"] is None
                assert row["dart_reviewed_revision"] is None
            else:
                assert row["dart_disposition"] in {
                    "dart-supported",
                    "dart-partial",
                    "dart-pending-implementation",
                }
                assert (REPO_ROOT / row["dart_evidence_path"]).is_file()
                assert row["dart_native_check"]
                assert row["dart_reviewed_revision"]
            if row["dart_disposition"] in {
                "dart-partial",
                "dart-pending-implementation",
            }:
                assert row["dart_limitation"]
        elif row["expansion_disposition"] == "framework-bound":
            framework_rows.append(row)
            assert row["fact_level"] == "framework"
            assert row["outcome_class"] == "framework-specific"
            assert row["framework_family"]
            assert row["javascript_disposition"] == "stack-bound"
            assert row["go_disposition"] == "stack-bound"
            assert row["java_disposition"] == "stack-bound"
            assert row["php_disposition"] == "stack-bound"
            assert row["swift_disposition"] == "stack-bound"
            assert row["c_disposition"] == "stack-bound"
            assert row["cpp_disposition"] == "stack-bound"
            assert row["ruby_disposition"] == "stack-bound"
            assert row["rust_disposition"] == "stack-bound"
            assert row["dart_disposition"] == "stack-bound"
        elif row["expansion_disposition"] == "validated-neutral":
            assert row["fact_level"] == "neutral"
            assert row["outcome_class"] == "not-applicable"
            assert row["javascript_disposition"] == "validated-neutral"
            assert row["go_disposition"] == "validated-neutral"
            assert row["java_disposition"] == "validated-neutral"
            assert row["php_disposition"] == "validated-neutral"
            assert row["swift_disposition"] == "validated-neutral"
            assert row["c_disposition"] == "validated-neutral"
            assert row["cpp_disposition"] == "validated-neutral"
            assert row["ruby_disposition"] == "validated-neutral"
            assert row["rust_disposition"] == "validated-neutral"
            assert row["dart_disposition"] == "validated-neutral"
        else:
            assert row["fact_level"] == "ecosystem-runtime"
            assert row["outcome_class"] == "not-applicable"
            assert row["javascript_disposition"] == "ecosystem-runtime"
            assert row["go_disposition"] == "ecosystem-runtime"
            assert row["java_disposition"] == "ecosystem-runtime"
            assert row["php_disposition"] == "ecosystem-runtime"
            assert row["swift_disposition"] == "ecosystem-runtime"
            assert row["c_disposition"] == "ecosystem-runtime"
            assert row["cpp_disposition"] == "ecosystem-runtime"
            assert row["ruby_disposition"] == "ecosystem-runtime"
            assert row["rust_disposition"] == "ecosystem-runtime"
            assert row["dart_disposition"] == "ecosystem-runtime"

        if row["expansion_disposition"] != "language-level":
            assert row["go_evidence_path"] is None
            assert row["go_native_check"] is None
            assert row["go_reviewed_revision"] is None
            assert row["java_evidence_path"] is None
            assert row["java_native_check"] is None
            assert row["java_reviewed_revision"] is None
            assert row["php_evidence_path"] is None
            assert row["php_native_check"] is None
            assert row["php_reviewed_revision"] is None
            assert row["php_limitation"] is None
            assert row["swift_evidence_path"] is None
            assert row["swift_native_check"] is None
            assert row["swift_reviewed_revision"] is None
            assert row["swift_limitation"] is None
            assert row["c_evidence_path"] is None
            assert row["c_native_check"] is None
            assert row["c_reviewed_revision"] is None
            assert row["c_limitation"] is None
            assert row["cpp_evidence_path"] is None
            assert row["cpp_native_check"] is None
            assert row["cpp_reviewed_revision"] is None
            assert row["cpp_limitation"] is None
            assert row["ruby_evidence_path"] is None
            assert row["ruby_native_check"] is None
            assert row["ruby_reviewed_revision"] is None
            assert row["ruby_limitation"] is None
            assert row["rust_evidence_path"] is None
            assert row["rust_native_check"] is None
            assert row["rust_reviewed_revision"] is None
            assert row["rust_limitation"] is None
            assert row["dart_evidence_path"] is None
            assert row["dart_native_check"] is None
            assert row["dart_reviewed_revision"] is None
            assert row["dart_limitation"] is None

        if row["expansion_disposition"] != "language-level":
            assert row["javascript_cohort"] is None
            assert row["javascript_evidence_modes"] == ["not-applicable"]
            assert row["javascript_evidence_path"] is None
            assert row["javascript_native_check"] is None
            assert row["javascript_reviewed_revision"] is None
            assert row["javascript_limitation"] is None

    assert len(language_rows) == 22
    assert {
        row["skill"]
        for row in language_rows
        if row["php_disposition"] == "php-supported"
    } == {"find-comment-drift", "map-subsystem", "move-path"}
    assert {
        row["skill"]
        for row in language_rows
        if row["swift_disposition"] == "swift-supported"
    } == {"find-omnibus", "map-subsystem", "move-path"}
    assert {
        row["skill"]
        for row in language_rows
        if row["c_disposition"] == "c-supported"
    } == {"find-comment-drift", "map-subsystem"}
    assert {
        row["skill"]
        for row in language_rows
        if row["cpp_disposition"] == "cpp-supported"
    } == {"find-comment-drift", "map-subsystem"}
    assert {
        row["skill"]
        for row in language_rows
        if row["ruby_disposition"] == "ruby-supported"
    } == {"find-comment-drift"}
    assert {
        row["skill"]
        for row in language_rows
        if row["ruby_disposition"] == "ruby-partial"
    } == {"map-subsystem"}
    assert {
        row["skill"]
        for row in language_rows
        if row["rust_disposition"] == "rust-supported"
    } == {
        "adapt-project",
        "audit-decisions",
        "explain-code",
        "extract-enum",
        "find-comment-drift",
        "find-complexity-hotspots",
        "find-concept-divergence",
        "find-dormant",
        "find-duplication",
        "find-folder-topology-drift",
        "find-implicit-state",
        "find-incomplete-sweep",
        "find-omnibus",
        "find-semantic-duplication",
        "find-standard-gaps",
        "move-path",
        "prevent-regression",
        "propose-boundary",
        "propose-folder-reorganization",
        "rename-concept",
        "unify-shadows",
    }
    assert {
        row["skill"]
        for row in language_rows
        if row["rust_disposition"] == "rust-partial"
    } == {"map-subsystem"}
    assert not {
        row["skill"]
        for row in language_rows
        if row["dart_disposition"] == "dart-pending-implementation"
    }
    assert {
        row["skill"]
        for row in language_rows
        if row["dart_closure_mode"] == "external-library"
    } == {
        "adapt-project",
        "audit-decisions",
        "explain-code",
        "extract-enum",
        "find-comment-drift",
        "find-complexity-hotspots",
        "find-concept-divergence",
        "find-duplication",
        "find-folder-topology-drift",
        "find-omnibus",
        "find-semantic-duplication",
        "find-standard-gaps",
        "move-path",
        "prevent-regression",
        "propose-boundary",
        "propose-folder-reorganization",
        "unify-shadows",
    }
    assert {
        row["skill"]
        for row in language_rows
        if row["dart_closure_mode"] == "stock-selected-install"
    } == {
        "find-dormant",
        "find-implicit-state",
        "find-incomplete-sweep",
        "map-subsystem",
        "rename-concept",
    }
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
        "map-subsystem",
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
