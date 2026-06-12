#!/usr/bin/env python3
"""Detector for orphaned ideas in the Tier 1 idea ledger.

Three modes:
    --stale            in-flight ideas with no event in N days
    --harvest          has-more-potential ideas not in-flight
    --plan-dropouts <path>  items in a plan file missing from the ledger

Usage:
    find.py [--stale|--harvest|--plan-dropouts PATH|--all]
            [--stale-days N] [--apply-stale] [--json]

Exit codes:
    0 success (findings may or may not be present)
    1 write error during --apply-stale
    2 usage error (missing plan file, unknown mode, etc.)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".claude" / "skills" / "_common"))

import engineering_home as _home  # noqa: E402
import ideas_lib as L  # noqa: E402

LEDGER = REPO_ROOT / ".claude" / "ideas" / "log.jsonl"

BULLET_RE = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")

TODO_RE = re.compile(r"(?:#|//)\s*(TODO|FIXME)[:\s]\s*(.+?)$", re.IGNORECASE)
SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache", ".idea",
    ".next", ".cache", "site-packages",
})
SOURCE_EXTENSIONS = frozenset({".py", ".js", ".ts", ".tsx", ".jsx"})

TIER_ORDER = {"critical": 0, "core": 1, "supporting": 2}
TIER_RE = re.compile(r"^\s*Tier\s*:\s*([A-Za-z-]+)", re.IGNORECASE)
LOCATOR_RE = re.compile(r"^\s*-\s*`(path|kind):([^`]+)`\s*(?:—\s*(.*))?$")


def _git_file_mtime(path: Path) -> datetime | None:
    """Last-commit timestamp for a file via `git log -1`. Returns None on error."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.fromtimestamp(int(result.stdout.strip()), tz=timezone.utc)
    except ValueError:
        return None


