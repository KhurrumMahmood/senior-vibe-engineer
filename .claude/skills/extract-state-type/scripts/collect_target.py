#!/usr/bin/env python3
"""Resolve a Form-B target spec + enumerate callers for /extract-state-type.

The `/extract-state-type` orchestrator calls this at Stage 1 to turn a
`<file>::<symbol>` spec into a `targets.json` the scout can consume.
The script:

1. Parses the target file, locates the function or method named by
   the symbol spec.
2. Records signature, line range (for scout context), docstring,
   return type annotation, and the list of `return` expressions in
   the body (so the scout knows what the current caller contract is).
3. Identifies the implicit-dict-state variable by heuristic:

   a. Local assignment `name = {...}` or `name = dict(...)` in the
      function body (first such assignment).
   b. Parameter typed as `dict`, `Dict[...]`, or `Mapping[...]`.
   c. Otherwise flag as ambiguous; list every dict-local the scout
      needs to disambiguate.

4. Greps the project for inbound callers — constructor + method call
   patterns for methods, bare-name invocations for module functions.

Usage:

    python3 .claude/skills/extract-state-type/scripts/collect_target.py \\
      --file core/services/agentic_discovery_service.py \\
      --symbol AgenticDiscoveryService.discover \\
      --project-root "$(pwd)" \\
      --output reports/extract-state-type/agentic_discovery_service__discover/targets.json

Exit status:

    0  targets.json written (target located, callers enumerated)
    1  target file or symbol not found
    2  invocation error

Output schema:

    {
      "file": "core/services/agentic_discovery_service.py",
      "symbol": "AgenticDiscoveryService.discover",
      "kind": "method",
      "lineno": 156,
      "end_lineno": 587,
      "signature": "def discover(self, base_url, site_name='', progress_callback=None, include_sitemap_urls=False)",
      "has_docstring": true,
      "docstring_first_sentence": "Main entry point. Returns result dict with sitemaps, patterns, samples.",
      "return_annotation": null,
      "return_count": 4,
      "dict_state_candidates": [
        {"name": "state", "kind": "local_assign", "lineno": 158, "ambiguous": false}
      ],
      "callers": [
        {
          "file": "core/views/sitemaps.py",
          "lineno": 402,
          "context": "discovery.discover(base_url)",
          "kind": "method_call"
        },
        ...
      ],
      "caller_count": 2
    }

Stdlib-only; runs under bare `python3`.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


DICT_STATE_TYPE_HINTS = {"dict", "Dict", "Mapping", "MutableMapping"}
SKIP_DIRS = {".venv", "__pycache__", "migrations", "node_modules", "staticfiles"}


def _find_symbol(tree: ast.Module, qualified: str) -> tuple[ast.AST | None, str, str]:
    """Locate a symbol by qualified name. Returns (node, kind, class_name).

    Handles `Cls.method`, `method` (method in any class, first match),
    and `function` (module-level function).
    """
    parts = qualified.split(".")
    if len(parts) == 2:
        class_name, method_name = parts
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for sub in node.body:
                    if (
                        isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and sub.name == method_name
                    ):
                        return sub, "method", class_name
        return None, "", ""
    # Bare name — try module-level function first, then first method
    # anywhere with that name (shorthand disambiguation).
    bare = parts[0]
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == bare
        ):
            return node, "function", ""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if (
                    isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and sub.name == bare
                ):
                    return sub, "method", node.name
    return None, "", ""


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Rebuild the signature as a string, stdlib-style.
    Does not fully preserve type annotations but captures names + defaults."""
    args = node.args
    pieces: list[str] = []
    # Positional-or-keyword args, with defaults from the right.
    defaults = args.defaults
    pos_args = args.args
    pos_defaults_start = len(pos_args) - len(defaults)
    for i, a in enumerate(pos_args):
        if i >= pos_defaults_start:
            d = defaults[i - pos_defaults_start]
            pieces.append(f"{a.arg}={ast.unparse(d)}")
        else:
            pieces.append(a.arg)
    if args.vararg:
        pieces.append(f"*{args.vararg.arg}")
    # Keyword-only args.
    for i, a in enumerate(args.kwonlyargs):
        d = args.kw_defaults[i]
        if d is None:
            pieces.append(a.arg)
        else:
            pieces.append(f"{a.arg}={ast.unparse(d)}")
    if args.kwarg:
        pieces.append(f"**{args.kwarg.arg}")
    return f"def {node.name}({', '.join(pieces)})"


def _return_annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    if node.returns is None:
        return None
    try:
        return ast.unparse(node.returns)
    except (AttributeError, ValueError):
        return None


def _docstring_first_sentence(node: ast.AST) -> tuple[bool, str]:
    doc = ast.get_docstring(node)
    if not doc:
        return False, ""
    # Split on the first period followed by whitespace/newline.
    parts = re.split(r"\.\s", doc.strip(), maxsplit=1)
    if parts and parts[0]:
        sentence = parts[0].strip()
        if not sentence.endswith("."):
            sentence += "."
        return True, sentence
    return True, doc.strip()


def _return_count(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Return):
            count += 1
    return count


