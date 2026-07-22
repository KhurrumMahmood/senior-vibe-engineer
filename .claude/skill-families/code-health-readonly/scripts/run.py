#!/usr/bin/env python3
"""Run and synthesize the bounded TypeScript/JavaScript code-health family."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


LANES = ("audit-decisions", "find-complexity-hotspots", "find-standard-gaps")
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
LANGUAGE_SUFFIXES = {
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
}
SOURCE_SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "__tests__", "build", "coverage",
    "dist", "fixture", "fixtures", "generated", "migrations", "node_modules",
    "out", "reports", "spec", "specs", "staticfiles", "test", "tests",
    "vendor", "vendored",
}
SOURCE_SKIP_GLOBS = (
    "*.d.ts", "*.d.tsx", "*.generated.*", "*.min.*", "*-min.*", "*.bundle.*",
    "*.spec.*", "*.test.*", "test_*", "tests_*", "*_test.*",
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _source_digest(target: Path) -> str:
    digest = hashlib.sha256()
    files = [target] if target.is_file() else sorted(target.rglob("*"))
    for path in files:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        digest.update(str(path.relative_to(target.parent)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _has_eligible_source(target: Path, language: str) -> bool:
    """Conservatively preflight the family primary's production-source surface."""
    candidates = [target] if target.is_file() else target.rglob("*")
    suffixes = LANGUAGE_SUFFIXES[language]
    for path in candidates:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part.lower() in SOURCE_SKIP_DIRS for part in path.relative_to(target.parent).parts[:-1]):
            continue
        if any(fnmatch.fnmatch(path.name, pattern) for pattern in SOURCE_SKIP_GLOBS):
            continue
        return True
    return False


