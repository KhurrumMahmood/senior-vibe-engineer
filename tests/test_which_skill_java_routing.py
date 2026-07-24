"""Java contract-routing regressions for the metadata-only skill matcher."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
MATCHER = REPO_ROOT / ".claude/skills/which-skill/scripts/match.py"


JAVA_CLEAR_CASES = (
    (
        "J01",
        "adapt-project",
        "Onboard an unfamiliar Java repository: inventory its stack, build/test commands, "
        "CI, source roots, docs, domain vocabulary, and existing guardrails, then write an "
        "adapter facts report without guessing team priorities.",
    ),
    (
        "J02",
        "audit-decisions",
        "Audit the Java repository's ADR registry before release: flag stale or orphaned "
        "decision links in Java comments and Markdown, and write a read-only registry-drift "
        "report.",
    ),
    (
        "J03",
        "explain-code",
        "Create an annotated behavior document for the direct public classes and methods of "
        "this Java package, including preconditions, invariants, callers, and unexplained "
        "regions; do not refactor.",
    ),
    (
        "J04",
        "extract-enum",
        "A Java 17 audit has already confirmed one String status field with repeated literals. "
        "Produce only a reviewed enum migration and caller-impact proposal for that finding; "
        "do not edit source.",
    ),
    (
        "J05",
        "find-comment-drift",
        "Audit Java comments and Javadoc for stale terminology, detached banners, and thin "
        "public class documentation after AI-heavy development; report only.",
    ),
    (
        "J06",
        "find-complexity-hotspots",
        "Audit syntactic branch complexity in Java methods and constructors, with exact source "
        "spans and no runtime profiling.",
    ),
    (
        "J07",
        "find-concept-divergence",
        "Scan Java source and docs against our canonical glossary for forbidden terms, "
        "coexisting competing terms, and deprecated/replacement names in the same file; do "
        "not rename anything.",
    ),
    (
        "J08",
        "find-dormant",
        "Review Java private methods with zero compiler-resolved source uses as possible "
        "dormant code; do not claim deletion is safe.",
    ),
    (
        "J09",
        "find-duplication",
        "Find exact normalized Java method-body clone candidates for human review, not "
        "behavioral equivalence or a consolidation.",
    ),
    (
        "J10",
        "find-folder-topology-drift",
        "Inspect this Java source root for direct sibling filenames sharing a leading "
        "CamelCase domain token, such as BillingParser, BillingValidator, and BillingTypes; "
        "report topology drift, not a move plan.",
    ),
    (
        "J11",
        "find-implicit-state",
        "Detect repeated bare String status and phase comparisons or assignments in Java 17 "
        "code, distinguishing enum authorities from unsafe reference equality; report "
        "candidates only.",
    ),
    (
        "J12",
        "find-incomplete-sweep",
        "Review a Java 17 multi-file change for options-record constructor calls where a new "
        "option was passed at some callers but a git-older sibling still uses the old shape; "
        "report stragglers only.",
    ),
    (
        "J13",
        "find-omnibus",
        "Find Java modules that mix three or more unrelated responsibilities and rank "
        "decomposition candidates; do not split any files.",
    ),
    (
        "J14",
        "find-semantic-duplication",
        "Find Java live functions that plausibly implement the same behavior with different "
        "code shapes, using compiler-resolved return and direct-call evidence, but do not "
        "claim they are safe to merge.",
    ),
    (
        "J15",
        "find-standard-gaps",
        "Given our host-owned standards JSON, scan Java 17 code for direct calls that should "
        "be inside a try guard but are not; report coverage gaps only.",
    ),
    (
        "J16",
        "map-subsystem",
        "Produce a durable inventory document for this Java package: file list, exported "
        "public surface, dependency/import graph, responsibility table, and "
        "convention-compliance score; no refactor plan.",
    ),
    (
        "J17",
        "move-path",
        "Move src/main/java/com/acme/legacy/billing to "
        "src/main/java/com/acme/billingcore, dry-run package, import, and fully qualified name "
        "updates, then verify with javac; this is a path move, not a terminology rename.",
    ),
    (
        "J18",
        "prevent-regression",
        "A confirmed Java string-state cleanup cluster has just been closed. Propose a "
        "permanent diff-scoped guardrail or focused regression test so repeated bare status "
        "literals cannot return; do not modify production code.",
    ),
    (
        "J19",
        "propose-boundary",
        "For a Java package that has distinct domain concerns but no stable public boundary, "
        "produce a read-only extraction proposal with candidate seams, API, compatibility, "
        "caller impact, and native verification; do not refactor.",
    ),
    (
        "J20",
        "propose-folder-reorganization",
        "A confirmed Java folder-topology finding needs a read-only reorganization proposal: "
        "current/proposed tree, package-move table, import impact, compatibility, and test "
        "plan; do not move files.",
    ),
    (
        "J21",
        "rename-concept",
        "Assess a glossary-backed Java domain concept rename across identifiers, docs, agent "
        "mirrors, and the two-band completeness gate; report lifecycle status only and do not "
        "execute a codemod.",
    ),
    (
        "J22",
        "unify-shadows",
        "Given one accepted Java semantic-duplication finding, produce a read-only "
        "consolidation proposal with source and caller impact, tests, stop condition, and "
        "human approval; do not merge code.",
    ),
)


def _run_match(prompt: str, *extra: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(MATCHER), prompt, "--json", "--top", "22", *extra],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def test_java_clear_case_matrix_has_one_contract_per_skill():
    expected = [skill for _case_id, skill, _prompt in JAVA_CLEAR_CASES]

    assert len(JAVA_CLEAR_CASES) == 22
    assert len(set(expected)) == 22


@pytest.mark.parametrize(
    ("case_id", "expected_skill", "prompt"),
    JAVA_CLEAR_CASES,
    ids=[case_id for case_id, _skill, _prompt in JAVA_CLEAR_CASES],
)
def test_java_clear_case_routes_to_its_distinct_contract(
    case_id: str,
    expected_skill: str,
    prompt: str,
    tmp_path: Path,
):
    del case_id
    returncode, payload = _run_match(prompt, "--project-root", str(tmp_path))

    assert returncode == 0, payload
    assert payload["routing_context"]["languages"] == ["java"]
    assert payload["recommendation"] == expected_skill
    assert payload["handoff"]["skills"][0] == expected_skill
    assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"


@pytest.mark.parametrize(
    ("prompt", "expected_candidates"),
    (
        (
            "Audit the Java service for either dormant private methods or duplicated method "
            "bodies and tell us what to fix.",
            {"find-dormant", "find-duplication"},
        ),
        (
            "The Java package feels tangled; should we map it, find an omnibus, propose a "
            "boundary, or refactor it?",
            {"map-subsystem", "find-omnibus", "propose-boundary"},
        ),
    ),
)
def test_java_ambiguous_prompt_keeps_named_contracts_in_ranked_candidates(
    prompt: str,
    expected_candidates: set[str],
    tmp_path: Path,
):
    returncode, payload = _run_match(prompt, "--project-root", str(tmp_path))

    assert returncode == 0, payload
    candidates = {
        candidate["name"]: candidate["score"] for candidate in payload["candidates"]
    }
    assert expected_candidates <= candidates.keys()
    assert all(candidates[name] >= 5 for name in expected_candidates)


def test_java_one_line_typo_still_proceeds_directly(tmp_path: Path):
    returncode, payload = _run_match(
        "Fix a one-line typo in a Java exception message.",
        "--project-root",
        str(tmp_path),
    )

    assert returncode == 1
    assert payload["recommendation"] == "proceed_directly"
    assert "handoff" not in payload


@pytest.mark.parametrize("skill", ["adapt-project", "propose-folder-reorganization"])
def test_promoted_java_capability_returns_on_demand_handoff(skill: str, tmp_path: Path):
    returncode, payload = _run_match(
        f"Use {skill} on this Java repository.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0, payload
    assert payload["recommendation"] == skill
    assert payload["handoff"]["skills"][0] == skill
    assert payload["handoff"]["default_execution"] == "fresh_non_context_subagent"
    capability = payload["handoff"]["capabilities"]["skills"][0]
    assert capability["skill"] == skill
    assert capability["java_disposition"] == "java-supported"


def test_promoted_rust_scanner_routes_exact_skill(tmp_path: Path):
    returncode, payload = _run_match(
        "Find exact normalized Rust function-body clone candidates.",
        "--project-root",
        str(tmp_path),
        "--library-root",
        str(REPO_ROOT),
    )

    assert returncode == 0, payload
    assert payload["routing_context"]["languages"] == ["rust"]
    assert payload["recommendation"] == "find-duplication"
    capability = payload["handoff"]["capabilities"]["skills"][0]
    assert capability["skill"] == "find-duplication"
    assert capability["rust_disposition"] == "rust-supported"
