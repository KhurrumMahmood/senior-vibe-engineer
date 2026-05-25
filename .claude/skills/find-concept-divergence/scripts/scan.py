#!/usr/bin/env python3
"""Strict concept-divergence scan.

Reads `.claude/contracts/concepts.yaml` and surfaces three drift bands:

1. `avoid_term_hit`           — code mentions a phrase listed in a
   concept's `avoid:` block verbatim (the glossary explicitly says
   "do not use this phrasing for this concept").
2. `competing_term_coexistence` — a file contains multiple
   `competing_terms` from a `flagged_ambiguities` entry (open drift
   that has bled into the same module).
3. `superseded_co_occurrence` — a file mentions both a deprecated
   concept name and its `superseded_by:` replacement (rename
   transition drift; pairs with dedicated rename lints).

Strict-first: no similarity / stem / Levenshtein matching in v1. Add
those only if the strict pass produces nothing real.

Portable body. Project-specific exclusions live in an optional
`.claude/skills/find-concept-divergence/host_excludes.txt` (one
path-prefix per line) that the host installation drops in.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO = Path(__file__).resolve().parents[4]

# Common project roots. iter_files auto-skips paths that don't exist,
# so listing all of them is safe across language/framework shapes. Host
# projects can override via positional CLI args.
DEFAULT_TARGETS = (
    # Python/Django app roots
    "app",
    "src",
    "lib",
    # Tooling + tests + docs (common across most layouts)
    "scripts",
    "tests",
    "docs",
    # Skill libraries (engineering-skills-2-style ecosystems)
    ".claude/skills",
    ".claude/docs",
    # Root prose
    "CONTEXT.md",
    "README.md",
    "ONBOARDING.md",
    "CLAUDE.md",
    ".claude/CLAUDE.md",
)

# Exclusion segments. A file is skipped if any path part matches
# (segments) or if any prefix matches (prefixes). ADRs are excluded
# because they intentionally name both sides of a rename (rename
# mechanics live there). `migrations` is Django-shaped but the segment
# match is conservative enough to be safe on non-Django projects.
EXCLUDE_SEGMENTS = frozenset({
    ".venv", "node_modules", ".git", "__pycache__", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "migrations",
})
# Portable defaults. Host projects extend via host_excludes.txt (see
# load_host_excludes) — that's where project-specific rename tooling,
# generated subtrees, etc. should be listed.
EXCLUDE_PREFIXES_DEFAULT = (
    "ai-docs/decisions/",
    ".claude/worktrees/",
    "reports/",
)
EXCLUDE_SUFFIXES = (".worktree",)


def load_host_excludes() -> tuple[str, ...]:
    """Optional per-host extension to EXCLUDE_PREFIXES_DEFAULT. Lives at
    `.claude/skills/find-concept-divergence/host_excludes.txt`, one
    path-prefix per line, blank lines / `#` comments ignored. Missing
    file is fine — portable defaults apply."""
    host_path = (
        Path(__file__).resolve().parent.parent / "host_excludes.txt"
    )
    if not host_path.exists():
        return ()
    out: list[str] = []
    try:
        text = host_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return tuple(out)


EXCLUDE_PREFIXES = EXCLUDE_PREFIXES_DEFAULT + load_host_excludes()

# Files we scan: source + prose. Binary / build artifacts are skipped.
INCLUDE_SUFFIXES = frozenset({
    ".py", ".pyi", ".md", ".html", ".js", ".ts", ".yaml", ".yml",
    ".txt", ".rst",
})

# Don't scan ourselves.
SELF_EXCLUDE = (
    ".claude/contracts/concepts.yaml",
    ".claude/skills/find-concept-divergence/",
)


def load_glossary(path: Path) -> dict[str, Any]:
    if not path.exists():
        sys.exit(f"glossary not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        sys.exit(f"glossary read/parse error: {exc}")
    if not isinstance(data, dict) or "concepts" not in data:
        sys.exit("glossary missing top-level `concepts:` block")
    return data


def is_excluded(rel: str) -> bool:
    parts = Path(rel).parts
    if any(seg in EXCLUDE_SEGMENTS for seg in parts):
        return True
    if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
        return True
    if any(rel.endswith(s) for s in EXCLUDE_SUFFIXES):
        return True
    if any(rel.startswith(s) or rel == s.rstrip("/") for s in SELF_EXCLUDE):
        return True
    return False


def iter_files(targets: Iterable[str]) -> Iterable[Path]:
    for raw in targets:
        p = (REPO / raw).resolve()
        if not p.exists():
            continue
        if p.is_file():
            rel = str(p.relative_to(REPO))
            if not is_excluded(rel) and p.suffix in INCLUDE_SUFFIXES:
                yield p
            continue
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in INCLUDE_SUFFIXES:
                continue
            rel = str(f.relative_to(REPO))
            if is_excluded(rel):
                continue
            yield f


def compile_term(term: str) -> re.Pattern[str]:
    """Word-boundary regex for a term. Identifier-like terms get strict
    word boundaries; phrases get loose boundaries (start/end of word
    character class). Case-insensitive in either mode."""
    t = term.strip()
    if not t:
        return re.compile(r"(?!x)x")  # never matches
    escaped = re.escape(t)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def scan_file_for_terms(path: Path, terms: list[tuple[str, re.Pattern[str]]]) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for term, pattern in terms:
            m = pattern.search(line)
            if m:
                hits.append({
                    "line": lineno,
                    "term": term,
                    "match": line.strip()[:200],
                })
    return hits


def _source_files(entry: dict[str, Any]) -> set[str]:
    """Files cited under an entry's `source:` field. Hits inside these
    files are excluded from the relevant band — the source file
    documents the concept or ambiguity, so listing the named phrases
    there is expected, not drift. Used by band 1 (against `concepts`)
    and band 2 (against `flagged_ambiguities`)."""
    raw = entry.get("source") or ""
    if not isinstance(raw, str):
        return set()
    out: set[str] = set()
    for chunk in raw.replace(";", ",").split(","):
        ref = chunk.strip().split("#", 1)[0].strip()
        if ref and not ref.startswith("ADR"):
            out.add(ref)
    return out


def scan(glossary: dict[str, Any], targets: Iterable[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    files = list(iter_files(targets))

    # Band 1: avoid-term hits.
    for concept in glossary.get("concepts", []):
        avoid = [a for a in (concept.get("avoid") or []) if isinstance(a, str)]
        if not avoid:
            continue
        # Pull the identifier-ish prefix out of each entry — `avoid:` lines
        # follow a "phrase (clarifier)" convention, and we only want the
        # phrase to grep on.
        terms: list[tuple[str, re.Pattern[str]]] = []
        for entry in avoid:
            phrase = entry.split("(")[0].strip().strip('"').strip("'").rstrip(",.;:")
            if phrase:
                terms.append((phrase, compile_term(phrase)))
        if not terms:
            continue
        source_files = _source_files(concept)
        for f in files:
            rel = str(f.relative_to(REPO))
            if rel in source_files:
                continue
            for hit in scan_file_for_terms(f, terms):
                findings.append({
                    "band": "avoid_term_hit",
                    "concept": concept["name"],
                    "file": rel,
                    **hit,
                })

    # Band 2: competing-term coexistence (per ambiguity, per file).
    for amb in glossary.get("flagged_ambiguities", []):
        competing = amb.get("competing_terms") or []
        if len(competing) < 2:
            continue
        term_patterns = [(t, compile_term(t)) for t in competing if isinstance(t, str)]
        if len(term_patterns) < 2:
            continue
        source_files = _source_files(amb)
        for f in files:
            rel = str(f.relative_to(REPO))
            if rel in source_files:
                continue
            file_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for hit in scan_file_for_terms(f, term_patterns):
                file_hits[hit["term"]].append(hit)
            if len(file_hits) < 2:
                continue
            for _term, hits in file_hits.items():
                for h in hits:
                    findings.append({
                        "band": "competing_term_coexistence",
                        "ambiguity_id": amb.get("id", "?"),
                        "competing_terms": list(file_hits.keys()),
                        "file": rel,
                        **h,
                    })

    # Band 3: superseded co-occurrence. A concept may set `coverage_lint:`
    # to declare the rename is already enforced by a dedicated lint;
    # the scanner skips co-occurrence noise for those concepts (the
    # lint owns the enforcement story).
    concepts_by_name = {c["name"]: c for c in glossary.get("concepts", []) if c.get("name")}
    for concept in glossary.get("concepts", []):
        replacement = concept.get("superseded_by")
        if not replacement or replacement not in concepts_by_name:
            continue
        if concept.get("coverage_lint"):
            continue
        old_terms = [concept["name"]] + [a for a in (concept.get("aliases") or []) if isinstance(a, str)]
        new_concept = concepts_by_name[replacement]
        new_terms = [new_concept["name"]] + [a for a in (new_concept.get("aliases") or []) if isinstance(a, str)]
        old_pat = [(t, compile_term(t)) for t in old_terms]
        new_pat = [(t, compile_term(t)) for t in new_terms]
        for f in files:
            old_hits = scan_file_for_terms(f, old_pat)
            if not old_hits:
                continue
            new_hits = scan_file_for_terms(f, new_pat)
            if not new_hits:
                continue
            for h in old_hits:
                findings.append({
                    "band": "superseded_co_occurrence",
                    "concept": concept["name"],
                    "superseded_by": replacement,
                    "file": str(f.relative_to(REPO)),
                    "side": "old",
                    **h,
                })

    return findings


def write_report(findings: list[dict[str, Any]], path: Path) -> None:
    by_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in findings:
        by_band[f["band"]].append(f)
    lines = ["# Concept-divergence scan", ""]
    if not findings:
        lines.append("No drift detected against the current glossary.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    lines.append(f"Total findings: **{len(findings)}** across **{len(by_band)}** band(s).")
    lines.append("")
    for band in ("avoid_term_hit", "competing_term_coexistence", "superseded_co_occurrence"):
        items = by_band.get(band, [])
        if not items:
            continue
        lines.append(f"## {band} ({len(items)})")
        lines.append("")
        by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for it in items:
            key = it.get("concept") or it.get("ambiguity_id") or "?"
            by_key[key].append(it)
        for key in sorted(by_key):
            lines.append(f"### {key}")
            lines.append("")
            for it in sorted(by_key[key], key=lambda x: (x["file"], x["line"])):
                lines.append(f"- `{it['file']}:{it['line']}` — `{it['term']}` — {it['match']}")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--glossary", default=str(REPO / ".claude/contracts/concepts.yaml"))
    ap.add_argument("--output", required=True, help="JSONL findings path")
    ap.add_argument("--report", required=True, help="Markdown report path")
    ap.add_argument("targets", nargs="*", default=list(DEFAULT_TARGETS),
                    help="paths to scan (relative to repo root)")
    args = ap.parse_args(argv)

    glossary = load_glossary(Path(args.glossary))
    targets = args.targets or list(DEFAULT_TARGETS)
    findings = scan(glossary, targets)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for f in findings:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(findings, report_path)

    print(f"wrote {len(findings)} findings → {out_path}")
    print(f"report → {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
