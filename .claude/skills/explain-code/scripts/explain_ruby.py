#!/usr/bin/env python3
"""Render bounded Ruby direct-declaration explanations and sidecars."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROVIDER = Path(__file__).resolve().parents[2] / "_ruby-project-lexical"
sys.path.insert(0, str(PROVIDER))

from ruby_project_lexical_facts import (  # noqa: E402
    add_snapshot_arguments,
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
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", fact["symbol"]).strip("-") or "symbol"
    return f"{safe}-{hash_bytes(raw)[:12]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    add_snapshot_arguments(parser)
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
        ruby=args.ruby,
        bundler=args.bundler,
        test=args.test,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    facts: list[dict] = []
    if snapshot["status"] != "failed":
        for row in snapshot["inventory"]:
            if row["role"] == "eligible":
                facts.extend(declaration_facts(row))
    facts.sort(key=lambda fact: (fact["file"], fact["span"]["start_byte"], fact["symbol"]))
    for fact in facts:
        fact["symbol_key"] = _key(fact)
    selected, overflow = facts[:20], facts[20:]
    annotations.mkdir(parents=True, exist_ok=True)
    for fact in selected:
        atomic_text(
            annotations / f"{fact['symbol_key']}.md",
            f"# `{fact['symbol']}`\n\n"
            f"- Kind: `{fact['kind']}`\n"
            f"- Source: `{fact['file']}`\n"
            "- Contract: direct Prism syntax with an exact source span.\n"
            "- Visibility: runtime unresolved.\n"
            "- Preconditions and postconditions: unexplained without runtime/caller evidence.\n"
            "- Unexplained: dynamic loading, reopening, metaprogramming, reflection, callbacks, Rails, and Zeitwerk.\n",
        )
    analysis = public_snapshot(snapshot)
    unresolved = [
        {
            "file": item["file"],
            "kind": item["kind"],
            "operation": item["operation"],
            "reason": "runtime identity/effect remains unresolved",
        }
        for item in snapshot.get("dynamic_signals", [])
    ]
    targets = {
        "schema_version": 1,
        "target": args.target,
        "language": "ruby",
        "status": snapshot["status"],
        "analysis": {"ruby": analysis},
        "files": [row["file"] for row in snapshot["inventory"] if row["role"] == "eligible"],
        "direct_declaration_count": len(facts),
        "selected": selected,
        "overflow": overflow,
        "unexplained": unresolved,
    }
    atomic_json(sidecar / "targets.json", targets)
    atomic_json(sidecar / "scan.json", analysis)
    unresolved_lines = [
        f"- `{item['file']}` — `{item['operation']}`: {item['reason']}" for item in unresolved
    ]
    atomic_text(
        sidecar / "unexplained.txt",
        "\n".join(unresolved_lines) + ("\n" if unresolved_lines else ""),
    )
    atomic_text(sidecar / "surprises.txt", "")
    contracts = [
        f"### `{fact['symbol']}`\n\n"
        f"- Kind: `{fact['kind']}`\n"
        f"- Source: `{fact['file']}`\n"
        "- Invariant: direct syntax only; runtime identity and behavior remain unexplained.\n"
        "- Evidence: exact source span and spelling hash in `targets.json`."
        for fact in selected
    ]
    markdown = (
        f"# Explanation — {args.target}\n\n"
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Status | {snapshot['status']} |\n"
        f"| Direct declarations | {len(facts)} |\n"
        f"| Annotated this run | {len(selected)} |\n"
        f"| Overflow | {len(overflow)} |\n\n"
        "## Summary\n\nDirect Ruby declarations from a frozen plain-gem snapshot. "
        "This is Prism syntax evidence, not runtime identity, reachability, visibility, or behavior.\n\n"
        "## Direct contracts\n\n"
        + ("\n\n".join(contracts) if contracts else "No complete direct declaration inventory.")
    )
    if unresolved_lines:
        markdown += "\n\n## Unexplained regions\n\n" + "\n".join(unresolved_lines)
    atomic_text(output, markdown + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
