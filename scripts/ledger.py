#!/usr/bin/env python
"""
File review ledger CLI for architecture drift tracking.

Tracks per-file review state (last reviewed, decision, rationale, next review
threshold) and surfaces files that need attention based on size, age, or growth.

Subcommands:
  list           List ledger entries with optional filters
  show           Show one entry with full history
  update         Upsert an entry (snapshots prior state to history)
  needs-review   List entries past their review threshold
  drift-scan     Walk the repo, find big files not in the ledger
  history        Show an entry's audit trail

Backing store: reports/architecture/ledger.json (override via --ledger-path).

Read-only on source files by default. Only `update` mutates the ledger JSON.

Usage:
  .venv/bin/python scripts/ledger.py list
  .venv/bin/python scripts/ledger.py list --decision split_queued --json
  .venv/bin/python scripts/ledger.py show core/tasks.py
  .venv/bin/python scripts/ledger.py update core/tasks.py \\
      --decision split_queued \\
      --rationale "10K LOC monolith; see ai-docs/specs/async-tasks.md" \\
      --owner refactor-subsystem \\
      --next-review-days 30
  .venv/bin/python scripts/ledger.py needs-review --above-loc 5000
  .venv/bin/python scripts/ledger.py drift-scan core --above-loc 2000

Exit codes: 0 = results / success, 1 = no results / empty, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
DEFAULT_LEDGER_PATH = REPO_ROOT / "reports" / "architecture" / "ledger.json"
LEDGER_VERSION = 1

VALID_DECISIONS = {
    "no_action",
    "monitor",
    "split_queued",
    "split_in_progress",
    "split_complete",
    "consolidate_queued",
    "consolidate_in_progress",
    "consolidate_complete",
    "delete_queued",
    "delete_complete",
}

# Decisions that already have a planned action — skip re-review suggestions.
SKIP_REREVIEW_DECISIONS = {
    "split_queued",
    "split_in_progress",
    "consolidate_queued",
    "consolidate_in_progress",
    "delete_queued",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "staticfiles",
    "migrations",
}


# ---------------------------------------------------------------------------
# Pure functions (testable without argparse)
# ---------------------------------------------------------------------------


def load_ledger(path: Path) -> dict:
    """Read ledger JSON; return empty ledger if file absent or empty."""
    if not path.exists() or path.stat().st_size == 0:
        return {"version": LEDGER_VERSION, "entries": {}}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"cannot read ledger at {path}: {exc}") from exc
    if not isinstance(data, dict) or "entries" not in data:
        raise RuntimeError(f"ledger at {path} is malformed (expected dict with 'entries')")
    data.setdefault("version", LEDGER_VERSION)
    if not isinstance(data["entries"], dict):
        raise RuntimeError(f"ledger at {path} is malformed ('entries' must be object)")
    return data


def save_ledger(data: dict, path: Path) -> None:
    """Write ledger JSON atomically (.tmp then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_last_commit_date(rel_path: str, root: Path) -> str | None:
    """Return YYYY-MM-DD of the file's last commit, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def count_loc(abs_path: Path) -> int:
    """Return newline count for a file; 0 on read failure."""
    try:
        with abs_path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def compute_file_metrics(rel_path: str, root: Path) -> dict:
    """Measure a file on disk. Returns dict with loc + last_commit."""
    abs_path = root / rel_path
    return {
        "loc": count_loc(abs_path),
        "last_commit": git_last_commit_date(rel_path, root),
    }


def iter_py_files(
    root: Path, scan_root: Path, ignore: Iterable[str] = ()
) -> Iterator[str]:
    """Yield relative paths of .py files under scan_root, skipping ignored dirs."""
    skip = IGNORED_DIRS | set(ignore)
    for dirpath, dirs, files in os.walk(scan_root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip]
        for f in files:
            if f.endswith(".py"):
                abs_p = Path(dirpath) / f
                try:
                    yield str(abs_p.relative_to(root))
                except ValueError:
                    continue


def upsert_entry(
    ledger: dict,
    rel_path: str,
    *,
    decision: str,
    rationale: str,
    metrics: dict | None = None,
    owner: str | None = None,
    next_review_days: int | None = None,
    next_review_loc_delta: int | None = None,
    reviewer: str = "claude-code",
    today: str | None = None,
    now: str | None = None,
) -> dict:
    """Insert or update an entry. Pushes prior state to history before updating."""
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"invalid decision {decision!r}; valid: {sorted(VALID_DECISIONS)}"
        )
    entries = ledger.setdefault("entries", {})
    today = today or today_iso()
    now = now or now_iso()

    existing = entries.get(rel_path)
    history: list[dict] = []
    if existing:
        history = list(existing.get("history", []))
        history.append(
            {
                "timestamp": now,
                "last_reviewed": existing.get("last_reviewed"),
                "decision": existing.get("decision"),
                "rationale": existing.get("rationale"),
                "metrics_at_review": existing.get("metrics_at_review"),
            }
        )

    threshold: dict[str, Any] = {}
    if next_review_days is not None:
        threshold["after_days"] = next_review_days
    if next_review_loc_delta is not None:
        threshold["after_loc_delta"] = next_review_loc_delta

    entry = {
        "last_reviewed": today,
        "last_reviewed_by": reviewer,
        "metrics_at_review": metrics or {},
        "decision": decision,
        "rationale": rationale,
        "action_owner": owner,
        "next_review_threshold": threshold,
        "history": history,
    }
    entries[rel_path] = entry
    return entry


def _days_between(past_iso: str | None, today: str) -> int:
    """Days from past to today (ISO strings); huge number if past is unparseable."""
    if not past_iso:
        return 10**6
    try:
        past = date.fromisoformat(past_iso)
        now = date.fromisoformat(today)
    except (TypeError, ValueError):
        return 0
    return (now - past).days


def entries_needing_review(
    ledger: dict,
    *,
    since_days: int | None = None,
    above_loc: int | None = None,
    above_growth_pct: int | None = None,
    today: str | None = None,
    fs_metrics: dict[str, dict] | None = None,
) -> list[dict]:
    """Return entries that should be re-reviewed, with human-readable reasons.

    Triggers (any fires):
      - since_days:                 last_reviewed older than N days
      - above_loc:                  current LOC >= N
      - above_growth_pct:           current_loc grew >= N% since last review
      - per-entry after_days:       entry's own threshold crossed
      - per-entry after_loc_delta:  entry's own threshold crossed

    Skips entries whose decision is already in SKIP_REREVIEW_DECISIONS.
    """
    today = today or today_iso()
    fs_metrics = fs_metrics or {}
    out: list[dict] = []
    for rel_path, entry in ledger.get("entries", {}).items():
        if entry.get("decision") in SKIP_REREVIEW_DECISIONS:
            continue
        reasons: list[str] = []
        last = entry.get("last_reviewed")
        age = _days_between(last, today)

        if since_days is not None and age >= since_days:
            reasons.append(f"age={age}d>={since_days}d")

        per_entry_days = entry.get("next_review_threshold", {}).get("after_days")
        if per_entry_days is not None and age >= per_entry_days:
            reasons.append(f"per-entry age={age}d>={per_entry_days}d")

        prior_loc = entry.get("metrics_at_review", {}).get("loc", 0) or 0
        cur_metrics = fs_metrics.get(rel_path, {})
        cur_loc = cur_metrics.get("loc", prior_loc)

        if above_loc is not None and cur_loc >= above_loc:
            reasons.append(f"loc={cur_loc}>={above_loc}")

        loc_delta = cur_loc - prior_loc
        per_entry_delta = entry.get("next_review_threshold", {}).get("after_loc_delta")
        if per_entry_delta is not None and loc_delta >= per_entry_delta:
            reasons.append(f"per-entry delta={loc_delta}>={per_entry_delta}")

        if prior_loc and above_growth_pct is not None:
            pct = int((loc_delta / prior_loc) * 100)
            if pct >= above_growth_pct:
                reasons.append(f"growth={pct}%>={above_growth_pct}%")

        if reasons:
            out.append(
                {
                    "path": rel_path,
                    "last_reviewed": last,
                    "decision": entry.get("decision"),
                    "current_loc": cur_loc,
                    "prior_loc": prior_loc,
                    "loc_delta": loc_delta,
                    "reasons": reasons,
                }
            )
    out.sort(key=lambda e: (-e["current_loc"], e["path"]))
    return out


def drift_scan(
    ledger: dict,
    root: Path,
    scan_root: Path,
    *,
    above_loc: int = 1000,
    ignore: Iterable[str] = (),
) -> list[dict]:
    """Walk scan_root; flag .py files >= above_loc that are not in the ledger."""
    tracked = set((ledger.get("entries") or {}).keys())
    out: list[dict] = []
    for rel in iter_py_files(root, scan_root, ignore=ignore):
        if rel in tracked:
            continue
        loc = count_loc(root / rel)
        if loc < above_loc:
            continue
        out.append({"path": rel, "loc": loc})
    out.sort(key=lambda e: (-e["loc"], e["path"]))
    return out


def filter_entries(
    ledger: dict,
    *,
    decision: str | Iterable[str] | None = None,
    above_loc: int | None = None,
) -> list[tuple[str, dict]]:
    """Sorted list of (path, entry) pairs matching filters (largest LOC first).

    ``decision`` accepts either a single decision string (e.g. ``"monitor"``),
    a comma-separated string (e.g. ``"split_queued,monitor"``), or any iterable
    of decision strings. ``None`` means no filter.
    """
    entries = ledger.get("entries", {})
    decision_set: set[str] | None
    if decision is None:
        decision_set = None
    elif isinstance(decision, str):
        decision_set = {part.strip() for part in decision.split(",") if part.strip()}
    else:
        decision_set = {str(part).strip() for part in decision if str(part).strip()}
    out: list[tuple[str, dict]] = []
    for path, entry in entries.items():
        if decision_set is not None and entry.get("decision") not in decision_set:
            continue
        loc = entry.get("metrics_at_review", {}).get("loc", 0) or 0
        if above_loc is not None and loc < above_loc:
            continue
        out.append((path, entry))
    out.sort(key=lambda t: (-(t[1].get("metrics_at_review", {}).get("loc", 0) or 0), t[0]))
    return out


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _fmt_row(path: str, entry: dict) -> str:
    loc = entry.get("metrics_at_review", {}).get("loc", "?")
    last = entry.get("last_reviewed", "?")
    decision = entry.get("decision", "?")
    owner = entry.get("action_owner") or "-"
    return f"{str(loc):>6}  {last:<10}  {decision:<22}  {owner:<20}  {path}"


def cmd_list(args: argparse.Namespace, ledger: dict) -> int:
    results = filter_entries(ledger, decision=args.decision, above_loc=args.above_loc)
    if args.json:
        payload = [{"path": p, **e} for p, e in results]
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if results else 1
    if not results:
        print("no entries match", file=sys.stderr)
        return 1
    print(f"{'LOC':>6}  {'REVIEWED':<10}  {'DECISION':<22}  {'OWNER':<20}  PATH")
    for path, entry in results:
        print(_fmt_row(path, entry))
    return 0


def cmd_show(args: argparse.Namespace, ledger: dict) -> int:
    entry = ledger.get("entries", {}).get(args.path)
    if not entry:
        print(f"no entry for {args.path}", file=sys.stderr)
        return 1
    if args.json:
        json.dump({"path": args.path, **entry}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(f"path: {args.path}")
    print(f"last_reviewed: {entry.get('last_reviewed')}")
    print(f"last_reviewed_by: {entry.get('last_reviewed_by')}")
    print(f"decision: {entry.get('decision')}")
    print(f"rationale: {entry.get('rationale')}")
    print(f"action_owner: {entry.get('action_owner') or '-'}")
    metrics = entry.get("metrics_at_review") or {}
    print(
        f"metrics_at_review: loc={metrics.get('loc','?')} "
        f"last_commit={metrics.get('last_commit','?')}"
    )
    thresh = entry.get("next_review_threshold") or {}
    if thresh:
        parts = []
        if "after_days" in thresh:
            parts.append(f"after_days={thresh['after_days']}")
        if "after_loc_delta" in thresh:
            parts.append(f"after_loc_delta={thresh['after_loc_delta']}")
        print(f"next_review_threshold: {' '.join(parts)}")
    hist = entry.get("history") or []
    print(f"history: {len(hist)} prior state(s)")
    for i, h in enumerate(hist[-5:], start=max(1, len(hist) - 4)):
        rationale = (h.get("rationale") or "")[:60]
        print(f"  [{i}] {h.get('timestamp','?')}  {h.get('decision','?')}  {rationale}")
    return 0


def cmd_update(
    args: argparse.Namespace, ledger: dict, ledger_path: Path, repo_root: Path
) -> int:
    if args.metrics_loc is not None:
        metrics = {"loc": args.metrics_loc}
        if args.metrics_last_commit:
            metrics["last_commit"] = args.metrics_last_commit
    else:
        metrics = compute_file_metrics(args.path, repo_root)

    try:
        entry = upsert_entry(
            ledger,
            args.path,
            decision=args.decision,
            rationale=args.rationale,
            metrics=metrics,
            owner=args.owner,
            next_review_days=args.next_review_days,
            next_review_loc_delta=args.next_review_loc_delta,
            reviewer=args.reviewer,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print("dry-run: would write")
        json.dump({"path": args.path, **entry}, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    save_ledger(ledger, ledger_path)
    print(f"updated {args.path} -> {entry['decision']} (loc={metrics.get('loc','?')})")
    return 0


def cmd_needs_review(
    args: argparse.Namespace, ledger: dict, repo_root: Path
) -> int:
    fs_metrics: dict[str, dict] = {}
    for rel_path in ledger.get("entries", {}):
        fs_metrics[rel_path] = compute_file_metrics(rel_path, repo_root)

    results = entries_needing_review(
        ledger,
        since_days=args.since_days,
        above_loc=args.above_loc,
        above_growth_pct=args.above_growth_pct,
        fs_metrics=fs_metrics,
    )
    if args.json:
        json.dump(results, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if results else 1
    if not results:
        print("no entries need review")
        return 1
    print(f"{'LOC':>6}  {'DELTA':>6}  REASONS  PATH")
    for r in results:
        print(
            f"{r['current_loc']:>6}  {r['loc_delta']:>+6}  "
            f"{', '.join(r['reasons'])}  {r['path']}"
        )
    return 0


def cmd_drift_scan(
    args: argparse.Namespace, ledger: dict, repo_root: Path
) -> int:
    scan_root = (repo_root / args.path).resolve() if args.path else repo_root
    if not scan_root.is_dir():
        print(f"error: {scan_root} is not a directory", file=sys.stderr)
        return 2
    results = drift_scan(
        ledger,
        repo_root,
        scan_root,
        above_loc=args.above_loc,
        ignore=args.ignore or (),
    )
    if args.json:
        json.dump(results, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0 if results else 1
    if not results:
        print(f"no untracked files above {args.above_loc} LOC under {scan_root}")
        return 1
    print(f"{'LOC':>6}  PATH")
    for r in results:
        print(f"{r['loc']:>6}  {r['path']}")
    return 0


def cmd_history(args: argparse.Namespace, ledger: dict) -> int:
    entry = ledger.get("entries", {}).get(args.path)
    if not entry:
        print(f"no entry for {args.path}", file=sys.stderr)
        return 1
    hist = list(entry.get("history") or [])
    current = {
        "last_reviewed": entry.get("last_reviewed"),
        "decision": entry.get("decision"),
        "rationale": entry.get("rationale"),
        "metrics_at_review": entry.get("metrics_at_review"),
    }
    if args.json:
        payload = {"path": args.path, "history": hist, "current": current}
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(f"history for {args.path}:")
    for i, h in enumerate(hist, start=1):
        print(f"  [{i}] {h.get('timestamp','?')}  {h.get('decision','?')}")
        rationale = h.get("rationale") or ""
        if rationale:
            print(f"       {rationale}")
    print(f"  [current] {current['last_reviewed']}  {current['decision']}")
    rationale = current.get("rationale") or ""
    if rationale:
        print(f"            {rationale}")
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledger.py",
        description="File review ledger CLI for architecture drift tracking.",
    )
    p.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Override ledger JSON path (default: reports/architecture/ledger.json)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override repo root (default: script's parent.parent)",
    )

    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List ledger entries")
    p_list.add_argument(
        "--decision",
        default=None,
        help=(
            "Filter by decision. Accepts a single value (e.g. 'monitor') or "
            "a comma-separated list (e.g. 'split_queued,monitor')."
        ),
    )
    p_list.add_argument(
        "--above-loc", type=int, default=None,
        help="Only entries with metrics_at_review.loc >= N",
    )
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one entry with full history")
    p_show.add_argument("path", help="Repo-relative file path")
    p_show.add_argument("--json", action="store_true")

    p_up = sub.add_parser("update", help="Upsert a ledger entry")
    p_up.add_argument("path", help="Repo-relative file path")
    p_up.add_argument("--decision", required=True, choices=sorted(VALID_DECISIONS))
    p_up.add_argument("--rationale", required=True)
    p_up.add_argument("--owner", default=None, help="Action owner")
    p_up.add_argument(
        "--metrics-loc", type=int, default=None,
        help="Override computed LOC (snapshots/tests)",
    )
    p_up.add_argument("--metrics-last-commit", default=None)
    p_up.add_argument("--next-review-days", type=int, default=None)
    p_up.add_argument("--next-review-loc-delta", type=int, default=None)
    p_up.add_argument("--reviewer", default="claude-code")
    p_up.add_argument("--dry-run", action="store_true")

    p_nr = sub.add_parser("needs-review", help="List entries past review threshold")
    p_nr.add_argument("--since-days", type=int, default=None)
    p_nr.add_argument("--above-loc", type=int, default=None)
    p_nr.add_argument("--above-growth-pct", type=int, default=None)
    p_nr.add_argument("--json", action="store_true")

    p_ds = sub.add_parser("drift-scan", help="Find untracked big files")
    p_ds.add_argument("path", nargs="?", default="core", help="Directory to scan")
    p_ds.add_argument("--above-loc", type=int, default=1000)
    p_ds.add_argument(
        "--ignore", action="append", default=None,
        help="Directory name to skip (may repeat)",
    )
    p_ds.add_argument("--json", action="store_true")

    p_hi = sub.add_parser("history", help="Show entry audit trail")
    p_hi.add_argument("path", help="Repo-relative file path")
    p_hi.add_argument("--json", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ledger_path = args.ledger_path or DEFAULT_LEDGER_PATH
    repo_root = (args.repo_root or REPO_ROOT).resolve()
    try:
        ledger = load_ledger(ledger_path)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "list":
        return cmd_list(args, ledger)
    if args.command == "show":
        return cmd_show(args, ledger)
    if args.command == "update":
        return cmd_update(args, ledger, ledger_path, repo_root)
    if args.command == "needs-review":
        return cmd_needs_review(args, ledger, repo_root)
    if args.command == "drift-scan":
        return cmd_drift_scan(args, ledger, repo_root)
    if args.command == "history":
        return cmd_history(args, ledger)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
