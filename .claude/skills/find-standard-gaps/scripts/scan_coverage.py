#!/usr/bin/env python3
"""Run executable standard detectors — compute application-coverage gaps.

Gap-enumeration model (see knowledge/detector-model.md): a detector is
lint-shaped. It finds a *situation* site and reports it as a **gap** when
the standard's satisfaction condition is absent.

Input: a JSON file with an `ideas` array — a standards file
`{"ideas": [{id, label, contract:{detector}}]}`.

Detector kinds:
  - `grep` — regex `situation` + optional `satisfied_by`, line-scoped
    (`scope` = window | file). Cross-language (operates on text) but
    comment/string-blind. If `satisfied_by` is omitted, every situation
    match is a gap (a pure-prohibition standard).
  - `ast`  — `call_matches` regex on a call's dotted name, plus one
    satisfaction condition: `enclosed_by` (`try`|`with`) or
    `requires_kwarg`. Python uses CPython's AST; TypeScript/TSX supports
    the direct-syntax `enclosed_by: try` form through the host-local
    TypeScript Compiler API. Neither branch matches comments/strings.
  - `skill` — recognised, not implemented in v1.
  - `manual` — skipped; checked by hand.

Per-standard status in the output:
  - `gated_out`           — the standard's `activation` (ADR 0020) is
                            NOT in scope for the project's declared
                            (maturity, stakes). Computed BEFORE the
                            detector — it is NOT scanned, NOT counted as
                            gaps, and is NEVER a "0 gaps" pass.
  - `scanned`             — fully ran; see gaps.
  - `partial`             — some files could not be read/parsed or had an
                            unsupported extension. Findings from supported
                            files are useful triage evidence but the standard
                            is not clean/compliant.
  - `no_files_matched`    — the detector's `paths` matched nothing. A
                            misconfigured glob / project-root — NOT a
                            pass.
  - `language_unsupported`— an `ast` standard whose source language or
                            condition is unsupported, or whose TypeScript
                            prerequisite cannot be established.
  - `skipped` / `error`   — manual/skill detector, or a malformed one.
A "0 gaps" result is only trustworthy under `status: scanned`.

Standard activation (ADR 0020): each standard may carry an `activation`
of `{"baseline": true}` or `{"rungs": [{min_maturity, min_stakes}, ...]}`.
The project's state is read from
`<project-root>/.engineering/project-state.json`, with a legacy
`<project-root>/.project-state.json` fallback (maturity x stakes). A
standard is gated in scope BEFORE its detector runs; if no state file is
found, MAX (production / public-adversarial) is assumed so nothing is
silently skipped, with a prominent warning to run `/orient`. See
knowledge/detector-model.md and project_state.py.

The Python runner is stdlib-only. JavaScript/TypeScript scans additionally require Node and
the host's project-local `typescript` package. Read-only against the codebase.

Usage:
    python3 scan_coverage.py --ideas path/to/standards.json \\
        --project-root "$(pwd)" \\
        --output-dir reports/standard-gaps/scan-<TS>
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# project_state lives beside this script; add our own dir to sys.path so
# the import works whether the script is run directly or imported by a
# test that has not put this directory on the path.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from project_state import (  # noqa: E402
    assumed_max_state,
    load_project_state,
    load_state_file,
    resolve_project_state_path,
    standard_in_scope,
)

SKIP_DIRS = {".venv", "__pycache__", "migrations", ".git", "node_modules",
             "tests", "experiments", "worktrees"}
# `worktrees` (e.g. `.claude/worktrees/<name>/`) holds full repo checkouts
# created for agent isolation. Scanning them double-counts the whole tree —
# a dogfood run on a host project with one stale worktree inflated every
# `**/*.py` detector ~10x (e.g. eval/exec: 462 of 483 hits were the worktree
# copy). They are repo copies, never first-party source — skip like `.git`.

# Python 3.11+ `try/except*` is a distinct node; treat it like `try`.
_TRY_TYPES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())

SCRIPT_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
TYPESCRIPT_SKIP_DIRS = {
    "__tests__", "build", "coverage", "dist", "fixture", "fixtures",
    "generated", "reports", "spec", "specs", "test", "tests", "vendor",
}
TYPESCRIPT_SKIP_FILE_GLOBS = (
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


def iter_files(root: Path, globs: list[str]) -> list[Path]:
    """All project-root-relative glob matches, minus generic excluded trees.

    The globs are the file selector — `app/**/*.py` already restricts to
    Python; this function does not second-guess the extension. Note
    SKIP_DIRS is fixed (tests / experiments / vendored dirs are never
    scanned) — a standard cannot currently opt back in.
    """
    root = root.resolve()
    seen: set[Path] = set()
    out: list[Path] = []
    for glob in globs:
        if Path(glob).is_absolute():
            raise ValueError("detector paths must be project-root-relative")
        for path in sorted(root.glob(glob)):
            try:
                path.resolve().relative_to(root)
            except ValueError:
                # A direct symlinked directory/file that escapes the project
                # is never a valid source root or source file.
                continue
            candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
            for candidate in candidates:
                if not candidate.is_file():
                    continue
                try:
                    resolved = candidate.resolve()
                    physical_rel = resolved.relative_to(root)
                except ValueError:
                    # A symlink beneath the project root that escapes it is
                    # not first-party source, even when a direct path selected it.
                    continue
                logical_rel = candidate.relative_to(root)
                if (any(part in SKIP_DIRS for part in logical_rel.parts[:-1])
                        or any(part in SKIP_DIRS for part in physical_rel.parts[:-1])):
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                out.append(candidate)
    return out


def _typescript_path_is_excluded(path: Path, root: Path) -> bool:
    """Whether a TS/TSX candidate is outside this skill's source policy.

    Evaluate against the project root, not a narrowed detector glob, so a
    direct target under `vendor/` or `tests/` cannot bypass the exclusion.
    """
    root = root.resolve()
    try:
        logical_rel = path.relative_to(root)
        physical_rel = path.resolve().relative_to(root)
    except ValueError:
        return True
    skipped = SKIP_DIRS | TYPESCRIPT_SKIP_DIRS
    return (
        any(part.lower() in skipped for part in logical_rel.parts[:-1])
        or any(part.lower() in skipped for part in physical_rel.parts[:-1])
        or any(
            fnmatch.fnmatchcase(path.name.lower(), glob.lower())
            for glob in TYPESCRIPT_SKIP_FILE_GLOBS
        )
    )


def _dotted(node: ast.AST) -> str:
    """Reconstruct a dotted name from a Name/Attribute chain.

    Returns "" when the receiver is unresolvable (e.g. `factory().connect`)
    rather than collapsing to the bare attribute name — a bare-name
    detector should not match an unresolvable call.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""


