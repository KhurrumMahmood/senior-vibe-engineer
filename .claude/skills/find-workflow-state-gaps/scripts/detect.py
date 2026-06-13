#!/usr/bin/env python3
"""Detect workflow state coverage gaps."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from product_health import expand_paths, finding, load_module, normalize_record, read_text  # noqa: E402
from product_topology import write_jsonl  # noqa: E402

SUFFIXES = (".js", ".html")
WORKFLOW_RE = re.compile(
    r"\b(?:site|workflow|download|export|progress|job|poll|status|ptid|field|brand|discovery|image|page|training)\b",
    re.IGNORECASE,
)
ASYNC_RE = re.compile(r"\b(?:fetch|csrfFetch|poll|progress|job|download|export|resume|status)\b", re.IGNORECASE)
STATE_PATTERNS = {
    "loading": re.compile(r"\b(?:loading|spinner|busy|skeleton|in_progress|pending)\b", re.IGNORECASE),
    "empty": re.compile(r"\b(?:empty|no\s+(?:data|results|items|pages|images|brands)|zero-state)\b", re.IGNORECASE),
    "failure": re.compile(r"\b(?:failed|failure|error|exception|cancelled|canceled)\b", re.IGNORECASE),
    "recovery": re.compile(r"\b(?:retry|cancel|resume|abort|try\s+again)\b", re.IGNORECASE),
    "disabled": re.compile(r"\b(?:disabled|aria-disabled|is-disabled|disable)\b", re.IGNORECASE),
    "mobile": re.compile(r"\b(?:mobile|responsive|sm:|md:|lg:|stack|grid-cols|@media)\b", re.IGNORECASE),
}


def _is_workflow_file(path: Path, text: str) -> bool:
    name = path.name.lower()
    if name.startswith(("site-config", "export-", "download-")):
        return True
    return bool(WORKFLOW_RE.search(text))


def _state_gap(
    pattern: str,
    path: Path,
    project_root: Path,
    state_name: str,
    recommendation: str,
    confidence: str = "medium",
) -> dict[str, object]:
    return finding(
        pattern,
        path,
        1,
        f"Workflow surface mentions async/product workflow behavior but has no obvious `{state_name}` state.",
        recommendation,
        project_root,
        confidence=confidence,
        next_skill="fix-workflow",
        guard_candidate=False,
        state=state_name,
    )


def _scan_file(path: Path, project_root: Path) -> list[dict[str, object]]:
    text = read_text(path)
    if not _is_workflow_file(path, text):
        return []
    records: list[dict[str, object]] = []
    has_async = bool(ASYNC_RE.search(text))
    if has_async and not STATE_PATTERNS["loading"].search(text):
        records.append(
            _state_gap(
                "missing_loading_state",
                path,
                project_root,
                "loading",
                "Add or wire a visible loading/busy state before the async work starts.",
            )
        )
    if not STATE_PATTERNS["empty"].search(text):
        records.append(
            _state_gap(
                "missing_empty_state",
                path,
                project_root,
                "empty",
                "Add the expected empty/no-results state for this workflow surface, or document why it cannot be empty.",
            )
        )
    if has_async and not STATE_PATTERNS["failure"].search(text):
        records.append(
            _state_gap(
                "missing_failure_state",
                path,
                project_root,
                "failure",
                "Render failure/cancelled/error states explicitly; do not leave terminal errors as silent console-only outcomes.",
                confidence="high",
            )
        )
    if has_async and not STATE_PATTERNS["recovery"].search(text):
        records.append(
            _state_gap(
                "missing_recovery_state",
                path,
                project_root,
                "retry/cancel/resume",
                "Expose a retry, cancel, abort, or resume path when a workflow can fail or take background time.",
            )
        )
    if path.suffix == ".html" and re.search(r"<(?:button|input|select|textarea)\b", text) and not STATE_PATTERNS["disabled"].search(text):
        records.append(
            _state_gap(
                "missing_disabled_state",
                path,
                project_root,
                "disabled",
                "Controls that launch workflow work should show the disabled/unavailable state.",
            )
        )
    if path.suffix == ".html" and not STATE_PATTERNS["mobile"].search(text):
        records.append(
            _state_gap(
                "missing_mobile_state",
                path,
                project_root,
                "mobile/responsive",
                "Confirm the tab has a mobile/responsive state; add layout tokens or a targeted Playwright viewport check.",
                confidence="low",
            )
        )
    return records


def _workflow_duplication_context(project_root: Path) -> list[dict[str, Any]]:
    detector_path = PROJECT_ROOT / ".claude" / "skills" / "find-workflow-duplication" / "scripts" / "detect.py"
    if not detector_path.exists():
        return []
    module = load_module("workflow_duplication_detector", detector_path)
    records: list[dict[str, Any]] = []
    for record in module.detect(project_root, min_owners=3, min_active_owners=2):
        record = dict(record)
        record["pattern"] = f"state_authority_context:{record.get('pattern', 'workflow_duplication')}"
        record["summary"] = f"Workflow state/label authority context: {record.get('summary', '')}"
        records.append(
            normalize_record(
                record,
                project_root,
                default_confidence="medium",
                next_skill="extract-workflow-registry",
                guard_candidate=False,
            )
        )
    return records


def detect(
    project_root: Path,
    paths: list[str] | None = None,
    include_workflow_duplication: bool = True,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in expand_paths(project_root, paths, SUFFIXES):
        records.extend(_scan_file(path, project_root))
    if include_workflow_duplication:
        records.extend(_workflow_duplication_context(project_root))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--no-workflow-duplication", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    records = detect(args.project_root.resolve(), args.paths or None, not args.no_workflow_duplication)
    write_jsonl(records, args.output)
    print(f"wrote {args.output}: {len(records)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
