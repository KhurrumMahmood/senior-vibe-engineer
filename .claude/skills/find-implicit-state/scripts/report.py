#!/usr/bin/env python3
"""Render report.md + findings.json from implicit-state scout output.

Reads a directory of scout JSON files (one per candidate) produced by
the Stage-3 verifiers, plus the raw ``candidates.jsonl`` from collapse,
and bundles them into the final report the user reads + a
machine-readable ``findings.json`` that ``/extract-enum`` and
``/introduce-fk`` can parse.

Output sections:

- Sub-pattern A: stringly-typed state (``stringly_compare``,
  ``stringly_field``, ``possible_state_literal``).
- Sub-pattern B: tuple-inferred identity (``tuple_identity``).
- Each section grouped by bucket (``extract_enum_candidate``,
  ``introduce_fk_candidate``, ``enum_already_used``, ``legacy_allow_list``).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BUCKET_ORDER: tuple[str, ...] = (
    "extract_enum_candidate",
    "introduce_fk_candidate",
    "enum_already_used",
    "legacy_allow_list",
)
BUCKET_LABEL: dict[str, str] = {
    "extract_enum_candidate": "Extract-enum candidates",
    "introduce_fk_candidate": "Introduce-FK candidates",
    "enum_already_used": "Enum already used (false positive)",
    "legacy_allow_list": "Legacy allow-list (no action)",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "extract_enum_candidate": "`/extract-enum {symbol}` (propose TextChoices + migration plan)",
    "introduce_fk_candidate": "`/introduce-fk {symbol}` (propose FK + backfill + set-NOT-NULL)",
    "enum_already_used": "Drop from candidates",
    "legacy_allow_list": "Leave as-is (already noqa'd)",
}

SUBPATTERN_A_PATTERNS = {
    "stringly_compare", "stringly_field", "possible_state_literal",
}
SUBPATTERN_B_PATTERNS = {"tuple_identity"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
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
        except json.JSONDecodeError:
            print(
                f"[report] WARN: bad JSON in {path}",
                file=sys.stderr,
            )
    return out


def _render_hit_table(hits: list[dict[str, Any]], limit: int = 8) -> list[str]:
    lines: list[str] = []
    if not hits:
        return lines
    lines.append("**Sample hits:**")
    lines.append("")
    lines.append("| Symbol | Field | Evidence |")
    lines.append("|---|---|---|")
    for h in hits[:limit]:
        symbol = h.get("symbol", "?")
        field = h.get("field", "—")
        if field == "—":
            kwargs = h.get("filter_kwargs")
            if isinstance(kwargs, list):
                field = ",".join(kwargs)
        evidence = (h.get("evidence") or "").replace("|", "\\|").strip()
        lines.append(f"| `{symbol}` | `{field}` | `{evidence}` |")
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
    pattern = scout.get("pattern") or (
        candidate.get("pattern") if candidate else "?"
    )
    bucket = scout.get("bucket", "extract_enum_candidate")
    confidence = scout.get("confidence") or (
        candidate.get("confidence") if candidate else "?"
    )
    fields = scout.get("fields_touched") or (
        candidate.get("fields_touched", []) if candidate else []
    )
    symbols = scout.get("symbols") or (
        candidate.get("symbols", []) if candidate else []
    )
    hits = candidate.get("hits", []) if candidate else []

    out: list[str] = []
    out.append(f"### {idx}. `{file}` — {pattern}")
    out.append("")
    out.append(f"- **Candidate ID:** `{scout.get('candidate_id', '?')}`")
    out.append(f"- **Confidence:** {confidence}")
    if fields:
        out.append(f"- **Fields:** {', '.join(f'`{f}`' for f in fields)}")
    if symbols:
        out.append(
            f"- **Symbols:** {', '.join(f'`{s}`' for s in symbols[:6])}"
            + ("" if len(symbols) <= 6 else f" (+{len(symbols) - 6} more)")
        )
    out.append(f"- **Hit count:** {scout.get('hit_count', len(hits))}")
    out.append("")
    notes = scout.get("notes")
    if notes:
        out.append(f"> {notes}")
        out.append("")
    out.extend(_render_hit_table(hits))
    rec_key = scout.get("recommendation_hint_symbol", "")
    if not rec_key and symbols:
        rec_key = symbols[0]
    if not rec_key:
        rec_key = Path(file).stem
    rec_template = BUCKET_RECOMMENDATION.get(bucket, "(no default action)")
    out.append(
        f"**Recommended action:** {rec_template.format(symbol=rec_key)} "
        f"— scout bucket: `{bucket}`."
    )
    out.append("")
    return "\n".join(out)


def _classify_subpattern(pattern: str) -> str:
    if pattern in SUBPATTERN_A_PATTERNS:
        return "A"
    if pattern in SUBPATTERN_B_PATTERNS:
        return "B"
    return "?"


def render_report(
    scouts: list[dict[str, Any]],
    raw_candidates: list[dict[str, Any]],
    scan_id: str | None,
    target: str | None,
) -> tuple[str, dict[str, Any]]:
    # Index raw candidates by id for hit-list lookup.
    by_id: dict[str, dict[str, Any]] = {
        c["candidate_id"]: c for c in raw_candidates if "candidate_id" in c
    }

    by_subpattern_bucket: dict[str, dict[str, list[dict[str, Any]]]] = {
        "A": defaultdict(list), "B": defaultdict(list),
    }
    for s in scouts:
        pattern = s.get("pattern", "")
        sub = _classify_subpattern(pattern)
        if sub not in by_subpattern_bucket:
            continue
        bucket = s.get("bucket", "extract_enum_candidate")
        by_subpattern_bucket[sub][bucket].append(s)

    lines: list[str] = []
    title = (
        f"# Implicit-state audit — {scan_id}"
        if scan_id
        else "# Implicit-state audit"
    )
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
    lines.append(f"**Raw candidates:** {len(raw_candidates)}")
    lines.append(f"**Scout verifications:** {len(scouts)}")
    lines.append("")

    pattern_counts = Counter(c.get("pattern", "?") for c in raw_candidates)
    lines.append("## Summary")
    lines.append("")
    lines.append("| Pattern | Candidate count |")
    lines.append("|---|---|")
    for p in sorted(pattern_counts):
        lines.append(f"| {p} | {pattern_counts[p]} |")
    lines.append("")

    for bucket in BUCKET_ORDER:
        total = (
            len(by_subpattern_bucket["A"].get(bucket, []))
            + len(by_subpattern_bucket["B"].get(bucket, []))
        )
        if total == 0:
            continue
        lines.append(f"- **{BUCKET_LABEL[bucket]}:** {total}")
    lines.append("")

    def _append_section(sub: str, heading: str) -> None:
        bucketed = by_subpattern_bucket[sub]
        if not any(bucketed.values()):
            return
        lines.append(f"## {heading}")
        lines.append("")
        for bucket in BUCKET_ORDER:
            items = bucketed.get(bucket, [])
            if not items:
                continue
            lines.append(f"### {BUCKET_LABEL[bucket]} ({len(items)})")
            lines.append("")
            for i, scout in enumerate(items, start=1):
                raw = by_id.get(scout.get("candidate_id", ""))
                lines.append(_render_candidate(scout, raw, i))

    _append_section(
        "A",
        "Sub-pattern A — stringly-typed state",
    )
    _append_section(
        "B",
        "Sub-pattern B — tuple-inferred identity",
    )

    # Next actions — top 3 high-confidence recommendations.
    lines.append("## Next action")
    lines.append("")
    all_scouts = scouts
    highest = [
        s for s in all_scouts
        if s.get("bucket") in (
            "extract_enum_candidate", "introduce_fk_candidate",
        )
    ]
    highest.sort(
        key=lambda s: (
            0 if s.get("bucket") == "introduce_fk_candidate" else 1,
            -(s.get("hit_count") or 0),
        ),
    )
    if not highest:
        lines.append("No high-confidence candidates — all hits bucketed as false positives or legacy allow-list.")
    else:
        for i, s in enumerate(highest[:3], start=1):
            symbols = s.get("symbols") or []
            symbol = symbols[0] if symbols else Path(s.get("file", "")).stem
            bucket = s.get("bucket", "extract_enum_candidate")
            rec = BUCKET_RECOMMENDATION.get(bucket, "").format(symbol=symbol)
            lines.append(f"{i}. {rec} — `{s.get('file', '?')}`")
    lines.append("")

    bucket_counts: dict[str, int] = defaultdict(int)
    for s in scouts:
        bucket_counts[s.get("bucket", "extract_enum_candidate")] += 1

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(raw_candidates),
            "scout_verifications": len(scouts),
            "pattern_counts": dict(pattern_counts),
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
        f"[report_implicit_state] scouts={len(scouts)} "
        f"raw_candidates={len(raw_candidates)}",
        file=sys.stderr,
    )
    print(f"[report_implicit_state] wrote {args.output_md}", file=sys.stderr)
    print(f"[report_implicit_state] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
