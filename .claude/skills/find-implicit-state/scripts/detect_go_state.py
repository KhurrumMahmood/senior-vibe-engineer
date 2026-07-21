#!/usr/bin/env python3
"""Launch the self-contained Go implicit-state analyzer."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


MINIMUM_GO = (1, 22)


class GoStateError(ValueError):
    """Known invalid or unsupported analyzer condition."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_inside(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = (raw if raw.is_absolute() else root / raw).resolve()
    if not _inside(root, candidate):
        raise GoStateError(f"{label} must stay inside project root: {supplied}")
    return candidate


def _go_tool(supplied: str | None) -> tuple[Path, str]:
    found = supplied or shutil.which("go")
    if not found:
        raise GoStateError("Go toolchain is unavailable on PATH")
    tool = Path(found)
    result = subprocess.run([str(tool), "version"], capture_output=True, text=True, check=False)
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise GoStateError(f"cannot determine Go version: {rendered}")
    if (int(match.group(1)), int(match.group(2))) < MINIMUM_GO:
        raise GoStateError(f"Go analyzer requires Go >= 1.22; found {rendered}")
    return tool, rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--go-executable")
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise GoStateError(f"project root is not a directory: {args.project_root}")
        target = _resolve_inside(root, args.target, "target")
        if not target.exists() or target.is_symlink():
            raise GoStateError(f"target must be an existing non-symlink path: {args.target}")
        output = _resolve_inside(root, args.output, "output")
        allowed = root / "reports" / "implicit-state"
        if output == allowed or not _inside(allowed, output):
            raise GoStateError("output must stay beneath reports/implicit-state/")
        go, version = _go_tool(args.go_executable)
        helper = Path(__file__).with_name("detect_go_state.go")
        result = subprocess.run(
            [str(go), "run", str(helper), "--target", str(target),
             "--project-root", str(root), "--output", str(output),
             "--go-executable", str(go)],
            cwd=root,
            env={**os.environ, "GOTOOLCHAIN": "local"},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise GoStateError(detail)
    except (GoStateError, OSError) as error:
        print(f"[detect_go_state] ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[detect_go_state] wrote {output} ({version})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
