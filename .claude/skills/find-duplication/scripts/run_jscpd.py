#!/usr/bin/env python3
"""Run the pinned TypeScript lexical detector without a network fallback.

The scan copies only eligible TypeScript source into a disposable staging
directory, then invokes ``jscpd@4.0.5`` through the stock npm cache in offline
mode.  This keeps generated, tests, declarations, and vendor files out of the
tool input rather than trying to recover their false positives afterwards.

Exit status 3 means the explicitly pinned jscpd package is not already present
in the selected npm cache.  The scan never reaches the network on its own.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


JSCPD_VERSION = "4.0.5"
DEFAULT_NPM_CACHE = Path(tempfile.gettempdir()) / "engineering-skills-jscpd-cache"
TYPESCRIPT_SUFFIXES = frozenset({".ts", ".tsx"})
SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".next",
        ".venv",
        "__tests__",
        "build",
        "coverage",
        "dist",
        "generated",
        "node_modules",
        "test",
        "tests",
        "vendor",
    }
)


def is_eligible_source(path: Path, target: Path) -> bool:
    """Return whether *path* belongs in the TypeScript lexical scan."""
    if not path.is_file() or path.suffix.lower() not in TYPESCRIPT_SUFFIXES:
        return False
    name = path.name.lower()
    if name.endswith(".d.ts") or ".test." in name or ".spec." in name:
        return False
    if ".generated." in name or ".gen." in name:
        return False
    try:
        ancestors = path.relative_to(target).parts[:-1]
    except ValueError:
        return False
    return not any(part.lower() in SKIP_DIRECTORIES for part in ancestors)


def iter_sources(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if is_eligible_source(target, target.parent) else []
    return sorted(
        path for path in target.rglob("*") if is_eligible_source(path, target)
    )


def stage_sources(target: Path, output: Path) -> tuple[Path, list[Path]]:
    """Copy eligible sources to an output-local input tree and return it."""
    source_root = target if target.is_dir() else target.parent
    staging = output / ".jscpd-input"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    sources = iter_sources(target)
    for source in sources:
        destination = staging / source.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return staging, sources


def _staged_to_source_name(name: str, staging: Path, source_root: Path) -> str:
    """Replace a staged jscpd pathname with the original absolute source path."""
    raw = Path(name)
    try:
        candidate = raw if raw.is_absolute() else (staging / raw)
        relative = candidate.resolve().relative_to(staging.resolve())
    except (OSError, ValueError):
        return name
    return str((source_root / relative).resolve())


def _normalise_report_paths(payload: dict[str, Any], staging: Path, source_root: Path) -> None:
    for duplicate in payload.get("duplicates", []) or []:
        if not isinstance(duplicate, dict):
            continue
        for key in ("firstFile", "secondFile"):
            record = duplicate.get(key)
            if isinstance(record, dict) and isinstance(record.get("name"), str):
                record["name"] = _staged_to_source_name(
                    record["name"], staging, source_root
                )

    formats = ((payload.get("statistics") or {}).get("formats") or {})
    for format_data in formats.values():
        if not isinstance(format_data, dict) or not isinstance(format_data.get("sources"), dict):
            continue
        sources = format_data["sources"]
        format_data["sources"] = {
            _staged_to_source_name(str(name), staging, source_root): value
            for name, value in sources.items()
        }


def _report_schema_error(payload: object) -> str | None:
    """Return why a zero-exit jscpd output is not a usable report."""
    if not isinstance(payload, dict):
        return "report root must be an object"
    duplicates = payload.get("duplicates")
    if not isinstance(duplicates, list):
        return "`duplicates` must be a list"
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return "`statistics` must be an object"
    if not isinstance(statistics.get("formats"), dict):
        return "`statistics.formats` must be an object"
    if not isinstance(statistics.get("total"), dict):
        return "`statistics.total` must be an object"
    for index, duplicate in enumerate(duplicates):
        if not isinstance(duplicate, dict):
            return f"`duplicates[{index}]` must be an object"
        if not isinstance(duplicate.get("format"), str):
            return f"`duplicates[{index}].format` must be a string"
        if type(duplicate.get("lines")) is not int:
            return f"`duplicates[{index}].lines` must be an integer"
        for file_key in ("firstFile", "secondFile"):
            file_data = duplicate.get(file_key)
            if not isinstance(file_data, dict):
                return f"`duplicates[{index}].{file_key}` must be an object"
            if not isinstance(file_data.get("name"), str) or not file_data["name"]:
                return f"`duplicates[{index}].{file_key}.name` must be a nonempty string"
            start, end = file_data.get("start"), file_data.get("end")
            if type(start) is not int or type(end) is not int or start < 1 or end < start:
                return f"`duplicates[{index}].{file_key}` must have a valid line range"
    return None


def build_command(*, npx_bin: str, output: Path, staging: Path) -> list[str]:
    return [
        npx_bin,
        "--offline",
        "--yes",
        f"jscpd@{JSCPD_VERSION}",
        "--format",
        "typescript,tsx",
        "--min-tokens",
        "20",
        "--threshold",
        "100",
        "--reporters",
        "json",
        "--output",
        str(output),
        str(staging),
    ]


def run(
    *,
    target: Path,
    output: Path,
    npm_cache: Path,
    npx_bin: str,
) -> int:
    if not target.is_dir():
        print("error: --target must be a TypeScript source directory", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "jscpd-report.json"
    run_path = output / "run.json"
    for artifact in (report_path, run_path):
        if artifact.exists():
            artifact.unlink()
    staging, sources = stage_sources(target.resolve(), output.resolve())
    if not sources:
        print("error: no eligible .ts or .tsx source files under --target", file=sys.stderr)
        return 2

    command = build_command(npx_bin=npx_bin, output=output.resolve(), staging=staging)
    env = dict(os.environ)
    env["NPM_CONFIG_CACHE"] = str(npm_cache)
    env["NPM_CONFIG_OFFLINE"] = "true"
    env["NPM_CONFIG_AUDIT"] = "false"
    env["NPM_CONFIG_FUND"] = "false"
    try:
        result = subprocess.run(
            command,
            cwd=staging,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        print(
            f"error: pinned jscpd@{JSCPD_VERSION} is unavailable offline: {exc}. "
            "Populate the declared npm cache explicitly, then retry.",
            file=sys.stderr,
        )
        return 3
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        print(
            f"error: pinned jscpd@{JSCPD_VERSION} is unavailable offline. "
            "Populate the declared npm cache explicitly, then retry.",
            file=sys.stderr,
        )
        if detail:
            print(detail[-2000:], file=sys.stderr)
        return 3

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: jscpd did not write a valid JSON report: {exc}", file=sys.stderr)
        return 3
    schema_error = _report_schema_error(payload)
    if schema_error:
        report_path.unlink(missing_ok=True)
        print(f"error: unexpected jscpd report schema: {schema_error}", file=sys.stderr)
        return 3
    _normalise_report_paths(payload, staging, target.resolve())
    payload["run"] = {
        "status": "completed",
        "tool": "jscpd",
        "version": JSCPD_VERSION,
        "offline": True,
        "eligible_source_count": len(sources),
        "excluded_source_policy": "generated,test,declaration,vendor",
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    run_path.write_text(
        json.dumps(
            {
                "command": command,
                "offline": True,
                "npm_cache": str(npm_cache),
                "eligible_sources": [str(path) for path in sources],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    print(f"[run_jscpd] wrote {report_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--npm-cache", type=Path, default=DEFAULT_NPM_CACHE)
    parser.add_argument("--npx-bin", default="npx", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(
        target=args.target,
        output=args.output,
        npm_cache=args.npm_cache,
        npx_bin=args.npx_bin,
    )


if __name__ == "__main__":
    raise SystemExit(main())
