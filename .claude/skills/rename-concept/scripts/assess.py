#!/usr/bin/env python3
"""rename-concept — v0 assess (read-only lifecycle status + completeness gate).

Given an OLD -> NEW concept rename, inspect the repo and report:

  - scope-gate    : is this a glossary concept / wide-blast rename, or a
                    trivial local one the skill should bail on?
  - blast radius  : how many live-code files still mention the old token
  - glossary      : is concepts.yaml's old entry marked superseded_by: new?
  - guard lint    : does a no_<old>_references reintroduction lint exist?
  - completeness  : the two-band /find-concept-divergence gate —
                    band 3 (superseded_co_occurrence) = OLD/NEW identifiers
                    co-occurring in live code, AND band 1 (avoid_term_hit) =
                    retired prose still using the old phrasing. Band 3 is
                    SKIPPED by find-concept-divergence for any concept with a
                    coverage_lint, so for lint-guarded renames band 1 is what
                    actually proves the prose was corrected (the lint + band 3
                    are both identifier-level and prose-blind).

Definition of done = BOTH completeness bands clean AND the lifecycle steps
resolved — NOT the codemod having run. Read-only; the write half (author a
codemod plan, scaffold a guard lint, --apply) is roadmap and not yet ported
to this ecosystem (no `tools/rename` codemod ships here — see SKILL.md).

Usage:
    .venv/bin/python .claude/skills/rename-concept/scripts/assess.py <old> <new>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

# KIT_ROOT anchors kit-shipped resources ONLY (the delegated
# find-concept-divergence detector and the _common import below). Every
# target-project surface (git grep, glossary, guard-lint check, divergence-scan
# anchoring) anchors on --project-root instead — the kit may live in a
# different repo than the target project (de-baking convention, ADR 0024).
# Layout: .claude/skills/rename-concept/scripts/assess.py
#   parents[0]=scripts [1]=rename-concept [2]=skills [3]=.claude [4]=kit root
KIT_ROOT = pathlib.Path(__file__).resolve().parents[4]
_COMMON = str(KIT_ROOT / ".claude" / "skills" / "_common")
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)

from diff_resolution import resolve_project_root  # noqa: E402

# Paths where the OLD name legitimately persists (not "incomplete rename").
# ES2-native residue: the ADR tree (ai-docs/decisions/ — ADRs intentionally
# name both sides of a rename), the glossary itself, this skill + the detector
# it drives, gitignored reports, and migrations. There is no `tools/rename`
# codemod in this ecosystem, so no codemod-plan path is allowlisted.
ALLOW_SUBSTR = (
    "/migrations/", "ai-docs/decisions/",
    ".claude/contracts/concepts.yaml", ".claude/ideas/", "/reports/",
    "scripts/lint/no_", "CONTEXT.md", "ONBOARDING.md",
    ".claude/skills/rename-concept/",
    ".claude/skills/find-concept-divergence/", ".git/",
)


def git_grep_files(term: str, project_root: pathlib.Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "grep", "-lI", "-i", "-e", term],
            cwd=project_root, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode not in (0, 1):
        return []
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def allowed(path: str) -> bool:
    return any(s in path for s in ALLOW_SUBSTR)


def _norm_concept(s: str) -> str:
    """Canonical comparison form so CamelCase / snake_case / spaced / kebab forms
    of a concept all collapse to one key: `FlattenedData`, `flattened_data`,
    `Flattened Data` and `flattened-data` -> `flattened-data`."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", s)        # camelCase boundary
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "-", s)      # ABCWord -> ABC-Word
    s = re.sub(r"[\s_]+", "-", s)
    return s.lower().strip("-")


def read_glossary_supersede(old: str, project_root: pathlib.Path) -> str | None:
    """Resolve `old` against the glossary by NAME or ALIAS (normalized, so
    CamelCase/snake/spaced inputs match kebab slugs), and report its rename
    status. Returns one of:
      - "<no concepts.yaml>" : glossary file missing
      - "<no entry>"         : concept not found by name or alias
      - "<not superseded>"   : found, but superseded_by is unset (rename not
                               yet recorded — a real glossary concept)
      - <slug>               : found, superseded_by points at <slug>.
    """
    p = project_root / ".claude/contracts/concepts.yaml"
    if not p.exists():
        return "<no concepts.yaml>"
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        # Unreadable/unparseable glossary degrades to the same verdict as a
        # missing one (read-decode-safety.v1: never let the decode error escape).
        return "<no concepts.yaml>"
    target = _norm_concept(old)
    for c in data.get("concepts", []) or []:
        names = [c.get("name", "")] + list(c.get("aliases", []) or [])
        if any(_norm_concept(str(nm)) == target for nm in names if nm):
            sup = c.get("superseded_by")
            if sup in (None, "null", "~", ""):
                return "<not superseded>"
            return str(sup)
    return "<no entry>"


def guard_lint_exists(old: str, project_root: pathlib.Path) -> str | None:
    lint_dir = project_root / "scripts" / "lint"
    cands = list(lint_dir.glob(f"no_*{old.lower()}*references.py"))
    cands += list(lint_dir.glob(f"no_{old.lower()}*.py"))
    return str(cands[0].relative_to(project_root)) if cands else None


