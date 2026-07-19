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
import importlib.util
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from functools import lru_cache

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


def _detector_script() -> pathlib.Path | None:
    """Find the coupled divergence scanner in an install or source checkout.

    A stock copied install puts both skills beneath `.agents/skills/`; that
    sibling is the runtime authority. The source-tree location exists solely
    for repository development and never substitutes for a missing installed
    companion in a copied host.
    """
    skills_root = SCRIPT_DIR.parents[1]
    installed = skills_root / "find-concept-divergence" / "scripts" / "scan.py"
    if SCRIPT_DIR.parents[2].name == ".agents":
        return installed if installed.exists() else None
    development = SCRIPT_DIR.parents[3] / ".claude" / "skills" / "find-concept-divergence" / "scripts" / "scan.py"
    return development if development.exists() else None


@lru_cache(maxsize=1)
def detector_module():
    """Load the coupled scanner as a module without a repository import path."""
    script = _detector_script()
    if script is None:
        return None
    spec = importlib.util.spec_from_file_location("rename_concept_divergence", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_project_root(explicit: pathlib.Path | None = None) -> pathlib.Path:
    detector = detector_module()
    if detector is not None:
        return detector.resolve_project_root(explicit)
    if explicit is not None:
        return explicit.resolve()
    return pathlib.Path.cwd().resolve()


def assessment_output_path(output: pathlib.Path, project_root: pathlib.Path) -> pathlib.Path:
    """Accept only a contained assessment report with no symlink components.

    The assessment is read-only with respect to the host source tree.  Its
    optional persistence surface is deliberately narrower: a report beneath
    ``reports/rename-concept/`` in the selected project.  Validate the logical
    path before creating parents, and reject every existing symlink component
    from ``reports/`` through the final filename.  Even an in-project symlink
    could otherwise redirect a nominal report write into host source.
    """
    project_root = project_root.resolve()
    report_root = project_root / "reports" / "rename-concept"
    candidate = output if output.is_absolute() else project_root / output
    logical_output = pathlib.Path(os.path.abspath(candidate))
    try:
        relative_output = logical_output.relative_to(report_root)
    except ValueError as exc:
        raise ValueError(
            "assessment --output must be inside "
            "<project-root>/reports/rename-concept/"
        ) from exc
    if not relative_output.parts:
        raise ValueError("assessment --output must name a file inside reports/rename-concept/")

    current = project_root
    for part in logical_output.relative_to(project_root).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"assessment output component could not be inspected: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(
                "assessment --output must not use symlink components inside "
                "reports/rename-concept/"
            )

    if logical_output.exists() and logical_output.is_dir():
        raise ValueError("assessment --output must name a file inside reports/rename-concept/")
    return logical_output


def load_glossary(path: pathlib.Path) -> dict:
    detector = detector_module()
    if detector is None:
        raise ValueError("coupled find-concept-divergence skill is unavailable")
    try:
        return detector.load_glossary(path)
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc

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
    try:
        data = load_glossary(p)
    except ValueError:
        # Unreadable/unparseable glossary degrades to the same verdict as a
        # missing one. The assessment remains an honest INCONCLUSIVE gate
        # rather than leaking an environment-specific YAML exception.
        return "<no concepts.yaml>"
    target = _norm_concept(old)
    for c in data.get("concepts", []) or []:
        aliases = c.get("aliases", [])
        names = [c.get("name", "")] + (aliases if isinstance(aliases, list) else [])
        if any(_norm_concept(str(nm)) == target for nm in names if nm):
            sup = c.get("superseded_by")
            if sup in (None, "null", "~", ""):
                return "<not superseded>"
            return str(sup)
    return "<no entry>"


def guard_lint_exists(old: str, project_root: pathlib.Path) -> str | None:
    lint_dir = project_root / "scripts" / "lint"
    token = _norm_concept(old).replace("-", "_")
    cands = list(lint_dir.glob(f"no_*{token}*references.py"))
    cands += list(lint_dir.glob(f"no_{token}*.py"))
    if token != old.lower():
        cands += list(lint_dir.glob(f"no_*{old.lower()}*references.py"))
        cands += list(lint_dir.glob(f"no_{old.lower()}*.py"))
    return str(cands[0].relative_to(project_root)) if cands else None


