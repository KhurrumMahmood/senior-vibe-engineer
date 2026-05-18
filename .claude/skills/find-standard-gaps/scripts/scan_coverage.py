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
    `requires_kwarg`. Real Python syntax — no comment/string false
    positives. **Python-only** (it is CPython's `ast` module).
  - `skill` — recognised, not implemented in v1.
  - `manual` — skipped; checked by hand.

Per-standard status in the output:
  - `scanned`             — ran; see gaps. `skipped_files` flags any
                            file that could not be read/parsed.
  - `no_files_matched`    — the detector's `paths` matched nothing. A
                            misconfigured glob / project-root — NOT a
                            pass.
  - `language_unsupported`— an `ast` standard whose `paths` matched
                            files but none are `.py`.
  - `skipped` / `error`   — manual/skill detector, or a malformed one.
A "0 gaps" result is only trustworthy under `status: scanned`.

Stdlib-only. Read-only against the codebase.

Usage:
    python3 scan_coverage.py --ideas path/to/standards.json \\
        --project-root "$(pwd)" \\
        --output-dir reports/standard-gaps/scan-<TS>
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {".venv", "__pycache__", "migrations", ".git", "node_modules",
             "tests", "experiments"}

# Python 3.11+ `try/except*` is a distinct node; treat it like `try`.
_TRY_TYPES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())


def iter_files(root: Path, globs: list[str]) -> list[Path]:
    """All files matching the globs (any extension), minus SKIP_DIRS.

    The globs are the file selector — `app/**/*.py` already restricts to
    Python; this function does not second-guess the extension. Note
    SKIP_DIRS is fixed (tests / experiments / vendored dirs are never
    scanned) — a standard cannot currently opt back in.
    """
    seen: set[Path] = set()
    out: list[Path] = []
    for glob in globs:
        for path in sorted(root.glob(glob)):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if path in seen:
                continue
            seen.add(path)
            out.append(path)
    return out


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

    files = iter_files(root, paths)
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