def _run_concept_divergence(project_root: pathlib.Path) -> list[dict] | None:
    """Run find-concept-divergence ONCE and return its raw findings (parsed
    JSONL). None if the detector can't run. Both completeness bands —
    superseded_co_occurrence (band 3) and avoid_term_hit (band 1) — filter
    this single scan, so we never double-scan the tree.

    Reuse, don't rebuild — a crude old+new grep is a massive false-positive
    generator (e.g. a generic English word that is a substring of unrelated
    identifiers), and band 1 needs the glossary's per-concept `avoid:`
    phrasing, which only find-concept-divergence knows.

    Scan targets are DELEGATED to find-concept-divergence's own portable
    DEFAULT_TARGETS (it auto-skips roots that don't exist in this repo), so
    this skill stays framework-agnostic and never drifts from the detector's
    notion of what to scan — pass no positional targets."""
    script = KIT_ROOT / ".claude/skills/find-concept-divergence/scripts/scan.py"
    if not script.exists():
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            out = str(pathlib.Path(td) / "findings.jsonl")
            rep = str(pathlib.Path(td) / "report.md")
            subprocess.run([sys.executable, str(script),
                            "--project-root", str(project_root),
                            "--output", out, "--report", rep],
                           cwd=project_root, capture_output=True, text=True, timeout=180)
            findings = []
            for line in pathlib.Path(out).read_text().splitlines():
                if not line.strip():
                    continue
                findings.append(json.loads(line))
            return findings
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError):
        return None


def concept_divergence_cooccurrence(findings: list[dict] | None, old: str) -> list[str] | None:
    """The AUTHORITATIVE term-level completeness gate (band 3): from a
    find-concept-divergence scan, return the files where `old` co-occurs with
    its glossary replacement (band=superseded_co_occurrence, concept=old). None
    if the scan couldn't run.

    NOTE: this band is SKIPPED by find-concept-divergence for any concept that
    declares `coverage_lint:` (the lint owns identifier enforcement) — so for
    lint-guarded renames it is structurally empty and the avoid_term_hit band
    below is what actually proves the prose was corrected."""
    if findings is None:
        return None
    files = []
    for d in findings:
        # find-concept-divergence emits the canonical kebab slug as `concept`;
        # `old` may be an alias / CamelCase / snake form, so normalize BOTH
        # sides or the gate falsely reports GREEN.
        if (d.get("band") == "superseded_co_occurrence"
                and _norm_concept(str(d.get("concept") or "")) == _norm_concept(old)):
            files.append(d.get("file"))
    return sorted(set(files))


