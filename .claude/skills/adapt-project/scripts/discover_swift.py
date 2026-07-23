#!/usr/bin/env python3
"""Produce a bounded SwiftPM adapter from copied Swift project facts."""

from __future__ import annotations

import argparse
import json
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
    native_command_templates,
    public_snapshot,
    sources_preserved,
    terminal_return_code,
    validate_artifacts,
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
    artifacts = [
        output / "adapter.yml",
        output / "adapter.json",
        output / "report.md",
        output / "evidence.json",
    ]
    try:
        validate_artifacts(root, artifacts)
    except ValueError as exc:
        parser.error(str(exc))
    clear_artifacts(artifacts)
    snapshot = collect_snapshot(
        root,
        args.targets or ["."],
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
    authored = [row for row in snapshot["inventory"] if row["role"] == "eligible"]
    analysis = public_snapshot(snapshot)
    adapter = {
        "schema_version": 1,
        "status": snapshot["status"],
        "analysis": {"swift": analysis},
        "project": {
            "name": snapshot.get("project", {}).get("name", root.name),
            "root": str(root),
            "markers": ["Package.swift"] if (root / "Package.swift").is_file() else [],
            "units": snapshot.get("project", {}).get("targets", []),
        },
        "stack": {
            "languages": ["swift"] if snapshot["inventory"] else [],
            "frameworks": [],
            "package_managers": ["swiftpm"] if (root / "Package.swift").is_file() else [],
        },
        "commands": native_command_templates(args.check_product, args.smoke_product),
        "native_test_boundary": snapshot["native_test_boundary"],
        "source_roots": [
            {
                "path": "Sources",
                "swift_files": len(authored),
                "source_languages": ["swift"] if authored else [],
            }
        ],
        "standardization": {
            "cautions": [
                "Observed SwiftPM layout is objective evidence, not proof of a healthy standard."
            ]
        },
        "open_questions": [
            "Which observed SwiftPM patterns are healthy enough to teach future agents?"
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    outcome = "complete" if snapshot["status"] == "complete" else "incomplete"
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — Swift\n\n"
        f"**Status:** `{snapshot['status']}`\n\n"
        f"**Outcome:** `{outcome}`\n\n"
        f"Authored SwiftPM source files: {len(authored)}. "
        "The observed layout is objective evidence, not an endorsed standard.\n",
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