def typescript_source_files(project_root: pathlib.Path) -> list[str]:
    """Return root-relative TS/TSX files on the same safe scan surface.

    The coupled scanner is deliberately lexical. Presence of a TypeScript
    source surface therefore blocks a terminal identifier-completeness claim:
    declarations, imports, aliases, property keys, strings, and comments need
    a TypeScript-aware resolver to distinguish them.
    """
    detector = detector_module()
    if detector is None:
        return []
    return sorted(
        path.relative_to(project_root).as_posix()
        for path in detector.iter_files(detector.DEFAULT_TARGETS, project_root)
        if path.suffix in {".ts", ".tsx"}
    )


def concept_terms(concept: str, project_root: pathlib.Path) -> list[str]:
    """Return the glossary name and aliases for one requested concept."""
    try:
        glossary = load_glossary(project_root / ".claude/contracts/concepts.yaml")
    except ValueError:
        return [concept]
    target = _norm_concept(concept)
    for entry in glossary.get("concepts", []):
        if not isinstance(entry, dict):
            continue
        aliases = entry.get("aliases")
        names = [entry.get("name")] + (aliases if isinstance(aliases, list) else [])
        if any(_norm_concept(str(name)) == target for name in names if name):
            return [str(name) for name in names if isinstance(name, str) and name]
    return [concept]


