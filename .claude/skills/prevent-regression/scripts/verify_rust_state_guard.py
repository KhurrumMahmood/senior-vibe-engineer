#!/usr/bin/env python3
"""Prove a staged Rust exact-field guard with locked/offline native checks."""

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


MINIMUM_RUST = (1, 85)


class RustGuardVerifyError(ValueError):
    """Invalid stage, native-tool failure, or unproved regression boundary."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    if candidate.is_symlink():
        raise RustGuardVerifyError(f"{label} must not be a symbolic link: {supplied}")
    return candidate.resolve(strict=False)


def _load_stage(path: Path) -> tuple[dict[str, Any], Path]:
    if not path.is_dir() or path.is_symlink():
        raise RustGuardVerifyError("staged guard directory is missing")
    metadata_path = path / "authority.json"
    guard = path / "guard/exact_field_type_guard.rs"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RustGuardVerifyError(f"cannot read staged authority: {error}") from error
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") != "rust-state-guard-v1"
        or metadata.get("status") != "staged"
        or metadata.get("outcome") != "exact_native_guard"
        or not guard.is_file()
        or guard.is_symlink()
    ):
        raise RustGuardVerifyError("staged Rust guard closure is malformed")
    if metadata.get("guard_sha256") != hashlib.sha256(guard.read_bytes()).hexdigest():
        raise RustGuardVerifyError("staged Rust guard source is stale or modified")
    return metadata, guard


def _probe(tool: str, label: str) -> dict[str, Any]:
    path = Path(tool)
    executable = str(path.resolve()) if path.is_file() else shutil.which(tool)
    if not executable:
        raise RustGuardVerifyError(f"Rust native tool is missing: {label}")
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=False, timeout=30
    )
    rendered = (result.stdout + result.stderr).strip()
    match = re.search(r"\b(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise RustGuardVerifyError(f"Rust native tool probe failed: {label}")
    if label in {"cargo", "rustc"} and (int(match.group(1)), int(match.group(2))) < MINIMUM_RUST:
        raise RustGuardVerifyError(f"Rust >= {MINIMUM_RUST[0]}.{MINIMUM_RUST[1]} is required")
    return {"path": executable, "version": rendered}


def _copy_project(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", "reports", "target"),
        symlinks=True,
    )


def _source_hashes(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "reports", "target"} for part in relative.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _run(command: list[str], root: Path, target: Path) -> dict[str, Any]:
    env = {**os.environ, "CARGO_NET_OFFLINE": "true", "CARGO_TARGET_DIR": str(target)}
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _native(
    root: Path, tools: dict[str, dict[str, Any]], target: Path
) -> dict[str, dict[str, Any]]:
    cargo = tools["cargo"]["path"]
    commands = {
        "cargo_metadata": [
            cargo,
            "metadata",
            "--format-version",
            "1",
            "--locked",
            "--offline",
            "--no-deps",
        ],
        "cargo_check": [
            cargo,
            "check",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ],
        "cargo_test": [
            cargo,
            "test",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
        ],
        "cargo_clippy": [
            cargo,
            "clippy",
            "--locked",
            "--offline",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--",
            "-D",
            "warnings",
        ],
        "cargo_fmt": [cargo, "fmt", "--all", "--", "--check"],
    }
    return {name: _run(command, root, target / name) for name, command in commands.items()}


def _install_guard(root: Path, metadata: dict[str, Any], source: Path) -> Path:
    destination = root / metadata["guard"]["test_destination"]
    if (
        not _inside(root.resolve(), destination.resolve(strict=False))
        or destination.suffix != ".rs"
    ):
        raise RustGuardVerifyError("staged guard destination escapes the verified project")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _seed_regression(root: Path, metadata: dict[str, Any]) -> Path:
    authority, enum = metadata["authority"], metadata["enum"]
    relative = Path(authority["declaration_file"])
    source = (root / relative).resolve(strict=False)
    if (
        relative.is_absolute()
        or source.suffix != ".rs"
        or source.is_symlink()
        or not _inside(root.resolve(), source)
        or not source.is_file()
    ):
        raise RustGuardVerifyError("staged authority source escapes the verified project")
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    owner_pattern = re.compile(rf"\bstruct\s+{re.escape(authority['owner'])}\b")
    field_pattern = re.compile(
        rf"^(?P<prefix>\s*pub\s+{re.escape(authority['field'])}\s*:\s*){re.escape(enum['type_name'])}(?P<tail>\s*,?\s*)$"
    )
    in_owner = False
    depth = 0
    replaced = 0
    for index, line in enumerate(lines):
        content = line.rstrip("\n")
        if not in_owner and owner_pattern.search(content):
            in_owner = True
        if in_owner:
            match = field_pattern.match(content)
            if match:
                newline = "\n" if line.endswith("\n") else ""
                lines[index] = f"{match.group('prefix')}String{match.group('tail')}{newline}"
                replaced += 1
            depth += content.count("{") - content.count("}")
            if depth <= 0 and "}" in content:
                in_owner = False
    if replaced != 1:
        raise RustGuardVerifyError("could not seed exactly one buildable exact-field regression")
    source.write_text("".join(lines), encoding="utf-8")
    return source


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}."
    ) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rustfmt", default="rustfmt")
    parser.add_argument("--cargo-clippy", default="cargo-clippy")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise RustGuardVerifyError("project root must be a non-symlink directory")
        output = _resolve(root, args.output, "verification output")
        allowed = root / "reports" / "prevent-regression"
        if not _inside(allowed, output):
            raise RustGuardVerifyError(
                "verification output must stay beneath reports/prevent-regression/"
            )
        output.unlink(missing_ok=True)
        metadata, guard = _load_stage(Path(args.stage).resolve())
        tools = {
            "cargo": _probe(args.cargo, "cargo"),
            "rustc": _probe(args.rustc, "rustc"),
            "rustfmt": _probe(args.rustfmt, "rustfmt"),
            "cargo_clippy": _probe(args.cargo_clippy, "cargo-clippy"),
        }
        before = _source_hashes(root)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            clean_root, regression_root = base / "clean", base / "regression"
            _copy_project(root, clean_root)
            _copy_project(root, regression_root)
            clean_guard = _install_guard(clean_root, metadata, guard)
            clean_native = _native(clean_root, tools, base / "targets-clean")
            if any(row["returncode"] for row in clean_native.values()):
                failed = next(name for name, row in clean_native.items() if row["returncode"])
                raise RustGuardVerifyError(f"clean native verification failed: {failed}")
            _seed_regression(regression_root, metadata)
            without_guard = _run(
                [
                    tools["cargo"]["path"],
                    "check",
                    "--locked",
                    "--offline",
                    "--workspace",
                    "--all-targets",
                    "--all-features",
                ],
                regression_root,
                base / "targets-regression-without",
            )
            if without_guard["returncode"] != 0:
                raise RustGuardVerifyError(
                    "seeded regression is not independently buildable without the guard"
                )
            regression_guard = _install_guard(regression_root, metadata, guard)
            with_guard = _run(
                [
                    tools["cargo"]["path"],
                    "test",
                    "--locked",
                    "--offline",
                    "--workspace",
                    "--all-targets",
                    "--all-features",
                    "--no-run",
                ],
                regression_root,
                base / "targets-regression-with",
            )
            rendered = with_guard["stdout"] + with_guard["stderr"]
            guard_caught = with_guard["returncode"] != 0 and regression_guard.name in rendered
            if not guard_caught:
                raise RustGuardVerifyError(
                    "staged guard did not catch the buildable seeded regression"
                )
            authority_source = (clean_root / metadata["authority"]["declaration_file"]).read_text(
                encoding="utf-8"
            )
            unrelated = bool(
                re.search(r"\b(?:state|status|phase)\s*:\s*String\b", authority_source)
            )
            report = {
                "schema_version": "rust-state-guard-verification-v1",
                "language": "rust",
                "status": "complete",
                "outcome": "guard_proved",
                "tools": tools,
                "guard_destination": clean_guard.relative_to(clean_root).as_posix(),
                "clean_native": clean_native,
                "seeded_regression": {
                    "kind": "exact field type reverted from accepted enum to String",
                    "without_guard": without_guard,
                    "with_guard": with_guard,
                    "caught_by_guard": guard_caught,
                },
                "must_not_fire": {
                    "unrelated_string_field": unrelated
                    and all(row["returncode"] == 0 for row in clean_native.values())
                },
                "source_preserved": _source_hashes(root) == before,
                "nonclaims": metadata["nonclaims"],
            }
        if not report["source_preserved"]:
            raise RustGuardVerifyError("verification mutated project source")
        _write_report(output, report)
    except (
        RustGuardVerifyError,
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        subprocess.TimeoutExpired,
    ) as error:
        if output is not None:
            failure = {
                "schema_version": "rust-state-guard-verification-v1",
                "language": "rust",
                "status": "failed",
                "outcome": "unproved",
                "failure": str(error),
            }
            _write_report(output, failure)
        print(f"[verify_rust_state_guard] ERROR: {error}", file=sys.stderr)
        return 2
    print("[verify_rust_state_guard] native exact-field guard proved", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
