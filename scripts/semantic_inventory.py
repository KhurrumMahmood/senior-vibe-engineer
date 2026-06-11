#!/usr/bin/env python3
"""
Tooling for the find-semantic-duplication skill.

Subcommands:
  collect   — AST inventory: definitions + call edges + source code
  graph     — Build call graph, identify entry points, trace workflows
  callers   — Pre-compute caller counts via git grep
  artifacts — Inventory non-code artifacts (benchmarks, reports, configs)
  prompts   — Generate structured comparison prompts for LLM agents
  validate  — Validate any JSONL/JSON file against its expected schema

Each subcommand reads the previous phase's output and writes the next.
Schemas enforce communication contracts between phases and between agents.

Stdlib-only. No venv required.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from pathlib import Path


# ============================================================
# SCHEMAS — Communication contracts between phases and agents
# ============================================================
# Each schema defines required fields and their types.
# validate_record() checks a dict against a schema and returns errors.

SCHEMAS = {
    "definition": {
        "type": {"type": str, "values": ["def"]},
        "file": {"type": str},
        "name": {"type": str},
        "qualified_name": {"type": str},
        "line": {"type": int},
        "end_line": {"type": int},
        "kind": {"type": str, "values": ["function", "method", "class"]},
        "arity": {"type": int},
        "size": {"type": int},
        "tier": {"type": str, "values": ["skip", "light", "full", "priority"]},
        "parent_class": {"type": (str, type(None))},
        "decorators": {"type": list},
        "domain_hint": {"type": str},
        "source": {"type": str},
    },
    "edge": {
        "type": {"type": str, "values": ["edge"]},
        "caller": {"type": str},
        "callee_name": {"type": str},
        "call_style": {"type": str, "values": ["self", "attribute", "name"]},
        "line": {"type": int},
    },
    "workflow": {
        "type": {"type": str, "values": ["workflow"]},
        "entry_point": {"type": str},
        "entry_kind": {"type": str, "values": ["view", "task", "command"]},
        "depth": {"type": int},
        "node_count": {"type": int},
        "chain": {"type": list},
        "domain_hint": {"type": str},
    },
    "summary": {
        "file": {"type": str},
        "name": {"type": str},
        "qualified_name": {"type": str},
        "line": {"type": int},
        "kind": {"type": str},
        "size": {"type": int},
        "tier": {"type": str},
        "purpose": {"type": str},
        "domain": {"type": str},
        "inputs": {"type": str},
        "outputs": {"type": str},
        "side_effects": {"type": list},
        "key_operations": {"type": list},
    },
    "candidate": {
        "id": {"type": str},
        "level": {"type": str, "values": ["structural", "workflow", "function"]},
        "similarity": {"type": int, "min": 0, "max": 5},
        "a": {"type": dict},
        "b": {"type": dict},
        "rationale": {"type": str},
    },
    "artifact": {
        "type": {"type": str, "values": ["artifact"]},
        "path": {"type": str},
        "kind": {"type": str, "values": [
            "test_module", "benchmark_result", "report",
            "config", "data_file", "module_rollup",
        ]},
        "concern": {"type": str},
        "first_line_summary": {"type": str},
    },
    "caller_info": {
        "type": {"type": str, "values": ["caller_info"]},
        "qualified_name": {"type": str},
        "file": {"type": str},
        "total_refs": {"type": int},
        "ref_files": {"type": list},
        "categorized": {"type": dict},
    },
    "comparison_prompt": {
        "type": {"type": str, "values": ["comparison_prompt"]},
        "domain": {"type": str},
        "items": {"type": list},
        "item_count": {"type": int},
        "output_schema": {"type": str, "values": ["candidate"]},
        "output_template": {"type": dict},
        "instructions": {"type": str},
    },
}


def validate_record(record, schema_name):
    """Validate a record against a named schema. Returns list of error strings."""
    if schema_name not in SCHEMAS:
        return [f"Unknown schema: {schema_name}"]
    schema = SCHEMAS[schema_name]
    errors = []
    for field, spec in schema.items():
        if field not in record:
            errors.append(f"Missing required field: {field}")
            continue
        val = record[field]
        expected_type = spec["type"]
        if isinstance(expected_type, tuple):
            if not isinstance(val, expected_type):
                errors.append(f"{field}: expected {expected_type}, got {type(val).__name__}")
        elif not isinstance(val, expected_type):
            errors.append(f"{field}: expected {expected_type.__name__}, got {type(val).__name__}")
        if "values" in spec and val not in spec["values"]:
            errors.append(f"{field}: got '{val}', expected one of {spec['values']}")
        if "min" in spec and isinstance(val, (int, float)) and val < spec["min"]:
            errors.append(f"{field}: {val} < min {spec['min']}")
        if "max" in spec and isinstance(val, (int, float)) and val > spec["max"]:
            errors.append(f"{field}: {val} > max {spec['max']}")
    return errors


# ============================================================
# DOMAIN HINTS — Derive from file path + class hierarchy
# ============================================================

DOMAIN_PATTERNS = [
    (r"ptid", "ptid"),
    (r"external_source", "external_source"),
    (r"brand", "brand"),
    (r"interchange", "interchange"),
    (r"export|export", "export"),
    (r"crawl|scrape|proxy", "crawling"),
    (r"extract|selector|field_config|compiler", "extraction"),
    (r"discover|sitemap", "discovery"),
    (r"visual", "visual"),
    (r"training|ai_training", "agent"),
    (r"auth|login|permission", "auth"),
    (r"setting|global_setting|config", "configuration"),
    (r"email|notification", "email"),
    (r"pricing|price", "pricing"),
    (r"agent|llm|agentic", "agent"),
]


def _infer_domain(filepath, qualified_name, parent_class=None):
    """Infer domain from file path and names. Returns best guess."""
    text = f"{filepath} {qualified_name} {parent_class or ''}".lower()
    for pattern, domain in DOMAIN_PATTERNS:
        if re.search(pattern, text):
            return domain
    return "utility"


# ============================================================
# SKIP LISTS
# ============================================================

SKIP_DIRS = {"migrations", "__pycache__", "staticfiles", "node_modules", ".git", ".venv"}

SKIP_FUNCTION_NAMES = {
    "save", "clean", "get_queryset", "get_context_data", "form_valid",
    "dispatch", "ready",
    "setUp", "tearDown", "setUpClass", "setUpTestData",
}
# Note: `handle` is NOT skipped — it's the entry point for management commands.
# `get/post/put/delete/patch` are NOT skipped — they're view entry points.

SKIP_FILE_PREFIXES = ("test_", "tests_")
SKIP_FILE_EXACT = ("tests.py", "conftest.py")

ENTRY_POINT_DECORATORS = {"task", "shared_task", "periodic_task"}
ENTRY_POINT_VIEW_DECORATORS = {"api_view"}
ENTRY_POINT_METHODS = {"get", "post", "put", "delete", "patch"}

SCOPE_FOCUS = "focus"
SCOPE_CONTEXT = "context"
SCOPE_FOCUS_FOCUS = "focus_focus"
SCOPE_FOCUS_CONTEXT = "focus_context"
SCOPE_CONTEXT_ONLY = "context_only"


# ============================================================
# SUBCOMMAND: collect
# ============================================================

def _dedupe_paths(paths):
    seen = set()
    out = []
    for raw in paths:
        if not raw:
            continue
        key = os.path.abspath(raw)
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def _iter_py_files(roots):
    """Yield .py file paths from one or more root paths."""
    yielded = set()
    for root in _dedupe_paths(roots):
        if os.path.isfile(root) and root.endswith(".py"):
            key = os.path.abspath(root)
            if key not in yielded:
                yielded.add(key)
                yield root
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS and not d.startswith(".")]
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                if f in SKIP_FILE_EXACT or any(f.startswith(p) for p in SKIP_FILE_PREFIXES):
                    continue
                path = os.path.join(dirpath, f)
                key = os.path.abspath(path)
                if key in yielded:
                    continue
                yielded.add(key)
                yield path


def _path_is_relative_to(path, root):
    path = Path(path).resolve()
    root = Path(root).resolve()
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _scan_roots(args):
    paths = list(args.paths or [])
    focus = list(args.focus or [])
    context = list(args.context_root or [])
    roots = _dedupe_paths(paths + focus + context)
    if not roots:
        raise SystemExit("collect requires a path, --focus, or --context-root")
    focus_roots = _dedupe_paths(focus or paths)
    return roots, focus_roots


def _scope_for_path(filepath, focus_roots):
    if not focus_roots:
        return SCOPE_FOCUS
    if any(_path_is_relative_to(filepath, root) for root in focus_roots):
        return SCOPE_FOCUS
    return SCOPE_CONTEXT


def _scope_relation(scopes):
    scopes = [s for s in scopes if s]
    if not scopes or all(s == SCOPE_CONTEXT for s in scopes):
        return SCOPE_CONTEXT_ONLY
    if all(s == SCOPE_FOCUS for s in scopes):
        return SCOPE_FOCUS_FOCUS
    return SCOPE_FOCUS_CONTEXT


def _get_decorators(node):
    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(dec.func.attr)
        elif isinstance(dec, ast.Attribute):
            decorators.append(dec.attr)
    return decorators


def _size_tier(size):
    if size <= 10:
        return "skip"
    elif size <= 30:
        return "light"
    elif size <= 100:
        return "full"
    return "priority"


def _resolve_call_target(node, current_class=None):
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id in ("self", "cls"):
            return func.attr, "self"
        return f"{func.value.id}.{func.attr}", "attribute"
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        return func.attr, "attribute"
    if isinstance(func, ast.Name):
        return func.id, "name"
    if isinstance(func, ast.Attribute):
        return func.attr, "attribute"
    return None, None


def _collect_file(filepath, source_lines, tree, scan_scope=SCOPE_FOCUS):
    """Collect definitions and edges from one file."""
    definitions = []
    edges = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            if node.name in SKIP_FUNCTION_NAMES:
                continue

            size = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
            args = node.args.args
            has_self = bool(args) and args[0].arg in ("self", "cls")
            arity = len(args) - (1 if has_self else 0)
            qname = node.name

            definitions.append({
                "type": "def", "file": filepath, "name": node.name,
                "qualified_name": qname, "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "kind": "function", "arity": arity, "size": size,
                "tier": _size_tier(size), "parent_class": None,
                "decorators": _get_decorators(node),
                "domain_hint": _infer_domain(filepath, qname),
                "scan_scope": scan_scope,
            })

            caller_key = f"{filepath}::{qname}"
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name, style = _resolve_call_target(child)
                    if name and not name.startswith("__"):
                        edges.append({"type": "edge", "caller": caller_key,
                                      "callee_name": name, "call_style": style,
                                      "line": child.lineno,
                                      "caller_scope": scan_scope})

        elif isinstance(node, ast.ClassDef):
            class_size = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
            definitions.append({
                "type": "def", "file": filepath, "name": node.name,
                "qualified_name": node.name, "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "kind": "class", "arity": 0, "size": class_size,
                "tier": _size_tier(class_size), "parent_class": None,
                "decorators": _get_decorators(node),
                "domain_hint": _infer_domain(filepath, node.name),
                "scan_scope": scan_scope,
            })

            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("__") and item.name.endswith("__"):
                    continue
                if item.name in SKIP_FUNCTION_NAMES:
                    continue

                size = getattr(item, "end_lineno", item.lineno) - item.lineno + 1
                args = item.args.args
                has_self = bool(args) and args[0].arg in ("self", "cls")
                arity = len(args) - (1 if has_self else 0)
                qname = f"{node.name}.{item.name}"

                definitions.append({
                    "type": "def", "file": filepath, "name": item.name,
                    "qualified_name": qname, "line": item.lineno,
                    "end_line": getattr(item, "end_lineno", item.lineno),
                    "kind": "method", "arity": arity, "size": size,
                    "tier": _size_tier(size), "parent_class": node.name,
                    "decorators": _get_decorators(item),
                    "domain_hint": _infer_domain(filepath, qname, node.name),
                    "scan_scope": scan_scope,
                })

                caller_key = f"{filepath}::{qname}"
                for child in ast.walk(item):
                    if isinstance(child, ast.Call):
                        name, style = _resolve_call_target(child, current_class=node.name)
                        if name and not name.startswith("__"):
                            edges.append({"type": "edge", "caller": caller_key,
                                          "callee_name": name, "call_style": style,
                                          "line": child.lineno,
                                          "caller_scope": scan_scope})

    return definitions, edges


def _add_source(definitions, filepath, source_lines):
    for d in definitions:
        if d["file"] != filepath:
            continue
        start = d["line"] - 1
        if d["kind"] == "class":
            end = min(d["line"] + 5, d["end_line"])
            lines = source_lines[start:end]
            d["source"] = textwrap.dedent("".join(lines)).rstrip() + "\n    ..."
        else:
            end = d["end_line"]
            lines = source_lines[start:end]
            d["source"] = textwrap.dedent("".join(lines)).rstrip()


def cmd_collect(args):
    all_defs, all_edges = [], []
    files_scanned, parse_errors = 0, 0
    roots, focus_roots = _scan_roots(args)

    for filepath in _iter_py_files(roots):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
                source_lines = source.splitlines(keepends=True)
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            parse_errors += 1
            print(f"WARN: {filepath}: {e}", file=sys.stderr)
            continue

        files_scanned += 1
        scan_scope = _scope_for_path(filepath, focus_roots)
        defs, edges = _collect_file(filepath, source_lines, tree, scan_scope)
        _add_source(defs, filepath, source_lines)
        all_defs.extend(defs)
        all_edges.extend(edges)

    # Validate and write
    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    val_errors = 0
    try:
        for d in all_defs:
            errs = validate_record(d, "definition")
            if errs:
                val_errors += 1
                print(f"WARN: validation: {d['qualified_name']}: {errs}", file=sys.stderr)
            out.write(json.dumps(d) + "\n")
        for e in all_edges:
            errs = validate_record(e, "edge")
            if errs:
                val_errors += 1
            out.write(json.dumps(e) + "\n")
    finally:
        if args.output:
            out.close()

    tiers = defaultdict(int)
    kinds = defaultdict(int)
    scopes = defaultdict(int)
    for d in all_defs:
        tiers[d["tier"]] += 1
        kinds[d["kind"]] += 1
        scopes[d.get("scan_scope", SCOPE_FOCUS)] += 1

    print("\n=== collect ===", file=sys.stderr)
    print(f"Files: {files_scanned} (errors: {parse_errors})", file=sys.stderr)
    print(f"Definitions: {len(all_defs)} ({kinds['function']}f {kinds['method']}m {kinds['class']}c)", file=sys.stderr)
    print(f"Edges: {len(all_edges)}", file=sys.stderr)
    print(f"Tiers: skip={tiers['skip']} light={tiers['light']} full={tiers['full']} priority={tiers['priority']}", file=sys.stderr)
    print(f"Scope: focus={scopes[SCOPE_FOCUS]} context={scopes[SCOPE_CONTEXT]}", file=sys.stderr)
    print(f"Eligible: {tiers['light'] + tiers['full'] + tiers['priority']}", file=sys.stderr)
    if val_errors:
        print(f"Validation errors: {val_errors}", file=sys.stderr)


# ============================================================
# SUBCOMMAND: graph
# ============================================================

def cmd_graph(args):
    """Build call graph, identify entry points, trace workflows."""
    defs, edges = [], []
    with open(args.inventory, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["type"] == "def":
                defs.append(rec)
            elif rec["type"] == "edge":
                edges.append(rec)

    # Build lookup: qualified_name -> definition
    by_qname = {}  # caller key (file::qname) -> def
    by_name = defaultdict(list)  # bare name -> [def, ...]
    for d in defs:
        key = f"{d['file']}::{d['qualified_name']}"
        by_qname[key] = d
        by_name[d["name"]].append(d)
        by_name[d["qualified_name"]].append(d)

    # Build adjacency: caller_key -> [callee_keys]
    adjacency = defaultdict(list)
    for e in edges:
        # Try to resolve callee_name to a known definition
        callee = e["callee_name"]
        call_style = e.get("call_style", "")
        resolved = []

        # For self/cls calls, restrict to methods of the same class
        if call_style == "self":
            caller_def = by_qname.get(e["caller"])
            if caller_def and caller_def.get("parent_class"):
                parent = caller_def["parent_class"]
                # Look for ClassName.method_name
                qname = f"{parent}.{callee}"
                if qname in by_name:
                    resolved = [r for r in by_name[qname]
                                if r["file"] == caller_def["file"]]
                # Fallback: bare name but filter to same parent class
                if not resolved and callee in by_name:
                    resolved = [r for r in by_name[callee]
                                if r.get("parent_class") == parent]
        else:
            # Direct match: ClassName.method or function_name
            if callee in by_name:
                resolved = by_name[callee]
            # Partial match: just the method name part
            elif "." in callee:
                method_part = callee.split(".")[-1]
                if method_part in by_name:
                    resolved = by_name[method_part]

        for r in resolved:
            callee_key = f"{r['file']}::{r['qualified_name']}"
            if callee_key != e["caller"]:  # no self-loops
                adjacency[e["caller"]].append(callee_key)

    # Identify entry points
    entry_points = []
    for d in defs:
        key = f"{d['file']}::{d['qualified_name']}"
        decorators = set(d.get("decorators", []))

        # Celery tasks
        if decorators & ENTRY_POINT_DECORATORS:
            entry_points.append((key, "task"))
            continue

        # DRF @api_view decorated functions
        if decorators & ENTRY_POINT_VIEW_DECORATORS:
            entry_points.append((key, "view"))
            continue

        # View HTTP methods (get/post/put/delete/patch)
        if d["kind"] == "method" and d["name"] in ENTRY_POINT_METHODS:
            entry_points.append((key, "view"))
            continue

        # Management commands
        if d["kind"] == "method" and d["name"] == "handle" and "management" in d["file"]:
            entry_points.append((key, "command"))
            continue

    # Trace workflows from entry points (BFS, max depth 8)
    workflows = []
    for ep_key, ep_kind in entry_points:
        if ep_key not in by_qname:
            continue
        ep_def = by_qname[ep_key]

        chain = []
        visited = set()
        queue = [(ep_key, 0)]
        while queue:
            node_key, depth = queue.pop(0)
            if node_key in visited or depth > 8:
                continue
            visited.add(node_key)

            node_def = by_qname.get(node_key)
            if node_def:
                chain.append({
                    "qualified_name": node_def["qualified_name"],
                    "file": node_def["file"],
                    "line": node_def["line"],
                    "depth": depth,
                })

            for callee_key in adjacency.get(node_key, []):
                if callee_key not in visited:
                    queue.append((callee_key, depth + 1))

        if len(chain) > 1:  # only interesting if the workflow has depth
            workflows.append({
                "type": "workflow",
                "entry_point": ep_key,
                "entry_kind": ep_kind,
                "depth": max(c["depth"] for c in chain),
                "node_count": len(chain),
                "chain": chain,
                "domain_hint": ep_def["domain_hint"],
            })

    # Write output
    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    val_errors = 0
    try:
        for w in workflows:
            errs = validate_record(w, "workflow")
            if errs:
                val_errors += 1
                print(f"WARN: workflow validation: {w['entry_point']}: {errs}", file=sys.stderr)
            out.write(json.dumps(w) + "\n")
    finally:
        if args.output:
            out.close()

    print("\n=== graph ===", file=sys.stderr)
    print(f"Definitions loaded: {len(defs)}", file=sys.stderr)
    print(f"Edges loaded: {len(edges)}", file=sys.stderr)
    print(f"Entry points found: {len(entry_points)}", file=sys.stderr)
    kinds = defaultdict(int)
    for _, k in entry_points:
        kinds[k] += 1
    print(f"  views={kinds['view']} tasks={kinds['task']} commands={kinds['command']}", file=sys.stderr)
    print(f"Workflows traced: {len(workflows)}", file=sys.stderr)
    if val_errors:
        print(f"Validation errors: {val_errors}", file=sys.stderr)


# ============================================================
# SUBCOMMAND: callers
# ============================================================

def cmd_callers(args):
    """Pre-compute caller counts via git grep."""
    with open(args.inventory, encoding="utf-8") as fh:
        all_records = [json.loads(line) for line in fh if line.strip()]
    defs = [r for r in all_records if r["type"] == "def"]
    eligible = [d for d in defs if d["tier"] != "skip" and d["kind"] != "class"]

    def _rel_key(fpath):
        path = Path(fpath)
        if path.is_absolute():
            try:
                return path.resolve().relative_to(Path(args.repo_root).resolve()).as_posix()
            except ValueError:
                return path.as_posix()
        return fpath.replace(os.sep, "/")

    file_scope = {
        _rel_key(d["file"]): d.get("scan_scope", SCOPE_FOCUS)
        for d in defs
    }

    # Categorize files by role
    def _categorize_file(fpath):
        if "test" in fpath:
            return "test"
        if "views" in fpath:
            return "view"
        if "tasks" in fpath:
            return "task"
        if "services" in fpath:
            return "service"
        if "template" in fpath or fpath.endswith(".html"):
            return "template"
        if "management/commands" in fpath:
            return "command"
        return "other"

    results = []
    for d in eligible:
        name = d["name"]
        try:
            r = subprocess.run(
                ["git", "grep", "-l", "-w", name, "--", "*.py", "*.html"],
                capture_output=True, text=True, timeout=5,
                cwd=args.repo_root,
            )
            ref_files = [f for f in r.stdout.strip().splitlines() if f]
            # Exclude the defining file from the count — compare the full
            # relative path, not the basename, so sibling files with the
            # same basename (e.g. two `tasks.py`, paired `sites/<site>/scrape.py`)
            # aren't silently dropped and mis-classified as dormant.
            def_file = _rel_key(d["file"])
            ref_files = [f for f in ref_files if f.replace(os.sep, "/") != def_file]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            ref_files = []

        categorized = defaultdict(int)
        ref_scope_counts = defaultdict(int)
        for f in ref_files:
            categorized[_categorize_file(f)] += 1
            ref_scope_counts[file_scope.get(f.replace(os.sep, "/"), SCOPE_CONTEXT)] += 1

        scan_scope = d.get("scan_scope", SCOPE_FOCUS)
        scope_relation = _scope_relation(
            [scan_scope]
            + [
                file_scope.get(f.replace(os.sep, "/"), SCOPE_CONTEXT)
                for f in ref_files
            ]
        )

        results.append({
            "type": "caller_info",
            "qualified_name": d["qualified_name"],
            "file": d["file"],
            "total_refs": len(ref_files),
            "ref_files": ref_files,
            "categorized": dict(categorized),
            "scan_scope": scan_scope,
            "ref_scope_counts": dict(ref_scope_counts),
            "scope_relation": scope_relation,
        })

    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        for r in results:
            out.write(json.dumps(r) + "\n")
    finally:
        if args.output:
            out.close()

    print("\n=== callers ===", file=sys.stderr)
    print(f"Functions checked: {len(results)}", file=sys.stderr)
    zero_refs = sum(1 for r in results if r["total_refs"] == 0)
    print(f"Zero external refs: {zero_refs} (potential dormant)", file=sys.stderr)


# ============================================================
# SUBCOMMAND: artifacts
# ============================================================

ARTIFACT_PATTERNS = {
    "test_module": ["tests/test_*.py", "testing/test_*.py"],
    "benchmark_result": ["testing/*.json", "testing/*.jsonl"],
    "report": ["reports/**/*.md"],
    "config": [".claude/**/*.md", "*.json"],
    "data_file": ["testing/**/*.jsonl", "data/**/*"],
}


def cmd_artifacts(args):
    """Inventory non-code artifacts."""
    results = []
    root = Path(args.repo_root)

    for kind, patterns in ARTIFACT_PATTERNS.items():
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                if path.is_dir():
                    continue
                relpath = str(path.relative_to(root))

                # Read first line for summary
                first_line = ""
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and not line.startswith("---"):
                                first_line = line[:200]
                                break
                except OSError:
                    pass

                results.append({
                    "type": "artifact",
                    "path": relpath,
                    "kind": kind,
                    "concern": "",  # filled by LLM agent
                    "first_line_summary": first_line,
                })

    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        for r in results:
            out.write(json.dumps(r) + "\n")
    finally:
        if args.output:
            out.close()

    kinds = defaultdict(int)
    for r in results:
        kinds[r["kind"]] += 1
    print("\n=== artifacts ===", file=sys.stderr)
    print(f"Total: {len(results)}", file=sys.stderr)
    for k, c in sorted(kinds.items()):
        print(f"  {k}: {c}", file=sys.stderr)


# ============================================================
# SUBCOMMAND: prompts
# ============================================================

def cmd_prompts(args):
    """Generate structured comparison prompts for LLM agents.

    Reads summaries.jsonl, groups by domain, produces one prompt file per
    domain group. Each prompt file includes the items to compare and the
    exact output schema the agent must follow.
    """
    with open(args.summaries, encoding="utf-8") as fh:
        summaries = [json.loads(line) for line in fh if line.strip()]

    by_domain = defaultdict(list)
    for s in summaries:
        by_domain[s.get("domain", "utility")].append(s)

    os.makedirs(args.output_dir, exist_ok=True)

    # The output schema the LLM agent must produce
    output_template = {
        "id": "SC-{n}",
        "level": "function",
        "similarity": 0,
        "a": {"qualified_name": "", "file": "", "line": 0},
        "b": {"qualified_name": "", "file": "", "line": 0},
        "scope_relation": SCOPE_FOCUS_FOCUS,
        "rationale": "",
    }

    prompt_count = 0

    def _compact(item):
        return {
            "qualified_name": item["qualified_name"],
            "file": item["file"],
            "line": item["line"],
            "size": item["size"],
            "tier": item["tier"],
            "purpose": item["purpose"],
            "key_operations": item.get("key_operations", []),
            "inputs": item.get("inputs", ""),
            "outputs": item.get("outputs", ""),
            "scan_scope": item.get("scan_scope", SCOPE_FOCUS),
        }

    def _scope_summary(items):
        scopes = [item.get("scan_scope", SCOPE_FOCUS) for item in items]
        return {
            "focus": sum(1 for scope in scopes if scope == SCOPE_FOCUS),
            "context": sum(1 for scope in scopes if scope == SCOPE_CONTEXT),
            "relation_hint": _scope_relation(scopes),
        }

    def _write_prompt(domain, items, filename):
        nonlocal prompt_count
        if len(items) < 2:
            return

        compact_items = [_compact(item) for item in items]

        prompt = {
            "type": "comparison_prompt",
            "domain": domain,
            "item_count": len(compact_items),
            "items": compact_items,
            "output_schema": "candidate",
            "output_template": output_template,
            "scope_summary": _scope_summary(compact_items),
            "candidate_scope_instructions": (
                "For every candidate, set scope_relation to focus_focus "
                "when both items have scan_scope=focus, focus_context when "
                "exactly one item is focus, and context_only when neither is focus."
            ),
            "instructions": (
                f"Compare all {len(compact_items)} items in the '{domain}' domain. "
                "Find pairs that solve the SAME PROBLEM with DIFFERENT CODE. "
                "Score similarity 0-5 (3=partial overlap, 4=high overlap, 5=near-identical). "
                "Only report pairs scoring >= 3. "
                "Do NOT flag: caller-callee pairs, different workflow steps, "
                "thin HTTP wrappers, genuinely different subproblems. "
                "Output: a JSON array of objects matching the output_template exactly. "
                "Empty array if no pairs found."
            ),
        }

        outpath = os.path.join(args.output_dir, filename)
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(prompt, f, indent=2)
        prompt_count += 1

    for domain, items in sorted(by_domain.items()):
        if len(items) < 2:
            continue
        _write_prompt(domain, items, f"prompt_{domain}.json")

    if args.include_cross_domain:
        eligible = [
            item
            for item in summaries
            if item.get("tier") in {"full", "priority"}
            and item.get("kind") != "class"
        ]
        focus_items = [
            item for item in eligible if item.get("scan_scope", SCOPE_FOCUS) == SCOPE_FOCUS
        ]
        cross_items = focus_items or eligible
        tier_order = {"priority": 0, "full": 1, "light": 2, "skip": 3}
        cross_items = sorted(
            cross_items,
            key=lambda item: (tier_order.get(item.get("tier"), 9), -int(item.get("size") or 0)),
        )[: args.cross_domain_limit]
        if len({item.get("domain", "utility") for item in cross_items}) >= 2:
            _write_prompt("cross_domain", cross_items, "prompt_cross_domain.json")

    print("\n=== prompts ===", file=sys.stderr)
    print(f"Domains with 2+ items: {prompt_count}", file=sys.stderr)
    print(f"Prompts written to: {args.output_dir}/", file=sys.stderr)


# ============================================================
# SUBCOMMAND: validate
# ============================================================

def cmd_validate(args):
    """Validate a JSONL or JSON file against a named schema."""
    schema_name = args.schema

    if args.file.endswith(".json"):
        with open(args.file, encoding="utf-8") as fh:
            data = json.load(fh)
        records = data if isinstance(data, list) else [data]
    else:
        with open(args.file, encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]

    # An empty input would otherwise read as "PASS: 0/0 records valid" —
    # a silent success that lets a downstream gate skip the stage. Treat
    # it as a FAIL so a scout that produced zero summaries is surfaced.
    if not records:
        print(f"FAIL: input {args.file!r} contains no records")
        return 1

    total, failed = 0, 0
    schema_counts = defaultdict(int)
    for i, rec in enumerate(records):
        total += 1
        if schema_name == "auto":
            rec_type = rec.get("type", "")
            # Map record type to schema name
            if rec_type == "def":
                s = "definition"
            elif rec_type in SCHEMAS:
                s = rec_type
            else:
                failed += 1
                if args.verbose:
                    print(f"Record {i}: unknown type '{rec_type}'", file=sys.stderr)
                continue
        else:
            s = schema_name
        schema_counts[s] += 1
        errs = validate_record(rec, s)
        if errs:
            failed += 1
            if args.verbose:
                print(f"Record {i} ({s}): {errs}", file=sys.stderr)

    status = "PASS" if failed == 0 else "FAIL"
    schema_detail = ", ".join(f"{k}={v}" for k, v in sorted(schema_counts.items()))
    print(f"{status}: {total - failed}/{total} records valid ({schema_detail})")
    return 0 if failed == 0 else 1


# ============================================================
# MAIN — Argparse subcommands
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Semantic inventory tooling for find-semantic-duplication skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Workflow:
              1. collect  — AST inventory of definitions + call edges
              2. graph    — Build call graph + trace workflows from entry points
              3. callers  — Pre-compute caller counts via git grep
              4. artifacts — Inventory non-code artifacts
              5. [LLM]   — Summarize definitions (writes summaries.jsonl)
              6. prompts  — Generate comparison prompts from summaries
              7. [LLM]   — Score similarity using prompts
              8. validate — Check any output against its schema

            Schemas (for validate):
              definition, edge, workflow, summary, candidate,
              artifact, caller_info, comparison_prompt
        """),
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # collect
    p = subs.add_parser("collect", help="AST inventory: definitions + edges + source")
    p.add_argument("paths", nargs="*")
    p.add_argument(
        "--focus",
        action="append",
        default=[],
        help="Path to tag as focus scope; may be repeated",
    )
    p.add_argument(
        "--context-root",
        action="append",
        default=[],
        help="Additional context root to scan; may be repeated",
    )
    p.add_argument("--output", "-o", default=None)

    # graph
    p = subs.add_parser("graph", help="Build call graph + trace workflows")
    p.add_argument("inventory", help="Path to inventory.jsonl from collect")
    p.add_argument("--output", "-o", default=None)

    # callers
    p = subs.add_parser("callers", help="Pre-compute caller counts via git grep")
    p.add_argument("inventory", help="Path to inventory.jsonl")
    p.add_argument("--repo-root", default=".", help="Git repo root for git grep")
    p.add_argument("--output", "-o", default=None)

    # artifacts
    p = subs.add_parser("artifacts", help="Inventory non-code artifacts")
    p.add_argument("--repo-root", default=".", help="Project root to scan")
    p.add_argument("--output", "-o", default=None)

    # prompts
    p = subs.add_parser("prompts", help="Generate comparison prompts from summaries")
    p.add_argument("summaries", help="Path to summaries.jsonl")
    p.add_argument("--output-dir", default=".", help="Dir to write prompt files")
    p.add_argument(
        "--include-cross-domain",
        action="store_true",
        help="Also write a bounded cross-domain prompt for focused scans",
    )
    p.add_argument(
        "--cross-domain-limit",
        type=int,
        default=60,
        help="Max items in the optional cross-domain prompt",
    )

    # validate
    p = subs.add_parser("validate", help="Validate file against schema")
    p.add_argument("file", help="JSONL or JSON file to validate")
    p.add_argument("--schema", required=True, choices=["auto"] + list(SCHEMAS.keys()))
    p.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "graph":
        cmd_graph(args)
    elif args.command == "callers":
        cmd_callers(args)
    elif args.command == "artifacts":
        cmd_artifacts(args)
    elif args.command == "prompts":
        cmd_prompts(args)
    elif args.command == "validate":
        sys.exit(cmd_validate(args))


if __name__ == "__main__":
    main()
