#!/usr/bin/env python3
"""Prove one staged C17 exact-field guard on disposable native project copies."""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _evidence() -> Any:
    path = Path(__file__).with_name("c_state_guard_evidence.py")
    spec = importlib.util.spec_from_file_location("c_state_guard_verify_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C guard evidence helper is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


E = _evidence()


def _run(command: list[str], root: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-6000:],
    }


def _executable(value: str, label: str) -> str:
    path = Path(value)
    selected = str(path.resolve()) if path.is_file() else shutil.which(value)
    if selected is None:
        raise E.EvidenceError("tool_missing", f"accepted native tool is missing: {label}")
    return selected


def _tools(clang_arg: str, make_arg: str, root: Path) -> dict[str, dict[str, str]]:
    clang = _executable(clang_arg, "clang")
    make = _executable(make_arg, "make")
    clang_probe = _run([clang, "--version"], root)
    match = re.search(
        r"(?:Apple\s+)?clang\s+version\s+(\d+)\.(\d+)(?:\.(\d+))?",
        clang_probe["stdout"] + clang_probe["stderr"],
        re.IGNORECASE,
    )
    if clang_probe["returncode"] or match is None:
        raise E.EvidenceError("tool_invalid", "cannot determine Clang version")
    version = tuple(int(part or 0) for part in match.groups())
    if version < (21, 0, 0):
        raise E.EvidenceError("tool_invalid", "Clang 21+ is required")
    make_probe = _run([make, "--version"], root)
    if make_probe["returncode"]:
        raise E.EvidenceError("tool_invalid", "cannot execute Make")
    return {
        "clang": {"path": clang, "version": ".".join(str(part) for part in version)},
        "make": {"path": make, "version": make_probe["stdout"].splitlines()[0]},
    }


def _stage(root: Path, supplied: str) -> tuple[Path, dict[str, Any], Path]:
    stage = E.artifact(root, supplied, "staged guard", "prevent-regression")
    metadata = E.load_json(stage / "authority.json", "staged C guard authority")
    guard = stage / "guard/exact_field_type_guard.c"
    if (
        metadata.get("schema_version") != "c-state-guard-v1"
        or metadata.get("language") != "c"
        or metadata.get("status") != "staged"
        or metadata.get("outcome") != "exact_field_type_guard"
        or metadata.get("installed") is not False
        or not guard.is_file()
        or guard.is_symlink()
        or E.sha256(guard) != metadata.get("guard_sha256")
    ):
        raise E.EvidenceError("stage_tampered", "staged C guard closure is invalid")
    return stage, metadata, guard


def _native(
    root: Path, metadata: dict[str, Any], tools: dict[str, dict[str, str]]
) -> dict[str, Any]:
    native = metadata["migration"]["native"]
    make = tools["make"]["path"]
    clang = tools["clang"]["path"]
    clean = _run([make, "clean"], root)
    if clean["returncode"]:
        raise E.EvidenceError("native_failed", "accepted Make clean failed")
    make_test = _run(
        [
            make,
            native["compile_database_target"],
            native["make_target"],
            f"CC={clang}",
        ],
        root,
    )
    if make_test["returncode"]:
        raise E.EvidenceError("native_failed", "accepted Make/C17 build or test failed")
    smoke_path = E.safe_path(root, native["smoke_path"], "accepted smoke executable")
    if not smoke_path.is_file():
        raise E.EvidenceError("native_failed", "accepted native smoke executable is missing")
    smoke = _run([str(smoke_path)], root)
    if smoke["returncode"] or smoke["stdout"] != native["smoke_stdout"]:
        raise E.EvidenceError("native_failed", "accepted native smoke output differs")
    return {"make_clean": clean, "make_test": make_test, "smoke": smoke}


def _compile_guard(
    root: Path,
    guard: Path,
    metadata: dict[str, Any],
    tools: dict[str, dict[str, str]],
) -> dict[str, Any]:
    flags = metadata["migration"]["native"]["guard_cflags"]
    return _run(
        [tools["clang"]["path"], *flags, "-fsyntax-only", str(guard)],
        root,
    )


