#!/usr/bin/env python3
"""Matcher for the Tier 2 pattern library at .claude/patterns/.

Usage:
    .venv/bin/python .claude/skills/query-patterns/scripts/query.py \
        "<problem description>" [--top N] [--json] [--include-deprecated]

Exit codes:
    0 at least one match scored above the relevance threshold
    1 no match (zero patterns OR all scores at zero)
    2 usage error

Scoring: token-overlap on the query against problem_class, pros, cons,
domain, tags, title, and the body's "Problem fit" section. Frontmatter
fields are weighted higher than body matches; problem_class is the
single highest-weighted field. The matcher is intentionally primitive —
the design assumption is that frontmatter is the headline. See
.claude/docs/pattern-library.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# KIT_ROOT anchors kit-relative imports ONLY (scripts/_lib, _common). The
# pattern library is a target-project surface and anchors on --project-root
# instead — the kit may live in a different repo (de-baking convention, ADR 0024).
KIT_ROOT = Path(__file__).resolve().parents[4]
for _p in (str(KIT_ROOT / "scripts"), str(KIT_ROOT / ".claude" / "skills" / "_common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _lib.yaml_frontmatter import FrontmatterError, read  # noqa: E402
from diff_resolution import resolve_project_root  # noqa: E402

WEIGHTS: dict[str, float] = {
    "problem_class": 6.0,
    "title": 4.0,
    "pros": 2.0,
    "cons": 1.5,
    "domain": 1.5,
    "tags": 1.5,
    "headline": 4.0,
    "body": 1.0,
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "for", "on", "to", "in",
    "with", "is", "are", "be", "by", "at", "as", "this", "that", "from",
    "use", "using", "want", "need", "needs", "should", "could", "would",
    "do", "does", "doing", "done", "into", "out", "vs", "via", "per",
    "i", "we", "you", "it", "its", "their", "my", "your", "our",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")


@dataclass
class PatternRecord:
    slug: str
    path: Path
    metadata: dict[str, Any]
    body: str
    headline: str = ""
    fields_text: dict[str, str] = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for tok in TOKEN_RE.findall(text.lower()):
        if tok in STOPWORDS or len(tok) <= 1:
            continue
        out.append(tok)
    return out


def extract_headline(body: str) -> str:
    """Pull the 'Use this when X' line from the Problem fit section."""
    in_problem_fit = False
    candidate = ""
    for line in body.splitlines():
        s = line.strip()
        if s.lower().startswith("## problem fit"):
            in_problem_fit = True
            continue
        if in_problem_fit and s.startswith("#"):
            break
        if in_problem_fit and "use this when" in s.lower():
            candidate = s
            break
    return candidate


def listify(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def load_patterns(
    patterns_dir: Path, include_deprecated: bool = False
) -> tuple[list[PatternRecord], list[str]]:
    patterns: list[PatternRecord] = []
    errors: list[str] = []
    if not patterns_dir.exists():
        return patterns, errors
    for path in sorted(patterns_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            doc = read(path)
        except FrontmatterError as exc:
            errors.append(f"{path}: {exc}")
            continue
        meta = doc.metadata or {}
        slug = str(meta.get("id") or path.stem)
        status = str(meta.get("status") or "validated")
        if status == "deprecated" and not include_deprecated:
            continue
        rec = PatternRecord(slug=slug, path=path, metadata=meta, body=doc.body)
        rec.headline = extract_headline(doc.body)
        rec.fields_text = {
            "problem_class": str(meta.get("problem_class") or ""),
            "title": str(meta.get("title") or ""),
            "pros": " ".join(listify(meta.get("pros"))),
            "cons": " ".join(listify(meta.get("cons"))),
            "domain": str(meta.get("domain") or ""),
            "tags": " ".join(listify(meta.get("tags"))),
            "headline": rec.headline,
            "body": doc.body,
        }
        patterns.append(rec)
    return patterns, errors


def score(query_tokens: list[str], rec: PatternRecord) -> tuple[float, dict[str, int]]:
    overlap: dict[str, int] = {}
    total = 0.0
    qset = set(query_tokens)
    for field_name, weight in WEIGHTS.items():
        field_tokens = set(tokenize(rec.fields_text.get(field_name, "")))
        if not field_tokens:
            overlap[field_name] = 0
            continue
        hit_count = len(qset & field_tokens)
        overlap[field_name] = hit_count
        total += hit_count * weight
    return total, overlap


def rank(query: str, patterns: list[PatternRecord], project_root: Path) -> list[dict]:
    qt = tokenize(query)
    if not qt:
        return []
    scored: list[dict] = []
    for rec in patterns:
        s, hits = score(qt, rec)
        if s <= 0:
            continue
        meta = rec.metadata
        scored.append({
            "slug": rec.slug,
            "title": str(meta.get("title") or rec.slug),
            "status": str(meta.get("status") or "validated"),
            "generalizability": str(meta.get("generalizability") or "single-constraint-set"),
            "problem_class": str(meta.get("problem_class") or ""),
            "headline": rec.headline,
            "composes_with": listify(meta.get("composes_with")),
            "lineage_parents": listify(meta.get("lineage_parents")),
            "lineage_children": listify(meta.get("lineage_children")),
            "domain": str(meta.get("domain") or ""),
            "path": (str(rec.path.relative_to(project_root))
                     if rec.path.is_relative_to(project_root) else str(rec.path)),
            "score": round(s, 2),
            "hits": hits,
        })
    scored.sort(key=lambda d: (-d["score"], d["slug"]))
    return scored


def render_markdown(query: str, results: list[dict], total_patterns: int, parse_errors: list[str]) -> str:
    lines: list[str] = [f"Query: {query}", f"Library size: {total_patterns} patterns"]
    if parse_errors:
        lines.append("")
        lines.append("Parse errors (these files were skipped):")
        for err in parse_errors:
            lines.append(f"- {err}")
    lines.append("")
    if not results:
        if total_patterns == 0:
            lines.append("No patterns recorded yet. Capture the problem with `/track-idea intake`")
            lines.append("and promote manually into `.claude/patterns/` once it satisfies")
            lines.append("the Tier 2 gate in `.claude/docs/pattern-library.md`.")
        else:
            lines.append("Top match score: 0 (below threshold)")
            lines.append("")
            lines.append("No patterns match closely. Either:")
            lines.append("- The problem is genuinely new — capture with `/track-idea intake`.")
            lines.append("- Re-query with different wording (the matcher is token-overlap).")
        return "\n".join(lines)

    lines.append("## Top matches")
    for i, r in enumerate(results, 1):
        lines.append("")
        status_part = f"{r['status']} / {r['generalizability']}"
        lines.append(f"### {i}. `{r['slug']}` — {r['title']} [{status_part}]")
        if r["headline"]:
            lines.append(f"**Use this when**: {r['headline']}")
        if r["problem_class"]:
            lines.append(f"**Problem class**: {r['problem_class']}")
        cw = ", ".join(r["composes_with"]) if r["composes_with"] else "(none)"
        lines.append(f"**Composes with**: {cw}")
        lp = ", ".join(r["lineage_parents"]) if r["lineage_parents"] else "(none)"
        lc = ", ".join(r["lineage_children"]) if r["lineage_children"] else "(none)"
        if r["lineage_parents"] or r["lineage_children"]:
            lines.append(f"**Lineage**: parents={lp} ; children={lc}")
        lines.append(f"Score: {r['score']}  |  Path: `{r['path']}`")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pattern library matcher")
    p.add_argument("query", nargs="?")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-deprecated", action="store_true")
    p.add_argument("--project-root", type=Path, default=None,
                   help="Target project root owning .claude/patterns/ "
                        "(default: git toplevel of cwd, else cwd)")
    args = p.parse_args(argv)

    if not args.query or not args.query.strip():
        print(
            "usage: query.py \"<problem description>\" [--top N] [--json]",
            file=sys.stderr,
        )
        return 2

    project_root = resolve_project_root(args.project_root)
    patterns_dir = project_root / ".claude" / "patterns"
    patterns, parse_errors = load_patterns(
        patterns_dir, include_deprecated=args.include_deprecated
    )
    results = rank(args.query, patterns, project_root)[: args.top]

    if args.json:
        print(json.dumps({
            "query": args.query,
            "total_patterns": len(patterns),
            "parse_errors": parse_errors,
            "matches": results,
        }, indent=2, sort_keys=True))
    else:
        print(render_markdown(args.query, results, len(patterns), parse_errors))

    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