def _parse_plan_status(text: str) -> str | None:
    """Extract `status` from YAML frontmatter or a `**Status:**` line."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("status:"):
                    return stripped.split(":", 1)[1].strip().strip("\"'").lower()
    m = re.search(
        r"\*\*\s*Status\s*[:\*]+\s*([a-zA-Z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().lower()
    return None


def _load_todo_tuning(repo_root: Path) -> dict:
    """Read optional todo-tuning.md (path skips, min-words override).

    Resolved from `.engineering/docs/todo-tuning.md`, falling back to the
    legacy `.claude/docs/todo-tuning.md` during the ADR 0021 transition.

    Format (loose): under `## Path skip`, each bullet's leading
    backtick-delimited token is the glob pattern. Under `## Min words`,
    the first bare integer line wins.
    """
    out: dict = {"path_skip": [], "min_words": None}
    path, _used_legacy = _home.docs_path(
        repo_root, "todo-tuning.md", legacy_claude_docs=True
    )
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    section: str | None = None
    backtick_pattern = re.compile(r"`([^`]+)`")
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if heading in {"path skip", "paths to skip", "skip", "path-skip"}:
                section = "path_skip"
            elif heading in {"min words", "minimum words", "min-words"}:
                section = "min_words"
            else:
                section = None
            continue
        if section == "path_skip" and line.startswith("-"):
            body = line[1:].strip()
            m = backtick_pattern.search(body)
            pattern = m.group(1).strip() if m else body.split(" — ", 1)[0].strip()
            if pattern:
                out["path_skip"].append(pattern)
        elif section == "min_words":
            # Honor the doc's stated contract: "the first integer-only line
            # wins; comment lines (starting with `#`) are skipped." The old
            # lstrip("#") turned a "# 4" comment into the value 4 — it only
            # appeared correct when the comment's number matched the default.
            if not line or line.startswith("#"):
                continue
            try:
                out["min_words"] = int(line.split()[0])
                section = None
            except (ValueError, IndexError):
                pass
    return out


def _walk_source_files(repo_root: Path) -> list[Path]:
    """Walk repo for source files matching SOURCE_EXTENSIONS, pruning SKIP_DIRS."""
    out: list[Path] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if Path(fname).suffix in SOURCE_EXTENSIONS:
                out.append(Path(root) / fname)
    return out


def extract_plan_items(text: str) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = BULLET_RE.match(line) or HEADING_RE.match(line)
        if not m:
            continue
        title = m.group(1).strip().strip("`").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        items.append(title)
    return items


def detect_stale(records: list[dict], stale_days: int) -> list[dict]:
    ids = L.find_stalled(records, stale_days=stale_days)
    projs = L.project_all(records)
    out: list[dict] = []
    for idea_id in ids:
        proj = projs[idea_id]
        last_at = proj["last_event_at"]
        out.append({
            "id": idea_id,
            "title": proj["title"],
            "last_event_at": last_at,
        })
    return out


def detect_harvest(records: list[dict]) -> list[dict]:
    ids = L.find_harvest_opportunities(records)
    projs = L.project_all(records)
    out: list[dict] = []
    for idea_id in ids:
        proj = projs[idea_id]
        out.append({
            "id": idea_id,
            "title": proj["title"],
            "state": proj["state"],
            "quality_markers": proj["quality_markers"],
        })
    return out


def detect_plan_dropouts(records: list[dict], plan_path: Path) -> list[str]:
    if not plan_path.exists():
        return []
    try:
        text = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    items = extract_plan_items(text)
    if not items:
        return []
    return L.find_plan_dropouts(records, items)


def detect_todo_orphans(
    repo_root: Path,
    *,
    min_words: int = 4,
    min_age_days: int | None = None,
    path_skip: list[str] | None = None,
) -> list[dict]:
    """Find TODO/FIXME comments worth surfacing for ledger intake.

    Over-surfaces by default — no upper age bound, no test-file skip.
    User prunes via the brainstorm.py hand-off downstream.
    """
    skip_patterns = path_skip or []
    now = datetime.now(timezone.utc)

    out: list[dict] = []
    for fpath in _walk_source_files(repo_root):
        rel = fpath.relative_to(repo_root)
        rel_str = str(rel)

        if any(fnmatch.fnmatch(rel_str, p) for p in skip_patterns):
            continue

        if min_age_days is not None:
            mtime = _git_file_mtime(fpath)
            if mtime is None:
                continue
            age_days = (now - mtime).days
            if age_days < min_age_days:
                continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(content.splitlines(), 1):
            m = TODO_RE.search(line)
            if not m:
                continue
            kind = m.group(1).upper()
            body = m.group(2).strip()
            if len(body.split()) < min_words:
                continue
            out.append({
                "kind": kind,
                "body": body,
                "file": rel_str,
                "line": lineno,
            })
    return out


def detect_stale_plans(
    repo_root: Path,
    records: list[dict],
    *,
    stale_threshold_days: int = 30,
) -> list[dict]:
    """Find ai-docs/plans/*.md in a non-terminal status, untouched > N days, not actively tracked in the ledger.

    Non-terminal = every status a plan can stall in (scripts/plans.py
    VALID_STATUSES minus terminal promoted/abandoned) plus legacy
    "proposed" for host projects that use it. Untracked plans fall back
    to filesystem mtime — an uncommitted plan still ages. A ledger slug
    match only exempts the plan while the ledger idea is in-flight
    (--stale owns the watching then); a proposed-state intake is not
    active tracking.
    """
    non_terminal = {"draft", "proposed", "scoped", "impacted", "architected"}
    plans_dir = repo_root / "ai-docs" / "plans"
    if not plans_dir.exists():
        return []

    projections = L.project_all(records)
    ledger_states = {
        k: (v.get("state") if isinstance(v, dict) else None)
        for k, v in projections.items()
    }
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=stale_threshold_days)

    out: list[dict] = []
    for plan_path in sorted(plans_dir.glob("*.md")):
        try:
            text = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        status = _parse_plan_status(text)
        if status not in non_terminal:
            continue

        mtime = _git_file_mtime(plan_path)
        if mtime is None:
            try:
                mtime = datetime.fromtimestamp(
                    plan_path.stat().st_mtime, tz=timezone.utc
                )
            except OSError:
                continue
        if mtime > threshold:
            continue

        slug = plan_path.stem.lower().replace("_", "-")
        if ledger_states.get(slug) == "in-flight":
            continue

        out.append({
            "path": str(plan_path.relative_to(repo_root)),
            "slug": slug,
            "status": status,
            "last_modified": mtime.isoformat(),
            "days_silent": (now - mtime).days,
        })
    return out


def detect_dead_prototype(
    repo_root: Path,
    from_report: Path | None,
) -> list[dict]:
    """Surface orphan candidates from a /find-dormant report.

    Requires --from-report or auto-resolves the most recent
    reports/find-dormant/scan-*/ (by directory mtime). Downstream of
    /find-dormant's output schema — a schema change there is breaking.
    """
    if from_report is None:
        scans_dir = repo_root / "reports" / "find-dormant"
        if not scans_dir.exists():
            raise ValueError(
                "dead-prototype mode requires --from-report PATH or "
                "an existing reports/find-dormant/scan-*/ directory; "
                "neither was found. Run /find-dormant first or pass --from-report."
            )
        scans = sorted(
            (p for p in scans_dir.iterdir()
             if p.is_dir() and p.name.startswith("scan-")),
            key=lambda p: p.stat().st_mtime,
        )
        if not scans:
            raise ValueError(
                "dead-prototype mode requires --from-report PATH or "
                "a scan-* subdirectory under reports/find-dormant/; "
                "the directory exists but contains no scans."
            )
        latest = scans[-1]
        report_candidates = sorted(latest.glob("*.json"))
        if not report_candidates:
            raise ValueError(
                f"latest scan {latest.relative_to(repo_root)} has no JSON report file"
            )
        from_report = report_candidates[0]

    if not from_report.exists():
        raise ValueError(f"--from-report path does not exist: {from_report}")

    try:
        data = json.loads(from_report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not parse --from-report as JSON: {exc}") from exc

    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("items", "findings", "dormant", "results", "candidates"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            raise ValueError(
                "--from-report JSON has no recognized items array "
                "(expected one of: items, findings, dormant, results, candidates)"
            )
    else:
        raise ValueError(
            f"--from-report JSON has unexpected shape: {type(data).__name__}"
        )

    try:
        report_label = str(from_report.relative_to(repo_root))
    except ValueError:
        report_label = str(from_report)

    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append({
            "path": (
                item.get("path") or item.get("file")
                or item.get("route") or item.get("template") or "?"
            ),
            "reason": (
                item.get("reason") or item.get("description")
                or item.get("kind") or item.get("status") or ""
            ),
            "source_report": report_label,
        })
    return out


def _parse_importance_map(text: str) -> list[dict]:
    """Parse importance-map.md per ADR 0016.

    Returns a list of areas:
        [{"name": str, "tier": str, "locators": [{"kind": "path"|"kind",
                                                  "value": str,
                                                  "note": str}], ...]
    Skips areas missing a tier or locators (with a flag) — the caller
    decides whether to surface diagnostics.
    """
    areas: list[dict] = []
    current: dict | None = None
    in_locators = False

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.startswith("## "):
            heading = line[3:].strip()
            if current is not None:
                areas.append(current)
            current = {
                "name": heading,
                "tier": None,
                "locators": [],
                "notes": "",
            }
            in_locators = False
            continue

        if current is None:
            continue

        if line.startswith("# "):
            continue

        m = TIER_RE.match(line)
        if m:
            current["tier"] = m.group(1).strip().lower()
            in_locators = False
            continue

        stripped = line.strip()
        if stripped.lower().startswith("locators:"):
            in_locators = True
            continue
        if stripped.lower().startswith("notes:"):
            in_locators = False
            current["notes"] = stripped.split(":", 1)[1].strip()
            continue

        if in_locators:
            loc = LOCATOR_RE.match(line)
            if loc:
                current["locators"].append({
                    "kind": loc.group(1).lower(),
                    "value": loc.group(2).strip(),
                    "note": (loc.group(3) or "").strip(),
                })

    if current is not None:
        areas.append(current)

    return [a for a in areas if a["tier"] and a["locators"]]


def detect_attention_gap(
    repo_root: Path,
    records: list[dict],
) -> dict:
    """Read importance-map.md (ADR 0016) and produce a ranked report.

    Resolved from `.engineering/docs/importance-map.md`, falling back to the
    legacy `.claude/docs/importance-map.md` during the ADR 0021 transition.

    Skeleton per Improvement 3 / ADR 0016:
        - File absent or empty → {"status": "no_map", "areas": [], "drift": []}
          (caller emits the "no importance map declared" notice).
        - File malformed → {"status": "malformed", "error": str}
          (diagnostic, no crash).
        - Otherwise → {"status": "ok", "areas": [...], "drift": [...]}
          where each area is ranked by tier (critical > core > supporting).

    Drift detector flags `path:` entries whose path doesn't exist and
    `kind:` entries that don't appear in the ledger's subsystem_kind set.

    Signal joins / output columns / "useful audit" threshold are deferred
    to the post-ADR addendum — the skeleton ships the graceful-degradation
    path and a rendered table with locator counts.
    """
    map_path, _used_legacy = _home.docs_path(
        repo_root, "importance-map.md", legacy_claude_docs=True
    )
    if not map_path.exists():
        return {"status": "no_map", "areas": [], "drift": []}

    try:
        text = map_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"status": "malformed", "error": str(exc), "areas": [], "drift": []}

    if not text.strip():
        return {"status": "no_map", "areas": [], "drift": []}

    try:
        areas = _parse_importance_map(text)
    except Exception as exc:  # noqa: BLE001 — any parse failure becomes a structured "malformed" result
        return {
            "status": "malformed",
            "error": f"could not parse importance-map.md: {exc}",
            "areas": [],
            "drift": [],
        }

    if not areas:
        return {
            "status": "malformed",
            "error": (
                "importance-map.md has no parseable areas — each '## <area>' "
                "section needs a 'Tier:' line and at least one locator. "
                "See ADR 0016."
            ),
            "areas": [],
            "drift": [],
        }

    projections = L.project_all(records)
    known_kinds = {
        proj.get("subsystem_kind") for proj in projections.values()
        if proj.get("subsystem_kind")
    }

    drift: list[dict] = []
    for area in areas:
        for loc in area["locators"]:
            if loc["kind"] == "path":
                value = loc["value"]
                stripped = value.split("*", 1)[0].rstrip("/")
                if stripped and not (repo_root / stripped).exists():
                    drift.append({
                        "area": area["name"],
                        "kind": "path",
                        "value": value,
                        "reason": "path does not exist",
                    })
            elif loc["kind"] == "kind":
                if loc["value"] not in known_kinds:
                    drift.append({
                        "area": area["name"],
                        "kind": "kind",
                        "value": loc["value"],
                        "reason": "subsystem_kind not seen in ledger",
                    })

    areas.sort(key=lambda a: (TIER_ORDER.get(a["tier"], 99), a["name"].lower()))

    return {"status": "ok", "areas": areas, "drift": drift}


def apply_stale(stale: list[dict]) -> tuple[int, list[str]]:
    failures: list[str] = []
    written = 0
    for finding in stale:
        rec = {
            "record_kind": "event",
            "id": finding["id"],
            "event_at": L.utc_now_iso(),
            "event_kind": "transition",
            "from_state": "in-flight",
            "to_state": "stalled",
            "summary": "auto-detected stale after inactivity",
        }
        try:
            L.append_record(LEDGER, rec)
            written += 1
        except ValueError as exc:
            failures.append(f"{finding['id']}: {exc}")
            break
    return written, failures


def render_markdown(
    findings: dict,
    *,
    stale_days: int,
    stale_plans_days: int,
    now_iso: str,
) -> str:
    lines: list[str] = [
        f"# Orphaned-idea audit (now: {now_iso}, stale_days: {stale_days})",
        "",
    ]

    stale = findings.get("stale")
    if stale is not None:
        lines.append("## Stale (in-flight > stale_days)")
        if not stale:
            lines.append("- (none)")
        else:
            for f in stale:
                lines.append(f"- `{f['id']}` — {f['title']}")
                lines.append(f"  (last event: {f['last_event_at']})")
        lines.append("")

    harvest = findings.get("harvest")
    if harvest is not None:
        lines.append("## Harvest opportunities (has-more-potential, not in-flight)")
        if not harvest:
            lines.append("- (none)")
        else:
            for f in harvest:
                markers = ",".join(f["quality_markers"]) or "-"
                lines.append(f"- `{f['id']}` — {f['title']} [{f['state']}]")
                lines.append(f"  (markers: {markers})")
        lines.append("")

    plan_dropouts = findings.get("plan_dropouts")
    if plan_dropouts is not None:
        path, items = plan_dropouts
        lines.append(f"## Plan-dropouts (in `{path}`, missing from ledger)")
        if not items:
            lines.append("- (none)")
        else:
            for item in items:
                lines.append(f"- {item}")
        lines.append("")

    todo = findings.get("todo")
    if todo is not None:
        lines.append("## TODO/FIXME orphans")
        if not todo:
            lines.append("- (none)")
        else:
            for f in todo:
                lines.append(
                    f"- `{f['file']}:{f['line']}` [{f['kind']}] — {f['body']}"
                )
        lines.append("")

    stale_plans = findings.get("stale_plans")
    if stale_plans is not None:
        lines.append(
            f"## Stale plans (proposed, > {stale_plans_days}d silent, missing from ledger)"
        )
        if not stale_plans:
            lines.append("- (none)")
        else:
            for f in stale_plans:
                lines.append(
                    f"- `{f['path']}` — {f['days_silent']}d silent "
                    f"(last commit: {f['last_modified']})"
                )
        lines.append("")

    dead_prototype = findings.get("dead_prototype")
    if dead_prototype is not None:
        lines.append("## Dead-prototype candidates (from /find-dormant report)")
        if not dead_prototype:
            lines.append("- (none)")
        else:
            for f in dead_prototype:
                reason = f" — {f['reason']}" if f.get("reason") else ""
                lines.append(f"- `{f['path']}`{reason}")
        lines.append("")

    attention_gap = findings.get("attention_gap")
    if attention_gap is not None:
        lines.append("## Attention gap (importance-weighted, ADR 0016)")
        status = attention_gap.get("status")
        if status == "no_map":
            lines.append(
                "- No importance map declared — see "
                "`ai-docs/decisions/0016-importance-map-shape.md` for the "
                "format and create `.engineering/docs/importance-map.md`."
            )
        elif status == "malformed":
            lines.append(f"- Malformed importance-map.md: {attention_gap.get('error')}")
        else:
            areas = attention_gap.get("areas", [])
            if not areas:
                lines.append("- (no areas declared)")
            else:
                for area in areas:
                    locator_count = len(area["locators"])
                    lines.append(
                        f"- [{area['tier']}] **{area['name']}** "
                        f"({locator_count} locator{'s' if locator_count != 1 else ''})"
                    )
                    for loc in area["locators"]:
                        note = f" — {loc['note']}" if loc["note"] else ""
                        lines.append(f"  - `{loc['kind']}:{loc['value']}`{note}")
            drift = attention_gap.get("drift", [])
            if drift:
                lines.append("")
                lines.append("### Drift (locators that no longer resolve)")
                for d in drift:
                    lines.append(
                        f"- [{d['area']}] `{d['kind']}:{d['value']}` — {d['reason']}"
                    )
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Orphaned-idea detector")
    p.add_argument("--stale", action="store_true")
    p.add_argument("--harvest", action="store_true")
    p.add_argument("--plan-dropouts", type=Path)
    p.add_argument(
        "--todo", action="store_true",
        help="Scan source for TODO/FIXME orphans",
    )
    p.add_argument(
        "--stale-plans", action="store_true",
        help="Find proposed plans > N days silent with no ledger intake",
    )
    p.add_argument(
        "--dead-prototype", action="store_true",
        help="Surface orphans from a /find-dormant report",
    )
    p.add_argument(
        "--attention-gap", action="store_true",
        help="Importance-weighted attention audit (reads ADR 0016 importance map)",
    )
    p.add_argument("--all", action="store_true")
    p.add_argument("--stale-days", type=int, default=L.DEFAULT_STALE_DAYS)
    p.add_argument(
        "--stale-plans-days", type=int, default=30,
        help="Threshold for --stale-plans (default 30)",
    )
    p.add_argument(
        "--min-age-days", type=int, default=None,
        help="Optional file-age floor for --todo (uses git mtime)",
    )
    p.add_argument(
        "--min-words", type=int, default=None,
        help="Min words in TODO body to surface (default 4)",
    )
    p.add_argument(
        "--from-report", type=Path,
        help="Path to /find-dormant JSON report (for --dead-prototype)",
    )
    p.add_argument("--apply-stale", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    any_mode = any([
        args.stale, args.harvest, args.plan_dropouts,
        args.todo, args.stale_plans, args.dead_prototype,
        args.attention_gap, args.all,
    ])
    if not any_mode:
        args.all = True

    if args.plan_dropouts and not args.plan_dropouts.exists():
        print(f"error: plan file not found: {args.plan_dropouts}", file=sys.stderr)
        return 2

    records = L.load_ledger(LEDGER)

    todo_config = _load_todo_tuning(REPO_ROOT)
    # Precedence: an explicit --min-words (any value, including 4) wins; else
    # the host's todo-tuning.md override; else the built-in default of 4. The
    # None argparse default is what lets us distinguish "user passed 4" from
    # "user passed nothing" — the old `== 4` sentinel could not.
    if args.min_words is not None:
        todo_min_words = args.min_words
    elif todo_config["min_words"] is not None:
        todo_min_words = todo_config["min_words"]
    else:
        todo_min_words = 4

    findings: dict = {}

    if args.stale or args.all:
        findings["stale"] = detect_stale(records, args.stale_days)
    if args.harvest or args.all:
        findings["harvest"] = detect_harvest(records)
    if args.plan_dropouts:
        findings["plan_dropouts"] = (
            args.plan_dropouts,
            detect_plan_dropouts(records, args.plan_dropouts),
        )
    if args.todo:
        findings["todo"] = detect_todo_orphans(
            REPO_ROOT,
            min_words=todo_min_words,
            min_age_days=args.min_age_days,
            path_skip=todo_config["path_skip"],
        )
    if args.stale_plans:
        findings["stale_plans"] = detect_stale_plans(
            REPO_ROOT, records,
            stale_threshold_days=args.stale_plans_days,
        )
    if args.dead_prototype:
        try:
            findings["dead_prototype"] = detect_dead_prototype(
                REPO_ROOT, args.from_report,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.attention_gap:
        findings["attention_gap"] = detect_attention_gap(REPO_ROOT, records)

    if args.apply_stale and findings.get("stale"):
        written, failures = apply_stale(findings["stale"])
        if failures:
            print(
                f"applied {written}; then failed: {'; '.join(failures)}",
                file=sys.stderr,
            )
            return 1
        records = L.load_ledger(LEDGER)
        findings["stale"] = detect_stale(records, args.stale_days)

    now_iso = L.utc_now_iso()
    if args.json:
        plan_drop = findings.get("plan_dropouts")
        payload = {
            "now": now_iso,
            "stale_days": args.stale_days,
            "stale_plans_days": args.stale_plans_days,
            "stale": findings.get("stale") or [],
            "harvest": findings.get("harvest") or [],
            "plan_dropouts": {
                "path": str(plan_drop[0]) if plan_drop else None,
                "items": plan_drop[1] if plan_drop else [],
            },
            "todo": findings.get("todo") or [],
            "stale_plans": findings.get("stale_plans") or [],
            "dead_prototype": findings.get("dead_prototype") or [],
            "attention_gap": findings.get("attention_gap") or {
                "status": "not_requested", "areas": [], "drift": []
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_markdown(
            findings,
            stale_days=args.stale_days,
            stale_plans_days=args.stale_plans_days,
            now_iso=now_iso,
        ))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
