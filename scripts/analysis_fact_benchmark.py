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
from collections.abc import Callable
from typing import Any

from _lib.lang_adapter import FACT_CAPABILITIES, AnalysisResult, TypeScriptAdapter


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "tests" / "fixtures" / "analysis_portfolio_spike"
FACT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis_facts"
EXTERNAL_CORPUS = FACT_FIXTURES / "external-corpus.json"
PLATFORM_CONTRACT = FACT_FIXTURES / "platform-contract.json"
SOURCE_SCOPE = (
    "scripts/analysis_fact_benchmark.py",
    "requirements.txt",
    "scripts/_lib/lang_adapter",
    "tests/fixtures/analysis_facts",
    "tests/fixtures/analysis_portfolio_spike",
)
EXTERNAL_CORPUS_RELATIVE = "tests/fixtures/analysis_facts"
CORPUS_RELATIVE = "tests/fixtures/analysis_portfolio_spike"
EXPECTED_EXTERNAL_PROVENANCE = {
    "project": "microsoft/TypeScript",
    "upstream_repository": "https://github.com/microsoft/TypeScript",
    "upstream_tag": "v5.9.3",
    "upstream_revision": "c63de15a992d37f0d6cec03ac7631872838602cb",
    "upstream_path": "src/compiler/symbolWalker.ts",
    "upstream_raw_sha256": "6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a",
    "local_path": "external/typescript-symbol-walker-v5.9.3.ts",
    "normalization": ["CRLF line endings converted to LF"],
    "license": "Apache-2.0",
    "license_path": "external/LICENSE-TypeScript.txt",
    "license_upstream_raw_sha256": "a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47",
    "license_normalization": [
        "CRLF line endings converted to LF",
        "Trailing whitespace removed",
    ],
}
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


def _validate_external_corpus(
    provenance: dict[str, Any],
    *,
    read_relative_bytes: Callable[[str], bytes],
) -> dict[str, Any]:
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
        "license_upstream_raw_sha256",
        "license_sha256",
        "license_normalization",
        "input_bytes",
        "input_lines",
        "selection_rationale",
        "retrieved_on",
    }
    if set(provenance) != required or provenance.get("schema_version") != 1:
        raise ValueError("external corpus provenance has an invalid schema")
    for field in ("source_sha256", "license_sha256"):
        length = 64
        if not _is_hex_digest(provenance.get(field), length):
            raise ValueError(f"external corpus {field} is not a valid digest")
    for field, expected in EXPECTED_EXTERNAL_PROVENANCE.items():
        if provenance.get(field) != expected:
            raise ValueError(f"external corpus {field} differs from the pinned provenance")
    local_path = Path(str(provenance["local_path"]))
    license_relative = Path(str(provenance["license_path"]))
    if (
        local_path.is_absolute()
        or license_relative.is_absolute()
        or ".." in local_path.parts
        or ".." in license_relative.parts
    ):
        raise ValueError("external corpus paths must remain inside the fixture root")
    try:
        source_bytes = read_relative_bytes(local_path.as_posix())
        license_bytes = read_relative_bytes(license_relative.as_posix())
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"external corpus source or license is unreadable: {exc}") from exc
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    license_hash = hashlib.sha256(license_bytes).hexdigest()
    source_lines = len(source_text.splitlines())
    if source_hash != provenance.get("source_sha256"):
        raise ValueError("external corpus source hash does not match provenance")
    if license_hash != provenance.get("license_sha256"):
        raise ValueError("external corpus license hash does not match provenance")
    if len(source_bytes) != provenance.get("input_bytes") or source_lines != provenance.get("input_lines"):
        raise ValueError("external corpus size does not match provenance")
    if provenance.get("license") != "Apache-2.0" or not str(provenance.get("selection_rationale", "")).strip():
        raise ValueError("external corpus requires a supported license and selection rationale")
    return provenance


