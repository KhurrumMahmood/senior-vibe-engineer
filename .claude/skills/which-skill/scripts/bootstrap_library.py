#!/usr/bin/env python3
"""Materialize engineering-skills outside agent discovery directories."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_SOURCE = "https://github.com/KhurrumMahmood/senior-vibe-engineer"  # host-ref-allow: public distribution repository


def default_library_root(project_root: Path) -> Path:
    return project_root.parent / ".engineering-skills" / project_root.name


def _library_errors(root: Path) -> list[str]:
    required = (
        root / ".claude" / "skills" / "which-skill" / "SKILL.md",
        root / ".claude" / "skills" / "which-shape" / "SKILL.md",
        root / ".claude" / "skills" / "which-cleanup" / "SKILL.md",
        root / "scripts",
    )
    return [str(path) for path in required if not path.exists()]


def materialize(*, source: str, destination: Path) -> tuple[Path, bool]:
    destination = destination.resolve()
    if destination.exists() or destination.is_symlink():
        errors = _library_errors(destination)
        if errors:
            raise ValueError(
                f"existing library is incomplete at {destination}; missing: {', '.join(errors)}"
            )
        return destination, False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    shutil.rmtree(temporary)
    try:
        result = subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--no-tags", source, str(temporary)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "git clone failed"
            raise ValueError(detail)
        errors = _library_errors(temporary)
        if errors:
            raise ValueError(f"source is not an engineering-skills library; missing: {', '.join(errors)}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination, True


def setup_runtime(*, library_root: Path, python: str | None) -> str:
    helper = Path(__file__).with_name("setup_runtime.py")
    command = [
        sys.executable,
        str(helper),
        "--project-root",
        str(library_root),
        "--no-hooks",
    ]
    if python:
        command.extend(["--python", python])
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "runtime setup failed"
        raise ValueError(detail)
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--library-root", type=Path)
    parser.add_argument("--python", help="exact Python executable for the library venv")
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="materialize the library without creating its Python runtime",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    library_root = args.library_root or default_library_root(project_root)
    if not library_root.is_absolute():
        library_root = project_root / library_root
    try:
        root, created = materialize(source=args.source, destination=library_root)
        runtime_summary = None
        if not args.skip_runtime:
            runtime_summary = setup_runtime(library_root=root, python=args.python)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    state = "created" if created else "already available"
    print(f"engineering-skills library {state}: {root}")
    if runtime_summary:
        print(runtime_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
