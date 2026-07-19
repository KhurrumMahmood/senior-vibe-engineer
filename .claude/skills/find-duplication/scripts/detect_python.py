#!/usr/bin/env python3
"""Run the family-local Python AST duplication detector.

This is the installed-skill form of the legacy ``duplication_audit.py``
stage. It uses only the Python standard library and keeps the original
categories: request integer parsing, shadow safe-conversion helpers, LLM
client definitions, inline JSON-body parsing, and cross-module name/arity
collisions.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".jscpd-input",
        ".venv",
        "__pycache__",
        "migrations",
        "node_modules",
        "reports",
        "staticfiles",
        "test",
        "tests",
    }
)
CANONICAL_INPUT_UTILS: tuple[str, ...] = ()
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


def _iter_py_files(root: Path) -> Iterator[Path]:
    for dirpath, directories, files in os.walk(root):
        directories[:] = sorted(
            directory
            for directory in directories
            if not directory.startswith(".")
            and directory.lower() not in SKIP_DIRECTORIES
        )
        for filename in sorted(files):
            if filename.endswith(".py") and not filename.startswith("test_"):
                yield Path(dirpath) / filename


def _parse(path: Path) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _is_request_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "request"
        and node.attr in {"GET", "POST"}
    )


def _find_bare_int_request(tree: ast.Module, path: str) -> list[dict[str, Any]]:
    hits = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "int"
            and node.args
        ):
            continue
        argument = node.args[0]
        if (
            isinstance(argument, ast.Call)
            and isinstance(argument.func, ast.Attribute)
            and argument.func.attr == "get"
            and _is_request_attr(argument.func.value)
        ):
            hits.append({"file": path, "line": node.lineno, "col": node.col_offset})
    return hits


def _find_shadow_safe_helpers(
    tree: ast.Module, path: str, canonical_homes: tuple[str, ...]
) -> list[dict[str, Any]]:
    if any(path.endswith(home) for home in canonical_homes):
        return []
    names = {"_safe_int", "_safe_float", "_safe_bool", "safe_int_local", "_coerce_int"}
    return [
        {"file": path, "line": node.lineno, "name": node.name}
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]


def _find_call_llm_defs(tree: ast.Module, path: str) -> list[dict[str, Any]]:
    names = {"_call_llm", "_llm_call", "call_llm", "_invoke_llm"}
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            arguments = [argument.arg for argument in node.args.args]
            hits.append(
                {
                    "file": path,
                    "line": node.lineno,
                    "name": node.name,
                    "args": arguments,
                    "arity": len(arguments),
                }
            )
    return hits


def _find_json_loads_request_body(
    tree: ast.Module, path: str
) -> list[dict[str, Any]]:
    hits = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "loads"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "json"
            and node.args
        ):
            continue
        argument = node.args[0]
        if (
            isinstance(argument, ast.Attribute)
            and argument.attr == "body"
            and isinstance(argument.value, ast.Name)
            and argument.value.id == "request"
        ):
            hits.append({"file": path, "line": node.lineno, "col": node.col_offset})
    return hits


def _collect_function_fingerprints(
    tree: ast.Module, path: str
) -> list[dict[str, Any]]:
    fingerprints = []
    framework_hooks = {
        "save",
        "clean",
        "get_queryset",
        "get_context_data",
        "form_valid",
        "dispatch",
        "ready",
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("__") and node.name.endswith("__"):
            continue
        if node.name in framework_hooks:
            continue
        arguments = node.args.args
        fingerprints.append(
            {
                "file": path,
                "line": node.lineno,
                "name": node.name,
                "arity": len(arguments),
                "has_self": bool(arguments) and arguments[0].arg in {"self", "cls"},
                "protocol_name": node.name in PROTOCOL_CLONE_NAMES,
            }
        )
    return fingerprints


def audit(
    root: Path,
    project_root: Path,
    canonical_homes: tuple[str, ...] = (),
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "bare_int_request": [],
        "shadow_safe_helpers": [],
        "call_llm_defs": [],
        "json_loads_request_body": [],
        "function_clone_candidates": [],
    }
    fingerprints = []
    for path in _iter_py_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        try:
            relative = path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            relative = path.relative_to(root).as_posix()
        report["bare_int_request"].extend(_find_bare_int_request(tree, relative))
        report["shadow_safe_helpers"].extend(
            _find_shadow_safe_helpers(tree, relative, canonical_homes)
        )
        report["call_llm_defs"].extend(_find_call_llm_defs(tree, relative))
        report["json_loads_request_body"].extend(
            _find_json_loads_request_body(tree, relative)
        )
        fingerprints.extend(_collect_function_fingerprints(tree, relative))

    by_key: dict[tuple[str, int, bool], list[dict[str, Any]]] = defaultdict(list)
    for fingerprint in fingerprints:
        key = (
            fingerprint["name"],
            fingerprint["arity"],
            fingerprint["has_self"],
        )
        by_key[key].append(fingerprint)
    for key, entries in by_key.items():
        files = sorted({entry["file"] for entry in entries})
        if len(files) < 2:
            continue
        report["function_clone_candidates"].append(
            {
                "name": key[0],
                "arity": key[1],
                "has_self": key[2],
                "protocol_name": key[0] in PROTOCOL_CLONE_NAMES,
                "occurrences": len(entries),
                "files": files,
                "entries": entries,
            }
        )
    report["function_clone_candidates"].sort(
        key=lambda candidate: (-candidate["occurrences"], candidate["name"])
    )
    report["summary"] = {
        "bare_int_request": len(report["bare_int_request"]),
        "shadow_safe_helpers": len(report["shadow_safe_helpers"]),
        "call_llm_defs": len(report["call_llm_defs"]),
        "json_loads_request_body": len(report["json_loads_request_body"]),
        "function_clone_candidate_groups": len(report["function_clone_candidates"]),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--canonical-input-utils", action="append", default=[])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    payload = audit(
        root,
        args.project_root.resolve(),
        tuple(args.canonical_input_utils or CANONICAL_INPUT_UTILS),
    )
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"[detect-python] wrote {args.output}", file=sys.stderr)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
