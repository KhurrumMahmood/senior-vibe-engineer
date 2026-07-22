#!/usr/bin/env python3
"""/which-cleanup — diff-driven, scope-tiered closeout router.

Resolves "what changed" (files / --staged / --changed-from / --commit / --range
/ --area / --since), sizes it into a scope band, and recommends which cleanup
skills to run at task closeout (pre-baseline / post-sweep / guard-tail). Advisory
and read-only: writes only under reports/which-cleanup/ (+ a large-band spec stub
under ai-docs/specs/). See ADR 0024.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# KIT_ROOT anchors kit-relative imports ONLY (this skill kit's _common/ and
# scripts/). Target-project paths (registry, reports, specs, git scope) anchor
# on --project-root instead — the kit may live in a different repo (ADR 0024
# de-baking convention; see which-shape/scripts/route.py).
SCRIPT_DIR = Path(__file__).resolve().parent
KIT_ROOT = Path(__file__).resolve().parents[4]
for _p in (str(SCRIPT_DIR), str(KIT_ROOT / ".claude" / "skills" / "_common"), str(KIT_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import classify
import closeout as closeout_mod
import diff_resolution as dr
import select_scanners
from query_planner import report_for_files
from subsystems import for_path, load_registry


def _relativize(paths: list[Path], root: Path) -> list[str]:
    out = []
    for p in paths:
        try:
            out.append(str(p.resolve().relative_to(root)))
        except ValueError:
            continue
    return out


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def resolve_scope(args, registry, root: Path) -> tuple[str, list[str], int | None]:
    """Return (target_label, repo_relative_files, diff_loc_or_None)."""
    if args.paths:
        files = _relativize(dr.changed_paths(root, args.paths), root)
        return (" ".join(args.paths), files, None)
    if args.area:
        try:
            files = _relativize(dr.resolve_area(root, args.area, registry), root)
        except KeyError:
            print(f"error: unknown subsystem/area: {args.area}", file=sys.stderr)
            raise SystemExit(2) from None
        return (f"--area {args.area}", files, None)
    if args.since:
        return (f"--since {args.since}", dr.resolve_since(root, args.since), None)
    if args.commit:
        return (f"--commit {args.commit}", dr.resolve_commit(root, args.commit),
                dr.diff_loc(root, [f"{args.commit}~1", args.commit]))
    if args.range:
        return (f"--range {args.range}", dr.resolve_range(root, args.range),
                dr.diff_loc(root, [args.range]))
    if args.changed_from:
        return (f"--changed-from {args.changed_from}",
                dr.git_files(root, changed_from=args.changed_from),
                dr.diff_loc(root, [args.changed_from]))
    if args.staged:
        return ("--staged", dr.git_files(root, staged=True), dr.diff_loc(root, ["--cached"]))
    # default: working-tree diff (uncommitted changes) — NOT a whole-repo scan.
    return ("working tree", dr.git_files(root), dr.diff_loc(root, []))


def _log_effectiveness(scan_id: str, target: str, c: dict, project_root: Path) -> None:
    buckets = {k: len(v) for k, v in c["checklist"].items()}
    buckets["dropped"] = len(c["dropped"])
    total = sum(len(v) for v in c["checklist"].values())
    try:
        # The helper script ships with the kit; cwd anchors its relative
        # default log path (reports/_meta/effectiveness.jsonl) in the target.
        subprocess.run(
            [sys.executable, str(KIT_ROOT / "scripts" / "log_effectiveness.py"),
             "--skill", "which-cleanup", "--scan-id", scan_id, "--target", target[:120],
             "--findings-total", str(total), "--buckets", json.dumps(buckets)],
            cwd=project_root, capture_output=True, text=True, check=False,
        )
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="*", help="Explicit files/globs (else a diff mode is used)")
    p.add_argument("--staged", action="store_true", help="Use the staged diff")
    p.add_argument("--changed-from", metavar="REF", help="Diff against REF")
    p.add_argument("--commit", metavar="SHA", help="Files changed by a single commit")
    p.add_argument("--range", metavar="A..B", help="Files changed across a commit range")
    p.add_argument("--area", metavar="NAME", help="A subsystem name from the registry")
    p.add_argument("--since", metavar="SPEC", help="Files touched since a git time spec")
    p.add_argument("--max-scouts", type=int, default=5, help="Cap the medium-band fan-out roster")
    p.add_argument("--emit-plan", action="store_true",
                   help="On the large band, also write the /refactor-subsystem spec stub + Workflow script")
    p.add_argument("--project-root", type=Path, default=None,
                   help="Target project root (default: git toplevel of cwd, else cwd)")
    p.add_argument("--registry", default=None,
                   help="Subsystem registry (default: <project-root>/.claude/subsystems.yaml)")
    p.add_argument("--reports-dir", default=None,
                   help="Report output dir (default: <project-root>/reports/which-cleanup)")
    p.add_argument("--specs-dir", default=None,
                   help="Spec-stub output dir (default: <project-root>/ai-docs/specs)")
    p.add_argument("--now", default=None, help="Override timestamp (tests); ISO or scan-id stamp")
    p.add_argument("--skip-effectiveness-log", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    project_root = dr.resolve_project_root(args.project_root)
    registry_path = Path(args.registry).resolve() if args.registry else project_root / ".claude" / "subsystems.yaml"

    try:
        registry = load_registry(registry_path)
    except FileNotFoundError:
        registry = {}  # no project registry shipped (generic default): universal floor + band only
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    target, files, dloc = resolve_scope(args, registry, project_root)
    # A diff can name deleted/renamed-away paths; they can't be cleaned, would
    # inflate the file count, and would emit commands against non-existent files.
    # Drop them (matching find-test-obligation-drift's detect() contract). diff_loc
    # still counts deletions as churn, so the LOC axis keeps seeing the change.
    files = [f for f in files if (project_root / f).exists()]
    if not files:
        print(f"No changes detected for scope ({target}); nothing to clean up.")
        return 0

    subsystems = sorted({s for f in files if (s := for_path(f, registry))})
    report = report_for_files(files, registry, include_checklist=False)
    inputs = classify.ScopeInputs(file_count=len(files), subsystem_count=len(subsystems), diff_loc=dloc)
    band = classify.classify(inputs)
    # Transparency when both the subsystem and LOC axes are inert (no registry
    # match and a non-diff input mode): the band is file-count-only and may
    # understate a large rewrite of few files.
    caveat = None
    if not subsystems and dloc is None and len(files) > 1:
        caveat = ("scope sized from file count only — no registry subsystem matched and this "
                  "input mode carries no diff-LOC signal; a large rewrite of few files may be "
                  "understated. Re-run with --changed-from/--commit/--range for LOC sizing.")
    has_doc_change = any(f.endswith(".md") or f.startswith("docs/") or "/docs/" in f for f in files)
    # Rename signal: the glossary or a reintroduction-guard lint was touched — a concept
    # rename is underway, so recommend /rename-concept to drive it to completion (any band).
    has_rename_signal = any(
        f == ".claude/contracts/concepts.yaml"
        or (f.startswith("scripts/lint/no_") and f.endswith("_references.py"))
        for f in files
    )
    roster = select_scanners.select(report, band=band, has_doc_change=has_doc_change,
                                    has_rename_signal=has_rename_signal)

    c = closeout_mod.build(
        target=target, scope_band=band, axis_breakdown=classify.axis_breakdown(inputs),
        resolved_paths=files, report=report, roster=roster, max_scouts=args.max_scouts,
    )

    now = args.now or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    scan_id = f"scan-{now}"
    c["scan_id"] = scan_id
    c["generated"] = datetime.now(timezone.utc).isoformat() if not args.now else args.now
    if caveat:
        c["scope_caveat"] = caveat

    # Trivial scope honors the "text only, no scan dir" contract.
    if band != "trivial":
        reports_dir = (Path(args.reports_dir) if args.reports_dir
                       else project_root / "reports" / "which-cleanup").resolve()
        scan_dir = reports_dir / scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        (scan_dir / "closeout.json").write_text(json.dumps(c, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (scan_dir / "closeout.md").write_text(closeout_mod.render_md(c), encoding="utf-8")
        latest = reports_dir / "latest"
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        elif latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(scan_id)
        c["report_dir"] = _rel(scan_dir, project_root)

        # Large band always shows the sequenced plan in closeout.md; the spec stub
        # + Workflow script are written to ai-docs/specs/ only on --emit-plan (avoids
        # polluting the spec dir on every large closeout).
        if band == "large" and args.emit_plan:
            base = subsystems[0] if subsystems else "mixed"
            slug = re.sub(r"[^a-z0-9]+", "-", f"{base}-closeout-{now}".lower()).strip("-")
            specs_dir = (Path(args.specs_dir) if args.specs_dir
                         else project_root / "ai-docs" / "specs").resolve()
            specs_dir.mkdir(parents=True, exist_ok=True)
            spec_path = specs_dir / f"{slug}.md"
            spec_path.write_text(closeout_mod.spec_stub(c, slug), encoding="utf-8")
            (scan_dir / f"{slug}.workflow.js").write_text(closeout_mod.workflow_script(c, slug), encoding="utf-8")
            c["spec_stub"] = _rel(spec_path, project_root)

        if not args.skip_effectiveness_log:
            _log_effectiveness(scan_id, target, c, project_root)

    if args.json:
        print(json.dumps(c, indent=2, sort_keys=True))
    else:
        print(closeout_mod.render_md(c), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
