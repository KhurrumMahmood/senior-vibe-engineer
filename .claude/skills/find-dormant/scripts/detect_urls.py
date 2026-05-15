#!/usr/bin/env python3
"""Extract URL patterns from a Django project's urls.py tree.

Walks `core/urls.py` (or a custom root) and follows every `include()` call
to discover sub-modules (`core.api_urls`, etc.). Captures `path()` and
`re_path()` patterns plus their view reference and optional `name=`.

Output: JSONL, one record per URL pattern, at `--output`.

Each record:
{
  "type": "url_pattern",
  "source_file": "core/urls.py",
  "url_path": "/api/foo/",
  "view_ref": "core.views.foo.FooView",
  "url_name": "foo"
}

The `view_ref` is the dotted string exactly as written in urls.py — the
consumer (collapse.py + verify scout) is responsible for resolving it to
a concrete (file, line, qualified_name) tuple.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Match path() / re_path() lines. Non-greedy view capture with lookahead so
# "View.as_view()" doesn't get swallowed by the greedy \w+ pattern and break
# the trailing name= capture.
_URL_PATTERN = re.compile(
    r"(?:re_)?path\s*\(\s*"
    r"[rR]?['\"]([^'\"]*)['\"]"         # URL path
    r"\s*,\s*"
    r"([\w.]+?)"                         # dotted view reference (non-greedy)
    r"(?=\.as_view\(\)|\s*,|\s*\))"
    r"(?:\.as_view\(\))?"
    r"\s*(?:,\s*name\s*=\s*['\"]([^'\"]+)['\"])?"
)

_INCLUDE_PATTERN = re.compile(
    r"include\s*\(\s*['\"]([^'\"]+)['\"]"
)


def _extract(filepath: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    try:
        content = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return [], []
    patterns = [
        (m.group(1), m.group(2), m.group(3) or "")
        for m in _URL_PATTERN.finditer(content)
    ]
    includes = [m.group(1) for m in _INCLUDE_PATTERN.finditer(content)]
    return patterns, includes


def walk(root_file: Path, project_root: Path) -> list[dict[str, str]]:
    seen: set[Path] = set()
    queue: list[Path] = [root_file]
    out: list[dict[str, str]] = []
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        patterns, includes = _extract(current)
        rel = str(current.relative_to(project_root)) if current.is_absolute() else str(current)
        for url_path, view_ref, url_name in patterns:
            out.append({
                "type": "url_pattern",
                "source_file": rel,
                "url_path": url_path,
                "view_ref": view_ref,
                "url_name": url_name,
            })
        for inc in includes:
            inc_path = project_root / (inc.replace(".", "/") + ".py")
            if inc_path.exists():
                queue.append(inc_path)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root-urls", required=True, type=Path,
                   help="Root urls.py (typically core/urls.py)")
    p.add_argument("--project-root", required=True, type=Path,
                   help="Project root for resolving include() dotted paths")
    p.add_argument("--output", required=True, type=Path,
                   help="Output JSONL file")
    args = p.parse_args()

    if not args.root_urls.exists():
        print(f"[detect_urls] ERROR: {args.root_urls} not found", file=sys.stderr)
        return 2
    records = walk(args.root_urls, args.project_root)
    with args.output.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    named = sum(1 for r in records if r["url_name"])
    print(f"[detect_urls] wrote {args.output} ({len(records)} patterns, {named} named)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
