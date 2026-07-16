#!/usr/bin/env python3
"""Run the pinned D3 analysis portfolio spike and emit machine evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "tests" / "fixtures" / "analysis_portfolio_spike"
SYNTAX_FAMILIES = ("definitions", "imports", "calls", "writes")


def _tree_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _hash_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _score(expected: list[str], actual: list[str]) -> dict[str, Any]:
    expected_set, actual_set = set(expected), set(actual)
    true_positive = len(expected_set & actual_set)
    precision = true_positive / len(actual_set) if actual_set else (1.0 if not expected_set else 0.0)
    recall = true_positive / len(expected_set) if expected_set else 1.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "false_positive": sorted(actual_set - expected_set),
        "false_negative": sorted(expected_set - actual_set),
    }


def _run_json(command: list[str], *, env: dict[str, str] | None = None) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}"
        )
    return json.loads(result.stdout), elapsed


def _candidate(
    *,
    name: str,
    command: list[str],
    oracle: dict[str, list[str]],
    supported_families: tuple[str, ...],
    install_root: Path,
    version: str,
    license_name: str,
    platform_claim: list[str],
    deterministic_setup: str,
    owner: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    first, cold = _run_json(command, env=env)
    second, warm = _run_json(command, env=env)
    if first != second:
        raise RuntimeError(f"{name} emitted non-deterministic facts")
    metrics = {family: _score(oracle[family], first.get(family, [])) for family in supported_families}
    unsupported = sorted(set(oracle) - set(supported_families))
    return {
        "status": "executed",
        "version": version,
        "license": license_name,
        "supported_platforms": platform_claim,
        "executed_platform": f"{platform.system().lower()}-{platform.machine().lower()}",
        "deterministic_setup": deterministic_setup,
        "maintenance_owner": owner,
        "install_size_bytes": _tree_size(install_root),
        "cold_runtime_seconds": round(cold, 6),
        "warm_runtime_seconds": round(warm, 6),
        "facts": first,
        "metrics": metrics,
        "unsupported_capabilities": unsupported,
    }


def run_spike(args: argparse.Namespace) -> dict[str, Any]:
    corpus = args.corpus.resolve()
    oracle_payload = json.loads((corpus / "oracle.json").read_text(encoding="utf-8"))
    oracle = oracle_payload["facts"]
    python_site = args.python_site.resolve()
    node_modules = args.node_modules.resolve()
    ast_grep = node_modules / ".bin" / "ast-grep"
    typescript_api = node_modules / "typescript-api"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(python_site)
    installed = {
        (distribution.metadata.get("Name") or "").lower(): distribution
        for distribution in importlib.metadata.distributions(path=[str(python_site)])
    }
    tree_version = installed["tree-sitter"].version
    pack_distribution = installed["tree-sitter-language-pack"]

    candidates = {
        "tree-sitter-language-pack": _candidate(
            name="tree-sitter-language-pack",
            command=[
                str(Path(sys.executable)),
                str(REPO_ROOT / "scripts" / "spikes" / "tree_sitter_probe.py"),
                str(corpus),
            ],
            env=env,
            oracle=oracle,
            supported_families=SYNTAX_FAMILIES,
            install_root=python_site,
            version=f"tree-sitter {tree_version}; language-pack {pack_distribution.version}",
            license_name=pack_distribution.metadata.get("License-Expression") or pack_distribution.metadata.get("License") or "not-declared-in-wheel-metadata",
            platform_claim=["macos-arm64 wheel executed", "other published wheels require CI verification"],
            deterministic_setup=(
                ".venv/bin/python -m pip install --target <temp>/python "
                "tree-sitter==0.26.0 tree-sitter-language-pack==1.12.5"
            ),
            owner="analysis-substrate maintainer",
        ),
        "ast-grep": _candidate(
            name="ast-grep",
            command=[
                str(Path(sys.executable)),
                str(REPO_ROOT / "scripts" / "spikes" / "ast_grep_probe.py"),
                str(ast_grep),
                str(corpus),
            ],
            oracle=oracle,
            supported_families=SYNTAX_FAMILIES,
            install_root=node_modules / "@ast-grep",
            version="0.44.1",
            license_name="MIT",
            platform_claim=["npm optional native binaries; macos-arm64 executed", "other package targets require CI verification"],
            deterministic_setup="npm install --prefix <temp>/node @ast-grep/cli@0.44.1",
            owner="refactor-query maintainer",
        ),
        "typescript-compiler-api": _candidate(
            name="typescript-compiler-api",
            command=[
                "node",
                str(REPO_ROOT / "scripts" / "spikes" / "typescript_compiler_probe.cjs"),
                str(typescript_api),
                str(corpus),
            ],
            oracle=oracle,
            supported_families=tuple(oracle),
            install_root=typescript_api,
            version="5.9.3",
            license_name="Apache-2.0",
            platform_claim=["Node.js >=14.17; macos-arm64 executed", "platform-neutral JavaScript package"],
            deterministic_setup="npm install --prefix <temp>/node typescript-api@npm:typescript@5.9.3",
            owner="typescript binding maintainer",
        ),
        "scip-index": {
            "status": "unsupported",
            "reason": "No pinned SCIP indexer is installed; adding an index protocol and indexer fleet is disproportionate before a cross-file consumer exists.",
            "license": "candidate-specific; not evaluated",
            "supported_platforms": [],
            "maintenance_owner": "unassigned until a semantic-index consumer is accepted",
        },
        "lsp": {
            "status": "unsupported",
            "reason": "No pinned TypeScript LSP is installed; lifecycle/state synchronization adds a service boundary without a WP4 consumer.",
            "license": "candidate-specific; not evaluated",
            "supported_platforms": [],
            "maintenance_owner": "unassigned until an interactive semantic consumer is accepted",
        },
        "typescript-7-native-compiler-api": {
            "status": "unsupported",
            "version": "7.0.2",
            "reason": "The current package exports the native compiler and unstable APIs, not the stable 5.x Compiler API used by the semantic probe; tsc remains viable as a native guard shim.",
            "license": "Apache-2.0",
            "supported_platforms": ["native packages declared for major desktop/server OS and CPU combinations; macos-arm64 tsc executed"],
            "maintenance_owner": "typescript binding maintainer",
        },
    }

    budgets = {
        "tree-sitter-language-pack": {
            "minimum_precision": 1.0,
            "minimum_recall": 1.0,
            "maximum_warm_seconds": 1.0,
            "maximum_install_bytes": 25_000_000,
        },
        "typescript-compiler-api": {
            "minimum_precision": 1.0,
            "minimum_recall": 1.0,
            "maximum_warm_seconds": 1.0,
            "maximum_install_bytes": 30_000_000,
        },
        "ast-grep-optional": {
            "minimum_precision": 1.0,
            "minimum_recall": 1.0,
            "maximum_warm_seconds": 6.0,
            "maximum_install_bytes": 200_000_000,
        },
    }
    return {
        "schema_version": 1,
        "corpus": str(corpus.relative_to(REPO_ROOT)),
        "corpus_sha256": _hash_tree(corpus),
        "oracle_schema_version": oracle_payload["schema_version"],
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        },
        "time_box": "one implementation slice; no persistent dependency added",
        "selected_portfolio": {
            "syntax": "tree-sitter-language-pack",
            "semantic": "project-pinned native compiler API when a named consumer requires it",
            "query_and_rewrite": "ast-grep as an optional on-demand tool, not a mandatory runtime dependency",
            "native_guards": "project-native compiler/linter/test commands",
            "deferred": ["SCIP", "LSP service lifecycle"],
        },
        "wp4_acceptance_budgets": budgets,
        "candidates": candidates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-site", type=Path, required=True)
    parser.add_argument("--node-modules", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_spike(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
