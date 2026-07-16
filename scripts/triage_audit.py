"""Deterministic accountability checker for quality scan triage.

CLI:
    triage_audit.py --effectiveness PATH --findings PATH --dismissals PATH
                    [--grace-days 7] [--now ISO-8601] [--json OUT] [--md OUT]

Exit codes:
    0  — all scans with findings_total > 0 are accounted for (or within grace)
    1  — one or more UNACCOUNTED scans exist
    2  — invocation error (bad args / files not readable)

Auditable unit: the SCAN, not individual findings.
Latest-scan-per-(skill, target) only — superseded older runs collapse to a
one-line count rather than individual failures.

Acknowledgment criteria (any one satisfies):
    (a) findings.jsonl has a record whose source_scan == scan_id, or whose
        source_skill == skill AND created_at is within the grace window.
    (b) dismissals.jsonl has a record referencing the scan_id or the skill
        within the grace window.
    (c) the scan is newer than the grace period (not yet due).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ---- helpers ----------------------------------------------------------------

def _parse_ts(raw: Any) -> datetime | None:
    """Return a UTC-aware datetime from an ISO-8601 string, or None."""
    if not isinstance(raw, str):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    # fromisoformat fallback (Python 3.7+, handles +HH:MM offsets)
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _parse_cli_timestamp(raw: str) -> datetime:
    """Parse an explicit audit clock for reproducible CLI runs."""
    parsed = _parse_ts(raw)
    if parsed is None:
        raise argparse.ArgumentTypeError(
            "must be an ISO-8601 timestamp, for example 2026-06-11T12:00:00Z"
        )
    return parsed.astimezone(timezone.utc)


def _load_jsonl(path: Path) -> tuple[list[dict], int]:
    """Load a JSONL file, returning (records, malformed_count).

    Skips blank lines and lines that are not valid JSON objects.
    """
    records: list[dict] = []
    bad = 0
    if not path.exists():
        return records, bad
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(obj, dict):
            bad += 1
            continue
        records.append(obj)
    return records, bad


def _get_ts(rec: dict) -> datetime | None:
    """Extract a timestamp from a record, trying multiple field names."""
    for key in ("ts", "created_at", "event_at"):
        val = rec.get(key)
        if val:
            dt = _parse_ts(val)
            if dt:
                return dt
    return None


# ---- core logic -------------------------------------------------------------

def _select_latest_scans(
    effectiveness: list[dict],
) -> tuple[list[dict], int]:
    """Return the latest scan per (skill, target), and the superseded count.

    Records without a parseable timestamp are kept but treated as ts=epoch.
    """
    # Map (skill, target) -> best record so far
    best: dict[tuple[str, str], dict] = {}
    for rec in effectiveness:
        skill = rec.get("skill", "")
        target = rec.get("target", "")
        key = (skill, target)
        ts = _get_ts(rec) or datetime(1970, 1, 1, tzinfo=timezone.utc)
        if key not in best:
            best[key] = rec
        else:
            existing_ts = _get_ts(best[key]) or datetime(1970, 1, 1, tzinfo=timezone.utc)
            if ts > existing_ts:
                best[key] = rec
    latest = list(best.values())
    superseded = len(effectiveness) - len(latest)
    return latest, superseded


def _build_acknowledgment_index(
    findings: list[dict],
    dismissals: list[dict],
    grace_window: timedelta,
    now: datetime,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Build sets of acknowledged scan_ids and skills.

    Returns:
        (ack_scan_ids, ack_skills_findings, ack_scan_ids_dismissals, ack_skills_dismissals)
    """
    ack_scan_ids_findings: set[str] = set()
    ack_skills_findings: set[str] = set()
    ack_scan_ids_dismissals: set[str] = set()
    ack_skills_dismissals: set[str] = set()

    for rec in findings:
        # findings.jsonl criteria (a): source_scan match
        src_scan = rec.get("source_scan")
        if src_scan:
            ack_scan_ids_findings.add(str(src_scan))
        # findings.jsonl criteria (a): source_skill match within window
        src_skill = rec.get("source_skill")
        ts = _get_ts(rec)
        if src_skill and ts and (now - ts) <= grace_window:
            ack_skills_findings.add(str(src_skill))

    for rec in dismissals:
        # Leniently try multiple field names for scan reference
        for scan_field in ("source_scan", "scan_id", "scan"):
            val = rec.get(scan_field)
            if val:
                ack_scan_ids_dismissals.add(str(val))
        # Leniently try skill reference
        for skill_field in ("source_skill", "skill"):
            val = rec.get(skill_field)
            if val:
                ts = _get_ts(rec)
                if ts and (now - ts) <= grace_window:
                    ack_skills_dismissals.add(str(val))

    return (
        ack_scan_ids_findings,
        ack_skills_findings,
        ack_scan_ids_dismissals,
        ack_skills_dismissals,
    )


