#!/usr/bin/env python3
"""Render bounded direct C17 declaration explanations and sidecars."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROVIDER = Path(__file__).resolve().parents[2] / "_c"
sys.path.insert(0, str(PROVIDER))

from c_lexical_facts import (  # noqa: E402
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    hash_bytes,
    lexical_facts,
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
        clang=args.clang,
        make=args.make,
        test_target=args.test_target,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    facts: list[dict] = []
    if snapshot["status"] != "failed":
        for row in snapshot["inventory"]:
            if row["role"] == "eligible" and row["selected"]:
                facts.extend(lexical_facts(row))
    facts.sort(key=lambda fact: (fact["file"], fact["span"]["start_byte"], fact["symbol"]))
    for fact in facts:
        fact.pop("normalized_body", None)
        fact.pop("normalized_body_sha256", None)
        fact["symbol_key"] = _key(fact)
    selected, overflow = facts[:20], facts[20:]
    annotations.mkdir(parents=True, exist_ok=True)
    for fact in selected:
        atomic_text(
            annotations / f"{fact['symbol_key']}.md",
            f"# `{fact['symbol']}`\n\n"
            f"- Kind: `{fact['kind']}`\n"
            f"- Source: `{fact['file']}`\n"
            "- Contract: direct C source spelling with an exact byte span.\n"
            f"- Linkage: `{fact['linkage']}`.\n"
            "- Behavior, callers, types after macros, and pre/postconditions remain unexplained.\n",
        )
    analysis = public_snapshot(snapshot)
    targets = {
        "schema_version": 1,
        "target": args.target,
        "language": "c",
        "status": snapshot["status"],
        "analysis": {"c": analysis},
        "files": [row["file"] for row in snapshot["inventory"] if row["role"] == "eligible" and row["selected"]],
        "direct_declaration_count": len(facts),
        "selected": selected,
        "overflow": overflow,
        "unexplained": [
            "macro expansion and inactive branches",
            "function-pointer targets and runtime behavior",
            "cross-variant linkage, ABI, and object layout",
        ],
    }
    atomic_json(sidecar / "targets.json", targets)
    atomic_json(sidecar / "scan.json", analysis)
    atomic_text(sidecar / "unexplained.txt", "\n".join(targets["unexplained"]) + "\n")
    atomic_text(sidecar / "surprises.txt", "")
    contracts = [
        f"### `{fact['symbol']}`\n\n"
        f"- Kind: `{fact['kind']}`\n"
        f"- Source: `{fact['file']}`\n"
        "- Invariant: direct lexical spelling only; runtime behavior remains unexplained.\n"
        "- Evidence: exact source span and spelling hash in `targets.json`."
        for fact in selected
    ]
    atomic_text(
        output,
        f"# Explanation — {args.target}\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        "Direct C17 declaration spelling follows. This is static/lexical evidence only, not "
        "macro-expanded identity, reachability, behavior, ABI, or a framework contract.\n\n"
        "## Direct contracts\n\n"
        + ("\n\n".join(contracts) if contracts else "No complete direct declaration inventory.")
        + "\n",
    )
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
