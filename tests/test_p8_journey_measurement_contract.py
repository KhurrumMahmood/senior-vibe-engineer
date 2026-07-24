"""Freeze the P8 routing corpus and measurement contract before optimization."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/p8-router-quality/corpus.json"
PROTOCOL = ROOT / ".claude/tasks/p8-journey-measurement-protocol.json"
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
    assert protocol["status"] == "frozen-before-router-changes"
    assert protocol["frozen_revision"] == corpus["frozen_revision"]
    assert ROOT / protocol["router_corpus"] == CORPUS
    assert protocol["trial_policy"]["paired_trials"] >= 5
    assert set(protocol["workflows"]) == {"serial", "existing_batched"}
    assert Path(protocol["fixed_inputs"]["benchmark_script"]).as_posix() == "scripts/benchmark_code_health_family.py"

    required_metrics = {
        "correctness",
        "completion",
        "wall_time_ms",
        "observable_model_tokens",
        "controlled_context_utf8_bytes",
        "repeated_context_utf8_bytes",
        "native_tool_invocations",
        "human_interventions",
        "recoverable_failures",
    }
    assert set(protocol["metrics"]) == required_metrics
    for metric in protocol["metrics"].values():
        assert metric["observation"]
        assert metric["missing_value"] in {"fail", "unavailable"}
    assert "measure-only" in protocol["decision"]
    assert protocol["p9_adoption_threshold"]["minimum_paired_trials"] >= 5
