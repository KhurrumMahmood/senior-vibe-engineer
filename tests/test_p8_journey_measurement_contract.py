"""Freeze the P8 routing corpus and measurement contract before optimization."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/p8-router-quality/corpus.json"
PROTOCOL = ROOT / ".claude/tasks/p8-journey-measurement-protocol.json"
EVIDENCE = ROOT / ".claude/tasks/p8-performance-measurement-evidence.json"
REQUIRED_CATEGORIES = {
    "clear",
    "ambiguous",
    "negated-misleading",
    "direct-no-skill",
    "unsupported-language-or-stack",
    "different-scope",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_router_corpus_is_content_addressed_complete_and_prechange() -> None:
    corpus = _load(CORPUS)
    assert corpus["schema_version"] == 1
    assert len(corpus["frozen_revision"]) == 40
    assert subprocess.run(
        ["git", "cat-file", "-e", f"{corpus['frozen_revision']}^{{commit}}"],
        cwd=ROOT,
        check=False,
    ).returncode == 0

    source = ROOT / corpus["source"]["path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == corpus["source"]["sha256"]
    source_cases = _load(source)
    observed_categories: set[str] = set()
    for router in ("which_shape", "which_skill", "which_cleanup"):
        case_ids = {row["id"] for row in source_cases[router]}
        categories = corpus["case_categories"][router]
        assert set(categories) == case_ids
        observed_categories.update(categories.values())
        command_key = router.replace("_", "-")
        assert command_key in corpus["commands"][command_key]
    assert observed_categories == REQUIRED_CATEGORIES
    assert set(corpus["rubrics"]) == {"shape-route", "skill-route", "cleanup-route"}
    assert all(len(rows) == 4 for rows in corpus["rubrics"].values())
    assert corpus["hard_gates"]["clear_route_accuracy_percent"] == 100
    assert corpus["hard_gates"]["heavy_false_positives_on_direct_tasks"] == 0


def test_measurement_protocol_is_fixed_honest_and_measure_only() -> None:
    protocol = _load(PROTOCOL)
    corpus = _load(CORPUS)
    assert protocol["schema_version"] == 2
    assert protocol["status"] == "revised-after-preflight-no-new-model-calls"
    assert protocol["frozen_revision"] == corpus["frozen_revision"]
    assert ROOT / protocol["router_corpus"] == CORPUS
    assert protocol["trial_policy"]["paired_trials"] >= 5
    assert set(protocol["workflows"]) == {
        "historical_full_serial",
        "historical_compressed_serial",
        "historical_compressed_parallel",
        "product_launcher_serial",
        "product_launcher_parallel",
    }
    assert set(protocol["comparisons"]) == {
        "compression_only",
        "batching_only",
        "actual_product_batching",
    }

    hashed_files = {
        "historical_harness": ROOT / "scripts/benchmark_code_health_family.py",
        "product_launcher_harness": ROOT
        / "scripts/benchmark_product_code_health_launcher.py",
        "product_launcher": ROOT
        / ".claude/skill-families/code-health-readonly/scripts/run.py",
        "router_corpus_manifest": CORPUS,
        "historical_results": ROOT / ".claude/tasks/ml020-code-health-results.json",
    }
    for name, path in hashed_files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == protocol[
            "execution_contract"
        ]["hashes"][name]

    required_metrics = {
        "correctness",
        "completion",
        "true_root_wall_time_ms",
        "observable_model_tokens",
        "controlled_context_utf8_bytes",
        "repeated_context_utf8_bytes",
        "scanner_invocations",
        "native_tool_invocations",
        "human_interventions",
        "recoverable_failures",
        "cache_state",
    }
    assert set(protocol["metrics"]) == required_metrics
    for metric in protocol["metrics"].values():
        assert metric["observation"]
        assert metric["missing_value"] in {"fail", "unavailable"}
    assert "(occurrences - 1) * blob_utf8_bytes" in protocol["metrics"][
        "repeated_context_utf8_bytes"
    ]["observation"]
    assert "trial_id" in protocol["trial_record_schema"]["required"]
    assert "Do not build a coordinator" in protocol["decision"]
    assert protocol["p9_adoption_threshold"]["minimum_paired_trials"] >= 5


def test_performance_evidence_separates_compression_from_product_batching() -> None:
    evidence = _load(EVIDENCE)
    assert evidence["status"] == "passed"
    historical = evidence["historical_model_eval"]
    assert historical["compression_A_to_B"][
        "controlled_context_reduction_percent"
    ] >= 30
    assert historical["batching_B_to_C"][
        "median_modeled_wall_reduction_percent"
    ] >= 20
    assert historical["limitations"]["true_root_wall_time_ms"].startswith(
        "unavailable"
    )

    product = evidence["actual_product_launcher"]
    assert product["paired_trials"] >= 5
    assert product["parallel_improvement_percent"] >= 20
    assert product["all_semantically_equal"] is True
    assert product["all_source_preserved"] is True
    assert product["native_tool_invocations"].startswith("unavailable")
    assert evidence["decision"]["new_coordinator"] == "not justified"
