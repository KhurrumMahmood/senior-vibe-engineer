#!/usr/bin/env python3
"""
Component primitive inventory (profile-driven, framework-neutral).

Reads the host's component system from the durable host profile's
`component_profile` block (`engineering_home.component_profile`) and emits a
JSON catalogue of every UI primitive it declares. Nothing is baked in: the
profile's `kind` (e.g. `cotton`, `jsx`, `vue`) selects per-kind defaults
(definition file extensions, the callsite-reference regex, how a primitive
name is derived from a file), and the profile may override the definitions
root / reference pattern / extensions. Per-invocation CLI flags override the
profile in turn.

`kind == "none"` (the default for an un-adapted repo) is the graceful no-op:
no declared component system, so the inventory is simply empty rather than a
crash. The same empty result is returned when there is no resolvable
definitions root on disk.

For `kind: cotton` the full django-cotton analysis is preserved: declared
props (from `<c-vars>`), default-slot presence, named-slot candidates (bare
`{{ name }}` refs that aren't props), and per-primitive callsite counts. For
other kinds the inventory is reduced to names + callsite counts (deep
prop/slot analysis is cotton-only for now), and the top-level dict carries
`"analysis": "names-and-callsites-only"` to be honest about that.

Callsite searching uses the shared per-skill *scope* mechanism
(`_common/scope.py`) — the host tunes which files are searched via
`.engineering/docs/find-frontend-duplication-scope.md`, not by editing this
script. The default is the whole repo minus builtin/host ignores.

Used by:
  - find-frontend-duplication (to know which primitives already exist
    before the agent suggests "extract a new component")
  - extract-cotton-primitive (to know the conventions a new primitive
    must match: tone-prop pattern, {{ attrs }} pass-through, etc.)
  - manual review (`--print` for a quick human summary)

Usage:
  python3 scripts/cotton_inventory.py
  python3 scripts/cotton_inventory.py --print
  python3 scripts/cotton_inventory.py --out /tmp/inventory.json
  python3 scripts/cotton_inventory.py --kind jsx --definitions-root src/components

Stdlib only. Read-only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# _common is two levels up from this scripts/ dir
# (.claude/skills/find-frontend-duplication/scripts/ -> .claude/skills).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
import engineering_home as _eh  # noqa: E402
import scope as _scope  # noqa: E402

SKILL_NAME = "find-frontend-duplication"

# Files searched for primitive callsites, regardless of kind. The definition
# files themselves live under definitions_root and are scanned separately.
CALLSITE_EXTENSIONS = {
    ".cjs", ".html", ".js", ".jsx", ".mjs", ".py", ".ts", ".tsx", ".vue",
}


def _stem_dashed(path):
    """File stem with `_` -> `-` (cotton's primitive-name convention)."""
    return path.stem.replace("_", "-")


def _stem_plain(path):
    """File stem unchanged (PascalCase / camelCase kept for JSX/Vue)."""
    return path.stem


# Per-kind defaults a minimal manifest (`{"kind": "<k>"}`) relies on. The
# profile's non-empty `definitions_root` / `reference_pattern` / `extensions`
# override these; per-invocation CLI flags override the profile. Each entry:
#   extensions    — definition file suffixes to scan under definitions_root
#   reference     — per-primitive callsite regex template; `{name}` is filled
#                   with the re.escape'd primitive name
#   name_from     — file -> primitive name derivation
KIND_DEFAULTS = {
    "cotton": {
        "extensions": [".html"],
        "reference": r"<c-{name}\b",
        "name_from": _stem_dashed,
    },
    "jsx": {
        "extensions": [".jsx", ".tsx"],
        "reference": r"<{name}\b",
        "name_from": _stem_plain,
    },
    "vue": {
        "extensions": [".vue"],
        "reference": r"<{name}\b",
        "name_from": _stem_plain,
    },
}


# --- Cotton-specific deep parsing (preserved verbatim) ----------------------

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


# --- Callsite scanning (scope-driven, framework-neutral) --------------------

def _scan_callsites(primitives, reference_template, project_root):
    """Count per-primitive callsites across the skill's in-scope files.

    Returns ``{name: (total, {rel_path: count})}``. Files are resolved via the
    shared scope mechanism (host-tunable, ignore-first whole-repo by default)
    and each is read exactly once; per-primitive match counts are accumulated
    from a precompiled reference regex.
    """
    patterns = {
        name: re.compile(reference_template.format(name=re.escape(name)))
        for name in primitives
    }
    results = {name: (0, {}) for name in primitives}
    sc = _scope.load_scope(project_root, SKILL_NAME)
    for path in _scope.iter_paths(project_root, sc, extensions=CALLSITE_EXTENSIONS):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(project_root))
        for name, pattern in patterns.items():
            n = len(pattern.findall(text))
            if n:
                total, files = results[name]
                files[rel] = n
                results[name] = (total + n, files)
    return results


