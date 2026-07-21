#!/usr/bin/env python3
"""Produce conservative exact-function clone evidence for Go source."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MINIMUM_GO = (1, 22)
SKIP_DIRS = frozenset({
    ".git", ".venv", "build", "coverage", "dependencies", "deps", "dist",
    "fixture", "fixtures", "gen", "generated", "node_modules", "out",
    "reports", "test", "testdata", "tests", "third-party", "third_party", "vendor",
})
SKIP_FILES = ("*_test.go", "*.generated.go", "*_generated.go")


class DetectorError(ValueError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _excluded(path: Path, project_root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return True
    return (
        any(part.casefold() in SKIP_DIRS for part in relative.parts[:-1])
        or any(fnmatch.fnmatchcase(path.name.casefold(), pattern) for pattern in SKIP_FILES)
    )


def _resolve_target(raw: Path, project_root: Path) -> Path:
    target = raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise DetectorError("failed", f"target is outside project root: {raw}") from exc
    if not target.exists():
        raise DetectorError("failed", f"target does not exist: {raw}")
    return target


def _files(target: Path, project_root: Path) -> tuple[list[Path], dict[str, int]]:
    candidates = [target] if target.is_file() else sorted(target.rglob("*.go"))
    candidates = [path for path in candidates if path.is_file() and path.suffix == ".go"]
    eligible = [path for path in candidates if not _excluded(path, project_root)]
    return eligible, {
        "go_candidates": len(candidates),
        "policy_excluded": len(candidates) - len(eligible),
    }


def _go_tool() -> tuple[Path, str]:
    discovered = shutil.which("go")
    if discovered is None:
        raise DetectorError("unsupported", "Go toolchain is unavailable on PATH")
    go = Path(discovered)
    try:
        result = subprocess.run(
            [str(go), "version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise DetectorError("unsupported", f"cannot run Go toolchain: {exc}") from exc
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.\d+)?\b", rendered)
    if result.returncode or match is None:
        raise DetectorError("unsupported", f"cannot determine Go version: {rendered}")
    if (int(match.group(1)), int(match.group(2))) < MINIMUM_GO:
        raise DetectorError("unsupported", f"Go detector requires Go >= 1.22; found {rendered}")
    return go, rendered


def _detect(paths: list[Path], go: Path) -> dict[str, Any]:
    helper = Path(__file__).resolve().with_name("detect_go.go")
    try:
        result = subprocess.run(
            [str(go), "run", str(helper), "--", *(str(path) for path in paths)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GO111MODULE": "off", "GOTOOLCHAIN": "local", "GOWORK": "off"},
        )
    except OSError as exc:
        raise DetectorError("unsupported", f"cannot run bundled Go detector: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise DetectorError("failed", f"bundled Go detector failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DetectorError("failed", "bundled Go detector emitted invalid JSON") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("analyzer") != "go-parser-exact-function-body"
        or not isinstance(payload.get("files"), list)
    ):
        raise DetectorError("failed", "bundled Go detector emitted invalid evidence")
    return payload


def _collapse(payload: dict[str, Any], project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    for record in payload["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("file"), str):
            raise DetectorError("failed", "bundled Go detector emitted invalid file evidence")
        status = record.get("status")
        statuses[str(status)] += 1
        if status in {"syntax-error", "format-error"}:
            raise DetectorError("failed", f"{status} in {_relative(Path(record['file']), project_root)}: {record.get('error', '')}")
        if status not in {"complete", "generated", "build-constraint-ambiguous"}:
            raise DetectorError("failed", "bundled Go detector emitted invalid file status")
        if status != "complete":
            continue
        functions = record.get("functions")
        if not isinstance(functions, list):
            raise DetectorError("failed", "bundled Go detector emitted invalid function evidence")
        for function in functions:
            if not isinstance(function, dict) or not isinstance(function.get("fingerprint"), str):
                raise DetectorError("failed", "bundled Go detector emitted invalid function evidence")
            by_fingerprint[function["fingerprint"]].append({
                "file": _relative(Path(record["file"]), project_root),
                "method": str(function.get("name")),
                "start_line": int(function.get("start_line")),
                "end_line": int(function.get("end_line")),
                "loc": int(function.get("loc")),
            })
    findings: list[dict[str, Any]] = []
    groups = [sites for sites in by_fingerprint.values() if len(sites) >= 2]
    groups.sort(key=lambda sites: (-len(sites), -max(site["loc"] for site in sites), sites[0]["file"]))
    for index, sites in enumerate(groups, start=1):
        distinct_files = len({site["file"] for site in sites})
        if len(sites) >= 3:
            shape_hint = "three_way_plus"
        elif distinct_files >= 2:
            shape_hint = "cross_file_clone"
        else:
            shape_hint = "same_file_clone"
        findings.append({
            "finding_id": f"go-exact-{index:04d}",
            "category": "go-exact-function-body",
            "shape_hint": shape_hint,
            "multiplicity": len(sites),
            "shared_lines_max": max(site["loc"] for site in sites),
            "sites": sites,
            "consolidation_safety": "unknown_human_review_required",
            "evidence": "Exact go/format-normalized function-body fingerprint; callers and semantics were not resolved.",
        })
    return findings, {
        "file_status_counts": dict(sorted(statuses.items())),
        "function_fingerprint_count": len(by_fingerprint),
    }


def run(target_raw: Path, project_root: Path) -> dict[str, Any]:
    target = _resolve_target(target_raw, project_root)
    paths, inventory = _files(target, project_root)
    if not paths:
        raise DetectorError("unsupported", "no eligible first-party Go source under target")
    go, go_version = _go_tool()
    detector = _detect(paths, go)
    findings, analysis = _collapse(detector, project_root)
    constrained = analysis["file_status_counts"].get("build-constraint-ambiguous", 0)
    complete = analysis["file_status_counts"].get("complete", 0)
    if complete == 0 and constrained == 0:
        raise DetectorError("unsupported", "no analyzable first-party Go source under target")
    status = "partial" if constrained else "complete"
    return {
        "scan_meta": {
            "target": _relative(target, project_root),
            "project_root": str(project_root),
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "language": "go",
            "status": status,
            "analyzer": "go-parser-exact-function-body",
            "go_version": go_version,
            "source_inventory": inventory,
            "analysis": analysis,
            "jscpd_raw_pair_count": 0,
            "jscpd_filtered_pair_count": 0,
            "jscpd_finding_count": 0,
            "ast_finding_count": len(findings),
            "ast_filtered_count": 0,
        },
        "findings": findings,
    }


def _prepare_output(output: Path) -> None:
    resolved = output.resolve()
    if output.is_dir():
        raise DetectorError("failed", f"output path must be a file: {output}")
    if resolved.suffix.casefold() == ".go":
        raise DetectorError("failed", f"output overlaps Go source: {output}")
    if output.exists() or output.is_symlink():
        output.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        _prepare_output(args.output)
        payload = run(args.target, project_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except DetectorError as exc:
        print(f"status={exc.status}: {exc}", file=sys.stderr)
        return 2 if exc.status in {"failed", "unsupported"} else 1
    except OSError as exc:
        print(f"status=failed: cannot write {args.output}: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output}: status={payload['scan_meta']['status']} findings={len(payload['findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
