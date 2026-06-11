#!/usr/bin/env python3
"""Audit the quality perimeter — code roots no structural detector covers.

The detector fleet (SUSPECT skills) each scan some part of a host
codebase. Nothing else reports the inverse: code that *nobody* scans.
This script makes the perimeter explicit (ADR 0032):

1. Walk the project root and bucket source files into
   ``(top-level root, language)`` cells by extension, skipping vendored /
   generated / minified trees.
2. Inventory the skill fleet: every ``SKILL.md`` with ``job: suspect``
   declares its coverage via frontmatter — the optional ``scans:`` list
   of languages its scan surface covers, falling back to ``language:``
   (where ``any`` covers everything).
3. Report every cell at or above ``--min-loc`` with the detectors that
   cover it. Cells with **zero** covering detectors are perimeter gaps.

A gap is not automatically work — vendored or generated code can be an
*accepted* blind spot via ``--accept root:language`` — but it must be
visible. Exit code 1 with ``--fail-on-gap`` makes the audit CI-able.

Stdlib-only; no YAML dependency (frontmatter is parsed line-wise for the
three fields this audit needs).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "templates",
    ".htm": "templates",
    ".jinja": "templates",
    ".j2": "templates",
    ".css": "css",
    ".scss": "css",
    ".sh": "shell",
    ".bash": "shell",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".sql": "sql",
}

SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", "staticfiles", "vendor", "vendored",
    ".tox", ".mypy_cache", ".ruff_cache", "migrations",
    # Data/artifact trees, not product source.
    "media", "tmp", "fixtures", "snapshots", "crawled", ".cache",
})

SKIP_FILE_GLOBS: tuple[str, ...] = (
    "*.min.js", "*.min.css", "*-min.js", "*.bundle.js",
)

# A single source file beyond this is almost certainly data or generated
# output (crawled page snapshots, SQL dumps), not hand-maintained code.
# Hand-written omnibus files top out around 5-6K lines.
DEFAULT_MAX_FILE_LOC = 10_000


def _iter_source_files(
    project_root: Path,
    *,
    skip_roots: frozenset[str],
    max_file_loc: int,
) -> list[tuple[str, str, int]]:
    """Yield (top_level_root, language, loc) per source file."""
    rows: list[tuple[str, str, int]] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        language = LANGUAGE_BY_EXTENSION.get(path.suffix.lower())
        if language is None:
            continue
        try:
            rel = path.relative_to(project_root)
        except ValueError:
            continue
        parts = rel.parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        # Hidden trees (.claude/, .github/) are tooling, not product code.
        if parts[0].startswith("."):
            continue
        if parts[0] in skip_roots:
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in SKIP_FILE_GLOBS):
            continue
        try:
            loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if loc > max_file_loc:
            continue
        root = parts[0] if len(parts) > 1 else "(root)"
        rows.append((root, language, loc))
    return rows


def _parse_frontmatter_fields(skill_md: Path) -> dict[str, object]:
    """Line-wise frontmatter parse for name / job / language / scans.

    Handles ``scans: [a, b]`` inline lists and block lists::

        scans:
          - javascript
          - templates
    """
    fields: dict[str, object] = {}
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return fields
    if not lines or lines[0].strip() != "---":
        return fields
    in_scans_block = False
    scans: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if in_scans_block:
            stripped = line.strip()
            if stripped.startswith("- "):
                scans.append(stripped[2:].strip().strip("'\""))
                continue
            in_scans_block = False
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "scans":
            if value.startswith("[") and value.endswith("]"):
                scans = [
                    item.strip().strip("'\"")
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
            elif not value:
                in_scans_block = True
            else:
                scans = [item.strip().strip("'\"") for item in value.split(",")]
        elif key in {"name", "job", "language"}:
            fields[key] = value.strip("'\"")
    if scans:
        fields["scans"] = scans
    return fields


def _detector_coverage(skills_root: Path) -> list[dict[str, object]]:
    """Inventory suspect detectors and the languages each covers.

    Coverage is the explicit ``scans:`` list when declared. Without it,
    the fallback is the exact ``language:`` value — and ``language: any``
    deliberately covers *nothing* here: it states the detector's
    implementation is portable, not that its scan surface reaches every
    language. Overstated coverage is the failure mode this audit exists
    to catch (ADR 0032), so absence of a declaration reads as a gap.
    """
    detectors: list[dict[str, object]] = []
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        fields = _parse_frontmatter_fields(skill_md)
        if fields.get("job") != "suspect":
            continue
        scans = fields.get("scans")
        if isinstance(scans, list) and scans:
            covered = [str(item) for item in scans]
        else:
            language = str(fields.get("language", ""))
            covered = [language] if language and language != "any" else []
        detectors.append({
            "name": str(fields.get("name", skill_md.parent.name)),
            "covers": covered,
            "declared_scans": bool(isinstance(scans, list) and scans),
        })
    return detectors


def _covers(detector: dict[str, object], language: str) -> bool:
    return language in detector["covers"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--skills-root", type=Path, default=None,
                   help="Defaults to <project-root>/.claude/skills")
    p.add_argument("--min-loc", type=int, default=3000,
                   help="Cells below this LOC are reported but not gap-flagged")
    p.add_argument("--accept", action="append", default=[],
                   help="Accepted blind spot as root:language (repeatable)")
    p.add_argument("--skip-root", action="append", default=[],
                   help="Extra top-level roots to exclude entirely (repeatable)")
    p.add_argument("--max-file-loc", type=int, default=DEFAULT_MAX_FILE_LOC,
                   help="Files above this LOC are treated as data/generated and skipped")
    p.add_argument("--output", type=Path, default=None,
                   help="Optional JSON report path")
    p.add_argument("--fail-on-gap", action="store_true")
    args = p.parse_args(argv)

    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"[perimeter] ERROR: {project_root} is not a directory", file=sys.stderr)
        return 2
    skills_root = args.skills_root or (project_root / ".claude" / "skills")

    cells: dict[tuple[str, str], dict[str, int]] = {}
    for root, language, loc in _iter_source_files(
        project_root,
        skip_roots=frozenset(args.skip_root),
        max_file_loc=args.max_file_loc,
    ):
        cell = cells.setdefault((root, language), {"loc": 0, "files": 0})
        cell["loc"] += loc
        cell["files"] += 1

    detectors = _detector_coverage(skills_root) if skills_root.is_dir() else []
    accepted = {tuple(item.split(":", 1)) for item in args.accept}

    rows: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    for (root, language), cell in sorted(
        cells.items(), key=lambda kv: -kv[1]["loc"]
    ):
        covering = [d["name"] for d in detectors if _covers(d, language)]
        significant = cell["loc"] >= args.min_loc
        is_accepted = (root, language) in accepted
        row = {
            "root": root,
            "language": language,
            "loc": cell["loc"],
            "files": cell["files"],
            "covered_by": covering,
            "significant": significant,
            "accepted_blind_spot": is_accepted,
        }
        rows.append(row)
        if significant and not covering and not is_accepted:
            gaps.append(row)

    if not detectors:
        print(
            f"[perimeter] WARNING: no suspect detectors found under {skills_root}",
            file=sys.stderr,
        )

    print(f"# Quality perimeter — {project_root.name}")
    print()
    print(f"Suspect detectors inventoried: {len(detectors)}; "
          f"cells: {len(rows)}; min LOC for gap-flagging: {args.min_loc}")
    print()
    print("| root | language | LOC | files | covered by |")
    print("|---|---|---:|---:|---|")
    for row in rows:
        if not row["significant"]:
            continue
        coverage = ", ".join(row["covered_by"]) if row["covered_by"] else "**NONE**"
        if row["accepted_blind_spot"]:
            coverage += " (accepted blind spot)"
        print(f"| {row['root']} | {row['language']} | {row['loc']} "
              f"| {row['files']} | {coverage} |")
    print()
    if gaps:
        print(f"## PERIMETER GAPS ({len(gaps)})")
        print()
        for row in gaps:
            print(f"- `{row['root']}` / {row['language']}: {row['loc']} LOC "
                  f"across {row['files']} files with **no covering detector**")
    else:
        print("## No perimeter gaps above threshold")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(
            {"detectors": detectors, "cells": rows, "gaps": gaps}, indent=2,
        ))

    if gaps and args.fail_on_gap:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