def _load_external_corpus() -> dict[str, Any]:
    provenance = _load_json_mapping(EXTERNAL_CORPUS, "external corpus provenance")
    return _validate_external_corpus(
        provenance,
        read_relative_bytes=lambda relative: (FACT_FIXTURES / relative).read_bytes(),
    )


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
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().lower()
    if completed.returncode != 0 or not _is_hex_digest(revision, 40):
        raise ValueError("benchmark evidence requires a Git checkout")
    if explicit is None:
        return revision
    if not _is_hex_digest(explicit, 40):
        raise ValueError("source revision must be a 40-character Git SHA")
    if explicit.lower() != revision:
        raise ValueError("source revision must equal the checked-out Git commit")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_SCOPE],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0 or status.stdout.strip():
        raise ValueError("benchmark evidence requires a clean relevant source tree")
    return revision


def _included_source_file(path: Path) -> bool:
    return path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"


def _working_source_files() -> list[Path]:
    files: set[Path] = set()
    for relative in SOURCE_SCOPE:
        target = REPO_ROOT / relative
        if target.is_file():
            files.add(target)
        elif target.is_dir():
            files.update(path for path in target.rglob("*") if _included_source_file(path))
        else:
            raise ValueError(f"benchmark source scope path is missing: {relative}")
    return sorted(files, key=lambda item: item.relative_to(REPO_ROOT).as_posix())


def _source_tree_hash() -> str:
    digest = hashlib.sha256()
    for path in _working_source_files():
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _verified_revision(revision: str) -> str:
    if not _is_hex_digest(revision, 40):
        raise ValueError("source revision must be a 40-character Git SHA")
    verified = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if verified.returncode != 0 or verified.stdout.strip().lower() != revision.lower():
        raise ValueError("source revision is not a repository commit")
    return revision.lower()


def _git_paths_at_revision(revision: str, scopes: tuple[str, ...]) -> list[str]:
    _verified_revision(revision)
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", *scopes],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        raise ValueError("cannot enumerate source revision")
    names = sorted(
        name
        for name in listing.stdout.splitlines()
        if "__pycache__" not in Path(name).parts and Path(name).suffix != ".pyc"
    )
    if not names:
        raise ValueError("source revision has no benchmark source files")
    return names


def _git_blob_at_revision(revision: str, name: str) -> bytes:
    blob = subprocess.run(
        ["git", "cat-file", "blob", f"{revision}:{name}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if blob.returncode != 0:
        raise ValueError(f"cannot read source revision path: {name}")
    return blob.stdout


def _source_tree_hash_at_revision(revision: str) -> str:
    names = _git_paths_at_revision(revision, SOURCE_SCOPE)
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_git_blob_at_revision(revision, name))
        digest.update(b"\0")
    return digest.hexdigest()


def _tree_hash_at_revision(revision: str, root: str) -> str:
    names = _git_paths_at_revision(revision, (root,))
    prefix = Path(root)
    digest = hashlib.sha256()
    for name in names:
        relative = Path(name).relative_to(prefix).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_git_blob_at_revision(revision, name))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_external_corpus_at_revision(revision: str) -> dict[str, Any]:
    manifest_path = f"{EXTERNAL_CORPUS_RELATIVE}/external-corpus.json"
    try:
        provenance = json.loads(_git_blob_at_revision(revision, manifest_path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"committed external corpus provenance is invalid: {exc}") from exc
    if not isinstance(provenance, dict):
        raise ValueError("committed external corpus provenance must be a JSON object")
    return _validate_external_corpus(
        provenance,
        read_relative_bytes=lambda relative: _git_blob_at_revision(
            revision, f"{EXTERNAL_CORPUS_RELATIVE}/{relative}"
        ),
    )


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


def _budget_violations(
    metrics: dict[str, Any],
    fixtures: dict[str, Any],
    install_size: int,
) -> list[str]:
    if set(metrics) != set(CAPABILITY_TO_ORACLE.values()):
        raise ValueError("benchmark metrics do not match the required fact families")
    if set(fixtures) != {"small", "external_large"}:
        raise ValueError("benchmark fixtures do not match the required corpus")
    if not isinstance(install_size, int) or isinstance(install_size, bool) or install_size < 0:
        raise ValueError("benchmark install size is invalid")
    violations: list[str] = []
    for family, score in metrics.items():
        if not isinstance(score, dict):
            raise ValueError(f"{family}: metric result is invalid")
        for field, budget in (
            ("precision", "minimum_precision"),
            ("recall", "minimum_recall"),
        ):
            value = score.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{family}: {field} is invalid")
            if value < BUDGETS[budget]:
                violations.append(f"{family}: {field} budget missed")
    for name, result in fixtures.items():
        if not isinstance(result, dict) or result.get("runs") != RUNS:
            raise ValueError(f"{name}: benchmark result or run count is invalid")
        if result.get("deterministic") is not True:
            violations.append(f"{name}: non-deterministic facts")
        for field, budget in (
            ("cold_seconds", "maximum_cold_seconds"),
            ("warm_mean_seconds", "maximum_warm_seconds"),
            ("peak_rss_bytes", "maximum_peak_rss_bytes"),
            ("peak_python_bytes", "maximum_peak_python_bytes"),
            ("warm_cv", "maximum_warm_cv"),
        ):
            value = result.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name}: {field} is invalid")
            if value > BUDGETS[budget]:
                violations.append(f"{name}: {field}={value} exceeds {BUDGETS[budget]}")
    if install_size > BUDGETS["maximum_install_bytes"]:
        violations.append("tree-sitter install-size budget missed")
    return violations