def _is_acknowledged(
    rec: dict,
    ack_scan_ids_findings: set[str],
    ack_skills_findings: set[str],
    ack_scan_ids_dismissals: set[str],
    ack_skills_dismissals: set[str],
) -> bool:
    scan_id = str(rec.get("scan_id", ""))
    skill = str(rec.get("skill", ""))
    if scan_id and scan_id in ack_scan_ids_findings:
        return True
    if skill and skill in ack_skills_findings:
        return True
    if scan_id and scan_id in ack_scan_ids_dismissals:
        return True
    if skill and skill in ack_skills_dismissals:
        return True
    return False


def _open_finding_age_days(
    findings: list[dict],
    now: datetime,
) -> list[dict]:
    """Return open findings with age_days, sorted oldest first.

    An open finding is a record_kind=finding whose id has never received a
    resolving event (status in fixed/false-positive/wont-fix) in any later
    event record.
    """
    # Collect resolution events: id -> latest resolved status
    resolved_ids: dict[str, str] = {}
    for rec in findings:
        if rec.get("record_kind") == "event":
            ev_status = rec.get("status", "")
            if ev_status in ("fixed", "false-positive", "wont-fix"):
                rec_id = rec.get("id", "")
                if rec_id:
                    resolved_ids[rec_id] = ev_status

    open_findings: list[dict] = []
    for rec in findings:
        if rec.get("record_kind") != "finding":
            continue
        status = rec.get("status", "open")
        rec_id = rec.get("id", "")
        if rec_id in resolved_ids:
            continue
        if status not in ("open", "uncertain"):
            continue
        ts = _get_ts(rec)
        age_days = int((now - ts).total_seconds() / 86400) if ts else None
        open_findings.append({
            "id": rec_id,
            "source_skill": rec.get("source_skill", ""),
            "source_scan": rec.get("source_scan", ""),
            "pattern": rec.get("pattern", ""),
            "status": status,
            "created_at": rec.get("created_at", rec.get("ts", "")),
            "age_days": age_days,
        })

    open_findings.sort(key=lambda r: (r["age_days"] is None, -(r["age_days"] or 0)))
    return open_findings


# ---- report assembly --------------------------------------------------------

def run_audit(
    effectiveness_path: Path,
    findings_path: Path,
    dismissals_path: Path,
    grace_days: int = 7,
    now: datetime | None = None,
) -> dict:
    """Run the full audit and return a structured result dict."""
    if now is None:
        now = datetime.now(tz=timezone.utc)
    grace = timedelta(days=grace_days)

    eff_recs, eff_bad = _load_jsonl(effectiveness_path)
    find_recs, find_bad = _load_jsonl(findings_path)
    dism_recs, dism_bad = _load_jsonl(dismissals_path)
    total_warnings = eff_bad + find_bad + dism_bad

    # Only audit rows that have findings
    candidate_recs = [r for r in eff_recs if (r.get("findings_total") or 0) > 0]
    latest_scans, superseded_count = _select_latest_scans(candidate_recs)

    ack_sf, ack_sk_f, ack_sd, ack_sk_d = _build_acknowledgment_index(
        find_recs, dism_recs, grace, now
    )

    unaccounted: list[dict] = []
    acknowledged: list[dict] = []
    within_grace: list[dict] = []

    for rec in latest_scans:
        ts = _get_ts(rec)
        age_days = int((now - ts).total_seconds() / 86400) if ts else None

        # Criterion (c): within grace period
        if ts and (now - ts) <= grace:
            within_grace.append(rec)
            continue

        if _is_acknowledged(rec, ack_sf, ack_sk_f, ack_sd, ack_sk_d):
            acknowledged.append(rec)
        else:
            unaccounted.append({
                "skill": rec.get("skill", ""),
                "target": rec.get("target", ""),
                "scan_id": rec.get("scan_id", ""),
                "findings_total": rec.get("findings_total", 0),
                "age_days": age_days,
                "ts": rec.get("ts", rec.get("created_at", "")),
            })

    open_findings = _open_finding_age_days(find_recs, now)

    return {
        "now": now.isoformat(),
        "grace_days": grace_days,
        "warnings": total_warnings,
        "superseded_count": superseded_count,
        "unaccounted": sorted(unaccounted, key=lambda r: -(r["age_days"] or 0)),
        "acknowledged_count": len(acknowledged),
        "within_grace_count": len(within_grace),
        "open_findings": open_findings,
    }


