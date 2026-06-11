#!/usr/bin/env python3
"""Merge detector outputs into a single unified candidate list.

Reads `vulture.txt`, `url_patterns.jsonl`, `unreferenced_defs.jsonl`,
and `silent_catches.jsonl`, dedupes where the same (file, line, name)
tuple surfaces from multiple detectors, and emits a single
`candidates.jsonl` that the scout phase consumes.

Each output record:
{
  "candidate_id": "dormant-0001",
  "name": "FooHelper",
  "qualified_name": "FooHelper",
  "file": "core/services/foo.py",
  "line": 42,
  "kind": "function | method | class | module | except_handler",
  "sources": ["vulture", "unreferenced"],
  "hints": {
    "vulture_confidence": 80,
    "vulture_kind": "function",
    "url_wired_hint": false,
    "url_wire_files": [],
    "body_shape": "pass",            # silent_catches only
    "protected_lines": [67, 86],     # silent_catches only
    "enclosing_function": "FooSvc.lookup"  # silent_catches only
  }
}

URL patterns are NOT emitted as standalone candidates — they're a
lookup table the scout consults during 6a. Orphan endpoints surface
as `unreferenced_def` candidates with `url_wired_hint: true`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# vulture output: file:line: unused <kind> '<name>' (XX% confidence)
# The `file` group is non-greedy so Windows drive-letter paths like
# `C:\foo\bar.py:42: unused function 'x' (60% confidence)` match cleanly —
# a `[^:]+` file pattern would truncate after `C`.
_VULTURE_LINE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s+unused\s+(?P<kind>\w+)\s+"
    r"'(?P<name>[^']+)'\s+\((?P<conf>\d+)%\s+confidence\)"
)


def _parse_vulture(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(errors="replace").splitlines():
        m = _VULTURE_LINE.match(raw.strip())
        if not m:
            continue
        out.append({
            "file": m.group("file"),
            "line": int(m.group("line")),
            "name": m.group("name"),
            "kind": m.group("kind"),
            "confidence": int(m.group("conf")),
        })
    return out


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return out
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _merge(
    vulture: list[dict[str, Any]],
    unreferenced: list[dict[str, Any]],
    silent_catches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Key: (file, line, name). Both vulture and unreferenced produce def-level
    # records, so they dedupe naturally on this key.
    by_key: dict[tuple[str, int, str], dict[str, Any]] = {}

    for u in unreferenced:
        key = (u["file"], int(u["line"]), u["name"])
        entry = by_key.setdefault(key, {
            "name": u["name"],
            "qualified_name": u.get("qualified_name", u["name"]),
            "file": u["file"],
            "line": int(u["line"]),
            "kind": u.get("kind", "function"),
            "sources": [],
            "hints": {},
        })
        if "unreferenced" not in entry["sources"]:
            entry["sources"].append("unreferenced")
        entry["hints"]["url_wired_hint"] = bool(u.get("url_wired_hint"))
        entry["hints"]["url_wire_files"] = u.get("url_wire_files", [])

    for v in vulture:
        key = (v["file"], v["line"], v["name"])
        entry = by_key.setdefault(key, {
            "name": v["name"],
            "qualified_name": v["name"],
            "file": v["file"],
            "line": v["line"],
            "kind": v["kind"],
            "sources": [],
            "hints": {},
        })
        if "vulture" not in entry["sources"]:
            entry["sources"].append("vulture")
        entry["hints"]["vulture_confidence"] = v["confidence"]
        entry["hints"]["vulture_kind"] = v["kind"]

    # Silent catches are separate candidates — same (file, line) often
    # differs from def-level records because the except is mid-function.
    # We key them independently using their own (file, line) + "except"
    # marker so they never collide with vulture/unreferenced defs.
    for s in silent_catches:
        key = (s["file"], int(s["line"]), f"<except@{s['line']}>")
        entry = {
            "name": f"except_in_{s.get('enclosing_function', 'module').replace('.', '_')}",
            "qualified_name": s.get("enclosing_function", "<module>"),
            "file": s["file"],
            "line": int(s["line"]),
            "kind": "except_handler",
            "sources": ["silent_catches"],
            "hints": {
                "handler": s.get("handler", ""),
                "body_shape": s.get("body_shape", ""),
                "protected_lines": s.get("protected_lines", []),
                "enclosing_function": s.get("enclosing_function", "<module>"),
            },
        }
        by_key[key] = entry

    # Stable ordering: unreferenced/vulture defs first, then silent_catches,
    # each sorted by file + line.
    ordered = sorted(
        by_key.values(),
        key=lambda e: (
            0 if e["kind"] != "except_handler" else 1,
            e["file"],
            e["line"],
            e["name"],
        ),
    )
    for i, entry in enumerate(ordered, start=1):
        entry["candidate_id"] = f"dormant-{i:04d}"
    return ordered


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vulture", type=Path, default=None,
                   help="Path to vulture.txt (optional)")
    p.add_argument("--url-patterns", type=Path, default=None,
                   help="Path to url_patterns.jsonl (optional; passed "
                        "through as lookup table, not collapsed here)")
    p.add_argument("--unreferenced", type=Path, default=None,
                   help="Path to unreferenced_defs.jsonl (optional)")
    p.add_argument("--silent-catches", type=Path, default=None,
                   help="Path to silent_catches.jsonl (optional)")
    p.add_argument("--output", required=True, type=Path,
                   help="Output candidates.jsonl")
    args = p.parse_args(argv)

    vulture = _parse_vulture(args.vulture) if args.vulture else []
    unreferenced = _read_jsonl(args.unreferenced) if args.unreferenced else []
    silent = _read_jsonl(args.silent_catches) if args.silent_catches else []

    candidates = _merge(vulture, unreferenced, silent)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for c in candidates:
            fh.write(json.dumps(c) + "\n")

    counts = {
        "vulture": len(vulture),
        "unreferenced": len(unreferenced),
        "silent_catches": len(silent),
        "total_candidates": len(candidates),
    }
    print(
        f"[collapse] vulture={counts['vulture']} "
        f"unreferenced={counts['unreferenced']} "
        f"silent_catches={counts['silent_catches']} "
        f"→ candidates={counts['total_candidates']}",
        file=sys.stderr,
    )
    print(f"[collapse] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
