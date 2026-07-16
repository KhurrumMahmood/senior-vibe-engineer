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
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from _lib.lang_adapter import FACT_CAPABILITIES, AnalysisResult, TypeScriptAdapter


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "tests" / "fixtures" / "analysis_portfolio_spike"
FACT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis_facts"
EXTERNAL_CORPUS = FACT_FIXTURES / "external-corpus.json"
PLATFORM_CONTRACT = FACT_FIXTURES / "platform-contract.json"
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


def _hash_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_hex_digest(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _hash_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _load_external_corpus() -> dict[str, Any]:
    provenance = _load_json_mapping(EXTERNAL_CORPUS, "external corpus provenance")
    required = {
        "schema_version",
        "project",
        "upstream_repository",
        "upstream_tag",
        "upstream_revision",
        "upstream_path",
        "upstream_raw_sha256",
        "local_path",
        "source_sha256",
        "normalization",
        "license",
        "license_path",
        "license_sha256",
        "license_normalization",
        "input_bytes",
        "input_lines",
        "selection_rationale",
        "retrieved_on",
    }
    if set(provenance) != required or provenance.get("schema_version") != 1:
        raise ValueError("external corpus provenance has an invalid schema")
    for field in ("upstream_revision", "upstream_raw_sha256", "source_sha256", "license_sha256"):
        length = 40 if field == "upstream_revision" else 64
        if not _is_hex_digest(provenance.get(field), length):
            raise ValueError(f"external corpus {field} is not a valid digest")
    if provenance.get("normalization") != ["CRLF line endings converted to LF"]:
        raise ValueError("external corpus normalization contract is invalid")
    if provenance.get("license_normalization") != ["Trailing whitespace removed"]:
        raise ValueError("external corpus license normalization contract is invalid")
    fixture = FACT_FIXTURES / str(provenance["local_path"])
    license_path = FACT_FIXTURES / str(provenance["license_path"])
    if not fixture.is_file() or not license_path.is_file():
        raise ValueError("external corpus source or license is missing")
    source_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    license_hash = hashlib.sha256(license_path.read_bytes()).hexdigest()
    source_lines = len(fixture.read_text(encoding="utf-8").splitlines())
    if source_hash != provenance.get("source_sha256"):
        raise ValueError("external corpus source hash does not match provenance")
    if license_hash != provenance.get("license_sha256"):
        raise ValueError("external corpus license hash does not match provenance")
    if fixture.stat().st_size != provenance.get("input_bytes") or source_lines != provenance.get("input_lines"):
        raise ValueError("external corpus size does not match provenance")
    if provenance.get("license") != "Apache-2.0" or not str(provenance.get("selection_rationale", "")).strip():
        raise ValueError("external corpus requires a supported license and selection rationale")
    return provenance


def _load_platform_contract() -> dict[str, Any]:
    contract = _load_json_mapping(PLATFORM_CONTRACT, "platform contract")
    if set(contract) != {
        "schema_version",
        "required_platforms",
        "required_tool_versions",
        "excluded_platforms",
    } or contract.get("schema_version") != 1:
        raise ValueError("platform contract has an invalid schema")
    required = contract.get("required_platforms")
    if not isinstance(required, list) or not required:
        raise ValueError("platform contract requires executed platforms")
    if any(not isinstance(row, dict) or set(row) != {"platform_key", "system", "machine"} for row in required):
        raise ValueError("platform contract required-platform rows are invalid")
    keys = [row["platform_key"] for row in required]
    if len(keys) != len(required) or keys != sorted(set(keys)):
        raise ValueError("platform contract keys must be unique and sorted")
    if any(row["platform_key"] != f"{row['system']}-{row['machine']}" for row in required):
        raise ValueError("platform contract keys must derive from system and machine")
    tools = contract.get("required_tool_versions")
    if not isinstance(tools, dict) or set(tools) != {
        "python_series",
        "tree_sitter",
        "tree_sitter_language_pack",
    } or any(not isinstance(value, str) or not value for value in tools.values()):
        raise ValueError("platform contract tool versions are invalid")
    excluded = contract.get("excluded_platforms")
    if not isinstance(excluded, list) or any(
        not isinstance(row, dict)
        or set(row) != {"system", "reason"}
        or not isinstance(row["system"], str)
        or not isinstance(row["reason"], str)
        or not row["reason"].strip()
        for row in excluded
    ):
        raise ValueError("platform contract exclusions are invalid")
    return contract


def _platform_execution() -> dict[str, str]:
    system = platform.system()
    machine = platform.machine()
    return {
        "platform_key": f"{system}-{machine}",
        "system": system,
        "machine": machine,
        "python": platform.python_version(),
        "python_series": ".".join(platform.python_version_tuple()[:2]),
        "tree_sitter": importlib.metadata.version("tree-sitter"),
        "tree_sitter_language_pack": importlib.metadata.version("tree-sitter-language-pack"),
    }


def _source_revision(explicit: str | None = None) -> str:
    if explicit:
        if not _is_hex_digest(explicit, 40):
            raise ValueError("source revision must be a 40-character Git SHA")
        return explicit.lower()
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().lower()
    return revision if completed.returncode == 0 and len(revision) == 40 else "unavailable"


def _source_tree_hash() -> str:
    digest = hashlib.sha256()
    roots = [REPO_ROOT / "scripts" / "_lib" / "lang_adapter", FACT_FIXTURES]
    files = [
        REPO_ROOT / "scripts" / "analysis_fact_benchmark.py",
        REPO_ROOT / "requirements.txt",
        *(
            path
            for root in roots
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ),
    ]
    for path in sorted(files):
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
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


def _cold_probe(paths: list[Path]) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--cold-probe", *(str(path) for path in paths)],
        check=True,
        capture_output=True,
        text=True,
        timeout=BUDGETS["maximum_cold_seconds"] + 5.0,
    )
    elapsed = time.perf_counter() - started
    payload = json.loads(completed.stdout)
    return {
        "seconds": elapsed,
        "digest": payload["digest"],
        "peak_rss_bytes": payload["peak_rss_bytes"],
    }