def run_ast_detector(root: Path, detector: dict):
    """Return ({...}, error_or_None). Python-only — uses CPython's `ast`.

    Possible result shapes: `{no_files}`, `{unsupported}`, or
    `{sites, gaps, scanned_files, skipped_files}`. A file that fails to
    read/parse — or whose traversal hits the recursion limit — is counted
    as `skipped`, never silently folded into `scanned_files`.

    Finds Call nodes whose dotted name matches `call_matches`, then checks
    one satisfaction condition — exactly one of `enclosed_by` (`try`|
    `with`, lexical block scope) or `requires_kwarg` (a `**kwargs` spread
    counts as satisfied). A gap = a matched call that fails the condition.
    Enclosure resets at a nested-function *body*; decorators and default
    arguments inherit the enclosing scope.
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
    matched = iter_files(root, paths)
    if not matched:
        return {"no_files": True}, None
    py_files = [f for f in matched if f.suffix == ".py"]
    if not py_files:
        exts = sorted({f.suffix or "<none>" for f in matched})
        return {"unsupported": True, "matched": len(matched),
                "extensions": exts[:8]}, None

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
    return {"sites": sites, "gaps": gaps,
            "scanned_files": analyzed, "skipped_files": skipped}, None


# --------------------------------------------------------------------------
def analyze_idea(root: Path, idea: dict) -> dict:
    detector = (idea.get("contract") or {}).get("detector") or {}
    kind = detector.get("kind", "none")
    base = {"id": idea.get("id", "?"), "label": idea.get("label", ""),
            "detector_kind": kind}
    runner = {"grep": run_grep_detector, "ast": run_ast_detector}.get(kind)
    if runner:
        result, err = runner(root, detector)
        if err:
            return {**base, "status": "error", "error": err}
        if result.get("no_files"):
            globs = detector.get("paths") or ["app/**/*.py"]
            return {**base, "status": "no_files_matched",
                    "error": f"the detector's `paths` ({', '.join(globs)}) "
                             f"matched no files — check the globs and "
                             f"--project-root. This is NOT a passing result."}
        if result.get("unsupported"):
            return {**base, "status": "language_unsupported",
                    "matched": result["matched"], "extensions": result["extensions"],
                    "error": f"the `ast` detector is Python-only; "
                             f"{result['matched']} file(s) matched `paths` but none "
                             f"are .py (found: {', '.join(result['extensions'])}). "
                             f"Apply the rule in SKILL.md — When the target "
                             f"language isn't supported."}
        sites, gaps = result["sites"], result["gaps"]
        return {**base, "status": "scanned",
                "scanned_files": result["scanned_files"],
                "skipped_files": result["skipped_files"],
                "situation_sites": len(sites), "gaps": gaps,
                "coverage": round((len(sites) - len(gaps)) / len(sites), 4)
                if sites else None}
    if kind == "skill":
        return {**base, "status": "skipped",
                "error": "detector kind 'skill' is not implemented in v1"}
    return {**base, "status": "skipped",
            "error": "no executable detector (kind manual / none)"}


def render_report(source: str, results: list[dict]) -> str:
    L = [f"# Application-coverage scan — {source}", "",
         f"_Scanned {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
         f"by scan_coverage.py._", ""]
    scanned = [r for r in results if r["status"] == "scanned"]
    with_gaps = [r for r in scanned if r["gaps"]]
    unsupported = [r for r in results if r["status"] == "language_unsupported"]
    no_files = [r for r in results if r["status"] == "no_files_matched"]
    L += ["## Summary", "",
          f"- {len(results)} standard(s) in input; {len(scanned)} scanned",
          f"- **{sum(len(r['gaps']) for r in scanned)} coverage gap(s)** "
          f"across {len(with_gaps)} standard(s)"]
    if unsupported:
        L.append(f"- ⚠ {len(unsupported)} standard(s) **language-unsupported** — "
                 f"the `ast` detector is Python-only; see SKILL.md "
                 f"\"When the target language isn't supported\"")
    if no_files:
        L.append(f"- ⚠ {len(no_files)} standard(s) matched **no files** — a "
                 f"misconfigured glob; NOT a passing result")
    L.append("")
    for r in results:
        L.append(f"### `{r['id']}` — {r['label']}")
        if r["status"] == "scanned":
            sites = r["situation_sites"]
            cov = "n/a" if not sites else f"{int(100 * (sites - len(r['gaps'])) / sites)}%"
            skipped = f", {r['skipped_files']} skipped" if r["skipped_files"] else ""
            L.append(f"- detector: `{r['detector_kind']}` · "
                     f"{sites} situation site(s), **{len(r['gaps'])} gap(s)**, "
                     f"coverage {cov} ({r['scanned_files']} files analyzed{skipped})")
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
    args = ap.parse_args()

    try:
        doc = json.loads(args.ideas.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        sys.exit(f"error: cannot read --ideas: {exc}")
    ideas = doc.get("ideas")
    if not ideas:
        sys.exit("error: --ideas file has no `ideas` array")

    root = args.project_root.resolve()
    results = [analyze_idea(root, idea) for idea in ideas]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "coverage.json").write_text(
        json.dumps({"source": str(args.ideas), "results": results}, indent=2))
    (args.output_dir / "coverage.md").write_text(
        render_report(str(args.ideas), results))

    scanned = [r for r in results if r["status"] == "scanned"]
    unsupported = [r for r in results if r["status"] == "language_unsupported"]
    no_files = [r for r in results if r["status"] == "no_files_matched"]
    total_gaps = sum(len(r["gaps"]) for r in scanned)
    flags = []
    if unsupported:
        flags.append(f"{len(unsupported)} language-unsupported")
    if no_files:
        flags.append(f"{len(no_files)} no-files-matched")
    print(f"scanned {len(scanned)}/{len(results)} standard(s): {total_gaps} "
          f"coverage gap(s)" + ("; " + ", ".join(flags) if flags else ""))
    for r in scanned:
        skipped = f", {r['skipped_files']} skipped" if r["skipped_files"] else ""
        print(f"  {r['id']} [{r['detector_kind']}]: {len(r['gaps'])} gap(s) "
              f"of {r['situation_sites']} situation site(s){skipped}")
    for r in unsupported:
        print(f"  {r['id']}: LANGUAGE-UNSUPPORTED — {r['matched']} non-Python "
              f"file(s) matched ({', '.join(r['extensions'])})")
    for r in no_files:
        print(f"  {r['id']}: NO FILES MATCHED — check the detector's `paths`")
    print(f"  -> {args.output_dir / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
