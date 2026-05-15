#!/usr/bin/env python3
"""Query planner — "I just touched these files, what else should I check?"

Given one or more file paths, surfaces:
  * The subsystem each file belongs to (via `scripts/subsystems.py`)
  * Adjacency smells declared in `.claude/subsystems.yaml`
  * Per-subsystem touch checklists from `.claude/checks/<name>.md` (optional)
  * Related decisions / docs

Usage:
  query_planner.py for-files <path> [<path> ...] [--no-checklist] [--json]

Exit codes:
  0  at least one path matched a subsystem
  1  no path matched any subsystem (registry doesn't cover them)
  2  usage error / malformed registry / missing files

## v0.1 scope

Deliberately small — answers "what subsystem(s), what adjacency, what
checklist?" and stops. Does NOT (yet) look up cached `find-*` findings
that touch the files (needs PR E's `report.json` to do that without the
fragile keyword-grepping that bit `/triage-debt`), and does NOT check
per-file staleness (needs the coverage tracker's `coverage.json`).
v1.0 layers those in once both substrates ship. The CLI surface stays
stable; output gets richer.

## Substrate philosophy (forward-looking)

For projects at this scale, a hand-curated subsystem registry is the right
substrate — small enough to maintain, precise enough to be actionable.
For general / opensource / SaaS-scale ecosystems where curation doesn't
scale, the same surface could be backed by embedding-derived subsystem
clusters + on-demand cheap-LLM scout scans (Haiku, Cerebras-GLM-4.7) of
the touched files for the adjacency smells. That's a substitute for the
registry, not the query-planner — keep the CLI surface stable so the
substrate can swap underneath.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_REGISTRY = REPO_ROOT / ".claude" / "subsystems.yaml"
DEFAULT_CHECKS_DIR = REPO_ROOT / ".claude" / "checks"

_scripts_parent = str(SCRIPT_PATH.parent)
if _scripts_parent not in sys.path:
    sys.path.insert(0, _scripts_parent)
from subsystems import for_path, load_registry  # noqa: E402


def _group_by_subsystem(paths: list[str], registry: dict[str, dict[str, Any]]) -> dict[str | None, list[str]]:
    grouped: dict[str | None, list[str]] = defaultdict(list)
    for p in paths:
        grouped[for_path(p, registry)].append(p)
    return grouped


def _load_checklist(subsystem: str, checks_dir: Path) -> str | None:
    f = checks_dir / f"{subsystem}.md"
    if not f.is_file():
        return None
    return f.read_text(encoding="utf-8").strip()


def _build_report(
    grouped: dict[str | None, list[str]],
    registry: dict[str, dict[str, Any]],
    checks_dir: Path,
    include_checklist: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {"subsystems": [], "unmatched": []}
    for subsystem, paths in grouped.items():
        if subsystem is None:
            report["unmatched"] = sorted(paths)
            continue
        body = registry.get(subsystem, {})
        entry: dict[str, Any] = {
            "name": subsystem,
            "paths": sorted(paths),
            "description": body.get("description", "") or "",
            "adjacency": body.get("adjacency") or [],
            "related_skills": body.get("related_skills") or [],
            "related_decisions": body.get("related_decisions") or [],
            "docs": body.get("docs") or [],
        }
        if include_checklist:
            entry["checklist"] = _load_checklist(subsystem, checks_dir)
        report["subsystems"].append(entry)
    report["subsystems"].sort(key=lambda e: e["name"])
    return report


def _render_text(report: dict[str, Any], include_checklist: bool) -> str:
    lines: list[str] = []
    for entry in report["subsystems"]:
        lines.append(f"Subsystem: {entry['name']} ({len(entry['paths'])} file(s))")
        if entry["description"]:
            lines.append(f"  {entry['description']}")
        for p in entry["paths"]:
            lines.append(f"    - {p}")
        if entry["adjacency"]:
            lines.append("  Adjacency suggests also checking:")
            for a in entry["adjacency"]:
                lines.append(f"    - {a}")
        if entry["related_decisions"]:
            lines.append(f"  Related decisions: {', '.join(entry['related_decisions'])}")
        if entry["docs"]:
            lines.append(f"  Relevant docs: {', '.join(entry['docs'])}")
        if include_checklist and entry.get("checklist"):
            lines.append(f"  Touch checklist (.claude/checks/{entry['name']}.md):")
            for line in entry["checklist"].splitlines():
                lines.append(f"    {line}" if line else "")
        elif include_checklist:
            lines.append(f"  Touch checklist: (none defined — add .claude/checks/{entry['name']}.md to seed)")
        lines.append("")
    if report["unmatched"]:
        lines.append("Unmatched files (no subsystem in registry):")
        for p in report["unmatched"]:
            lines.append(f"  - {p}")
        lines.append("  Hint: extend .claude/subsystems.yaml to cover these paths.")
    return "\n".join(lines).rstrip() + "\n"


def cmd_for_files(args: argparse.Namespace, registry: dict[str, dict[str, Any]]) -> int:
    paths = args.paths
    if not paths:
        print("error: at least one path required", file=sys.stderr)
        return 2
    grouped = _group_by_subsystem(paths, registry)
    include_checklist = not args.no_checklist
    checks_dir = Path(args.checks_dir).resolve()
    report = _build_report(grouped, registry, checks_dir, include_checklist)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(_render_text(report, include_checklist), end="")
    return 0 if report["subsystems"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY),
                        help=f"Subsystem registry (default: {DEFAULT_REGISTRY})")
    parser.add_argument("--checks-dir", default=str(DEFAULT_CHECKS_DIR),
                        help=f"Touch-checklist directory (default: {DEFAULT_CHECKS_DIR})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("for-files", help="Surface adjacency/checklist for one or more touched files")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-checklist", action="store_true", help="Skip the touch-checklist section")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_for_files)

    args = parser.parse_args(argv)
    try:
        registry = load_registry(Path(args.registry).resolve())
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return args.func(args, registry)


if __name__ == "__main__":
    raise SystemExit(main())
