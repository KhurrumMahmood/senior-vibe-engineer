#!/usr/bin/env python
"""
AST-based duplication audit for the your-project codebase.

Finds categories of duplication that grep misses:
  (a) bare int(request.(GET|POST).get(...)) call sites   -- safe_int violations
  (b) shadow _safe_int/_safe_float/_safe_bool helpers    -- hidden reimplementations
  (c) duplicate _call_llm / _llm_call definitions        -- LLM client clones
  (d) inline json.loads(request.body) patterns           -- JSON body boilerplate
  (e) same-name + same-arity functions across modules    -- possible clone pairs

Usage:
  .venv/bin/python scripts/duplication_audit.py [path]
  .venv/bin/python scripts/duplication_audit.py core > reports/duplication/baseline/ast_findings.json

Read-only: never modifies files.
"""

import ast
import json
import os
import sys
from collections import defaultdict


CANONICAL_INPUT_UTILS = ("core/input_utils.py",)  # the ONE legit home for _safe_*
PROTOCOL_CLONE_NAMES = {
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
}


def _iter_py_files(root):
    for dirpath, dirs, files in os.walk(root):
        # skip dotted dirs, migrations (intentionally repetitive), venv, node_modules
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"migrations", "node_modules", "__pycache__", "staticfiles"}]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def _parse(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        return ast.parse(src), src
    except (SyntaxError, UnicodeDecodeError):
        return None, None


def _is_request_attr(node):
    """True if AST node is `request.GET` or `request.POST`."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "request"
        and node.attr in {"GET", "POST"}
    )


def _find_bare_int_request(tree, path):
    """(a) int(request.GET.get(...)) or int(request.POST.get(...)) without safe_int."""
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        # int(request.GET.get("x")) or int(request.POST.get("x"))
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "get":
            if _is_request_attr(arg.func.value):
                hits.append({"file": path, "line": node.lineno, "col": node.col_offset})
    return hits


def _find_shadow_safe_helpers(tree, path):
    """(b) def _safe_int|_safe_float|_safe_bool at any non-canonical location."""
    hits = []
    canonical = any(path.endswith(c) for c in CANONICAL_INPUT_UTILS)
    if canonical:
        return hits
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in {"_safe_int", "_safe_float", "_safe_bool", "safe_int_local", "_coerce_int"}:
                hits.append({"file": path, "line": node.lineno, "name": node.name})
    return hits


def _find_call_llm_defs(tree, path):
    """(c) def _call_llm / _llm_call — any such definition is a potential clone."""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in {"_call_llm", "_llm_call", "call_llm", "_invoke_llm"}:
                # Signature fingerprint: name + arg count + arg names
                args = [a.arg for a in node.args.args]
                hits.append({
                    "file": path,
                    "line": node.lineno,
                    "name": node.name,
                    "args": args,
                    "arity": len(args),
                })
    return hits


def _find_json_loads_request_body(tree, path):
    """(d) json.loads(request.body) occurrences."""
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "loads":
            continue
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "json"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Attribute) and arg.attr == "body":
            if isinstance(arg.value, ast.Name) and arg.value.id == "request":
                hits.append({"file": path, "line": node.lineno, "col": node.col_offset})
    return hits


def _collect_function_fingerprints(tree, path):
    """(e) Record (name, arity, has_self) fingerprints for cross-module clone hunt."""
    fingerprints = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args.args
            has_self = bool(args) and args[0].arg in {"self", "cls"}
            # Skip dunder methods (intentionally shared naming like __init__, __str__)
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            # Skip obvious Django/framework hooks (save, clean, get_queryset, etc.)
            if node.name in {"save", "clean", "get_queryset", "get_context_data", "form_valid", "dispatch", "ready"}:
                continue
            fingerprints.append({
                "file": path,
                "line": node.lineno,
                "name": node.name,
                "arity": len(args),
                "has_self": has_self,
                "protocol_name": node.name in PROTOCOL_CLONE_NAMES,
            })
    return fingerprints


def audit(root):
    report = {
        "bare_int_request": [],
        "shadow_safe_helpers": [],
        "call_llm_defs": [],
        "json_loads_request_body": [],
        "function_clone_candidates": [],
    }
    all_fingerprints = []

    for path in _iter_py_files(root):
        tree, _src = _parse(path)
        if tree is None:
            continue
        rel = os.path.relpath(path)
        report["bare_int_request"].extend(_find_bare_int_request(tree, rel))
        report["shadow_safe_helpers"].extend(_find_shadow_safe_helpers(tree, rel))
        report["call_llm_defs"].extend(_find_call_llm_defs(tree, rel))
        report["json_loads_request_body"].extend(_find_json_loads_request_body(tree, rel))
        all_fingerprints.extend(_collect_function_fingerprints(tree, rel))

    # Cross-module clone candidates: same (name, arity, has_self) across 2+ files
    by_key = defaultdict(list)
    for fp in all_fingerprints:
        key = (fp["name"], fp["arity"], fp["has_self"])
        by_key[key].append(fp)
    for key, entries in by_key.items():
        distinct_files = {e["file"] for e in entries}
        if len(distinct_files) >= 2:
            report["function_clone_candidates"].append({
                "name": key[0],
                "arity": key[1],
                "has_self": key[2],
                "protocol_name": key[0] in PROTOCOL_CLONE_NAMES,
                "occurrences": len(entries),
                "files": sorted(distinct_files),
                "entries": entries,
            })
    # Sort clone candidates by (occurrences desc, name)
    report["function_clone_candidates"].sort(key=lambda c: (-c["occurrences"], c["name"]))

    report["summary"] = {
        "bare_int_request": len(report["bare_int_request"]),
        "shadow_safe_helpers": len(report["shadow_safe_helpers"]),
        "call_llm_defs": len(report["call_llm_defs"]),
        "json_loads_request_body": len(report["json_loads_request_body"]),
        "function_clone_candidate_groups": len(report["function_clone_candidates"]),
    }
    return report


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "core"
    if not os.path.isdir(root):
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(2)
    report = audit(root)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
