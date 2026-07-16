#!/usr/bin/env python3
"""Audit the quality perimeter — code roots no structural detector covers.

The detector fleet (SUSPECT skills) each scan some part of a host
codebase. Nothing else reports the inverse: code that *nobody* scans.
This script makes the perimeter explicit (ADR 0032):

1. Walk the project root and bucket source files into
   ``(top-level root, language)`` cells by extension, skipping vendored /
   generated / minified trees.
2. Inventory the skill fleet. In canonical host-profile mode a ``job: suspect``
   declaration counts only when its registry-compatible capability contract,
   hashed implementation, tool/platform evidence, and fixture command all
   validate and execute. Legacy no-profile mode retains declaration-only
   behavior solely for the pinned predecessor comparison oracle.
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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from _lib.capability_registry import load_registry  # noqa: E402
from _lib.host_profile import validate_host_profile  # noqa: E402
from _lib.support_evidence import attested_paths  # noqa: E402
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402

CAPABILITY_REGISTRY = load_registry()

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
        language = CAPABILITY_REGISTRY.language_for_extension(path.suffix)
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


def _iter_profile_source_files(
    project_root: Path,
    profile: dict[str, Any],
    *,
    skip_roots: frozenset[str],
    max_file_loc: int,
) -> list[tuple[str, str, int]]:
    """Yield source rows owned by the most-specific declared profile root."""
    specs: list[tuple[Path, str, frozenset[str], tuple[Path, ...]]] = []
    for item in profile["roots"]:
        label = str(item["path"])
        root = project_root if label == "." else project_root / label
        code_roots = tuple(
            project_root if value == "." else project_root / str(value)
            for value in item.get("code_roots", [])
        ) or (root,)
        specs.append((root.resolve(), label, frozenset(item["languages"]), code_roots))
    specs.sort(key=lambda item: len(item[0].parts), reverse=True)
    exclusions = [str(item["pattern"]) for item in profile.get("exclusions", [])]
    rows: list[tuple[str, str, int]] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(project_root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.parts[0] in skip_roots:
            continue
        rendered = rel.as_posix()
        if any(fnmatch.fnmatchcase(rendered, pattern) for pattern in exclusions):
            continue
        if any(fnmatch.fnmatchcase(path.name, glob) for glob in SKIP_FILE_GLOBS):
            continue
        language = CAPABILITY_REGISTRY.language_for_extension(path.suffix)
        if language is None:
            continue
        owner: tuple[Path, str, frozenset[str], tuple[Path, ...]] | None = None
        resolved = path.resolve()
        for spec in specs:
            root, _, languages, code_roots = spec
            if language not in languages or (resolved != root and root not in resolved.parents):
                continue
            if not any(resolved == code_root.resolve() or code_root.resolve() in resolved.parents for code_root in code_roots):
                continue
            owner = spec
            break
        if owner is None:
            continue
        try:
            loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if loc <= max_file_loc:
            rows.append((owner[1], language, loc))
    return rows


def _parse_frontmatter_fields(skill_md: Path) -> dict[str, Any]:
    """Parse the canonical YAML frontmatter used by contract validation."""
    try:
        return parse(skill_md.read_text(encoding="utf-8"), path=skill_md).metadata
    except (OSError, UnicodeDecodeError, FrontmatterError):
        return {}


def _evaluate_detector_evidence(
    metadata: dict[str, Any],
    skill_dir: Path,
) -> tuple[bool, str, list[str]]:
    if "capability_contract" not in metadata:
        return False, "missing", ["missing capability_contract"]
    errors = CAPABILITY_REGISTRY.validate_skill_contract(metadata, skill_dir=skill_dir)
    evidence = metadata.get("capability_evidence")
    required: dict[str, set[Path]] = {}
    if isinstance(evidence, dict):
        for subject, attestations in evidence.items():
            required[str(subject)] = attested_paths(
                attestations,
                root=skill_dir,
                kind="test",
            )
    state, support_reasons = CAPABILITY_REGISTRY.evaluate_support(
        {
            "state": metadata.get("support", "unsupported"),
            "evidence": metadata.get("support_evidence"),
        },
        root=skill_dir,
        execute=True,
        expected_claim={"kind": "skill", "id": skill_dir.name},
        required_test_paths_by_subject=required,
    )
    errors.extend(support_reasons)
    ready = not errors and state != "unsupported"
    return ready, state, sorted(set(errors))


def _detector_coverage(
    skills_root: Path,
    *,
    require_evidence: bool,
) -> list[dict[str, object]]:
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
        ready, state, reasons = (
            _evaluate_detector_evidence(fields, skill_md.parent)
            if require_evidence
            else (True, "legacy-declaration", [])
        )
        detectors.append(
            {
                "name": str(fields.get("name", skill_md.parent.name)),
                "covers": covered,
                "declared_scans": bool(isinstance(scans, list) and scans),
                "coverage_ready": ready,
                "support_state": state,
                "evidence_reasons": reasons,
            }
        )
    return detectors


def _covers(detector: dict[str, object], language: str) -> bool:
    return bool(detector["coverage_ready"]) and language in detector["covers"]


def _parse_acceptances(values: list[str]) -> tuple[dict[tuple[str, str], str], list[str]]:
    accepted: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    for value in values:
        cell, separator, reason = value.partition("=")
        root, colon, language = cell.partition(":")
        if not separator or not colon or not root or not language or not reason.strip():
            errors.append(
                f"accepted exclusion {value!r} must be root:language=non-empty-reason"
            )
            continue
        accepted[(root, language)] = reason.strip()
    return accepted, errors


# spec:portable-host-profile-routing::IM-6
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--skills-root", type=Path, default=None,
                   help="Defaults to <project-root>/.claude/skills")
    p.add_argument("--min-loc", type=int, default=3000,
                   help="Cells below this LOC are reported but not gap-flagged")
    p.add_argument("--accept", action="append", default=[],
                   help="Accepted blind spot as root:language=reason (repeatable)")
    p.add_argument("--host-profile", type=Path,
                   help="Canonical host profile; enables evidence-backed coverage mode")
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

    profile: dict[str, Any] | None = None
    if args.host_profile:
        try:
            loaded = json.loads(args.host_profile.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[perimeter] ERROR: invalid host profile: {exc}", file=sys.stderr)
            return 2
        if not isinstance(loaded, dict):
            print("[perimeter] ERROR: host profile must be a mapping", file=sys.stderr)
            return 2
        profile_errors = validate_host_profile(loaded)
        if profile_errors:
            print(f"[perimeter] ERROR: invalid host profile: {'; '.join(profile_errors)}", file=sys.stderr)
            return 2
        profile = loaded

    cells: dict[tuple[str, str], dict[str, int]] = {}
    source_rows = (
        _iter_profile_source_files(
            project_root,
            profile,
            skip_roots=frozenset(args.skip_root),
            max_file_loc=args.max_file_loc,
        )
        if profile is not None
        else _iter_source_files(
            project_root,
            skip_roots=frozenset(args.skip_root),
            max_file_loc=args.max_file_loc,
        )
    )
    for root, language, loc in source_rows:
        cell = cells.setdefault((root, language), {"loc": 0, "files": 0})
        cell["loc"] += loc
        cell["files"] += 1

    detectors = (
        _detector_coverage(skills_root, require_evidence=profile is not None)
        if skills_root.is_dir()
        else []
    )
    accepted, acceptance_errors = _parse_acceptances(args.accept)
    if acceptance_errors:
        for error in acceptance_errors:
            print(f"[perimeter] ERROR: {error}", file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    for (root, language), cell in sorted(
        cells.items(), key=lambda kv: -kv[1]["loc"]
    ):
        covering = [d["name"] for d in detectors if _covers(d, language)]
        candidates = [
            {
                "name": d["name"],
                "support_state": d["support_state"],
                "reasons": d["evidence_reasons"],
            }
            for d in detectors
            if language in d["covers"] and not d["coverage_ready"]
        ]
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
            "accepted_reason": accepted.get((root, language)),
            "rejected_coverage_candidates": candidates,
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
            coverage += f" (accepted: {row['accepted_reason']})"
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
            {
                "schema_version": 2,
                "coverage_mode": "executable-evidence" if profile is not None else "legacy-declaration",
                "host_profile_sha256": profile.get("profile_sha256") if profile else None,
                "profile_exclusions": profile.get("exclusions", []) if profile else [],
                "accepted_exclusions": [
                    {"root": root, "language": language, "reason": reason}
                    for (root, language), reason in sorted(accepted.items())
                ],
                "detectors": detectors,
                "cells": rows,
                "gaps": gaps,
            },
            indent=2,
        ))

    if gaps and args.fail_on_gap:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
