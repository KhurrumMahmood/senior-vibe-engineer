#!/usr/bin/env python3
"""Extract a semantic-duplication finding from triage.md into targets.json.

The `/unify-shadows` orchestrator calls this in Stage 1 (Form A). The
triage's format is stable: H3 headings of the form
``### SC-N: <title> [LEVEL]`` open each finding, members live in a
``**Members:**`` bullet list, and a ``**Consolidation shape:**`` line
pins the shape.

Usage:

    python3 .claude/skills/unify-shadows/scripts/collect_shadows.py \\
      --triage reports/semantic-duplication/latest/triage.md \\
      --finding-id SC-3 \\
      --output reports/unify-shadows/SC-3/targets.json

Exit status:

    0  targets.json written (≥ 1 member)
    1  finding not found — stderr lists the IDs present in the triage
    2  invocation error (unreadable file, malformed triage)

Output schema:

    {
      "finding_id": "SC-3",
      "title": "...",
      "shape": "keep_separate_document_why",
      "notes": "<triage notes block, first paragraph>",
      "capability_matrix": "reports/semantic-duplication/<scan>/capability_matrices/SC-3.md",
      "members": [
        {
          "member_key": "agentic_discovery_service__call_llm",
          "file": "core/services/agentic_discovery_service.py",
          "symbol": "AgenticDiscoveryService._call_llm",
          "lineno": 1420,
          "caller_count": 3
        },
        ...
      ]
    }

Stdlib-only; runs under bare `python3`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# spec:status-projection-and-presentation::IM-5
def _write_scope_sidecar(artifact_dir: Path, paths: list[str]) -> None:
    """scope.json sidecar (ADR 0037) — declares which repo paths this
    artifact's conclusions depend on, so the status projection can flag
    input drift. Strictly additive; silently skipped when the toolkit
    helper is absent (skill vendored without scripts/_lib)."""
    helper = Path(__file__).resolve().parents[4] / "scripts" / "_lib" / "artifact_scope.py"
    if not helper.is_file():
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("artifact_scope", helper)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.write_scope(artifact_dir, paths)


HEADING_RE = re.compile(r"^### (SC-\d+): (.+?)\s*\[[A-Z]+\]\s*$")
MEMBER_RE = re.compile(
    r"^- `([^`]+):(\d+)` — `([^`]+)`\s*\((\d+) lines?,\s*(\d+) callers?\)"
)
SHAPE_RE = re.compile(r"^\*\*Consolidation shape:\*\*\s*`([a-z_]+)`")
MATRIX_RE = re.compile(r"^\*\*Capability matrix:\*\*\s*`([^`]+)`")


def _member_key(file_path: str, symbol: str) -> str:
    """Stable key for a member. `core/services/foo.py` + `Cls.method`
    → `foo__method` (basename + bare method). Falls back to the full
    symbol if the method name collides with another member."""
    base = Path(file_path).stem
    tail = symbol.rsplit(".", 1)[-1]
    return f"{base}__{tail}"


def _resolve_matrix_path(raw: str, triage_path: Path) -> str:
    """Resolve the capability matrix path; the triage sometimes uses
    a relative `capability_matrices/SC-N.md` and sometimes a full
    `reports/semantic-duplication/scan-*/capability_matrices/SC-N.md`.
    We normalize to a repo-root-relative string for downstream tools."""
    if raw.startswith("reports/"):
        return raw
    if raw.startswith("../"):
        # Path from triage.md up to repo root.
        return str((triage_path.parent / raw).resolve().relative_to(Path.cwd().resolve()))
    return str((triage_path.parent / raw).resolve().relative_to(Path.cwd().resolve()))


def _parse_finding(lines: list[str], start_idx: int) -> tuple[dict, int]:
    """Parse one finding starting at H3 heading line index.
    Returns (finding_dict, next_heading_idx)."""
    heading = HEADING_RE.match(lines[start_idx])
    assert heading, f"not a finding heading: {lines[start_idx]!r}"
    finding_id, title = heading.group(1), heading.group(2).strip()

    members: list[dict] = []
    shape: str | None = None
    matrix: str | None = None
    notes_lines: list[str] = []
    in_notes = False

    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        if HEADING_RE.match(line):
            break
        if line.strip() == "---":
            break
        m = MEMBER_RE.match(line)
        if m:
            file_path, lineno, symbol, _lines, callers = m.groups()
            members.append(
                {
                    "file": file_path,
                    "lineno": int(lineno),
                    "symbol": symbol,
                    "caller_count": int(callers),
                }
            )
            i += 1
            continue
        s = SHAPE_RE.match(line)
        if s:
            shape = s.group(1)
            i += 1
            continue
        mx = MATRIX_RE.match(line)
        if mx:
            matrix = mx.group(1)
            i += 1
            continue
        if line.startswith("**Notes:**"):
            in_notes = True
            notes_lines.append(line[len("**Notes:**") :].strip())
            i += 1
            continue
        if in_notes:
            if line.startswith("**") or line.startswith("- "):
                in_notes = False
            else:
                notes_lines.append(line.rstrip())
        i += 1

    # Assign stable member keys; collisions get the full symbol appended.
    seen: dict[str, int] = {}
    for m in members:
        key = _member_key(m["file"], m["symbol"])
        seen[key] = seen.get(key, 0) + 1
    for m in members:
        key = _member_key(m["file"], m["symbol"])
        if seen[key] > 1:
            key = f"{key}__{m['lineno']}"
        m["member_key"] = key

    notes = "\n".join(line for line in notes_lines if line.strip()).strip()

    return (
        {
            "finding_id": finding_id,
            "title": title,
            "shape": shape,
            "capability_matrix": matrix,
            "notes": notes,
            "members": members,
        },
        i,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--triage", required=True, type=Path)
    parser.add_argument("--finding-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not args.triage.exists():
        print(f"error: triage file not found: {args.triage}", file=sys.stderr)
        return 2

    try:
        lines = args.triage.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read triage file: {exc}", file=sys.stderr)
        return 2

    findings: dict[str, dict] = {}
    i = 0
    while i < len(lines):
        if HEADING_RE.match(lines[i]):
            f, i = _parse_finding(lines, i)
            findings[f["finding_id"]] = f
            continue
        i += 1

    if args.finding_id not in findings:
        ids = ", ".join(sorted(findings)) or "<none>"
        print(
            f"error: {args.finding_id!r} not in triage. Present IDs: {ids}",
            file=sys.stderr,
        )
        return 1

    finding = findings[args.finding_id]

    if not finding["members"]:
        print(
            f"error: {args.finding_id} has zero members — triage malformed?",
            file=sys.stderr,
        )
        return 2

    if finding["capability_matrix"]:
        finding["capability_matrix"] = _resolve_matrix_path(
            finding["capability_matrix"], args.triage
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(finding, indent=2) + "\n", encoding="utf-8")
    _write_scope_sidecar(
        args.output.parent, sorted({m["file"] for m in finding["members"]})
    )
    print(
        f"wrote {args.output}: {finding['finding_id']} "
        f"({finding['shape']}, {len(finding['members'])} members)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
