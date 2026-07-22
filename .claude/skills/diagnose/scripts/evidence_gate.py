#!/usr/bin/env python3
"""Validate a /diagnose evidence manifest without repository imports.

This is the selected-closure check for the installed skill.  It implements the
only gate the skill invokes: every ``evidence_required`` token in sibling
frontmatter must name an existing file in the scan manifest.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _required_tokens(skill_file: Path) -> list[str]:
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read skill file: {exc}") from exc
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"missing frontmatter in {skill_file}")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "evidence_required":
            value = value.strip()
            if not (value.startswith("[") and value.endswith("]")):
                raise ValueError("evidence_required must be an inline list")
            return [
                token.strip().strip("'\"")
                for token in value[1:-1].split(",")
                if token.strip()
            ]
    raise ValueError("skill frontmatter has no evidence_required tokens")


def check(skill_file: Path, scan_dir: Path) -> int:
    try:
        required = _required_tokens(skill_file)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not scan_dir.is_dir():
        print(f"error: scan-dir not found: {scan_dir}", file=sys.stderr)
        return 2
    manifest_path = scan_dir / "evidence.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no manifest found at {manifest_path}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, UnicodeError) as exc:
        print(f"error: malformed manifest at {manifest_path}: {exc}", file=sys.stderr)
        return 2
    evidence = manifest.get("evidence") if isinstance(manifest, dict) else None
    evidence = evidence if isinstance(evidence, dict) else {}
    rows: list[tuple[str, str, str | None]] = []
    for token in required:
        declared = evidence.get(token)
        if not isinstance(declared, str) or not declared.strip():
            rows.append((token, "missing_token", None))
            continue
        path = Path(declared)
        if not path.is_absolute():
            path = scan_dir / path
        rows.append((token, "ok" if path.is_file() else "missing_file", declared))
    for token, status, declared in rows:
        if status == "ok":
            print(f"  [ok] {token} -> {declared}")
        elif status == "missing_token":
            print(f"  [FAIL] {token} -> MISSING (no path declared in manifest)")
        else:
            print(f"  [FAIL] {token} -> DECLARED but file not found at {declared}")
    passed = sum(status == "ok" for _, status, _ in rows)
    print(f"{'OK' if passed == len(rows) else 'FAIL'}: {passed}/{len(rows)} required evidence shapes present.")
    return 0 if passed == len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--skill-file", required=True, type=Path)
    check_parser.add_argument("--scan-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    return check(args.skill_file, args.scan_dir)


if __name__ == "__main__":
    raise SystemExit(main())
