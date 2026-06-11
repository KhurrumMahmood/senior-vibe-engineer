#!/usr/bin/env python3
"""Guard: the open-source core must not name a specific private host.

The core is deliberately Django/Python-*flavored* (so "django"/"celery"/"ruff" are
allowed — see the README's Tech assumptions). What it must never carry is a reference
to the specific *private downstream adaptation* it was extracted from, or that host's
proprietary identifiers. This guard greps the open-source-facing surfaces for a
deny-list of such tokens and exits non-zero with file:line on any hit, so it can run
in pre-commit / CI instead of being hand-checked.

Extend DENY with new proprietary tokens as they surface. A deliberate, justified
occurrence (e.g. a fixture, or this file's own deny-list) is exempted by putting
`host-ref-allow` on the same line (`# host-ref-allow: <reason>`).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Open-source-facing surfaces that ship in the distribution.
SCAN_GLOBS = [
    "ai-docs/decisions/*.md",
    "README.md",
    "VISION.md",
    "ONBOARDING.md",
]

# Unambiguous private-host / proprietary identifiers. NOT framework names
# (django/celery/ruff) — the core is openly Django/Python-flavored.
DENY = [  # host-ref-allow: this list names the tokens; it is the guard, not a leak
    r"\bpnci\b",
    r"pnci[-_]pricing",
    r"PiesProductData",
    r"\bwws_export\b",
    r"SiteScopedView",
    r"SiteConfiguration",
    r"SiteBrandMapping",
    r"RetailerBrandMapping",
    r"\bsite_config\b",
    r"\bsite_status\b",
    r"\bsite_workflow\b",
]
DENY_RE = re.compile("|".join(DENY))
ALLOW_RE = re.compile(r"host-ref-allow")


def main() -> int:
    hits: list[tuple[str, int, str, str]] = []
    seen: set[Path] = set()
    for glob in SCAN_GLOBS:
        for path in sorted(REPO.glob(glob)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if ALLOW_RE.search(line):
                    continue
                m = DENY_RE.search(line)
                if m:
                    hits.append((str(path.relative_to(REPO)), lineno, m.group(0), line.strip()[:100]))

    if hits:
        print("Host-reference guard FAILED — the open-source core must not name a private host:")
        for rel, ln, tok, txt in hits:
            print(f"  {rel}:{ln}: {tok!r}  | {txt}")
        print(
            f"\n{len(hits)} hit(s). Genericize the reference, or annotate a deliberate one "
            "with `# host-ref-allow: <reason>` on the same line."
        )
        return 1
    print(f"OK — no private-host references across {len(seen)} open-source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
