#!/usr/bin/env python3
"""Detect async lifecycle drift on the `/sites` surface."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from product_health import expand_paths, finding, line_for_offset, read_text  # noqa: E402
from product_topology import write_jsonl  # noqa: E402

SUFFIXES = (".py", ".js")
POLL_TIMER_RE = re.compile(r"\bset(?:Interval|Timeout)\s*\([^;\n]*(?:poll|progress|status|refresh)", re.IGNORECASE)
CLEAR_TIMER_RE = re.compile(r"\bclear(?:Interval|Timeout)\s*\(")
FETCH_RE = re.compile(r"\b(?:fetch|App\.csrfFetch)\s*\(")
DOM_MUTATION_RE = re.compile(
    r"\.(?:innerHTML|innerText|textContent|value)\s*=|"
    r"\.classList\.(?:add|remove|toggle|replace)\(|"
    r"\.(?:appendChild|insertAdjacentHTML|remove)\("
)
STALE_GUARD_RE = re.compile(
    r"\b(?:AbortController|requestGeneration|requestId|latestRequest|currentRequest|isLatest|isStale|signal|abort)\b",
    re.IGNORECASE,
)
TERMINAL_RE = re.compile(r"\b(?:complete|completed|success|succeeded|failed|error|cancelled|canceled)\b", re.IGNORECASE)
RECOVERY_RE = re.compile(r"\b(?:retry|cancel|abort|resume)\b", re.IGNORECASE)
DISPATCH_RE = re.compile(r"\.(?:delay|apply_async)\s*\(|safe_dispatch\s*\(", re.IGNORECASE)
ACTIVE_GUARD_RE = re.compile(
    r"\b(?:active|existing|running|pending)(?:_|\b)|\b(?:in_progress|idempotent|duplicate|lock|select_for_update)\b",
    re.IGNORECASE,
)


def _scan_js(path: Path, project_root: Path) -> list[dict[str, object]]:
    text = read_text(path)
    records: list[dict[str, object]] = []
    has_poll_timer = bool(POLL_TIMER_RE.search(text))
    has_clear = bool(CLEAR_TIMER_RE.search(text))
    if has_poll_timer and not has_clear:
        match = POLL_TIMER_RE.search(text)
        records.append(
            finding(
                "unguarded_polling_timer",
                path,
                line_for_offset(text, match.start() if match else 0),
                "Polling timer is started without a clear/stop path in the same module.",
                "Pair every polling timer with explicit stop logic and call it on terminal status, page teardown, and error paths.",
                project_root,
                confidence="high",
                next_skill="fix-workflow",
                guard_candidate=True,
            )
        )
    if has_poll_timer and TERMINAL_RE.search(text) and not has_clear:
        records.append(
            finding(
                "missing_terminal_poll_stop",
                path,
                line_for_offset(text, POLL_TIMER_RE.search(text).start()),
                "Progress/status polling mentions terminal states but has no timer cleanup path.",
                "Stop polling when the job reaches success, failure, or cancellation; keep terminal UI rendering separate from polling cadence.",
                project_root,
                confidence="high",
                next_skill="fix-workflow",
                guard_candidate=True,
            )
        )
    if FETCH_RE.search(text) and DOM_MUTATION_RE.search(text) and not STALE_GUARD_RE.search(text):
        match = FETCH_RE.search(text)
        records.append(
            finding(
                "missing_stale_response_guard",
                path,
                line_for_offset(text, match.start() if match else 0),
                "Async fetch flow mutates UI without an abort/request-generation/latest-response guard.",
                "Add an AbortController or monotonic request token so stale responses cannot overwrite newer UI state.",
                project_root,
                confidence="medium",
                next_skill="fix-workflow",
                guard_candidate=True,
            )
        )
    if has_poll_timer and re.search(r"\b(?:job|progress|status)\b", text, re.IGNORECASE) and not RECOVERY_RE.search(text):
        records.append(
            finding(
                "missing_recovery_control",
                path,
                line_for_offset(text, POLL_TIMER_RE.search(text).start()),
                "Job/progress UI has polling but no nearby retry, cancel, abort, or resume control.",
                "Expose the workflow's expected recovery action or document why the job is intentionally fire-and-forget.",
                project_root,
                confidence="medium",
                next_skill="fix-workflow",
                guard_candidate=False,
            )
        )
    return records


class _DispatchVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.lines = source.splitlines()
        self.findings: list[tuple[int, str]] = []
        self.stack: list[ast.AST] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        segment = ast.get_source_segment(self.source, node) or ""
        if not DISPATCH_RE.search(segment):
            self.generic_visit(node)
            return
        owner = self.stack[-1] if self.stack else node
        start = getattr(owner, "lineno", getattr(node, "lineno", 1))
        end = getattr(owner, "end_lineno", getattr(node, "end_lineno", start))
        block = "\n".join(self.lines[start - 1 : end])
        owner_names = [str(getattr(item, "name", "")) for item in self.stack if getattr(item, "name", "")]
        owner_label = ".".join(owner_names) or "<module>"
        if re.search(r"(?:start|run|queue|download|export|create)", owner_label, re.IGNORECASE) and not ACTIVE_GUARD_RE.search(block):
            self.findings.append((getattr(node, "lineno", start), owner_label))
        self.generic_visit(node)


def _scan_python(path: Path, project_root: Path) -> list[dict[str, object]]:
    text = read_text(path)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    visitor = _DispatchVisitor(text)
    visitor.visit(tree)
    records: list[dict[str, object]] = []
    for lineno, owner_name in visitor.findings:
        records.append(
            finding(
                "duplicate_job_path",
                path,
                lineno,
                f"`{owner_name}` dispatches async work without an obvious active/existing/running guard.",
                "Check for an existing live job before dispatch, or document why duplicate starts are impossible at this boundary.",
                project_root,
                confidence="medium",
                next_skill="fix-workflow",
                guard_candidate=True,
                symbol=owner_name,
            )
        )
    return records


def detect(project_root: Path, paths: list[str] | None = None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in expand_paths(project_root, paths, SUFFIXES):
        if path.suffix == ".js":
            records.extend(_scan_js(path, project_root))
        elif path.suffix == ".py":
            records.extend(_scan_python(path, project_root))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    records = detect(args.project_root.resolve(), args.paths or None)
    write_jsonl(records, args.output)
    print(f"wrote {args.output}: {len(records)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
