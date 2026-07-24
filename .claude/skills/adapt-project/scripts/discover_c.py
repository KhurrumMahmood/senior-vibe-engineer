#!/usr/bin/env python3
"""Produce a bounded C17 host adapter from copied project/lexical facts."""

from __future__ import annotations

import argparse
import json
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
    public_snapshot,
    sources_preserved,
    terminal_return_code,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("targets", nargs="*", default=["."])
    add_snapshot_arguments(parser)
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
        clang=args.clang,
        make=args.make,
        test_target=args.test_target,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    authored = (
        [
            row
            for row in snapshot["inventory"]
            if row["role"] == "eligible" and row["_path"].suffix.casefold() in {".c", ".i"}
        ]
        if snapshot["status"] != "failed"
        else []
    )
    owned_headers = (
        [
            row
            for row in snapshot["inventory"]
            if row["role"] == "eligible" and row["_path"].suffix.casefold() in {".h", ".inc"}
        ]
        if snapshot["status"] != "failed"
        else []
    )
    adapter = {
        "schema_version": 1,
        "status": snapshot["status"],
        "analysis": {"c": public_snapshot(snapshot)},
        "project": {"name": root.name, "root": str(root)},
        "stack": {
            "languages": ["c"] if snapshot["inventory"] else [],
            "frameworks": [],
            "package_managers": [],
            "build_systems": ["make"] if (root / "Makefile").is_file() else [],
        },
        "commands": {
            "compile_database": ["make compile-db CC=clang"],
            "check": ["clang <recorded C17 flags> -fsyntax-only <translation-unit>"],
            "test": [f"make {args.test_target} CC=clang"],
            "smoke": [args.smoke or "native smoke not supplied"],
        },
        "source_roots": [
            {
                "path": ".",
                "c_translation_units": len(authored),
                "compiler_owned_headers": len(owned_headers),
                "source_languages": ["c"] if authored else [],
            }
        ],
        "standardization": {
            "cautions": [
                "Observed Make/C17 facts do not endorse a framework, layout, architecture, or build variant."
            ]
        },
        "open_questions": [
            "Which observed build variants and layout conventions are intentionally project-owned?"
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — C17\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        f"Authored translation units: {len(authored)}; compiler-owned headers: {len(owned_headers)}. "
        "These are direct compile-database and lexical facts, not framework or layout endorsement.\n",
    )
    atomic_json(
        artifacts[3],
        {
            "skill": "adapt-project",
            "status": snapshot["status"],
            "evidence": {"adapter": "adapter.yml", "report": "report.md"},
        },
    )
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
