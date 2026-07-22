#!/usr/bin/env python3
"""Produce a Rust host adapter from the copied lexical/filesystem closure."""

from __future__ import annotations

import argparse
import json
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
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("targets", nargs="*", default=["."])
    add_tool_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        parser.error("--output-dir must be inside --project-root")
    artifacts = [
        output / "adapter.yml",
        output / "adapter.json",
        output / "report.md",
        output / "evidence.json",
    ]
    clear_artifacts(artifacts)
    snapshot = collect_snapshot(
        root,
        args.targets or ["."],
        rustc=args.rustc,
        cargo=args.cargo,
        rustfmt=args.rustfmt,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    analysis = public_snapshot(snapshot)
    authored = [row for row in snapshot["inventory"] if row["role"] == "eligible"]
    adapter = {
        "schema_version": 1,
        "status": snapshot["status"],
        "analysis": {"rust": analysis},
        "project": {"name": root.name, "root": str(root)},
        "stack": {
            "languages": ["rust"] if snapshot["inventory"] else [],
            "frameworks": [],
            "package_managers": ["cargo"] if (root / "Cargo.toml").is_file() else [],
        },
        "commands": {
            "test": ["cargo test --locked --offline --workspace --all-targets --all-features"],
            "check": ["cargo check --locked --offline --workspace --all-targets --all-features"],
            "format": ["cargo fmt --all -- --check"],
        },
        "source_roots": [
            {
                "path": ".",
                "rust_files": len(authored),
                "source_languages": ["rust"] if authored else [],
            }
        ],
        "standardization": {
            "cautions": [
                "Observed Cargo/Rust layout is objective evidence, not proof that it is a healthy standard."
            ]
        },
        "open_questions": [
            "Which observed Rust patterns are healthy enough to teach future agents?"
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    outcome = "complete" if snapshot["status"] == "complete" else "incomplete"
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — Rust\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        f"**Outcome:** `{outcome}`\n\n"
        f"Authored Rust files: {len(authored)}. Cargo facts are locked/offline and source-preserving.\n",
    )
    atomic_json(
        artifacts[3],
        {
            "skill": "adapt-project",
            "status": snapshot["status"],
            "evidence": {"adapter": "adapter.yml", "report": "report.md"},
        },
    )
    print(output)
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
