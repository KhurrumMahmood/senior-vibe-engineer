#!/usr/bin/env python3
"""Build the tracked multi-language expansion matrix from accepted inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / ".claude" / "skills" / "which-skill" / "catalog.json"
DEFAULT_TYPESCRIPT_COVERAGE = (
    REPO_ROOT / ".claude" / "tasks" / "typescript-skill-coverage.json"
)
DEFAULT_JAVASCRIPT_COVERAGE = (
    REPO_ROOT / ".claude" / "tasks" / "javascript-language-coverage.json"
)
DEFAULT_GO_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "go-language-coverage.json"
DEFAULT_JAVA_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "java-language-coverage.json"
DEFAULT_PHP_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "php-language-coverage.json"
DEFAULT_SWIFT_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "swift-language-coverage.json"
DEFAULT_C_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "c-language-coverage.json"
DEFAULT_CPP_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "cpp-language-coverage.json"
DEFAULT_RUBY_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "ruby-language-coverage.json"
DEFAULT_RUST_COVERAGE = REPO_ROOT / ".claude" / "tasks" / "rust-language-coverage.json"
DEFAULT_OUTPUT = REPO_ROOT / ".claude" / "tasks" / "multilanguage-skill-matrix.json"

DISPOSITION_MAP = {
    "validated-neutral": "validated-neutral",
    "ecosystem-runtime": "ecosystem-runtime",
    "typescript-supported": "language-level",
    "stack-bound": "framework-bound",
}

# This is the small, reviewed judgment layer. Everything else in the matrix is
# joined mechanically from the router catalog and accepted TypeScript evidence.
LANGUAGE_CLASSIFICATION = {
    "adapt-project": ("lexical-filesystem", "configuration-output"),
    "audit-decisions": ("syntax", "read-only-report"),
    "explain-code": ("lexical-filesystem", "read-only-report"),
    "extract-enum": ("semantic-project", "proposal-only"),
    "find-comment-drift": ("lexical-filesystem", "read-only-report"),
    "find-complexity-hotspots": ("syntax", "read-only-report"),
    "find-concept-divergence": ("lexical-filesystem", "read-only-report"),
    "find-dormant": ("semantic-project", "read-only-report"),
    "find-duplication": ("lexical-filesystem", "read-only-report"),
    "find-folder-topology-drift": ("lexical-filesystem", "read-only-report"),
    "find-implicit-state": ("semantic-project", "read-only-report"),
    "find-incomplete-sweep": ("semantic-project", "read-only-report"),
    "find-omnibus": ("syntax", "read-only-report"),
    "find-semantic-duplication": ("semantic-project", "read-only-report"),
    "find-standard-gaps": ("syntax", "read-only-report"),
    "map-subsystem": ("semantic-project", "read-only-report"),
    "move-path": ("lexical-filesystem", "source-mutation"),
    "prevent-regression": ("semantic-project", "guard-generation"),
    "propose-boundary": ("semantic-project", "proposal-only"),
    "propose-folder-reorganization": ("semantic-project", "proposal-only"),
    "rename-concept": ("semantic-project", "read-only-report"),
    "unify-shadows": ("semantic-project", "proposal-only"),
}

JAVASCRIPT_COHORTS = {
    "lexical-filesystem": {
        "adapt-project",
        "explain-code",
        "find-comment-drift",
        "find-concept-divergence",
        "find-duplication",
        "find-folder-topology-drift",
    },
    "syntax": {
        "audit-decisions",
        "find-complexity-hotspots",
        "find-omnibus",
        "find-standard-gaps",
    },
    "semantic-read-only": {
        "find-dormant",
        "find-implicit-state",
        "find-incomplete-sweep",
        "find-semantic-duplication",
        "map-subsystem",
        "rename-concept",
    },
    "proposal-mutation-guard": {
        "extract-enum",
        "move-path",
        "prevent-regression",
        "propose-boundary",
        "propose-folder-reorganization",
        "unify-shadows",
    },
}

LEARNING_PACKETS = {
    "adapt-project": ["adapt-project-typescript"],
    "audit-decisions": ["audit-decisions-typescript"],
    "explain-code": ["explain-code-typescript"],
    "extract-enum": ["b2p-state-reference", "b2t-typescript-closed-state"],
    "find-comment-drift": ["b3-comment-drift"],
    "find-complexity-hotspots": ["find-complexity-hotspots-typescript"],
    "find-concept-divergence": ["b1-portability"],
    "find-dormant": ["find-dormant-typescript"],
    "find-duplication": ["find-duplication-typescript"],
    "find-folder-topology-drift": ["find-folder-topology-drift-typescript"],
    "find-implicit-state": ["b2p-state-reference", "b2t-typescript-closed-state"],
    "find-incomplete-sweep": ["find-incomplete-sweep-typescript", "go-final-coverage"],
    "find-omnibus": ["find-omnibus-typescript"],
    "find-semantic-duplication": [
        "find-semantic-duplication-typescript",
        "go-semantic-maintenance-family",
    ],
    "find-standard-gaps": ["find-standard-gaps-typescript"],
    "map-subsystem": ["map-subsystem-typescript"],
    "move-path": ["move-path-typescript"],
    "prevent-regression": ["b2p-state-reference", "b2t-typescript-closed-state"],
    "propose-boundary": ["propose-boundary-typescript"],
    "propose-folder-reorganization": ["propose-folder-reorganization-typescript", "go-final-coverage"],
    "rename-concept": [
        "b1-portability",
        "rename-concept-typescript",
        "go-semantic-maintenance-family",
    ],
    "unify-shadows": [
        "unify-shadows-typescript",
        "go-semantic-maintenance-family",
    ],
}

FRAMEWORK_FAMILIES = {
    "frontend-ui": {
        "extract-cotton-primitive",
        "find-frontend-contract-drift",
        "find-frontend-duplication",
    },
    "route-workflow": {
        "extract-workflow-registry",
        "find-dead-route-surface",
        "find-doc-route-drift",
        "find-route-sprawl",
        "find-workflow-duplication",
        "find-workflow-state-gaps",
        "fix-workflow",
        "map-product-workflow",
    },
    "data-model": {
        "extract-state-type",
        "find-query-mutation",
        "find-transaction-overreach",
        "introduce-fk",
    },
    "architecture-planning": {
        "find-layer-violation",
        "impact-feature",
        "plan-feature",
        "refactor-subsystem",
    },
    "framework-quality": {
        "find-async-lifecycle-drift",
        "find-contract-drift",
        "find-test-obligation-drift",
    },
}

SHARED_PRIMITIVES = [
    {
        "primitive": "project-local-typescript-resolution",
        "p1_decision": "deferred-until-real-repair",
        "consumers": [
            "audit-decisions",
            "find-complexity-hotspots",
            "find-dormant",
            "find-implicit-state",
            "find-incomplete-sweep",
            "find-omnibus",
            "find-semantic-duplication",
            "find-standard-gaps",
            "map-subsystem",
            "prevent-regression",
            "propose-boundary",
            "propose-folder-reorganization",
            "rename-concept",
        ],
        "boundary": "Resolve TypeScript from the audited host and reject packages outside its project root.",
    },
    {
        "primitive": "tsconfig-project-loading",
        "p1_decision": "deferred-until-real-repair",
        "consumers": [
            "find-dormant",
            "find-implicit-state",
            "find-incomplete-sweep",
            "find-semantic-duplication",
            "map-subsystem",
            "prevent-regression",
            "propose-boundary",
            "propose-folder-reorganization",
            "rename-concept",
        ],
        "boundary": "Load one explicit host tsconfig, preserve diagnostics, and never invent a project graph.",
    },
    {
        "primitive": "project-path-containment",
        "p1_decision": "deferred-until-real-repair",
        "consumers": [
            "find-dormant",
            "find-incomplete-sweep",
            "find-semantic-duplication",
            "map-subsystem",
            "propose-boundary",
            "propose-folder-reorganization",
            "rename-concept",
            "unify-shadows",
        ],
        "boundary": "Normalize real paths, reject boundary escapes and unsafe symlink traversal, and render project-relative paths.",
    },
    {
        "primitive": "first-party-typescript-inventory",
        "p1_decision": "shared-contract",
        "consumers": [
            "adapt-project",
            "find-concept-divergence",
            "find-dormant",
            "find-folder-topology-drift",
            "map-subsystem",
            "rename-concept",
        ],
        "boundary": "Inventory every first-party .ts/.tsx file before skill-specific eligibility and record exclusions.",
    },
    {
        "primitive": "typed-failure-status",
        "p1_decision": "contract-only",
        "consumers": [
            "find-dormant",
            "find-incomplete-sweep",
            "find-semantic-duplication",
            "find-standard-gaps",
            "map-subsystem",
            "propose-boundary",
            "propose-folder-reorganization",
            "rename-concept",
        ],
        "boundary": "Distinguish complete, partial, unsupported, and failed without sharing analysis-specific result schemas.",
    },
]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _learning_paths(skill: str) -> list[str]:
    paths = [
        f".claude/tasks/multilanguage-learnings/{stem}.json"
        for stem in LEARNING_PACKETS.get(skill, [])
    ]
    missing = [path for path in paths if not (REPO_ROOT / path).is_file()]
    if missing:
        raise ValueError(f"{skill} references missing learning packets: {missing}")
    return paths


def _framework_family(skill: str) -> str:
    matches = [family for family, skills in FRAMEWORK_FAMILIES.items() if skill in skills]
    if len(matches) != 1:
        raise ValueError(f"{skill} must belong to exactly one framework family: {matches}")
    return matches[0]


def _on_demand_closure(skill: str, companions: list[str]) -> dict:
    closure_skills = [skill, *companions]
    guides = []
    for closure_skill in closure_skills:
        skill_root = Path(".claude") / "skills" / closure_skill
        guide = skill_root / "SKILL.md"
        tooling = skill_root / "scripts"
        if not (REPO_ROOT / guide).is_file():
            raise ValueError(f"missing on-demand guide for {closure_skill}: {guide}")
        guides.append(
            {
                "skill": closure_skill,
                "skill_root": str(skill_root),
                "guide": str(guide),
                "bundled_tooling": str(tooling) if (REPO_ROOT / tooling).is_dir() else None,
            }
        )
    return {
        "mode": "on-demand-library",
        "closure_skills": closure_skills,
        "guides": guides,
        "shared_tooling": "scripts",
        "common_guidance": ".claude/skills/_common",
        "shared_guidance": ".claude/docs",
    }


def _javascript_coverage(payload: dict) -> dict[str, dict]:
    if payload.get("schema_version") != 1:
        raise ValueError("JavaScript coverage schema must be 1")
    if payload.get("suffixes") != [".js", ".jsx", ".mjs", ".cjs"]:
        raise ValueError("JavaScript coverage must declare .js/.jsx/.mjs/.cjs")
    allowed_dispositions = set(payload.get("allowed_dispositions", []))
    allowed_evidence = set(payload.get("allowed_evidence_modes", []))
    rows = payload.get("skills")
    if not isinstance(rows, list):
        raise ValueError("JavaScript coverage skills must be a list")
    by_name: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("skill"), str):
            raise ValueError("JavaScript coverage rows need skill names")
        skill = row["skill"]
        if not skill or skill in by_name:
            raise ValueError("JavaScript coverage skill names must be unique")
        if row.get("disposition") not in allowed_dispositions:
            raise ValueError(f"invalid JavaScript disposition for {skill}")
        evidence_modes = row.get("evidence_modes")
        if (
            not isinstance(evidence_modes, list)
            or not evidence_modes
            or not set(evidence_modes) <= allowed_evidence
        ):
            raise ValueError(f"invalid JavaScript evidence modes for {skill}")
        by_name[skill] = row

    expected = set(LANGUAGE_CLASSIFICATION)
    if set(by_name) != expected:
        raise ValueError("JavaScript coverage must contain the 22 language-level skills")
    for cohort, skills in JAVASCRIPT_COHORTS.items():
        actual = {name for name, row in by_name.items() if row.get("cohort") == cohort}
        if actual != skills:
            raise ValueError(f"JavaScript cohort mismatch for {cohort}")
    if set().union(*JAVASCRIPT_COHORTS.values()) != expected:
        raise ValueError("JavaScript cohorts must assign every language-level skill once")

    for skill, row in by_name.items():
        disposition = row["disposition"]
        if disposition == "pending-validation":
            if row["evidence_modes"] != ["pending"] or any(
                row.get(field) is not None
                for field in ("evidence_path", "native_check", "reviewed_revision")
            ):
                raise ValueError(f"pending JavaScript row has premature evidence: {skill}")
            continue
        evidence_path = row.get("evidence_path")
        native_check = row.get("native_check")
        if (
            "pending" in row["evidence_modes"]
            or not isinstance(evidence_path, str)
            or not (REPO_ROOT / evidence_path).is_file()
            or not isinstance(native_check, list)
            or not native_check
            or any(not isinstance(arg, str) or not arg for arg in native_check)
            or not isinstance(row.get("reviewed_revision"), str)
            or not row["reviewed_revision"]
        ):
            raise ValueError(f"completed JavaScript row lacks evidence: {skill}")
        if disposition == "javascript-limited" and not row.get("limitation"):
            raise ValueError(f"limited JavaScript row lacks a limitation: {skill}")
    return by_name


def _simple_language_coverage(
    payload: dict,
    *,
    language: str,
    suffixes: list[str],
    supported_disposition: str,
) -> dict[str, dict]:
    if payload.get("schema_version") != 1:
        raise ValueError(f"{language} coverage schema must be 1")
    if payload.get("suffixes") != suffixes:
        raise ValueError(f"{language} coverage must declare {suffixes}")
    allowed = set(payload.get("allowed_dispositions", []))
    if "pending-validation" not in allowed or supported_disposition not in allowed:
        raise ValueError(f"{language} coverage dispositions are incomplete")
    rows = payload.get("skills")
    if not isinstance(rows, list):
        raise ValueError(f"{language} coverage skills must be a list")
    by_name: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("skill"), str):
            raise ValueError(f"{language} coverage rows need skill names")
        skill = row["skill"]
        if not skill or skill in by_name:
            raise ValueError(f"{language} coverage skill names must be unique")
        if row.get("disposition") not in allowed:
            raise ValueError(f"invalid {language} disposition for {skill}")
        disposition = row["disposition"]
        evidence_fields = ("evidence_path", "native_check", "reviewed_revision")
        if disposition == "pending-validation":
            if any(row.get(field) is not None for field in evidence_fields):
                raise ValueError(f"pending {language} row has premature evidence: {skill}")
        else:
            evidence_path = row.get("evidence_path")
            native_check = row.get("native_check")
            if (
                not isinstance(evidence_path, str)
                or not (REPO_ROOT / evidence_path).is_file()
                or not isinstance(native_check, list)
                or not native_check
                or any(not isinstance(arg, str) or not arg for arg in native_check)
                or not isinstance(row.get("reviewed_revision"), str)
                or not row["reviewed_revision"]
            ):
                raise ValueError(f"non-pending {language} row lacks evidence: {skill}")
        if disposition.endswith("-unsupported"):
            if row.get("unsupported_basis") not in {
                "technical-impossibility",
                "conceptually-inapplicable",
            }:
                raise ValueError(
                    f"permanent {language} unsupported row lacks a valid basis: {skill}"
                )
            alternative = row.get("alternative_skill")
            if alternative is not None and (
                not isinstance(alternative, str) or not alternative.strip()
            ):
                raise ValueError(
                    f"permanent {language} unsupported row has an invalid alternative: "
                    f"{skill}"
                )
            job_absent = row.get("underlying_job_absent") is True
            if bool(alternative) == job_absent:
                raise ValueError(
                    f"permanent {language} unsupported row must name exactly one "
                    f"alternative or absent underlying job: {skill}"
                )
        if disposition.endswith("-unsupported") or disposition == "not-applicable":
            if not isinstance(row.get("independent_review"), str) or not row[
                "independent_review"
            ].strip():
                raise ValueError(
                    f"exceptional {language} disposition lacks independent review: {skill}"
                )
            if not isinstance(row.get("language_reference"), str) or not row[
                "language_reference"
            ].strip():
                raise ValueError(
                    f"exceptional {language} disposition lacks a language reference: "
                    f"{skill}"
                )
        if disposition == "not-applicable" and row.get("underlying_job_absent") is not True:
            raise ValueError(
                f"{language} not-applicable row must prove the underlying job absent: {skill}"
            )
        if disposition.endswith("-unsupported") and row.get("alternative_skill"):
            for field in ("alternative_evidence_path", "alternative_routing_test"):
                value = row.get(field)
                if not isinstance(value, str) or not (REPO_ROOT / value).is_file():
                    raise ValueError(
                        f"permanent {language} unsupported row lacks {field}: {skill}"
                    )
        by_name[skill] = row
    if set(by_name) != set(LANGUAGE_CLASSIFICATION):
        raise ValueError(f"{language} coverage must contain the 22 language-level skills")
    return by_name


def _go_coverage(payload: dict) -> dict[str, dict]:
    return _simple_language_coverage(
        payload,
        language="Go",
        suffixes=[".go"],
        supported_disposition="go-supported",
    )


def _java_coverage(payload: dict) -> dict[str, dict]:
    return _simple_language_coverage(
        payload,
        language="Java",
        suffixes=[".java"],
        supported_disposition="java-supported",
    )


def _php_coverage(payload: dict) -> dict[str, dict]:
    coverage = _simple_language_coverage(
        payload,
        language="PHP",
        suffixes=[".php"],
        supported_disposition="php-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "php-pending-implementation",
            "php-partial",
            "php-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded PHP row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("PHP coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload["decision_reason"]:
        raise ValueError("PHP coverage decision needs a reason")
    return coverage


def _swift_coverage(payload: dict) -> dict[str, dict]:
    coverage = _simple_language_coverage(
        payload,
        language="Swift",
        suffixes=[".swift"],
        supported_disposition="swift-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "swift-pending-implementation",
            "swift-partial",
            "swift-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded Swift row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("Swift coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload["decision_reason"]:
        raise ValueError("Swift coverage decision needs a reason")
    return coverage


def _c_coverage(payload: dict) -> dict[str, dict]:
    coverage = _simple_language_coverage(
        payload,
        language="C",
        suffixes=[".c", ".i"],
        supported_disposition="c-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "c-pending-implementation",
            "c-partial",
            "c-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded C row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("C coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload["decision_reason"]:
        raise ValueError("C coverage decision needs a reason")
    return coverage


def _cpp_coverage(payload: dict) -> dict[str, dict]:
    source_suffixes = [".cc", ".cpp", ".cxx", ".c++", ".C", ".ii"]
    declaration_suffixes = [".hpp", ".hh", ".hxx", ".h++", ".ipp", ".inl", ".tpp"]
    normalized = {
        **payload,
        "suffixes": [*source_suffixes, *declaration_suffixes],
    }
    if payload.get("source_suffixes") != source_suffixes:
        raise ValueError("C++ coverage source suffixes are incomplete")
    if payload.get("declaration_suffixes") != declaration_suffixes:
        raise ValueError("C++ coverage declaration suffixes are incomplete")
    coverage = _simple_language_coverage(
        normalized,
        language="C++",
        suffixes=[*source_suffixes, *declaration_suffixes],
        supported_disposition="cpp-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "cpp-pending-implementation",
            "cpp-partial",
            "cpp-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded C++ row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("C++ coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload[
        "decision_reason"
    ]:
        raise ValueError("C++ coverage decision needs a reason")
    return coverage


def _ruby_coverage(payload: dict) -> dict[str, dict]:
    if payload.get("source_suffixes") != [".rb"]:
        raise ValueError("Ruby coverage source suffixes are incomplete")
    coverage = _simple_language_coverage(
        {**payload, "suffixes": [".rb"]},
        language="Ruby",
        suffixes=[".rb"],
        supported_disposition="ruby-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "ruby-pending-implementation",
            "ruby-partial",
            "ruby-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded Ruby row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("Ruby coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload[
        "decision_reason"
    ]:
        raise ValueError("Ruby coverage decision needs a reason")
    return coverage


def _rust_coverage(payload: dict) -> dict[str, dict]:
    if payload.get("source_suffixes") != [".rs"]:
        raise ValueError("Rust coverage source suffixes are incomplete")
    coverage = _simple_language_coverage(
        {**payload, "suffixes": [".rs"]},
        language="Rust",
        suffixes=[".rs"],
        supported_disposition="rust-supported",
    )
    for skill, row in coverage.items():
        if row["disposition"] in {
            "rust-pending-implementation",
            "rust-partial",
            "rust-unsupported",
        } and not row.get("limitation"):
            raise ValueError(f"bounded Rust row lacks a limitation: {skill}")
    if payload.get("decision") not in {"expand", "stop-after-pilot"}:
        raise ValueError("Rust coverage must record an expand or stop-after-pilot decision")
    if not isinstance(payload.get("decision_reason"), str) or not payload[
        "decision_reason"
    ]:
        raise ValueError("Rust coverage decision needs a reason")
    return coverage


def build_matrix(
    catalog_path: Path,
    coverage_path: Path,
    javascript_coverage_path: Path,
    go_coverage_path: Path,
    java_coverage_path: Path,
    php_coverage_path: Path,
    swift_coverage_path: Path,
    c_coverage_path: Path,
    cpp_coverage_path: Path,
    ruby_coverage_path: Path,
    rust_coverage_path: Path,
) -> dict:
    catalog_payload = _read_json(catalog_path)
    coverage_payload = _read_json(coverage_path)
    javascript_payload = _read_json(javascript_coverage_path)
    go_payload = _read_json(go_coverage_path)
    java_payload = _read_json(java_coverage_path)
    php_payload = _read_json(php_coverage_path)
    swift_payload = _read_json(swift_coverage_path)
    c_payload = _read_json(c_coverage_path)
    cpp_payload = _read_json(cpp_coverage_path)
    ruby_payload = _read_json(ruby_coverage_path)
    rust_payload = _read_json(rust_coverage_path)
    catalog = {row["name"]: row for row in catalog_payload.get("skills", [])}
    coverage = {row["skill"]: row for row in coverage_payload.get("skills", [])}
    javascript_coverage = _javascript_coverage(javascript_payload)
    go_coverage = _go_coverage(go_payload)
    java_coverage = _java_coverage(java_payload)
    php_coverage = _php_coverage(php_payload)
    swift_coverage = _swift_coverage(swift_payload)
    c_coverage = _c_coverage(c_payload)
    cpp_coverage = _cpp_coverage(cpp_payload)
    ruby_coverage = _ruby_coverage(ruby_payload)
    rust_coverage = _rust_coverage(rust_payload)
    if not catalog or set(catalog) != set(coverage):
        raise ValueError("catalog and TypeScript coverage must contain the same skills")

    language_skills = {
        name
        for name, row in coverage.items()
        if row.get("disposition") == "typescript-supported"
    }
    if language_skills != set(LANGUAGE_CLASSIFICATION):
        missing = sorted(language_skills - set(LANGUAGE_CLASSIFICATION))
        stale = sorted(set(LANGUAGE_CLASSIFICATION) - language_skills)
        raise ValueError(f"language classification mismatch; missing={missing}, stale={stale}")
    if set(LANGUAGE_CLASSIFICATION) != set(LEARNING_PACKETS):
        raise ValueError("every language-level skill must declare learning packets")

    framework_skills = {
        name
        for name, row in coverage.items()
        if row.get("disposition") == "stack-bound"
    }
    classified_frameworks = set().union(*FRAMEWORK_FAMILIES.values())
    if framework_skills != classified_frameworks:
        missing = sorted(framework_skills - classified_frameworks)
        stale = sorted(classified_frameworks - framework_skills)
        raise ValueError(f"framework classification mismatch; missing={missing}, stale={stale}")

    rows = []
    for skill in sorted(catalog):
        metadata = catalog[skill]
        accepted = coverage[skill]
        companions = metadata.get("install_with", [])
        baseline = accepted["disposition"]
        try:
            expansion = DISPOSITION_MAP[baseline]
        except KeyError as exc:
            raise ValueError(f"unknown TypeScript disposition for {skill}: {baseline}") from exc

        if expansion == "language-level":
            fact_level, outcome_class = LANGUAGE_CLASSIFICATION[skill]
            learning_packets = _learning_paths(skill)
            framework_family = None
        elif expansion == "framework-bound":
            fact_level = "framework"
            outcome_class = "framework-specific"
            learning_packets = []
            framework_family = _framework_family(skill)
        elif expansion == "validated-neutral":
            fact_level = "neutral"
            outcome_class = "not-applicable"
            learning_packets = []
            framework_family = None
        else:
            fact_level = "ecosystem-runtime"
            outcome_class = "not-applicable"
            learning_packets = []
            framework_family = None

        if expansion == "language-level":
            javascript = javascript_coverage[skill]
            javascript_disposition = javascript["disposition"]
            javascript_cohort = javascript["cohort"]
            javascript_evidence_modes = javascript["evidence_modes"]
            javascript_evidence_path = javascript["evidence_path"]
            javascript_native_check = javascript["native_check"]
            javascript_reviewed_revision = javascript["reviewed_revision"]
            javascript_limitation = javascript.get("limitation")
        else:
            javascript_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            javascript_cohort = None
            javascript_evidence_modes = ["not-applicable"]
            javascript_evidence_path = None
            javascript_native_check = None
            javascript_reviewed_revision = None
            javascript_limitation = None

        if expansion == "language-level":
            go = go_coverage[skill]
            go_disposition = go["disposition"]
            go_evidence_path = go.get("evidence_path")
            go_native_check = go.get("native_check")
            go_reviewed_revision = go.get("reviewed_revision")
        else:
            go_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            go_evidence_path = None
            go_native_check = None
            go_reviewed_revision = None

        if expansion == "language-level":
            java = java_coverage[skill]
            java_disposition = java["disposition"]
            java_evidence_path = java.get("evidence_path")
            java_native_check = java.get("native_check")
            java_reviewed_revision = java.get("reviewed_revision")
        else:
            java_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            java_evidence_path = None
            java_native_check = None
            java_reviewed_revision = None

        if expansion == "language-level":
            php = php_coverage[skill]
            php_disposition = php["disposition"]
            php_evidence_path = php.get("evidence_path")
            php_native_check = php.get("native_check")
            php_reviewed_revision = php.get("reviewed_revision")
            php_limitation = php.get("limitation")
        else:
            php_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            php_evidence_path = None
            php_native_check = None
            php_reviewed_revision = None
            php_limitation = None

        if expansion == "language-level":
            swift = swift_coverage[skill]
            swift_disposition = swift["disposition"]
            swift_evidence_path = swift.get("evidence_path")
            swift_native_check = swift.get("native_check")
            swift_reviewed_revision = swift.get("reviewed_revision")
            swift_limitation = swift.get("limitation")
        else:
            swift_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            swift_evidence_path = None
            swift_native_check = None
            swift_reviewed_revision = None
            swift_limitation = None

        if expansion == "language-level":
            c = c_coverage[skill]
            c_disposition = c["disposition"]
            c_evidence_path = c.get("evidence_path")
            c_native_check = c.get("native_check")
            c_reviewed_revision = c.get("reviewed_revision")
            c_limitation = c.get("limitation")
        else:
            c_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            c_evidence_path = None
            c_native_check = None
            c_reviewed_revision = None
            c_limitation = None

        if expansion == "language-level":
            cpp = cpp_coverage[skill]
            cpp_disposition = cpp["disposition"]
            cpp_evidence_path = cpp.get("evidence_path")
            cpp_native_check = cpp.get("native_check")
            cpp_reviewed_revision = cpp.get("reviewed_revision")
            cpp_limitation = cpp.get("limitation")
        else:
            cpp_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            cpp_evidence_path = None
            cpp_native_check = None
            cpp_reviewed_revision = None
            cpp_limitation = None

        if expansion == "language-level":
            ruby = ruby_coverage[skill]
            ruby_disposition = ruby["disposition"]
            ruby_evidence_path = ruby.get("evidence_path")
            ruby_native_check = ruby.get("native_check")
            ruby_reviewed_revision = ruby.get("reviewed_revision")
            ruby_limitation = ruby.get("limitation")
        else:
            ruby_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            ruby_evidence_path = None
            ruby_native_check = None
            ruby_reviewed_revision = None
            ruby_limitation = None

        if expansion == "language-level":
            rust = rust_coverage[skill]
            rust_disposition = rust["disposition"]
            rust_evidence_path = rust.get("evidence_path")
            rust_native_check = rust.get("native_check")
            rust_reviewed_revision = rust.get("reviewed_revision")
            rust_limitation = rust.get("limitation")
        else:
            rust_disposition = {
                "validated-neutral": "validated-neutral",
                "framework-bound": "stack-bound",
                "ecosystem-runtime": "ecosystem-runtime",
            }[expansion]
            rust_evidence_path = None
            rust_native_check = None
            rust_reviewed_revision = None
            rust_limitation = None

        rows.append(
            {
                "skill": skill,
                "expansion_disposition": expansion,
                "typescript_disposition": baseline,
                "javascript_disposition": javascript_disposition,
                "javascript_cohort": javascript_cohort,
                "javascript_evidence_modes": javascript_evidence_modes,
                "javascript_evidence_path": javascript_evidence_path,
                "javascript_native_check": javascript_native_check,
                "javascript_reviewed_revision": javascript_reviewed_revision,
                "javascript_limitation": javascript_limitation,
                "go_disposition": go_disposition,
                "go_evidence_path": go_evidence_path,
                "go_native_check": go_native_check,
                "go_reviewed_revision": go_reviewed_revision,
                "java_disposition": java_disposition,
                "java_evidence_path": java_evidence_path,
                "java_native_check": java_native_check,
                "java_reviewed_revision": java_reviewed_revision,
                "php_disposition": php_disposition,
                "php_evidence_path": php_evidence_path,
                "php_native_check": php_native_check,
                "php_reviewed_revision": php_reviewed_revision,
                "php_limitation": php_limitation,
                "swift_disposition": swift_disposition,
                "swift_evidence_path": swift_evidence_path,
                "swift_native_check": swift_native_check,
                "swift_reviewed_revision": swift_reviewed_revision,
                "swift_limitation": swift_limitation,
                "c_disposition": c_disposition,
                "c_evidence_path": c_evidence_path,
                "c_native_check": c_native_check,
                "c_reviewed_revision": c_reviewed_revision,
                "c_limitation": c_limitation,
                "cpp_disposition": cpp_disposition,
                "cpp_evidence_path": cpp_evidence_path,
                "cpp_native_check": cpp_native_check,
                "cpp_reviewed_revision": cpp_reviewed_revision,
                "cpp_limitation": cpp_limitation,
                "ruby_disposition": ruby_disposition,
                "ruby_evidence_path": ruby_evidence_path,
                "ruby_native_check": ruby_native_check,
                "ruby_reviewed_revision": ruby_reviewed_revision,
                "ruby_limitation": ruby_limitation,
                "rust_disposition": rust_disposition,
                "rust_evidence_path": rust_evidence_path,
                "rust_native_check": rust_native_check,
                "rust_reviewed_revision": rust_reviewed_revision,
                "rust_limitation": rust_limitation,
                "fact_level": fact_level,
                "outcome_class": outcome_class,
                "framework_family": framework_family,
                "catalog": {
                    "job": metadata.get("job"),
                    "language": metadata.get("language", "any"),
                    "framework": metadata.get("framework", "any"),
                    "scans": metadata.get("scans", []),
                    "install_with": companions,
                },
                "on_demand_closure": _on_demand_closure(skill, companions),
                "optional_install": {
                    "role": "secondary-explicit-user-choice",
                    "status": accepted["install_status"],
                    "command": accepted["install_command"],
                    "evidence_basis": "historical-stock-selected-install",
                },
                "typescript_evidence_path": accepted["evidence_path"],
                "typescript_reviewed_revision": accepted["reviewed_revision"],
                "learning_packets": learning_packets,
            }
        )

    counts = Counter(row["expansion_disposition"] for row in rows)
    for primitive in SHARED_PRIMITIVES:
        unknown = sorted(set(primitive["consumers"]) - language_skills)
        if unknown:
            raise ValueError(
                f"shared primitive {primitive['primitive']} has unknown consumers: {unknown}"
            )
        if len(set(primitive["consumers"])) < 2:
            raise ValueError(
                f"shared primitive {primitive['primitive']} needs two consumers"
            )
    return {
        "schema_version": 5,
        "sources": [
            {"path": _relative(catalog_path), "sha256": _sha256(catalog_path)},
            {"path": _relative(coverage_path), "sha256": _sha256(coverage_path)},
            {
                "path": _relative(javascript_coverage_path),
                "sha256": _sha256(javascript_coverage_path),
            },
            {"path": _relative(go_coverage_path), "sha256": _sha256(go_coverage_path)},
            {"path": _relative(java_coverage_path), "sha256": _sha256(java_coverage_path)},
            {"path": _relative(php_coverage_path), "sha256": _sha256(php_coverage_path)},
            {"path": _relative(swift_coverage_path), "sha256": _sha256(swift_coverage_path)},
            {"path": _relative(c_coverage_path), "sha256": _sha256(c_coverage_path)},
            {
                "path": _relative(cpp_coverage_path),
                "sha256": _sha256(cpp_coverage_path),
            },
            {
                "path": _relative(ruby_coverage_path),
                "sha256": _sha256(ruby_coverage_path),
            },
            {
                "path": _relative(rust_coverage_path),
                "sha256": _sha256(rust_coverage_path),
            },
        ],
        "counts": {
            "validated-neutral": counts["validated-neutral"],
            "ecosystem-runtime": counts["ecosystem-runtime"],
            "language-level": counts["language-level"],
            "framework-bound": counts["framework-bound"],
        },
        "typescript_shared_primitives": SHARED_PRIMITIVES,
        "skills": rows,
    }


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--typescript-coverage", type=Path, default=DEFAULT_TYPESCRIPT_COVERAGE
    )
    parser.add_argument(
        "--javascript-coverage", type=Path, default=DEFAULT_JAVASCRIPT_COVERAGE
    )
    parser.add_argument("--go-coverage", type=Path, default=DEFAULT_GO_COVERAGE)
    parser.add_argument("--java-coverage", type=Path, default=DEFAULT_JAVA_COVERAGE)
    parser.add_argument("--php-coverage", type=Path, default=DEFAULT_PHP_COVERAGE)
    parser.add_argument("--swift-coverage", type=Path, default=DEFAULT_SWIFT_COVERAGE)
    parser.add_argument("--c-coverage", type=Path, default=DEFAULT_C_COVERAGE)
    parser.add_argument("--cpp-coverage", type=Path, default=DEFAULT_CPP_COVERAGE)
    parser.add_argument("--ruby-coverage", type=Path, default=DEFAULT_RUBY_COVERAGE)
    parser.add_argument("--rust-coverage", type=Path, default=DEFAULT_RUST_COVERAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="Exit nonzero when the matrix is stale"
    )
    mode.add_argument(
        "--write", action="store_true", help="Write the generated matrix atomically"
    )
    args = parser.parse_args(argv)
    try:
        rendered = render(
            build_matrix(
                args.catalog,
                args.typescript_coverage,
                args.javascript_coverage,
                args.go_coverage,
                args.java_coverage,
                args.php_coverage,
                args.swift_coverage,
                args.c_coverage,
                args.cpp_coverage,
                args.ruby_coverage,
                args.rust_coverage,
            )
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.output}: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print(f"error: stale multi-language matrix: {args.output}", file=sys.stderr)
            return 1
        print(f"multi-language matrix current: {len(json.loads(rendered)['skills'])} skills")
        return 0

    if args.write:
        write_atomic(args.output, rendered)
        print(f"wrote multi-language matrix: {args.output}")
        return 0

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