def concept_avoid_hits(findings: list[dict] | None, old: str, new: str) -> list[str] | None:
    """The PROSE-level completeness gate (band 1): from the SAME
    find-concept-divergence scan, return files where retired phrasing for this
    rename still appears verbatim (band=avoid_term_hit). The `avoid:` block for
    a rename lives on the NEW/canonical concept (the new slug carries the
    retired phrasings the old name used), so match the finding's `concept`
    against the NEW slug — or the OLD slug, in case the avoid block was
    authored on the deprecated entry. Unlike band 3, find-concept-divergence
    does NOT skip this band for coverage_lint concepts, so it sees
    comments/docstrings/strings the lint and the term-level gate are both blind
    to. None if the scan couldn't run."""
    if findings is None:
        return None
    new_key, old_key = _norm_concept(new), _norm_concept(old)
    files = []
    for d in findings:
        if d.get("band") != "avoid_term_hit":
            continue
        ck = _norm_concept(str(d.get("concept") or ""))
        if ck == new_key or ck == old_key:
            files.append(d.get("file"))
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--min-blast", type=int, default=3,
                    help="files below this = scope-gate bails to local rename")
    ap.add_argument("--project-root", type=pathlib.Path, default=None,
                    help="Target project root (git grep, glossary, guard lint, "
                         "divergence scan; default: git toplevel of cwd, else cwd)")
    args = ap.parse_args()
    old, new = args.old, args.new
    project_root = resolve_project_root(args.project_root)

    old_files_all = git_grep_files(old, project_root)
    old_files_live = [f for f in old_files_all if not allowed(f)]
    # Run find-concept-divergence ONCE; both completeness bands filter it.
    divergence = _run_concept_divergence(project_root)        # None if unavailable
    co_occur = concept_divergence_cooccurrence(divergence, old)      # band 3 (term co-occurrence)
    avoid_hits = concept_avoid_hits(divergence, old, new)           # band 1 (retired prose)

    supersede = read_glossary_supersede(old, project_root)
    lint = guard_lint_exists(old, project_root)

    is_concept = supersede not in ("<no entry>", "<no concepts.yaml>")
    supersede_set = supersede not in ("<not superseded>", "<no entry>", "<no concepts.yaml>")
    supersede_display = supersede if supersede_set else "(not set)"
    # Normalize BOTH sides — the glossary stores kebab slugs, but `new` may be
    # passed CamelCase/snake/spaced (e.g. `Site` vs stored `site`).
    supersede_matches_new = supersede_set and _norm_concept(supersede) == _norm_concept(new)
    wide = len(old_files_live) >= args.min_blast

    print(f"# rename-concept assess — {old} → {new}\n")
    print("## scope-gate")
    if not wide and not is_concept:
        print(f"  VERDICT: LOCAL rename ({len(old_files_live)} live files, no "
              f"glossary concept) — bail to an IDE / scoped find-and-replace.\n")
        # still print the rest for transparency
    else:
        kind = []
        if is_concept:
            kind.append("glossary concept")
        if wide:
            kind.append(f"wide-blast ({len(old_files_live)} live files)")
        print(f"  VERDICT: CONCEPT rename ({', '.join(kind)}) — run the lifecycle.\n")

    print("## lifecycle status")
    print(f"  [glossary]   concepts.yaml '{old}' superseded_by: {supersede_display}"
          f"  {'OK' if supersede_matches_new else 'MISMATCH/UNSET' if is_concept else 'n/a'}")
    print(f"  [guard lint] no_<old>_references: {lint or '(none)'}"
          f"  {'OK' if lint else 'MISSING'}")
    print(f"  [blast]      live-code files mentioning '{old}': {len(old_files_live)}"
          f"  (allowlisted residue excluded: {len(old_files_all)-len(old_files_live)})")

    print("\n## completeness gate (find-concept-divergence)")
    print("  Two bands must BOTH be clean. Band 3 (superseded_co_occurrence) is")
    print("  TERM-level identifier drift; for a coverage_lint-guarded rename the")
    print("  scanner skips it, so band 1 (avoid_term_hit) is what proves the")
    print("  retired prose — comments/docstrings/strings — was actually corrected.")

    print("\n  ### band 3 — superseded_co_occurrence (old/new identifier co-occurrence)")
    if co_occur is None:
        print("    UNAVAILABLE — could not run find-concept-divergence; band not evaluated.")
    elif not co_occur:
        print(f"    GREEN — no live file pairs the deprecated name with '{new}' "
              f"(note: skipped entirely if '{old}' declares a coverage_lint).")
    else:
        print(f"    RED — {len(co_occur)} file(s) where '{old}' co-occurs with '{new}' "
              f"(identifier transition incomplete):")
        for f in co_occur[:20]:
            print(f"      - {f}")
        if len(co_occur) > 20:
            print(f"      … (+{len(co_occur)-20} more)")

    print("\n  ### band 1 — avoid_term_hit (retired prose still using the old phrasing)")
    if avoid_hits is None:
        print("    UNAVAILABLE — could not run find-concept-divergence; band not evaluated.")
    elif not avoid_hits:
        print(f"    GREEN — no file uses a phrasing the glossary's '{new}'/'{old}' "
              f"avoid: block forbids (retired prose corrected).")
    else:
        print(f"    RED — {len(avoid_hits)} file(s) still use retired phrasing for this "
              f"rename (prose/docs not yet corrected):")
        for f in avoid_hits[:20]:
            print(f"      - {f}")
        if len(avoid_hits) > 20:
            print(f"      … (+{len(avoid_hits)-20} more)")

    if (co_occur is not None and not co_occur) and old_files_live:
        print(f"\n  NOTE: {len(old_files_live)} live file(s) still mention '{old}' "
              f"(rough grep — includes prose/comments/allowlisted residue); "
              f"eyeball for any genuinely un-renamed identifiers:")
        for f in old_files_live[:15]:
            print(f"    - {f}")
        if len(old_files_live) > 15:
            print(f"    … (+{len(old_files_live)-15} more)")

    print("\n## verdict")
    # The gate is GREEN only when BOTH bands ran and are empty. Band 1 is
    # additive to band 3 — either one non-empty turns the gate RED.
    band3_green = (co_occur is not None) and (len(co_occur) == 0)
    band1_green = (avoid_hits is not None) and (len(avoid_hits) == 0)
    gate_green = band3_green and band1_green
    done = gate_green and (supersede_matches_new if is_concept else True) and bool(lint)
    if co_occur is None or avoid_hits is None:
        print("  INCONCLUSIVE — completeness gate could not run (see above).")
    elif done and not old_files_live:
        print("  COMPLETE — both gate bands green, glossary set, guard present, no live residue.")
    elif done:
        print("  LIKELY COMPLETE — both gate bands green + glossary + guard; residual "
              "old-name-only mentions to eyeball (above).")
    else:
        missing = []
        if co_occur:
            missing.append(f"band 3 RED ({len(co_occur)} co-occurrence file(s))")
        if avoid_hits:
            missing.append(f"band 1 RED ({len(avoid_hits)} retired-prose file(s))")
        if is_concept and not supersede_matches_new:
            missing.append("glossary superseded_by not set to new")
        if not lint:
            missing.append("reintroduction guard lint absent")
        print("  HALF-APPLIED / INCOMPLETE — open: " + "; ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