# --- Profile resolution -----------------------------------------------------

def _resolve_profile(project_root, kind, definitions_root, reference_pattern,
                     extensions):
    """Resolve effective component config from CLI overrides + host profile.

    Precedence per field: CLI override (non-None) > host profile (non-empty)
    > per-kind default. Returns a dict with resolved ``kind``,
    ``definitions_root`` (str or ""), ``reference`` (template or ""),
    ``extensions`` (list), and ``name_from`` (callable) — or ``None`` when the
    resolved kind is ``"none"`` (no declared component system).
    """
    profile = _eh.component_profile(project_root)

    # kind: CLI > host profile. component_profile() defaults to "none".
    eff_kind = kind if kind else profile["kind"]
    if not eff_kind or eff_kind == "none":
        return None

    defaults = KIND_DEFAULTS.get(eff_kind, {})

    eff_defs = definitions_root
    if eff_defs is None:
        eff_defs = profile["definitions_root"] or ""

    # The callsite reference is a per-primitive *template*: it must contain the
    # `{name}` placeholder so each primitive compiles its OWN pattern. A pattern
    # without `{name}` (e.g. a bare discovery regex like `<(c-[\w-]+)`) would
    # `.format()` to one identical regex for every primitive, silently
    # collapsing all of them onto the same repo-wide total. Such a pattern is
    # rejected here in favor of the kind default; if the kind has no default
    # either, `reference` stays "" and callsite counting is skipped (counts
    # reported as 0) rather than reported wrong. This guards both the manifest
    # value and a `--reference-pattern` CLI override, since neither has any
    # legitimate use without `{name}` on this code path.
    eff_ref = reference_pattern
    if eff_ref is None:
        eff_ref = profile["reference_pattern"] or ""
    if "{name}" not in (eff_ref or ""):
        eff_ref = defaults.get("reference", "")

    if extensions is not None:
        eff_exts = list(extensions)
    elif profile["extensions"]:
        eff_exts = list(profile["extensions"])
    else:
        eff_exts = list(defaults.get("extensions", []))

    return {
        "kind": eff_kind,
        "definitions_root": eff_defs,
        "reference": eff_ref,
        "extensions": eff_exts,
        "name_from": defaults.get("name_from", _stem_plain),
    }


def _empty_inventory():
    return {
        "generated_by": "scripts/cotton_inventory.py",
        "component_system": "none",
        "definitions_root": None,
        "primitive_count": 0,
        "primitives": [],
    }


def _iter_definition_files(defs_dir, extensions):
    """Sorted definition files directly under ``defs_dir`` matching ``extensions``."""
    exts = {e.lower() for e in extensions}
    files = [
        p for p in sorted(defs_dir.glob("*"))
        if p.is_file() and p.suffix.lower() in exts
    ]
    return files


