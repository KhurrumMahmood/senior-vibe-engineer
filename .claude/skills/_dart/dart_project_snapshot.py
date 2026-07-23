#!/usr/bin/env python3
"""Dependency-free Dart project snapshot for read-only D1 consumers.

The snapshot owns project markers, source roles, exact fingerprints, Dart SDK
preflight, the host-safe native matrix, source preservation, zero-write checks,
and terminal status. Consumers keep their final artifact schemas and meaning.
No analyzer package, Analysis Server/LSP, symbol identity, framework inference,
package graph, or architectural recommendation is provided here.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_DART = (3, 12, 0)
MAXIMUM_DART = (3, 13, 0)
TEST_DIRS = frozenset({"test", "tests", "integration_test"})
EXAMPLE_DIRS = frozenset({"example", "examples", "benchmark", "benchmarks"})
GENERATED_DIRS = frozenset({"generated", "gen"})
VENDOR_DIRS = frozenset({"vendor", "vendored", ".pub-cache"})
BUILD_DIRS = frozenset({"build", "dist", "out"})
REPORT_DIRS = frozenset({"report", "reports", "coverage"})
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart", ".mocks.dart")
GENERATED_MARKER_RE = re.compile(
    r"(?:GENERATED CODE\s*-\s*DO NOT MODIFY BY HAND|Code generated .* DO NOT EDIT\.|@generated\b)",
    re.IGNORECASE,
)
CONFIGURATION_FILES = (
    "pubspec.yaml",
    "pubspec.lock",
    "analysis_options.yaml",
    "build.yaml",
    ".dart_tool/package_config.json",
)
FORMAT_ROOTS = ("lib", "bin", "test", "integration_test", "tool", "example", "benchmark")


def add_snapshot_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dart", type=Path, default=Path("dart"))
    parser.add_argument("--direct-test", required=True)
    parser.add_argument("--smoke-entrypoint", required=True)
    parser.add_argument("--expected-smoke", required=True)


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def clear_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_artifact_paths(project_root: Path, paths: Iterable[Path]) -> list[Path]:
    """Return normalized report paths or reject source overlap and symlinks."""
    root = project_root.resolve()
    normalized: list[Path] = []
    for raw in paths:
        logical = raw if raw.is_absolute() else root / raw
        logical = Path(os.path.realpath(logical))
        if not _is_within(logical, root):
            raise ValueError("artifact path must stay inside --project-root")
        relative = logical.relative_to(root)
        if not relative.parts or relative.parts[0].casefold() != "reports":
            raise ValueError("Dart D1 artifacts must stay below project reports/")
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("artifact path must not cross a symlink")
        normalized.append(logical)
    parents = {path.parent for path in normalized}
    if len(parents) != 1:
        raise ValueError("one Dart D1 outcome must keep artifacts in one report directory")
    return normalized


def _which(configured: Path) -> Path | None:
    if configured.is_absolute():
        return configured if configured.is_file() and os.access(configured, os.X_OK) else None
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory or ".") / configured
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _run(argv: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 126, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(argv, 124, exc.stdout or "", exc.stderr or "timeout")


def _probe_dart(configured: Path, root: Path) -> dict[str, Any]:
    tool = _which(configured)
    if tool is None:
        return {
            "state": "missing",
            "failure_kind": "dart-tool-missing",
            "minimum_version": "3.12.0",
            "maximum_exclusive_version": "3.13.0",
        }
    result = _run([str(tool), "--version"], root)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode:
        return {
            "state": "failed",
            "path": str(tool),
            "failure_kind": "dart-version-failed",
            "detail": output,
        }
    match = re.search(r"Dart SDK version:\s*(\d+)\.(\d+)\.(\d+)", output)
    if match is None:
        return {
            "state": "failed",
            "path": str(tool),
            "failure_kind": "dart-version-unrecognized",
            "detail": output,
        }
    version = tuple(map(int, match.groups()))
    evidence: dict[str, Any] = {
        "path": str(tool),
        "version": ".".join(match.groups()),
        "minimum_version": "3.12.0",
        "maximum_exclusive_version": "3.13.0",
    }
    if version < MINIMUM_DART:
        return {**evidence, "state": "too-old", "failure_kind": "dart-version-too-old"}
    if version >= MAXIMUM_DART:
        return {
            **evidence,
            "state": "untested",
            "failure_kind": "dart-toolchain-untested",
        }
    return {**evidence, "state": "ready"}


def _logical_targets(root: Path, targets: Iterable[str]) -> tuple[list[Path], list[str]]:
    selected: list[Path] = []
    errors: list[str] = []
    for raw in targets:
        logical = Path(raw)
        logical = logical if logical.is_absolute() else root / logical
        logical = Path(os.path.abspath(logical))
        if logical.is_symlink():
            errors.append(f"target-symlink:{raw}")
            continue
        if not logical.exists():
            errors.append(f"target-missing:{raw}")
            continue
        logical = logical.resolve()
        if not _is_within(logical, root):
            errors.append(f"target-outside-project:{raw}")
            continue
        selected.append(logical)
    return selected, errors


def _is_selected(path: Path, targets: list[Path]) -> bool:
    return any(path == target or (target.is_dir() and _is_within(path, target)) for target in targets)


def _is_part_file(text: str) -> bool:
    in_block = False
    for raw in text[:4096].splitlines():
        line = raw.strip()
        if in_block:
            if "*/" in line:
                in_block = False
                line = line.split("*/", 1)[1].strip()
            else:
                continue
        if not line or line.startswith("//"):
            continue
        if line.startswith("/*"):
            in_block = "*/" not in line
            if in_block:
                continue
            line = line.split("*/", 1)[1].strip()
        return re.match(r"part\s+of\b", line) is not None
    return False


def _role(relative: Path, text: str) -> tuple[str, str | None]:
    parents = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if parents & REPORT_DIRS:
        return "excluded", "report"
    if parents & VENDOR_DIRS:
        return "excluded", "vendor"
    if parents & BUILD_DIRS:
        return "excluded", "build"
    if ".dart_tool" in parents:
        return "excluded", "cache"
    if parents & TEST_DIRS:
        return "excluded", "test"
    if parents & EXAMPLE_DIRS:
        return "excluded", "example"
    if "bin" in parents:
        return "excluded", "executable"
    if "tool" in parents:
        return "excluded", "tooling"
    if parents & GENERATED_DIRS:
        return "excluded", "generated-tree"
    if name.endswith(GENERATED_SUFFIXES):
        return "excluded", "generated-file"
    if GENERATED_MARKER_RE.search(text[:4096]):
        return "excluded", "generated-marker"
    if _is_part_file(text):
        return "excluded", "part-file"
    if relative.parts and relative.parts[0].casefold() == "lib":
        return "library", None
    return "excluded", "outside-library"


def _inventory(root: Path, targets: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected, errors = _logical_targets(root, targets)
    discovered: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
        for name in symlink_dirs:
            path = current / name
            discovered[path.relative_to(root).as_posix()] = path
        dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
        for name in sorted(filenames):
            path = current / name
            if path.suffix.casefold() == ".dart" or path.is_symlink():
                discovered[path.relative_to(root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    for label, path in sorted(discovered.items()):
        if path.is_symlink():
            inventory.append(
                {
                    "file": label,
                    "role": "excluded",
                    "reason": "symlink",
                    "selected": _is_selected(path, selected),
                    "_path": path,
                }
            )
            continue
        try:
            source = path.read_bytes()
            text = source.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            inventory.append(
                {
                    "file": label,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                    "selected": _is_selected(path, selected),
                    "_path": path,
                }
            )
            continue
        role, reason = _role(path.relative_to(root), text)
        inventory.append(
            {
                "file": label,
                "role": role,
                **({"reason": reason} if reason else {}),
                "selected": _is_selected(path, selected),
                "sha256": hash_bytes(source),
                "bytes": len(source),
                "_path": path,
                "_source": source,
            }
        )
    return inventory, errors


def _manifest(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    public = [
        {"file": row["file"], "sha256": row["sha256"], "bytes": row["bytes"]}
        for row in rows
        if "sha256" in row
    ]
    digest = hashlib.sha256()
    for row in public:
        digest.update(row["file"].encode("utf-8") + b"\0")
        digest.update(row["sha256"].encode("ascii") + b"\n")
    return public, digest.hexdigest()


def _configuration_manifest(root: Path) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    for label in CONFIGURATION_FILES:
        path = root / label
        if path.is_file() and not path.is_symlink():
            source = path.read_bytes()
            rows.append({"file": label, "sha256": hash_bytes(source), "bytes": len(source)})
    return _manifest(rows)


def _host_state(root: Path) -> str:
    digest = hashlib.sha256()
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        relative_dir = current.relative_to(root)
        if relative_dir.parts and relative_dir.parts[0].casefold() == "reports":
            dirnames[:] = []
            continue
        for name in sorted(dirnames):
            path = current / name
            if path.is_symlink():
                label = path.relative_to(root).as_posix()
                digest.update(label.encode() + b"\0L\0" + os.readlink(path).encode() + b"\n")
        dirnames[:] = sorted(name for name in dirnames if not (current / name).is_symlink())
        for name in sorted(filenames):
            path = current / name
            label = path.relative_to(root).as_posix()
            if path.is_symlink():
                digest.update(label.encode() + b"\0L\0" + os.readlink(path).encode() + b"\n")
            else:
                digest.update(label.encode() + b"\0F\0" + hash_bytes(path.read_bytes()).encode() + b"\n")
    return digest.hexdigest()


def _native_check(identifier: str, argv: list[str], root: Path) -> dict[str, Any]:
    result = _run(argv, root)
    return {
        "id": identifier,
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _native_matrix(
    root: Path,
    tool: Path,
    *,
    direct_test: str,
    smoke_entrypoint: str,
) -> list[dict[str, Any]]:
    roots = [name for name in FORMAT_ROOTS if (root / name).is_dir()]
    return [
        _native_check(
            "dart-analyze",
            [str(tool), "analyze", "--fatal-infos", "--fatal-warnings", "."],
            root,
        ),
        _native_check(
            "format-check",
            [str(tool), "format", "--output=none", "--set-exit-if-changed", *roots],
            root,
        ),
        _native_check("direct-test", [str(tool), direct_test], root),
        _native_check("executable-smoke", [str(tool), smoke_entrypoint], root),
    ]


def _source_preserved(inventory: list[dict[str, Any]]) -> bool:
    for row in inventory:
        path = row.get("_path")
        if row.get("sha256") and isinstance(path, Path):
            try:
                if hash_bytes(path.read_bytes()) != row["sha256"]:
                    return False
            except OSError:
                return False
    return True


def _summary(inventory: list[dict[str, Any]], errors: list[str]) -> dict[str, int]:
    return {
        "discovered": len(inventory),
        "eligible": sum(row["role"] == "library" and row["selected"] for row in inventory),
        "excluded": sum(row["role"] == "excluded" for row in inventory),
        "failed": sum(row["role"] == "failed" for row in inventory) + len(errors),
    }


def collect_snapshot(
    project_root: Path,
    targets: Iterable[str],
    *,
    dart: Path,
    direct_test: str,
    smoke_entrypoint: str,
    expected_smoke: str,
) -> dict[str, Any]:
    """Collect one immutable Dart project snapshot and execute its native gates."""
    root = project_root.resolve()
    inventory, errors = _inventory(root, targets)
    source_manifest, source_digest = _manifest(inventory)
    configuration_manifest, configuration_digest = _configuration_manifest(root)
    before = _host_state(root)
    tool = _probe_dart(dart, root)
    snapshot: dict[str, Any] = {
        "language": "dart",
        "analyzer": "dart-project-filesystem-snapshot-v1",
        "status": "complete",
        "inventory": inventory,
        "errors": errors,
        "tool": tool,
        "source_manifest": source_manifest,
        "source_manifest_sha256": source_digest,
        "configuration_manifest": configuration_manifest,
        "configuration_manifest_sha256": configuration_digest,
        "native_checks": [],
        "source_preserved": True,
        "host_state_preserved": True,
        "summary": _summary(inventory, errors),
        "limits": [
            "strict filesystem/text facts only; no symbol identity or conceptual equivalence",
            "no analyzer package, Analysis Server/LSP, package graph, or framework inference",
            "no Flutter, workspace, build_runner, generated API, parts semantics, or move safety claim",
            "common Dart generated suffixes are an explicit Dart-only boundary",
        ],
    }
    if errors:
        snapshot.update(status="failed", failure_kind="unsafe-target")
    elif any(row["role"] == "failed" for row in inventory):
        snapshot.update(status="failed", failure_kind="unreadable-source")
    elif not (root / "pubspec.yaml").is_file():
        snapshot.update(status="partial", failure_kind="dart-project-marker-missing")
    elif tool["state"] != "ready":
        snapshot.update(
            status="failed" if tool["state"] == "failed" else "partial",
            failure_kind=tool["failure_kind"],
        )
    else:
        direct = root / direct_test
        smoke = root / smoke_entrypoint
        if not direct.is_file() or not smoke.is_file():
            snapshot.update(status="partial", failure_kind="native-entrypoint-missing")
        else:
            checks = _native_matrix(
                root,
                Path(tool["path"]),
                direct_test=direct_test,
                smoke_entrypoint=smoke_entrypoint,
            )
            snapshot["native_checks"] = checks
            failing = next((check for check in checks if check["returncode"]), None)
            smoke_check = checks[-1]
            if failing is not None:
                detail = f"{failing['stdout']}\n{failing['stderr']}"
                kind = (
                    "syntax-error"
                    if failing["id"] in {"dart-analyze", "format-check"}
                    and ("error -" in detail or "Could not format" in detail)
                    else "native-check-failure"
                )
                snapshot.update(status="failed", failure_kind=kind)
            elif smoke_check["stdout"].strip() != expected_smoke:
                snapshot.update(status="failed", failure_kind="native-smoke-mismatch")

    snapshot["source_preserved"] = _source_preserved(inventory)
    after = _host_state(root)
    snapshot["host_state_sha256_before"] = before
    snapshot["host_state_sha256_after"] = after
    snapshot["host_state_preserved"] = before == after
    if not snapshot["source_preserved"] or not snapshot["host_state_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    snapshot_key = {
        "source_manifest_sha256": source_digest,
        "configuration_manifest_sha256": configuration_digest,
        "dart_version": tool.get("version"),
        "direct_test": direct_test,
        "smoke_entrypoint": smoke_entrypoint,
        "expected_smoke": expected_smoke,
    }
    snapshot["snapshot_sha256"] = hash_bytes(
        json.dumps(snapshot_key, sort_keys=True, separators=(",", ":")).encode()
    )
    return snapshot


def public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            [{k: v for k, v in row.items() if not k.startswith("_")} for row in value]
            if key == "inventory"
            else value
        )
        for key, value in snapshot.items()
        if not key.startswith("_")
    }


def eligible_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in snapshot["inventory"]
        if row["role"] == "library" and row["selected"]
    ]


def terminal_return_code(snapshot: dict[str, Any]) -> int:
    return 1 if snapshot["status"] == "failed" else 2 if snapshot["status"] == "partial" else 0


def _line_offsets(source: bytes) -> list[int]:
    return [0, *(match.end() for match in re.finditer(b"\n", source))]


def _position(offset: int, lines: list[int]) -> dict[str, int]:
    index = bisect.bisect_right(lines, offset) - 1
    return {"line": index + 1, "column": offset - lines[index] + 1}


def span(source: bytes, start: int, end: int) -> dict[str, Any]:
    lines = _line_offsets(source)
    return {
        "start_byte": start,
        "end_byte": end,
        "start": _position(start, lines),
        "end": _position(end, lines),
    }
