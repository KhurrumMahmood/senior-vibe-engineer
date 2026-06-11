#!/usr/bin/env python3
"""Convention census — discover what variants exist across a surface.

Complementary to scan_coverage.py (which asks "where is a *declared* standard
absent?"), census mode asks: "for a given *concern*, what variants exist across
a surface, what is the majority, and who are the stragglers?"

Use this **before** declaring a standard: census tells you what the population
looks like, which variant to adopt as canonical, and who must migrate.

Concerns are Python plugins registered in the CONCERN_REGISTRY dict below (~30
lines each to add). Detection is pure AST — deterministic, no LLM calls.
Stdlib-only.

Usage:
    python3 census.py --concern json_response_envelope <paths...> [--json OUT]

    <paths...>  One or more source roots or glob patterns to scan.
                Example: app/api app/api/site_config
    --json OUT  Optional path to write a JSON artifact with the full results.

Output (stdout):
    - Per-variant counts sorted desc.
    - Majority variant + share %.
    - Straggler file:line list for each minority variant.
    - Opaque count (variable/non-literal payloads, not classified).
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, NamedTuple

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

SKIP_DIRS = {".venv", "__pycache__", "migrations", ".git", "node_modules",
             "tests", "experiments", "worktrees"}


class Site(NamedTuple):
    """A single detected occurrence of a concern."""
    file: str       # path relative to the project root
    line: int
    variant: str    # normalised variant key, or "opaque"
    text: str       # source line snippet (truncated)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _iter_py_files(paths: list[str], root: Path) -> Iterator[Path]:
    """Yield .py files under each path, skipping SKIP_DIRS.

    root must already be resolved (no symlinks). All candidate paths are
    resolved before relative_to() to avoid /var vs /private/var mismatches
    on macOS.
    """
    seen: set[Path] = set()
    for raw in paths:
        # Treat as a glob if it contains *, else as a directory or file.
        candidates: list[Path] = []
        if "*" in raw:
            candidates = sorted(root.glob(raw))
        else:
            p = Path(raw) if Path(raw).is_absolute() else root / raw
            p = p.resolve()
            if p.is_file() and p.suffix == ".py":
                candidates = [p]
            elif p.is_dir():
                candidates = sorted(p.rglob("*.py"))
        for path in candidates:
            path = path.resolve()
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                # Path outside of root — skip.
                continue
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if path not in seen:
                seen.add(path)
                yield path


def _dotted(node: ast.AST) -> str:
    """Reconstruct a dotted name from a Name/Attribute chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""


def _literal_dict_keys(node: ast.AST) -> list[str] | None:
    """Return sorted string keys if node is a dict literal with all-string keys.

    Returns None if the node is not a dict literal, has non-string keys, or
    has any non-literal values (we want only pure dict-literal payloads).
    """
    if not isinstance(node, ast.Dict):
        return None
    keys: list[str] = []
    for k in node.keys:
        if k is None:
            return None  # dict unpacking — e.g. {**other}
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            return None
        keys.append(k.value)
    return sorted(keys)


def _status_kwarg(call_node: ast.Call) -> tuple[bool, int | None]:
    """Return (has_status_kwarg, status_value_if_literal) for a Call node."""
    for kw in call_node.keywords:
        if kw.arg == "status":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                return True, kw.value.value
            return True, None
    return False, None


# ---------------------------------------------------------------------------
# Concern: json_response_envelope
# ---------------------------------------------------------------------------
# Variant key: a JSON-serialisable string encoding
#   (sorted_keys_tuple, has_status_kwarg, status_value_or_null)
# e.g. '["error"],status=500'  or  '["error","success"],no_status'
#
# Only dict-literal payloads are classified.  Variable/non-literal payloads
# (e.g. `JsonResponse(result.payload, ...)`) are counted as "opaque".

def _json_response_envelope_finder(
    tree: ast.Module,
    path: Path,
    root: Path,
    srclines: list[str],
) -> list[Site]:
    """Find all JsonResponse calls; classify by envelope shape."""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    sites: list[Site] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name == "JsonResponse" or name.endswith(".JsonResponse"):
                ln = getattr(node, "lineno", 0)
                text = (srclines[ln - 1].strip()[:120]
                        if 0 < ln <= len(srclines) else "")
                # First positional arg (or `data` kwarg) is the payload.
                payload: ast.AST | None = None
                if node.args:
                    payload = node.args[0]
                else:
                    for kw in node.keywords:
                        if kw.arg == "data":
                            payload = kw.value
                            break
                if payload is None:
                    variant = "opaque"
                else:
                    keys = _literal_dict_keys(payload)
                    if keys is None:
                        # Non-literal payload (variable, attribute, call, etc.)
                        variant = "opaque"
                    else:
                        has_status, status_val = _status_kwarg(node)
                        key_part = json.dumps(keys, separators=(",", ":"))
                        if has_status:
                            status_part = (f"status={status_val}"
                                           if status_val is not None
                                           else "status=<expr>")
                        else:
                            status_part = "no_status"
                        variant = f"{key_part},{status_part}"
                sites.append(Site(file=rel, line=ln, variant=variant, text=text))
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return sites


def _find_json_response_envelope(path: Path, root: Path) -> list[Site]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        srclines = src.splitlines()
        return _json_response_envelope_finder(tree, path.resolve(), root, srclines)
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError, RecursionError):
        return []


# ---------------------------------------------------------------------------
# Concern registry
# ---------------------------------------------------------------------------

class Concern:
    """A registered census concern."""

    def __init__(
        self,
        id: str,
        description: str,
        site_finder: Callable[[Path, Path], list[Site]],
    ) -> None:
        self.id = id
        self.description = description
        self.site_finder = site_finder


