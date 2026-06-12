#!/usr/bin/env python3
"""Guard: the open-source core must not name a specific private host.

The core is deliberately Django/Python-*flavored* (so "django"/"celery"/"ruff" are
allowed — see the README's Tech assumptions). What it must never carry is a reference
to the specific *private downstream adaptation* it was extracted from, or that host's
proprietary identifiers. The host is referred to only by its public alias ("host-a");
the alias→identity mapping lives outside this repository (ADR 0035).

Two tiers, both stored base64-encoded so this file itself never carries the tokens
in greppable / search-indexable plaintext (the encoding is obfuscation, not secrecy —
it keeps the names out of code search and crawlers, which is the stated goal):

- IDENTITY tokens (the host's name, personal identifiers): scanned across EVERY
  git-tracked text file. These must not appear anywhere in the distribution.
- STRUCTURAL tokens (host-proprietary model/route names): scanned only on the
  published doc surfaces. Generic lookalikes in synthetic fixtures/tests are
  tolerated; published doctrine naming them is not.

Extend a tier with new tokens as they surface (base64-encode them). A deliberate,
justified occurrence is exempted by putting `host-ref-allow` on the same line
(`# host-ref-allow: <reason>`).
"""
from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()

# Identity tokens — the private host's name (and variants) and personal path
# identifiers. Base64-encoded; decoded at runtime. Matched with non-alphanumeric
# lookarounds so token_inside_identifiers is caught too.
IDENTITY_B64 = [
    "cG5jaQ==",
    "cG5jaS1wcmljaW5n",
    "cG5jaV9wcmljaW5n",
    "a2h1cnJ1bW1haG1vb2Q=",
]

# Inspiration-source tokens — external projects analyzed for evidence or drawn
# on for ideas are referred to by codename (Hermes, Atlas, Talos, Daedalus),
# never by real name, regardless of their license or public status. Same
# identity tier as the host: scanned across every tracked file.
INSPIRATION_B64 = [
    "ZXhwZW5zaWZ5",
    "b3BlbmNsYXc=",
    "Y2xhdWRlLWNvZGUtcnVzdA==",
]

# Structural tokens — host-proprietary model / export / view names. Doc surfaces only.
STRUCTURAL_B64 = [
    "UGllc1Byb2R1Y3REYXRh",
    "d3dzX2V4cG9ydA==",
    "U2l0ZVNjb3BlZFZpZXc=",
    "U2l0ZUNvbmZpZ3VyYXRpb24=",
    "U2l0ZUJyYW5kTWFwcGluZw==",
    "UmV0YWlsZXJCcmFuZE1hcHBpbmc=",
    "c2l0ZV9jb25maWc=",
    "c2l0ZV9zdGF0dXM=",
    "c2l0ZV93b3JrZmxvdw==",
]

DOC_SURFACE_GLOBS = [
    "ai-docs/decisions/*.md",
    "README.md",
    "VISION.md",
    "ONBOARDING.md",
]

ALLOW_RE = re.compile(r"host-ref-allow")


def _compile(b64_tokens: list[str]) -> re.Pattern:
    parts = []
    for b in b64_tokens:
        tok = base64.b64decode(b).decode()
        parts.append(rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])")
    return re.compile("|".join(parts), re.IGNORECASE)


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout
        return [REPO / line for line in out.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("warning: git ls-files unavailable; falling back to doc surfaces only", file=sys.stderr)
        return []


def _scan(paths: list[Path], pattern: re.Pattern, hits: list, seen: set) -> int:
    count = 0
    for path in paths:
        if not path.is_file() or path == SELF:
            continue
        key = (path, pattern.pattern)
        if key in seen:
            continue
        seen.add(key)
        count += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — identity tokens are text artifacts
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOW_RE.search(line):
                continue
            m = pattern.search(line)
            if m:
                hits.append((str(path.relative_to(REPO)), lineno, m.group(0), line.strip()[:100]))
    return count


def main() -> int:
    identity_re = _compile(IDENTITY_B64 + INSPIRATION_B64)
    structural_re = _compile(STRUCTURAL_B64)
    hits: list[tuple[str, int, str, str]] = []
    seen: set = set()

    n_tracked = _scan(_tracked_files(), identity_re, hits, seen)
    doc_paths = [p for glob in DOC_SURFACE_GLOBS for p in sorted(REPO.glob(glob))]
    _scan(doc_paths, identity_re, hits, seen)  # fallback coverage when git is absent
    n_docs = _scan(doc_paths, structural_re, hits, seen)

    if hits:
        print("Host-reference guard FAILED — the open-source core must not name a private host:")
        for rel, ln, tok, txt in hits:
            print(f"  {rel}:{ln}: {tok!r}  | {txt}")
        print(
            f"\n{len(hits)} hit(s). Genericize the reference (alias: host-a), or annotate a "
            "deliberate one with `# host-ref-allow: <reason>` on the same line."
        )
        return 1
    print(
        f"OK — no private-host references (identity tier: {n_tracked} tracked files; "
        f"structural tier: {n_docs} doc surfaces)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