def _is_dict_type_hint(annotation: ast.expr) -> bool:
    """Heuristic: does this annotation look like a dict-ish type?"""
    if annotation is None:
        return False
    text = ast.unparse(annotation) if hasattr(ast, "unparse") else ""
    for hint in DICT_STATE_TYPE_HINTS:
        if text == hint or text.startswith(f"{hint}[") or text.startswith(f"typing.{hint}"):
            return True
    return False


def _dict_state_candidates(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:
    """Enumerate plausible implicit-dict-state variables inside the
    function body. Return a list of candidates — the scout disambiguates
    if more than one is present."""
    candidates: list[dict[str, Any]] = []

    # Parameter-based candidates (dict-typed parameters).
    for param in node.args.args:
        if param.annotation is not None and _is_dict_type_hint(param.annotation):
            candidates.append(
                {
                    "name": param.arg,
                    "kind": "param_dict_typed",
                    "lineno": node.lineno,
                    "ambiguous": False,
                }
            )

    # Local-assignment candidates: `<name> = {...}` or `<name> = dict(...)`.
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                value = stmt.value
                if isinstance(value, ast.Dict):
                    candidates.append(
                        {
                            "name": target.id,
                            "kind": "local_assign_dict_literal",
                            "lineno": stmt.lineno,
                            "ambiguous": False,
                            "initial_keys": [
                                ast.unparse(k) if hasattr(ast, "unparse") else ""
                                for k in value.keys
                                if k is not None
                            ],
                        }
                    )
                elif (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "dict"
                ):
                    candidates.append(
                        {
                            "name": target.id,
                            "kind": "local_assign_dict_call",
                            "lineno": stmt.lineno,
                            "ambiguous": False,
                        }
                    )

    # Mark ambiguous if more than one candidate — scout chooses.
    if len(candidates) > 1:
        for c in candidates:
            c["ambiguous"] = True
    return candidates


def _iter_python_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for p in project_root.rglob("*.py"):
        parts = set(p.relative_to(project_root).parts)
        if parts & SKIP_DIRS:
            continue
        files.append(p)
    return files


def _grep_callers(
    project_root: Path,
    target_file: Path,
    bare_name: str,
    kind: str,
    class_name: str,
) -> list[dict[str, Any]]:
    """Grep the repo for plausible callers of the target symbol.
    Returns up to 50 matches (the scout can widen if needed)."""
    callers: list[dict[str, Any]] = []
    target_file_abs = target_file.resolve()

    # Patterns to search for.
    patterns: list[re.Pattern[str]] = []
    if kind == "method":
        # `.<name>(` — method call on any instance
        patterns.append(re.compile(rf"\.{re.escape(bare_name)}\s*\("))
        # `<ClassName>(` — constructor call (to identify creators)
        if class_name:
            patterns.append(re.compile(rf"\b{re.escape(class_name)}\s*\("))
    elif kind == "function":
        # Bare call — `<name>(` at word boundary
        patterns.append(re.compile(rf"\b{re.escape(bare_name)}\s*\("))
        # Import reference — `from X import <name>`
        patterns.append(re.compile(rf"import\s+\w+.*\b{re.escape(bare_name)}\b"))

    for path in _iter_python_files(project_root):
        if path.resolve() == target_file_abs:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for pat in patterns:
                if pat.search(line):
                    rel = path.relative_to(project_root)
                    callers.append(
                        {
                            "file": str(rel),
                            "lineno": lineno,
                            "context": line.strip()[:140],
                            "kind": "method_call" if kind == "method" else "function_call",
                        }
                    )
                    break
            if len(callers) >= 50:
                return callers
    return callers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument(
        "--symbol",
        required=True,
        help="Qualified symbol: `Cls.method` or bare function name",
    )
    parser.add_argument(
        "--project-root", required=True, type=Path, help="Repo root for caller grep"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"error: target file not found: {args.file}", file=sys.stderr)
        return 1

    try:
        source = args.file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read target file: {exc}", file=sys.stderr)
        return 2

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"error: cannot parse target file: {exc}", file=sys.stderr)
        return 2

    node, kind, class_name = _find_symbol(tree, args.symbol)
    if node is None:
        print(f"error: symbol {args.symbol!r} not found in {args.file}", file=sys.stderr)
        return 1

    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        print(f"error: {args.symbol!r} is not a function or method", file=sys.stderr)
        return 1

    has_doc, first_sent = _docstring_first_sentence(node)
    bare_name = args.symbol.rsplit(".", 1)[-1]

    try:
        file_rel = args.file.relative_to(args.project_root)
    except ValueError:
        file_rel = args.file

    callers = _grep_callers(
        project_root=args.project_root,
        target_file=args.file,
        bare_name=bare_name,
        kind=kind,
        class_name=class_name,
    )

    payload: dict[str, Any] = {
        "file": str(file_rel),
        "symbol": args.symbol,
        "kind": kind,
        "class_name": class_name or None,
        "lineno": node.lineno,
        "end_lineno": getattr(node, "end_lineno", node.lineno),
        "signature": _signature(node),
        "has_docstring": has_doc,
        "docstring_first_sentence": first_sent,
        "return_annotation": _return_annotation(node),
        "return_count": _return_count(node),
        "dict_state_candidates": _dict_state_candidates(node),
        "callers": callers,
        "caller_count": len(callers),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output}: {args.symbol} "
        f"(kind={kind}, dict_candidates={len(payload['dict_state_candidates'])}, "
        f"callers={payload['caller_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
