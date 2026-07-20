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
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

sys.dont_write_bytecode = True

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
TYPESCRIPT_SKIP_DIRS = {
    "__tests__",
    "build",
    "coverage",
    "dist",
    "fixture",
    "fixtures",
    "generated",
    "spec",
    "specs",
    "test",
    "tests",
    "vendor",
}
SCRIPT_SKIP_GLOBS = (
    "*.d.ts", "*.d.tsx", "*.generated.ts", "*.generated.tsx",
    "*.min.ts", "*.min.tsx", "*-min.ts", "*-min.tsx",
    "*.bundle.ts", "*.bundle.tsx", "*.spec.ts", "*.spec.tsx",
    "*.test.ts", "*.test.tsx", "test_*.ts", "test_*.tsx",
    "tests_*.ts", "tests_*.tsx", "*_test.ts", "*_test.tsx",
    "*.generated.js", "*.generated.jsx", "*.generated.mjs", "*.generated.cjs",
    "*.min.js", "*.min.jsx", "*.min.mjs", "*.min.cjs",
    "*-min.js", "*-min.jsx", "*-min.mjs", "*-min.cjs",
    "*.bundle.js", "*.bundle.jsx", "*.bundle.mjs", "*.bundle.cjs",
    "*.spec.js", "*.spec.jsx", "*.spec.mjs", "*.spec.cjs",
    "*.test.js", "*.test.jsx", "*.test.mjs", "*.test.cjs",
    "test_*.js", "test_*.jsx", "test_*.mjs", "test_*.cjs",
    "tests_*.js", "tests_*.jsx", "tests_*.mjs", "tests_*.cjs",
    "*_test.js", "*_test.jsx", "*_test.mjs", "*_test.cjs",
)
SCRIPT_SUFFIXES = {
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
}
GO_SKIP_DIRS = {
    "__tests__",
    "build",
    "coverage",
    "dist",
    "fixture",
    "fixtures",
    "gen",
    "generated",
    "spec",
    "specs",
    "test",
    "testdata",
    "tests",
    "vendor",
}
GO_SKIP_GLOBS = (
    "*_test.go",
    "*.generated.go",
    "*_generated.go",
)
GO_MIN_VERSION = (1, 22, 0)

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


class TypeScriptExtractionError(RuntimeError):
    """Raised when syntax-only TypeScript facts cannot be established."""


class GoExtractionError(RuntimeError):
    """Raised when syntax-only Go facts cannot be established honestly."""


@dataclass(frozen=True)
class ScanResult:
    """Final detector records plus bounded language-level execution evidence."""

    records: list[dict[str, Any]]
    status: str = "complete"
    analysis: dict[str, Any] | None = None


def _relpath(path: Path | str, project_root: Path) -> str:
    if not isinstance(path, Path):
        return path
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _infer_surface(file: str) -> str:
    if file.startswith("app/pages/sites") or file.startswith("templates/core/site_config"):
        return "sites_template_or_view"
    if file.startswith("app/site_management") or file.startswith("app/api/"):
        return "sites_backend"
    if file.startswith("app/services/sites"):
        return "sites_service"
    if file.startswith("static/js/"):
        return "sites_frontend"
    if file.startswith(".claude/skills"):
        return "skill"
    if file.startswith(".claude/docs") or file.startswith("docs/"):
        return "docs"
    if file.startswith("tests/") or file.startswith("testing/"):
        return "tests"
    return "sites_surface"