def _validate_report_budgets(report: dict[str, Any], platform_key: str) -> None:
    if report.get("budgets") != BUDGETS:
        raise ValueError(f"{platform_key}: benchmark budgets differ from the contract")
    toolchain = report.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError(f"{platform_key}: toolchain record is invalid")
    metrics = report.get("metrics")
    fixtures = report.get("fixtures")
    if not isinstance(metrics, dict) or not isinstance(fixtures, dict):
        raise ValueError(f"{platform_key}: benchmark results are invalid")
    computed = _budget_violations(metrics, fixtures, toolchain.get("install_size_bytes"))
    if report.get("violations") != computed:
        raise ValueError(f"{platform_key}: reported violations do not match benchmark values")
    if report.get("passed") is not (not computed):
        raise ValueError(f"{platform_key}: reported pass state does not match benchmark values")
    if computed:
        raise ValueError(f"{platform_key}: benchmark budgets failed: {computed}")


def _stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report["schema_version"],
        "analysis_interface_version": report["analysis_interface_version"],
        "corpus": report["corpus"],
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
        "external_corpus": report["external_corpus"],
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
    revision_inputs: dict[str, tuple[str, dict[str, Any]]] = {}
    required_tools = contract["required_tool_versions"]
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
        _validate_report_budgets(report, str(key))
        if any(execution.get(field) != expected[field] for field in ("system", "machine")):
            raise ValueError(f"platform execution identity does not match contract: {key}")
        for tool, version in required_tools.items():
            if execution.get(tool) != version:
                raise ValueError(f"{key}: {tool} must be {version}")
        revision = report.get("source_revision")
        if not _is_hex_digest(revision, 40):
            raise ValueError(f"{key}: exact source revision is missing")
        source_hash = report.get("source_tree_sha256")
        if not _is_hex_digest(source_hash, 64) or source_hash != _source_tree_hash_at_revision(revision):
            raise ValueError(f"{key}: source tree hash is missing or stale")
        if revision not in revision_inputs:
            revision_inputs[revision] = (
                _tree_hash_at_revision(revision, CORPUS_RELATIVE),
                _load_external_corpus_at_revision(revision),
            )
        expected_corpus_hash, expected_external = revision_inputs[revision]
        if report.get("corpus") != CORPUS_RELATIVE:
            raise ValueError(f"{key}: benchmark corpus path differs from the contract")
        if report.get("corpus_sha256") != expected_corpus_hash:
            raise ValueError(f"{key}: benchmark corpus hash is not bound to the source revision")
        if report.get("external_corpus") != expected_external:
            raise ValueError(f"{key}: external corpus provenance is not bound to the source revision")
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
    revision = _source_revision(source_revision)
    working_source_hash = _source_tree_hash()
    if source_revision is not None and working_source_hash != _source_tree_hash_at_revision(revision):
        raise ValueError("benchmark source tree differs from the declared Git revision")
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
    violations = _budget_violations(metrics, fixtures, install_size)
    report = {
        "schema_version": 2,
        "analysis_interface_version": 1,
        "source_revision": revision,
        "source_tree_sha256": working_source_hash,
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
    if source_revision is not None and _source_tree_hash() != working_source_hash:
        raise ValueError("benchmark source tree changed during report generation")
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
