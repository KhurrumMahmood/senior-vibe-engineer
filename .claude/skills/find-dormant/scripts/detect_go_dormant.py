#!/usr/bin/env python3
"""Render the conservative Go dormant-review artifact from a batched helper."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


MINIMUM_GO = (1, 22)


class DormantGoError(ValueError):
    """Known unsupported or failed Go dormant-scan condition."""


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_inside(root: Path, value: str, label: str) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else root / raw
    candidate = Path(os.path.abspath(candidate))
    if not _within(root, candidate):
        raise DormantGoError(f"{label} must stay inside project root: {value}")
    return candidate


def _traverses_symlink(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current /= part
        if current.exists() and current.is_symlink():
            return True
    return False


def _safe_report_dir(root: Path, supplied: str) -> Path:
    report = _resolve_inside(root, supplied, "report directory")
    allowed = root / "reports" / "find-dormant"
    if report == allowed or not _within(allowed, report):
        raise DormantGoError(
            f"report directory must stay beneath reports/find-dormant/: {supplied}",
        )
    if _traverses_symlink(root, report):
        raise DormantGoError(f"report directory must not traverse a symbolic link: {supplied}")
    return report


def _go_tool() -> tuple[Path, str]:
    discovered = shutil.which("go")
    if discovered is None:
        raise DormantGoError("Go toolchain is unavailable on PATH")
    go = Path(discovered)
    try:
        result = subprocess.run(
            [str(go), "version"], capture_output=True, text=True, check=False,
        )
    except OSError as error:
        raise DormantGoError(f"cannot run Go toolchain: {error}") from error
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise DormantGoError(f"cannot determine Go version: {rendered}")
    if (int(match.group(1)), int(match.group(2))) < MINIMUM_GO:
        raise DormantGoError(f"Go detector requires Go >= 1.22; found {rendered}")
    return go, rendered


def _write_report(report: Path, payload: dict[str, Any]) -> None:
    """Stage both artifacts before atomically replacing either final path."""
    contents = {
        "findings.json": f"{json.dumps(payload, indent=2)}\n",
        "report.md": _render_report(payload),
    }
    report.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    try:
        for name, text in contents.items():
            temporary = report / f".{name}.tmp-{os.getpid()}"
            temporary.write_text(text, encoding="utf-8")
            staged[name] = temporary
        for name in contents:
            staged[name].replace(report / name)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Go dormant-code audit",
        "",
        f"Status: **{payload['status']}**. Active-build package static-use inventory for `{payload['target']['path']}`.",
        "",
        "## Never safe deletion from static evidence",
        "",
        "Every result is human-review-only. Static facts do not establish reflection, `//go:linkname`, generated registration, plugin, cgo, assembly, external, or runtime reachability.",
        "",
        "## Summary",
        "",
        f"- Review-required static candidates: {payload['summary']['review_required']}",
        f"- Uncertain symbols: {payload['summary']['uncertain']}",
        "- Certain-delete findings: 0 (not a Go v1 outcome)",
        "",
        "## Review-required static candidates",
        "",
    ]
    candidates = payload["candidates"]
    if not candidates:
        lines.append("None.")
    for candidate in candidates:
        lines.append(
            f"- `{candidate['file']}:{candidate['line']}` — `{candidate['name']}` ({candidate['kind']}); {candidate['recommendation']}",
        )
    lines.extend(["", "## Uncertain symbols", ""])
    uncertain = payload["uncertain_symbols"]
    if not uncertain:
        lines.append("None.")
    for item in uncertain:
        lines.append(f"- `{item['file']}:{item['line']}` — `{item['name']}`: {item['reason']}")
    lines.extend(["", "## Package and build resolution", ""])
    lines.append(f"State: **{payload['project_resolution']['state']}**.")
    for item in payload["project_resolution"].get("unavailable_files", []):
        lines.append(f"- `{item['file']}` — {item['reason']}")
    for item in payload["packages"]:
        if item["status"] != "complete":
            detail = f": {item['detail']}" if item.get("detail") else ""
            lines.append(f"- `{item['directory']}` — {item['status']}{detail}")
    if payload["project_resolution"].get("go_list_warning"):
        lines.append(f"- Go list warning: {payload['project_resolution']['go_list_warning']}")
    lines.extend(["", "## How to act", ""])
    lines.append("Inspect each result with package/runtime knowledge before any deletion discussion; this report does not authorize a deletion.")
    lines.append("")
    return "\n".join(lines)


def _run_helper(go: Path, helper: Path, target: Path, root: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            str(go), "run", str(helper),
            "--target", str(target), "--project-root", str(root), "--go-executable", str(go),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GOTOOLCHAIN": "local"},
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise DormantGoError(f"batched Go detector failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DormantGoError("batched Go detector emitted invalid JSON") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("analyzer") != "go-list-go-parser-go-types"
        or payload.get("language") != "go"
        or not isinstance(payload.get("candidates"), list)
        or not isinstance(payload.get("uncertain_symbols"), list)
    ):
        raise DormantGoError("batched Go detector emitted invalid evidence")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise DormantGoError(f"project root is not a directory: {args.project_root}")
        target = _resolve_inside(root, args.target, "target")
        if not target.exists():
            raise DormantGoError(f"target does not exist: {args.target}")
        if _traverses_symlink(root, target) or target.is_symlink():
            raise DormantGoError(f"target must not traverse a symbolic link: {args.target}")
        report = _safe_report_dir(root, args.report_dir)
        go, go_version = _go_tool()
        payload = _run_helper(go, Path(__file__).with_name("detect_go_dormant.go"), target, root)
        payload["go_version"] = go_version
        _write_report(report, payload)
    except DormantGoError as error:
        print(f"[find-dormant-go] ERROR: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"[find-dormant-go] ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[find-dormant-go] wrote {report} "
        f"(review_required={payload['summary']['review_required']} uncertain={payload['summary']['uncertain']} status={payload['status']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