def _benchmark(paths: list[Path]) -> dict[str, Any]:
    durations: list[float] = []
    digests: list[str] = []
    cold = _cold_probe(paths)
    tracemalloc.start()
    for _ in range(RUNS - 1):
        started = time.perf_counter()
        _, digest = _analyze(paths)
        durations.append(time.perf_counter() - started)
        digests.append(digest)
    _, peak_python = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    warm_mean = statistics.mean(durations)
    warm_stdev = statistics.pstdev(durations)
    return {
        "runs": RUNS,
        "cold_seconds": round(cold["seconds"], 6),
        "warm_mean_seconds": round(warm_mean, 6),
        "warm_stdev_seconds": round(warm_stdev, 6),
        "warm_cv": round(warm_stdev / warm_mean if warm_mean else 0.0, 6),
        "peak_python_bytes": peak_python,
        "peak_rss_bytes": max(_rss_bytes(), int(cold["peak_rss_bytes"])),
        "deterministic": len({cold["digest"], *digests}) == 1,
        "facts_sha256": cold["digest"],
        "input_sha256": _hash_paths(paths),
        "input_bytes": sum(path.stat().st_size for path in paths),
        "input_files": len(paths),
        "input_lines": sum(len(path.read_text(encoding="utf-8").splitlines()) for path in paths),
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


def _stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report["schema_version"],
        "analysis_interface_version": report["analysis_interface_version"],
        "corpus_sha256": report["corpus_sha256"],
        "metrics": report["metrics"],
        "fixtures": {
            name: {
                field: result[field]
                for field in (
                    "deterministic",
                    "facts_sha256",
                    "input_sha256",
                    "input_bytes",
                    "input_files",
                    "input_lines",
                )
            }
            for name, result in report["fixtures"].items()
        },
        "budgets": report["budgets"],
        "tool_versions": {
            key: report["platform_execution"][key]
            for key in ("python_series", "tree_sitter", "tree_sitter_language_pack")
        },
        "external_corpus": {
            key: report["external_corpus"][key]
            for key in (
                "upstream_revision",
                "upstream_path",
                "source_sha256",
                "license",
                "license_sha256",
                "input_bytes",
                "input_lines",
                "selection_rationale",
            )
        },
        "platform_contract_sha256": report["platform_contract_sha256"],
    }


