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
PYTHON_ARGV_TOKEN = "{python-interpreter}"
FIXTURE_ROOT = "tests/fixtures/wp3/extract-enum"
FIXED_SCOPE_CLOCK = "2000-01-01T00:00:00+00:00"
EVIDENCE_REPORT_REL = (
    "reports/portable-skill-ecosystem-completion/WP3/slice-4-evidence.md"
)
MANIFEST_REL = (
    "reports/portable-skill-ecosystem-completion/WP3/"
    "slice-4-repair-command-manifest.json"
)
CHECKSUM_REL = (
    "reports/portable-skill-ecosystem-completion/WP3/"
    "slice-4-repair-command-manifest.sha256"
)
EVIDENCE_PATHS = (EVIDENCE_REPORT_REL, MANIFEST_REL, CHECKSUM_REL)
EXPECTED_ARTIFACT_PATHS = {
    "binding-selection/evidence.json",
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
    "scripts/wp3_binding_selection_evidence.py",
    "tests/test_extract_enum_binding.py",
    "tests/test_artifact_scope_adoption.py",
    "tests/test_wp3_slice4_replay.py",
    "tests/fixtures/wp3/extract-enum/python/app.py",
    "tests/fixtures/wp3/extract-enum/django-options/app/models.py",
    "tests/fixtures/wp3/extract-enum/django-options/app/services.py",
]
PRINCIPAL_SOURCE_PATHS = [
    "scripts/_lib/binding_loader.py",
    ".claude/skills/extract-enum/SKILL.md",
    ".claude/skills/extract-enum/bindings/python.md",
    ".claude/skills/extract-enum/bindings/django.md",
    ".claude/skills/extract-enum/scripts/collect.py",
    ".claude/skills/extract-enum/scripts/propose.py",
    ".claude/skills/extract-enum/scripts/propose_python.py",
    "scripts/wp3_binding_selection_evidence.py",
    "scripts/wp3_slice4_replay.py",
    "tests/test_binding_loader.py",
    "tests/test_extract_enum_binding.py",
    "tests/test_wp3_slice4_replay.py",
    "tests/fixtures/wp3/extract-enum/ar7-semantic-oracle.json",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_python(value: str) -> str:
    path = Path(value).expanduser().absolute()
    if not path.is_file():
        raise ValueError(f"explicit Python interpreter is not a file: {path}")
    return str(path)


def _python_contract(python: str) -> dict[str, Any]:
    result = subprocess.run(
        [python, "--version"], capture_output=True, check=False
    )
    if result.returncode != 0:
        raise ValueError("explicit Python interpreter did not report its version")
    output = result.stdout + result.stderr
    return {
        "argv_token": PYTHON_ARGV_TOKEN,
        "version_output_sha256": _sha256(output),
    }


def _verification_commands(python: str) -> list[tuple[str, list[str]]]:
    # Disabling pytest's terminal plugin removes elapsed-time output while
    # preserving the exit-code contract, so exact output hashes are replayable.
    return [
        ("python-version", [python, "--version"]),
        ("pytest-version", [python, "-m", "pytest", "--version"]),
        ("ruff-version", [python, "-m", "ruff", "--version"]),
        (
            "focused-repair",
            [
                python,
                "-m",
                "pytest",
                "-p",
                "no:terminal",
                "tests/test_extract_enum_binding.py",
                "tests/test_artifact_scope_adoption.py",
                "tests/test_status.py",
                "tests/test_skill_detector_reads.py",
                "tests/test_wp3_slice4_replay.py",
            ],
        ),
        ("full-suite", [python, "-m", "pytest", "-p", "no:terminal"]),
        ("ruff-changed", [python, "-m", "ruff", "check", *RUFF_PATHS]),
        (
            "skill-meta",
            [python, "scripts/skill_meta.py", "lint", "--strict", "--quiet"],
        ),
        (
            "core-leakage",
            [python, "scripts/lint/no_core_framework_leakage.py", "--all"],
        ),
        (
            "artifact-drift",
            [
                python,
                ".claude/skills/find-skill-artifact-drift/scripts/detect.py",
                "--gate",
            ],
        ),
        (
            "spec-inventory",
            [
                python,
                "scripts/specs.py",
                "inventory-check",
                "portable-skill-layer-distribution",
            ],
        ),
    ]


def _replay_commands(
    output_root: Path, python: str
) -> list[tuple[str, list[str]]]:
    root = output_root.as_posix()
    collect = ".claude/skills/extract-enum/scripts/collect.py"
    return [
        (
            "binding-selection-evidence",
            [
                python,
                "scripts/wp3_binding_selection_evidence.py",
                "--output",
                f"{root}/binding-selection/evidence.json",
            ],
        ),
        ("python-fixture", [python, f"{FIXTURE_ROOT}/python/app.py"]),
        (
            "python-collect",
            [
                python,
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
                python,
                ".claude/skills/extract-enum/scripts/propose_python.py",
                "--targets",
                f"{root}/python/targets.json",
                "--output",
                f"{root}/python/job_status.py",
                "--semantic-output",
                f"{root}/python/semantic.json",
            ],
        ),
        ("python-render-exec", [python, f"{root}/python/job_status.py"]),
        (
            "django-collect",
            [
                python,
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
                python,
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
    output_root: Path, *, python: str, include_verification: bool
) -> list[tuple[str, list[str]]]:
    _normalize_python(python)
    verification = (
        _verification_commands(PYTHON_ARGV_TOKEN) if include_verification else []
    )
    return [*verification, *_replay_commands(output_root, PYTHON_ARGV_TOKEN)]


def _run(
    command_id: str,
    argv: list[str],
    *,
    python: str,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if not argv or argv[0] != PYTHON_ARGV_TOKEN:
        raise ValueError(f"replay command {command_id!r} lacks the Python argv token")
    executed_argv = [python, *argv[1:]]
    result = subprocess.run(
        executed_argv, cwd=repo_root, capture_output=True, check=False
    )
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


def _git(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise ValueError(f"Git validation failed for {' '.join(args)}: {detail.strip()}")
    return result.stdout


def _validate_git_binding(
    payload: dict[str, Any], *, repo_root: Path = REPO_ROOT
) -> None:
    reviewed_revision = payload.get("reviewed_revision")
    reviewed_tree = payload.get("reviewed_tree")
    if not isinstance(reviewed_revision, str) or not re.fullmatch(
        r"[0-9a-f]{40}", reviewed_revision
    ):
        raise ValueError("reviewed_revision must be a lowercase 40-character Git object ID")
    if not isinstance(reviewed_tree, str) or not re.fullmatch(
        r"[0-9a-f]{40}", reviewed_tree
    ):
        raise ValueError("reviewed_tree must be a lowercase 40-character Git object ID")
    if payload.get("allowed_evidence_paths") != list(EVIDENCE_PATHS):
        raise ValueError("manifest allowed evidence paths are not canonical")
    try:
        _git(repo_root, "cat-file", "-e", f"{reviewed_revision}^{{commit}}")
    except ValueError as exc:
        raise ValueError("reviewed revision does not exist as a Git commit") from exc
    actual_tree = _git(
        repo_root, "rev-parse", f"{reviewed_revision}^{{tree}}"
    ).decode("ascii").strip()
    if actual_tree != reviewed_tree:
        raise ValueError(
            f"reviewed tree does not match Git: expected {reviewed_tree}, got {actual_tree}"
        )
    head = _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", reviewed_revision, head],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError("reviewed revision is not an ancestor of the evidence state")
    allowed = set(EVIDENCE_PATHS)
    descendants = _git(
        repo_root, "rev-list", "--reverse", f"{reviewed_revision}..{head}"
    ).decode("ascii").split()
    for commit in descendants:
        parents = _git(repo_root, "rev-list", "--parents", "-n", "1", commit).decode(
            "ascii"
        ).split()
        if len(parents) != 2:
            raise ValueError("post-implementation evidence history must be linear")
        paths = set(
            _git(
                repo_root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                commit,
            )
            .decode("utf-8")
            .splitlines()
        )
        unexpected = sorted(paths - allowed)
        if unexpected:
            raise ValueError(
                "post-implementation non-evidence path changed in "
                f"{commit}: {unexpected}"
            )
    dirty_paths: set[str] = set()
    status = _git(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    ).decode("utf-8")
    for line in status.splitlines():
        value = line[3:]
        dirty_paths.update(value.split(" -> "))
    unexpected_dirty = sorted(dirty_paths - allowed)
    if unexpected_dirty:
        raise ValueError(
            f"non-evidence working-tree paths differ from reviewed state: {unexpected_dirty}"
        )


def _principal_sources(
    payload: dict[str, Any], *, repo_root: Path = REPO_ROOT
) -> list[dict[str, Any]]:
    revision = str(payload["reviewed_revision"])
    records = []
    for path in PRINCIPAL_SOURCE_PATHS:
        data = _git(repo_root, "show", f"{revision}:{path}")
        records.append({"path": path, "bytes": len(data), "sha256": _sha256(data)})
    return records


def _pytest_collected(python: str, *, repo_root: Path = REPO_ROOT) -> int:
    result = subprocess.run(
        [python, "-m", "pytest", "--collect-only", "-q"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"pytest collection failed: {result.stdout}{result.stderr}")
    matches = re.findall(r"(\d+) tests collected", result.stdout + result.stderr)
    if len(matches) != 1:
        raise ValueError("pytest collection output did not contain one exact test count")
    return int(matches[0])


def _report_path_record(path: Path, *, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _render_evidence_report(payload: dict[str, Any], *, output_root: Path) -> bytes:
    artifacts = payload["generated_replay_artifacts"]
    binding_path = output_root / "binding-selection" / "evidence.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    successful = binding["successful_selection"]["roots"][0]
    lines = [
        "# WP3 Slice 4 deterministic evidence",
        "",
        "This generated report supersedes every earlier Slice 4 evidence claim.",
        "Its hashes and counts are reconstructed and checked by `wp3_slice4_replay.py`.",
        "",
        "## Git and runtime binding",
        "",
        f"- Implementation revision: `{payload['reviewed_revision']}`",
        f"- Implementation tree: `{payload['reviewed_tree']}`",
        f"- Evidence relationship: only `{', '.join(EVIDENCE_PATHS)}` may change afterward.",
        f"- Python argv token: `{payload['python']['argv_token']}`",
        "- Python version-output SHA-256: "
        f"`{payload['python']['version_output_sha256']}`",
        f"- Collected tests: `{payload['verification']['pytest_collected']}`",
        "",
        "## Command evidence",
        "",
        "| Command | Exit | stdout+stderr SHA-256 |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| `{command['id']}` | {command['exit_code']} | "
        f"`{command['combined_stdout_then_stderr_sha256']}` |"
        for command in payload["commands"]
    )
    lines.extend(
        [
            "",
            "## Binding-selection evidence",
            "",
            f"- Profile SHA-256: `{binding['successful_selection']['profile_sha256']}`",
            f"- Core SHA-256: `{successful['core_sha256']}`",
            f"- Binding SHA-256 map: `{json.dumps(successful['binding_sha256'], sort_keys=True)}`",
            f"- Rendered SHA-256: `{successful['rendered_sha256']}`",
            "- Negative outcomes: `ambiguity`, `incompatibility`, and `zero_match` all rejected.",
            "- Cross-root binding leak: `false`.",
            f"- Order-independent: `{str(binding['order_independence']['equal']).lower()}`.",
            "",
            "## Replay artifacts",
            "",
            "| Path | Bytes | SHA-256 |",
            "|---|---:|---|",
        ]
    )
    lines.extend(
        f"| `{artifact['path']}` | {artifact['bytes']} | `{artifact['sha256']}` |"
        for artifact in artifacts
    )
    lines.extend(
        [
            "",
            "## Principal implementation sources",
            "",
            "| Path | Bytes | SHA-256 |",
            "|---|---:|---|",
        ]
    )
    lines.extend(
        f"| `{source['path']}` | {source['bytes']} | `{source['sha256']}` |"
        for source in payload["principal_sources"]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _checksum_path(manifest_path: Path) -> Path:
    return manifest_path.with_suffix(".sha256")


def _write_checksum(manifest_path: Path) -> None:
    data = manifest_path.read_bytes()
    _checksum_path(manifest_path).write_text(
        f"{_sha256(data)}  {manifest_path.name}\n", encoding="utf-8"
    )


def _verify_checksum(manifest_path: Path) -> None:
    expected = f"{_sha256(manifest_path.read_bytes())}  {manifest_path.name}\n"
    actual = _checksum_path(manifest_path).read_text(encoding="utf-8")
    if actual != expected:
        raise ValueError("manifest checksum sidecar does not match manifest bytes")


def record(
    output_root: Path,
    manifest_path: Path,
    *,
    reviewed_revision: str,
    reviewed_tree: str,
    include_verification: bool = True,
    python: str = sys.executable,
    evidence_report_path: Path | None = REPO_ROOT / EVIDENCE_REPORT_REL,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    selected_python = _normalize_python(python)
    canonical_manifest = manifest_path.resolve() == (repo_root / MANIFEST_REL).resolve()
    if canonical_manifest and not include_verification:
        raise ValueError("canonical Slice 4 evidence cannot use replay-only mode")
    if canonical_manifest and (
        evidence_report_path is None
        or evidence_report_path.resolve()
        != (repo_root / EVIDENCE_REPORT_REL).resolve()
    ):
        raise ValueError("canonical manifest requires the canonical evidence report")
    git_binding = {
        "reviewed_revision": reviewed_revision,
        "reviewed_tree": reviewed_tree,
        "allowed_evidence_paths": list(EVIDENCE_PATHS),
    }
    _validate_git_binding(git_binding, repo_root=repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    commands = [
        _run(
            command_id,
            argv,
            python=selected_python,
            repo_root=repo_root,
        )
        for command_id, argv in _commands(
            output_root,
            python=selected_python,
            include_verification=include_verification,
        )
    ]
    payload = {
        "schema_version": 1,
        "reviewed_revision": reviewed_revision,
        "reviewed_tree": reviewed_tree,
        "allowed_evidence_paths": list(EVIDENCE_PATHS),
        "python": _python_contract(selected_python),
        "artifact_root": output_root.as_posix(),
        "profile": (
            "full-verification-and-replay"
            if include_verification
            else "replay-only"
        ),
        "scope_written_at": FIXED_SCOPE_CLOCK,
        "commands": commands,
        "generated_replay_artifacts": _artifacts(output_root),
        "principal_sources": [],
        "verification": {
            "pytest_collected": _pytest_collected(
                selected_python, repo_root=repo_root
            )
        },
    }
    payload["principal_sources"] = _principal_sources(payload, repo_root=repo_root)
    if evidence_report_path is not None:
        report_bytes = _render_evidence_report(payload, output_root=output_root)
        evidence_report_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_report_path.write_bytes(report_bytes)
        payload["evidence_report"] = {
            "bytes": len(report_bytes),
            "path": _report_path_record(evidence_report_path, repo_root=repo_root),
            "sha256": _sha256(report_bytes),
        }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_checksum(manifest_path)
    return payload


def verify(
    manifest_path: Path,
    *,
    python: str = sys.executable,
    repo_root: Path = REPO_ROOT,
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected_python = _normalize_python(python)
    if payload.get("python") != _python_contract(selected_python):
        raise ValueError("manifest Python runtime contract does not match --python")
    _validate_git_binding(payload, repo_root=repo_root)
    _verify_checksum(manifest_path)
    output_root = Path(payload["artifact_root"])
    expected_commands = payload["commands"]
    profile = payload.get("profile")
    if profile not in {"full-verification-and-replay", "replay-only"}:
        raise ValueError("manifest has an unsupported replay profile")
    canonical_manifest = manifest_path.resolve() == (repo_root / MANIFEST_REL).resolve()
    if canonical_manifest and profile != "full-verification-and-replay":
        raise ValueError("canonical Slice 4 evidence requires full verification")
    canonical_commands = _commands(
        output_root,
        python=selected_python,
        include_verification=profile == "full-verification-and-replay",
    )
    actual_artifacts = _artifacts(output_root)
    if actual_artifacts != payload["generated_replay_artifacts"]:
        raise ValueError("artifact hashes differ before replay")
    if payload.get("principal_sources") != _principal_sources(
        payload, repo_root=repo_root
    ):
        raise ValueError("principal source hashes differ from the reviewed Git revision")
    if payload.get("verification", {}).get(
        "pytest_collected"
    ) != _pytest_collected(selected_python, repo_root=repo_root):
        raise ValueError("mechanically collected pytest count differs from manifest")
    report_record = payload.get("evidence_report")
    if profile == "full-verification-and-replay" and not isinstance(
        report_record, dict
    ):
        raise ValueError("full verification manifest requires an evidence report")
    if isinstance(report_record, dict):
        if canonical_manifest and report_record.get("path") != EVIDENCE_REPORT_REL:
            raise ValueError("canonical manifest names a non-canonical evidence report")
        report_path = Path(str(report_record.get("path")))
        if not report_path.is_absolute():
            report_path = repo_root / report_path
        report_bytes = report_path.read_bytes()
        expected_report = _render_evidence_report(payload, output_root=output_root)
        expected_record = {
            "bytes": len(expected_report),
            "path": _report_path_record(report_path, repo_root=repo_root),
            "sha256": _sha256(expected_report),
        }
        if report_record != expected_record or report_bytes != expected_report:
            raise ValueError("evidence report differs from mechanically rendered claims")
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
        _run(
            command_id,
            argv,
            python=selected_python,
            repo_root=repo_root,
        )
        for command_id, argv in canonical_commands
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
        "--python",
        default=sys.executable,
        help="Explicit Python interpreter recorded in every replay argv",
    )
    record_parser.add_argument(
        "--replay-only",
        action="store_true",
        help="Record only final pipeline replay commands (intended for narrow tests)",
    )
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True, type=Path)
    verify_parser.add_argument(
        "--python",
        default=sys.executable,
        help="Explicit Python interpreter required to match the manifest",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            record(
                args.output_root,
                args.manifest,
                reviewed_revision=args.reviewed_revision,
                reviewed_tree=args.reviewed_tree,
                include_verification=not args.replay_only,
                python=args.python,
            )
        else:
            verify(args.manifest, python=args.python)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"slice-4 replay {args.command}: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
