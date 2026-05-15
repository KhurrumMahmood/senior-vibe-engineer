#!/usr/bin/env python
"""
Stage 2 of /find-frontend-duplication: collapse scanner outputs into
typed consolidation candidates.

Reads:
  --cotton            cotton-inventory.json
  --class-chains-raw  class-chains/raw.json
  --class-chains-norm class-chains/tone-norm.json
  --helpers           helpers.json

Writes:
  --output            candidates.json

Each candidate has:
  id, category, title, evidence (occurrence_count, file_count, files,
  occurrences, tokens), existing_primitive (or null), primitive_bypass
  (bool), notes.

Stdlib only. Read-only.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


# Class-chain category classifiers. Each rule is (name, predicate).
# Predicate receives the set of tokens (after tone-normalization).
def is_pill(tokens):
    return (
        any(t.startswith("bg-{tone}-") for t in tokens)
        and "rounded-full" in tokens
        and ("inline-flex" in tokens or "items-center" in tokens)
        and ("px-2.5" in tokens or "px-3" in tokens or "px-2" in tokens)
        and any(t.startswith("text-") and ("xs" in t or "sm" in t) for t in tokens)
    )


def is_alert(tokens):
    return (
        any(t.startswith("bg-{tone}-50") for t in tokens)
        and any(t.startswith("border-{tone}-200") for t in tokens)
        and ("rounded-lg" in tokens or "rounded-md" in tokens)
    )


def is_modal_overlay(tokens):
    return (
        ("fixed" in tokens or "absolute" in tokens)
        and ("inset-0" in tokens)
        and ("z-50" in tokens or "z-40" in tokens)
        and any(t.startswith("bg-") and "opacity" in t for t in tokens)
    )


def is_modal_panel(tokens):
    return (
        ("fixed" in tokens)
        and ("z-50" in tokens or "z-40" in tokens)
        and ("rounded-lg" in tokens or "rounded-md" in tokens)
        and "bg-white" in tokens
    )


def is_dropdown_menu(tokens):
    return (
        ("absolute" in tokens)
        and ("right-0" in tokens or "left-0" in tokens)
        and ("shadow-lg" in tokens or "shadow-md" in tokens)
        and ("z-50" in tokens or "z-40" in tokens)
        and "bg-white" in tokens
        and ("ring-1" in tokens or any(t.startswith("ring-") for t in tokens))
    )


def is_button(tokens):
    return (
        "inline-flex" in tokens
        and "items-center" in tokens
        and any(t in tokens for t in ("px-3", "px-4", "px-5"))
        and any(t in tokens for t in ("py-2", "py-1.5", "py-2.5"))
        and ("rounded-md" in tokens or "rounded-lg" in tokens)
        and ("shadow-sm" in tokens or "shadow" in tokens)
    )


def is_layout_utility(tokens):
    # Pure layout — no colors, no rounding, no shadow.
    has_color = any(t.startswith(("bg-", "text-", "border-", "ring-")) for t in tokens)
    has_shape = any(t.startswith(("rounded-", "shadow")) for t in tokens)
    return not has_color and not has_shape and len(tokens) <= 5


CLASSIFIERS = [
    ("modal-overlay", is_modal_overlay),
    ("modal-panel", is_modal_panel),
    ("dropdown-menu", is_dropdown_menu),
    ("pill-shell", is_pill),
    ("alert-shell", is_alert),
    ("button-variant", is_button),
    ("layout-utility", is_layout_utility),
]


# Map class-chain category -> existing cotton primitive name (or None).
PRIMITIVE_FOR_CATEGORY = {
    "pill-shell": "pill",
    "alert-shell": "alert",
    "modal-overlay": None,  # no c-modal primitive yet
    "modal-panel": None,
    "dropdown-menu": None,  # only c-user-menu exists, narrow
    "button-variant": None,
    "layout-utility": None,
}


def classify_chain(tokens_set):
    for name, fn in CLASSIFIERS:
        if fn(tokens_set):
            return name
    return "hand-rolled-primitive"


def stable_id(payload):
    h = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return h[:12]


def collapse_class_chains(norm_buckets, cotton_index):
    candidates = []
    for bucket in norm_buckets:
        tokens = set(bucket["tokens"])
        category = classify_chain(tokens)
        if category == "layout-utility":
            # surface as low-priority info but still emit
            pass
        primitive_name = PRIMITIVE_FOR_CATEGORY.get(category)
        existing = cotton_index.get(primitive_name) if primitive_name else None
        primitive_bypass = bool(existing) and bucket["occurrence_count"] >= 3
        if category == "hand-rolled-primitive":
            title = (
                f"unclassified hand-rolled chain "
                f"({bucket['occurrence_count']}× across {bucket['file_count']} files)"
            )
        elif category == "layout-utility":
            title = (
                f"layout-utility cluster "
                f"({bucket['occurrence_count']}× across {bucket['file_count']} files)"
            )
        else:
            title = (
                f"hand-rolled {category} "
                f"({bucket['occurrence_count']}× across {bucket['file_count']} files)"
            )
        if existing and primitive_bypass:
            title = (
                f"<c-{primitive_name}/> bypass — raw markup duplicated "
                f"{bucket['occurrence_count']}× across {bucket['file_count']} files"
            )
        candidates.append({
            "id": stable_id("chain:" + bucket["key"]),
            "source": "class-chain",
            "category": category,
            "title": title,
            "evidence": {
                "occurrence_count": bucket["occurrence_count"],
                "file_count": bucket["file_count"],
                "files": bucket["files"],
                "tokens": bucket["tokens"],
                "occurrences": bucket["occurrences"][:8],  # cap for output size
            },
            "existing_primitive": (
                {"name": primitive_name,
                 "callsite_count": existing["callsite_count"],
                 "callsite_files": list(existing["callsite_files"].keys())}
                if existing else None
            ),
            "primitive_bypass": primitive_bypass,
            "notes": "",
        })
    return candidates


def collapse_helpers(helpers):
    candidates = []
    for fork in helpers.get("duplicates_same_name", []):
        # Skip likely module-scoped sentinels
        name = fork["name"]
        if name in {"init", "close", "open", "start", "initialize"}:
            note = (
                "These names commonly mark per-module IIFE entry points; "
                "investigator must verify each is module-scoped before "
                "recommending consolidation."
            )
        else:
            note = ""
        candidates.append({
            "id": stable_id(f"helper:{name}:{','.join(fork['files'])}"),
            "source": "helper-scanner",
            "category": "helper-fork",
            "title": f"`{name}()` defined in {fork['file_count']} files",
            "evidence": {
                "occurrence_count": fork["definition_count"],
                "file_count": fork["file_count"],
                "files": fork["files"],
                "occurrences": fork["definitions"],
            },
            "existing_primitive": None,
            "primitive_bypass": False,
            "notes": note,
        })

    csrf_count = helpers.get("csrf_inline_count", 0)
    csrf_files = helpers.get("csrf_inline_files", [])
    if csrf_count >= 5:
        candidates.append({
            "id": stable_id(f"csrf-inline:{','.join(csrf_files)}"),
            "source": "helper-scanner",
            "category": "csrf-fetch",
            "title": (
                f"Inline 'X-CSRFToken' header in {csrf_count} places across "
                f"{len(csrf_files)} files (no shared csrfFetch wrapper)"
            ),
            "evidence": {
                "occurrence_count": csrf_count,
                "file_count": len(csrf_files),
                "files": csrf_files,
                "occurrences": helpers.get("csrf_inline_occurrences", [])[:8],
            },
            "existing_primitive": None,
            "primitive_bypass": False,
            "notes": (
                "A single `App.csrfFetch(url, init)` wrapper would absorb "
                "this. Investigator must confirm whether all callsites "
                "follow the same shape (same headers, same body handling)."
            ),
        })

    bare_count = helpers.get("bare_get_cookie_count", 0)
    bare_files = helpers.get("bare_get_cookie_files", [])
    if bare_count >= 5:
        candidates.append({
            "id": stable_id(f"bare-getcookie:{','.join(bare_files)}"),
            "source": "helper-scanner",
            "category": "implicit-cross-file-dependency",
            "title": (
                f"Bare `getCookie('csrftoken')` called {bare_count}× across "
                f"{len(bare_files)} files — implicit dependency on "
                f"site-config-core.js load order"
            ),
            "evidence": {
                "occurrence_count": bare_count,
                "file_count": len(bare_files),
                "files": bare_files,
                "occurrences": helpers.get("bare_get_cookie_occurrences", [])[:8],
            },
            "existing_primitive": None,
            "primitive_bypass": False,
            "notes": (
                "These callsites assume `getCookie` is hoisted globally. "
                "Should be `window.SiteConfigCore.getCookie(...)` or a "
                "shared csrfFetch wrapper. Investigator must verify the "
                "load order assumption holds for each file."
            ),
        })
    return candidates


def build_cotton_index(cotton_inventory):
    return {p["name"]: p for p in cotton_inventory["primitives"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cotton", type=Path, required=True)
    parser.add_argument("--class-chains-raw", type=Path, required=True)
    parser.add_argument("--class-chains-norm", type=Path, required=True)
    parser.add_argument("--helpers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cotton = json.loads(args.cotton.read_text())
    norm = json.loads(args.class_chains_norm.read_text())
    helpers = json.loads(args.helpers.read_text())

    cotton_index = build_cotton_index(cotton)
    chain_candidates = collapse_class_chains(norm["buckets"], cotton_index)
    helper_candidates = collapse_helpers(helpers)

    candidates = chain_candidates + helper_candidates

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "candidate_count": len(candidates),
        "by_category": _count_by(candidates, "category"),
        "candidates": candidates,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(candidates)} candidates)")
    return 0


def _count_by(items, key):
    out = {}
    for item in items:
        out[item[key]] = out.get(item[key], 0) + 1
    return out


if __name__ == "__main__":
    sys.exit(main())
