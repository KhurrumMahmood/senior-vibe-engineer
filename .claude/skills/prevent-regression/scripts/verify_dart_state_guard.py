#!/usr/bin/env python3
"""Prove a staged Dart exact-field guard in disposable good and bad trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


class DartGuardVerifyError(ValueError):
    """Malformed stage, unsupported SDK, or unproved native guard."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _snapshot(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = _sha256(path)
    return rows


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DartGuardVerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DartGuardVerifyError(f"{label} must be a JSON object")
    return payload


def _load_stage(root: Path, supplied: Path) -> tuple[Path, dict[str, Any], Path, Path]:
    raw = supplied if supplied.is_absolute() else root / supplied
    if raw.is_symlink():
        raise DartGuardVerifyError("stage must not be a symbolic link")
    stage = Path(os.path.realpath(raw.resolve(strict=False)))
    allowed = root / "reports" / "prevent-regression"
    if not stage.is_dir() or stage == allowed or not _inside(allowed, stage):
        raise DartGuardVerifyError("stage must be a directory beneath reports/prevent-regression/")
    metadata = _json(stage / "authority.json", "staged Dart guard authority")
    if (
        metadata.get("schema_version") != "dart-state-guard-v1"
        or metadata.get("language") != "dart"
        or metadata.get("status") != "staged"
        or metadata.get("outcome") != "exact_native_guard"
    ):
        raise DartGuardVerifyError("staged Dart guard authority is malformed")
    tool = stage / "staged" / metadata.get("tool_destination", "")
    test = stage / "staged" / metadata.get("test_destination", "")
    if (
        not tool.is_file()
        or tool.is_symlink()
        or not test.is_file()
        or test.is_symlink()
        or metadata.get("tool_sha256") != _sha256(tool)
        or metadata.get("test_sha256") != _sha256(test)
    ):
        raise DartGuardVerifyError("staged Dart guard files are missing or stale")
    authority = metadata.get("authority")
    if not isinstance(authority, dict):
        raise DartGuardVerifyError("staged exact authority is missing")
    source = root / authority.get("declaration_file", "")
    if (
        not source.is_file()
        or source.is_symlink()
        or authority.get("source_sha256") != _sha256(source)
    ):
        raise DartGuardVerifyError("staged exact authority source is stale")
    return stage, metadata, tool, test


def _probe(dart: Path) -> dict[str, str]:
    executable = dart.resolve() if dart.is_file() else Path(shutil.which(str(dart)) or "")
    if not executable.is_file():
        raise DartGuardVerifyError("Dart SDK is unavailable")
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise DartGuardVerifyError("Dart SDK version probe timed out") from exc
    rendered = (result.stdout + result.stderr).strip()
    match = re.search(r"Dart SDK version:\s+(\d+)\.(\d+)\.(\d+)", rendered)
    if result.returncode or match is None or (int(match.group(1)), int(match.group(2))) != (3, 12):
        raise DartGuardVerifyError("Dart SDK >=3.12.0 <3.13.0 is required")
    return {"path": str(executable), "version": rendered}


def _copy_host(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", "reports"),
        symlinks=True,
    )


