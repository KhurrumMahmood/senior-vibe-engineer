#!/usr/bin/env python
"""
Frontend class-chain scanner.

Scans HTML templates for Tailwind class chains and groups them into
buckets to surface UX-shell duplication (modal frames, badge styles,
button variants, alert frames, dropdown menus) BEFORE proposing a
cotton primitive extraction.

Two normalization passes:
  raw          — exact class chain (after sort+dedupe)
  tone-norm    — color names replaced with `{tone}`, shades preserved
                 (so `bg-red-100 text-red-800` and `bg-blue-100 text-blue-800`
                  collide, surfacing the c-alert / c-pill candidate)

Used by:
  - find-frontend-duplication (the primary detection script)
  - extract-cotton-primitive (to confirm the candidate's class chain
    appears N times across the codebase before recommending extraction)

Output:
  reports/frontend-class-chains/raw.json
  reports/frontend-class-chains/tone-norm.json
  Buckets are ranked by (occurrence_count, file_count) descending.

Stdlib only. Read-only.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

CLASS_ATTR_RE = re.compile(r'\bclass\s*=\s*"([^"]*)"')

TAILWIND_TONES = [
    "slate", "gray", "zinc", "neutral", "stone",
    "red", "orange", "amber", "yellow", "lime", "green", "emerald",
    "teal", "cyan", "sky", "blue", "indigo", "violet", "purple",
    "fuchsia", "pink", "rose",
]

VARIANT_PREFIXES = (
    r"(?:hover:|focus:|focus-within:|focus-visible:|active:|disabled:|"
    r"group-hover:|group-focus:|peer-hover:|peer-focus:|"
    r"sm:|md:|lg:|xl:|2xl:|dark:|first:|last:|odd:|even:)*"
)

TONE_BASES = (
    r"(?:bg|text|border|ring|placeholder|divide|from|to|via|outline|"
    r"caret|fill|stroke|shadow|decoration|accent)"
)

TONE_TOKEN_RE = re.compile(
    rf"""
    ^
    (?P<prefix>{VARIANT_PREFIXES})
    (?P<base>{TONE_BASES})
    -
    (?P<tone>{"|".join(sorted(TAILWIND_TONES, key=len, reverse=True))})
    (?P<shade>(?:-(?:50|100|200|300|400|500|600|700|800|900|950))?)
    (?P<opacity>(?:/\d+)?)
    $
    """,
    re.VERBOSE,
)


def normalize_token(token):
    m = TONE_TOKEN_RE.match(token)
    if not m:
        return token
    return f"{m.group('prefix')}{m.group('base')}-{{tone}}{m.group('shade')}{m.group('opacity')}"


def split_class_chain(chain_text):
    cleaned = re.sub(r"\{%[^%]*%\}", " ", chain_text)
    cleaned = re.sub(r"\{\{[^}]*\}\}", " ", cleaned)
    return tuple(sorted({t for t in cleaned.split() if t}))


def bucket_key(tokens, normalize):
    if normalize:
        tokens = tuple(sorted({normalize_token(t) for t in tokens}))
    return "|".join(tokens)


def scan_html(project_root, search_paths):
    for base in search_paths:
        if not base.exists():
            continue
        for path in base.rglob("*.html"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_idx, line in enumerate(text.splitlines(), 1):
                for m in CLASS_ATTR_RE.finditer(line):
                    yield (str(path.relative_to(project_root)), line_idx, m.group(1))


def build_buckets(occurrences, normalize, min_tokens, min_count):
    buckets = defaultdict(list)
    for path, line, chain_text in occurrences:
        tokens = split_class_chain(chain_text)
        if len(tokens) < min_tokens:
            continue
        key = bucket_key(tokens, normalize=normalize)
        buckets[key].append({
            "file": path,
            "line": line,
            "tokens": list(tokens),
            "raw": chain_text,
        })
    return {k: v for k, v in buckets.items() if len(v) >= min_count}


def rank_buckets(buckets, normalize):
    ranked = []
    for key, occs in buckets.items():
        files = sorted({o["file"] for o in occs})
        representative = (
            sorted({normalize_token(t) for t in occs[0]["tokens"]})
            if normalize
            else occs[0]["tokens"]
        )
        ranked.append({
            "key": hashlib.md5(key.encode()).hexdigest()[:10],
            "tokens": list(representative),
            "occurrence_count": len(occs),
            "file_count": len(files),
            "files": files,
            "occurrences": occs,
        })
    ranked.sort(key=lambda b: (-b["occurrence_count"], -b["file_count"]))
    return ranked


def write_report(out_path, occurrences_total, min_tokens, min_count, ranked):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "occurrences_total": occurrences_total,
        "min_tokens": min_tokens,
        "min_count": min_count,
        "bucket_count": len(ranked),
        "buckets": ranked,
    }, indent=2) + "\n", encoding="utf-8")


def print_top(label, ranked, limit=10):
    print(f"Top {limit} {label} buckets:")
    for b in ranked[:limit]:
        preview = " ".join(b["tokens"][:6])
        if len(b["tokens"]) > 6:
            preview += " …"
        print(f"  {b['occurrence_count']:>3}× across {b['file_count']:>2} files: {preview}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path,
                        default=Path("reports/frontend-class-chains"))
    parser.add_argument("--min-tokens", type=int, default=3,
                        help="Ignore chains with fewer tokens (default 3)")
    parser.add_argument("--min-count", type=int, default=2,
                        help="Ignore buckets with fewer occurrences (default 2)")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    project_root = args.root.resolve()
    search_paths = [project_root / "templates"]
    occurrences = list(scan_html(project_root, search_paths))

    raw = rank_buckets(
        build_buckets(occurrences, normalize=False,
                      min_tokens=args.min_tokens, min_count=args.min_count),
        normalize=False,
    )
    norm = rank_buckets(
        build_buckets(occurrences, normalize=True,
                      min_tokens=args.min_tokens, min_count=args.min_count),
        normalize=True,
    )

    out_dir = args.out_dir if args.out_dir.is_absolute() else project_root / args.out_dir
    write_report(out_dir / "raw.json", len(occurrences),
                 args.min_tokens, args.min_count, raw)
    write_report(out_dir / "tone-norm.json", len(occurrences),
                 args.min_tokens, args.min_count, norm)

    if args.print:
        print_top("raw class-chain", raw)
        print_top("tone-normalized", norm)

    print(f"Scanned {len(occurrences)} class chains")
    print(f"Wrote {out_dir / 'raw.json'} ({len(raw)} buckets)")
    print(f"Wrote {out_dir / 'tone-norm.json'} ({len(norm)} buckets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
