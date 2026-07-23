#!/usr/bin/env python3
"""SwiftPM project and lexical facts for six read-only Swift consumers.

This copied helper owns source roles, restrictive dependency-free SwiftPM
checks, exact source fingerprints, Swift-aware string/comment masking, and
direct declaration/function spans. Consumers own their final artifacts and
verdicts. The facts are compiler-validated lexical evidence: no SwiftSyntax,
resolved-symbol, cross-module reference, runtime-dispatch, framework, or
SwiftUI identity is claimed.
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


MINIMUM_SWIFT = (6, 0, 0)
MINIMUM_FORMAT = (6, 0, 0)
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen", "derivedsources"})
BUILD_DIRS = frozenset({".build", "build", "dist", "out"})
REPORT_DIRS = frozenset({"report", "reports"})
GENERATED_RE = re.compile(r"(?:generated .* do not edit|@generated\b)", re.I)
FUNCTION_RE = re.compile(
    rb"(?m)^[ \t]*(?P<visibility>public|open|package|internal|fileprivate|private)?"
    rb"[ \t]*(?:(?:static|class|mutating|nonmutating|async|distributed|final|override|"
    rb"required|convenience)[ \t]+)*func[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*"
)
DECLARATION_BOUNDARY_RE = re.compile(
    rb"(?<![A-Za-z0-9_])(?:actor|associatedtype|case|class|deinit|enum|extension|func|"
    rb"import|init|let|macro|operator|precedencegroup|protocol|struct|subscript|"
    rb"typealias|var)(?![A-Za-z0-9_])"
)
PUBLIC_DECL_RE = re.compile(
    rb"(?m)^[ \t]*(?P<visibility>public|open)[ \t]+"
    rb"(?:(?:final|indirect|nonisolated|static|class)[ \t]+)*"
    rb"(?P<kind>struct|class|enum|protocol|actor|typealias|let|var)[ \t]+"
    rb"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)


def add_tool_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--swift", type=Path, default=Path("swift"))
    parser.add_argument("--swiftc", type=Path, default=Path("swiftc"))
    parser.add_argument("--swift-format", type=Path, default=Path("swift-format"))
    parser.add_argument("--check-product", required=True)
    parser.add_argument("--expected-check", required=True)
    parser.add_argument("--smoke-product", required=True)
    parser.add_argument("--expected-smoke", required=True)


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


def validate_artifacts(root: Path, paths: Iterable[Path]) -> None:
    """Reject destinations outside the host or below an existing symlink."""
    root = root.resolve()
    for raw in paths:
        path = Path(os.path.abspath(raw))
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"artifact outside project: {raw}") from exc
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError(f"artifact path crosses symlink: {current}")


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(argv: list[str], cwd: Path, *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, "", str(exc))


def _which(configured: Path) -> Path | None:
    if configured.is_absolute():
        return configured
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory or ".") / configured
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _version_tuple(text: str, *, formatter: bool) -> tuple[int, int, int] | None:
    pattern = r"(?i)Apple Swift version\s+(\d+)\.(\d+)(?:\.(\d+))?"
    match = re.search(pattern, text)
    if match is None and formatter:
        match = re.search(r"(?m)^\s*(\d+)\.(\d+)(?:\.(\d+))?\s*$", text)
    if match is None:
        return None
    return tuple(int(value or 0) for value in match.groups())


def _probe(configured: Path, name: str, root: Path) -> dict[str, Any]:
    path = _which(configured)
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        return {"state": "missing", "failure_kind": f"{name}-tool-missing"}
    result = _run([str(path), "--version"], root, timeout=30)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    version = _version_tuple(result.stdout + result.stderr, formatter=name == "swift-format")
    if version is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": (result.stdout + result.stderr).strip(),
        }
    minimum = MINIMUM_FORMAT if name == "swift-format" else MINIMUM_SWIFT
    ready = version >= minimum
    return {
        "state": "ready" if ready else "too-old",
        "path": str(path),
        "version": ".".join(map(str, version)),
        "minimum_version": ".".join(map(str, minimum)),
        **({"failure_kind": f"{name}-version-too-old"} if not ready else {}),
    }


def _logical_targets(root: Path, targets: Iterable[str]) -> tuple[list[Path], list[str]]:
    selected: list[Path] = []
    errors: list[str] = []
    for raw in targets:
        path = Path(raw)
        path = path if path.is_absolute() else root / path
        path = Path(os.path.abspath(path))
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"target-outside-project:{raw}")
            continue
        if not path.exists() and not path.is_symlink():
            errors.append(f"target-missing:{raw}")
            continue
        selected.append(path)
    return selected, errors


def _is_selected(path: Path, targets: list[Path]) -> bool:
    for target in targets:
        if target.is_file() or target.is_symlink():
            if path == target:
                return True
            continue
        try:
            path.relative_to(target)
            return True
        except ValueError:
            pass
    return False


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if relative.as_posix() == "Package.swift":
        return "excluded", "configuration"
    if "vendor" in parts:
        return "excluded", "vendor"
    if parts & BUILD_DIRS:
        return "excluded", "build"
    if parts & REPORT_DIRS:
        return "excluded", "report"
    if parts & TEST_DIRS:
        return "excluded", "test"
    if parts & GENERATED_DIRS:
        return "excluded", "generated-tree"
    if name.endswith(("generated.swift", ".generated.swift")):
        return "excluded", "generated-file"
    if GENERATED_RE.search(text[:4096]):
        return "excluded", "generated-marker"
    if "sources" not in parts:
        return "excluded", "non-source-root"
    return "candidate", None


def _inventory(root: Path, targets: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected, errors = _logical_targets(root, targets)
    paths: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        linked = [name for name in dirnames if (current / name).is_symlink()]
        for name in linked:
            path = current / name
            paths[path.relative_to(root).as_posix()] = path
        dirnames[:] = sorted(name for name in dirnames if name not in linked)
        for name in sorted(filenames):
            path = current / name
            if path.suffix.casefold() == ".swift" or path.is_symlink():
                paths[path.relative_to(root).as_posix()] = path

    inventory: list[dict[str, Any]] = []
    for relative, path in sorted(paths.items()):
        if path.is_symlink():
            inventory.append(
                {
                    "file": relative,
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
                    "file": relative,
                    "role": "failed",
                    "reason": "read-error",
                    "detail": str(exc),
                    "selected": _is_selected(path, selected),
                    "_path": path,
                }
            )
            continue
        role, reason = _role(path, root, text)
        inventory.append(
            {
                "file": relative,
                "role": role,
                **({"reason": reason} if reason else {}),
                "selected": _is_selected(path, selected),
                "source_sha256": hash_bytes(source),
                "source_bytes": len(source),
                "_path": path,
                "_source": source,
            }
        )
    return inventory, errors


def _blank(mask: bytearray, start: int, end: int) -> None:
    for index in range(start, min(end, len(mask))):
        if mask[index] not in (10, 13):
            mask[index] = 32


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


def _string_start(source: bytes, start: int) -> tuple[int, int] | None:
    cursor = start
    hashes = 0
    while cursor < len(source) and source[cursor] == 35:
        hashes += 1
        cursor += 1
    if cursor >= len(source) or source[cursor] != 34:
        return None
    quotes = 3 if source.startswith(b'"""', cursor) else 1
    return hashes, quotes


