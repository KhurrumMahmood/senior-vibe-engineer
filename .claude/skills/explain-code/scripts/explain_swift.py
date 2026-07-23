#!/usr/bin/env python3
"""Render bounded Swift direct declarations into explanation artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_swift-project-lexical"
sys.path.insert(0, str(COMMON))

from swift_project_facts import (  # noqa: E402
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
    validate_artifacts,
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
    sidecar = output.with_suffix("")
    annotations = sidecar / "annotations"
    artifacts = [
        output,
        sidecar / "targets.json",
        sidecar / "scan.json",
        sidecar / "unexplained.txt",
        sidecar / "surprises.txt",
    ]
    try:
        validate_artifacts(root, artifacts)
    except ValueError as exc:
        parser.error(str(exc))
    clear_artifacts(artifacts)
    if annotations.is_dir():
        for old in annotations.glob("*.md"):
            old.unlink()

    snapshot = collect_snapshot(
        root,
        [args.target],
        swift=args.swift,
        swiftc=args.swiftc,
        swift_format=args.swift_format,
        check_product=args.check_product,
        expected_check=args.expected_check,
        smoke_product=args.smoke_product,
        expected_smoke=args.expected_smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    snapshot["host_state_preserved"] = snapshot["source_preserved"]
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    facts: list[dict] = []
    unexplained: list[dict] = []
    if snapshot["status"] == "complete":
        for row in snapshot["inventory"]:
            if row["role"] != "eligible":
                continue
            facts.extend(declaration_facts(row))
            source = row["_source"].decode("utf-8")
            for match in re.finditer(r"(?m)^\s*(?:public\s+)?extension\s+([^\s:{]+)", source):
                unexplained.append(
                    {
                        "file": row["file"],
                        "symbol": match.group(1),
                        "reason": "extension members require resolved type identity and remain unexplained",
                    }
                )
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
            "- Contract: direct compiler-validated lexical declaration with an exact span.\n"
            "- Preconditions: unresolved without project semantic and caller evidence.\n"
            "- Postconditions: unresolved without project semantic and caller evidence.\n"
            "- Invariants: declaration spelling only; runtime behavior remains unexplained.\n"
            "- Unexplained regions: bodies, overloads, extensions, types, callers, and dispatch.\n",
        )
    analysis = public_snapshot(snapshot)
    targets = {
        "schema_version": 1,
        "target": args.target,
        "language": "swift",
        "status": snapshot["status"],
        "analysis": {"swift": analysis},
        "files": [row["file"] for row in snapshot["inventory"] if row["role"] == "eligible"],
        "public_symbol_count": len(facts),
        "selected": selected,
        "overflow": overflow,
        "unexplained": unexplained,
    }
    atomic_json(sidecar / "targets.json", targets)
    atomic_json(sidecar / "scan.json", analysis)
    unresolved = [
        f"- `{item['file']}` — `{item['symbol']}`: {item['reason']}" for item in unexplained
    ]
    atomic_text(sidecar / "unexplained.txt", "\n".join(unresolved) + ("\n" if unresolved else ""))
    atomic_text(sidecar / "surprises.txt", "")
    contracts = [
        f"### `{fact['symbol']}`\n\n"
        f"- Kind: `{fact['kind']}`\n"
        f"- Source: `{fact['file']}`\n"
        "- Invariant: compiler-validated lexical declaration; behavior remains unexplained.\n"
        "- Evidence: exact source span and spelling hash in `targets.json`."
        for fact in selected
    ]
    markdown = (
        f"# Explanation — {args.target}\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        "## Summary\n\n"
        "Direct public Swift declarations from a complete dependency-free SwiftPM build. "
        "These source-file facts do not resolve symbol identity or runtime behavior.\n\n"
        "## Public contracts\n\n"
        + ("\n\n".join(contracts) if contracts else "No complete public declaration inventory.")
    )
    if unresolved:
        markdown += "\n\n## Unexplained regions\n\n" + "\n".join(unresolved)
    atomic_text(output, markdown + "\n")
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