# --------------------------------------------------------------------------
def run_grep_detector(root: Path, detector: dict):
    """Return ({...}, error_or_None). Cross-language (operates on text)."""
    try:
        situation = re.compile(detector["situation"])
    except KeyError as exc:
        return None, f"grep detector missing field: {exc}"
    except re.error as exc:
        return None, f"grep detector has an invalid regex: {exc}"
    sat_src = detector.get("satisfied_by")
    try:
        satisfied = re.compile(sat_src) if sat_src else None
    except re.error as exc:
        return None, f"grep detector satisfied_by is an invalid regex: {exc}"

    paths = detector.get("paths") or ["app/**/*.py"]
    scope = detector.get("scope", "window")
    if scope not in ("window", "file"):
        return None, f"grep detector scope must be window|file, got {scope!r}"
    try:
        window = int(detector.get("window", 20))
    except (TypeError, ValueError):
        return None, "grep detector window must be an integer"
    if window < 0:
        return None, "grep detector window must be >= 0"

    try:
        files = iter_files(root, paths)
    except ValueError as exc:
        return None, str(exc)
    if not files:
        return {"no_files": True}, None

    sites: list[dict] = []
    gaps: list[dict] = []
    analyzed = 0
    skipped = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            skipped += 1
            continue
        analyzed += 1
        file_satisfied = satisfied is not None and bool(satisfied.search("\n".join(lines)))
        for idx, line in enumerate(lines):
            if not situation.search(line):
                continue
            site = {"file": str(path.relative_to(root)), "line": idx + 1,
                    "text": line.strip()[:120]}
            sites.append(site)
            if satisfied is None:
                ok = False  # pure-prohibition standard — every match is a gap
            elif scope == "file":
                ok = file_satisfied
            else:
                lo, hi = max(0, idx - window), min(len(lines), idx + window + 1)
                ok = bool(satisfied.search("\n".join(lines[lo:hi])))
            if not ok:
                gaps.append(site)
    return {"sites": sites, "gaps": gaps,
            "scanned_files": analyzed, "skipped_files": skipped}, None