def _run(command: list[str], cwd: Path) -> tuple[int | None, str, str, float]:
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, "", str(exc), (time.perf_counter_ns() - started) / 1_000_000
    return (
        result.returncode,
        result.stdout,
        result.stderr,
        (time.perf_counter_ns() - started) / 1_000_000,
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _inactive_reason(project_root: Path, skill: str) -> str | None:
    """Mirror the host's small active/inactive contract at execution time."""
    manifest = project_root / ".engineering" / "manifest.json"
    try:
        payload = _read_json(manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    skills = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(skills, dict):
        return None

    def reasons(value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(name): str(reason) for name, reason in value.items()}
        if isinstance(value, list):
            return {str(name): "" for name in value}
        return {}

    active = reasons(skills.get("active"))
    inactive = reasons(skills.get("inactive"))
    if skills.get("default") == "inactive":
        return None if skill in active else inactive.get(skill) or "host_skill_inactive"
    return inactive.get(skill) if skill in inactive else None


def _detector_dispatchable(idea: object) -> bool:
    """Check only fields needed to start a scanner detector."""
    if not isinstance(idea, dict) or not isinstance(idea.get("contract"), dict):
        return False
    detector = idea["contract"].get("detector")
    if not isinstance(detector, dict):
        return False
    paths = detector.get("paths")
    if paths is not None and (
        not isinstance(paths, list)
        or not paths
        or any(
            not isinstance(path, str) or not path or Path(path).is_absolute()
            for path in paths
        )
    ):
        return False
    try:
        if detector.get("kind") == "grep":
            re.compile(detector["situation"])
            satisfied_by = detector.get("satisfied_by")
            if satisfied_by is not None:
                re.compile(satisfied_by)
            window = int(detector.get("window", 20))
            return detector.get("scope", "window") in {"window", "file"} and window >= 0
        if detector.get("kind") == "ast":
            re.compile(detector["call_matches"])
            enclosed_by = detector.get("enclosed_by")
            requires_kwarg = detector.get("requires_kwarg")
            return (
                bool(enclosed_by) != bool(requires_kwarg)
                and (not enclosed_by or enclosed_by in {"try", "with", "defer"})
                and (not requires_kwarg or isinstance(requires_kwarg, str))
            )
    except (KeyError, TypeError, ValueError, re.error):
        return False
    return False


def _standards_dispatchable(path: Path) -> bool:
    try:
        payload = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    ideas = payload.get("ideas") if isinstance(payload, dict) else None
    return isinstance(ideas, list) and any(_detector_dispatchable(row) for row in ideas)


def _lane_command(
    lane: str,
    *,
    project_root: Path,
    library_root: Path,
    target_argument: str,
    language: str,
    standards: Path | None,
    run_id: str,
) -> tuple[list[str], Path, set[int]]:
    python = sys.executable
    skill = library_root / ".claude" / "skills" / lane / "scripts"
    prefix = [python, "-I", "-S"]
    if lane == "audit-decisions":
        output = project_root / "reports" / "audit-decisions" / f"code-health-{run_id}"
        return (
            prefix
            + [
                str(skill / "audit.py"),
                "--project-root",
                str(project_root),
                "--target",
                target_argument,
                "--output-dir",
                str(output),
            ],
            output / "raw-drift.json",
            {0, 1},
        )
    if lane == "find-complexity-hotspots":
        return (
            prefix
            + [
                str(skill / "run.py"),
                "--project-root",
                str(project_root),
                "--language",
                language,
                "--skip-effectiveness-log",
                target_argument,
            ],
            project_root
            / "reports"
            / "find-complexity-hotspots"
            / "latest"
            / "findings.json",
            {0},
        )
    if standards is None:
        raise ValueError("find-standard-gaps requires host standards")
    output = project_root / "reports" / "standard-gaps" / f"code-health-{run_id}"
    return (
        prefix
        + [
            str(skill / "scan_coverage.py"),
            "--ideas",
            str(standards),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output),
        ],
        output / "coverage.json",
        {0},
    )


def _semantic_projection(lane: str, payload: dict[str, Any]) -> Any:
    if lane == "audit-decisions":
        references = [
            {
                key: row.get(key)
                for key in ("path", "line", "id", "language", "resolved")
            }
            for row in payload.get("references", [])
        ]
        return {
            "drift": payload.get("drift", []),
            "references": references,
            "link_check": payload.get("link_check", {}),
            "registry_audit": payload.get("registry_audit", {}),
        }
    if lane == "find-complexity-hotspots":
        return {"findings": payload.get("findings", []), "status": payload.get("status")}
    return {"results": payload.get("results", [])}


def _run_lane(
    lane: str,
    *,
    project_root: Path,
    library_root: Path,
    target_argument: str,
    language: str,
    standards: Path | None,
    run_id: str,
) -> dict[str, Any]:
    try:
        command, artifact, accepted = _lane_command(
            lane,
            project_root=project_root,
            library_root=library_root,
            target_argument=target_argument,
            language=language,
            standards=standards,
            run_id=run_id,
        )
    except ValueError as exc:
        return {"skill": lane, "status": "skipped", "reason": str(exc)}
    exit_code, stdout, stderr, wall_ms = _run(command, project_root)
    result: dict[str, Any] = {
        "skill": lane,
        "command": command,
        "artifact": str(artifact),
        "exit_code": exit_code,
        "wall_ms": round(wall_ms, 3),
        "stdout": stdout,
        "stderr": stderr,
    }
    if exit_code not in accepted:
        return {**result, "status": "error", "reason": "unexpected_exit"}
    try:
        raw = _read_json(artifact)
        if not isinstance(raw, dict):
            raise TypeError("final artifact must be an object")
        projection = _semantic_projection(lane, raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        return {**result, "status": "error", "reason": f"invalid_final_artifact: {exc}"}
    return {**result, "status": "complete", "semantic_projection": projection}


def _finding_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    location = row.get("line", row.get("symbol", row.get("id", "")))
    evidence = json.dumps(row.get("evidence"), ensure_ascii=False, sort_keys=True)
    return (
        str(row.get("kind", "")),
        str(row.get("path", "")),
        str(location),
        evidence,
    )


def _synthesize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    findings: list[dict[str, Any]] = []
    clean: list[str] = []
    incomplete: list[str] = []
    for row in rows:
        lane = row["skill"]
        if row["status"] != "complete":
            incomplete.append(lane)
            continue
        projection = row["semantic_projection"]
        if lane == "audit-decisions":
            for drift in projection["drift"]:
                evidence = drift.get("evidence", {})
                findings.append(
                    {
                        "kind": "decision-drift",
                        "skill": lane,
                        "path": evidence.get("path", ""),
                        "line": evidence.get("line"),
                        "id": drift.get("adr_id"),
                        "evidence": drift,
                    }
                )
            nested_drift = [
                *projection.get("link_check", {}).get("drift", []),
                *projection.get("registry_audit", {}).get("drift", []),
            ]
            for drift in nested_drift:
                findings.append(
                    {
                        "kind": "decision-drift",
                        "skill": lane,
                        "path": "ai-docs/decisions",
                        "evidence": drift,
                    }
                )
            if not projection["drift"] and not nested_drift:
                clean.append(lane)
        elif lane == "find-complexity-hotspots":
            for finding in projection["findings"]:
                findings.append(
                    {
                        "kind": "complexity-hotspot",
                        "skill": lane,
                        "path": finding.get("file", ""),
                        "symbol": finding.get("symbol"),
                        "evidence": finding,
                    }
                )
            if projection.get("status") in {"partial", "error"}:
                incomplete.append(lane)
            elif not projection["findings"]:
                clean.append(lane)
        else:
            results = projection["results"]
            non_clean = False
            for standard in results:
                status = standard.get("status")
                if (
                    status != "scanned"
                    or int(standard.get("skipped_files", 0) or 0) > 0
                    or int(standard.get("unsupported_files", 0) or 0) > 0
                ):
                    non_clean = True
                    continue
                for gap in standard.get("gaps", []):
                    findings.append(
                        {
                            "kind": "standard-gap",
                            "skill": lane,
                            "path": gap.get("file", ""),
                            "line": gap.get("line"),
                            "id": standard.get("id"),
                            "evidence": gap,
                        }
                    )
            if non_clean:
                incomplete.append(lane)
            elif not any(row["skill"] == lane for row in findings):
                clean.append(lane)
    deduplicated: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for finding in findings:
        deduplicated.setdefault(_finding_key(finding), finding)
    lane_order = {lane: index for index, lane in enumerate(LANES)}
    ordered = sorted(
        deduplicated.values(),
        key=lambda row: (
            lane_order[row["skill"]],
            row.get("path", ""),
            str(row.get("line", row.get("symbol", row.get("id", "")))),
        ),
    )
    return ordered, list(dict.fromkeys(clean)), list(dict.fromkeys(incomplete))


def _summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Code-health result",
        "",
        f"- Language: `{payload['language']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Findings: {len(payload['synthesis']['findings'])}",
        f"- Clean lanes: {', '.join(payload['synthesis']['clean_lanes']) or 'none'}",
        f"- Incomplete lanes: {', '.join(payload['synthesis']['incomplete_lanes']) or 'none'}",
        f"- Source mutation: {'yes' if payload['source_mutated'] else 'no'}",
        "",
        "## Findings",
        "",
    ]
    if not payload["synthesis"]["findings"]:
        lines.append("No actionable findings were produced by complete lanes.")
    for finding in payload["synthesis"]["findings"]:
        location = finding.get("line", finding.get("symbol", finding.get("id", "")))
        suffix = f":{location}" if location not in {None, ""} else ""
        lines.append(
            f"- `{finding['kind']}` via `{finding['skill']}` — "
            f"`{finding.get('path', '')}{suffix}`"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--library-root", type=Path, required=True)
    parser.add_argument("--target", default="src")
    parser.add_argument("--language", choices=("typescript", "javascript"), required=True)
    parser.add_argument("--standards", type=Path)
    parser.add_argument("--mode", choices=("serial", "parallel"), default="parallel")
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    library_root = args.library_root.resolve()
    target = Path(args.target)
    target_path = (project_root / target).resolve() if not target.is_absolute() else target.resolve()
    standards = args.standards
    if standards is not None and not standards.is_absolute():
        standards = (project_root / standards).resolve()
    elif standards is not None:
        standards = standards.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = (project_root / output_dir).resolve()
    else:
        output_dir = output_dir.resolve()
    report_root = (project_root / "reports" / "code-health").resolve()

    if not project_root.is_dir() or not library_root.is_dir():
        parser.error("project and library roots must exist")
    if not target_path.exists() or not _within(target_path, project_root):
        parser.error("target must exist below project root")
    if not _within(output_dir, report_root):
        parser.error("--output-dir must resolve below <project>/reports/code-health")
    if not args.run_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in args.run_id):
        parser.error("--run-id must contain only letters, digits, dash, or underscore")

    selected = []
    skipped = []
    for lane in LANES:
        inactive_reason = _inactive_reason(project_root, lane)
        if inactive_reason is not None:
            skipped.append({"skill": lane, "reason": inactive_reason})
        elif lane == "audit-decisions" and not (project_root / "ai-docs" / "decisions").is_dir():
            skipped.append({"skill": lane, "reason": "decision_registry_missing"})
        elif lane == "find-complexity-hotspots" and not _has_eligible_source(
            target_path, args.language
        ):
            skipped.append({"skill": lane, "reason": "no_files_matched"})
        elif lane == "find-standard-gaps" and standards is None:
            skipped.append({"skill": lane, "reason": "host_standards_path_not_supplied"})
        elif lane == "find-standard-gaps" and not standards.is_file():
            skipped.append({"skill": lane, "reason": "host_standards_path_missing"})
        elif lane == "find-standard-gaps" and not _standards_dispatchable(standards):
            skipped.append({"skill": lane, "reason": "host_standards_invalid"})
        else:
            selected.append(lane)
    before = _source_digest(target_path)
    started = time.perf_counter_ns()

    kwargs = {
        "project_root": project_root,
        "library_root": library_root,
        "target_argument": str(target_path.relative_to(project_root)),
        "language": args.language,
        "standards": standards,
        "run_id": args.run_id,
    }
    if args.mode == "parallel":
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {lane: executor.submit(_run_lane, lane, **kwargs) for lane in selected}
            rows = [futures[lane].result() for lane in selected]
    else:
        rows = [_run_lane(lane, **kwargs) for lane in selected]
    rows.extend({"skill": row["skill"], "status": "skipped", "reason": row["reason"]} for row in skipped)
    rows.sort(key=lambda row: LANES.index(row["skill"]))
    wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    after = _source_digest(target_path)
    findings, clean, incomplete = _synthesize(rows)
    source_mutated = before != after
    failures = [row["skill"] for row in rows if row["status"] == "error"]
    if source_mutated:
        failures.append("source_mutation")
    payload = {
        "schema_version": 1,
        "family": "code-health-readonly",
        "language": args.language,
        "mode": args.mode,
        "target": str(target_path.relative_to(project_root)),
        "wall_ms": round(wall_ms, 3),
        "source_digest_before": before,
        "source_digest_after": after,
        "source_mutated": source_mutated,
        "lanes": rows,
        "synthesis": {
            "findings": findings,
            "clean_lanes": clean,
            "incomplete_lanes": incomplete,
        },
        "failures": failures,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "family-result.json", payload)
    (output_dir / "summary.md").write_text(_summary_markdown(payload), encoding="utf-8")
    print(output_dir / "family-result.json")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
