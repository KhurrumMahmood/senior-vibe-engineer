#!/usr/bin/env python3
"""Enumerate public symbols for /explain-code Stage 1.

Walks the AST of a target file (or every `*.py` under a target directory),
emits one entry per public symbol, and ranks them by
`(no_docstring, branch_count, LOC > 50)` descending. The `/explain-code`
orchestrator consumes the output to dispatch per-symbol annotation scouts.

Usage:

    python3 .claude/skills/explain-code/scripts/inventory_symbols.py \\
      --target core/services/agentic_discovery_service.py \\
      --output reports/explanations/services-agentic-discovery-service/targets.json \\
      --max 15

Public-symbol rule (matches `/map-subsystem` Stage 2):

- Top-level function / class / assignment with a non-leading-underscore name.
- Public methods on a class (non-leading-underscore names).
- If the module defines a module-level `__all__`, only names in `__all__`
  count as public.

Branch count is an approximation: count of AST nodes of type `If`, `For`,
`While`, `Try`, `With`, `BoolOp`, and `IfExp` within the symbol body.
Good-enough proxy for cyclomatic complexity; we don't need exact.

Exit status:

    0  targets.json written (≥ 1 symbol)
    1  target path invalid or no public symbols found
    2  invocation error

Output schema:

    {
      "target": "core/services/agentic_discovery_service.py",
      "files": ["core/services/agentic_discovery_service.py"],
      "symbol_count_total": 34,
      "public_symbol_count": 22,
      "max": 15,
      "targets": [
        {
          "symbol_key": "agentic_discovery_service__discover",
          "file": "core/services/agentic_discovery_service.py",
          "symbol": "AgenticDiscoveryService.discover",
          "kind": "method",
          "lineno": 156,
          "loc": 78,
          "branch_count": 14,
          "has_docstring": true,
          "rank_score": 14
        },
        ...
      ],
      "overflow": [
        {"symbol_key": "...", "file": "...", "symbol": "...", "reason": "budget-cap"}
      ]
    }

Stdlib-only; runs under bare `python3`.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


BRANCH_NODE_TYPES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.BoolOp,
    ast.IfExp,
)


def _is_public(name: str, dunder_all: set[str] | None) -> bool:
    """A name is public iff it doesn't start with `_` AND (if `__all__`
    is defined) appears in `__all__`."""
    if name.startswith("_"):
        return False
    if dunder_all is not None and name not in dunder_all:
        return False
    return True


def _loc(node: ast.AST) -> int:
    """Rough LOC for an AST node — last line minus start line plus one.
    Blank lines and comments count; we don't want clever."""
    end = getattr(node, "end_lineno", None)
    if end is None:
        return 1
    return max(1, end - node.lineno + 1)


def _branch_count(node: ast.AST) -> int:
    """Count branch-like AST nodes in the subtree rooted at `node`.
    Does NOT subtract `node` itself if it happens to be a branch — the
    caller is a function/class body, not a branch."""
    return sum(1 for child in ast.walk(node) if isinstance(child, BRANCH_NODE_TYPES))


def _symbol_key(file_rel: Path, symbol: str) -> str:
    """Stable key: `<basename>__<bare-name>`. Uses the module stem (not
    the full relative path) so keys stay short; collisions get the full
    qualified name appended by the caller."""
    base = file_rel.stem
    tail = symbol.rsplit(".", 1)[-1]
    return f"{base}__{tail}"


def _dunder_all(tree: ast.Module) -> set[str] | None:
    """Return the set of names in a module-level `__all__`, or None if
    no such assignment exists. Only handles `__all__ = [...]` or
    `__all__ = (...)`. Dynamic `__all__` = ignored (None)."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    names: set[str] = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
                    return names
    return None


def _inventory_file(path: Path, repo_root: Path) -> tuple[list[dict[str, Any]], int]:
    """Return (public_symbols, total_symbol_count) for one Python file.

    `total_symbol_count` counts every top-level declaration (private + public)
    for the summary stats. Public methods on public classes also count.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"warn: cannot read {path}: {exc}", file=sys.stderr)
        return [], 0

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"warn: cannot parse {path}: {exc}", file=sys.stderr)
        return [], 0

    dunder_all = _dunder_all(tree)
    file_rel = path.relative_to(repo_root) if path.is_absolute() else path
    public: list[dict[str, Any]] = []
    total = 0

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            name = node.name
            if not _is_public(name, dunder_all):
                continue
            public.append(
                _build_entry(
                    file_rel=file_rel,
                    symbol=name,
                    kind="function",
                    node=node,
                )
            )
        elif isinstance(node, ast.ClassDef):
            total += 1
            class_name = node.name
            class_public = _is_public(class_name, dunder_all)
            if class_public:
                public.append(
                    _build_entry(
                        file_rel=file_rel,
                        symbol=class_name,
                        kind="class",
                        node=node,
                    )
                )
            # Methods on a public class — enumerate regardless of class
            # visibility? Only enumerate on public classes; private
            # classes' methods aren't part of the public surface.
            if class_public:
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = sub.name
                        # Special-case: `__init__` is a public constructor,
                        # everything else starting with `_` is private.
                        if method_name.startswith("_") and method_name != "__init__":
                            continue
                        public.append(
                            _build_entry(
                                file_rel=file_rel,
                                symbol=f"{class_name}.{method_name}",
                                kind="method",
                                node=sub,
                            )
                        )
        elif isinstance(node, ast.Assign):
            total += 1
            # Module-level public constants — rare target for /explain-code
            # but surface them for completeness.
            for target in node.targets:
                if isinstance(target, ast.Name) and _is_public(target.id, dunder_all):
                    public.append(
                        _build_entry(
                            file_rel=file_rel,
                            symbol=target.id,
                            kind="module-var",
                            node=node,
                        )
                    )

    return public, total


