#!/usr/bin/env python3
"""Render a bounded Rust public-declaration explanation and sidecars."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_rust"
sys.path.insert(0, str(COMMON))

from rust_lexical_facts import (  # noqa: E402
    add_tool_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    declaration_facts,
    hash_bytes,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def _key(fact: dict) -> str:
    raw = f"{fact['file']}\0{fact['kind']}\0{fact['symbol']}".encode()
    return f"{fact['symbol']}-{hash_bytes(raw)[:12]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output must be inside --project-root")
    sidecar = output.with_suffix("")
    annotations = sidecar / "annotations"
    artifacts = [
        output,
        sidecar / "targets.json",
        sidecar / "scan.json",
        sidecar / "unexplained.txt",
        sidecar / "surprises.txt",
    ]
    clear_artifacts(artifacts)
    if annotations.is_dir():
        for old in annotations.glob("*.md"):
            old.unlink()

    snapshot = collect_snapshot(
        root,
        [args.target],
        rustc=args.rustc,
        cargo=args.cargo,
        rustfmt=args.rustfmt,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    facts: list[dict] = []
    unexplained: list[dict] = []
    for row in snapshot["inventory"]:
        if row["role"] != "eligible":
            continue
        facts.extend(declaration_facts(row))
        source = row["_source"].decode("utf-8")
        for match in re.finditer(r"(?m)^\s*pub\s+use\s+([^;]+);", source):
            unexplained.append(
                {
                    "file": row["file"],
                    "symbol": match.group(1).strip(),
                    "reason": "re-export requires name resolution and remains unexplained",
                }
            )
    facts.sort(key=lambda fact: (fact["file"], fact["span"]["start_byte"], fact["symbol"]))
    for fact in facts:
        fact["symbol_key"] = _key(fact)
    selected, overflow = facts[:15], facts[15:]
    annotations.mkdir(parents=True, exist_ok=True)
    for fact in selected:
        atomic_text(
            annotations / f"{fact['symbol_key']}.md",
            f"# `{fact['symbol']}`\n\n"
            f"- Kind: `{fact['kind']}`\n"
            f"- Source: `{fact['file']}`\n"
            f"- Contract: direct public Rust declaration with exact lexical span.\n"
            f"- Preconditions: unexplained without semantic/caller evidence.\n"
            f"- Postconditions: unexplained without semantic/caller evidence.\n"
            f"- Invariants: lexical declaration; behavior remains unexplained.\n"
            f"- Unexplained regions: function body, macro expansion, resolved types, and callers.\n",
        )
    analysis = public_snapshot(snapshot)
    targets = {
        "schema_version": 1,
        "target": args.target,
        "language": "rust",
        "status": snapshot["status"],
        "analysis": {"rust": analysis},
        "files": [row["file"] for row in snapshot["inventory"] if row["role"] == "eligible"],
        "public_symbol_count": len(facts),
        "selected": selected,
        "overflow": overflow,
        "unexplained": unexplained,
    }
    atomic_json(sidecar / "targets.json", targets)
    atomic_json(sidecar / "scan.json", analysis)
    unresolved_lines = [
        f"- `{item['file']}` — `{item['symbol']}`: {item['reason']}" for item in unexplained
    ]
    atomic_text(
        sidecar / "unexplained.txt",
        "\n".join(unresolved_lines) + ("\n" if unresolved_lines else ""),
    )
    atomic_text(sidecar / "surprises.txt", "")
    contracts = []
    for fact in selected:
        contracts.append(
            f"### `{fact['symbol']}`\n\n"
            f"- Kind: `{fact['kind']}`\n"
            f"- Source: `{fact['file']}`\n"
            "- Invariant: lexical declaration; behavior remains unexplained.\n"
            "- Evidence: exact source span and spelling hash in `targets.json`."
        )
    markdown = (
        f"# Explanation — {args.target}\n\n"
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Status | {snapshot['status']} |\n"
        f"| Public symbols | {len(facts)} |\n"
        f"| Annotated this run | {len(selected)} |\n"
        f"| Overflow | {len(overflow)} |\n\n"
        "## Summary\n\nDirect public Rust declarations for the locked/offline Cargo snapshot. "
        "This is lexical explanation evidence, not resolved behavior.\n\n"
        "## Public contracts\n\n"
        + ("\n\n".join(contracts) if contracts else "No complete public declaration inventory.")
    )
    if unresolved_lines:
        markdown += "\n\n## Unexplained regions\n\n" + "\n".join(unresolved_lines)
    atomic_text(output, markdown + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