def compare_platform_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate required platform executions and deterministic stable outputs."""
    contract = _load_platform_contract()
    contract_hash = _hash_json(contract)
    required_rows = {
        row["platform_key"]: row for row in contract["required_platforms"]
    }
    executions: dict[str, dict[str, Any]] = {}
    revisions: set[str] = set()
    source_hashes: set[str] = set()
    stable_hashes: set[str] = set()
    required_tools = contract["required_tool_versions"]
    current_source_hash = _source_tree_hash()
    for report in reports:
        if report.get("schema_version") != 2 or report.get("passed") is not True:
            raise ValueError("platform report must be schema v2 and budget-passing")
        if report.get("violations") != []:
            raise ValueError("platform report contains benchmark violations")
        if report.get("platform_contract") != contract:
            raise ValueError("platform report embeds a different platform contract")
        if report.get("platform_contract_sha256") != contract_hash:
            raise ValueError("platform report does not match the platform contract")
        execution = report.get("platform_execution")
        if not isinstance(execution, dict):
            raise ValueError("platform report is missing execution identity")
        key = execution.get("platform_key")
        expected = required_rows.get(key)
        if expected is None:
            raise ValueError(f"unexpected platform execution: {key!r}")
        if key in executions:
            raise ValueError(f"duplicate platform execution: {key}")
        if any(execution.get(field) != expected[field] for field in ("system", "machine")):
            raise ValueError(f"platform execution identity does not match contract: {key}")
        for tool, version in required_tools.items():
            if execution.get(tool) != version:
                raise ValueError(f"{key}: {tool} must be {version}")
        revision = report.get("source_revision")
        if not _is_hex_digest(revision, 40):
            raise ValueError(f"{key}: exact source revision is missing")
        source_hash = report.get("source_tree_sha256")
        if not _is_hex_digest(source_hash, 64) or source_hash != current_source_hash:
            raise ValueError(f"{key}: source tree hash is missing or stale")
        stable_hash = report.get("stable_result_sha256")
        if not _is_hex_digest(stable_hash, 64) or stable_hash != _hash_json(_stable_projection(report)):
            raise ValueError(f"{key}: stable result hash is invalid")
        revisions.add(revision)
        source_hashes.add(source_hash)
        stable_hashes.add(stable_hash)
        executions[key] = {
            "report_sha256": _hash_json(report),
            "source_revision": revision,
            "source_tree_sha256": report.get("source_tree_sha256"),
            "stable_result_sha256": report.get("stable_result_sha256"),
            "python": execution.get("python"),
            "tree_sitter": execution.get("tree_sitter"),
            "tree_sitter_language_pack": execution.get("tree_sitter_language_pack"),
            "passed": True,
        }
    missing = sorted(set(required_rows) - set(executions))
    if missing:
        raise ValueError(f"missing required platform executions: {missing}")
    if len(revisions) != 1:
        raise ValueError("platform reports use different source revisions")
    if len(source_hashes) != 1:
        raise ValueError("platform reports use different source trees")
    if len(stable_hashes) != 1:
        raise ValueError("stable result hashes differ across platforms")
    return {
        "schema_version": 1,
        "source_revision": next(iter(revisions)),
        "source_tree_sha256": next(iter(source_hashes)),
        "stable_result_sha256": next(iter(stable_hashes)),
        "platform_contract_sha256": contract_hash,
        "required_platforms": sorted(required_rows),
        "executions": {key: executions[key] for key in sorted(executions)},
        "cross_platform_deterministic": True,
        "passed": True,
    }


# spec:portable-analysis-substrate::IM-9
def build_report(*, source_revision: str | None = None) -> dict[str, Any]:
    corpus_paths = sorted((CORPUS / "src").glob("*.ts"))
    corpus_results, _ = _analyze(corpus_paths)
    actual: dict[str, set[str]] = {name: set() for name in CAPABILITY_TO_ORACLE.values()}
    for result in corpus_results:
        for capability, family in CAPABILITY_TO_ORACLE.items():
            actual[family].update(fact.name for fact in result.for_capability(capability))
    oracle = json.loads((CORPUS / "oracle.json").read_text(encoding="utf-8"))["facts"]
    metrics = {family: _score(set(oracle[family]), values) for family, values in actual.items()}
    external = _load_external_corpus()
    platform_contract = _load_platform_contract()
    fixtures = {
        "small": _benchmark([FACT_FIXTURES / "typescript-small.tsx"]),
        "external_large": _benchmark([FACT_FIXTURES / external["local_path"]]),
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
    report = {
        "schema_version": 2,
        "analysis_interface_version": 1,
        "source_revision": _source_revision(source_revision),
        "source_tree_sha256": _source_tree_hash(),
        "corpus": str(CORPUS.relative_to(REPO_ROOT)),
        "corpus_sha256": _hash_tree(CORPUS),
        "external_corpus": external,
        "metrics": metrics,
        "fixtures": fixtures,
        "budgets": BUDGETS,
        "platform_contract": platform_contract,
        "platform_contract_sha256": _hash_json(platform_contract),
        "platform_execution": _platform_execution(),
        "toolchain": {
            "python": platform.python_version(),
            "tree_sitter": importlib.metadata.version("tree-sitter"),
            "tree_sitter_language_pack": importlib.metadata.version("tree-sitter-language-pack"),
            "tree_sitter_license": "MIT",
            "install_size_bytes": install_size,
            "deterministic_setup": (
                ".venv/bin/python -m pip install tree-sitter==0.26.0 "
                "tree-sitter-language-pack==1.12.5"
            ),
        },
        "fixture_rationale": {
            "small": "18-line TSX component with imports, exports, class/method, nested scope, JSX, call, reference, and write facts",
            "external_large": external["selection_rationale"],
        },
        "variance_method": "fresh subprocess cold (startup and provider load included); six same-process warm runs; population CV",
        "violations": violations,
        "passed": not violations,
    }
    report["stable_result_sha256"] = _hash_json(_stable_projection(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cold-probe", type=Path, nargs="+")
    parser.add_argument("--source-revision")
    parser.add_argument("--compare-platform-reports", type=Path, nargs="+")
    args = parser.parse_args(argv)
    if args.cold_probe:
        _, digest = _analyze(args.cold_probe)
        print(json.dumps({"digest": digest, "peak_rss_bytes": _rss_bytes()}))
        return 0
    if args.output is None:
        parser.error("--output is required unless --cold-probe is used")
    if args.compare_platform_reports:
        report = compare_platform_reports(
            [_load_json_mapping(path, "platform report") for path in args.compare_platform_reports]
        )
    else:
        report = build_report(source_revision=args.source_revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "violations": report.get("violations", [])}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