def _render_md(result: dict) -> str:
    lines: list[str] = []
    lines.append("# Triage Audit Report")
    lines.append(f"\nGenerated: {result['now']}  ")
    lines.append(f"Grace period: {result['grace_days']} days  ")
    if result["warnings"]:
        lines.append(f"Parse warnings (malformed lines skipped): {result['warnings']}  ")
    lines.append(
        f"Superseded scans collapsed (same skill+target, older run): "
        f"{result['superseded_count']}  "
    )
    lines.append("")

    # --- UNACCOUNTED ---------------------------------------------------------
    unaccounted = result["unaccounted"]
    if unaccounted:
        lines.append(f"## UNACCOUNTED ({len(unaccounted)} scan(s))")
        lines.append("")
        lines.append("| skill | target | scan_id | findings_total | age_days |")
        lines.append("|---|---|---|---|---|")
        for row in unaccounted:
            lines.append(
                f"| {row['skill']} | {row['target']} | {row['scan_id']} "
                f"| {row['findings_total']} | {row['age_days']} |"
            )
        lines.append("")
    else:
        lines.append("## UNACCOUNTED — none")
        lines.append("")

    # --- ACKNOWLEDGED --------------------------------------------------------
    lines.append(
        f"## ACKNOWLEDGED — {result['acknowledged_count']} scan(s)  "
        f"(plus {result['within_grace_count']} within grace, not yet due)"
    )
    lines.append("")

    # --- OPEN FINDINGS AGING -------------------------------------------------
    open_findings = result["open_findings"]
    if open_findings:
        lines.append(f"## OPEN-FINDINGS AGING ({len(open_findings)} open finding(s))")
        lines.append("")
        lines.append("| id | source_skill | pattern | age_days |")
        lines.append("|---|---|---|---|")
        for row in open_findings:
            lines.append(
                f"| {row['id']} | {row['source_skill']} | {row['pattern']} "
                f"| {row['age_days']} |"
            )
        lines.append("")
    else:
        lines.append("## OPEN-FINDINGS AGING — none")
        lines.append("")

    return "\n".join(lines)


def _render_text(result: dict) -> str:
    lines: list[str] = []
    unaccounted = result["unaccounted"]

    if result["warnings"]:
        lines.append(f"WARNING: {result['warnings']} malformed line(s) skipped")

    lines.append(
        f"Superseded scans collapsed: {result['superseded_count']}"
    )
    lines.append("")

    if unaccounted:
        lines.append(f"UNACCOUNTED ({len(unaccounted)}):")
        for row in unaccounted:
            lines.append(
                f"  [{row['age_days']}d] {row['skill']}  target={row['target']!r}"
                f"  scan_id={row['scan_id']!r}  findings={row['findings_total']}"
            )
    else:
        lines.append("UNACCOUNTED: none")

    lines.append("")
    lines.append(
        f"ACKNOWLEDGED: {result['acknowledged_count']} scan(s)"
        f"  |  WITHIN GRACE (not due): {result['within_grace_count']}"
    )

    open_findings = result["open_findings"]
    lines.append("")
    if open_findings:
        lines.append(f"OPEN-FINDINGS AGING ({len(open_findings)}, oldest first):")
        for row in open_findings:
            lines.append(
                f"  [{row['age_days']}d] {row['id']}  skill={row['source_skill']!r}"
                f"  pattern={row['pattern']!r}  status={row['status']}"
            )
    else:
        lines.append("OPEN-FINDINGS AGING: none")

    return "\n".join(lines)


# ---- CLI --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit scan accountability: every scan with findings must be triaged."
    )
    parser.add_argument("--effectiveness", required=True,
                        help="Path to effectiveness.jsonl")
    parser.add_argument("--findings", required=True,
                        help="Path to findings.jsonl")
    parser.add_argument("--dismissals", required=True,
                        help="Path to dismissals.jsonl")
    parser.add_argument("--grace-days", type=int, default=7,
                        help="Days before a scan becomes due (default: 7)")
    parser.add_argument(
        "--now",
        type=_parse_cli_timestamp,
        default=None,
        help="UTC audit clock for reproducible runs (default: current time)",
    )
    parser.add_argument("--json", dest="json_out", metavar="OUT",
                        help="Write JSON result to this path")
    parser.add_argument("--md", dest="md_out", metavar="OUT",
                        help="Write Markdown report to this path")

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code != 0 else 0

    try:
        result = run_audit(
            effectiveness_path=Path(args.effectiveness),
            findings_path=Path(args.findings),
            dismissals_path=Path(args.dismissals),
            grace_days=args.grace_days,
            now=args.now,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Always print text to stdout
    print(_render_text(result))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )

    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(_render_md(result), encoding="utf-8")

    return 1 if result["unaccounted"] else 0


if __name__ == "__main__":
    sys.exit(main())