def run_typescript_identifier_evidence(
    project_root: pathlib.Path,
    old_terms: list[str],
    new_terms: list[str],
    sources: list[str],
) -> dict:
    """Invoke the host-pinned TypeScript Compiler API runner without mutation."""
    node = shutil.which("node")
    runner = pathlib.Path(__file__).resolve().with_name("typescript_identifier_evidence.mjs")
    if not node:
        return {"status": "unavailable", "reason": "node executable is unavailable"}
    if not runner.exists():
        return {"status": "unavailable", "reason": "bundled TypeScript evidence runner is missing"}
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = pathlib.Path(temp_dir) / "typescript-identifiers.json"
            result = subprocess.run(
                [
                    node,
                    str(runner),
                    "--project-root", str(project_root),
                    "--old-terms", json.dumps(old_terms),
                    "--new-terms", json.dumps(new_terms),
                    "--sources", json.dumps(sources),
                    "--output", str(output),
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if not output.exists():
                return {
                    "status": "unavailable",
                    "reason": f"TypeScript evidence runner exited {result.returncode}",
                }
            evidence = json.loads(output.read_text(encoding="utf-8"))
            if result.returncode != 0 and evidence.get("status") == "resolved":
                return {"status": "unavailable", "reason": "TypeScript evidence runner failed"}
            return evidence
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "unavailable", "reason": str(exc)}


def classify_lexical_candidates(findings: list[dict] | None, old: str, evidence: dict) -> list[dict]:
    """Classify band-3 hits with compiler identity or text-only evidence."""
    occurrences = evidence.get("occurrences") if isinstance(evidence, dict) else []
    if not isinstance(occurrences, list):
        occurrences = []
    by_key = {
        (item.get("file"), item.get("line"), _norm_concept(str(item.get("name") or ""))): item
        for item in occurrences
        if isinstance(item, dict)
    }
    candidates: list[dict] = []
    for finding in findings or []:
        if (
            finding.get("band") != "superseded_co_occurrence"
            or _norm_concept(str(finding.get("concept") or "")) != _norm_concept(old)
        ):
            continue
        key = (
            finding.get("file"),
            finding.get("line"),
            _norm_concept(str(finding.get("term") or "")),
        )
        occurrence = by_key.get(key)
        if occurrence:
            classification = occurrence.get("classification", "unresolved_identifier")
        else:
            classification = _text_only_candidate_kind(finding)
        candidates.append({
            "file": finding.get("file"),
            "line": finding.get("line"),
            "term": finding.get("term"),
            "classification": classification,
        })
    return candidates


def _text_only_candidate_kind(finding: dict) -> str:
    """Separate obvious comment/string hits that have no AST identifier node."""
    line = str(finding.get("match") or "")
    term = str(finding.get("term") or "")
    position = line.lower().find(term.lower())
    if position < 0:
        return "non_identifier_text"
    comment = min((index for index in (line.find("//"), line.find("/*")) if index >= 0), default=-1)
    if comment >= 0 and comment < position:
        return "comment_text"
    prefix = line[:position]
    if any(prefix.count(quote) % 2 for quote in ('"', "'", "`")):
        return "string_literal"
    return "non_identifier_text"


def _run_concept_divergence(project_root: pathlib.Path) -> list[dict] | None:
    """Run find-concept-divergence ONCE and return its raw findings (parsed
    JSONL). None if the detector can't run. Both completeness bands —
    superseded_co_occurrence (band 3) and avoid_term_hit (band 1) — filter
    this single scan, so we never double-scan the tree.

    Reuse, don't rebuild — a crude old+new grep is a massive false-positive
    generator (e.g. a generic English word that is a substring of unrelated
    identifiers), and band 1 needs the glossary's per-concept `avoid:`
    phrasing, which only find-concept-divergence knows.

    Scan targets are delegated to the coupled, stdlib-only detector. Its
    portable DEFAULT_TARGETS and project-root-relative exclusions are the
    single lexical authority for this assessment. Pass no positional targets.
    """
    script = _detector_script()
    if script is None:
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            out = str(pathlib.Path(td) / "findings.jsonl")
            rep = str(pathlib.Path(td) / "report.md")
            result = subprocess.run([sys.executable, str(script),
                                     "--project-root", str(project_root),
                                     "--output", out, "--report", rep],
                                    cwd=project_root, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                return None
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
    ap.add_argument("--output", type=pathlib.Path, default=None,
                    help="Optional JSON under reports/rename-concept/ (source files remain read-only)")
    args = ap.parse_args()
    old, new = args.old, args.new
    project_root = resolve_project_root(args.project_root)
    output = None
    if args.output is not None:
        try:
            output = assessment_output_path(args.output, project_root)
        except ValueError as exc:
            ap.error(str(exc))

    old_files_all = git_grep_files(old, project_root)
    old_files_live = [f for f in old_files_all if not allowed(f)]
    # Run find-concept-divergence ONCE; both completeness bands filter it.
    divergence = _run_concept_divergence(project_root)        # None if unavailable
    co_occur = concept_divergence_cooccurrence(divergence, old)      # band 3 (term co-occurrence)
    avoid_hits = concept_avoid_hits(divergence, old, new)           # band 1 (retired prose)

    supersede = read_glossary_supersede(old, project_root)
    lint = guard_lint_exists(old, project_root)
    typescript_files = typescript_source_files(project_root)
    typescript_evidence = (
        run_typescript_identifier_evidence(
            project_root,
            concept_terms(old, project_root),
            concept_terms(new, project_root),
            typescript_files,
        )
        if typescript_files
        else None
    )
    lexical_candidates = classify_lexical_candidates(divergence, old, typescript_evidence or {})

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
    if typescript_files:
        if typescript_evidence and typescript_evidence.get("status") == "resolved":
            declarations = typescript_evidence.get("declarations", {})
            occurrences = typescript_evidence.get("occurrences", [])
            old_declarations = len(declarations.get("old", [])) if isinstance(declarations, dict) else 0
            new_declarations = len(declarations.get("new", [])) if isinstance(declarations, dict) else 0
            resolution_diagnostics = len(typescript_evidence.get("resolution_diagnostics", []))
            old_references = sum(
                item.get("classification") == "old_concept_symbol"
                for item in occurrences
                if isinstance(item, dict)
            )
            print("  [identifiers] TypeScript/TSX: RESOLVED — compiler API "
                  f"{typescript_evidence.get('typescript_version', '?')}; "
                  f"old declarations={old_declarations}, old references={old_references}, "
                  f"new declarations={new_declarations}, resolution diagnostics={resolution_diagnostics}.")
        else:
            reason = (typescript_evidence or {}).get("reason", "unknown resolver failure")
            print("  [identifiers] TypeScript/TSX: UNAVAILABLE — " + str(reason))

    print("\n## completeness gate (find-concept-divergence)")
    print("  Two bands must BOTH be clean. Band 3 (superseded_co_occurrence) is")
    print("  lexical old/new candidate drift; for a coverage_lint-guarded rename the")
    print("  scanner skips it, so band 1 (avoid_term_hit) is what proves the")
    print("  retired prose — comments/docstrings/strings — was actually corrected.")

    print("\n  ### band 3 — superseded_co_occurrence (old/new lexical co-occurrence candidates)")
    if co_occur is None:
        print("    UNAVAILABLE — could not run find-concept-divergence; band not evaluated.")
    elif not co_occur:
        print(f"    GREEN — no live file pairs the deprecated name with '{new}' "
              f"(note: skipped entirely if '{old}' declares a coverage_lint).")
    else:
        print(f"    RED — {len(co_occur)} file(s) where '{old}' co-occurs with '{new}' "
              f"(see resolved identifier evidence below):")
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

    if typescript_files:
        print("\n  ### TypeScript identifier evidence (compiler API)")
        if not typescript_evidence or typescript_evidence.get("status") != "resolved":
            print("    UNAVAILABLE — cannot certify TypeScript identifier completeness.")
        elif not lexical_candidates:
            print("    RESOLVED — no old/new lexical co-occurrence candidates required classification.")
        else:
            print("    Candidate classifications:")
            for candidate in lexical_candidates[:20]:
                print("      - " + f"{candidate['file']}:{candidate['line']} "
                      f"`{candidate['term']}` → {candidate['classification']}")
            if len(lexical_candidates) > 20:
                print(f"      … (+{len(lexical_candidates)-20} more)")

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
    evidence_resolved = bool(typescript_evidence and typescript_evidence.get("status") == "resolved")
    evidence_declarations = (typescript_evidence or {}).get("declarations", {})
    evidence_occurrences = (typescript_evidence or {}).get("occurrences", [])
    old_symbol_references = sum(
        item.get("classification") == "old_concept_symbol"
        for item in evidence_occurrences
        if isinstance(item, dict)
    )
    unresolved_identifiers = sum(
        item.get("classification") == "unresolved_identifier"
        for item in evidence_occurrences
        if isinstance(item, dict)
    )
    new_symbol_declarations = len(evidence_declarations.get("new", [])) if isinstance(evidence_declarations, dict) else 0
    resolution_diagnostics = len((typescript_evidence or {}).get("resolution_diagnostics", []))
    typescript_complete = (
        not typescript_files
        or (
            evidence_resolved
            and old_symbol_references == 0
            and unresolved_identifiers == 0
            and new_symbol_declarations > 0
            and resolution_diagnostics == 0
        )
    )
    open_items: list[str] = []
    if co_occur is None or avoid_hits is None:
        verdict = "INCONCLUSIVE"
        print("  INCONCLUSIVE — completeness gate could not run (see above).")
    elif not typescript_complete:
        missing: list[str] = []
        if not evidence_resolved:
            missing.append("TypeScript compiler evidence unavailable")
        if old_symbol_references:
            missing.append(f"old concept symbol references ({old_symbol_references})")
        if unresolved_identifiers:
            missing.append(f"unresolved identifier candidates ({unresolved_identifiers})")
        if resolution_diagnostics:
            missing.append(f"compiler diagnostics affecting resolution ({resolution_diagnostics})")
        if not new_symbol_declarations:
            missing.append("no resolved new concept declaration")
        if avoid_hits:
            missing.append(f"band 1 retired prose ({len(avoid_hits)} file(s))")
        if is_concept and not supersede_matches_new:
            missing.append("glossary superseded_by not set to new")
        if not lint:
            missing.append("reintroduction guard lint absent")
        verdict = "HALF-APPLIED / INCOMPLETE"
        open_items = missing
        print("  HALF-APPLIED / INCOMPLETE — open: " + "; ".join(missing))
    elif done and not old_files_live:
        verdict = "COMPLETE"
        print("  COMPLETE — both gate bands green, glossary set, guard present, no live residue.")
    elif done:
        verdict = "LIKELY COMPLETE"
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
        verdict = "HALF-APPLIED / INCOMPLETE"
        open_items = missing
        print("  HALF-APPLIED / INCOMPLETE — open: " + "; ".join(missing))
    if output:
        payload = {
            "skill": "rename-concept",
            "project_root": str(project_root),
            "old": old,
            "new": new,
            "read_only": True,
            "lifecycle": {
                "glossary_superseded_by": supersede,
                "supersede_matches_new": supersede_matches_new,
                "guard_lint": lint,
                "old_files_live": old_files_live,
            },
            "lexical_gate": {
                "superseded_cooccurrence_files": co_occur,
                "retired_prose_files": avoid_hits,
                "candidate_classifications": lexical_candidates,
            },
            "typescript_identifier_evidence": typescript_evidence,
            "verdict": verdict,
            "open_items": open_items,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nassessment JSON → {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