def _run(argv: list[str], cwd: Path, *, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DartGuardVerifyError(f"native command timed out: {' '.join(argv)}") from exc
    return {
        "command": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _native(
    root: Path,
    dart: str,
    *,
    include_guard: bool,
    tool_destination: str | None = None,
    test_destination: str | None = None,
) -> dict[str, dict[str, Any]]:
    roots = [name for name in ("lib", "bin", "tool", "test") if (root / name).is_dir()]
    commands: dict[str, list[str]] = {
        "analyze": [dart, "analyze", "--fatal-infos", "--fatal-warnings", "."],
        "format": [dart, "format", "--output=none", "--set-exit-if-changed", *roots],
        "direct_test": [dart, "test/native_test.dart"],
        "smoke": [dart, "bin/smoke.dart"],
    }
    if (root / "test/dart_d6_enum_values.dart").is_file():
        commands["enum_value_test"] = [dart, "test/dart_d6_enum_values.dart"]
    if include_guard:
        if not tool_destination or not test_destination:
            raise DartGuardVerifyError("guard destinations are missing")
        commands["direct_guard"] = [dart, tool_destination]
        commands["guard_test"] = [dart, test_destination]
    return {name: _run(argv, root) for name, argv in commands.items()}


def _assert_native(results: dict[str, dict[str, Any]], expected: dict[str, str]) -> None:
    failed = [name for name, row in results.items() if row["returncode"] != 0]
    if failed:
        raise DartGuardVerifyError(f"native verification failed: {failed[0]}")
    for name, stdout in expected.items():
        if name in results and results[name]["stdout"].strip() != stdout:
            raise DartGuardVerifyError(f"native stdout mismatch: {name}")


def _install(root: Path, relative: str, source: Path) -> Path:
    path = Path(relative)
    destination = (root / path).resolve(strict=False)
    if path.is_absolute() or ".." in path.parts or not _inside(root.resolve(), destination):
        raise DartGuardVerifyError("staged guard destination escapes disposable tree")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _seed_regression(root: Path, metadata: dict[str, Any]) -> None:
    edits = metadata.get("regression_revert_edits")
    if not isinstance(edits, list) or not edits:
        raise DartGuardVerifyError("staged regression plan is missing")
    field_reverted = False
    for edit in edits:
        if not isinstance(edit, dict):
            raise DartGuardVerifyError("staged regression plan is malformed")
        relative = Path(edit.get("file", ""))
        path = (root / relative).resolve(strict=False)
        old, new = edit.get("old"), edit.get("new")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not _inside(root.resolve(), path)
            or not path.is_file()
            or not isinstance(old, str)
            or not isinstance(new, str)
        ):
            raise DartGuardVerifyError("staged regression edit is unsafe")
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise DartGuardVerifyError("staged regression edit is stale or ambiguous")
        path.write_text(text.replace(old, new), encoding="utf-8")
        if metadata["authority"]["expected_type"] in old and "String" in new:
            field_reverted = True
    if not field_reverted:
        raise DartGuardVerifyError("regression plan did not revert the exact field to String")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--dart", type=Path, default=Path("dart"))
    args = parser.parse_args(argv)
    stage: Path | None = None
    before: dict[str, str] = {}
    try:
        root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
        if not root.is_dir() or args.project_root.is_symlink():
            raise DartGuardVerifyError("project root is unavailable")
        before = _snapshot(root)
        stage, metadata, staged_tool, staged_test = _load_stage(root, args.stage)
        tool = _probe(args.dart)
        dart = tool["path"]
        with tempfile.TemporaryDirectory(prefix="dart-d6-guard-") as temporary:
            base = Path(temporary)
            good, bad = base / "good", base / "bad"
            _copy_host(root, good)
            _copy_host(root, bad)
            _install(good, metadata["tool_destination"], staged_tool)
            _install(good, metadata["test_destination"], staged_test)
            good_native = _native(
                good,
                dart,
                include_guard=True,
                tool_destination=metadata["tool_destination"],
                test_destination=metadata["test_destination"],
            )
            _assert_native(
                good_native,
                {
                    "smoke": "42",
                    "direct_guard": metadata["guard"]["expected_stdout"],
                },
            )

            _seed_regression(bad, metadata)
            bad_without = _native(bad, dart, include_guard=False)
            _assert_native(bad_without, {"smoke": "42"})
            installed_bad_tool = _install(
                bad, metadata["tool_destination"], staged_tool
            )
            _install(bad, metadata["test_destination"], staged_test)
            bad_with = _run([dart, metadata["tool_destination"]], bad)
            rendered = bad_with["stdout"] + bad_with["stderr"]
            caught = (
                bad_with["returncode"] != 0
                and installed_bad_tool.name in rendered
                and metadata["authority"]["expected_type"] in rendered
                and "String" in rendered
            )
            if not caught:
                raise DartGuardVerifyError(
                    "staged guard did not specifically catch the buildable String-field regression"
                )
            after = _snapshot(root)
            writes = sorted(
                path
                for path in set(before) | set(after)
                if before.get(path) != after.get(path)
            )
            report = {
                "schema_version": "dart-state-guard-verification-v1",
                "language": "dart",
                "status": "complete",
                "outcome": "guard_proved",
                "tool": tool,
                "good_native": good_native,
                "seeded_regression": {
                    "kind": "accepted enum representation reverted to a buildable String field and former literals",
                    "without_guard": bad_without,
                    "with_guard": bad_with,
                    "caught_by_guard": caught,
                },
                "native_values": metadata["native_values"],
                "source_preserved": before == after,
                "audited_host_writes": writes,
                "installed_in_audited_host": False,
                "limitations": [
                    "exact reviewed field only",
                    "not a universal lint or serialization/runtime invariant",
                    "no Flutter state-management claim",
                ],
            }
        if not report["source_preserved"] or report["audited_host_writes"]:
            raise DartGuardVerifyError("native verification mutated audited host source")
        _atomic_json(stage / "verification.json", report)
    except (
        DartGuardVerifyError,
        FileNotFoundError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        if stage is not None:
            _atomic_json(
                stage / "verification.json",
                {
                    "schema_version": "dart-state-guard-verification-v1",
                    "language": "dart",
                    "status": "failed",
                    "outcome": "unproved",
                    "failure_kind": "native_guard_unproved",
                    "failure_detail": str(exc),
                    "source_preserved": _snapshot(root) == before,
                },
            )
        print(f"[verify_dart_state_guard] failed: {exc}", file=sys.stderr)
        return 2
    print("[verify_dart_state_guard] complete/guard_proved", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
