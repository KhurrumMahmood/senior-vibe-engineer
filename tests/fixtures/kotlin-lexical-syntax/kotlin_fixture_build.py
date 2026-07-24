#!/usr/bin/env python3
"""Build the dependency-free Kotlin/JVM lexical/syntax fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath


JVM_TARGET = "17"
TIMEOUT_SECONDS = 60


class FixtureError(ValueError):
    """The fixture manifest or requested native tool boundary is invalid."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise FixtureError(f"{label} path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FixtureError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise FixtureError(f"{label} path is not executable: {path}")
    return resolved


def _input(root: Path, raw: object, label: str) -> tuple[str, Path]:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise FixtureError(f"{label} must be a safe relative path")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".kt":
        raise FixtureError(f"{label} must be a contained lowercase .kt path")
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise FixtureError(f"{label} is unavailable or symbolic: {raw}")
    return raw, path


def _manifest(root: Path) -> dict[str, object]:
    try:
        payload = json.loads((root / "kotlin-project.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError("kotlin-project.json is unavailable or malformed") from exc
    keys = {
        "schema_version", "jvm_target", "sources", "tests", "test_main", "smoke_output"
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise FixtureError("kotlin-project.json has an unexpected shape")
    if payload["schema_version"] != 1 or payload["jvm_target"] != JVM_TARGET:
        raise FixtureError("kotlin-project.json requests an unsupported contract")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        raise FixtureError("kotlin-project.json must declare sources")
    if not isinstance(payload["tests"], list) or not payload["tests"]:
        raise FixtureError("kotlin-project.json must declare tests")
    combined = [*payload["sources"], *payload["tests"]]
    if len(combined) != len(set(combined)):
        raise FixtureError("kotlin-project.json contains duplicate inputs")
    if not isinstance(payload["test_main"], str) or not payload["test_main"]:
        raise FixtureError("kotlin-project.json must declare a test main class")
    if not isinstance(payload["smoke_output"], str):
        raise FixtureError("kotlin-project.json must declare smoke output")
    return payload


def _run(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=root, capture_output=True, text=True, check=False,
        shell=False, timeout=TIMEOUT_SECONDS,
    )


def build(project_root: Path, kotlinc_path: Path, java_path: Path) -> int:
    root = project_root.resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise FixtureError("project root must be a regular directory")
    kotlinc = _tool(kotlinc_path, "kotlinc")
    java = _tool(java_path, "java")
    manifest = _manifest(root)
    sources = [_input(root, raw, "source") for raw in manifest["sources"]]
    tests = [_input(root, raw, "test") for raw in manifest["tests"]]
    build_root = root / ".native-build"
    if build_root.exists():
        if build_root.is_symlink() or not build_root.is_dir():
            raise FixtureError(".native-build must be a regular directory")
        shutil.rmtree(build_root)
    build_root.mkdir()
    app_jar = build_root / "kotlin-app.jar"
    test_jar = build_root / "kotlin-tests.jar"
    common = [str(kotlinc), "-jvm-target", JVM_TARGET, "-Werror", "-include-runtime"]
    commands = {
        "compile": [*common, "-d", str(app_jar), *(str(path) for _, path in sources)],
        "compile-tests": [
            *common, "-d", str(test_jar),
            *(str(path) for _, path in sources), *(str(path) for _, path in tests),
        ],
        "test": [str(java), "-cp", str(test_jar), manifest["test_main"]],
        "smoke": [str(java), "-jar", str(app_jar)],
    }
    checks: dict[str, dict[str, object]] = {}
    for label in ("compile", "compile-tests", "test", "smoke"):
        completed = _run(commands[label], root)
        if label in {"test", "smoke"}:
            checks[label] = {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        if completed.returncode:
            print(f"{label} failed with exit {completed.returncode}", file=sys.stderr)
            print(completed.stdout, file=sys.stderr, end="")
            print(completed.stderr, file=sys.stderr, end="")
            return 1
    if checks["smoke"]["stdout"] != manifest["smoke_output"]:
        print("smoke output did not match kotlin-project.json", file=sys.stderr)
        return 1
    evidence = {
        "schema_version": 1,
        "status": "complete",
        "project_root": str(root),
        "jvm_target": JVM_TARGET,
        "tools": {"kotlinc": str(kotlinc), "java": str(java)},
        "inputs": [
            {"path": relative, "role": role, "sha256": _sha256(path)}
            for role, rows in (("source", sources), ("test", tests))
            for relative, path in rows
        ],
        "commands": commands,
        "outputs": [
            {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
            for path in (app_jar, test_jar)
        ],
        "checks": checks,
    }
    destination = build_root / "kotlin-build-evidence.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--kotlinc", required=True, type=Path)
    parser.add_argument("--java", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        return build(args.project_root, args.kotlinc, args.java)
    except (FixtureError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
