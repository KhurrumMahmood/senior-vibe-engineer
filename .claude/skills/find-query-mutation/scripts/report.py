#!/usr/bin/env python3
"""Render report.md + findings.json from query-mutation scout output.

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
    "rename_to_mutator",
    "split_reader_and_mutator",
    "legitimate_cache_warming",
    "false_positive_stdlib_wrapper",
)
BUCKET_LABEL: dict[str, str] = {
    "rename_to_mutator": "Rename to mutator",
    "split_reader_and_mutator": "Split reader from mutator",
    "legitimate_cache_warming": "Legitimate cache warming (allow-list)",
    "false_positive_stdlib_wrapper": "False positive — not a queryset mutation",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "rename_to_mutator": "`/fix-workflow cluster:{symbol}` (rename `{symbol}` → `get_or_create_*` / `fetch_and_heal_*` / `touch_*`)",
    "split_reader_and_mutator": "`/fix-workflow cluster:{symbol}` (split `{symbol}` into pure reader + separate mutator)",
    "legitimate_cache_warming": "Add `# hidden-mutation: cache warming` comment; no other change.",
    "false_positive_stdlib_wrapper": "Drop from candidates (`dict.update` / `set.update` on non-queryset receiver).",
}


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
            print(f"[report] WARN: bad JSON in {path}", file=sys.stderr)
    return out


def _render_hit_table(hits: list[dict[str, Any]], limit: int = 8) -> list[str]:
    if not hits:
        return []
    lines = ["**Mutation calls:**", ""]
    lines.append("| Method | Evidence |")
    lines.append("|---|---|")
    for h in hits[:limit]:
        method = h.get("method", "?")
        evidence = (h.get("evidence") or "").replace("|", "\\|").strip()
        lines.append(f"| `{method}` | `{evidence}` |")
    if len(hits) > limit:
        lines.append(f"| … | ({len(hits) - limit} more) |")
    lines.append("")
    return lines


def _render_candidate(
    scout: dict[str, Any],
    candidate: dict[str, Any] | None,
    idx: int,
) -> str:
    file = scout.get("file") or (candidate.get("file") if candidate else "?")
    symbol = scout.get("symbol") or (
        candidate.get("symbol") if candidate else "?"
    )
    bucket = scout.get("bucket", "rename_to_mutator")
    confidence = scout.get("confidence") or (
        candidate.get("confidence") if candidate else "?"
    )
    methods = scout.get("mutation_methods") or (
        candidate.get("mutation_methods", []) if candidate else []
    )
    hits = candidate.get("hits", []) if candidate else []

    out: list[str] = []
    out.append(f"### {idx}. `{symbol}` in `{file}`")
    out.append("")
    out.append(f"- **Candidate ID:** `{scout.get('candidate_id', '?')}`")
    out.append(f"- **Confidence:** {confidence}")
    out.append(
        f"- **Mutation methods:** "
        f"{', '.join(f'`{m}`' for m in methods) if methods else '—'}"
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
        by_bucket[s.get("bucket", "rename_to_mutator")].append(s)

    lines: list[str] = []
    title = (
        f"# Query-mutation audit — {scan_id}"
        if scan_id else "# Query-mutation audit"
    )
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
    lines.append(f"**Raw candidates:** {len(raw_candidates)}")
    lines.append(f"**Scout verifications:** {len(scouts)}")
    lines.append("")

    method_counts: Counter[str] = Counter()
    for c in raw_candidates:
        for m in c.get("mutation_methods", []):
            method_counts[m] += 1

    lines.append("## Summary")
    lines.append("")
    lines.append("| Mutation method | Candidate count |")
    lines.append("|---|---|")
    for m in sorted(method_counts):
        lines.append(f"| `{m}` | {method_counts[m]} |")
    lines.append("")

    for bucket in BUCKET_ORDER:
        n = len(by_bucket.get(bucket, []))
        if n == 0:
            continue
        lines.append(f"- **{BUCKET_LABEL[bucket]}:** {n}")
    lines.append("")

    for bucket in BUCKET_ORDER:
        items = by_bucket.get(bucket, [])
        if not items:
            continue
        lines.append(f"## {BUCKET_LABEL[bucket]} ({len(items)})")
        lines.append("")
        for i, scout in enumerate(items, start=1):
            raw = by_id.get(scout.get("candidate_id", ""))
            lines.append(_render_candidate(scout, raw, i))

    lines.append("## Next action")
    lines.append("")
    actionable = [
        s for s in scouts
        if s.get("bucket") in ("rename_to_mutator", "split_reader_and_mutator")
    ]
    actionable.sort(
        key=lambda s: (
            0 if s.get("bucket") == "rename_to_mutator" else 1,
            -(s.get("hit_count") or 0),
        ),
    )
    if not actionable:
        lines.append(
            "No actionable findings — all hits bucketed as legitimate or false positive."
        )
    else:
        for i, s in enumerate(actionable[:3], start=1):
            symbol = s.get("symbol", "?")
            bucket = s.get("bucket", "rename_to_mutator")
            rec = BUCKET_RECOMMENDATION.get(bucket, "").format(symbol=symbol)
            lines.append(f"{i}. {rec} — `{s.get('file', '?')}`")
    lines.append("")

    bucket_counts: dict[str, int] = defaultdict(int)
    for s in scouts:
        bucket_counts[s.get("bucket", "rename_to_mutator")] += 1

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(raw_candidates),
            "scout_verifications": len(scouts),
            "mutation_method_counts": dict(method_counts),
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
        f"[report_query_mutation] scouts={len(scouts)} "
        f"raw_candidates={len(raw_candidates)}",
        file=sys.stderr,
    )
    print(f"[report_query_mutation] wrote {args.output_md}", file=sys.stderr)
    print(f"[report_query_mutation] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
