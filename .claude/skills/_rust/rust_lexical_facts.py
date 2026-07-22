#!/usr/bin/env python3
"""Copied Rust lexical/filesystem facts for read-only skill consumers.

This module owns only the facts shared by the Rust lexical cohort: source-role
inventory, exact source fingerprints, Rust-aware lexical masks, direct
declaration/function spans, supported tool probes, and locked/offline Cargo
metadata/check gates. Consumers retain their own final artifact schemas and
interpretation. No macro expansion, name/type resolution, cfg projection, or
runtime behavior is claimed.
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


MINIMUM = {"rustc": (1, 85, 0), "cargo": (1, 85, 0), "rustfmt": (1, 8, 0)}
TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "fixtures", "testdata"})
GENERATED_DIRS = frozenset({"generated", "gen"})
BUILD_DIRS = frozenset({"target", "build", "dist", "out"})
AUXILIARY_DIRS = frozenset({"examples", "benches"})
GENERATED_RE = re.compile(r"(?:Code generated .* DO NOT EDIT\.|@generated\b)", re.I)
FUNCTION_RE = re.compile(
    rb"(?P<leading>^[ \t]*)"
    rb"(?P<attrs>(?:\#\[[^\]\n]*\][ \t\r\n]*)*)"
    rb"(?P<prefix>(?:pub(?:\([^\n)]*\))?\s+)?(?:(?:const|async|unsafe)\s+)*"
    rb"(?:extern\s+\"[^\n\"]+\"\s+)?fn\s+)"
    rb"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*",
    re.MULTILINE,
)
DECLARATION_RE = re.compile(
    rb"(?P<leading>^[ \t]*)"
    rb"(?P<attrs>(?:\#\[[^\]\n]*\][ \t\r\n]*)*)"
    rb"(?P<visibility>pub(?:\([^\n)]*\))?\s+)"
    rb"(?P<kind>struct|enum|trait|type|const|static|mod)\s+"
    rb"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def add_tool_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rustc", type=Path, default=Path("rustc"))
    parser.add_argument("--cargo", type=Path, default=Path("cargo"))
    parser.add_argument("--rustfmt", type=Path, default=Path("rustfmt"))


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


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run(
    argv: list[str], cwd: Path, *, env: dict[str, str] | None = None, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
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


def _probe(configured: Path, name: str, root: Path) -> dict[str, Any]:
    path = _which(configured)
    if path is None or not path.is_file() or not os.access(path, os.X_OK):
        return {"state": "missing", "failure_kind": f"{name}-tool-missing"}
    result = _run([str(path), "--version"], root)
    if result.returncode:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-failed",
            "detail": (result.stderr or result.stdout).strip(),
        }
    match = re.search(rf"\b{re.escape(name)}\s+(\d+)\.(\d+)\.(\d+)", result.stdout)
    if match is None:
        return {
            "state": "failed",
            "path": str(path),
            "failure_kind": f"{name}-version-unrecognized",
            "detail": result.stdout.strip(),
        }
    version = tuple(map(int, match.groups()))
    ready = version >= MINIMUM[name]
    return {
        "state": "ready" if ready else "too-old",
        "path": str(path),
        "version": ".".join(match.groups()),
        "minimum_version": ".".join(map(str, MINIMUM[name])),
        **({"failure_kind": f"{name}-version-too-old"} if not ready else {}),
    }


def _role(path: Path, root: Path, text: str) -> tuple[str, str | None]:
    relative = path.relative_to(root)
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    if "vendor" in parts:
        return "excluded", "vendor"
    if parts & BUILD_DIRS:
        return "excluded", "build-tree"
    if parts & TEST_DIRS or name.endswith("_test.rs"):
        return "excluded", "test"
    if parts & AUXILIARY_DIRS:
        return "excluded", "auxiliary-target"
    if parts & GENERATED_DIRS:
        return "excluded", "generated-tree"
    if name == "build.rs":
        return "excluded", "configuration"
    if GENERATED_RE.search(text[:4096]):
        return "excluded", "generated-marker"
    return "candidate", None


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
        if target.is_symlink() or target.is_file():
            if path == target:
                return True
            continue
        try:
            path.relative_to(target)
            return True
        except ValueError:
            continue
    return False


def _inventory(root: Path, targets: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected, errors = _logical_targets(root, targets)
    paths: dict[str, Path] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        symlink_dirs = [name for name in dirnames if (current / name).is_symlink()]
        for name in symlink_dirs:
            path = current / name
            paths[path.relative_to(root).as_posix()] = path
        dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
        for name in sorted(filenames):
            path = current / name
            if path.suffix.casefold() == ".rs" or path.is_symlink():
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
    for index in range(start, end):
        if mask[index] not in (10, 13):
            mask[index] = 32


def _quoted_end(source: bytes, quote: int) -> int:
    cursor = quote + 1
    while cursor < len(source):
        if source[cursor] == 92:
            cursor += 2
            continue
        if source[cursor] == source[quote]:
            return cursor + 1
        cursor += 1
    return len(source)


def _raw_end(source: bytes, start: int) -> int | None:
    if start and (source[start - 1 : start].isalnum() or source[start - 1] == 95):
        return None
    prefix = next((item for item in (b"br", b"cr", b"r") if source.startswith(item, start)), None)
    if prefix is None:
        return None
    cursor = start + len(prefix)
    hashes = 0
    while cursor < len(source) and source[cursor] == 35:
        hashes += 1
        cursor += 1
    if cursor >= len(source) or source[cursor] != 34:
        return None
    terminator = b'"' + b"#" * hashes
    found = source.find(terminator, cursor + 1)
    return len(source) if found < 0 else found + len(terminator)


def _looks_like_char(source: bytes, start: int) -> bool:
    if start + 2 >= len(source):
        return False
    if source[start + 1] == 92:
        return source.find(b"'", start + 2, min(len(source), start + 12)) >= 0
    return source[start + 2] == 39


def lexical_mask(source: bytes) -> tuple[bytearray, list[str]]:
    """Blank strings/comments without changing byte offsets or newlines."""
    mask = bytearray(source)
    errors: list[str] = []
    cursor = 0
    while cursor < len(source):
        if source.startswith(b"//", cursor):
            end = source.find(b"\n", cursor + 2)
            end = len(source) if end < 0 else end
            _blank(mask, cursor, end)
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
            _blank(mask, cursor, end)
            cursor = end
            continue
        raw_end = _raw_end(source, cursor)
        if raw_end is not None:
            _blank(mask, cursor, raw_end)
            cursor = raw_end
            continue
        quote = cursor + 1 if source.startswith((b'b"', b'c"'), cursor) else cursor
        if source[quote : quote + 1] == b'"':
            end = _quoted_end(source, quote)
            _blank(mask, cursor, end)
            cursor = end
            continue
        if source[cursor] == 39 and _looks_like_char(source, cursor):
            end = _quoted_end(source, cursor)
            _blank(mask, cursor, end)
            cursor = end
            continue
        cursor += 1
    return mask, errors


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


def _cfg(attrs: bytes) -> bool:
    return re.search(rb"#\s*\[\s*cfg(?:_attr)?\b", attrs) is not None


def function_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    source: bytes = row["_source"]
    mask: bytearray = row["_mask"]
    results: list[dict[str, Any]] = []
    for match in FUNCTION_RE.finditer(mask):
        if _cfg(match.group("attrs")):
            continue
        open_paren = bytes(mask).find(b"(", match.end("name"))
        if open_paren < 0:
            continue
        close_paren = _matching(mask, open_paren, 40, 41)
        if close_paren is None:
            continue
        open_brace = bytes(mask).find(b"{", close_paren + 1)
        semicolon = bytes(mask).find(b";", close_paren + 1, open_brace if open_brace >= 0 else None)
        if open_brace < 0 or semicolon >= 0:
            continue
        close_brace = _matching(mask, open_brace, 123, 125)
        if close_brace is None:
            continue
        start = match.start("prefix")
        end = close_brace + 1
        normalized = re.sub(rb"\s+", b" ", bytes(mask[open_brace + 1 : close_brace]).strip())
        item_span = span(source, start, end)
        results.append(
            {
                "symbol": match.group("name").decode("ascii"),
                "visibility": "public"
                if match.group("prefix").lstrip().startswith(b"pub")
                else "private",
                "file": row["file"],
                "kind": "function",
                "span": item_span,
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
    functions = [fact for fact in function_facts(row) if fact["visibility"] == "public"]
    results = list(functions)
    for match in DECLARATION_RE.finditer(mask):
        if _cfg(match.group("attrs")):
            continue
        kind = match.group("kind").decode("ascii")
        name = match.group("name").decode("ascii")
        start = match.start("visibility")
        if kind in {"struct", "enum", "trait"}:
            open_brace = bytes(mask).find(b"{", match.end("name"))
            close_brace = _matching(mask, open_brace, 123, 125) if open_brace >= 0 else None
            end = close_brace + 1 if close_brace is not None else match.end("name")
        else:
            semicolon = bytes(mask).find(b";", match.end("name"))
            end = semicolon + 1 if semicolon >= 0 else match.end("name")
        results.append(
            {
                "symbol": name,
                "visibility": "public",
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
    return True


def terminal_return_code(snapshot: dict[str, Any]) -> int:
    if snapshot["status"] == "failed":
        return 1
    if snapshot["status"] != "partial":
        return 0
    failure = str(snapshot.get("failure_kind", ""))
    if failure.endswith(("-tool-missing", "-version-too-old")) or failure in {
        "cargo-project-incomplete",
        "no-eligible-rust-files",
    }:
        return 2
    return 0


def collect_snapshot(
    project_root: Path,
    targets: Iterable[str],
    *,
    rustc: Path,
    cargo: Path,
    rustfmt: Path,
) -> dict[str, Any]:
    """Collect one immutable Rust project snapshot for a consumer."""
    root = project_root.resolve()
    inventory, errors = _inventory(root, targets)
    manifest, manifest_hash = _manifest(inventory)
    tools = {
        "rustc": _probe(rustc, "rustc", root),
        "cargo": _probe(cargo, "cargo", root),
        "rustfmt": _probe(rustfmt, "rustfmt", root),
    }
    snapshot: dict[str, Any] = {
        "language": "rust",
        "analyzer": "rust-lexical-filesystem-facts-v1",
        "status": "complete",
        "inventory": inventory,
        "errors": errors,
        "tools": tools,
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_hash,
        "source_preserved": True,
        "limits": [
            "no macro_rules or procedural-macro expansion",
            "no build.rs output, OUT_DIR, include!, or environment inference",
            "no cfg projection beyond the exact all-target/all-feature Cargo gate",
            "no name/type resolution, trait dispatch, monomorphization, unsafe, or FFI claims",
        ],
    }
    bad = [tool for tool in tools.values() if tool["state"] != "ready"]
    if bad:
        first = bad[0]
        snapshot.update(
            status="failed" if first["state"] == "failed" else "partial",
            failure_kind=first["failure_kind"],
            summary={
                "discovered": len(inventory),
                "eligible": 0,
                "excluded": 0,
                "failed": len(bad),
            },
        )
        return snapshot
    if not (root / "Cargo.toml").is_file() or not (root / "Cargo.lock").is_file():
        snapshot.update(
            status="partial",
            failure_kind="cargo-project-incomplete",
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot

    cargo_path = tools["cargo"]["path"]
    with tempfile.TemporaryDirectory(prefix="rust-lexical-facts-") as temporary:
        state = Path(temporary)
        env = os.environ.copy()
        env.update(
            CARGO_NET_OFFLINE="true",
            CARGO_TARGET_DIR=str(state / "target"),
            CARGO_HOME=str(state / "cargo-home"),
            RUSTC=tools["rustc"]["path"],
        )
        metadata_command = [
            cargo_path,
            "metadata",
            "--format-version",
            "1",
            "--locked",
            "--offline",
            "--no-deps",
        ]
        metadata_result = _run(metadata_command, root, env=env)
        check_command = [
            cargo_path,
            "check",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ]
        check_result = (
            _run(check_command, root, env=env) if metadata_result.returncode == 0 else None
        )
    snapshot["cargo_metadata"] = {
        "command": "cargo metadata --format-version 1 --locked --offline --no-deps",
        "returncode": metadata_result.returncode,
    }
    if metadata_result.returncode:
        snapshot.update(
            status="failed",
            failure_kind="cargo-metadata-failed",
            native_detail=(metadata_result.stderr or metadata_result.stdout).strip()[-4000:],
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot
    try:
        metadata = json.loads(metadata_result.stdout)
    except json.JSONDecodeError as exc:
        snapshot.update(
            status="failed",
            failure_kind="cargo-metadata-invalid",
            native_detail=str(exc),
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot
    snapshot["cargo_metadata"]["packages"] = [
        {"name": package["name"], "targets": [target["name"] for target in package["targets"]]}
        for package in metadata.get("packages", [])
    ]
    snapshot["cargo_check"] = {
        "command": "cargo check --locked --offline --workspace --all-targets --all-features",
        "returncode": check_result.returncode if check_result else 1,
    }
    if check_result is None or check_result.returncode:
        detail = (
            "metadata prevented cargo check"
            if check_result is None
            else (check_result.stderr or check_result.stdout).strip()[-4000:]
        )
        snapshot.update(
            status="failed",
            failure_kind="cargo-check-failed",
            native_detail=detail,
            summary={"discovered": len(inventory), "eligible": 0, "excluded": 0, "failed": 1},
        )
        return snapshot

    eligible = [row for row in inventory if row["role"] == "candidate" and row["selected"]]
    for row in eligible:
        result = _run(
            [
                tools["rustfmt"]["path"],
                "--edition",
                "2024",
                "--emit",
                "stdout",
                "--config",
                "skip_children=true",
                str(row["_path"]),
            ],
            root,
        )
        if result.returncode:
            row.update(
                role="failed",
                reason="syntax-error"
                if "error:" in (result.stderr or result.stdout).casefold()
                else "rustfmt-failed",
                detail=(result.stderr or result.stdout).strip(),
            )
            errors.append(f"{row['file']}:{row['reason']}")
            continue
        mask, lexical_errors = lexical_mask(row["_source"])
        if lexical_errors:
            row.update(role="failed", reason="lexical-error", detail="; ".join(lexical_errors))
            errors.append(f"{row['file']}:lexical-error")
            continue
        row.update(role="eligible", native_syntax="rustfmt-parse", _mask=mask)

    completed = sum(row["role"] == "eligible" for row in inventory)
    excluded = sum(row["role"] == "excluded" for row in inventory)
    failed = sum(row["role"] == "failed" for row in inventory) + sum(
        error.startswith("target-") for error in errors
    )
    if failed:
        snapshot["status"] = "partial"
    elif not eligible:
        snapshot.update(status="partial", failure_kind="no-eligible-rust-files")
    snapshot["errors"] = errors
    snapshot["summary"] = {
        "discovered": len(inventory),
        "eligible": completed,
        "excluded": excluded,
        "failed": failed,
    }
    return snapshot