def build_inventory(project_root, *, kind=None, definitions_root=None,
                    reference_pattern=None, extensions=None):
    """Build a component primitive inventory for ``project_root``.

    ``project_root`` is the only required (positional) argument, preserving the
    existing call contract. The keyword overrides each default to ``None`` so
    the durable host ``component_profile`` is used when absent:

      - ``kind`` — component system (``cotton`` / ``jsx`` / ``vue`` / ...).
      - ``definitions_root`` — directory holding primitive definition files,
        resolved relative to ``project_root`` (absolute paths honored).
      - ``reference_pattern`` — per-primitive callsite regex template; ``{name}``
        is filled with the escaped primitive name.
      - ``extensions`` — definition file suffixes (iterable of ``".ext"``).

    Returns a dict with a ``"primitives"`` list (always present). Gracefully
    returns an empty inventory — never raises — when there is no declared
    component system (``kind == "none"``) or no resolvable definitions root.
    """
    resolved = _resolve_profile(
        project_root, kind, definitions_root, reference_pattern, extensions,
    )
    if resolved is None:
        return _empty_inventory()

    defs_rel = resolved["definitions_root"]
    if not defs_rel:
        return _empty_inventory()

    defs_path = Path(defs_rel)
    defs_dir = defs_path if defs_path.is_absolute() else project_root / defs_path
    if not defs_dir.exists():
        return _empty_inventory()

    is_cotton = resolved["kind"] == "cotton"
    name_from = resolved["name_from"]
    reference = resolved["reference"]

    # Pass 1: discover primitive names from definition files.
    definitions = []  # list of (name, path, text|None)
    for f in _iter_definition_files(defs_dir, resolved["extensions"]):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = None
        definitions.append((name_from(f), f, text))

    # Pass 2: one scope-driven walk to count callsites for all primitives.
    names = [name for name, _f, _t in definitions]
    callsites = (
        _scan_callsites(names, reference, project_root) if reference else
        {name: (0, {}) for name in names}
    )

    primitives = []
    for name, f, text in definitions:
        total, files = callsites.get(name, (0, {}))
        rel_file = str(f.relative_to(project_root))
        if is_cotton:
            if text is None:
                # Unreadable cotton definition: skip the deep parse but still
                # surface the primitive (matches prior skip-on-read behavior
                # for binary/undecodable files).
                continue
            props, found_cvars = parse_cvars(text)
            prop_names = {p["name"] for p in props}
            primitives.append({
                "name": name,
                "file": rel_file,
                "has_cvars": found_cvars,
                "props": props,
                "has_default_slot": has_default_slot(text),
                "named_slot_candidates": named_slot_candidates(text, prop_names),
                "callsite_count": total,
                "callsite_files": files,
            })
        else:
            primitives.append({
                "name": name,
                "file": rel_file,
                "callsite_count": total,
                "callsite_files": files,
            })

    inventory = {
        "generated_by": "scripts/cotton_inventory.py",
        "component_system": resolved["kind"],
        "definitions_root": defs_rel,
        "primitive_count": len(primitives),
        "primitives": primitives,
    }
    if not is_cotton:
        inventory["analysis"] = "names-and-callsites-only"
    return inventory


def print_summary(inventory):
    cotton = inventory.get("component_system") == "cotton"
    for p in inventory["primitives"]:
        n_files = len(p.get("callsite_files", {}))
        print(f"{p['name']}  ({p.get('callsite_count', 0)} callsites across {n_files} files)")
        if cotton:
            required = [pp["name"] for pp in p["props"] if pp["required"]]
            optional = [pp["name"] for pp in p["props"] if not pp["required"]]
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
    parser.add_argument("--kind", default=None,
                        help="Override component system (cotton/jsx/vue/...). "
                             "Default: read from durable component_profile.")
    parser.add_argument("--definitions-root", default=None,
                        help="Override the primitive definitions directory "
                             "(relative to --root unless absolute).")
    parser.add_argument("--reference-pattern", default=None,
                        help="Override the per-primitive callsite regex "
                             "template ({name} is the escaped primitive name).")
    parser.add_argument("--extensions", default=None,
                        help="Override definition file extensions "
                             "(comma-separated, e.g. '.jsx,.tsx').")
    args = parser.parse_args()

    project_root = args.root.resolve()
    exts = None
    if args.extensions is not None:
        exts = [e.strip() for e in args.extensions.split(",") if e.strip()]

    inventory = build_inventory(
        project_root,
        kind=args.kind,
        definitions_root=args.definitions_root,
        reference_pattern=args.reference_pattern,
        extensions=exts,
    )

    out = args.out if args.out.is_absolute() else project_root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    if inventory["component_system"] == "none":
        print("no component system declared (component_profile.kind = none) "
              "— empty inventory")
    elif args.print:
        print_summary(inventory)

    print(f"Wrote {out} ({inventory['primitive_count']} primitives)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