CONCERN_REGISTRY: dict[str, Concern] = {
    "json_response_envelope": Concern(
        id="json_response_envelope",
        description=(
            "Envelope shape of Django JsonResponse dict-literal payloads. "
            "Variant key = (sorted top-level string keys, status kwarg presence, "
            "literal status value). Opaque = variable/non-literal payload."
        ),
        site_finder=_find_json_response_envelope,
    ),
}


# ---------------------------------------------------------------------------
# Census runner
# ---------------------------------------------------------------------------

def run_census(
    concern: Concern,
    paths: list[str],
    root: Path,
) -> dict[str, Any]:
    """Run a concern over all Python files in paths.

    Returns a dict with:
        concern_id, description, total, opaque_count,
        variants: [{variant, count, share, sites: [{file, line, text}]}]
            sorted by count desc (deterministic: ties broken by variant key),
        majority_variant, majority_share,
        stragglers: [{variant, count, sites: [{file, line, text}]}]
            for every non-majority variant (i.e. all but the top one).
    """
    # Resolve root so relative_to() works correctly on macOS (/var → /private/var).
    root = root.resolve()
    all_sites: list[Site] = []
    for py_file in _iter_py_files(paths, root):
        all_sites.extend(concern.site_finder(py_file, root))

    total = len(all_sites)
    opaque_sites = [s for s in all_sites if s.variant == "opaque"]
    classified = [s for s in all_sites if s.variant != "opaque"]

    counts: Counter[str] = Counter(s.variant for s in classified)

    # Build per-variant lists sorted by count desc, ties broken by key.
    variant_order = sorted(counts.keys(), key=lambda v: (-counts[v], v))

    classified_total = sum(counts.values())

    def _site_dicts(sites: list[Site]) -> list[dict]:
        return sorted(
            [{"file": s.file, "line": s.line, "text": s.text} for s in sites],
            key=lambda d: (d["file"], d["line"]),
        )

    variants_out: list[dict] = []
    for v in variant_order:
        v_sites = [s for s in classified if s.variant == v]
        share = counts[v] / classified_total if classified_total else 0.0
        variants_out.append({
            "variant": v,
            "count": counts[v],
            "share": round(share, 4),
            "sites": _site_dicts(v_sites),
        })

    majority_variant = variant_order[0] if variant_order else None
    majority_share = (
        round(counts[majority_variant] / classified_total, 4)
        if majority_variant and classified_total
        else None
    )

    stragglers = [v for v in variants_out if v["variant"] != majority_variant]

    return {
        "concern_id": concern.id,
        "description": concern.description,
        "total": total,
        "classified": classified_total,
        "opaque_count": len(opaque_sites),
        "opaque_sites": _site_dicts(opaque_sites),
        "variants": variants_out,
        "majority_variant": majority_variant,
        "majority_share": majority_share,
        "stragglers": stragglers,
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_census(result: dict) -> str:
    """Render a human-readable census report."""
    L: list[str] = []
    L.append(f"# Convention census: {result['concern_id']}")
    L.append("")
    L.append(f"_{result['description']}_")
    L.append("")
    L.append(f"Scanned at {result['scanned_at']}.")
    L.append("")
    total = result["total"]
    classified = result["classified"]
    opaque = result["opaque_count"]
    L.append(f"**Total calls found:** {total}  "
             f"(classified: {classified}, opaque/non-literal: {opaque})")
    L.append("")

    variants = result["variants"]
    if not variants:
        L.append("No classified calls found.")
        if opaque:
            L.append(f"{opaque} opaque (non-literal payload) calls were found.")
        return "\n".join(L)

    majority = result["majority_variant"]
    majority_share = result["majority_share"]

    L.append("## Variant distribution (classified calls)")
    L.append("")
    L.append("| Variant | Count | Share |")
    L.append("|---------|-------|-------|")
    for v in variants:
        marker = " **[majority]**" if v["variant"] == majority else ""
        L.append(f"| `{v['variant']}` | {v['count']} | {v['share']*100:.1f}%{marker} |")
    L.append("")

    L.append(f"**Majority variant:** `{majority}` "
             f"({majority_share * 100:.1f}% of classified calls)")
    L.append("")

    stragglers = result["stragglers"]
    if not stragglers:
        L.append("No stragglers — all classified calls use the majority variant.")
    else:
        L.append(f"## Stragglers ({len(stragglers)} minority variant(s))")
        L.append("")
        for v in stragglers:
            L.append(f"### `{v['variant']}` — {v['count']} call(s)")
            for s in v["sites"]:
                L.append(f"  - `{s['file']}:{s['line']}` — {s['text']}")
            L.append("")

    if opaque:
        L.append(f"## Opaque calls ({opaque} non-literal payloads)")
        L.append("")
        L.append("These calls pass a variable or non-literal first argument and are "
                 "not classified into a variant. They do not count toward majority math.")
        L.append("")
        for s in result["opaque_sites"]:
            L.append(f"  - `{s['file']}:{s['line']}` — {s['text']}")
        L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--concern",
        required=True,
        choices=sorted(CONCERN_REGISTRY.keys()),
        help="Which concern to census.",
    )
    ap.add_argument(
        "paths",
        nargs="+",
        help="Source roots or glob patterns to scan (relative to cwd or absolute).",
    )
    ap.add_argument(
        "--json",
        dest="json_out",
        metavar="OUT",
        type=Path,
        default=None,
        help="Optional path to write a JSON artifact with the full results.",
    )
    ap.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root for relative path reporting (default: cwd).",
    )
    args = ap.parse_args(argv)

    root = (args.project_root or Path.cwd()).resolve()
    concern = CONCERN_REGISTRY[args.concern]

    result = run_census(concern, args.paths, root)

    print(render_census(result))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2))
        print(f"\n[JSON artifact written to {args.json_out}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