def _copy_project(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".native-build", "reports", "reviews"),
    )


def _replace_once(root: Path, replacement: dict[str, str]) -> None:
    path = E.safe_path(root, replacement["path"], "seeded regression source")
    text = path.read_text(encoding="utf-8")
    if text.count(replacement["before"]) != 1:
        raise E.EvidenceError(
            "regression_unseedable", f"regression anchor differs: {replacement['path']}"
        )
    path.write_text(text.replace(replacement["before"], replacement["after"]), encoding="utf-8")


def _seed_regression(root: Path, metadata: dict[str, Any]) -> None:
    regression = metadata["migration"]["seeded_regression"]
    _replace_once(root, regression["field_replacement"])
    for replacement in regression["caller_replacements"]:
        _replace_once(root, replacement)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--make", default="make")
    args = parser.parse_args(argv)
    report: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or Path(args.project_root).is_symlink():
            raise E.EvidenceError("unsafe_path", "project root must be a non-symlink directory")
        stage, metadata, guard = _stage(root, args.stage)
        report = stage / "verification.json"
        report.unlink(missing_ok=True)
        E.validate_sources(
            root,
            metadata["migration"]["migrated_sources"],
            kind="migration_stale",
        )
        tools = _tools(args.clang, args.make, root)
        before = E.source_snapshot(root)
        clean_native = _native(root, metadata, tools)
        clean_guard = _compile_guard(root, guard, metadata, tools)
        if clean_guard["returncode"]:
            raise E.EvidenceError("guard_clean_failed", "guard rejects the accepted migrated tree")
        with tempfile.TemporaryDirectory() as temporary:
            regression_root = Path(temporary) / "host"
            _copy_project(root, regression_root)
            _seed_regression(regression_root, metadata)
            regression_native = _native(regression_root, metadata, tools)
            with_guard = _compile_guard(regression_root, guard, metadata, tools)
            message = (
                f"{metadata['authority']['owner']}.{metadata['authority']['field']} must remain "
                f"{metadata['migration']['enum_type']}"
            )
            caught = (
                with_guard["returncode"] != 0
                and message in with_guard["stderr"]
                and guard.name in with_guard["stderr"]
            )
            if not caught:
                raise E.EvidenceError(
                    "guard_did_not_fire",
                    "buildable const char * regression did not fail specifically at the staged guard",
                )
        preserved = E.source_snapshot(root) == before
        if not preserved:
            raise E.EvidenceError("source_mutated", "guard verification mutated host source")
        payload = {
            "schema_version": "c-state-guard-verification-v1",
            "language": "c",
            "status": "complete",
            "outcome": "guard_proved",
            "installed": False,
            "tools": tools,
            "clean_native": clean_native,
            "clean_guard": clean_guard,
            "seeded_regression": {
                "kind": "exact field and accepted callers reverted to the buildable const char * form",
                "without_guard": regression_native["make_test"],
                "without_guard_smoke": regression_native["smoke"],
                "with_guard": with_guard,
                "caught_by_guard": True,
            },
            "source_preserved": True,
            "nonclaims": metadata["nonclaims"],
        }
        E.atomic_json(report, payload)
    except (
        E.EvidenceError,
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        subprocess.TimeoutExpired,
    ) as error:
        kind = error.kind if isinstance(error, E.EvidenceError) else "verification_failed"
        if report is None:
            try:
                root = Path(args.project_root).resolve()
                report = E.artifact(
                    root, args.stage, "staged guard", "prevent-regression"
                ) / "verification.json"
            except (E.EvidenceError, OSError):
                report = None
        if report is not None:
            E.atomic_json(
                report,
                {
                    "schema_version": "c-state-guard-verification-v1",
                    "language": "c",
                    "status": "failed",
                    "outcome": "unproved",
                    "failure_kind": kind,
                    "message": str(error),
                },
            )
        print(f"[verify_c_state_guard] ERROR: {kind}: {error}", file=sys.stderr)
        return 2
    print("[verify_c_state_guard] exact Clang/C17 field guard proved", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
