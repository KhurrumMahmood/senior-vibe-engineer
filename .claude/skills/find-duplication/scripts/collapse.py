#!/usr/bin/env python3
"""Collapse jscpd pair output + normalize AST audit categories.

Reads jscpd-report.json and (optionally) the project's ast_findings.json.
Groups overlapping jscpd clones by method identity, filters intentional
boilerplate, and emits a unified findings JSON ready for ranking.

Usage:
  python collapse.py \\
      --jscpd-report <path> \\
      --ast-findings <path> \\
      --target <scanned_dir> \\
      --project-root <repo_root> \\
      --output <path> \\
      [--ignore <glob> ...] [--no-defaults]
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Route Python parsing through the shared per-language adapter registry
# (ADR 0032) so enclosing-symbol resolution capability-gates on Python
# and gracefully skips non-Python / unparseable clone sites.
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[4] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from _lib.lang_adapter import CAP_PYTHON_AST, get_adapter  # noqa: E402


DEFAULT_IGNORES: list[str] = [
    "**/tests_*.py",
    "**/tests/**",
    "**/migrations/**",
    "sites/*/scrape.py",
    "**/vendor_*.py",
    "**/staticfiles/**",
    "**/theme/**",
]

# Framework handlers where raw multiplicity is structural, not a clone.
INTENTIONAL_CLONE_NAMES: frozenset[str] = frozenset({
    # Django CBV dispatch
    "post", "get", "put", "delete", "patch", "head", "options", "dispatch",
    # Django FormView / ListView / DetailView hooks
    "form_valid", "form_invalid", "get_queryset", "get_context_data",
    "get_object", "get_form_class", "get_success_url",
    # DRF viewset / mixin handlers
    "perform_create", "perform_update", "perform_destroy",
    "create", "retrieve", "update", "destroy",
    # Django management commands
    "handle", "add_arguments",
    # Django LoginRequired / UserPassesTestMixin
    "test_func",
    # App lifecycle
    "ready",
    # Tests
    "setUp", "tearDown", "setUpClass", "tearDownClass",
})

# Protocol-ish names are common across unrelated objects. Keep them visible
# as a weak signal, but only promote them when jscpd also saw lexical overlap.
PROTOCOL_CLONE_NAMES: frozenset[str] = frozenset({
    "run",
    "execute",
    "process",
    "validate",
    "serialize",
    "deserialize",
    "to_dict",
    "from_dict",
    "as_dict",
    "to_json",
    "from_json",
    "to_representation",
    "from_representation",
})


def path_is_ignored(path: str, patterns: list[str]) -> bool:
    base = os.path.basename(path)
    parts = path.split("/")
    for pat in patterns:
        if fnmatch.fnmatchcase(path, pat):
            return True
        if fnmatch.fnmatchcase(base, pat):
            return True
        for p in parts:
            if fnmatch.fnmatchcase(p, pat):
                return True
    return False


def normalize_path(name: str, project_root: str) -> str:
    """Return *name* as a forward-slashed, project-relative path."""
    if not name:
        return name
    if os.path.isabs(name):
        root = os.path.abspath(project_root)
        try:
            rel = os.path.relpath(name, root)
        except ValueError:
            return name.replace(os.sep, "/")
        if rel.startswith(".."):
            return name.replace(os.sep, "/")
        name = rel
    name = name.replace(os.sep, "/")
    if name.startswith("./"):
        name = name[2:]
    return name


def find_enclosing_function(
    source_file: str, start_line: int, end_line: int
) -> str | None:
    """Return the innermost qualified name of the class/func spanning the range."""
    try:
        src = Path(source_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    adapter = get_adapter(source_file)
    if adapter is None or CAP_PYTHON_AST not in adapter.capabilities:
        return None
    tree = adapter.parse(src)
    if tree is None:
        return None

    best: tuple[int, str, bool] | None = None

    def visit(node: ast.AST, parts: list[str]) -> None:
        nonlocal best
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                c_start = child.lineno
                c_end = getattr(child, "end_lineno", c_start)
                # Require the start to land inside this node; the end can leak
                # past (jscpd ranges often include trailing blank lines).
                if c_start <= start_line <= c_end:
                    is_fn = isinstance(
                        child, (ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                    new_parts = parts + [child.name]
                    qual = ".".join(new_parts)
                    span = c_end - c_start
                    # Prefer function matches over class matches at the same
                    # nesting, and innermost (smallest span) within that tier.
                    better = (
                        best is None
                        or (is_fn and not best[2])
                        or (is_fn == best[2] and span < best[0])
                    )
                    if better:
                        best = (span, qual, is_fn)
                    visit(child, new_parts)
            else:
                visit(child, parts)

    visit(tree, [])
    return best[1] if best else None


def _union_shared_sites(
    group_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge groups that share any (file, method) site. Handles three-way+
    duplication where jscpd emits A-B and A-C as separate pairs."""
    if len(group_list) <= 1:
        return group_list

    parent = list(range(len(group_list)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    site_to_groups: dict[tuple[str, str], list[int]] = {}
    for i, g in enumerate(group_list):
        for site_key in g["sites"].keys():
            site_to_groups.setdefault(site_key, []).append(i)
    for ids in site_to_groups.values():
        for j in ids[1:]:
            union(ids[0], j)

    merged_by_root: dict[int, dict[str, Any]] = {}
    for i, g in enumerate(group_list):
        root = find(i)
        bucket = merged_by_root.setdefault(
            root,
            {"sites": {}, "shared_lines_max": 0, "raw_pairs_collapsed": 0},
        )
        for site_key, site_data in g["sites"].items():
            bucket["sites"].setdefault(site_key, site_data)
        bucket["shared_lines_max"] = max(
            bucket["shared_lines_max"], g["shared_lines_max"]
        )
        bucket["raw_pairs_collapsed"] += g["raw_pairs_collapsed"]
    return list(merged_by_root.values())


def collapse_jscpd(
    jscpd_data: dict[str, Any],
    project_root: str,
    ignore_patterns: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collapse jscpd pairwise clones into method-identity findings."""
    run_meta = jscpd_data.get("run") or {}
    lexical_status = str(run_meta.get("status") or "completed")
    duplicates = jscpd_data.get("duplicates", []) or []
    raw_count = len(duplicates)
    groups: dict[frozenset[tuple[str, str]], dict[str, Any]] = {}
    filtered = 0

    for dup in duplicates:
        first = dup.get("firstFile") or {}
        second = dup.get("secondFile") or {}
        name_a = normalize_path(first.get("name", ""), project_root)
        name_b = normalize_path(second.get("name", ""), project_root)
        if not name_a or not name_b:
            filtered += 1
            continue
        if path_is_ignored(name_a, ignore_patterns) or path_is_ignored(
            name_b, ignore_patterns
        ):
            filtered += 1
            continue

        start_a = int(first.get("start") or 1)
        end_a = int(first.get("end") or start_a)
        start_b = int(second.get("start") or 1)
        end_b = int(second.get("end") or start_b)
        src_a = os.path.join(project_root, name_a)
        src_b = os.path.join(project_root, name_b)
        method_a = find_enclosing_function(src_a, start_a, end_a) or "<module>"
        method_b = find_enclosing_function(src_b, start_b, end_b) or "<module>"

        site_a = (name_a, method_a)
        site_b = (name_b, method_b)
        key = frozenset([site_a, site_b])
        shared_lines = int(dup.get("lines") or 0)

        entry = groups.setdefault(
            key,
            {
                "sites": {},
                "shared_lines_max": 0,
                "raw_pairs_collapsed": 0,
            },
        )
        entry["sites"].setdefault(
            site_a,
            {
                "file": name_a, "method": method_a,
                "start_line": start_a, "end_line": end_a,
            },
        )
        entry["sites"].setdefault(
            site_b,
            {
                "file": name_b, "method": method_b,
                "start_line": start_b, "end_line": end_b,
            },
        )
        entry["shared_lines_max"] = max(
            entry["shared_lines_max"], shared_lines
        )
        entry["raw_pairs_collapsed"] += 1

    merged_groups = _union_shared_sites(list(groups.values()))

    findings: list[dict[str, Any]] = []
    ordered = sorted(merged_groups, key=lambda e: -e["shared_lines_max"])
    for idx, entry in enumerate(ordered, start=1):
        sites = list(entry["sites"].values())
        shape = "pure_duplication" if len(sites) == 2 else "three_way_plus"
        findings.append({
            "finding_id": f"jscpd-{idx:04d}",
            "source": "jscpd",
            "shape_hint": shape,
            "multiplicity": len(sites),
            "shared_lines_max": entry["shared_lines_max"],
            "sites": sites,
            "raw_pairs_collapsed": entry["raw_pairs_collapsed"],
        })

    return findings, {
        "raw_pair_count": raw_count,
        "filtered_pair_count": filtered,
        "finding_count": len(findings),
        "lexical_scan_degraded": lexical_status == "skipped_lexical",
        "lexical_scan_status": lexical_status,
    }


def _is_intentional_function_clone(name: str) -> bool:
    if name in INTENTIONAL_CLONE_NAMES:
        return True
    if name.startswith("__") and name.endswith("__"):
        return True
    return False


def _is_protocol_name_clone(name: str) -> bool:
    return name in PROTOCOL_CLONE_NAMES


def _filter_entries(
    entries: list[dict[str, Any]], ignore_patterns: list[str]
) -> list[dict[str, Any]]:
    return [
        e for e in entries
        if not path_is_ignored(e.get("file", ""), ignore_patterns)
    ]


def collapse_ast(
    ast_data: dict[str, Any], ignore_patterns: list[str]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    findings: list[dict[str, Any]] = []
    filtered = 0

    for entry in ast_data.get("shadow_safe_helpers", []) or []:
        file = entry.get("file", "")
        if path_is_ignored(file, ignore_patterns):
            filtered += 1
            continue
        findings.append({
            "source": "ast",
            "category": "shadow_safe_helper",
            "shape_hint": "shadow_helper",
            "multiplicity": 1,
            "shared_lines_max": None,
            "sites": [{
                "file": file,
                "method": entry.get("name"),
                "start_line": entry.get("line"),
                "end_line": entry.get("line"),
            }],
            "raw_pairs_collapsed": 0,
        })

    call_llm = _filter_entries(
        ast_data.get("call_llm_defs", []) or [], ignore_patterns
    )
    if len(call_llm) >= 2:
        findings.append({
            "source": "ast",
            "category": "call_llm_shadow",
            "shape_hint": "shadow_helper",
            "multiplicity": len(call_llm),
            "shared_lines_max": None,
            "sites": [
                {
                    "file": e.get("file"),
                    "method": e.get("name"),
                    "start_line": e.get("line"),
                    "end_line": e.get("line"),
                    "arity": e.get("arity"),
                }
                for e in call_llm
            ],
            "raw_pairs_collapsed": 0,
        })

    bare_int = _filter_entries(
        ast_data.get("bare_int_request", []) or [], ignore_patterns
    )
    if bare_int:
        findings.append({
            "source": "ast",
            "category": "bare_int_request",
            "shape_hint": "canonical_pattern_violation",
            "multiplicity": len(bare_int),
            "shared_lines_max": None,
            "sites": [
                {
                    "file": e.get("file"),
                    "method": None,
                    "start_line": e.get("line"),
                    "end_line": e.get("line"),
                    "col": e.get("col"),
                }
                for e in bare_int
            ],
            "raw_pairs_collapsed": 0,
        })

    json_loads = _filter_entries(
        ast_data.get("json_loads_request_body", []) or [], ignore_patterns
    )
    if json_loads:
        findings.append({
            "source": "ast",
            "category": "json_loads_request_body",
            "shape_hint": "canonical_pattern_violation",
            "multiplicity": len(json_loads),
            "shared_lines_max": None,
            "sites": [
                {
                    "file": e.get("file"),
                    "method": None,
                    "start_line": e.get("line"),
                    "end_line": e.get("line"),
                    "col": e.get("col"),
                }
                for e in json_loads
            ],
            "raw_pairs_collapsed": 0,
        })

    for entry in ast_data.get("function_clone_candidates", []) or []:
        name = entry.get("name", "")
        if _is_intentional_function_clone(name):
            filtered += 1
            continue
        entries = _filter_entries(entry.get("entries", []) or [], ignore_patterns)
        if len(entries) < 2:
            continue
        is_protocol = _is_protocol_name_clone(name)
        findings.append({
            "source": "ast",
            "category": (
                "protocol_name_collision"
                if is_protocol
                else "cross_module_name_collision"
            ),
            "shape_hint": (
                "protocol_name_collision"
                if is_protocol
                else "cross_file_clone"
            ),
            "multiplicity": len(entries),
            "shared_lines_max": None,
            "sites": [
                {
                    "file": sub.get("file"),
                    "method": sub.get("name"),
                    "start_line": sub.get("line"),
                    "end_line": sub.get("line"),
                    "arity": sub.get("arity"),
                }
                for sub in entries
            ],
            "raw_pairs_collapsed": 0,
        })

    for i, f in enumerate(findings, start=1):
        f["finding_id"] = f"ast-{i:04d}"

    return findings, {
        "finding_count": len(findings),
        "filtered_count": filtered,
    }


def _cross_reference(
    jscpd_findings: list[dict[str, Any]],
    ast_findings: list[dict[str, Any]],
) -> None:
    """Annotate findings that share a (file, method) site across sources.

    jscpd methods are qualified (``Class.method``) while AST methods are bare
    (``method``); normalize to the last dotted segment so they can match.
    """
    def sites_of(f: dict[str, Any]) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for s in f.get("sites") or []:
            m = s.get("method")
            if not m:
                continue
            out.add((s.get("file"), m.rsplit(".", 1)[-1]))
        return out

    ast_by_site: dict[tuple[str, str], list[str]] = {}
    for f in ast_findings:
        for s in sites_of(f):
            ast_by_site.setdefault(s, []).append(f["finding_id"])
    jscpd_by_site: dict[tuple[str, str], list[str]] = {}
    for f in jscpd_findings:
        for s in sites_of(f):
            jscpd_by_site.setdefault(s, []).append(f["finding_id"])

    for f in jscpd_findings:
        related: set[str] = set()
        for s in sites_of(f):
            related.update(ast_by_site.get(s, []))
        if related:
            f["related_findings"] = sorted(related)
    for f in ast_findings:
        related = set()
        for s in sites_of(f):
            related.update(jscpd_by_site.get(s, []))
        if related:
            f["related_findings"] = sorted(related)


def promote_protocol_name_overlaps(findings: list[dict[str, Any]]) -> None:
    """Re-promote protocol-name collisions when lexical overlap confirms them."""
    for finding in findings:
        if finding.get("shape_hint") != "protocol_name_collision":
            continue
        if not finding.get("related_findings"):
            continue
        finding["shape_hint"] = "cross_file_clone"
        finding["protocol_name_overlap_confirmed"] = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collapse jscpd pairs by method identity and normalize "
                    "AST audit categories."
    )
    parser.add_argument("--jscpd-report", required=True)
    parser.add_argument("--ast-findings", default=None)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--no-defaults", action="store_true")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args(argv)

    ignore_patterns = list(args.ignore)
    if not args.no_defaults:
        ignore_patterns = DEFAULT_IGNORES + ignore_patterns

    with open(args.jscpd_report, encoding="utf-8") as fh:
        jscpd_data = json.load(fh)

    ast_data: dict[str, Any] = {}
    if args.ast_findings:
        with open(args.ast_findings, encoding="utf-8") as fh:
            ast_data = json.load(fh)

    jscpd_findings, jscpd_stats = collapse_jscpd(
        jscpd_data, args.project_root, ignore_patterns
    )
    ast_findings, ast_stats = collapse_ast(ast_data, ignore_patterns)
    _cross_reference(jscpd_findings, ast_findings)
    promote_protocol_name_overlaps(ast_findings)

    output = {
        "scan_meta": {
            "target": args.target,
            "project_root": args.project_root,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ignore_patterns": ignore_patterns,
            "jscpd_raw_pair_count": jscpd_stats["raw_pair_count"],
            "jscpd_filtered_pair_count": jscpd_stats["filtered_pair_count"],
            "jscpd_finding_count": jscpd_stats["finding_count"],
            "jscpd_lexical_scan_degraded": jscpd_stats["lexical_scan_degraded"],
            "jscpd_lexical_scan_status": jscpd_stats["lexical_scan_status"],
            "ast_finding_count": ast_stats["finding_count"],
            "ast_filtered_count": ast_stats["filtered_count"],
        },
        "findings": jscpd_findings + ast_findings,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    print(
        f"[collapse] jscpd: raw={jscpd_stats['raw_pair_count']} "
        f"filtered={jscpd_stats['filtered_pair_count']} "
        f"findings={jscpd_stats['finding_count']} "
        f"status={jscpd_stats['lexical_scan_status']}",
        file=sys.stderr,
    )
    print(
        f"[collapse] ast: findings={ast_stats['finding_count']} "
        f"filtered={ast_stats['filtered_count']}",
        file=sys.stderr,
    )
    print(f"[collapse] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
