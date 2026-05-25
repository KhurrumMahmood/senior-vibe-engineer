#!/usr/bin/env python
"""
Cotton primitive inventory.

Walks app/_components/cotton/*.html and emits a JSON catalogue of every
django-cotton primitive: declared props (from <c-vars>), default-slot
presence, named-slot candidates (bare {{ name }} refs that aren't props),
and callsite counts (across templates/, static/js/, core/).

Used by:
  - find-frontend-duplication (to know which primitives already exist
    before the agent suggests "extract a new component")
  - extract-cotton-primitive (to know the conventions a new primitive
    must match: tone-prop pattern, {{ attrs }} pass-through, etc.)
  - manual review (`--print` for a quick human summary)

Usage:
  .venv/bin/python scripts/cotton_inventory.py
  .venv/bin/python scripts/cotton_inventory.py --print
  .venv/bin/python scripts/cotton_inventory.py --out /tmp/cotton.json

Stdlib only. Read-only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

CVARS_RE = re.compile(r"<c-vars\b([^>]*?)/?\s*>", re.DOTALL)

ATTR_RE = re.compile(
    r"""
    (?P<typed>:?)               # optional `:` for Python-evaluated values
    (?P<name>[A-Za-z_][\w-]*)   # attribute name
    (?:                         # optional value
      \s*=\s*
      (?:
        "(?P<dq>[^"]*)"         # double-quoted
        | '(?P<sq>[^']*)'       # single-quoted
      )
    )?
    """,
    re.VERBOSE,
)

BARE_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}")

DJANGO_CONTEXT_NAMES = {
    "user", "request", "perms", "csrf_token", "settings", "messages",
    "now", "today", "True", "False", "None", "forloop", "block", "super",
    "DEBUG", "STATIC_URL", "MEDIA_URL", "LANGUAGES", "LANGUAGE_CODE",
}

COTTON_BUILTINS = {"attrs", "slot"}


def primitive_name_from_path(path):
    return path.stem.replace("_", "-")


def parse_cvars(template_text):
    """Returns (props, found_cvars). props = list of {name, default, typed, required}."""
    match = CVARS_RE.search(template_text)
    if not match:
        return [], False

    body = match.group(1)
    props = []
    for m in ATTR_RE.finditer(body):
        name = m.group("name")
        if name.startswith("c-"):
            continue
        default = m.group("dq")
        if default is None:
            default = m.group("sq")
        typed = m.group("typed") == ":"
        end = m.end("name")
        rest = body[end:].lstrip()
        has_eq = rest.startswith("=")
        if not has_eq:
            default = None
        props.append({
            "name": name,
            "default": default,
            "typed": typed,
            "required": default is None,
        })
    return props, True


def has_default_slot(template_text):
    body = CVARS_RE.sub("", template_text)
    return bool(re.search(r"\{\{\s*slot\s*\}\}", body))


def named_slot_candidates(template_text, prop_names):
    body = CVARS_RE.sub("", template_text)
    candidates = set()
    for m in BARE_VAR_RE.finditer(body):
        name = m.group(1)
        if name in COTTON_BUILTINS:
            continue
        if name in prop_names:
            continue
        if name in DJANGO_CONTEXT_NAMES:
            continue
        candidates.add(name)
    return sorted(candidates)


def count_callsites(primitive, project_root):
    pattern = re.compile(rf"<c-{re.escape(primitive)}\b")
    bases = [
        project_root / "templates",
        project_root / "static" / "js",
        project_root / "core",
    ]
    callsite_files = {}
    total = 0
    for base in bases:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir():
                continue
            if path.suffix.lower() not in {".html", ".js", ".py"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            n = len(pattern.findall(text))
            if n:
                callsite_files[str(path.relative_to(project_root))] = n
                total += n
    return total, callsite_files


def build_inventory(project_root):
    cotton_dir = project_root / "app" / "_components" / "cotton"
    if not cotton_dir.exists():
        raise SystemExit(f"app/_components/cotton not found under {project_root}")
    primitives = []
    for html in sorted(cotton_dir.glob("*.html")):
        try:
            text = html.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        primitive = primitive_name_from_path(html)
        props, found_cvars = parse_cvars(text)
        prop_names = {p["name"] for p in props}
        callsite_total, callsite_files = count_callsites(primitive, project_root)
        primitives.append({
            "name": primitive,
            "file": str(html.relative_to(project_root)),
            "has_cvars": found_cvars,
            "props": props,
            "has_default_slot": has_default_slot(text),
            "named_slot_candidates": named_slot_candidates(text, prop_names),
            "callsite_count": callsite_total,
            "callsite_files": callsite_files,
        })
    return {
        "generated_by": "scripts/cotton_inventory.py",
        "cotton_dir": "app/_components/cotton",
        "primitive_count": len(primitives),
        "primitives": primitives,
    }


def print_summary(inventory):
    for p in inventory["primitives"]:
        required = [pp["name"] for pp in p["props"] if pp["required"]]
        optional = [pp["name"] for pp in p["props"] if not pp["required"]]
        print(f"<c-{p['name']}/>  ({p['callsite_count']} callsites across {len(p['callsite_files'])} files)")
        print(f"  required: {', '.join(required) or '—'}")
        print(f"  optional: {', '.join(optional) or '—'}")
        print(f"  default-slot: {p['has_default_slot']}")
        if p["named_slot_candidates"]:
            print(f"  named-slot candidates: {', '.join(p['named_slot_candidates'])}")
        print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="Project root (default: cwd)")
    parser.add_argument("--out", type=Path,
                        default=Path("reports/cotton-inventory/inventory.json"),
                        help="Output JSON path (relative to --root unless absolute)")
    parser.add_argument("--print", action="store_true",
                        help="Print human-readable summary to stdout")
    args = parser.parse_args()

    project_root = args.root.resolve()
    inventory = build_inventory(project_root)

    out = args.out if args.out.is_absolute() else project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    if args.print:
        print_summary(inventory)

    print(f"Wrote {out} ({inventory['primitive_count']} primitives)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
