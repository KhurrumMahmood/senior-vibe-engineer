#!/usr/bin/env python3
"""Produce a Ruby host adapter from the copied project/lexical closure."""

from __future__ import annotations

import argparse
import json
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
        ruby=args.ruby,
        bundler=args.bundler,
        test=args.test,
        smoke=args.smoke,
    )
    snapshot["source_preserved"] = sources_preserved(snapshot)
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    analysis = public_snapshot(snapshot)
    authored = (
        [row for row in snapshot["inventory"] if row["role"] == "eligible"]
        if snapshot["status"] != "failed"
        else []
    )
    package_managers = ["bundler"] if (root / "Gemfile").is_file() else []
    adapter = {
        "schema_version": 1,
        "status": snapshot["status"],
        "analysis": {"ruby": analysis},
        "project": {"name": root.name, "root": str(root)},
        "stack": {
            "languages": ["ruby"] if snapshot["inventory"] else [],
            "frameworks": [],
            "package_managers": package_managers,
        },
        "commands": {
            "test": [
                f"ruby --disable-gems -Ilib {args.test}" if args.test else "native test not supplied"
            ],
            "check": ["ruby --disable-gems -c <each selected file>", "bundle check"],
            "smoke": [
                f"ruby --disable-gems -Ilib {args.smoke}" if args.smoke else "smoke not supplied"
            ],
        },
        "source_roots": [
            {
                "path": ".",
                "ruby_files": len(authored),
                "source_languages": ["ruby"] if authored else [],
            }
        ],
        "standardization": {
            "cautions": [
                "Observed plain-Ruby/gem layout is objective evidence, not a Rails, Zeitwerk, or architecture endorsement."
            ]
        },
        "open_questions": [
            "Which observed Ruby conventions are runtime-owned, framework-owned, or safe to teach future agents?"
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    outcome = "complete" if snapshot["status"] == "complete" else "incomplete"
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — Ruby\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        f"**Outcome:** `{outcome}`\n\n"
        f"Authored Ruby files: {len(authored)}. Facts are Prism/syntax bounded, "
        "Bundler-frozen, source-preserving, and not runtime semantics.\n",
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
