#!/usr/bin/env python3
"""Run pinned Python jscpd lexical detection with an optional AST-only fallback."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


JSCPD_VERSION = "4.0.5"
DEFAULT_NPM_CACHE = Path(tempfile.gettempdir()) / "engineering-skills-jscpd-cache"
SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".jscpd-input",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "generated",
        "migrations",
        "node_modules",
        "reports",
        "staticfiles",
        "test",
        "tests",
        "vendor",
    }
)


def is_eligible_source(
    path: Path, target: Path, *, excluded_root: Path
) -> bool:
    if not path.is_file() or path.suffix.lower() != ".py":
        return False
    resolved = path.resolve()
    if resolved == excluded_root or resolved.is_relative_to(excluded_root):
        return False
    name = path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == "tests.py":
        return False
    try:
        ancestors = path.relative_to(target).parts[:-1]
    except ValueError:
        return False
    return not any(part.lower() in SKIP_DIRECTORIES for part in ancestors)


def iter_sources(target: Path, output: Path) -> list[Path]:
    return sorted(
        path
        for path in target.rglob("*")
        if is_eligible_source(path, target, excluded_root=output.resolve())
    )


def stage_sources(target: Path, output: Path) -> tuple[Path, list[Path]]:
    staging = output / ".jscpd-input"
    sources = iter_sources(target, output)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for source in sources:
        destination = staging / source.relative_to(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return staging, sources


def _source_name(name: str, staging: Path, target: Path) -> str:
    raw = Path(name)
    try:
        candidate = raw if raw.is_absolute() else staging / raw
        relative = candidate.resolve().relative_to(staging.resolve())
    except (OSError, ValueError):
        return name
    return str((target / relative).resolve())


def _normalize_paths(payload: dict[str, Any], staging: Path, target: Path) -> None:
    for duplicate in payload.get("duplicates", []) or []:
        for key in ("firstFile", "secondFile"):
            record = duplicate.get(key)
            if isinstance(record, dict) and isinstance(record.get("name"), str):
                record["name"] = _source_name(record["name"], staging, target)
    formats = ((payload.get("statistics") or {}).get("formats") or {})
    for format_data in formats.values():
        if not isinstance(format_data, dict):
            continue
        sources = format_data.get("sources")
        if isinstance(sources, dict):
            format_data["sources"] = {
                _source_name(str(name), staging, target): data
                for name, data in sources.items()
            }


def _schema_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "report root must be an object"
    if not isinstance(payload.get("duplicates"), list):
        return "`duplicates` must be a list"
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return "`statistics` must be an object"
    if not isinstance(statistics.get("formats"), dict):
        return "`statistics.formats` must be an object"
    if not isinstance(statistics.get("total"), dict):
        return "`statistics.total` must be an object"
    for index, duplicate in enumerate(payload["duplicates"]):
        if not isinstance(duplicate, dict):
            return f"`duplicates[{index}]` must be an object"
        if not isinstance(duplicate.get("format"), str):
            return f"`duplicates[{index}].format` must be a string"
        if type(duplicate.get("lines")) is not int:
            return f"`duplicates[{index}].lines` must be an integer"
        for key in ("firstFile", "secondFile"):
            record = duplicate.get(key)
            if not isinstance(record, dict) or not isinstance(record.get("name"), str):
                return f"`duplicates[{index}].{key}` must name a file"
            start, end = record.get("start"), record.get("end")
            if type(start) is not int or type(end) is not int or start < 1 or end < start:
                return f"`duplicates[{index}].{key}` must have a valid line range"
    return None


def build_command(npx_bin: str, output: Path, staging: Path) -> list[str]:
    return [
        npx_bin,
        "--offline",
        "--yes",
        f"jscpd@{JSCPD_VERSION}",
        "--format",
        "python",
        "--mode",
        "weak",
        "--threshold",
        "100",
        "--reporters",
        "json",
        "--output",
        str(output),
        str(staging),
    ]


def _write_skipped(
    report_path: Path,
    skipped_path: Path,
    command: list[str],
    detail: str,
    source_count: int,
) -> None:
    run = {
        "status": "skipped_lexical",
        "tool": "jscpd",
        "version": JSCPD_VERSION,
        "offline": True,
        "command": command,
        "stderr": detail[-4000:],
        "eligible_source_count": source_count,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    report_path.write_text(
        json.dumps(
            {"statistics": {"formats": {}, "total": {}}, "duplicates": [], "run": run},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    skipped_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")


def run(
    *,
    target: Path,
    output: Path,
    npm_cache: Path,
    npx_bin: str,
    offline_ok: bool,
) -> int:
    target = target.resolve()
    output = output.resolve()
    if not target.is_dir():
        print("error: --target must be a Python source directory", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "jscpd-report.json"
    run_path = output / "run.json"
    skipped_path = output / "skipped-lexical.json"
    for artifact in (report_path, run_path, skipped_path):
        artifact.unlink(missing_ok=True)
    staging, sources = stage_sources(target, output)
    if not sources:
        print("error: no eligible .py source files under --target", file=sys.stderr)
        return 2
    command = build_command(npx_bin, output, staging)
    env = dict(os.environ)
    env.update(
        {
            "NPM_CONFIG_CACHE": str(npm_cache),
            "NPM_CONFIG_OFFLINE": "true",
            "NPM_CONFIG_AUDIT": "false",
            "NPM_CONFIG_FUND": "false",
        }
    )
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
        detail = str(exc)
        if offline_ok:
            _write_skipped(report_path, skipped_path, command, detail, len(sources))
            return 0
        print(f"error: pinned jscpd@{JSCPD_VERSION} is unavailable offline: {exc}", file=sys.stderr)
        return 3
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        report_path.unlink(missing_ok=True)
        if offline_ok:
            _write_skipped(report_path, skipped_path, command, detail, len(sources))
            print("[run-jscpd-python] lexical scan skipped; AST stage remains available", file=sys.stderr)
            return 0
        print(f"error: pinned jscpd@{JSCPD_VERSION} is unavailable offline", file=sys.stderr)
        return 3
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report_path.unlink(missing_ok=True)
        print(f"error: jscpd did not write a valid JSON report: {exc}", file=sys.stderr)
        return 3
    schema_error = _schema_error(payload)
    if schema_error:
        report_path.unlink(missing_ok=True)
        print(f"error: unexpected jscpd report schema: {schema_error}", file=sys.stderr)
        return 3
    _normalize_paths(payload, staging, target)
    payload["run"] = {
        "status": "completed",
        "tool": "jscpd",
        "version": JSCPD_VERSION,
        "offline": True,
        "eligible_source_count": len(sources),
        "excluded_source_policy": "tests,migrations,vendor,output,report,staging",
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    run_path.write_text(
        json.dumps(
            {
                "command": command,
                "offline": True,
                "npm_cache": str(npm_cache),
                "eligible_sources": [str(source) for source in sources],
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
    print(f"[run-jscpd-python] wrote {report_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--npm-cache", type=Path, default=DEFAULT_NPM_CACHE)
    parser.add_argument("--offline-ok", action="store_true")
    parser.add_argument("--npx-bin", default="npx", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(
        target=args.target,
        output=args.output,
        npm_cache=args.npm_cache,
        npx_bin=args.npx_bin,
        offline_ok=args.offline_ok,
    )


if __name__ == "__main__":
    raise SystemExit(main())
