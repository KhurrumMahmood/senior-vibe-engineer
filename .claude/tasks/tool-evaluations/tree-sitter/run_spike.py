#!/usr/bin/env python3
"""Prefetch and offline-replay a pinned tree-sitter language-pack slice."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path

from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import (
    PackConfig,
    cache_dir,
    configure,
    downloaded_languages,
    get_language,
    get_parser,
    prefetch,
)


REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "local"
CACHE = LOCAL / "tree-sitter-1.13.2-cache"
PREFETCH_STATE = LOCAL / "tree-sitter-prefetch-state.json"
OFFLINE_STATE = LOCAL / "tree-sitter-offline-state.json"
RESULT = HERE.parent / "tree-sitter-results.json"
LANGUAGES = ("java", "csharp", "php")

QUERY_SPECS = {
    "java": {
        "declarations": """
            (method_declaration name: (identifier) @name) @declaration
            (constructor_declaration name: (identifier) @name) @declaration
        """,
        "imports": "(import_declaration) @item",
        "calls": "(method_invocation name: (identifier) @name) @call",
    },
    "csharp": {
        "declarations": """
            (method_declaration name: (identifier) @name) @declaration
            (constructor_declaration name: (identifier) @name) @declaration
        """,
        "imports": "(using_directive) @item",
        "calls": "(invocation_expression function: (identifier) @name) @call",
    },
    "php": {
        "declarations": """
            (method_declaration name: (name) @name) @declaration
            (function_definition name: (name) @name) @declaration
        """,
        "imports": "(namespace_use_declaration) @item",
        "calls": "(function_call_expression function: (name) @name) @call",
    },
}


def tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def span(node) -> dict:
    return {
        "start": {"line": node.start_point.row + 1, "column": node.start_point.column},
        "end": {"line": node.end_point.row + 1, "column": node.end_point.column},
        "bytes": {"start": node.start_byte, "end": node.end_byte},
    }


def text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def captures(language: str, root, source: bytes, query_source: str) -> list[dict]:
    query = Query(get_language(language), query_source)
    result = QueryCursor(query).captures(root)
    rows = []
    for capture_name, nodes in sorted(result.items()):
        for node in nodes:
            rows.append({
                "capture": capture_name,
                "node_type": node.type,
                "text": text(node, source),
                "span": span(node),
            })
    return sorted(
        rows,
        key=lambda row: (
            row["capture"],
            row["span"]["bytes"]["start"],
            row["span"]["bytes"]["end"],
            row["node_type"],
        ),
    )


def parse_problems(root, source: bytes) -> list[dict]:
    problems = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            problems.append({
                "node_type": node.type,
                "is_error": node.is_error,
                "is_missing": node.is_missing,
                "text": text(node, source),
                "span": span(node),
            })
        stack.extend(reversed(node.children))
    return problems


def analyze_fixture(language: str, path: Path) -> dict:
    source = path.read_bytes()
    started = time.perf_counter()
    tree = get_parser(language).parse(source)
    parse_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "path": path.relative_to(REPO).as_posix(),
        "sha256": hashlib.sha256(source).hexdigest(),
        "parse_ms": parse_ms,
        "root_type": tree.root_node.type,
        "has_error": tree.root_node.has_error,
        "parse_problems": parse_problems(tree.root_node, source),
        "facts": {
            family: captures(language, tree.root_node, source, query)
            for family, query in QUERY_SPECS[language].items()
        },
    }


def analyze_all() -> dict:
    result = {}
    for language in LANGUAGES:
        root = HERE / "fixtures" / language
        valid = next(path for path in root.iterdir() if path.stem == "Sample")
        broken = next(path for path in root.iterdir() if path.stem == "Broken")
        result[language] = {
            "valid": analyze_fixture(language, valid),
            "malformed": analyze_fixture(language, broken),
            "query_node_types": {
                family: sorted({
                    row["node_type"]
                    for row in analyze_fixture(language, valid)["facts"][family]
                })
                for family in QUERY_SPECS[language]
            },
        }
    return result


def package_bytes(distribution_name: str) -> int:
    distribution = importlib.metadata.distribution(distribution_name)
    total = 0
    for entry in distribution.files or []:
        path = distribution.locate_file(entry)
        if path.is_file():
            total += path.stat().st_size
    return total


def summarize_analysis(analysis: dict) -> dict:
    return {
        language: {
            fixture: {
                "path": analysis[language][fixture]["path"],
                "sha256": analysis[language][fixture]["sha256"],
                "root_type": analysis[language][fixture]["root_type"],
                "has_error": analysis[language][fixture]["has_error"],
                "parse_problem_count": len(
                    analysis[language][fixture]["parse_problems"]
                ),
                "fact_counts": {
                    family: len(rows)
                    for family, rows in analysis[language][fixture]["facts"].items()
                },
            }
            for fixture in ("valid", "malformed")
        }
        for language in LANGUAGES
    }


def prefetch_phase() -> int:
    LOCAL.mkdir(parents=True, exist_ok=True)
    configure(PackConfig(cache_dir=str(CACHE)))
    started = time.perf_counter()
    prefetch(list(LANGUAGES))
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    payload = {
        "schema_version": 1,
        "phase": "prefetch",
        "package_version": importlib.metadata.version("tree-sitter-language-pack"),
        "tree_sitter_version": importlib.metadata.version("tree-sitter"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cache_dir": cache_dir(),
        "requested_languages": list(LANGUAGES),
        "downloaded_languages": downloaded_languages(),
        "prefetch_ms": elapsed,
        "grammar_cache_bytes": tree_size(CACHE),
        "installed_package_bytes": package_bytes("tree-sitter-language-pack"),
        "installed_tree_sitter_bytes": package_bytes("tree-sitter"),
        "environment_bytes": tree_size(Path(sys.prefix)),
        "online_analysis": analyze_all(),
    }
    PREFETCH_STATE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "phase": "prefetch",
        "state": str(PREFETCH_STATE.relative_to(REPO)),
        "prefetch_ms": elapsed,
        "grammar_cache_bytes": payload["grammar_cache_bytes"],
        "downloaded_languages": payload["downloaded_languages"],
    }, indent=2))
    return 0


def offline_phase() -> int:
    prefetch_state = json.loads(PREFETCH_STATE.read_text(encoding="utf-8"))
    configure(PackConfig(cache_dir=str(CACHE)))
    started = time.perf_counter()
    offline_analysis = analyze_all()
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    online_analysis = prefetch_state["online_analysis"]
    stable = {
        language: {
            fixture: {
                "same_root_type": offline_analysis[language][fixture]["root_type"]
                == online_analysis[language][fixture]["root_type"],
                "same_has_error": offline_analysis[language][fixture]["has_error"]
                == online_analysis[language][fixture]["has_error"],
                "same_facts": offline_analysis[language][fixture]["facts"]
                == online_analysis[language][fixture]["facts"],
                "same_parse_problems": offline_analysis[language][fixture]["parse_problems"]
                == online_analysis[language][fixture]["parse_problems"],
            }
            for fixture in ("valid", "malformed")
        }
        for language in LANGUAGES
    }
    all_valid = all(
        not offline_analysis[language]["valid"]["has_error"]
        and bool(offline_analysis[language]["valid"]["facts"]["declarations"])
        and bool(offline_analysis[language]["valid"]["facts"]["imports"])
        and bool(offline_analysis[language]["valid"]["facts"]["calls"])
        for language in LANGUAGES
    )
    all_malformed_visible = all(
        offline_analysis[language]["malformed"]["has_error"]
        and bool(offline_analysis[language]["malformed"]["parse_problems"])
        for language in LANGUAGES
    )
    all_stable = all(
        all(all(row.values()) for row in fixtures.values())
        for fixtures in stable.values()
    )
    OFFLINE_STATE.write_text(
        json.dumps(
            {
                "analysis": offline_analysis,
                "stability": stable,
                "analysis_ms": elapsed,
                "sandbox_marker": os.environ.get(
                    "TREE_SITTER_OFFLINE_SANDBOX", "absent"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    prefetch_summary = {
        key: value
        for key, value in prefetch_state.items()
        if key not in {"cache_dir", "online_analysis"}
    }
    payload = {
        "schema_version": 1,
        "experiment": "X2-tree-sitter-language-pack",
        "base_revision": subprocess_revision(),
        "prefetch": prefetch_summary,
        "offline_replay": {
            "network_denial_required": True,
            "sandbox_marker": os.environ.get("TREE_SITTER_OFFLINE_SANDBOX", "absent"),
            "analysis_ms": elapsed,
            "analysis_summary": summarize_analysis(offline_analysis),
            "stability": stable,
            "full_state": str(OFFLINE_STATE.relative_to(REPO)),
        },
        "capabilities": {
            "grammar_available": list(LANGUAGES),
            "validated_fact_families": {
                language: ["declarations", "imports", "calls", "spans", "parse-problems"]
                for language in LANGUAGES
            },
            "semantic_support": [],
            "must_not_claim": [
                "symbol identity", "types", "resolved calls/imports", "project graph",
                "framework behavior", "complete source coverage",
            ],
        },
        "query_portability": {
            "common_capture_families": ["declarations", "imports", "calls"],
            "language_specific_queries": QUERY_SPECS,
            "node_types": {
                language: offline_analysis[language]["query_node_types"]
                for language in LANGUAGES
            },
            "assessment": (
                "The capture families are portable, but grammar node names and declaration/call "
                "shapes remain language-specific. A small fact adapter is still required."
            ),
        },
        "maintenance": {
            "risk": "medium-high",
            "reason": (
                "The package and grammar catalog are new and fast-moving; pin package and grammar "
                "cache bytes, rerun fixtures on every version change, and never infer semantics from grammar availability."
            ),
            "estimated_per_language_work": (
                "One locked fixture, explicit declaration/import/call queries, error-recovery tests, "
                "and native project verification; semantic families still need native tooling."
            ),
        },
        "checks": {
            "all_valid_fact_families_present": all_valid,
            "all_malformed_inputs_visible": all_malformed_visible,
            "offline_matches_online": all_stable,
            "network_denial_marker_present": os.environ.get("TREE_SITTER_OFFLINE_SANDBOX") == "deny-network",
        },
        "disposition": "continue_pilot" if all_valid and all_malformed_visible and all_stable else "reject",
        "disposition_reason": (
            "The three cached grammars provide stable offline syntax facts with explicit parse-problem nodes, "
            "but language-specific queries and package maturity argue for one real C# or PHP product pilot before adoption."
            if all_valid and all_malformed_visible and all_stable
            else "The pinned package failed a fact, malformed-input, or offline-stability gate."
        ),
        "next_revisit": (
            "Use the cache and fact-family contract in the next C# or PHP detector pilot; do not add the package to default installation."
        ),
    }
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": str(RESULT.relative_to(REPO)),
        "checks": payload["checks"],
        "disposition": payload["disposition"],
        "grammar_cache_bytes": prefetch_state["grammar_cache_bytes"],
        "installed_package_bytes": prefetch_state["installed_package_bytes"],
    }, indent=2))
    return 0 if all(payload["checks"].values()) else 1


def subprocess_revision() -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True, text=True, capture_output=True
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("prefetch", "offline"), required=True)
    args = parser.parse_args()
    if args.phase == "prefetch":
        return prefetch_phase()
    return offline_phase()


if __name__ == "__main__":
    raise SystemExit(main())
