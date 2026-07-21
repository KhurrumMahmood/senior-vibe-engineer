#!/usr/bin/env python3
"""Launch the family-local Go incomplete-sweep detector without source writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


MINIMUM_GO = (1, 22)


class GoSweepError(ValueError):
    """Known Go incomplete-sweep failure that must not publish a report."""


class UnsupportedGoError(GoSweepError):
    """The host cannot supply the stdlib Go v1 capability."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlinks(root: Path, candidate: Path, label: str) -> None:
    current = root
    for part in candidate.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise GoSweepError(f"{label} must not traverse a symbolic link: {candidate}")


def _resolve_inside(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    if not _inside(root, candidate):
        raise GoSweepError(f"{label} must stay inside project root: {supplied}")
    _reject_symlinks(root, candidate, label)
    resolved = candidate.resolve()
    if not _inside(root, resolved):
        raise GoSweepError(f"{label} must stay inside project root: {supplied}")
    return resolved


def _go_tool(supplied: str | None) -> tuple[Path, str]:
    found = supplied or shutil.which("go")
    if not found:
        raise UnsupportedGoError("Go toolchain is unavailable on PATH")
    tool = Path(found)
    try:
        result = subprocess.run([str(tool), "version"], capture_output=True, text=True, check=False)
    except OSError as error:
        raise UnsupportedGoError(f"cannot run Go toolchain: {error}") from error
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise UnsupportedGoError(f"cannot determine Go version: {rendered}")
    if (int(match.group(1)), int(match.group(2))) < MINIMUM_GO:
        raise UnsupportedGoError(f"Go analyzer requires Go >= 1.22; found {rendered}")
    return tool, rendered


def _source_fingerprint(scripts: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_go_incomplete_sweep.py", "detect_go_incomplete_sweep.go"):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((scripts / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _render_findings(payload: dict[str, Any]) -> str:
    lines = [
        "# find-incomplete-sweep — findings (Go v1)",
        "",
        f"Status: **{payload['status']}**. Resolved direct-call and keyed struct-literal evidence only.",
        "",
        "## Gated IN — likely forgotten sweeps",
        "",
    ]
    if not payload["findings"]:
        lines.append("_none_")
    for finding in payload["findings"]:
        lines.extend([
            f"### `{finding['callee']}` missing `{finding['kwarg']}`",
            "",
            f"- straggler: `{finding['straggler']}`",
            f"- option position: {finding['option_position']}",
            f"- majority: {finding['present_count']}/{finding['group_size']} ({round(finding['majority_frac'] * 100)}%)",
            f"- comparable value: `{finding['value']}`",
            f"- trajectory: {finding['trajectory']}",
            "",
        ])
    lines.extend(["## Gated OUT — likely deliberate", ""])
    if not payload["gated_out"]:
        lines.append("_none_")
    for finding in payload["gated_out"]:
        lines.append(f"- `{finding['straggler']}` — {finding['trajectory']}")
    lines.extend(["", "## Deferred boundaries", ""])
    if not payload["deferred"]:
        lines.append("_none_")
    for item in payload["deferred"]:
        detail = f" ({item['detail']})" if item.get("detail") else ""
        lines.append(f"- `{item['file']}:{item['line']}` — {item['reason']}{detail}")
    lines.extend(["", "## Project resolution", ""])
    resolution = payload["project_resolution"]
    lines.append(f"State: **{resolution['state']}**; Git evidence: **{resolution['git_evidence']}**.")
    for file in resolution["inactive_files"]:
        lines.append(f"- `{file}` — inactive under the current build")
    lines.append("")
    return "\n".join(lines)


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


def _validated_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise GoSweepError("Go helper emitted invalid JSON") from error
    required = {
        "schema_version": 1,
        "band": "go-option-omission",
        "language": "go",
        "analyzer": "go-list-go-parser-go-types",
    }
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in required.items()):
        raise GoSweepError("Go helper emitted invalid evidence")
    if payload.get("status") not in {"complete", "partial"}:
        raise GoSweepError("Go helper emitted an invalid status")
    if not all(isinstance(payload.get(key), list) for key in ("findings", "gated_out", "deferred")):
        raise GoSweepError("Go helper emitted invalid candidate collections")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--go-executable")
    parser.add_argument("--min-callsites", type=int, default=4)
    parser.add_argument("--majority-frac", type=float, default=0.75)
    parser.add_argument("--min-present", type=int, default=3)
    args = parser.parse_args(argv)
    staged: Path | None = None
    try:
        logical_root = Path(os.path.abspath(args.project_root))
        if not logical_root.is_dir() or logical_root.is_symlink():
            raise GoSweepError(f"project root is not a directory: {args.project_root}")
        root = logical_root.resolve()
        target = _resolve_inside(root, args.target, "target")
        if not target.exists() or target.is_symlink():
            raise GoSweepError(f"target must be an existing non-symlink path: {args.target}")
        report = _resolve_inside(root, args.report_dir, "report directory")
        allowed = root / "reports" / "find-incomplete-sweep"
        if report == allowed or not _inside(allowed, report):
            raise GoSweepError("report directory must stay beneath reports/find-incomplete-sweep/")
        go, version = _go_tool(args.go_executable)
        helper = Path(__file__).with_name("detect_go_incomplete_sweep.go")
        result = subprocess.run(
            [
                str(go), "run", str(helper), "--target", str(target), "--project-root", str(root),
                "--go-executable", str(go), "--min-callsites", str(args.min_callsites),
                "--majority-frac", str(args.majority_frac), "--min-present", str(args.min_present),
            ],
            cwd=root,
            env={**os.environ, "GOTOOLCHAIN": "local"},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise GoSweepError(detail)
        payload = _validated_payload(result.stdout)
        payload["source_fingerprint"] = _source_fingerprint(Path(__file__).parent)
        report.parent.mkdir(parents=True, exist_ok=True)
        staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
        staged.mkdir()
        (staged / "manifest.json").write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
        (staged / "findings.md").write_text(_render_findings(payload), encoding="utf-8")
        _replace_directory(staged, report)
        staged = None
    except UnsupportedGoError as error:
        if staged is not None and staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[find-incomplete-sweep-go] unsupported: {error}", file=sys.stderr)
        return 2
    except (GoSweepError, OSError) as error:
        if staged is not None and staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[find-incomplete-sweep-go] failed: {error}", file=sys.stderr)
        return 2
    print(
        f"[find-incomplete-sweep-go] wrote {report} "
        f"(gated_in={payload['summary']['gated_in']} status={payload['status']} {version})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
