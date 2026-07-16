#!/usr/bin/env python3
"""Benchmark the productized WP4 fact provider against the pinned D3 oracle."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import resource
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from _lib.lang_adapter import FACT_CAPABILITIES, AnalysisResult, TypeScriptAdapter


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "tests" / "fixtures" / "analysis_portfolio_spike"
FACT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis_facts"
RUNS = 7
BUDGETS = {
    "maximum_cold_seconds": 1.0,
    "maximum_warm_seconds": 1.0,
    "maximum_peak_rss_bytes": 128 * 1024 * 1024,
    "maximum_peak_python_bytes": 64 * 1024 * 1024,
    "maximum_warm_cv": 0.20,
    "maximum_install_bytes": 25_000_000,
    "minimum_precision": 1.0,
    "minimum_recall": 1.0,
}
CAPABILITY_TO_ORACLE = {
    "analysis.definitions": "definitions",
    "analysis.imports": "imports",
    "analysis.references": "references",
    "analysis.calls": "calls",
    "analysis.writes": "writes",
}


def _hash_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _install_size() -> int:
    paths: set[Path] = set()
    for name in ("tree-sitter", "tree-sitter-language-pack"):
        distribution = importlib.metadata.distribution(name)
        for file in distribution.files or ():
            path = Path(distribution.locate_file(file))
            if path.is_file():
                paths.add(path.resolve())
    return sum(path.stat().st_size for path in paths)


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def _analyze(paths: list[Path]) -> tuple[list[AnalysisResult], str]:
    adapter = TypeScriptAdapter()
    results = [
        adapter.analyze(path.read_text(encoding="utf-8"), path=path.name, capabilities=FACT_CAPABILITIES)
        for path in paths
    ]
    encoded = json.dumps(
        [result.to_dict() for result in results],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return results, hashlib.sha256(encoded).hexdigest()


def _benchmark(paths: list[Path]) -> dict[str, Any]:
    durations: list[float] = []
    digests: list[str] = []
    tracemalloc.start()
    for _ in range(RUNS):
        started = time.perf_counter()
        _, digest = _analyze(paths)
        durations.append(time.perf_counter() - started)
        digests.append(digest)
    _, peak_python = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    warm = durations[1:]
    warm_mean = statistics.mean(warm)
    warm_stdev = statistics.pstdev(warm)
    return {
        "runs": RUNS,
        "cold_seconds": round(durations[0], 6),
        "warm_mean_seconds": round(warm_mean, 6),
        "warm_stdev_seconds": round(warm_stdev, 6),
        "warm_cv": round(warm_stdev / warm_mean if warm_mean else 0.0, 6),
        "peak_python_bytes": peak_python,
        "peak_rss_bytes": _rss_bytes(),
        "deterministic": len(set(digests)) == 1,
        "facts_sha256": digests[0],
        "input_bytes": sum(path.stat().st_size for path in paths),
    }


def _score(expected: set[str], actual: set[str]) -> dict[str, Any]:
    intersection = expected & actual
    precision = len(intersection) / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = len(intersection) / len(expected) if expected else 1.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "false_positive": sorted(actual - expected),
        "false_negative": sorted(expected - actual),
    }


# spec:portable-analysis-substrate::IM-9
def build_report() -> dict[str, Any]:
    corpus_paths = sorted((CORPUS / "src").glob("*.ts"))
    corpus_results, _ = _analyze(corpus_paths)
    actual: dict[str, set[str]] = {name: set() for name in CAPABILITY_TO_ORACLE.values()}
    for result in corpus_results:
        for capability, family in CAPABILITY_TO_ORACLE.items():
            actual[family].update(fact.name for fact in result.for_capability(capability))
    oracle = json.loads((CORPUS / "oracle.json").read_text(encoding="utf-8"))["facts"]
    metrics = {family: _score(set(oracle[family]), values) for family, values in actual.items()}
    fixtures = {
        "small": _benchmark([FACT_FIXTURES / "typescript-small.tsx"]),
        "large": _benchmark([FACT_FIXTURES / "typescript-large.ts"]),
    }
    install_size = _install_size()
    violations: list[str] = []
    for family, score in metrics.items():
        if score["precision"] < BUDGETS["minimum_precision"]:
            violations.append(f"{family}: precision budget missed")
        if score["recall"] < BUDGETS["minimum_recall"]:
            violations.append(f"{family}: recall budget missed")
    for name, result in fixtures.items():
        if not result["deterministic"]:
            violations.append(f"{name}: non-deterministic facts")
        for field, budget in (
            ("cold_seconds", "maximum_cold_seconds"),
            ("warm_mean_seconds", "maximum_warm_seconds"),
            ("peak_rss_bytes", "maximum_peak_rss_bytes"),
            ("peak_python_bytes", "maximum_peak_python_bytes"),
            ("warm_cv", "maximum_warm_cv"),
        ):
            if result[field] > BUDGETS[budget]:
                violations.append(f"{name}: {field}={result[field]} exceeds {BUDGETS[budget]}")
    if install_size > BUDGETS["maximum_install_bytes"]:
        violations.append("tree-sitter install-size budget missed")
    return {
        "schema_version": 1,
        "analysis_interface_version": 1,
        "corpus": str(CORPUS.relative_to(REPO_ROOT)),
        "corpus_sha256": _hash_tree(CORPUS),
        "metrics": metrics,
        "fixtures": fixtures,
        "budgets": BUDGETS,
        "toolchain": {
            "python": platform.python_version(),
            "platform": f"{platform.system()}-{platform.machine()}",
            "tree_sitter": importlib.metadata.version("tree-sitter"),
            "tree_sitter_language_pack": importlib.metadata.version("tree-sitter-language-pack"),
            "tree_sitter_license": "MIT",
            "install_size_bytes": install_size,
            "deterministic_setup": (
                ".venv/bin/python -m pip install tree-sitter==0.26.0 "
                "tree-sitter-language-pack==1.12.5"
            ),
        },
        "variance_method": "first run is cold; six same-process warm runs; population CV",
        "violations": violations,
        "passed": not violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "violations": report["violations"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
