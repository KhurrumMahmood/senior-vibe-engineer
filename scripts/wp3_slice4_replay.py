#!/usr/bin/env python3
"""Record or verify the deterministic WP3 Slice 4 executable replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = ".venv/bin/python"
FIXTURE_ROOT = "tests/fixtures/wp3/extract-enum"
FIXED_SCOPE_CLOCK = "2000-01-01T00:00:00+00:00"
EXPECTED_ARTIFACT_PATHS = {
    "django/normalization.json",
    "django/proposal.md",
    "django/scope.json",
    "django/semantic.json",
    "django/targets.json",
    "python/job_status.py",
    "python/scope.json",
    "python/semantic.json",
    "python/targets.json",
}
RUFF_PATHS = [
    ".claude/skills/extract-enum/scripts/collect.py",
    ".claude/skills/extract-enum/scripts/propose.py",
    ".claude/skills/extract-enum/scripts/propose_python.py",
    "scripts/_lib/artifact_scope.py",
    "scripts/wp3_slice4_replay.py",
    "tests/test_extract_enum_binding.py",
    "tests/test_artifact_scope_adoption.py",
    "tests/fixtures/wp3/extract-enum/python/app.py",
    "tests/fixtures/wp3/extract-enum/django-options/app/models.py",
    "tests/fixtures/wp3/extract-enum/django-options/app/services.py",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verification_commands() -> list[tuple[str, list[str]]]:
    # Disabling pytest's terminal plugin removes elapsed-time output while
    # preserving the exit-code contract, so exact output hashes are replayable.
    return [
        ("python-version", [PYTHON, "--version"]),
        ("pytest-version", [PYTHON, "-m", "pytest", "--version"]),
        ("ruff-version", [PYTHON, "-m", "ruff", "--version"]),
        (
            "focused-repair",
            [
                PYTHON,
                "-m",
                "pytest",
                "-p",
                "no:terminal",
                "tests/test_extract_enum_binding.py",
                "tests/test_artifact_scope_adoption.py",
                "tests/test_status.py",
                "tests/test_skill_detector_reads.py",
            ],
        ),
        ("full-suite", [PYTHON, "-m", "pytest", "-p", "no:terminal"]),
        ("ruff-changed", [PYTHON, "-m", "ruff", "check", *RUFF_PATHS]),
        (
            "skill-meta",
            [PYTHON, "scripts/skill_meta.py", "lint", "--strict", "--quiet"],
        ),
        (
            "core-leakage",
            [PYTHON, "scripts/lint/no_core_framework_leakage.py", "--all"],
        ),
        (
            "artifact-drift",
            [
                PYTHON,
                ".claude/skills/find-skill-artifact-drift/scripts/detect.py",
                "--gate",
            ],
        ),
        (
            "spec-inventory",
            [
                PYTHON,
                "scripts/specs.py",
                "inventory-check",
                "portable-skill-layer-distribution",
            ],
        ),
    ]


def _replay_commands(output_root: Path) -> list[tuple[str, list[str]]]:
    root = output_root.as_posix()
    collect = ".claude/skills/extract-enum/scripts/collect.py"
    return [
        ("python-fixture", [PYTHON, f"{FIXTURE_ROOT}/python/app.py"]),
        (
            "python-collect",
            [
                PYTHON,
                collect,
                "--target",
                "app.py::status::Job",
                "--project-root",
                f"{FIXTURE_ROOT}/python",
                "--output",
                f"{root}/python/targets.json",
                "--scope-written-at",
                FIXED_SCOPE_CLOCK,
            ],
        ),
        (
            "python-render",
            [
                PYTHON,
                ".claude/skills/extract-enum/scripts/propose_python.py",
                "--targets",
                f"{root}/python/targets.json",
                "--output",
                f"{root}/python/job_status.py",
                "--semantic-output",
                f"{root}/python/semantic.json",
            ],
        ),
        ("python-render-exec", [PYTHON, f"{root}/python/job_status.py"]),
        (
            "django-collect",
            [
                PYTHON,
                collect,
                "--target",
                "app/models.py::status::Job",
                "--project-root",
                f"{FIXTURE_ROOT}/django",
                "--output",
                f"{root}/django/targets.json",
                "--scope-written-at",
                FIXED_SCOPE_CLOCK,
            ],
        ),
        (
            "django-render-oracle",
            [
                PYTHON,
                ".claude/skills/extract-enum/scripts/propose.py",
                "--targets",
                f"{root}/django/targets.json",
                "--output",
                f"{root}/django/proposal.md",
                "--semantic-output",
                f"{root}/django/semantic.json",
                "--oracle",
                f"{FIXTURE_ROOT}/ar7-semantic-oracle.json",
                "--normalization-report",
                f"{root}/django/normalization.json",
            ],
        ),
    ]


def _commands(
    output_root: Path, *, include_verification: bool
) -> list[tuple[str, list[str]]]:
    verification = _verification_commands() if include_verification else []
    return [*verification, *_replay_commands(output_root)]


def _run(command_id: str, argv: list[str]) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise ValueError(f"replay command {command_id!r} failed: {detail}")
    return {
        "id": command_id,
        "argv": argv,
        "cwd": ".",
        "exit_code": result.returncode,
        "stdout": {"bytes": len(result.stdout), "sha256": _sha256(result.stdout)},
        "stderr": {"bytes": len(result.stderr), "sha256": _sha256(result.stderr)},
        "combined_stdout_then_stderr_sha256": _sha256(result.stdout + result.stderr),
    }


def _artifacts(output_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            records.append(
                {
                    "bytes": len(data),
                    "path": path.relative_to(output_root).as_posix(),
                    "sha256": _sha256(data),
                }
            )
    actual_paths = {record["path"] for record in records}
    if actual_paths != EXPECTED_ARTIFACT_PATHS:
        missing = sorted(EXPECTED_ARTIFACT_PATHS - actual_paths)
        unexpected = sorted(actual_paths - EXPECTED_ARTIFACT_PATHS)
        raise ValueError(
            "replay artifact set differs from the canonical set: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return records


def record(
    output_root: Path,
    manifest_path: Path,
    *,
    reviewed_revision: str,
    reviewed_tree: str,
    include_verification: bool = True,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", reviewed_revision):
        raise ValueError("reviewed_revision must be a lowercase 40-character Git object ID")
    if not re.fullmatch(r"[0-9a-f]{40}", reviewed_tree):
        raise ValueError("reviewed_tree must be a lowercase 40-character Git object ID")
    output_root.mkdir(parents=True, exist_ok=True)
    commands = [
        _run(command_id, argv)
        for command_id, argv in _commands(
            output_root, include_verification=include_verification
        )
    ]
    payload = {
        "schema_version": 1,
        "reviewed_revision": reviewed_revision,
        "reviewed_tree": reviewed_tree,
        "artifact_root": output_root.as_posix(),
        "profile": (
            "full-verification-and-replay"
            if include_verification
            else "replay-only"
        ),
        "scope_written_at": FIXED_SCOPE_CLOCK,
        "commands": commands,
        "generated_replay_artifacts": _artifacts(output_root),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def verify(manifest_path: Path) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_root = Path(payload["artifact_root"])
    expected_commands = payload["commands"]
    profile = payload.get("profile")
    if profile not in {"full-verification-and-replay", "replay-only"}:
        raise ValueError("manifest has an unsupported replay profile")
    canonical_commands = _commands(
        output_root,
        include_verification=profile == "full-verification-and-replay",
    )
    expected_invocations = [
        (recorded.get("id"), recorded.get("argv"), recorded.get("cwd"))
        for recorded in expected_commands
        if isinstance(recorded, dict)
    ]
    if expected_invocations != [
        (command_id, argv, ".") for command_id, argv in canonical_commands
    ]:
        raise ValueError("manifest command list is not the canonical Slice 4 replay")
    actual_commands = [
        _run(command_id, argv) for command_id, argv in canonical_commands
    ]
    if actual_commands != expected_commands:
        raise ValueError("replayed command exit/output hashes differ from manifest")
    actual_artifacts = _artifacts(output_root)
    if actual_artifacts != payload["generated_replay_artifacts"]:
        raise ValueError("replayed artifact hashes differ from manifest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--output-root", required=True, type=Path)
    record_parser.add_argument("--manifest", required=True, type=Path)
    record_parser.add_argument("--reviewed-revision", required=True)
    record_parser.add_argument("--reviewed-tree", required=True)
    record_parser.add_argument(
        "--replay-only",
        action="store_true",
        help="Record only final pipeline replay commands (intended for narrow tests)",
    )
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            record(
                args.output_root,
                args.manifest,
                reviewed_revision=args.reviewed_revision,
                reviewed_tree=args.reviewed_tree,
                include_verification=not args.replay_only,
            )
        else:
            verify(args.manifest)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"slice-4 replay {args.command}: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
