#!/usr/bin/env python3
"""Produce a Dart host adapter from the copied D1 project snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "_dart"
sys.path.insert(0, str(COMMON))

from dart_project_snapshot import (  # noqa: E402
    FORMAT_ROOTS,
    add_snapshot_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    collect_snapshot,
    public_snapshot,
    terminal_return_code,
    validate_artifact_paths,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    add_snapshot_arguments(parser)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    raw_artifacts = [
        args.output_dir / "adapter.yml",
        args.output_dir / "adapter.json",
        args.output_dir / "report.md",
        args.output_dir / "evidence.json",
    ]
    try:
        artifacts = validate_artifact_paths(root, raw_artifacts)
    except ValueError as exc:
        print(f"discover-dart: status=failed: {exc}", file=sys.stderr)
        return 2
    clear_artifacts(artifacts)
    snapshot = collect_snapshot(
        root,
        ["lib"],
        dart=args.dart,
        direct_test=args.direct_test,
        smoke_entrypoint=args.smoke_entrypoint,
        expected_smoke=args.expected_smoke,
    )
    analysis = public_snapshot(snapshot)
    authored = [row for row in snapshot["inventory"] if row["role"] == "library"]
    role_counts = Counter(
        row.get("reason", row["role"]) for row in snapshot["inventory"]
    )
    format_roots = [name for name in FORMAT_ROOTS if (root / name).is_dir()]
    adapter = {
        "schema_version": 1,
        "status": snapshot["status"],
        "analysis": {"dart": analysis},
        "project": {
            "name": root.name,
            "root": str(root),
            "markers": ["pubspec.yaml"] if (root / "pubspec.yaml").is_file() else [],
        },
        "stack": {
            "languages": ["dart"] if snapshot["inventory"] else [],
            "frameworks": [],
            "package_managers": ["pub"] if (root / "pubspec.yaml").is_file() else [],
        },
        "commands": {
            "check": ["dart analyze --fatal-infos --fatal-warnings ."],
            "format": [
                "dart format --output=none --set-exit-if-changed " + " ".join(format_roots)
            ],
            "test": [f"dart {args.direct_test}"],
            "smoke": [f"dart {args.smoke_entrypoint}"],
        },
        "source_roots": [
            {
                "path": "lib",
                "dart_files": len(authored),
                "source_languages": ["dart"] if authored else [],
            }
        ],
        "source_roles": dict(sorted(role_counts.items())),
        "standardization": {
            "cautions": []
            if snapshot["status"] == "complete"
            else ["Dart project facts are incomplete; do not standardize this layout."],
            "observed_layout_is_not_architecture_endorsement": True,
        },
        "open_questions": [
            "Which observed Dart layout choices are intentional project conventions?"
        ],
        "limitations": [
            "Observed filesystem layout only; no architecture endorsement, semantic graph, package graph, or framework inference."
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    outcome = "complete-objective-facts" if snapshot["status"] == "complete" else "incomplete"
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — Dart\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        f"**Outcome:** `{outcome}`\n\n"
        f"Authored Dart library files: {len(authored)}. "
        "The observed layout is not an architecture endorsement or framework inference.\n",
    )
    atomic_json(
        artifacts[3],
        {
            "skill": "adapt-project",
            "status": snapshot["status"],
            "evidence": {"adapter": "adapter.yml", "report": "report.md"},
        },
    )
    print(args.output_dir)
    return terminal_return_code(snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