def _string_end(source: bytes, start: int, hashes: int, quotes: int) -> int | None:
    quote = start + hashes
    cursor = quote + quotes
    terminator = b'"' * quotes + b"#" * hashes
    while cursor < len(source):
        if hashes == 0 and quotes == 1 and source[cursor] == 92:
            cursor += 2
            continue
        if source.startswith(terminator, cursor):
            return cursor + len(terminator)
        cursor += 1
    return None


def lexical_facts(source: bytes) -> tuple[bytearray, bytearray, list[dict[str, Any]], list[str]]:
    """Return code mask, comment-only mask, exact comments, and fail-closed errors."""
    code_mask = bytearray(source)
    comment_mask = bytearray(source)
    comments: list[dict[str, Any]] = []
    errors: list[str] = []
    cursor = 0
    while cursor < len(source):
        string = _string_start(source, cursor)
        if string is not None:
            end = _string_end(source, cursor, *string)
            if end is None:
                errors.append(f"unterminated-string@{cursor}")
                end = len(source)
            _blank(code_mask, cursor, end)
            cursor = end
            continue
        if source.startswith(b"//", cursor):
            end = source.find(b"\n", cursor + 2)
            end = len(source) if end < 0 else end
            spelling = source[cursor:end]
            marker = 3 if spelling.startswith(b"///") else 2
            comments.append(
                {
                    "kind": "doc-line" if marker == 3 else "line",
                    "text": spelling[marker:].decode("utf-8").strip(),
                    "span": span(source, cursor, end),
                    "spelling_sha256": hash_bytes(spelling),
                }
            )
            _blank(code_mask, cursor, end)
            _blank(comment_mask, cursor, end)
            cursor = end
            continue
        if source.startswith(b"/*", cursor):
            depth = 1
            end = cursor + 2
            while end < len(source) and depth:
                if source.startswith(b"/*", end):
                    depth += 1
                    end += 2
                elif source.startswith(b"*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            if depth:
                errors.append(f"unterminated-block-comment@{cursor}")
                end = len(source)
            spelling = source[cursor:end]
            marker = 3 if spelling.startswith(b"/**") else 2
            comments.append(
                {
                    "kind": "doc-block" if marker == 3 else "block",
                    "text": spelling[marker:-2].decode("utf-8").strip() if not depth else "",
                    "span": span(source, cursor, end),
                    "spelling_sha256": hash_bytes(spelling),
                }
            )
            _blank(code_mask, cursor, end)
            _blank(comment_mask, cursor, end)
            cursor = end
            continue
        cursor += 1
    return code_mask, comment_mask, comments, errors


def _matching(mask: bytes | bytearray, start: int, opening: int, closing: int) -> int | None:
    depth = 0
    for cursor in range(start, len(mask)):
        if mask[cursor] == opening:
            depth += 1
        elif mask[cursor] == closing:
            depth -= 1
            if depth == 0:
                return cursor
    return None


def _brace_depth(mask: bytes | bytearray, end: int) -> int:
    return bytes(mask[:end]).count(b"{") - bytes(mask[:end]).count(b"}")


def function_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    mask: bytearray = row["_mask"]
    results: list[dict[str, Any]] = []
    for match in FUNCTION_RE.finditer(mask):
        open_paren = bytes(mask).find(b"(", match.end("name"))
        if open_paren < 0:
            continue
        close_paren = _matching(mask, open_paren, 40, 41)
        if close_paren is None:
            continue
        open_brace = bytes(mask).find(b"{", close_paren + 1)
        if open_brace < 0:
            continue
        signature_tail = bytes(mask[close_paren + 1 : open_brace])
        if (
            b"}" in signature_tail
            or b";" in signature_tail
            or DECLARATION_BOUNDARY_RE.search(signature_tail)
            or _brace_depth(mask, open_brace) != _brace_depth(mask, match.start())
        ):
            continue
        close_brace = _matching(mask, open_brace, 123, 125)
        if close_brace is None:
            continue
        start, end = match.start(), close_brace + 1
        normalized = re.sub(
            rb"\s+", b" ", bytes(row["_comment_mask"][open_brace + 1 : close_brace]).strip()
        )
        item_span = span(source, start, end)
        results.append(
            {
                "symbol": match.group("name").decode("ascii"),
                "visibility": (match.group("visibility") or b"internal").decode("ascii"),
                "file": row["file"],
                "kind": "function",
                "top_level": _brace_depth(mask, match.start()) == 0,
                "span": item_span,
                "body_span": span(source, open_brace + 1, close_brace),
                "line_count": item_span["end"]["line"] - item_span["start"]["line"] + 1,
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
                "normalized_body_sha256": hash_bytes(normalized),
                "normalized_body": normalized.decode("utf-8", errors="replace"),
            }
        )
    return results


def declaration_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    mask: bytearray = row["_mask"]
    results = [
        fact
        for fact in function_facts(row)
        if fact["top_level"] and fact["visibility"] in {"public", "open"}
    ]
    for match in PUBLIC_DECL_RE.finditer(mask):
        if _brace_depth(mask, match.start()) != 0:
            continue
        kind = match.group("kind").decode("ascii")
        name = match.group("name").decode("ascii")
        start = match.start("visibility")
        if kind in {"struct", "class", "enum", "protocol", "actor"}:
            open_brace = bytes(mask).find(b"{", match.end("name"))
            close_brace = _matching(mask, open_brace, 123, 125) if open_brace >= 0 else None
            end = close_brace + 1 if close_brace is not None else match.end("name")
        else:
            line_end = source.find(b"\n", match.end("name"))
            end = len(source) if line_end < 0 else line_end
        results.append(
            {
                "symbol": name,
                "visibility": match.group("visibility").decode("ascii"),
                "file": row["file"],
                "kind": kind,
                "span": span(source, start, end),
                "source_sha256": row["source_sha256"],
                "spelling_sha256": hash_bytes(source[start:end]),
            }
        )
    results.sort(key=lambda fact: (fact["file"], fact["span"]["start_byte"], fact["symbol"]))
    return results


def _manifest(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows = [
        {
            "file": row["file"],
            "source_sha256": row["source_sha256"],
            "source_bytes": row["source_bytes"],
        }
        for row in inventory
        if "source_sha256" in row
    ]
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["file"].encode("utf-8") + b"\0")
        digest.update(row["source_sha256"].encode("ascii") + b"\n")
    return rows, digest.hexdigest()


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


def sources_preserved(snapshot: dict[str, Any]) -> bool:
    for row in snapshot["inventory"]:
        path = row.get("_path")
        if row.get("source_sha256") and isinstance(path, Path):
            try:
                if hash_bytes(path.read_bytes()) != row["source_sha256"]:
                    return False
            except OSError:
                return False
    manifest = snapshot.get("_package_manifest")
    if not isinstance(manifest, Path):
        return False
    if not snapshot.get("package_sha256"):
        return not manifest.exists()
    try:
        return hash_bytes(manifest.read_bytes()) == snapshot["package_sha256"]
    except OSError:
        return False


def terminal_return_code(snapshot: dict[str, Any]) -> int:
    if snapshot["status"] == "failed":
        return 1
    if snapshot["status"] == "partial":
        return 2
    return 0


def native_command_templates(check_product: str, smoke_product: str) -> dict[str, list[str]]:
    """Return the public, external-state native obligations for an adapter."""
    return {
        "build": [
            "swift build --package-path . --cache-path <external>/cache "
            "--config-path <external>/config --security-path <external>/security "
            "--scratch-path <external>/build --disable-dependency-cache "
            "--manifest-cache local --disable-netrc --disable-keychain "
            "--disable-prefetching --disable-automatic-resolution --enable-index-store"
        ],
        "formal_test": [],
        "static": ["swiftc -frontend -parse <each eligible Swift source>"],
        "direct_check": [f"<external>/build/debug/{check_product}"],
        "smoke": [f"<external>/build/debug/{smoke_product}"],
        "format": ["swift-format lint --strict --recursive Sources"],
    }


def _swiftpm_base(swift: str, root: Path, state: Path) -> list[str]:
    return [
        swift,
        "package",
        "--package-path",
        str(root),
        "--cache-path",
        str(state / "cache"),
        "--config-path",
        str(state / "config"),
        "--security-path",
        str(state / "security"),
        "--scratch-path",
        str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache",
        "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
    ]


def _check_row(identifier: str, argv: list[str], result: subprocess.CompletedProcess[str]) -> dict:
    return {
        "id": identifier,
        "command": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def collect_snapshot(
    project_root: Path,
    targets: Iterable[str],
    *,
    swift: Path,
    swiftc: Path,
    swift_format: Path,
    check_product: str,
    expected_check: str,
    smoke_product: str,
    expected_smoke: str,
) -> dict[str, Any]:
    """Collect one source-preserving SwiftPM and lexical snapshot."""
    root = project_root.resolve()
    inventory, errors = _inventory(root, targets)
    manifest, manifest_hash = _manifest(inventory)
    package = root / "Package.swift"
    package_sha256 = hash_bytes(package.read_bytes()) if package.is_file() else ""
    tools = {
        "swift": _probe(swift, "swift", root),
        "swiftc": _probe(swiftc, "swiftc", root),
        "swift-format": _probe(swift_format, "swift-format", root),
    }
    snapshot: dict[str, Any] = {
        "language": "swift",
        "analyzer": "swift-project-lexical-facts-v1",
        "status": "complete",
        "inventory": inventory,
        "errors": errors,
        "tools": tools,
        "package_sha256": package_sha256,
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_hash,
        "source_preserved": True,
        "host_state_preserved": True,
        "native_checks": [],
        "native_test_boundary": "unavailable-under-active-clt",
        "_package_manifest": package,
        "limits": [
            "dependency-free SwiftPM regular and executable targets only",
            "compiler-validated lexical source-file and direct declaration spans only",
            "no SwiftSyntax, resolved symbol/reference/type, overload, protocol, extension, or call identity",
            "no conditional-compilation projection, macro/plugin expansion, reflection, or dynamic dispatch",
            "string interpolation is treated as string content; comments inside interpolation are not inventoried",
            "no Xcode project, Apple framework, Objective-C/C-family, resource, or SwiftUI behavior claim",
            "native XCTest and Testing modules remain unavailable under the active Command Line Tools",
        ],
    }
    unreadable = [row for row in inventory if row["role"] == "failed"]
    if unreadable:
        snapshot.update(status="failed", failure_kind="unreadable-source")
        return snapshot
    bad = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad:
        first = bad[0]
        snapshot.update(
            status="failed" if first["state"] == "failed" else "partial",
            failure_kind=first["failure_kind"],
        )
        return snapshot
    if not package.is_file():
        snapshot.update(status="partial", failure_kind="swiftpm-project-incomplete")
        return snapshot

    with tempfile.TemporaryDirectory(prefix="swift-project-lexical-") as temporary:
        state = Path(temporary)
        base = _swiftpm_base(tools["swift"]["path"], root, state)
        dump_argv = [*base, "dump-package"]
        dump = _run(dump_argv, root)
        snapshot["native_checks"].append(_check_row("swiftpm-dump-package", dump_argv, dump))
        if dump.returncode:
            snapshot.update(status="failed", failure_kind="swiftpm-dump-package-failed")
            return snapshot
        try:
            package_data = json.loads(dump.stdout)
        except json.JSONDecodeError as exc:
            snapshot.update(status="failed", failure_kind="swiftpm-dump-package-invalid")
            snapshot["errors"].append(str(exc))
            return snapshot
        if package_data.get("dependencies"):
            snapshot.update(status="partial", failure_kind="swiftpm-dependencies-outside-contract")
            return snapshot

        describe_argv = [*base, "describe", "--type", "json"]
        describe = _run(describe_argv, root)
        snapshot["native_checks"].append(_check_row("swiftpm-describe", describe_argv, describe))
        if describe.returncode:
            snapshot.update(status="failed", failure_kind="swiftpm-describe-failed")
            return snapshot
        try:
            description = json.loads(describe.stdout)
        except json.JSONDecodeError as exc:
            snapshot.update(status="failed", failure_kind="swiftpm-describe-invalid")
            snapshot["errors"].append(str(exc))
            return snapshot

        target_rows = description.get("targets", [])
        unsupported = [
            row for row in target_rows if row.get("type") not in {"library", "executable", "test"}
        ]
        if unsupported:
            snapshot.update(status="partial", failure_kind="swiftpm-target-shape-outside-contract")
            return snapshot
        declared: set[str] = set()
        units: list[dict[str, Any]] = []
        for target in target_rows:
            units.append(
                {
                    "name": target.get("name"),
                    "type": target.get("type"),
                    "path": target.get("path"),
                    "sources": target.get("sources", []),
                    "target_dependencies": target.get("target_dependencies", []),
                }
            )
            if target.get("type") == "test":
                continue
            target_path = str(target.get("path", "")).rstrip("/")
            declared.update(f"{target_path}/{source}" for source in target.get("sources", []))
        snapshot["project"] = {
            "name": description.get("name"),
            "tools_version": description.get("tools_version"),
            "products": description.get("products", []),
            "targets": units,
        }
        for row in inventory:
            if row["role"] != "candidate" or not row["selected"]:
                continue
            if row["file"] not in declared:
                row.update(role="failed", reason="undeclared-swiftpm-source")
                errors.append(f"{row['file']}:undeclared-swiftpm-source")
                continue
            row["role"] = "eligible"

        selected_rows = [row for row in inventory if row["role"] == "eligible"]
        if not selected_rows:
            snapshot.update(status="partial", failure_kind="no-eligible-swift-files")
            return snapshot
        if errors:
            snapshot.update(status="failed", failure_kind="source-inventory-failed")
            return snapshot

        build_argv = [
            tools["swift"]["path"],
            "build",
            "--package-path",
            str(root),
            "--cache-path",
            str(state / "cache"),
            "--config-path",
            str(state / "config"),
            "--security-path",
            str(state / "security"),
            "--scratch-path",
            str(state / "build"),
            "--disable-dependency-cache",
            "--manifest-cache",
            "local",
            "--disable-netrc",
            "--disable-keychain",
            "--disable-prefetching",
            "--disable-automatic-resolution",
            "--enable-index-store",
        ]
        build = _run(build_argv, root)
        snapshot["native_checks"].append(_check_row("swiftpm-build", build_argv, build))
        if build.returncode:
            snapshot.update(status="failed", failure_kind="swiftpm-build-failed")
            return snapshot

        parse_argv = [tools["swiftc"]["path"], "-frontend", "-parse", "<each-eligible-source>"]
        parse_results = [
            _run([tools["swiftc"]["path"], "-frontend", "-parse", str(row["_path"])], root)
            for row in selected_rows
        ]
        parsed = subprocess.CompletedProcess(
            parse_argv,
            next((result.returncode for result in parse_results if result.returncode), 0),
            "\n".join(result.stdout for result in parse_results),
            "\n".join(result.stderr for result in parse_results),
        )
        snapshot["native_checks"].append(_check_row("compiler-parse", parse_argv, parsed))
        if parsed.returncode:
            snapshot.update(status="failed", failure_kind="compiler-parse-failed")
            return snapshot

        format_argv = [tools["swift-format"]["path"], "lint", "--strict", "--recursive", "Sources"]
        formatted = _run(format_argv, root)
        snapshot["native_checks"].append(_check_row("swift-format-lint", format_argv, formatted))
        if formatted.returncode:
            snapshot.update(status="failed", failure_kind="swift-format-lint-failed")
            return snapshot

        for identifier, product, expected in (
            ("direct-check", check_product, expected_check),
            ("executable-smoke", smoke_product, expected_smoke),
        ):
            executable = state / "build" / "debug" / product
            argv = [str(executable)]
            result = _run(argv, root, timeout=30)
            snapshot["native_checks"].append(_check_row(identifier, argv, result))
            if result.returncode or result.stdout.strip() != expected:
                snapshot.update(status="failed", failure_kind=f"{identifier}-failed")
                return snapshot

    for row in inventory:
        if row["role"] != "eligible":
            continue
        code_mask, comment_mask, comments, lexical_errors = lexical_facts(row["_source"])
        if lexical_errors:
            row.update(role="failed", reason="lexical-provider-failed", detail="; ".join(lexical_errors))
            errors.append(f"{row['file']}:lexical-provider-failed")
            continue
        row.update(
            native_syntax="swiftc-frontend-parse",
            comments=comments,
            _mask=code_mask,
            _comment_mask=comment_mask,
        )
    if errors:
        snapshot.update(status="failed", failure_kind="lexical-provider-failed")
    snapshot["errors"] = errors
    snapshot["source_preserved"] = sources_preserved(snapshot)
    snapshot["host_state_preserved"] = snapshot["source_preserved"]
    if not snapshot["source_preserved"]:
        snapshot.update(status="failed", failure_kind="unexpected-source-mutation")
    snapshot["summary"] = {
        "discovered": len(inventory),
        "eligible": sum(row["role"] == "eligible" for row in inventory),
        "excluded": sum(row["role"] == "excluded" for row in inventory),
        "failed": sum(row["role"] == "failed" for row in inventory),
    }
    return snapshot