def _build_entry(
    *,
    file_rel: Path,
    symbol: str,
    kind: str,
    node: ast.AST,
) -> dict[str, Any]:
    loc = _loc(node)
    branches = _branch_count(node)
    has_doc = False
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        has_doc = bool(ast.get_docstring(node))
    return {
        "symbol_key": _symbol_key(file_rel, symbol),
        "file": str(file_rel),
        "symbol": symbol,
        "kind": kind,
        "lineno": node.lineno,
        "loc": loc,
        "branch_count": branches,
        "has_docstring": has_doc,
        "rank_score": _rank_score(
            loc=loc, branches=branches, has_doc=has_doc, kind=kind
        ),
    }


def _rank_score(*, loc: int, branches: int, has_doc: bool, kind: str = "function") -> int:
    """Higher = more worth annotating. Rule:
       - missing docstring: +10
       - branch count: direct contribution
       - LOC > 50: +5
       - classes are capped at the raw score of their heaviest method
         when that method is also in the list (handled post-pass in
         `_demote_shadowed_classes`) — here we just apply a flat cap
         so very large class bodies don't dominate.
    Deliberately coarse — ranking is a hint, not a verdict."""
    score = branches
    if not has_doc:
        score += 10
    if loc > 50:
        score += 5
    # Classes frequently inherit their branch count from every method;
    # cap them so an omnibus class doesn't push every method off the
    # annotation budget. Methods and functions are the meaningful unit.
    if kind == "class":
        score = min(score, 20)
    return score


def _resolve_collisions(entries: list[dict[str, Any]]) -> None:
    """If two entries share the same `symbol_key`, append the full symbol
    to disambiguate. Mutates in place."""
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["symbol_key"]] = counts.get(e["symbol_key"], 0) + 1
    for e in entries:
        if counts[e["symbol_key"]] > 1:
            # Append the qualified symbol (dot-replaced) so the key stays
            # filesystem-safe.
            suffix = e["symbol"].replace(".", "_")
            e["symbol_key"] = f"{e['symbol_key']}__{suffix}"


def _collect_files(target: Path, repo_root: Path) -> list[Path]:
    """Return a list of `*.py` files to inventory.

    - Single file: [target]
    - Directory: every `*.py` under target excluding `__pycache__/`,
      `migrations/`, and tests.
    """
    if target.is_file():
        if target.suffix != ".py":
            return []
        return [target]
    if target.is_dir():
        files: list[Path] = []
        for p in sorted(target.rglob("*.py")):
            parts = set(p.relative_to(target).parts)
            if "__pycache__" in parts or "migrations" in parts:
                continue
            # Skip test files — they're not public surface.
            if p.name.startswith("tests_") or p.name.startswith("test_"):
                continue
            files.append(p)
        return files
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="File or directory")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--max",
        type=int,
        default=15,
        help="Max annotated symbols (budget cap; default 15)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repo root for computing file paths (default: cwd)",
    )
    args = parser.parse_args()

    if not args.target.exists():
        print(f"error: target not found: {args.target}", file=sys.stderr)
        return 1

    files = _collect_files(args.target, args.repo_root)
    if not files:
        print(f"error: no Python files under {args.target}", file=sys.stderr)
        return 1

    all_public: list[dict[str, Any]] = []
    total_symbols = 0
    for f in files:
        entries, file_total = _inventory_file(f, args.repo_root)
        all_public.extend(entries)
        total_symbols += file_total

    if not all_public:
        print(f"error: no public symbols in {args.target}", file=sys.stderr)
        return 1

    _resolve_collisions(all_public)
    all_public.sort(key=lambda e: e["rank_score"], reverse=True)

    budget = max(1, args.max)
    selected = all_public[:budget]
    overflow = [
        {
            "symbol_key": e["symbol_key"],
            "file": e["file"],
            "symbol": e["symbol"],
            "reason": "budget-cap",
        }
        for e in all_public[budget:]
    ]

    payload = {
        "target": str(args.target),
        "files": [str(f.relative_to(args.repo_root)) if f.is_absolute() else str(f) for f in files],
        "symbol_count_total": total_symbols,
        "public_symbol_count": len(all_public),
        "max": budget,
        "targets": selected,
        "overflow": overflow,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output}: {len(selected)} annotated / "
        f"{len(all_public)} public / {total_symbols} total"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