def _typescript_preflight(root: Path) -> str | None:
    """Return an unavailable-reason unless host Node + TypeScript are usable."""
    launcher = Path(__file__).resolve().with_name("detect_typescript_calls.mjs")
    try:
        result = subprocess.run(
            ["node", str(launcher), "--check", "--project-root", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return f"cannot run the bundled TypeScript parser: {exc}"
    if result.returncode != 0:
        return result.stderr.strip() or result.stdout.strip() or "TypeScript parser preflight failed"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "bundled TypeScript parser preflight emitted invalid JSON"
    if payload != {"ok": True}:
        return "bundled TypeScript parser preflight emitted an invalid response"
    return None


def _typescript_calls(path: Path, root: Path) -> tuple[list[dict] | None, str | None]:
    """Return direct syntax call facts, or the file-local parse failure."""
    launcher = Path(__file__).resolve().with_name("detect_typescript_calls.mjs")
    try:
        result = subprocess.run(
            ["node", str(launcher), "--file", str(path), "--project-root", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, f"cannot run the bundled TypeScript parser: {exc}"
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip() or "TypeScript parser failed"
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, "bundled TypeScript parser emitted invalid JSON"
    if not isinstance(records, list):
        return None, "bundled TypeScript parser emitted a non-list result"
    validated: list[dict] = []
    for record in records:
        try:
            name = record["name"]
            line = record["line"]
            text = record["text"]
            in_try = record["in_try"]
        except (KeyError, TypeError):
            return None, "bundled TypeScript parser emitted an invalid call record"
        if not isinstance(name, str) or not isinstance(line, int):
            return None, "bundled TypeScript parser emitted an invalid call record"
        if not isinstance(text, str) or not isinstance(in_try, bool):
            return None, "bundled TypeScript parser emitted an invalid call record"
        validated.append(record)
    return validated, None


def run_ast_detector(root: Path, detector: dict):
    """Return ({...}, error_or_None) for Python plus narrow TS/TSX syntax.

    Possible result shapes: `{no_files}`, `{unsupported}`, or
    `{sites, gaps, scanned_files, skipped_files}`. A file that fails to
    read/parse — or whose traversal hits the recursion limit — is counted
    as `skipped`, never silently folded into `scanned_files`. A matched file
    with an unsupported extension is counted separately so the orchestrator
    can report an otherwise useful supported-file scan as partial.

    Finds Call nodes whose dotted name matches `call_matches`, then checks
    one satisfaction condition — exactly one of `enclosed_by` (`try`|
    `with`, lexical block scope) or `requires_kwarg` (a `**kwargs` spread
    counts as satisfied). A gap = a matched call that fails the condition.
    Enclosure resets at a nested-function *body*; decorators and default
    arguments inherit the enclosing scope. TypeScript/TSX supports the direct
    syntactic `enclosed_by: try` form only, using the host's local TypeScript
    Compiler API. It does not resolve aliases, types, receivers, or frameworks.
    """
    try:
        call_re = re.compile(detector["call_matches"])
    except KeyError as exc:
        return None, f"ast detector missing field: {exc}"
    except re.error as exc:
        return None, f"ast detector has an invalid regex: {exc}"
    enclosed_by = detector.get("enclosed_by")
    requires_kwarg = detector.get("requires_kwarg")
    if bool(enclosed_by) == bool(requires_kwarg):
        return None, "ast detector needs exactly one of enclosed_by / requires_kwarg"
    if enclosed_by and enclosed_by not in ("try", "with"):
        return None, f"ast detector enclosed_by must be try|with, got {enclosed_by!r}"

    paths = detector.get("paths") or ["app/**/*.py"]
    try:
        matched = iter_files(root, paths)
    except ValueError as exc:
        return None, str(exc)
    if not matched:
        return {"no_files": True}, None
    py_files = [f for f in matched if f.suffix == ".py"]
    ts_candidates = [f for f in matched if f.suffix.lower() in SCRIPT_SUFFIXES]
    ts_files = [f for f in ts_candidates if not _typescript_path_is_excluded(f, root)]
    unsupported_files = [
        f for f in matched
        if f.suffix != ".py" and f.suffix.lower() not in SCRIPT_SUFFIXES
    ]
    if not py_files and not ts_files:
        if unsupported_files:
            exts = sorted({f.suffix.lower() or "<none>" for f in unsupported_files})
            return {"unsupported": True, "matched": len(unsupported_files),
                    "extensions": exts[:8]}, None
        if ts_candidates:
            return {"no_files": True, "excluded": True}, None
    if ts_files and requires_kwarg:
        return {"unsupported": True, "matched": len(ts_files),
                "extensions": sorted({f.suffix.lower() for f in ts_files}),
                "reason": "the JavaScript/TypeScript `ast` branch supports only "
                          "`enclosed_by: try`; `requires_kwarg` names Python "
                          "call syntax and has no equivalent detector contract yet"}, None
    if ts_files and enclosed_by == "with":
        return {"unsupported": True, "matched": len(ts_files),
                "extensions": sorted({f.suffix.lower() for f in ts_files}),
                "reason": "the JavaScript/TypeScript `ast` branch supports only "
                          "`enclosed_by: try`; JavaScript/TypeScript has no "
                          "Python-style `with` block"}, None
    if ts_files:
        unavailable = _typescript_preflight(root)
        if unavailable:
            if py_files:
                unsupported_files.extend(ts_files)
                ts_files = []
            else:
                return {"unsupported": True, "matched": len(ts_files),
                        "extensions": sorted({f.suffix.lower() for f in ts_files}),
                        "reason": unavailable}, None

    sites: list[dict] = []
    gaps: list[dict] = []
    analyzed = 0
    skipped = 0
    for path in py_files:
        rel = str(path.relative_to(root))
        file_sites: list[dict] = []
        file_gaps: list[dict] = []
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
            srclines = src.splitlines()

            # `visit` is defined inside the per-file loop; bind the
            # per-file state as default args so the closure captures this
            # iteration's values, not the loop variable (ruff B023).
            def visit(node: ast.AST, in_try: bool, in_with: bool,
                      srclines: list[str] = srclines, rel: str = rel,
                      file_sites: list[dict] = file_sites,
                      file_gaps: list[dict] = file_gaps) -> None:
                if isinstance(node, ast.Call):
                    name = _dotted(node.func)
                    if name and call_re.search(name):
                        ln = getattr(node, "lineno", 0)
                        text = (srclines[ln - 1].strip()[:120]
                                if 0 < ln <= len(srclines) else "")
                        site = {"file": rel, "line": ln, "text": text}
                        file_sites.append(site)
                        if requires_kwarg:
                            kw = {k.arg for k in node.keywords}
                            ok = requires_kwarg in kw or None in kw
                        else:
                            ok = in_try if enclosed_by == "try" else in_with
                        if not ok:
                            file_gaps.append(site)
                if isinstance(node, _TRY_TYPES):
                    for child in node.body:
                        visit(child, True, in_with)
                    for child in (*node.handlers, *node.orelse, *node.finalbody):
                        visit(child, in_try, in_with)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        # the context-manager expression IS the `with` —
                        # count it as in_with so `with open(...)` satisfies
                        # an enclosed_by:with standard.
                        visit(item.context_expr, in_try, True)
                        if item.optional_vars is not None:
                            visit(item.optional_vars, in_try, in_with)
                    for child in node.body:
                        visit(child, in_try, True)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # decorators / default args / annotations run in the
                    # enclosing scope; only the body resets enclosure.
                    for deco in node.decorator_list:
                        visit(deco, in_try, in_with)
                    visit(node.args, in_try, in_with)
                    if node.returns is not None:
                        visit(node.returns, in_try, in_with)
                    for child in node.body:
                        visit(child, False, False)
                elif isinstance(node, ast.Lambda):
                    visit(node.args, in_try, in_with)
                    visit(node.body, False, False)
                else:
                    for child in ast.iter_child_nodes(node):
                        visit(child, in_try, in_with)

            visit(tree, False, False)
        except (SyntaxError, UnicodeDecodeError, OSError, ValueError,
                RecursionError):
            skipped += 1
            continue
        analyzed += 1
        sites.extend(file_sites)
        gaps.extend(file_gaps)
    for path in ts_files:
        rel = str(path.relative_to(root))
        records, parse_error = _typescript_calls(path, root)
        if parse_error or records is None:
            skipped += 1
            continue
        analyzed += 1
        for record in records:
            name = record["name"]
            if not name or not call_re.search(name):
                continue
            site = {"file": rel, "line": record["line"], "text": record["text"][:120]}
            sites.append(site)
            if not record["in_try"]:
                gaps.append(site)
    sites.sort(key=lambda site: (site["file"], site["line"], site["text"]))
    gaps.sort(key=lambda site: (site["file"], site["line"], site["text"]))
    result = {"sites": sites, "gaps": gaps,
              "scanned_files": analyzed, "skipped_files": skipped}
    if unsupported_files:
        result["unsupported_files"] = len(unsupported_files)
        result["unsupported_extensions"] = sorted(
            {f.suffix.lower() or "<none>" for f in unsupported_files},
        )
    return result, None


# --------------------------------------------------------------------------
def analyze_idea(root: Path, idea: dict, state: dict) -> dict:
    detector = (idea.get("contract") or {}).get("detector") or {}
    kind = detector.get("kind", "none")
    base = {"id": idea.get("id", "?"), "label": idea.get("label", ""),
            "detector_kind": kind}

    # Activation gate (ADR 0020) runs FIRST — with precedence over detector
    # kind. A standard not in scope for the project's declared state is
    # reported `gated_out`: not scanned, not a gap, not a "0 gaps" pass.
    in_scope, reason = standard_in_scope(idea.get("activation"), state)
    if not in_scope:
        return {**base, "status": "gated_out", "reason": reason}

    runner = {"grep": run_grep_detector, "ast": run_ast_detector}.get(kind)
    if runner:
        result, err = runner(root, detector)
        if err:
            return {**base, "status": "error", "error": err}
        if result.get("no_files"):
            globs = detector.get("paths") or ["app/**/*.py"]
            excluded = (
                " All matched TypeScript/TSX files were excluded by the fixed "
                "source policy."
                if result.get("excluded") else ""
            )
            return {**base, "status": "no_files_matched",
                    "error": f"the detector's `paths` ({', '.join(globs)}) "
                             f"matched no files — check the globs and "
                             f"--project-root.{excluded} This is NOT a passing result."}
        if result.get("unsupported"):
            reason = result.get("reason") or (
                "the `ast` detector supports Python and JavaScript/TypeScript only; "
                f"{result['matched']} file(s) matched `paths` but none are supported "
                f"source files (found: {', '.join(result['extensions'])})."
            )
            return {**base, "status": "language_unsupported",
                    "matched": result["matched"], "extensions": result["extensions"],
                    "error": reason}
        sites, gaps = result["sites"], result["gaps"]
        skipped_files = result["skipped_files"]
        unsupported_files = result.get("unsupported_files", 0)
        analyzed = {**base,
                    "status": "partial" if skipped_files or unsupported_files else "scanned",
                    "scanned_files": result["scanned_files"],
                    "skipped_files": skipped_files,
                    "situation_sites": len(sites), "gaps": gaps,
                    "coverage": round((len(sites) - len(gaps)) / len(sites), 4)
                    if sites else None}
        if unsupported_files:
            analyzed["unsupported_files"] = unsupported_files
            analyzed["unsupported_extensions"] = result["unsupported_extensions"]
        return analyzed
    if kind == "skill":
        return {**base, "status": "skipped",
                "error": "detector kind 'skill' is not implemented in v1"}
    return {**base, "status": "skipped",
            "error": "no executable detector (kind manual / none)"}


def render_report(source: str, results: list[dict], state: dict) -> str:
    assumed = state.get("assumed") is True
    state_line = (f"maturity=`{state.get('maturity', '?')}` · "
                  f"stakes=`{state.get('stakes', '?')}`"
                  + (" (ASSUMED MAX — no project state declared)" if assumed else ""))
    L = [f"# Application-coverage scan — {source}", "",
         f"_Scanned {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
         f"by scan_coverage.py._",
         f"_Project state: {state_line}_", ""]
    if assumed:
        L += ["> ⚠ **No project state declared** — assuming MAX "
              "(production / public-adversarial) so no standard is silently "
              "skipped. Run `/orient` to declare the project's real "
              "(maturity, stakes) and gate stakes-driven rungs honestly.", ""]
    scanned = [r for r in results if r["status"] == "scanned"]
    partial = [r for r in results if r["status"] == "partial"]
    analyzed = [*scanned, *partial]
    with_gaps = [r for r in analyzed if r["gaps"]]
    gated = [r for r in results if r["status"] == "gated_out"]
    unsupported = [r for r in results if r["status"] == "language_unsupported"]
    no_files = [r for r in results if r["status"] == "no_files_matched"]
    L += ["## Summary", "",
          f"- {len(results)} standard(s) in input; {len(scanned)} fully scanned, "
          f"{len(partial)} partial, {len(gated)} gated out (out of scope at the declared state)",
          f"- **{sum(len(r['gaps']) for r in analyzed)} coverage gap(s)** "
          f"across {len(with_gaps)} standard(s)"]
    if partial:
        L.append(f"- ⚠ {len(partial)} standard(s) **partial** — one or more files "
                 "could not be read/parsed or had unsupported extensions; these are not "
                 "clean/compliant results")
    if gated:
        L.append(f"- {len(gated)} standard(s) **gated out** — not in scope for "
                 f"`{state.get('maturity', '?')}/{state.get('stakes', '?')}`; "
                 f"NOT scanned and NOT a \"0 gaps\" pass")
    if unsupported:
        L.append(f"- ⚠ {len(unsupported)} standard(s) **language-unsupported** — "
                 "the requested language, detector condition, or TypeScript "
                 "prerequisite could not be analyzed; see SKILL.md "
                 "\"TypeScript/TSX support and limits\"")
    if no_files:
        L.append(f"- ⚠ {len(no_files)} standard(s) matched **no files** — a "
                 f"misconfigured glob; NOT a passing result")
    L.append("")

    # Gated-out standards get their own clearly-labelled section: they were
    # never scanned, so folding them into the per-standard list below would
    # blur "0 gaps" (a pass) with "out of scope" (not even checked).
    if gated:
        L += ["## Gated out (out of scope at the declared state)", "",
              "_These standards' activation thresholds are not met by the "
              "project's declared (maturity, stakes). They were NOT scanned — "
              "this is not a passing result, it is \"does not apply yet\". "
              "Raising the declared state via `/orient` may activate them._",
              ""]
        for r in gated:
            L.append(f"### `{r['id']}` — {r['label']}")
            L.append(f"- _gated_out: {r.get('reason', '')}_")
            L.append("")

    L += ["## Scanned & other statuses", ""]
    for r in results:
        if r["status"] == "gated_out":
            continue  # already listed in the gated-out section above
        L.append(f"### `{r['id']}` — {r['label']}")
        if r["status"] in ("scanned", "partial"):
            sites = r["situation_sites"]
            cov = "n/a" if not sites else f"{int(100 * (sites - len(r['gaps'])) / sites)}%"
            skipped = f", {r['skipped_files']} skipped" if r["skipped_files"] else ""
            unsupported_files = r.get("unsupported_files", 0)
            unsupported_display = (
                f", {unsupported_files} unsupported "
                f"({', '.join(r['unsupported_extensions'])})"
                if unsupported_files else ""
            )
            L.append(f"- detector: `{r['detector_kind']}` · "
                     f"{sites} situation site(s), **{len(r['gaps'])} gap(s)**, "
                     f"coverage {cov} ({r['scanned_files']} files analyzed{skipped}"
                     f"{unsupported_display})")
            if r["status"] == "partial":
                causes = []
                if r["skipped_files"]:
                    causes.append("skipped files")
                if unsupported_files:
                    causes.append("unsupported extensions")
                L.append("- ⚠ _partial: " + " and ".join(causes)
                         + " mean this result is not clean/compliant_")
            for g in r["gaps"]:
                L.append(f"  - `{g['file']}:{g['line']}` — {g['text']}")
        else:
            L.append(f"- _{r['status']}: {r.get('error', '')}_")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ideas", required=True, type=Path,
                    help="JSON file with an `ideas` array (a standards file)")
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--project-state", type=Path, default=None,
                    help="path to the project-state file (default: "
                         "<project-root>/.engineering/project-state.json, with a "
                         "legacy <project-root>/.project-state.json fallback). "
                         "Declares (maturity, stakes); gates each standard's "
                         "activation (ADR 0020) before its detector runs.")
    args = ap.parse_args()

    try:
        doc = json.loads(args.ideas.read_text())
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.exit(f"error: cannot read --ideas: {exc}")
    ideas = doc.get("ideas")
    if not ideas:
        sys.exit("error: --ideas file has no `ideas` array")

    root = args.project_root.resolve()

    # Load the project-state surface. An explicit --project-state path that
    # does not exist is a user error (don't silently assume MAX for a typo);
    # the default-location absence is the legitimate "undeclared" case ->
    # assume MAX and warn. A present-but-malformed file raises ValueError.
    if args.project_state and not args.project_state.is_file():
        sys.exit(f"error: --project-state {args.project_state} does not exist")
    try:
        if args.project_state:
            state = load_state_file(args.project_state)
            state_loc = args.project_state
        else:
            state_loc, _ = resolve_project_state_path(root)
            state = load_project_state(root)
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    assumed = state is None
    if assumed:
        state = assumed_max_state()

    results = [analyze_idea(root, idea, state) for idea in ideas]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "coverage.json").write_text(
        json.dumps({"source": str(args.ideas), "project_state": state,
                    "results": results}, indent=2))
    (args.output_dir / "coverage.md").write_text(
        render_report(str(args.ideas), results, state))

    if assumed:
        print(f"WARNING: no project state found at {state_loc} — assuming MAX "
              f"(production / public-adversarial) so nothing is silently "
              f"skipped. Run /orient to declare (maturity, stakes).")

    scanned = [r for r in results if r["status"] == "scanned"]
    partial = [r for r in results if r["status"] == "partial"]
    analyzed = [*scanned, *partial]
    gated = [r for r in results if r["status"] == "gated_out"]
    unsupported = [r for r in results if r["status"] == "language_unsupported"]
    no_files = [r for r in results if r["status"] == "no_files_matched"]
    total_gaps = sum(len(r["gaps"]) for r in analyzed)
    flags = []
    if gated:
        flags.append(f"{len(gated)} gated out")
    if partial:
        flags.append(f"{len(partial)} partial")
    if unsupported:
        flags.append(f"{len(unsupported)} language-unsupported")
    if no_files:
        flags.append(f"{len(no_files)} no-files-matched")
    print(f"state {state['maturity']}/{state['stakes']}: fully scanned "
          f"{len(scanned)}/{len(results)} standard(s), {len(partial)} partial: {total_gaps} "
          f"coverage gap(s)" + ("; " + ", ".join(flags) if flags else ""))
    for r in analyzed:
        skipped = f", {r['skipped_files']} skipped" if r["skipped_files"] else ""
        unsupported_files = r.get("unsupported_files", 0)
        unsupported_display = (
            f", {unsupported_files} unsupported "
            f"({', '.join(r['unsupported_extensions'])})"
            if unsupported_files else ""
        )
        status = "PARTIAL — " if r["status"] == "partial" else ""
        print(f"  {r['id']} [{r['detector_kind']}]: {status}{len(r['gaps'])} gap(s) "
              f"of {r['situation_sites']} situation site(s){skipped}{unsupported_display}")
    for r in gated:
        print(f"  {r['id']}: GATED OUT — {r['reason']}")
    for r in unsupported:
        print(f"  {r['id']}: LANGUAGE-UNSUPPORTED — {r['error']}")
    for r in no_files:
        print(f"  {r['id']}: NO FILES MATCHED — check the detector's `paths`")
    print(f"  -> {args.output_dir / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
