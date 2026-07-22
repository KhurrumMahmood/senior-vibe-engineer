#!/usr/bin/env python3
"""Launch the skill-local Go semantic-duplication analyzer atomically."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


MINIMUM_GO = (1, 22)


class SemanticGoError(ValueError):
    """Known invalid or unsupported analyzer condition."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_inside(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    if not _inside(root, candidate):
        raise SemanticGoError(f"{label} must stay inside project root: {supplied}")
    _reject_symlinks(root, candidate, label)
    resolved = candidate.resolve()
    if not _inside(root, resolved):
        raise SemanticGoError(f"{label} must stay inside project root: {supplied}")
    return resolved


def _reject_symlinks(root: Path, candidate: Path, label: str) -> None:
    current = root
    for part in candidate.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise SemanticGoError(f"{label} must not traverse a symbolic link: {candidate}")


def _go_tool(supplied: str | None) -> tuple[Path, str]:
    found = supplied or shutil.which("go")
    if not found:
        raise SemanticGoError("Go toolchain is unavailable on PATH")
    tool = Path(found)
    try:
        result = subprocess.run(
            [str(tool), "version"], capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise SemanticGoError(f"cannot run Go toolchain: {error}") from error
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise SemanticGoError(f"cannot determine Go version: {rendered}")
    if (int(match.group(1)), int(match.group(2))) < MINIMUM_GO:
        raise SemanticGoError(f"Go analyzer requires Go >= 1.22; found {rendered}")
    return tool, rendered


def _replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    had_destination = destination.exists()
    if had_destination:
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if had_destination and backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--go-executable")
    args = parser.parse_args(argv)
    staged: Path | None = None
    try:
        logical_root = Path(os.path.abspath(args.project_root))
        if not logical_root.is_dir() or logical_root.is_symlink():
            raise SemanticGoError(f"project root is not a directory: {args.project_root}")
        root = logical_root.resolve()
        target = _resolve_inside(root, args.target, "target")
        if not target.exists() or target.is_symlink():
            raise SemanticGoError(f"target must be an existing non-symlink path: {args.target}")
        report = _resolve_inside(root, args.report_dir, "report directory")
        allowed = root / "reports" / "semantic-duplication"
        if report == allowed or not _inside(allowed, report):
            raise SemanticGoError(
                "report directory must stay beneath reports/semantic-duplication/"
            )
        go, version = _go_tool(args.go_executable)
        report.parent.mkdir(parents=True, exist_ok=True)
        staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
        helper = Path(__file__).with_name("detect_go_semantic.go")
        result = subprocess.run(
            [
                str(go),
                "run",
                str(helper),
                "--target",
                str(target),
                "--project-root",
                str(root),
                "--report-dir",
                str(staged),
                "--go-executable",
                str(go),
            ],
            cwd=root,
            env={**os.environ, "GOTOOLCHAIN": "local"},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise SemanticGoError(detail)
        _replace_directory(staged, report)
        staged = None
    except (SemanticGoError, OSError) as error:
        if staged is not None and staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[detect_go_semantic] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[detect_go_semantic] wrote {report} ({version})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
