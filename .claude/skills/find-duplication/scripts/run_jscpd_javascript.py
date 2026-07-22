#!/usr/bin/env python3
"""Run an explicitly supplied, project-local jscpd binary over JavaScript.

The runner never invokes npm, npx, or a global executable.  A host must pass
the checked project-local tool path (normally its `node_modules/.bin/jscpd`).
Its status artifact distinguishes a missing tool from a malformed source or a
tool execution failure, so a no-result scan is never reported as clean.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


JAVASCRIPT_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs"})
SKIP_DIRECTORIES = frozenset({
    ".git", ".jscpd-input", ".next", ".venv", "__tests__", "build",
    "coverage", "dist", "generated", "node_modules", "reports", "test",
    "tests", "vendor",
})


def is_eligible_source(
    path: Path, target: Path, *, excluded_roots: tuple[Path, ...] = ()
) -> bool:
    """Return whether a path is first-party JavaScript clone input."""
    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in JAVASCRIPT_SUFFIXES:
        return False
    try:
        resolved = path.resolve(strict=True)
        target_resolved = target.resolve(strict=True)
    except OSError:
        return False
    if any(resolved == root or resolved.is_relative_to(root) for root in excluded_roots):
        return False
    name = path.name.lower()
    if (
        ".test." in name
        or ".spec." in name
        or ".generated." in name
        or ".gen." in name
        or name.endswith((".min.js", ".min.jsx", ".min.mjs", ".min.cjs"))
    ):
        return False
    try:
        ancestors = path.relative_to(target_resolved).parts[:-1]
    except ValueError:
        return False
    return not any(part.lower() in SKIP_DIRECTORIES for part in ancestors)


def iter_sources(target: Path, *, excluded_roots: tuple[Path, ...] = ()) -> list[Path]:
    if target.is_file():
        return [target] if is_eligible_source(target, target.parent, excluded_roots=excluded_roots) else []
    return sorted(
        path
        for path in target.rglob("*")
        if is_eligible_source(path, target, excluded_roots=excluded_roots)
    )


def stage_sources(target: Path, output: Path) -> tuple[Path, list[Path]]:
    source_root = target if target.is_dir() else target.parent
    staging = output / ".jscpd-input"
    sources = iter_sources(target, excluded_roots=(output.resolve(),))
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for source in sources:
        destination = staging / source.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return staging, sources


def _staged_to_source_name(name: str, staging: Path, source_root: Path) -> str:
    raw = Path(name)
    try:
        candidate = raw if raw.is_absolute() else staging / raw
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
                record["name"] = _staged_to_source_name(record["name"], staging, source_root)


def _report_schema_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "report root must be an object"
    if not isinstance(payload.get("duplicates"), list):
        return "`duplicates` must be a list"
    for index, duplicate in enumerate(payload["duplicates"]):
        if not isinstance(duplicate, dict):
            return f"`duplicates[{index}]` must be an object"
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


def _write_run(path: Path, **payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_command(*, jscpd_bin: Path, output: Path, staging: Path) -> list[str]:
    return [
        str(jscpd_bin), "--format", "javascript,jsx", "--min-tokens", "20",
        "--threshold", "100", "--reporters", "json", "--output", str(output), str(staging),
    ]


def run(*, target: Path, project_root: Path, output: Path, jscpd_bin: Path) -> int:
    try:
        target = target.resolve(strict=True)
        project_root = project_root.resolve(strict=True)
        target.relative_to(project_root)
    except (OSError, ValueError):
        print("error: --target must be a source directory within --project-root", file=sys.stderr)
        return 2
    if not target.is_dir():
        print("error: --target must be a JavaScript source directory", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "jscpd-report.json"
    run_path = output / "run.json"
    for artifact in (report_path, run_path):
        artifact.unlink(missing_ok=True)
    try:
        jscpd_bin = jscpd_bin.resolve(strict=True)
        jscpd_bin.relative_to(project_root)
    except (OSError, ValueError):
        jscpd_bin = Path(jscpd_bin)
        tool_is_project_local = False
    else:
        tool_is_project_local = jscpd_bin.is_file() and os.access(jscpd_bin, os.X_OK)
    if not tool_is_project_local:
        _write_run(
            run_path,
            status="tool-missing",
            tool="jscpd",
            tool_path=str(jscpd_bin),
            detail="Pass an executable project-local jscpd binary; the skill never invokes npx or npm.",
        )
        print(f"tool-missing: project-local jscpd binary is unavailable: {jscpd_bin}", file=sys.stderr)
        return 3
    staging, sources = stage_sources(target, output.resolve())
    if not sources:
        _write_run(run_path, status="partial", tool="jscpd", eligible_source_count=0)
        print("partial: no eligible JavaScript source files under --target", file=sys.stderr)
        return 2
    command = build_command(jscpd_bin=jscpd_bin, output=output.resolve(), staging=staging)
    try:
        result = subprocess.run(command, cwd=staging, text=True, capture_output=True, check=False)
    except OSError as exc:
        _write_run(run_path, status="tool-missing", tool="jscpd", tool_path=str(jscpd_bin), detail=str(exc))
        print(f"tool-missing: could not execute project-local jscpd: {exc}", file=sys.stderr)
        return 3
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        status = "syntax-error" if any(token in detail.lower() for token in ("syntax", "parse", "unexpected token")) else "tool-failed"
        _write_run(run_path, status=status, tool="jscpd", command=command, detail=detail[-2000:])
        report_path.unlink(missing_ok=True)
        print(f"{status}: project-local jscpd exited {result.returncode}", file=sys.stderr)
        if detail:
            print(detail[-2000:], file=sys.stderr)
        return 1
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _write_run(run_path, status="tool-failed", tool="jscpd", command=command, detail=str(exc))
        report_path.unlink(missing_ok=True)
        print(f"tool-failed: jscpd did not write valid JSON: {exc}", file=sys.stderr)
        return 1
    schema_error = _report_schema_error(payload)
    if schema_error:
        _write_run(run_path, status="tool-failed", tool="jscpd", command=command, detail=schema_error)
        report_path.unlink(missing_ok=True)
        print(f"tool-failed: unexpected jscpd report schema: {schema_error}", file=sys.stderr)
        return 1
    _normalise_report_paths(payload, staging, target.resolve())
    payload["run"] = {
        "status": "completed",
        "tool": "jscpd",
        "eligible_source_count": len(sources),
        "excluded_source_policy": "generated,minified,test,vendor,output,report,staging,symlink",
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_run(
        run_path,
        status="completed",
        tool="jscpd",
        tool_path=str(jscpd_bin),
        command=command,
        eligible_sources=[str(path) for path in sources],
    )
    print(f"[run-jscpd-javascript] wrote {report_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jscpd-bin", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(
        target=args.target,
        project_root=args.project_root,
        output=args.output,
        jscpd_bin=args.jscpd_bin,
    )


if __name__ == "__main__":
    raise SystemExit(main())
