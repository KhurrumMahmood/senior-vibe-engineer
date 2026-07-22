#!/usr/bin/env python3
"""Verify a staged exact-field Java guard and its native fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def _authority(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        authority = payload["accepted_authority"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"cannot read staged authority: {error}") from error
    if not isinstance(authority, dict) or not isinstance(authority.get("package_name"), str) or not authority["package_name"]:
        raise ValueError("staged authority lacks a package name")
    return authority


def _host(base: Path, label: str, source: Path, authority: dict) -> tuple[Path, Path]:
    root = base / label
    destination = root / "src" / "main" / "java" / Path(*authority["package_name"].split(".")) / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return root, destination


def _native(root: Path) -> subprocess.CompletedProcess[str]:
    classes = root / "classes"
    return subprocess.run(
        ["javac", "--release", "17", "-proc:none", "-d", str(classes), *[str(path) for path in root.rglob("*.java")]],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _guard(rule: Path, root: Path, source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(rule), "--project-root", str(root), str(source)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--bad", required=True)
    parser.add_argument("--good", required=True)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args(argv)
    try:
        rule = Path(args.rule).resolve()
        authority = _authority(Path(args.authority).resolve())
        if not rule.is_file():
            raise ValueError("staged guard is missing")
        with tempfile.TemporaryDirectory(dir=Path(args.project_root)) as temporary:
            base = Path(temporary)
            bad_root, bad_source = _host(base, "bad", Path(args.bad).resolve(), authority)
            good_root, good_source = _host(base, "good", Path(args.good).resolve(), authority)
            bad_native = _native(bad_root)
            good_native = _native(good_root)
            bad = _guard(rule, bad_root, bad_source)
            good = _guard(rule, good_root, good_source)
    except (ValueError, OSError) as error:
        print(f"VERIFY_ERROR={error}")
        return 1
    print(
        f"BAD_NATIVE_RC={bad_native.returncode}, GOOD_NATIVE_RC={good_native.returncode}, "
        f"BAD_RC={bad.returncode}, GOOD_RC={good.returncode}"
    )
    if bad_native.returncode == 0 and good_native.returncode == 0 and bad.returncode == 1 and good.returncode == 0:
        print("PASS: BAD_RC=1, GOOD_RC=0, native Java fixtures compile")
        return 0
    if bad.stdout or bad.stderr:
        print(f"BAD_OUTPUT:\n{bad.stdout}{bad.stderr}")
    if good.stdout or good.stderr:
        print(f"GOOD_OUTPUT:\n{good.stdout}{good.stderr}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