def finding(
    pattern: str,
    path: Path | str,
    lineno: int,
    summary: str,
    recommendation: str,
    project_root: Path,
    *,
    confidence: str = "medium",
    surface: str | None = None,
    next_skill: str = "triage-debt",
    guard_candidate: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build the historical advisory finding shape without a shared runtime."""
    file = _relpath(path, project_root)
    record: dict[str, Any] = {
        "pattern": pattern,
        "file": file,
        "lineno": lineno,
        "summary": summary.strip(),
        "recommendation": recommendation.strip(),
        "confidence": confidence,
        "surface": surface or _infer_surface(file),
        "next_skill": next_skill,
        "guard_candidate": guard_candidate,
    }
    record.update(extra)
    return record


def normalize_record(
    record: dict[str, Any],
    project_root: Path,
    *,
    default_confidence: str = "medium",
    next_skill: str = "triage-debt",
    guard_candidate: bool = False,
) -> dict[str, Any]:
    """Preserve the selected skill's established JSONL compatibility fields."""
    file = str(record.get("file", ""))
    return {
        **record,
        "lineno": int(record.get("lineno") or 1),
        "summary": str(record.get("summary") or record.get("evidence") or "").strip(),
        "recommendation": str(record.get("recommendation") or "Review this advisory finding.").strip(),
        "confidence": str(record.get("confidence") or default_confidence),
        "surface": str(record.get("surface") or _infer_surface(file)),
        "next_skill": str(record.get("next_skill") or next_skill),
        "guard_candidate": bool(record.get("guard_candidate", guard_candidate)),
    }


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


def _typescript_complexity(path: Path, project_root: Path) -> list[dict[str, Any]]:
    """Return Compiler API syntax facts for supported TypeScript functions."""
    launcher = Path(__file__).resolve().with_name("detect_typescript_complexity.mjs")
    try:
        result = subprocess.run(
            ["node", str(launcher), "--file", str(path), "--project-root", str(project_root)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise TypeScriptExtractionError(f"cannot run bundled TypeScript parser: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown parser failure"
        raise TypeScriptExtractionError(detail)
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TypeScriptExtractionError("bundled TypeScript parser emitted invalid JSON") from exc
    if not isinstance(records, list):
        raise TypeScriptExtractionError("bundled TypeScript parser emitted a non-list result")
    validated: list[dict[str, Any]] = []
    for record in records:
        try:
            validated.append({
                "name": str(record["name"]),
                "symbol": str(record["symbol"]),
                "kind": str(record["kind"]),
                "branch_score": int(record["branch_score"]),
                "lineno": int(record["lineno"]),
                "end_lineno": int(record["end_lineno"]),
                "loc": int(record["loc"]),
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise TypeScriptExtractionError("bundled TypeScript parser emitted an invalid function") from exc
    return validated


def _script_high_branch_records(
    path: Path, project_root: Path, language: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for fact in _typescript_complexity(path, project_root):
        branch_score = int(fact["branch_score"])
        loc = int(fact["loc"])
        if branch_score < 18 and not (branch_score >= 12 and loc >= 120):
            continue
        symbol = str(fact["symbol"])
        records.append(
            finding(
                "high-branch-function",
                path,
                int(fact["lineno"]),
                f"`{symbol}` has approximate syntactic branch score {branch_score} over {loc} LOC.",
                "Read the block and its input sizes before changing it; preserve observable "
                f"behavior with native {language} tests if a behavior-backed boundary emerges.",
                project_root,
                confidence="medium" if branch_score >= 18 else "low",
                next_skill="manual-review",
                guard_candidate=False,
                symbol=symbol,
                impact=min(90, branch_score * 3 + loc // 20),
                category="structural",
                branch_score=branch_score,
                loc=loc,
                end_lineno=int(fact["end_lineno"]),
                kind=str(fact["kind"]),
                language=language,
                analyzer="typescript-compiler-api",
            )
        )
    return records


def _go_toolchain() -> tuple[str, str]:
    """Resolve and validate the host Go toolchain without bundling one."""
    executable = shutil.which("go")
    if executable is None:
        raise GoExtractionError("Go toolchain is unavailable on PATH")
    try:
        result = subprocess.run(
            [executable, "version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise GoExtractionError(f"cannot run Go toolchain: {exc}") from exc
    rendered = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise GoExtractionError(f"cannot determine Go version: {rendered or 'unknown error'}")
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.(\d+))?\b", rendered)
    if match is None:
        raise GoExtractionError(f"cannot parse Go version: {rendered or 'unknown version'}")
    version = tuple(int(part or 0) for part in match.groups())
    if version < GO_MIN_VERSION:
        minimum = ".".join(str(part) for part in GO_MIN_VERSION)
        raise GoExtractionError(f"Go detector requires Go >= {minimum}; found go{'.'.join(map(str, version))}")
    return executable, f"go{'.'.join(map(str, version))}"


def _go_complexity(path: Path, project_root: Path) -> dict[str, Any]:
    """Return stdlib parser facts for one eligible Go source file."""
    executable, _version = _go_toolchain()
    launcher = Path(__file__).resolve().with_name("detect_go_complexity.go")
    try:
        result = subprocess.run(
            [
                executable,
                "run",
                str(launcher),
                "--file",
                str(path),
                "--project-root",
                str(project_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GoExtractionError(f"cannot run bundled Go parser: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown parser failure"
        raise GoExtractionError(detail)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GoExtractionError("bundled Go parser emitted invalid JSON") from exc
    if not isinstance(payload, dict):
        raise GoExtractionError("bundled Go parser emitted a non-object result")
    if payload.get("schema_version") != 1:
        raise GoExtractionError("bundled Go parser emitted an unsupported schema")
    if payload.get("status") not in {"complete", "partial"}:
        raise GoExtractionError("bundled Go parser emitted an invalid status")
    if payload.get("analyzer") != "go-parser-go-ast":
        raise GoExtractionError("bundled Go parser emitted an invalid analyzer")
    if not isinstance(payload.get("go_version"), str) or not payload["go_version"]:
        raise GoExtractionError("bundled Go parser omitted its Go version")
    if not isinstance(payload.get("records"), list) or not isinstance(payload.get("skipped"), list):
        raise GoExtractionError("bundled Go parser emitted invalid records")
    return payload


def _go_high_branch_records(
    path: Path, project_root: Path, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for fact in payload["records"]:
        try:
            branch_score = int(fact["branch_score"])
            loc = int(fact["loc"])
            symbol = str(fact["symbol"])
            kind = str(fact["kind"])
            lineno = int(fact["lineno"])
            end_lineno = int(fact["end_lineno"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GoExtractionError("bundled Go parser emitted an invalid function") from exc
        if branch_score < 18 and not (branch_score >= 12 and loc >= 120):
            continue
        records.append(
            finding(
                "high-branch-function",
                path,
                lineno,
                f"`{symbol}` has approximate syntactic branch score {branch_score} over {loc} LOC.",
                "Read the block and its input sizes before changing it; preserve observable "
                "behavior with native Go tests if a behavior-backed boundary emerges.",
                project_root,
                confidence="medium" if branch_score >= 18 else "low",
                next_skill="manual-review",
                guard_candidate=False,
                symbol=symbol,
                impact=min(90, branch_score * 3 + loc // 20),
                category="structural",
                branch_score=branch_score,
                loc=loc,
                end_lineno=end_lineno,
                kind=kind,
                language="go",
                analyzer="go-parser-go-ast",
            )
        )
    return records


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


def _typescript_path_is_excluded(path: Path, project_root: Path) -> bool:
    try:
        parts = path.relative_to(project_root).parts
    except ValueError:
        parts = path.parts
    skipped_dirs = SKIP_DIRS | TYPESCRIPT_SKIP_DIRS
    if any(part.lower() in skipped_dirs for part in parts[:-1]):
        return True
    return any(fnmatch.fnmatchcase(path.name, glob) for glob in SCRIPT_SKIP_GLOBS)


def _iter_script_files(
    project_root: Path, paths: Iterable[str], language: str
) -> list[Path]:
    suffixes = SCRIPT_SUFFIXES[language]
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
            if candidate.is_file() and candidate.suffix.lower() in suffixes:
                found.append(candidate)
            elif candidate.is_dir():
                found.extend(
                    path
                    for path in candidate.rglob("*")
                    if path.is_file() and path.suffix.lower() in suffixes
                )
    clean: list[Path] = []
    for path in found:
        if _typescript_path_is_excluded(path, project_root):
            continue
        clean.append(path.resolve())
    return sorted(dict.fromkeys(clean))


def _go_exclusion_reason(path: Path, project_root: Path) -> str | None:
    if path.is_symlink():
        return "symlink_boundary"
    try:
        parts = path.relative_to(project_root).parts
    except ValueError:
        return "outside_project_root"
    directories = {part.lower() for part in parts[:-1]}
    if directories & SKIP_DIRS:
        return "excluded_directory"
    if directories & GO_SKIP_DIRS:
        return "go_excluded_directory"
    if any(fnmatch.fnmatchcase(path.name, glob) for glob in GO_SKIP_GLOBS):
        return "generated_or_test_filename"
    return None


def _iter_go_files(
    project_root: Path, paths: Iterable[str]
) -> tuple[list[Path], list[dict[str, str]]]:
    found: list[Path] = []
    excluded: list[dict[str, str]] = []
    seen: set[Path] = set()
    seen_exclusions: set[tuple[str, str]] = set()

    def note_exclusion(path: Path, reason: str) -> None:
        relative = _relpath(path, project_root)
        key = (relative, reason)
        if key not in seen_exclusions:
            seen_exclusions.add(key)
            excluded.append({"file": relative, "reason": reason})

    for raw in paths:
        raw_path = Path(raw)
        candidates: Iterable[Path]
        if any(ch in raw for ch in "*?[]"):
            candidates = project_root.glob(raw)
        else:
            candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
            candidates = [candidate]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() == ".go":
                possible = [candidate]
            elif candidate.is_dir():
                possible = [
                    path for path in candidate.rglob("*.go")
                    if path.is_file() or path.is_symlink()
                ]
            else:
                possible = []
            for path in possible:
                reason = _go_exclusion_reason(path, project_root)
                if reason is not None:
                    note_exclusion(path, reason)
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(resolved)
    return sorted(found), sorted(excluded, key=lambda row: (row["file"], row["reason"]))


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


def detect_scan(
    project_root: Path,
    paths: list[str],
    *,
    include_tests: bool = False,
    max_findings: int = 80,
    languages: set[str] | None = None,
) -> ScanResult:
    project_root = project_root.resolve()
    records: list[dict[str, Any]] = []
    wanted = languages or {"go", "javascript", "python", "typescript"}
    status = "complete"
    analysis: dict[str, Any] = {}
    if "python" in wanted:
        for path in _iter_python_files(project_root, paths, include_tests):
            try:
                text = path.read_text(encoding="utf-8")
                tree = ast.parse(text)
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            visitor = ComplexityVisitor(path, project_root)
            visitor.visit(tree)
            records.extend(visitor.records)
    for language in ("javascript", "typescript"):
        if language not in wanted:
            continue
        for path in _iter_script_files(project_root, paths, language):
            try:
                records.extend(_script_high_branch_records(path, project_root, language))
            except TypeScriptExtractionError as exc:
                raise TypeScriptExtractionError(f"{path}: {exc}") from exc

    if "go" in wanted:
        go_files, exclusions = _iter_go_files(project_root, paths)
        analyzed = 0
        ambiguous: list[dict[str, str]] = []
        actual_version: str | None = None
        for path in go_files:
            try:
                payload = _go_complexity(path, project_root)
            except GoExtractionError as exc:
                raise GoExtractionError(f"{path}: {exc}") from exc
            actual_version = str(payload["go_version"])
            skipped = payload["skipped"]
            if payload["status"] == "partial":
                status = "partial"
                for row in skipped:
                    if not isinstance(row, dict) or row.get("reason") != "build-constraint-ambiguous":
                        raise GoExtractionError("bundled Go parser emitted invalid partial evidence")
                    ambiguous.append({"file": str(row.get("file", "")), "reason": "build-constraint-ambiguous"})
                continue
            if skipped:
                for row in skipped:
                    if not isinstance(row, dict) or not isinstance(row.get("file"), str) or not isinstance(row.get("reason"), str):
                        raise GoExtractionError("bundled Go parser emitted invalid skipped evidence")
                    exclusions.append({"file": row["file"], "reason": row["reason"]})
                continue
            analyzed += 1
            records.extend(_go_high_branch_records(path, project_root, payload))
        minimum = ".".join(str(part) for part in GO_MIN_VERSION)
        analysis["go"] = {
            "status": status if go_files else "complete",
            "analyzer": "go-parser-go-ast",
            "minimum_go_version": minimum,
            "actual_go_version": actual_version,
            "files": {
                "eligible": len(go_files),
                "analyzed": analyzed,
                "excluded": len(exclusions),
                "ambiguous": len(ambiguous),
            },
            "exclusions": sorted(exclusions, key=lambda row: (row["file"], row["reason"])),
            "ambiguous": sorted(ambiguous, key=lambda row: (row["file"], row["reason"])),
            "limitations": (
                ["Build-constrained Go source was not evaluated; findings cover only analyzed files."]
                if ambiguous else []
            ),
        }

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
    return ScanResult(records=records[:max_findings], status=status, analysis=analysis or None)


def detect(
    project_root: Path,
    paths: list[str],
    *,
    include_tests: bool = False,
    max_findings: int = 80,
    languages: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Compatibility wrapper for callers that consume JSONL records only."""
    return detect_scan(
        project_root,
        paths,
        include_tests=include_tests,
        max_findings=max_findings,
        languages=languages,
    ).records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Files, directories, or globs to scan.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--max-findings", type=_positive_int, default=80)
    parser.add_argument(
        "--language",
        action="append",
        choices=("go", "javascript", "python", "typescript"),
        default=[],
        help="Restrict scanning to one or more supported languages.",
    )
    args = parser.parse_args(argv)

    try:
        scan = detect_scan(
            args.project_root,
            args.paths,
            include_tests=args.include_tests,
            max_findings=args.max_findings,
            languages=set(args.language) or None,
        )
    except (TypeScriptExtractionError, GoExtractionError) as exc:
        print(f"[find-complexity-hotspots] ERROR: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in scan.records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"wrote {len(scan.records)} findings to {args.output} (status={scan.status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
