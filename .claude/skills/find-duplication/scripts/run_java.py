#!/usr/bin/env python3
"""Produce conservative exact method/constructor clone evidence for Java."""
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


MINIMUM_JDK = (17, 0, 0)
SKIP_DIRS = frozenset({
    ".git", ".gradle", ".idea", ".venv", "build", "coverage", "dependencies",
    "deps", "dist", "fixture", "fixtures", "generated", "node_modules", "out",
    "reports", "target", "test", "testdata", "tests", "third-party", "third_party", "vendor",
})
SKIP_FILES = ("*Test.java", "*Tests.java", "*IT.java", "*Generated.java", "*.generated.java", "*_generated.java")
GENERATED_RE = re.compile(r"^// (?:Code )?[Gg]enerated .* DO NOT EDIT\.$")


class DetectorError(ValueError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _generated(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8") as source:
            return any(
                GENERATED_RE.fullmatch(line.strip())
                for _, line in zip(range(40), source, strict=False)
            )
    except (OSError, UnicodeDecodeError):
        return False


def _excluded(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return (
        any(part.casefold() in SKIP_DIRS for part in relative.parts[:-1])
        or any(fnmatch.fnmatchcase(path.name, pattern) for pattern in SKIP_FILES)
        or _generated(path)
    )


def _resolve_target(raw: Path, root: Path) -> Path:
    target = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise DetectorError("failed", f"target is outside project root: {raw}") from exc
    if not target.exists():
        raise DetectorError("failed", f"target does not exist: {raw}")
    return target


def _files(target: Path, root: Path) -> tuple[list[Path], dict[str, int]]:
    candidates = [target] if target.is_file() else sorted(target.rglob("*.java"))
    candidates = [path for path in candidates if path.is_file() and path.suffix.casefold() == ".java"]
    eligible = [path for path in candidates if not _excluded(path, root)]
    return eligible, {"java_candidates": len(candidates), "policy_excluded": len(candidates) - len(eligible)}


def _parse_version(rendered: str, tool: str) -> tuple[int, int, int]:
    prefix = r"^javac\s+" if tool == "javac" else r"^(?:openjdk|java)\s+"
    match = re.search(prefix + r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", rendered, re.MULTILINE)
    if match is None:
        raise DetectorError("unsupported", f"cannot determine {tool} version: {rendered.strip()}")
    return tuple(int(part or 0) for part in match.groups())


def _jdk() -> tuple[Path, str, str]:
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java is None or javac is None:
        raise DetectorError("unsupported", "JDK toolchain is unavailable on PATH")
    versions: dict[str, str] = {}
    for tool, command in (("java", [java, "--version"]), ("javac", [javac, "-version"])):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise DetectorError("unsupported", f"cannot run {tool}: {exc}") from exc
        rendered = (result.stdout + result.stderr).strip()
        version = _parse_version(rendered, tool)
        if result.returncode or version < MINIMUM_JDK:
            raise DetectorError("unsupported", f"Java detector requires JDK >= 17.0.0; found {rendered}")
        versions[tool] = ".".join(str(part) for part in version)
    return Path(java), versions["java"], versions["javac"]


def _detect(paths: list[Path], root: Path, java: Path) -> dict[str, Any]:
    helper = Path(__file__).resolve().with_name("detect_java.java")
    command = [str(java), str(helper), "--project-root", str(root)]
    for path in paths:
        command.extend(("--file", str(path)))
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, env=os.environ.copy())
    except OSError as exc:
        raise DetectorError("unsupported", f"cannot run bundled Java detector: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise DetectorError("failed", f"bundled Java detector failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DetectorError("failed", "bundled Java detector emitted invalid JSON") from exc
    if payload.get("schema_version") != 1 or payload.get("analyzer") != "jdk-tree-exact-method-body" or not isinstance(payload.get("files"), list):
        raise DetectorError("failed", "bundled Java detector emitted invalid evidence")
    return payload


def _collapse(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    for record in payload["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("file"), str):
            raise DetectorError("failed", "bundled Java detector emitted invalid file evidence")
        status = str(record.get("status"))
        statuses[status] += 1
        if status == "syntax-error":
            raise DetectorError("failed", f"syntax-error in {record['file']}: {record.get('error', '')}")
        if status != "complete" or not isinstance(record.get("methods"), list):
            raise DetectorError("failed", f"invalid Java detector status for {record['file']}: {status}")
        for method in record["methods"]:
            if not isinstance(method, dict) or not isinstance(method.get("fingerprint"), str):
                raise DetectorError("failed", "bundled Java detector emitted invalid method evidence")
            by_fingerprint[method["fingerprint"]].append({
                "file": record["file"], "method": str(method.get("name")),
                "start_line": int(method.get("start_line")), "end_line": int(method.get("end_line")),
                "loc": int(method.get("loc")),
            })
    groups = [sites for sites in by_fingerprint.values() if len(sites) >= 2]
    groups.sort(key=lambda sites: (-len(sites), -max(site["loc"] for site in sites), sites[0]["file"]))
    findings: list[dict[str, Any]] = []
    for index, sites in enumerate(groups, start=1):
        distinct_files = len({site["file"] for site in sites})
        shape = "three_way_plus" if len(sites) >= 3 else ("cross_file_clone" if distinct_files >= 2 else "same_file_clone")
        findings.append({
            "finding_id": f"java-exact-{index:04d}", "category": "java-exact-method-body",
            "shape_hint": shape, "multiplicity": len(sites), "shared_lines_max": max(site["loc"] for site in sites),
            "sites": sites, "consolidation_safety": "unknown_human_review_required",
            "evidence": "Exact JDK-tree-normalized method/constructor-body fingerprint; callers, types, and semantics were not resolved.",
        })
    return findings, {"file_status_counts": dict(sorted(statuses.items())), "method_fingerprint_count": len(by_fingerprint)}


def run(target_raw: Path, root: Path) -> dict[str, Any]:
    target = _resolve_target(target_raw, root)
    paths, inventory = _files(target, root)
    if not paths:
        raise DetectorError("unsupported", "no eligible first-party Java source under target")
    java, java_version, javac_version = _jdk()
    findings, analysis = _collapse(_detect(paths, root, java))
    return {
        "scan_meta": {
            "target": _relative(target, root), "project_root": str(root),
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "language": "java", "status": "complete", "analyzer": "jdk-tree-exact-method-body",
            "java_version": java_version, "javac_version": javac_version,
            "source_inventory": inventory, "analysis": analysis,
            "jscpd_raw_pair_count": 0, "jscpd_filtered_pair_count": 0, "jscpd_finding_count": 0,
            "ast_finding_count": len(findings), "ast_filtered_count": 0,
        },
        "findings": findings,
    }


def _prepare_output(output: Path) -> None:
    if output.is_dir():
        raise DetectorError("failed", f"output path must be a file: {output}")
    if output.resolve().suffix.casefold() == ".java":
        raise DetectorError("failed", f"output overlaps Java source: {output}")
    if output.exists() or output.is_symlink():
        output.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        _prepare_output(args.output)
        payload = run(args.target, root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except DetectorError as exc:
        print(f"status={exc.status}: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"status=failed: cannot write {args.output}: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output}: status=complete findings={len(payload['findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
