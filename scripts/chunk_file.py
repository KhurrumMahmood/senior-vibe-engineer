#!/usr/bin/env python3
"""AST-based chunker for oversized Python files (refactor-subsystem Phase 1.3.0).

Emits a chunk plan that respects AST structure: a class or function is never
split across chunks, and decorators travel with their ``def``. Packs top-level
declarations into chunks whose token count AND line count each stay below the
respective budgets (OR-gate — either budget trips a flush; L-21).

Between top-level declarations may lie free-floating statements (imports,
module docstrings, module-level constants, guarded ``if`` blocks). These become
``orphan-N`` chunks and get reported as first-class entries (R14 / L-12).

Tile-the-file invariant (L-22): the union of emitted chunks covers the entire
file gap-free from line 1 through EOF. Chunk N's reported ``line_end`` equals
one line before chunk N+1's first declaration; the last chunk extends to EOF;
chunk 1's reported ``line_start`` is clamped to 1.

Outputs:
  --format json      Machine-readable chunk map (used by inventory-scout briefs)
  --format markdown  Human-readable chunk map (inventory/<basename>__chunks.md)

Stdlib-only; runs on plain ``python3`` with no venv.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_TOKEN_BUDGET = 8000
DEFAULT_LOC_BUDGET = 2500
DEFAULT_MIN_FILE_LOC = 2000

# Rough heuristic: ~4 characters per token. Good enough for packing; scouts
# re-count actual tokens anyway.
CHARS_PER_TOKEN = 4


def _est_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _first_decorator_line(node: ast.AST) -> int:
    """Return ``node.lineno`` adjusted down to the first decorator line, if any."""
    decos = getattr(node, "decorator_list", None) or []
    if not decos:
        return node.lineno  # type: ignore[attr-defined]
    return min(d.lineno for d in decos)


def _kind(node: ast.AST) -> str:
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_def"
    if isinstance(node, ast.FunctionDef):
        return "def"
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return "assign"
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"
    if isinstance(node, ast.If):
        return "if"
    if isinstance(node, ast.Try):
        return "try"
    return node.__class__.__name__.lower()


def _name(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign):
        parts: list[str] = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                parts.append(target.id)
            elif isinstance(target, ast.Tuple):
                parts.extend(
                    e.id for e in target.elts if isinstance(e, ast.Name)
                )
        return ", ".join(parts) or "<assign>"
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Import):
        return ", ".join(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        return f"from {mod}"
    return "<module>"


def _summary(source_lines: list[str], node: ast.AST) -> str:
    """Return a one-line summary: docstring if present else first body line."""
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
    ):
        doc = ast.get_docstring(node)
        if doc:
            return doc.splitlines()[0].strip()
    start = node.lineno - 1  # type: ignore[attr-defined]
    for raw in source_lines[start:start + 5]:
        s = raw.strip()
        if s and not s.startswith("#"):
            return s[:120]
    return ""


def _declarations(
    tree: ast.Module, source_lines: list[str]
) -> list[dict[str, Any]]:
    """Extract top-level declarations with their decorator-anchored start lines."""
    decls: list[dict[str, Any]] = []
    for node in tree.body:
        start = _first_decorator_line(node)
        end = getattr(node, "end_lineno", node.lineno)  # type: ignore[attr-defined]
        text = "\n".join(source_lines[start - 1:end])
        decls.append({
            "kind": _kind(node),
            "name": _name(node),
            "line_start": start,
            "line_end": end,
            "summary": _summary(source_lines, node),
            "tokens": _est_tokens(text),
            "loc": end - start + 1,
        })
    decls.sort(key=lambda d: (d["line_start"], d["line_end"]))
    return decls


def _parse_loc_hints(raw: str | None) -> list[tuple[int, int]]:
    if not raw:
        return []
    out: list[tuple[int, int]] = []
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        try:
            a, b = token.split(":", 1)
            lo, hi = int(a), int(b)
        except ValueError:
            continue
        if hi >= lo > 0:
            out.append((lo, hi))
    return out


def _pack_chunks(
    decls: list[dict[str, Any]],
    token_budget: int,
    loc_budget: int,
    loc_hints: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    """OR-gate packer: flush when adding the next decl would breach either budget.

    Loc-hints bias the packer: if a hint range ends at the current decl's
    ``line_end``, that is a preferred flush point.
    """
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    cur_tokens = 0
    cur_loc = 0
    hint_ends = {hi for _, hi in loc_hints}

    for d in decls:
        d_tokens = d["tokens"]
        d_loc = d["loc"]
        if current and (
            cur_tokens + d_tokens > token_budget
            or cur_loc + d_loc > loc_budget
        ):
            chunks.append({"declarations": current})
            current = []
            cur_tokens = 0
            cur_loc = 0
        current.append(d)
        cur_tokens += d_tokens
        cur_loc += d_loc
        if d["line_end"] in hint_ends and current:
            chunks.append({"declarations": current})
            current = []
            cur_tokens = 0
            cur_loc = 0
    if current:
        chunks.append({"declarations": current})
    return chunks


def _tile_chunks(
    chunks: list[dict[str, Any]], total_loc: int
) -> list[dict[str, Any]]:
    """Extend each chunk's line_start/line_end so the union covers [1, total_loc].

    Chunk N's line_end is set to (chunk N+1's first decl line - 1). The first
    chunk's line_start is clamped to 1; the last chunk's line_end to total_loc.
    """
    for ch in chunks:
        decls = ch["declarations"]
        ch["line_start"] = decls[0]["line_start"]
        ch["line_end"] = decls[-1]["line_end"]
    for i in range(len(chunks) - 1):
        chunks[i]["line_end"] = chunks[i + 1]["line_start"] - 1
    if chunks:
        chunks[0]["line_start"] = 1
        chunks[-1]["line_end"] = total_loc
    return chunks


def _orphan_regions(
    decls: list[dict[str, Any]], total_loc: int
) -> list[tuple[int, int]]:
    """Return [start, end] line ranges not covered by any declaration."""
    if not decls:
        return [(1, total_loc)] if total_loc else []
    regions: list[tuple[int, int]] = []
    if decls[0]["line_start"] > 1:
        regions.append((1, decls[0]["line_start"] - 1))
    prev_end = decls[0]["line_end"]
    for d in decls[1:]:
        if d["line_start"] > prev_end + 1:
            regions.append((prev_end + 1, d["line_start"] - 1))
        prev_end = max(prev_end, d["line_end"])
    if prev_end < total_loc:
        regions.append((prev_end + 1, total_loc))
    # Drop blank-only regions
    return regions


def build_plan(
    source: str,
    filename: str,
    token_budget: int,
    loc_budget: int,
    loc_hints: list[tuple[int, int]],
    min_file_loc: int,
) -> dict[str, Any]:
    source_lines = source.splitlines()
    total_loc = len(source_lines)
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return {
            "file": filename,
            "total_loc": total_loc,
            "chunks": [],
            "error": f"SyntaxError: {exc}",
        }

    decls = _declarations(tree, source_lines)

    # Small files: single chunk, skip the packer.
    if total_loc < min_file_loc:
        return {
            "file": filename,
            "total_loc": total_loc,
            "token_budget": token_budget,
            "loc_budget": loc_budget,
            "chunks": [{
                "id": "C-01",
                "line_start": 1,
                "line_end": total_loc,
                "declarations": decls,
                "token_estimate": sum(d["tokens"] for d in decls),
                "loc": total_loc,
            }],
            "orphans": [],
        }

    chunks = _pack_chunks(decls, token_budget, loc_budget, loc_hints)
    chunks = _tile_chunks(chunks, total_loc)
    for i, ch in enumerate(chunks, start=1):
        ch["id"] = f"C-{i:02d}"
        ch["token_estimate"] = sum(d["tokens"] for d in ch["declarations"])
        ch["loc"] = ch["line_end"] - ch["line_start"] + 1

    orphan_regions = _orphan_regions(decls, total_loc)
    orphans = [
        {
            "id": f"orphan-{i}",
            "line_start": lo,
            "line_end": hi,
            "loc": hi - lo + 1,
        }
        for i, (lo, hi) in enumerate(orphan_regions, start=1)
    ]

    return {
        "file": filename,
        "total_loc": total_loc,
        "token_budget": token_budget,
        "loc_budget": loc_budget,
        "chunks": chunks,
        "orphans": orphans,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Chunk map: `{plan['file']}`")
    lines.append("")
    lines.append(f"- Total LOC: **{plan['total_loc']}**")
    if "token_budget" in plan:
        lines.append(
            f"- Budgets: token={plan['token_budget']} "
            f"loc={plan['loc_budget']}"
        )
    if plan.get("error"):
        lines.append(f"- **ERROR:** {plan['error']}")
        return "\n".join(lines) + "\n"

    lines.append(f"- Chunks: **{len(plan.get('chunks', []))}**")
    lines.append(f"- Orphan regions: **{len(plan.get('orphans', []))}**")
    lines.append("")

    for ch in plan.get("chunks", []):
        lines.append(
            f"## {ch['id']} — lines {ch['line_start']}–{ch['line_end']} "
            f"(loc={ch['loc']}, tokens≈{ch['token_estimate']})"
        )
        lines.append("")
        lines.append("| Line | Kind | Name | Summary |")
        lines.append("|---|---|---|---|")
        for d in ch["declarations"]:
            summary = (d.get("summary") or "").replace("|", "\\|")
            lines.append(
                f"| {d['line_start']} | {d['kind']} | "
                f"`{d['name']}` | {summary} |"
            )
        lines.append("")

    if plan.get("orphans"):
        lines.append("## Orphan regions")
        lines.append("")
        lines.append("| ID | Line range | LOC |")
        lines.append("|---|---|---|")
        for o in plan["orphans"]:
            lines.append(
                f"| {o['id']} | {o['line_start']}–{o['line_end']} "
                f"| {o['loc']} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", type=Path, help="Python source file to chunk")
    p.add_argument("--token-budget", type=int, default=DEFAULT_TOKEN_BUDGET)
    p.add_argument("--loc-budget", type=int, default=DEFAULT_LOC_BUDGET)
    p.add_argument(
        "--min-file-loc", type=int, default=DEFAULT_MIN_FILE_LOC,
        help="Files shorter than this return one chunk (skip the split).",
    )
    p.add_argument(
        "--loc-hints", default=None,
        help="Comma-separated preferred flush points, e.g. '120:240,300:480'",
    )
    p.add_argument(
        "--format", choices=("json", "markdown"), default="json",
    )
    p.add_argument(
        "--output", type=Path, default=None,
        help="Write to this file instead of stdout.",
    )
    args = p.parse_args(argv)

    if not args.path.is_file():
        print(f"[chunk_file] ERROR: not a file: {args.path}", file=sys.stderr)
        return 2
    if args.path.suffix != ".py":
        print(
            f"[chunk_file] WARN: {args.path} is not Python (.py); "
            f"chunker only handles Python.",
            file=sys.stderr,
        )

    source = args.path.read_text(encoding="utf-8", errors="replace")
    plan = build_plan(
        source,
        str(args.path),
        args.token_budget,
        args.loc_budget,
        _parse_loc_hints(args.loc_hints),
        args.min_file_loc,
    )

    if args.format == "json":
        body = json.dumps(plan, indent=2)
    else:
        body = render_markdown(plan)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        print(
            f"[chunk_file] wrote {args.output} "
            f"(chunks={len(plan.get('chunks', []))}, "
            f"orphans={len(plan.get('orphans', []))})",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
