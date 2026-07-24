#!/usr/bin/env python3
"""Compile and exercise the dependency-free Kotlin/JVM pilot with exact tools."""
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
TIMEOUT_SECONDS = 45


class FixtureError(ValueError):
    """The fixture manifest or requested native tool boundary is invalid."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise FixtureError(f"{label} path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FixtureError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise FixtureError(f"{label} path is not executable: {path}")
    return resolved


def _source(root: Path, raw: object, *, label: str) -> tuple[str, Path]:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise FixtureError(f"{label} must be a safe relative path")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".kt":
        raise FixtureError(f"{label} must be a contained .kt path")
    path = root / raw
    if not path.is_file() or path.is_symlink():
        raise FixtureError(f"{label} is unavailable or symbolic: {raw}")
    return raw, path


def _manifest(root: Path) -> dict[str, object]:
    path = root / "kotlin-project.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError("kotlin-project.json is unavailable or malformed") from exc
    keys = {
        "schema_version",
        "jvm_target",
        "sources",
        "tests",
        "test_main",
        "smoke_output",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise FixtureError("kotlin-project.json has an unexpected shape")
    if payload["schema_version"] != 1 or payload["jvm_target"] != JVM_TARGET:
        raise FixtureError("kotlin-project.json requests an unsupported contract")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        raise FixtureError("kotlin-project.json must declare sources")
    if not isinstance(payload["tests"], list) or not payload["tests"]:
        raise FixtureError("kotlin-project.json must declare tests")
    if len(payload["sources"]) != len(set(payload["sources"])) or len(
        payload["tests"]
    ) != len(set(payload["tests"])):
        raise FixtureError("kotlin-project.json contains duplicate inputs")
    if not isinstance(payload["test_main"], str) or not payload["test_main"]:
        raise FixtureError("kotlin-project.json must declare a test main class")
    if not isinstance(payload["smoke_output"], str):
        raise FixtureError("kotlin-project.json must declare smoke output")
    return payload


def _run(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=TIMEOUT_SECONDS,
    )


def _render_failure(label: str, completed: subprocess.CompletedProcess[str]) -> None:
    print(f"{label} failed with exit {completed.returncode}", file=sys.stderr)
    if completed.stdout:
        print(completed.stdout, file=sys.stderr, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")


def build(project_root: Path, kotlinc_path: Path, java_path: Path) -> int:
    try:
        root = project_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FixtureError(f"project root is unavailable: {project_root}") from exc
    if not root.is_dir() or root.is_symlink():
        raise FixtureError("project root must be a regular directory")
    kotlinc = _tool(kotlinc_path, label="kotlinc")
    java = _tool(java_path, label="java")
    manifest = _manifest(root)
    sources = [_source(root, raw, label="source") for raw in manifest["sources"]]
    tests = [_source(root, raw, label="test") for raw in manifest["tests"]]

    build_root = root / ".native-build"
    if build_root.exists():
        if build_root.is_symlink() or not build_root.is_dir():
            raise FixtureError(".native-build must be a regular directory when present")
        shutil.rmtree(build_root)
    build_root.mkdir()
    app_jar = build_root / "kotlin-pilot.jar"
    test_jar = build_root / "kotlin-pilot-tests.jar"
    common = [str(kotlinc), "-jvm-target", JVM_TARGET, "-Werror", "-include-runtime"]
    commands = {
        "compile": [
            *common,
            "-d",
            str(app_jar),
            *(str(path) for _relative, path in sources),
        ],
        "compile-tests": [
            *common,
            "-d",
            str(test_jar),
            *(str(path) for _relative, path in sources),
            *(str(path) for _relative, path in tests),
        ],
        "test": [str(java), "-cp", str(test_jar), manifest["test_main"]],
        "smoke": [str(java), "-jar", str(app_jar)],
    }
    for label in ("compile", "compile-tests"):
        completed = _run(commands[label], root)
        if completed.returncode != 0:
            _render_failure(label, completed)
            return 1
    checks: dict[str, dict[str, object]] = {}
    for label in ("test", "smoke"):
        completed = _run(commands[label], root)
        checks[label] = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            _render_failure(label, completed)
            return 1
    if checks["smoke"]["stdout"] != manifest["smoke_output"]:
        print("smoke output did not match kotlin-project.json", file=sys.stderr)
        return 1

    inputs = [
        {"path": relative, "role": role, "sha256": _sha256(path)}
        for role, rows in (("source", sources), ("test", tests))
        for relative, path in rows
    ]
    outputs = [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}
        for path in (app_jar, test_jar)
    ]
    evidence = {
        "schema_version": 1,
        "status": "complete",
        "project_root": str(root),
        "jvm_target": JVM_TARGET,
        "tools": {"kotlinc": str(kotlinc), "java": str(java)},
        "inputs": inputs,
        "commands": commands,
        "outputs": outputs,
        "checks": checks,
    }
    evidence_path = build_root / "kotlin-build-evidence.json"
    temporary = evidence_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(evidence_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--kotlinc", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return build(args.project_root, args.kotlinc, args.java)
    except (FixtureError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
