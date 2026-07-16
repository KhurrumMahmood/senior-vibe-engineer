#!/usr/bin/env python3
"""Detect likely Python/Django complexity hotspots.

This is a heuristic lead generator. It intentionally avoids imports,
Django setup, and database access so it can run quickly inside read-only
skill scans.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

# Route Python parsing through the shared per-language adapter registry
# (ADR 0032). The complexity analysis is Python/Django-specific (nested
# loops, ORM-in-loop, branch scoring), so this stays a Python-only
# consumer: ask the registry for the file's adapter and only proceed when
# it exposes the raw `ast.Module` (CAP_PYTHON_AST), keeping the existing
# visitor. Wire the repo `scripts/` dir onto sys.path so the package
# imports when this skill script runs standalone.
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _lib.lang_adapter import (  # noqa: E402
    CAP_PYTHON_AST,
    AnalysisFailure,
    get_adapter,
)
from product_health import finding, normalize_record  # noqa: E402


SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "migrations",
    "reports",
}
TEST_GLOBS = ("test_*.py", "tests_*.py", "tests.py", "conftest.py")

QUERYSET_METHODS = {
    "aggregate",
    "all",
    "annotate",
    "count",
    "create",
    "earliest",
    "exclude",
    "exists",
    "filter",
    "first",
    "get",
    "get_or_create",
    "in_bulk",
    "last",
    "latest",
    "order_by",
    "prefetch_related",
    "select_for_update",
    "select_related",
    "update",
    "update_or_create",
    "values",
    "values_list",
}
QUERYSET_FLUENT_METHODS = {
    "aggregate",
    "annotate",
    "exclude",
    "filter",
    "order_by",
    "prefetch_related",
    "select_for_update",
    "select_related",
    "values_list",
}
QUERYSET_AMBIGUOUS_METHODS = {
    "all",
    "count",
    "create",
    "earliest",
    "exists",
    "first",
    "get",
    "get_or_create",
    "in_bulk",
    "last",
    "latest",
    "update",
    "update_or_create",
    "values",
}
REPEATED_SCAN_CALLS = {"filter", "map", "sum", "any", "all", "min", "max", "list", "tuple"}
BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)


@dataclass(frozen=True)
class LoopFrame:
    lineno: int
    end_lineno: int
    symbol: str


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, project_root: Path) -> None:
        self.path = path
        self.project_root = project_root
        self.records: list[dict[str, Any]] = []
        self.loop_stack: list[LoopFrame] = []
        self.symbol_stack: list[str] = []

    @property
    def symbol(self) -> str:
        return ".".join(self.symbol_stack) if self.symbol_stack else "<module>"

    def add(
        self,
        node: ast.AST,
        pattern: str,
        summary: str,
        recommendation: str,
        *,
        confidence: str,
        impact: int,
        category: str,
    ) -> None:
        self.records.append(
            finding(
                pattern,
                self.path,
                getattr(node, "lineno", 1),
                summary,
                recommendation,
                self.project_root,
                confidence=confidence,
                next_skill="fix-workflow",
                guard_candidate=False,
                symbol=self.symbol,
                impact=impact,
                category=category,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbol_stack.append(node.name)
        self.generic_visit(node)
        self.symbol_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.symbol_stack.append(node.name)
        self.generic_visit(node)
        self._maybe_record_high_branch_function(node)
        self.symbol_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        if self.loop_stack:
            self.add(
                node,
                "nested-loop",
                f"`{self.symbol}` contains a loop nested under another loop; "
                "large inputs may turn this into repeated pairwise scans.",
                "Read the loop contract, then consider a precomputed dict/set, grouping, "
                "sort+two-pointer pass, or batching if input sizes are large.",
                confidence="medium",
                impact=80,
                category="algorithmic",
            )
        if isinstance(node, (ast.For, ast.AsyncFor)):
            self.visit(node.target)
            self.visit(node.iter)
        elif isinstance(node, ast.While):
            self.visit(node.test)
        self.loop_stack.append(
            LoopFrame(
                lineno=getattr(node, "lineno", 1),
                end_lineno=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                symbol=self.symbol,
            )
        )
        for child in list(node.body) + list(node.orelse):
            self.visit(child)
        self.loop_stack.pop()

    def visit_Compare(self, node: ast.Compare) -> None:
        if self.loop_stack and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            rhs = node.comparators[-1] if node.comparators else None
            if not _looks_constant_membership(rhs):
                self.add(
                    node,
                    "membership-scan-in-loop",
                    f"`{self.symbol}` performs membership testing inside a loop; "
                    "list/QuerySet/string membership can become repeated linear work.",
                    "If equality semantics allow it, build a set/dict once before the loop. "
                    "Preserve normalization, duplicate handling, and observable ordering.",
                    confidence="medium",
                    impact=60,
                    category="algorithmic",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.loop_stack:
            dotted = _call_dotted(node.func)
            method = dotted.rsplit(".", 1)[-1] if dotted else ""
            if method in QUERYSET_METHODS and _looks_like_query_call(dotted):
                self.add(
                    node,
                    "django-query-in-loop",
                    f"`{self.symbol}` calls `{dotted}` inside a loop; "
                    "this may be N+1 ORM work or repeated query shaping.",
                    "Check whether a bulk query, `in_bulk`, grouped lookup, "
                    "`select_related`, or `prefetch_related` can move the query work "
                    "outside the loop while preserving filters and ordering.",
                    confidence="high" if ".objects." in dotted or method in {"get", "filter", "count", "exists"} else "medium",
                    impact=95,
                    category="django",
                )
            elif method in {"sort", "sorted"} or dotted == "sorted":
                self.add(
                    node,
                    "sort-in-loop",
                    f"`{self.symbol}` sorts inside a loop; repeated O(n log n) work "
                    "can dominate larger collections.",
                    "If the same input is reused, sort once outside the loop. If each "
                    "item has its own candidate set, measure first; for top-k selection, "
                    "consider heap/select logic instead of fully sorting every list.",
                    confidence="high",
                    impact=75,
                    category="algorithmic",
                )
            elif dotted in REPEATED_SCAN_CALLS or method in REPEATED_SCAN_CALLS:
                self.add(
                    node,
                    "repeated-scan-in-loop",
                    f"`{self.symbol}` calls `{dotted or method}` inside a loop; "
                    "this may repeatedly scan another collection.",
                    "Consider precomputing an index/grouping or combining passes if the "
                    "inner collection can be large.",
                    confidence="low",
                    impact=45,
                    category="algorithmic",
                )
        self.generic_visit(node)

    def _maybe_record_high_branch_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        loc = max(1, end - start + 1)
        branch_score = _branch_score(node)
        if branch_score < 18 and not (branch_score >= 12 and loc >= 120):
            return
        self.records.append(
            finding(
                "high-branch-function",
                self.path,
                start,
                f"`{self.symbol}` has approximate branch score {branch_score} over {loc} LOC.",
                "Use this as a readability/refactor lead. First extract the hidden contract "
                "with `/explain-code`; only split when a behavior-backed boundary is clear.",
                self.project_root,
                confidence="medium" if branch_score >= 18 else "low",
                next_skill="explain-code",
                guard_candidate=False,
                symbol=self.symbol,
                impact=min(90, branch_score * 3 + loc // 20),
                category="structural",
                branch_score=branch_score,
                loc=loc,
            )
        )


def _call_dotted(node: ast.AST) -> str:
    parts: list[str] = []
    current: ast.AST = node
    while True:
        if isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        elif isinstance(current, ast.Name):
            parts.append(current.id)
            break
        elif isinstance(current, ast.Call):
            inner = _call_dotted(current.func)
            if inner:
                parts.append(f"{inner}()")
            break
        else:
            return ""
    return ".".join(reversed(parts))


def _looks_like_query_call(dotted: str) -> bool:
    if not dotted:
        return False
    method = dotted.rsplit(".", 1)[-1]
    if method not in QUERYSET_METHODS:
        return False
    if ".objects." in dotted or ".objects()" in dotted:
        return True
    receiver = dotted.rsplit(".", 1)[0]
    receiver_tail = receiver.rsplit(".", 1)[-1]
    receiver_lower = receiver_tail.lower()
    strong_receiver = (
        receiver_tail == "objects"
        or receiver_lower in {"queryset", "qs", "manager"}
        or receiver_lower.endswith(("_qs", "_queryset", "_manager"))
        or "queryset" in receiver_lower
        or (bool(receiver_tail) and receiver_tail[0].isupper())
    )
    if strong_receiver:
        return True
    if method in QUERYSET_AMBIGUOUS_METHODS:
        # `dict.get`, `list.count`, and `Path.exists` dominate false positives
        # in host-a's transformation-heavy code. Require a strong receiver for
        # these ambiguous names.
        return False
    return method in QUERYSET_FLUENT_METHODS


def _looks_constant_membership(node: ast.AST | None) -> bool:
    if isinstance(node, (ast.Set, ast.Tuple)) and len(node.elts) <= 8:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    return False


def _branch_score(node: ast.AST) -> int:
    score = 0
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, BRANCH_NODES):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(1, len(child.values) - 1)
        elif isinstance(child, ast.IfExp):
            score += 1
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += len(child.generators)
    return score


def _iter_python_files(project_root: Path, paths: Iterable[str], include_tests: bool) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        raw_path = Path(raw)
        candidates: Iterable[Path]
        if any(ch in raw for ch in "*?[]"):
            candidates = project_root.glob(raw)
        else:
            candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
            candidates = [candidate]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix == ".py":
                found.append(candidate)
            elif candidate.is_dir():
                found.extend(candidate.rglob("*.py"))
    clean: list[Path] = []
    for path in found:
        parts = set(path.parts)
        if parts & SKIP_DIRS:
            continue
        if not include_tests and any(fnmatch.fnmatchcase(path.name, glob) for glob in TEST_GLOBS):
            continue
        clean.append(path.resolve())
    return sorted(dict.fromkeys(clean))


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str, str]] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("file")),
            int(record.get("lineno") or 1),
            str(record.get("pattern")),
            str(record.get("symbol")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def _typed_python_tree(adapter: Any, text: str, path: Path) -> ast.Module:
    """Parse once through the WP4 compatibility seam with typed failures."""
    parse = getattr(adapter, "parse", None)
    if not callable(parse):
        raise AnalysisFailure(
            "unsupported_capability",
            adapter=adapter.name,
            path=path.as_posix(),
            capability=CAP_PYTHON_AST,
            detail="adapter advertises no Python compatibility-tree accessor",
        )
    try:
        tree = parse(text)
    except AnalysisFailure:
        raise
    except Exception as exc:
        raise AnalysisFailure(
            "corrupt_output",
            adapter=adapter.name,
            path=path.as_posix(),
            capability=CAP_PYTHON_AST,
            detail=f"invalid compatibility-tree output: {exc}",
        ) from exc
    if tree is None:
        raise AnalysisFailure(
            "parse_error",
            adapter=adapter.name,
            path=path.as_posix(),
            capability=CAP_PYTHON_AST,
            detail="Python syntax error",
        )
    if not isinstance(tree, ast.Module):
        raise AnalysisFailure(
            "corrupt_output",
            adapter=adapter.name,
            path=path.as_posix(),
            capability=CAP_PYTHON_AST,
            detail=f"expected ast.Module, got {type(tree).__name__}",
        )
    return tree


def detect(
    project_root: Path,
    paths: list[str],
    *,
    include_tests: bool = False,
    max_findings: int = 80,
) -> list[dict[str, Any]]:
    project_root = project_root.resolve()
    records: list[dict[str, Any]] = []
    for path in _iter_python_files(project_root, paths, include_tests):
        # The nested-control-flow visitor requires Python's compatibility tree.
        # Parse exactly once and reuse that tree; the typed wrapper converts the
        # compatibility seam's optional/exceptional outcomes into loud failures.
        adapter = get_adapter(path, capability=CAP_PYTHON_AST)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise AnalysisFailure(
                "tool_failure",
                adapter=adapter.name,
                path=path.as_posix(),
                capability=CAP_PYTHON_AST,
                detail=f"could not read source: {exc}",
            ) from exc
        tree = _typed_python_tree(adapter, text, path)
        visitor = ComplexityVisitor(path, project_root)
        visitor.visit(tree)
        records.extend(visitor.records)

    records = [normalize_record(record, project_root) for record in _dedupe(records)]
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    records.sort(
        key=lambda r: (
            confidence_rank.get(str(r.get("confidence")), 9),
            -int(r.get("impact") or 0),
            str(r.get("file")),
            int(r.get("lineno") or 1),
        )
    )
    return records[:max_findings]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files, directories, or globs to scan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--max-findings", type=_positive_int, default=80)
    args = parser.parse_args(argv)

    records = detect(
        args.project_root,
        args.paths,
        include_tests=args.include_tests,
        max_findings=args.max_findings,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"wrote {len(records)} findings to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
