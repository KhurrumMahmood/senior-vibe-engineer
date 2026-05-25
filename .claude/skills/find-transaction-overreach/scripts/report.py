#!/usr/bin/env python3
"""Render report.md + findings.json from transaction-overreach scout output.

Reads a directory of scout JSON files (one per candidate) produced by
the Stage-3 verifiers, plus the raw ``candidates.jsonl`` from collapse,
and bundles them into the final report the user reads + a
machine-readable ``findings.json`` that ``/fix-workflow`` can parse.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BUCKET_ORDER: tuple[str, ...] = (
    "narrow_transaction",
    "split_transaction",
    "defer_via_on_commit",
    "legitimate_long_transaction",
    "false_positive",
)
BUCKET_LABEL: dict[str, str] = {
    "narrow_transaction": "Narrow transaction (move slow op outside)",
    "split_transaction": "Split transaction (separate the DB writes)",
    "defer_via_on_commit": "Defer via transaction.on_commit",
    "legitimate_long_transaction": "Legitimate long transaction (allow-list)",
    "false_positive": "False positive (helper isn't actually slow / safe wrapper)",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "narrow_transaction": "`/fix-workflow cluster:{symbol}` — move the slow op outside the `transaction.atomic()` block; keep only the DB writes inside.",
    "split_transaction": "`/fix-workflow cluster:{symbol}` — split into two atomic blocks separated by the slow op so neither holds the connection during external work.",
    "defer_via_on_commit": "`/fix-workflow cluster:{symbol}` — wrap the dispatch / side effect in `transaction.on_commit(lambda: …)` so it runs after commit.",
    "legitimate_long_transaction": "Add `# atomic-overreach: <reason>` allow-list marker on the `with` / `def` line; no other change.",
    "false_positive": "Drop from candidates (the flagged helper does not actually do external I/O).",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _load_scouts(scout_dir: Path) -> list[dict[str, Any]]:
    if not scout_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(scout_dir.glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            print(f"[report] WARN: bad JSON in {path}", file=sys.stderr)
    return out


def _render_hit_table(hits: list[dict[str, Any]], limit: int = 8) -> list[str]:
    if not hits:
        return []
    lines = ["**Slow-op calls inside the block:**", ""]
    lines.append("| Category | Method | Evidence |")
    lines.append("|---|---|---|")
    for h in hits[:limit]:
        category = h.get("category", "?")
        method = h.get("call_method", "?")
        evidence = (h.get("evidence") or "").replace("|", "\\|").strip()
        lines.append(f"| `{category}` | `{method}` | `{evidence}` |")
    if len(hits) > limit:
        lines.append(f"| … | … | ({len(hits) - limit} more) |")
    lines.append("")
    return lines


def _render_candidate(
    scout: dict[str, Any],
    candidate: dict[str, Any] | None,
    idx: int,
) -> str:
    file = scout.get("file") or (candidate.get("file") if candidate else "?")
    symbol = scout.get("enclosing_symbol") or (
        candidate.get("enclosing_symbol") if candidate else "?"
    )
    bucket = scout.get("bucket", "narrow_transaction")
    confidence = scout.get("confidence") or (
        candidate.get("confidence") if candidate else "?"
    )
    categories = scout.get("categories") or (
        candidate.get("categories", []) if candidate else []
    )
    hits = candidate.get("hits", []) if candidate else []
    block_kind = candidate.get("block_kind", "with") if candidate else "with"

    out: list[str] = []
    out.append(f"### {idx}. `{symbol}` in `{file}`")
    out.append("")
    out.append(f"- **Candidate ID:** `{scout.get('candidate_id', '?')}`")
    out.append(
        f"- **Block:** `{block_kind}` "
        f"(L{candidate.get('block_lineno') if candidate else '?'}–"
        f"L{candidate.get('block_endline') if candidate else '?'})"
    )
    out.append(f"- **Confidence:** {confidence}")
    out.append(
        f"- **Categories:** "
        f"{', '.join(f'`{c}`' for c in categories) if categories else '—'}"
    )
    out.append(f"- **Hit count:** {scout.get('hit_count', len(hits))}")
    out.append("")
    if scout.get("notes"):
        out.append(f"> {scout['notes']}")
        out.append("")
    out.extend(_render_hit_table(hits))
    rec_template = BUCKET_RECOMMENDATION.get(bucket, "(no default action)")
    out.append(
        f"**Recommended action:** {rec_template.format(symbol=symbol)} "
        f"— scout bucket: `{bucket}`."
    )
    out.append("")
    return "\n".join(out)


def render_report(
    scouts: list[dict[str, Any]],
    raw_candidates: list[dict[str, Any]],
    scan_id: str | None,
    target: str | None,
) -> tuple[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {
        c["candidate_id"]: c for c in raw_candidates if "candidate_id" in c
    }

    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in scouts:
        by_bucket[s.get("bucket", "narrow_transaction")].append(s)

    lines: list[str] = []
    title = (
        f"# Transaction-overreach audit — {scan_id}"
        if scan_id else "# Transaction-overreach audit"
    )
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
    lines.append(f"**Raw candidates:** {len(raw_candidates)}")
    lines.append(f"**Scout verifications:** {len(scouts)}")
    lines.append("")

    if not raw_candidates:
        lines.append("## Summary")
        lines.append("")
        lines.append(
            "**Zero candidates found.** No `transaction.atomic()` block "
            "or `@transaction.atomic` function in the target contains "
            "a known slow-op call (HTTP, AI, cloud upload, sleep, "
            "subprocess, or Celery dispatch)."
        )
        lines.append("")
        lines.append(
            "This is the expected outcome on a codebase that consistently "
            "moves external I/O outside transactions and uses "
            "`transaction.on_commit` for deferred side effects. "
            "Re-run after major changes to extraction / discovery / export "
            "code paths or after adding new sites that touch external services."
        )
        lines.append("")
        findings_json = {
            "scan_id": scan_id,
            "target": target,
            "summary": {
                "raw_candidates": 0,
                "scout_verifications": 0,
                "category_counts": {},
                "bucket_counts": {},
                "findings_total": 0,
                "buckets": {},
            },
            "findings": [],
        }
        return "\n".join(lines), findings_json

    category_counts: Counter[str] = Counter()
    for c in raw_candidates:
        for cat in c.get("categories", []):
            category_counts[cat] += 1

    confidence_counts: Counter[str] = Counter()
    for c in raw_candidates:
        confidence_counts[c.get("confidence", "low")] += 1

    lines.append("## Summary")
    lines.append("")
    lines.append("| Slow-op category | Candidate count |")
    lines.append("|---|---|")
    for cat in sorted(category_counts):
        lines.append(f"| `{cat}` | {category_counts[cat]} |")
    lines.append("")
    lines.append("| Confidence | Candidate count |")
    lines.append("|---|---|")
    for conf in ("high", "medium", "low"):
        if confidence_counts.get(conf):
            lines.append(f"| `{conf}` | {confidence_counts[conf]} |")
    lines.append("")

    if scouts:
        for bucket in BUCKET_ORDER:
            n = len(by_bucket.get(bucket, []))
            if n == 0:
                continue
            lines.append(f"- **{BUCKET_LABEL[bucket]}:** {n}")
        lines.append("")

    if scouts:
        for bucket in BUCKET_ORDER:
            items = by_bucket.get(bucket, [])
            if not items:
                continue
            lines.append(f"## {BUCKET_LABEL[bucket]} ({len(items)})")
            lines.append("")
            for i, scout in enumerate(items, start=1):
                raw = by_id.get(scout.get("candidate_id", ""))
                lines.append(_render_candidate(scout, raw, i))
    else:
        lines.append("## Raw candidates (no scout verification yet)")
        lines.append("")
        for i, candidate in enumerate(raw_candidates[:20], start=1):
            file = candidate.get("file", "?")
            symbol = candidate.get("enclosing_symbol", "?")
            block_kind = candidate.get("block_kind", "with")
            block_lineno = candidate.get("block_lineno", "?")
            categories = candidate.get("categories", [])
            cats_str = ", ".join(f"`{c}`" for c in categories)
            lines.append(
                f"{i}. `{symbol}` in `{file}` "
                f"(`{block_kind}` block at L{block_lineno}) — {cats_str}"
            )
        if len(raw_candidates) > 20:
            lines.append(f"… and {len(raw_candidates) - 20} more.")
        lines.append("")

    lines.append("## Next action")
    lines.append("")
    actionable = [
        s for s in scouts
        if s.get("bucket") in (
            "narrow_transaction", "split_transaction", "defer_via_on_commit",
        )
    ]
    actionable.sort(
        key=lambda s: (
            {"narrow_transaction": 0, "defer_via_on_commit": 1, "split_transaction": 2}.get(
                s.get("bucket", "narrow_transaction"), 99,
            ),
            -(s.get("hit_count") or 0),
        ),
    )
    if not actionable and scouts:
        lines.append(
            "No actionable findings — all hits bucketed as legitimate or false positive."
        )
    elif not actionable:
        lines.append(
            "Scouts have not run yet. Re-invoke the skill with verification enabled, "
            "or pick from the raw candidates above."
        )
    else:
        for i, s in enumerate(actionable[:3], start=1):
            symbol = s.get("enclosing_symbol", "?")
            bucket = s.get("bucket", "narrow_transaction")
            rec = BUCKET_RECOMMENDATION.get(bucket, "").format(symbol=symbol)
            lines.append(f"{i}. {rec} — `{s.get('file', '?')}`")
    lines.append("")

    bucket_counts: dict[str, int] = defaultdict(int)
    for s in scouts:
        bucket_counts[s.get("bucket", "narrow_transaction")] += 1

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(raw_candidates),
            "scout_verifications": len(scouts),
            "category_counts": dict(category_counts),
            "confidence_counts": dict(confidence_counts),
            "bucket_counts": dict(bucket_counts),
            "findings_total": len(scouts),
            "buckets": dict(bucket_counts),
        },
        "findings": scouts,
    }
    return "\n".join(lines), findings_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scout-dir", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--scan-id", default=None)
    parser.add_argument("--target", default=None)
    args = parser.parse_args(argv)

    scouts = _load_scouts(args.scout_dir)
    raw_candidates = _read_jsonl(args.candidates)
    report_md, findings_json = render_report(
        scouts, raw_candidates, args.scan_id, args.target,
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(report_md, encoding="utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(findings_json, indent=2),
        encoding="utf-8",
    )
    print(
        f"[report_transaction_overreach] scouts={len(scouts)} "
        f"raw_candidates={len(raw_candidates)}",
        file=sys.stderr,
    )
    print(f"[report_transaction_overreach] wrote {args.output_md}", file=sys.stderr)
    print(f"[report_transaction_overreach] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
