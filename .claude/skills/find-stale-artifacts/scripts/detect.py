#!/usr/bin/env python3
"""Detect stale working artifacts under ai-docs/plans/ and reports/.

Detection bands:
  - abandoned_plan:        plan with `status: abandoned` in frontmatter.
  - stale_plan:            plan with in-flight status whose frontmatter
                           `date:` is older than the soft staleness budget.
  - aged_scan_dir:         reports/<skill>/scan-<TS>/ older than the soft
                           budget, not pointed at by `latest`, and not
                           referenced by any tracked artifact.
  - orphan_toplevel_report: reports/*.md at the top level, not in the
                           known-active list, untouched in git for >N days.

Output: JSONL with one finding per line. Each record has the keys
`pattern`, `file`, `lineno`, `summary`, `recommendation` so the shared
render_simple_report helper can render it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MAX_PLAN_AGE_DAYS = 60
DEFAULT_MAX_SCAN_AGE_DAYS = 30
DEFAULT_MAX_TOPLEVEL_AGE_DAYS = 30

IN_FLIGHT_PLAN_STATUSES = {"draft", "proposed", "scoped", "impacted", "architected"}
KNOWN_ACTIVE_TOPLEVEL = {"BACKLOG.md", "skill-ecosystem-backlog.md"}

SCAN_DIR_RE = re.compile(r"^scan-(\d{8})-(\d{6})(?:-.*)?$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(path: Path) -> tuple[dict[str, str], int]:
    """Return (frontmatter_dict, frontmatter_end_line) for a markdown file.

    Handles only flat `key: value` pairs — sufficient for plan/spec
    frontmatter, which never nests. Returns ({}, 0) if no frontmatter.
    """
    if not path.exists():
        return {}, 0
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, 0
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, 0
    block = match.group(1)
    fm: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    end_line = block.count("\n") + 2  # +2 for the two `---` fence lines
    return fm, end_line


def parse_plan_date(value: str) -> datetime | None:
    """Parse a plan-frontmatter `date:` value to a UTC datetime."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_scan_dir_timestamp(name: str) -> datetime | None:
    """Parse a `scan-YYYYMMDD-HHMMSS[-suffix]` directory name to UTC datetime."""
    match = SCAN_DIR_RE.match(name)
    if not match:
        return None
    try:
        return datetime.strptime(
            match.group(1) + match.group(2), "%Y%m%d%H%M%S"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def git_last_commit_ts(path: Path, project_root: Path) -> datetime | None:
    """Return the last-commit UTC timestamp for `path`, or None if untracked."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.fromtimestamp(int(result.stdout.strip()), tz=timezone.utc)
    except ValueError:
        return None


def collect_referenced_scan_ids(project_root: Path) -> set[str]:
    """Return the set of scan-IDs (`scan-YYYYMMDD-HHMMSS[-suffix]`) referenced
    anywhere outside `reports/`, `.git/`, vendor dirs, etc.

    Single batched grep — returning *every* scan-ID reference at once is much
    faster than asking grep N times whether scan #N is referenced.
    """
    result = subprocess.run(
        [
            "grep",
            "-rho",
            "--exclude-dir=reports",
            "--exclude-dir=.git",
            "--exclude-dir=worktrees",
            "--exclude-dir=__pycache__",
            "--exclude-dir=.venv",
            "--exclude-dir=node_modules",
            "-E",
            r"scan-[0-9]{8}-[0-9]{6}(-[A-Za-z0-9_.-]+)?",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def detect(
    *,
    project_root: Path,
    plans_root: Path,
    reports_root: Path,
    max_plan_age_days: int,
    max_scan_age_days: int,
    max_toplevel_age_days: int,
    now: datetime,
) -> list[dict]:
    findings: list[dict] = []

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    # 1. + 2. abandoned_plan and stale_plan
    if plans_root.is_dir():
        for plan in sorted(plans_root.glob("*.md")):
            if plan.name in {"README.md"}:
                continue
            fm, _ = parse_frontmatter(plan)
            status = fm.get("status", "").lower()
            if status == "abandoned":
                findings.append({
                    "pattern": "abandoned_plan",
                    "file": rel(plan),
                    "lineno": 1,
                    "summary": (
                        "Plan declares `status: abandoned`. The abandonment is "
                        "recorded in git history; the file itself is no longer "
                        "load-bearing."
                    ),
                    "recommendation": (
                        "Delete the file. If the work paused rather than "
                        "terminated, capture the pointer in the relevant backlog "
                        "and delete the plan anyway — empty templates with status "
                        "notes are noise."
                    ),
                })
                continue
            if status in IN_FLIGHT_PLAN_STATUSES:
                plan_date = parse_plan_date(fm.get("date", ""))
                if plan_date is None:
                    continue
                age_days = (now - plan_date).days
                if age_days > max_plan_age_days:
                    findings.append({
                        "pattern": "stale_plan",
                        "file": rel(plan),
                        "lineno": 1,
                        "summary": (
                            f"Plan is `status: {status}` with frontmatter date "
                            f"{plan_date.date()} — {age_days} days old "
                            f"(> {max_plan_age_days}-day soft budget)."
                        ),
                        "recommendation": (
                            "Refresh, promote, or abandon. A plan that sits in "
                            f"`{status}` past the budget is signal that the work "
                            "was either silently shelved or completed via a "
                            "different surface."
                        ),
                    })

    # 3. aged_scan_dir
    if reports_root.is_dir():
        referenced_scan_ids = collect_referenced_scan_ids(project_root)
        for skill_dir in sorted(reports_root.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            latest_link = skill_dir / "latest"
            latest_target: Path | None = None
            if latest_link.is_symlink():
                try:
                    latest_target = (skill_dir / latest_link.readlink()).resolve()
                except OSError:
                    latest_target = None
            for scan_dir in sorted(skill_dir.iterdir()):
                if not scan_dir.is_dir():
                    continue
                ts = parse_scan_dir_timestamp(scan_dir.name)
                if ts is None:
                    continue
                if latest_target is not None:
                    try:
                        if scan_dir.resolve() == latest_target:
                            continue
                    except OSError:
                        pass
                age_days = (now - ts).days
                if age_days <= max_scan_age_days:
                    continue
                if scan_dir.name in referenced_scan_ids:
                    continue  # referenced from outside reports/ — keep for audit trail
                findings.append({
                    "pattern": "aged_scan_dir",
                    "file": rel(scan_dir),
                    "lineno": 1,
                    "summary": (
                        f"Scan directory is {age_days} days old "
                        f"(> {max_scan_age_days}-day soft budget) and not the target "
                        f"of {rel(latest_link)}."
                    ),
                    "recommendation": (
                        "Delete the directory unless the scan is referenced from a "
                        "tracked artifact. The skill checked the repo for "
                        f"references to `{scan_dir.name}` outside `reports/` and "
                        "found none."
                    ),
                })

    # 4. orphan_toplevel_report
    if reports_root.is_dir():
        for entry in sorted(reports_root.glob("*.md")):
            if not entry.is_file():
                continue
            if entry.name in KNOWN_ACTIVE_TOPLEVEL:
                continue
            last_commit = git_last_commit_ts(entry, project_root)
            if last_commit is None:
                # Untracked or never committed. Use mtime as a fallback.
                try:
                    mtime = datetime.fromtimestamp(
                        entry.stat().st_mtime, tz=timezone.utc
                    )
                except OSError:
                    continue
                age_days = (now - mtime).days
                source = "filesystem mtime (untracked)"
            else:
                age_days = (now - last_commit).days
                source = "last git commit"
            if age_days <= max_toplevel_age_days:
                continue
            findings.append({
                "pattern": "orphan_toplevel_report",
                "file": rel(entry),
                "lineno": 1,
                "summary": (
                    f"Top-level report file untouched for {age_days} days "
                    f"(> {max_toplevel_age_days}-day soft budget; source: {source}) "
                    f"and not in the known-active list "
                    f"({', '.join(sorted(KNOWN_ACTIVE_TOPLEVEL))})."
                ),
                "recommendation": (
                    "Confirm the file is still working state or delete. Top-level "
                    "report files have no skill-imposed rotation; they accumulate "
                    "manually until someone notices."
                ),
            })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--plans-subdir", default="ai-docs/plans")
    parser.add_argument("--reports-subdir", default="reports")
    parser.add_argument("--max-plan-age-days", type=int, default=DEFAULT_MAX_PLAN_AGE_DAYS)
    parser.add_argument("--max-scan-age-days", type=int, default=DEFAULT_MAX_SCAN_AGE_DAYS)
    parser.add_argument(
        "--max-toplevel-age-days",
        type=int,
        default=DEFAULT_MAX_TOPLEVEL_AGE_DAYS,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.root.resolve()
    plans_root = project_root / args.plans_subdir
    reports_root = project_root / args.reports_subdir

    findings = detect(
        project_root=project_root,
        plans_root=plans_root,
        reports_root=reports_root,
        max_plan_age_days=args.max_plan_age_days,
        max_scan_age_days=args.max_scan_age_days,
        max_toplevel_age_days=args.max_toplevel_age_days,
        now=datetime.now(tz=timezone.utc),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")

    print(f"detect: wrote {len(findings)} findings to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
