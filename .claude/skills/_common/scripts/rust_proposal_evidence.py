#!/usr/bin/env python3
"""Shared, read-only Cargo evidence for bounded Rust proposal adapters.

This module owns only facts both proposal families need: safe project paths,
stable tool probes, locked/offline Cargo project validation, exact smoke, Rust
source inventory, and artifact lifecycle replacement. It deliberately does
not select a boundary, design a folder layout, or make compatibility claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


MINIMUM_RUST = (1, 85, 0)
SKIP_PARTS = {".git", ".agents", ".claude", "target", "reports", "vendor"}
DECLARATION = re.compile(
    r"(?m)^\s*(?P<visibility>pub(?:\s*\([^)]*\))?\s+)?"
    r"(?P<kind>fn|struct|enum|trait|type|const|static|mod)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
MODULE_DECLARATION = re.compile(
    r"(?m)^\s*(?P<visibility>pub(?:\s*\([^)]*\))?\s+)?mod\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;"
)


class EvidenceFailure(Exception):
    def __init__(
        self,
        status: str,
        kind: str,
        message: str,
        exit_code: int = 2,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.message = message
        self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message


def _version_tuple(text: str) -> tuple[int, int, int]:
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text)
    if match is None:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def _offline_env() -> dict[str, str]:
    return {
        **os.environ,
        "CARGO_NET_OFFLINE": "true",
        "CARGO_TARGET_DIR": os.environ.get(
            "RUST_PROPOSAL_TARGET_DIR",
            str(Path(tempfile.gettempdir()) / "engineering-skills-rust-proposals-target"),
        ),
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
    }


def _run(root: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        env=_offline_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def _probe(command: list[str], *, kind: str, enforce_rust_version: bool = True) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None:
        raise EvidenceFailure(
            "partial", f"{kind}_missing", f"{command[0]} was not found on PATH", 0
        )
    result = subprocess.run([executable, *command[1:]], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise EvidenceFailure(
            "partial",
            f"{kind}_probe_failed",
            (result.stderr or result.stdout).strip(),
            0,
        )
    version = (result.stdout or result.stderr).strip()
    if enforce_rust_version and _version_tuple(version) < MINIMUM_RUST:
        minimum = ".".join(str(item) for item in MINIMUM_RUST)
        raise EvidenceFailure(
            "partial",
            f"{kind}_too_old",
            f"{kind} must be at least {minimum}: {version}",
            0,
        )
    return {"path": executable, "version": version}


def probe_tools() -> dict[str, Any]:
    cargo = _probe(["cargo", "--version"], kind="cargo")
    rustc = _probe(["rustc", "--version"], kind="rustc")
    rustfmt = _probe(["rustfmt", "--version"], kind="rustfmt", enforce_rust_version=False)
    clippy_result = subprocess.run(
        [cargo["path"], "clippy", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if clippy_result.returncode != 0:
        raise EvidenceFailure(
            "partial",
            "clippy_missing",
            (clippy_result.stderr or clippy_result.stdout).strip(),
            0,
        )
    return {
        "cargo": cargo,
        "rustc": rustc,
        "rustfmt": rustfmt,
        "clippy": {"version": clippy_result.stdout.strip()},
        "minimum_rust": "1.85.0",
    }


def safe_project_path(root: Path, supplied: str | Path, *, must_exist: bool = True) -> Path:
    root = root.resolve()
    candidate = Path(supplied)
    if not candidate.is_absolute():
        candidate = root / candidate
    normalized = Path(os.path.abspath(candidate))
    try:
        normalized.relative_to(root)
    except ValueError as exc:
        raise EvidenceFailure(
            "failed", "unsafe_path", f"path must stay inside project root: {supplied}"
        ) from exc
    cursor = root
    for part in normalized.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise EvidenceFailure(
                "failed", "symlink_path", f"symbolic link is not allowed: {cursor}"
            )
        if not cursor.exists():
            break
    if must_exist and not normalized.exists():
        raise EvidenceFailure("failed", "path_missing", f"path does not exist: {supplied}")
    return normalized


def artifact_path(root: Path, supplied: str | Path) -> Path:
    return safe_project_path(root, supplied, must_exist=False)


def source_fingerprints(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.suffix != ".rs" and path.name not in {"Cargo.toml", "Cargo.lock"}:
            continue
        relative = path.relative_to(root).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _semantic_text(text: str) -> str:
    """Mask comments and literals while preserving offsets and line breaks."""
    excluded: list[tuple[int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if text.startswith("//", index):
            end = text.find("\n", index)
            end = length if end < 0 else end
            excluded.append((index, end))
            index = end
            continue
        if text.startswith("/*", index):
            depth = 1
            cursor = index + 2
            while cursor < length and depth:
                if text.startswith("/*", cursor):
                    depth += 1
                    cursor += 2
                elif text.startswith("*/", cursor):
                    depth -= 1
                    cursor += 2
                else:
                    cursor += 1
            excluded.append((index, cursor))
            index = cursor
            continue
        raw = re.match(r'(?:br|r)(#+)?"', text[index:])
        if raw:
            hashes = raw.group(1) or ""
            cursor = index + raw.end()
            closing = '"' + hashes
            found = text.find(closing, cursor)
            end = length if found < 0 else found + len(closing)
            excluded.append((index, end))
            index = end
            continue
        quote_start = None
        if text.startswith('b"', index):
            quote_start = index + 1
        elif char == '"':
            quote_start = index
        if quote_start is not None:
            cursor = quote_start + 1
            escaped = False
            while cursor < length:
                current = text[cursor]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    cursor += 1
                    break
                cursor += 1
            excluded.append((index, cursor))
            index = cursor
            continue
        if char == "'":
            closing = text.find("'", index + 1)
            if closing >= 0 and closing - index <= 8:
                excluded.append((index, closing + 1))
                index = closing + 1
                continue
        index += 1
    masked = list(text)
    for start, end in excluded:
        for offset in range(start, end):
            if masked[offset] != "\n":
                masked[offset] = " "
    return "".join(masked)


def _unsupported(semantic: str) -> list[str]:
    checks = (
        ("cfg_variants", r"#\s*\[\s*cfg(?:_attr)?\b"),
        ("path_attribute", r"#\s*\[\s*path\s*="),
        ("include_macro", r"\binclude(?:_str|_bytes)?\s*!"),
        ("declarative_macro", r"\bmacro_rules\s*!"),
        ("unsafe_contract", r"\bunsafe\b"),
        ("ffi_contract", r'\bextern\s+"'),
    )
    return [name for name, pattern in checks if re.search(pattern, semantic)]


def file_facts(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceFailure(
            "partial", "non_utf8_rust", f"Rust source is not UTF-8: {relative}", 0
        ) from exc
    first_lines = "\n".join(text.splitlines()[:5]).lower()
    generated = "@generated" in first_lines or "automatically generated" in first_lines
    test_like = path.name.endswith("_test.rs") or "tests" in path.relative_to(root).parts
    semantic = _semantic_text(text)
    declarations = [
        {
            "name": match.group("name"),
            "kind": match.group("kind"),
            "visibility": (match.group("visibility") or "private").strip(),
            "public": (match.group("visibility") or "").strip() == "pub",
            "line": _line_number(text, match.start()),
        }
        for match in DECLARATION.finditer(semantic)
    ]
    modules = [
        {
            "name": match.group("name"),
            "visibility": (match.group("visibility") or "private").strip(),
            "line": _line_number(text, match.start()),
        }
        for match in MODULE_DECLARATION.finditer(semantic)
    ]
    return {
        "path": relative,
        "text": text,
        "semantic_text": semantic,
        "generated": generated,
        "test_like": test_like,
        "declarations": declarations,
        "module_declarations": modules,
        "unsupported": _unsupported(semantic),
    }


def collect_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    tools = probe_tools()
    before = source_fingerprints(root)
    command = [
        "cargo",
        "metadata",
        "--locked",
        "--offline",
        "--format-version",
        "1",
    ]
    metadata_result = _run(root, command)
    if metadata_result.returncode != 0:
        raise EvidenceFailure(
            "failed",
            "cargo_metadata_failed",
            metadata_result.stderr.strip() or "cargo metadata failed",
        )
    try:
        metadata = json.loads(metadata_result.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceFailure("failed", "cargo_metadata_invalid", str(exc)) from exc
    packages = []
    for package in metadata.get("packages", []):
        manifest = Path(package["manifest_path"])
        try:
            manifest_relative = manifest.relative_to(root).as_posix()
        except ValueError:
            continue
        targets = []
        for target in package.get("targets", []):
            source = Path(target["src_path"])
            if not source.is_relative_to(root):
                continue
            targets.append(
                {
                    "name": target["name"],
                    "kind": target["kind"],
                    "src_path": source.relative_to(root).as_posix(),
                }
            )
        packages.append(
            {
                "name": package["name"],
                "version": package["version"],
                "manifest_path": manifest_relative,
                "edition": package.get("edition"),
                "rust_version": package.get("rust_version"),
                "targets": targets,
            }
        )
    files = []
    for path in sorted(root.rglob("*.rs")):
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_PARTS for part in relative_parts) or path.is_symlink():
            continue
        files.append(file_facts(root, path))
    after = source_fingerprints(root)
    if before != after:
        raise EvidenceFailure(
            "failed",
            "metadata_mutated_source",
            "Cargo metadata changed tracked source inputs",
        )
    workspace = Path(metadata["workspace_root"]).relative_to(root).as_posix() or "."
    return {
        "schema_version": "rust-proposal-project-evidence-v1",
        "tools": tools,
        "workspace_root": workspace,
        "packages": packages,
        "files": files,
        "source_fingerprints": before,
        "metadata_command": " ".join(command),
    }


def run_native(
    root: Path,
    *,
    smoke_package: str | None = None,
    smoke_expected: str | None = None,
) -> dict[str, Any]:
    before = source_fingerprints(root)
    commands = [
        [
            "cargo",
            "check",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
        ],
        [
            "cargo",
            "test",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
        ],
        [
            "cargo",
            "clippy",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--locked",
            "--offline",
            "--",
            "-D",
            "warnings",
        ],
        ["cargo", "fmt", "--all", "--", "--check"],
    ]
    results = []
    for command in commands:
        result = _run(root, command)
        results.append(
            {
                "command": " ".join(command),
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
        if result.returncode != 0:
            raise EvidenceFailure(
                "failed",
                f"native_{command[1]}_failed",
                result.stderr.strip() or result.stdout.strip() or f"{' '.join(command)} failed",
            )
    smoke: dict[str, Any] | None = None
    if smoke_package is not None:
        if smoke_expected is None:
            raise EvidenceFailure(
                "failed",
                "smoke_expected_required",
                "--smoke-expected is required with --smoke-package",
            )
        command = [
            "cargo",
            "run",
            "-p",
            smoke_package,
            "--locked",
            "--offline",
            "--quiet",
        ]
        result = _run(root, command)
        stdout = result.stdout.strip()
        smoke = {
            "command": " ".join(command),
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": result.stderr.strip(),
        }
        if result.returncode != 0 or stdout != smoke_expected:
            raise EvidenceFailure(
                "failed",
                "exact_smoke_failed",
                f"exact smoke expected {smoke_expected!r}, got {stdout!r}",
            )
    after = source_fingerprints(root)
    if before != after:
        raise EvidenceFailure(
            "failed", "native_checks_mutated_source", "native checks changed source inputs"
        )
    return {
        "status": "passed",
        "commands": [
            "cargo metadata --locked --offline --format-version 1",
            *[row["command"] for row in results],
        ],
        "results": results,
        "smoke": smoke,
        "source_preserved": True,
    }


def write_artifacts(
    root: Path,
    inspection: str | Path,
    proposal: str | Path,
    payload: dict[str, Any],
    markdown: str,
) -> None:
    targets = (
        (
            artifact_path(root, inspection),
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        ),
        (artifact_path(root, proposal), markdown),
    )
    for path, contents in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
