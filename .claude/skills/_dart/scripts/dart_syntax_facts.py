#!/usr/bin/env python3
"""Produce bounded, source-preserving Dart D2 syntax facts.

The audited host stays dependency-free and read-only. A locked analyzer tool is
copied to a temporary directory, prepared with Pub's offline enforce-lockfile
mode, and invoked directly with the SDK. No Pub command runs in the host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ANALYZER_VERSION = "14.1.0"
SDK_MINIMUM = (3, 12, 0)
SDK_MAXIMUM = (3, 13, 0)
TEST_DIRS = frozenset({"test", "tests", "integration_test", "fixtures", "testdata"})
EXAMPLE_DIRS = frozenset({"example", "examples", "benchmark", "benchmarks"})
GENERATED_DIRS = frozenset({"generated", "gen", "__generated__"})
VENDOR_DIRS = frozenset(
    {"vendor", "vendors", "third_party", "third-party", "deps", ".pub-cache"}
)
BUILD_DIRS = frozenset(
    {".dart_tool", "build", "dist", "out", "coverage", "reports"}
)
GENERATED_SUFFIXES = (
    ".g.dart",
    ".freezed.dart",
    ".mocks.dart",
    ".gr.dart",
    ".chopper.dart",
)
GENERATED_HEADER = re.compile(r"(?:GENERATED CODE|Generated code|DO NOT EDIT|@generated)")


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(
    argv: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "duration_seconds": round(time.monotonic() - started, 4),
        }
    return {
        "argv": argv,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:12000],
        "stderr": result.stderr[:12000],
        "duration_seconds": round(time.monotonic() - started, 4),
    }


def _resolve_tool(raw: str | None) -> Path | None:
    value = raw or "dart"
    if os.sep in value or (os.altsep and os.altsep in value):
        path = Path(value)
        return path.resolve() if path.is_file() and os.access(path, os.X_OK) else None
    discovered = shutil.which(value)
    return Path(discovered).resolve() if discovered else None


def _sdk_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"Dart SDK version:\s*(\d+)\.(\d+)\.(\d+)", text)
    return tuple(map(int, match.groups())) if match else None


def _project_state(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            path = current / name
            if path.is_symlink():
                rows[path.relative_to(root).as_posix()] = "symlink:" + os.readlink(path)
                dirnames.remove(name)
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                rows[relative] = "symlink:" + os.readlink(path)
            else:
                rows[relative] = _hash(path.read_bytes())
    return rows


def _manifest_hash(rows: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(rows.items()):
        digest.update(path.encode() + b"\0" + value.encode() + b"\n")
    return digest.hexdigest()


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    directories = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if path.is_symlink():
        return "symlink", "symlink"
    if directories & BUILD_DIRS:
        return "build", "build-output"
    if directories & VENDOR_DIRS:
        return "vendor", "vendor"
    if (
        directories & GENERATED_DIRS
        or name.endswith(GENERATED_SUFFIXES)
        or GENERATED_HEADER.search(text[:4096])
    ):
        return "generated", "generated"
    if directories & TEST_DIRS or name.endswith("_test.dart"):
        return "test", "test"
    if directories & EXAMPLE_DIRS:
        return "example", "example"
    return "source", None


def _in_target(path: Path, target: Path) -> bool:
    return path == target or target in path.parents


def _inventory(
    root: Path, target: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            path = current / name
            if path.is_symlink():
                relative = path.relative_to(root).as_posix()
                inventory.append({"file": relative, "role": "symlink", "reason": "symlink"})
                seen.add(relative)
                dirnames.remove(name)
        for name in filenames:
            path = current / name
            if path.suffix.casefold() != ".dart" and not path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            if path.is_symlink():
                inventory.append({"file": relative, "role": "symlink", "reason": "symlink"})
                continue
            try:
                content = path.read_bytes()
                text = content.decode("utf-8")
            except (OSError, UnicodeError) as exc:
                row = {
                    "file": relative,
                    "role": "failed",
                    "reason": "source-read-failed",
                    "detail": str(exc),
                }
                inventory.append(row)
                if _in_target(path, target):
                    failures.append(row)
                continue
            role, reason = _role(path, root, text)
            row = {
                "file": relative,
                "role": role,
                "source_sha256": _hash(content),
                "source_bytes": len(content),
                **({"reason": reason} if reason else {}),
            }
            inventory.append(row)
            if role == "source" and _in_target(path, target):
                selected.append({**row, "path": path})
    return sorted(inventory, key=lambda row: row["file"]), selected, failures


def _tool_manifest(tool: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in tool.rglob("*") if candidate.is_file()):
        if ".dart_tool" in path.parts:
            continue
        relative = path.relative_to(tool).as_posix()
        file_hash = _hash(path.read_bytes())
        rows.append({"path": relative, "sha256": file_hash})
        digest.update(relative.encode() + b"\0" + file_hash.encode() + b"\n")
    return {"sha256": digest.hexdigest(), "files": rows}


def _native(
    root: Path,
    dart: Path,
    native_test: Path | None,
    smoke: Path | None,
    smoke_stdout: str | None,
) -> tuple[dict[str, Any], str | None, str]:
    if native_test is None or smoke is None or smoke_stdout is None:
        return {}, "native_contract_unavailable", "partial"
    if not native_test.is_file() or not smoke.is_file():
        return {}, "native_contract_unavailable", "partial"
    for path in (native_test, smoke):
        try:
            path.resolve().relative_to(root)
        except ValueError:
            return {}, "unsafe_native_path", "failed"
    authored_roots = [
        str(path.relative_to(root))
        for name in ("lib", "bin", "tool")
        if (path := root / name).is_dir()
    ]
    if not authored_roots:
        return {}, "native_contract_unavailable", "partial"
    commands = {
        "dart_analyze": [str(dart), "analyze", "--fatal-infos", "--fatal-warnings", "."],
        "dart_format": [
            str(dart),
            "format",
            "--output=none",
            "--set-exit-if-changed",
            *authored_roots,
        ],
        "direct_test": [str(dart), str(native_test)],
        "smoke": [str(dart), str(smoke)],
    }
    results: dict[str, Any] = {}
    for name, argv in commands.items():
        result = _run(argv, root)
        results[name] = result
        if not result["passed"]:
            return results, f"{name}_failed", "failed"
    if results["smoke"]["stdout"] != smoke_stdout:
        return results, "smoke_stdout_mismatch", "failed"
    return results, None, "complete"


def _terminal(
    *,
    status: str,
    failure_kind: str,
    root: Path,
    target: Path,
    before: dict[str, str],
    after: dict[str, str],
    inventory: list[dict[str, Any]],
    files: list[dict[str, Any]],
    tools: dict[str, Any],
    native: dict[str, Any],
    tool_package: dict[str, Any],
) -> dict[str, Any]:
    changed = sorted(
        path for path in before.keys() & after.keys() if before[path] != after[path]
    )
    return {
        "schema_version": 1,
        "analyzer": "dart-syntax-facts-v1",
        "analyzer_package": ANALYZER_VERSION,
        "status": status,
        "failure_kind": failure_kind,
        "project_root": str(root),
        "target": target.relative_to(root).as_posix() if target != root else ".",
        "claim_boundary": (
            "real comments, adjacent doc/fixed-return shapes, and direct spelled calls "
            "inside direct try bodies; no identity, flow, framework, or Flutter semantics"
        ),
        "tools": tools,
        "tool_package": tool_package,
        "native": native,
        "inventory": inventory,
        "files": files,
        "source_manifest": {
            "before_sha256": _manifest_hash(before),
            "after_sha256": _manifest_hash(after),
            "preserved": before == after,
            "changed": changed,
            "missing": sorted(before.keys() - after.keys()),
            "unexpected": sorted(after.keys() - before.keys()),
        },
    }


def _early(status: str, failure_kind: str) -> tuple[dict[str, Any], int]:
    return (
        {
            "schema_version": 1,
            "analyzer": "dart-syntax-facts-v1",
            "analyzer_package": ANALYZER_VERSION,
            "status": status,
            "failure_kind": failure_kind,
            "inventory": [],
            "files": [],
            "tools": {},
            "tool_package": {},
            "native": {},
            "source_manifest": {"preserved": True},
        },
        2,
    )


def produce(
    project_root: Path,
    target: Path,
    *,
    dart: str | None = None,
    pub_cache: Path | None = None,
    native_test: Path | None = None,
    smoke: Path | None = None,
    smoke_stdout: str | None = None,
    tool_root: Path | None = None,
) -> tuple[dict[str, Any], int]:
    root = project_root.resolve()
    if not root.is_dir():
        return _early("failed", "invalid_project_root")
    selected_target = target if target.is_absolute() else root / target
    selected_target = Path(os.path.abspath(selected_target))
    if not selected_target.exists():
        return _early("failed", "invalid_target")
    try:
        selected_target.relative_to(root)
    except ValueError:
        return _early("failed", "unsafe_target")
    if not (root / "pubspec.yaml").is_file():
        return _early("partial", "pubspec_missing")

    before = _project_state(root)
    inventory, selected, read_failures = _inventory(root, selected_target)
    dart_path = _resolve_tool(dart)
    tools: dict[str, Any] = {}
    native: dict[str, Any] = {}
    facts: list[dict[str, Any]] = []
    package = tool_root or Path(__file__).resolve().parents[1] / "tool"
    package_manifest = _tool_manifest(package) if package.is_dir() else {}

    def finish(status: str, failure: str, *, code: int = 2) -> tuple[dict[str, Any], int]:
        after = _project_state(root)
        if before != after:
            status, failure, code = "failed", "unexpected_source_mutation", 2
        return _terminal(
            status=status,
            failure_kind=failure,
            root=root,
            target=selected_target,
            before=before,
            after=after,
            inventory=inventory,
            files=facts,
            tools=tools,
            native=native,
            tool_package=package_manifest,
        ), code

    if read_failures:
        return finish("failed", "source_read_failed")
    if not selected:
        return finish("partial", "no_eligible_dart_source")
    if dart_path is None:
        tools["dart"] = {"state": "missing", "path": dart}
        return finish("partial", "dart_tool_missing")
    probe = _run([str(dart_path), "--version"], root, timeout=20)
    version = _sdk_version(probe["stdout"] + probe["stderr"])
    if not probe["passed"] or version is None:
        tools["dart"] = {"state": "failed", "path": str(dart_path), "probe": probe}
        return finish("failed", "dart_tool_probe_failed")
    rendered_version = ".".join(map(str, version))
    if version < SDK_MINIMUM or version >= SDK_MAXIMUM:
        tools["dart"] = {
            "state": "untested",
            "path": str(dart_path),
            "version": rendered_version,
            "supported": ">=3.12.0 <3.13.0",
        }
        return finish("partial", "untested_toolchain")
    tools["dart"] = {"state": "ready", "path": str(dart_path), "version": rendered_version}
    if not all((package / name).is_file() for name in ("pubspec.yaml", "pubspec.lock", "bin/dart_syntax_facts.dart")):
        return finish("partial", "tool_dependency_unavailable")

    with tempfile.TemporaryDirectory(prefix="dart-d2-analyzer-") as raw:
        prepared = Path(raw) / "tool"
        shutil.copytree(
            package,
            prepared,
            ignore=shutil.ignore_patterns(".dart_tool", "__pycache__", "*.pyc"),
        )
        env = {
            **os.environ,
            "PUB_ENVIRONMENT": "engineering_skills_dart_d2",
            "ALL_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        }
        if pub_cache is not None:
            env["PUB_CACHE"] = str(pub_cache.resolve())
        setup = _run(
            [str(dart_path), "pub", "get", "--offline", "--enforce-lockfile"],
            prepared,
            env=env,
        )
        package_manifest["setup"] = setup
        package_manifest["setup_mode"] = "offline-enforce-lockfile"
        if not setup["passed"]:
            return finish("partial", "tool_dependency_unavailable")
        analyzer = _run(
            [
                str(dart_path),
                str(prepared / "bin" / "dart_syntax_facts.dart"),
                "--project-root",
                str(root),
                *(str(row["path"]) for row in selected),
            ],
            prepared,
            env=env,
        )
        package_manifest["execution"] = analyzer
        if not analyzer["passed"]:
            return finish("failed", "analyzer_execution_failed")
        try:
            payload = json.loads(analyzer["stdout"])
            raw_files = payload["files"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            package_manifest["payload_error"] = str(exc)
            return finish("failed", "analyzer_payload_invalid")
        inventory_by_absolute = {str(row["path"].resolve()): row for row in selected}
        for file in raw_files:
            absolute = str(Path(file["file"]).resolve())
            selected_row = inventory_by_absolute.get(absolute)
            if selected_row is None:
                return finish("failed", "analyzer_payload_unsafe_file")
            facts.append(
                {
                    "file": selected_row["file"],
                    "source_sha256": selected_row["source_sha256"],
                    "diagnostics": file.get("diagnostics", []),
                    "comments": file.get("comments", []),
                    "functions": file.get("functions", []),
                    "calls": file.get("calls", []),
                }
            )
    if any(file["diagnostics"] for file in facts):
        return finish("failed", "dart_parse_diagnostics")

    native_test_path = None if native_test is None else (
        native_test if native_test.is_absolute() else root / native_test
    )
    smoke_path = None if smoke is None else (smoke if smoke.is_absolute() else root / smoke)
    native, native_failure, native_status = _native(
        root,
        dart_path,
        native_test_path,
        smoke_path,
        smoke_stdout,
    )
    if native_failure:
        return finish(native_status, native_failure)
    return finish("complete", "none", code=0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--dart")
    parser.add_argument("--pub-cache", type=Path)
    parser.add_argument("--native-test", type=Path)
    parser.add_argument("--smoke", type=Path)
    parser.add_argument("--smoke-stdout")
    parser.add_argument("--tool-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, code = produce(
        args.project_root,
        args.target,
        dart=args.dart,
        pub_cache=args.pub_cache,
        native_test=args.native_test,
        smoke=args.smoke,
        smoke_stdout=args.smoke_stdout,
        tool_root=args.tool_root,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
