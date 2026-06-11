#!/usr/bin/env python
"""
Frontend helper / factory scanner.

Surfaces JavaScript helper duplication and forks across static/js/:

  duplicates_same_name  — same function name defined in >1 file
                          (e.g. `showToast` in core.js + brand-mapping.js)
  isolated_helpers      — small named functions defined in one file but
                          structurally similar to helpers elsewhere
                          (heuristic: name + arg-count signature collision)
  csrf_inline_patterns  — inline `'X-CSRFToken': ... getCookie(...)` or
                          unqualified `getCookie('csrftoken')` calls,
                          which suggest a missing csrf-fetch wrapper.

This is deliberately heuristic: regex-based, no JS parse. It produces
candidates for an investigation agent (extract-cotton-primitive or a
JS-sibling skill), not a definitive list. The agent must read the
actual definitions before recommending a consolidation.

Usage:
  .venv/bin/python scripts/frontend_helper_scanner.py
  .venv/bin/python scripts/frontend_helper_scanner.py --print

Output: reports/frontend-helpers/inventory.json

Stdlib only. Read-only.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

FUNC_DEF_PATTERNS = [
    re.compile(r"^\s*function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)"),
    re.compile(r"^\s*(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*function\s*\((?P<args>[^)]*)\)"),
    re.compile(r"^\s*(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*\((?P<args>[^)]*)\)\s*=>"),
    re.compile(r"^\s*(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?P<arg>[A-Za-z_$][\w$]*)\s*=>"),
    re.compile(r"^\s*(?P<name>[A-Za-z_$][\w$]*)\s*:\s*function\s*\((?P<args>[^)]*)\)"),
]

CSRF_INLINE_RE = re.compile(r"['\"]X-CSRFToken['\"]\s*:\s*([^,\n}]+)")
BARE_GET_COOKIE_RE = re.compile(r"(?<![.\w])getCookie\s*\(\s*['\"]csrftoken['\"]\s*\)")


def find_function_defs(text):
    """Yield (name, line_idx, args_text, signature_line) for each top-level def."""
    for line_idx, line in enumerate(text.splitlines(), 1):
        for pattern in FUNC_DEF_PATTERNS:
            m = pattern.match(line)
            if not m:
                continue
            name = m.group("name")
            args = m.groupdict().get("args")
            if args is None:
                args = m.groupdict().get("arg", "")
            arg_count = len([a for a in args.split(",") if a.strip()]) if args else 0
            yield name, line_idx, args.strip() if args else "", arg_count, line.strip()
            break


def scan_helpers(project_root):
    js_dir = project_root / "static" / "js"
    by_name = defaultdict(list)
    by_signature = defaultdict(list)
    csrf_inline_hits = []
    bare_get_cookie_hits = []

    if not js_dir.exists():
        return {"by_name": {}, "by_signature": {}, "csrf_inline": [], "bare_get_cookie": []}

    for path in sorted(js_dir.rglob("*.js")):
        rel = str(path.relative_to(project_root))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, line_idx, args, arg_count, sig in find_function_defs(text):
            entry = {"file": rel, "line": line_idx, "args": args,
                     "arg_count": arg_count, "signature": sig}
            by_name[name].append(entry)
            by_signature[(name, arg_count)].append(entry)

        for line_idx, line in enumerate(text.splitlines(), 1):
            m = CSRF_INLINE_RE.search(line)
            if m:
                csrf_inline_hits.append({"file": rel, "line": line_idx,
                                         "expression": m.group(1).strip()})
            if BARE_GET_COOKIE_RE.search(line):
                bare_get_cookie_hits.append({"file": rel, "line": line_idx,
                                             "snippet": line.strip()[:120]})

    return {
        "by_name": dict(by_name),
        "by_signature": dict(by_signature),
        "csrf_inline": csrf_inline_hits,
        "bare_get_cookie": bare_get_cookie_hits,
    }


def categorize(scan):
    duplicates_same_name = []
    for name, defs in scan["by_name"].items():
        if len(defs) <= 1:
            continue
        files = sorted({d["file"] for d in defs})
        if len(files) <= 1:
            continue  # multiple defs in same file (e.g. nested helpers); skip
        duplicates_same_name.append({
            "name": name,
            "definition_count": len(defs),
            "file_count": len(files),
            "files": files,
            "definitions": defs,
        })
    duplicates_same_name.sort(key=lambda d: -d["definition_count"])

    return {
        "duplicates_same_name": duplicates_same_name,
        "csrf_inline_count": len(scan["csrf_inline"]),
        "csrf_inline_files": sorted({h["file"] for h in scan["csrf_inline"]}),
        "csrf_inline_occurrences": scan["csrf_inline"],
        "bare_get_cookie_count": len(scan["bare_get_cookie"]),
        "bare_get_cookie_files": sorted({h["file"] for h in scan["bare_get_cookie"]}),
        "bare_get_cookie_occurrences": scan["bare_get_cookie"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path,
                        default=Path("reports/frontend-helpers/inventory.json"))
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    project_root = args.root.resolve()
    scan = scan_helpers(project_root)
    report = categorize(scan)

    out = args.out if args.out.is_absolute() else project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.print:
        print("=== Same-name forks (function defined in multiple files) ===")
        for d in report["duplicates_same_name"][:15]:
            print(f"  {d['name']}() — {d['definition_count']} definitions across {d['file_count']} files:")
            for defn in d["definitions"]:
                print(f"      {defn['file']}:{defn['line']}  ({defn['arg_count']} args)")
        print()
        print("=== Inline CSRF patterns (suggests csrf-fetch wrapper missing) ===")
        print(f"  {report['csrf_inline_count']} 'X-CSRFToken': occurrences across "
              f"{len(report['csrf_inline_files'])} files")
        print(f"  {report['bare_get_cookie_count']} bare getCookie('csrftoken') calls across "
              f"{len(report['bare_get_cookie_files'])} files")
        for f in report["bare_get_cookie_files"][:10]:
            print(f"    {f}")

    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
