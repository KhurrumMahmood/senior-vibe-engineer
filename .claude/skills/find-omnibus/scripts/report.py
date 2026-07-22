#!/usr/bin/env python3
"""Render report.md + findings.json for /find-omnibus.

Reads ``candidates.jsonl`` (raw detections, score-ordered) and a
``scout/`` directory of per-candidate verdict JSON files written by the
Stage-3 scouts. Bundles them into a markdown report (one section per
candidate, grouped by bucket) plus a machine-readable findings.json the
parent skills can parse.

Scout JSON schema (see knowledge/verification.md):

    {
      "candidate_id": "omnibus-0001",
      "file": "core/views/sitemaps.py",
      "bucket": "confirmed_omnibus | coordination_omnibus | facets_not_domains | borderline",
      "domains_confirmed": ["discovery", "crud", "import", "filter_state"],
      "srp_rewrite": "This file handles sitemap discovery and sitemap CRUD and URL import and filter state.",
      "decomposition_sketch": [
        {"new_file": "core/views/sitemaps/discovery.py", "symbols": [...]},
        ...
      ],
      "decomposition_depth_note": "Deletion test passes because each proposed file owns one independently-understandable domain.",
      "false_positive_reason": null,
      "notes": "1-3 sentence scout summary",
      "recommendation": "decompose | keep | borderline"
    }

If the scout file is missing for a candidate, the report falls back to
the raw detector record with ``bucket: "unverified"``.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BUCKET_ORDER: tuple[str, ...] = (
    "confirmed_omnibus",
    "borderline",
    "coordination_omnibus",
    "facets_not_domains",
    "unverified",
)
BUCKET_LABELS: dict[str, str] = {
    "confirmed_omnibus": "Confirmed omnibus (decompose)",
    "borderline": "Borderline (human call)",
    "coordination_omnibus": "Coordination omnibus (map workflow first)",
    "facets_not_domains": "Facets of one job (false positive)",
    "unverified": "Unverified (scout budget exceeded)",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "confirmed_omnibus": (
        "`/refactor-subsystem <spec-id>` in decomposition mode — "
        "write the spec first under `ai-docs/specs/`"
    ),
    "borderline": "Revisit after the confirmed set clears",
    "coordination_omnibus": (
        "`/map-product-workflow` then `/extract-workflow-registry` — "
        "make the workflow owner explicit before splitting files"
    ),
    "facets_not_domains": "Drop — the clusters were facets of one job",
    "unverified": "Re-run `/find-omnibus` with a higher scout budget",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text()
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


def _load_scouts(scout_dir: Path) -> dict[str, dict[str, Any]]:
    if not scout_dir.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(scout_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            print(f"[report] WARN: bad JSON in {path}", file=sys.stderr)
            continue
        cid = data.get("candidate_id") or path.stem
        out[cid] = data
    return out


def _load_scan(path: Path) -> dict[str, Any] | None:
    """Read optional language detector state emitted beside candidates.jsonl."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(f"[report] WARN: invalid scan state in {path}", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def _render_candidate(
    candidate: dict[str, Any],
    scout: dict[str, Any] | None,
    idx: int,
) -> str:
    cid = candidate.get("candidate_id", "?")
    file = candidate.get("file", "?")
    loc = candidate.get("loc", "?")
    and_count = candidate.get("and_count", "?")
    srp = candidate.get("srp_sentence", "?")
    clusters = candidate.get("clusters") or []

    out: list[str] = []
    out.append(f"### {idx}. `{file}`")
    out.append("")
    out.append(f"- **Candidate ID:** `{cid}`")
    out.append(f"- **LOC:** {loc}")
    out.append(f"- **Cluster count:** {candidate.get('cluster_count', '?')}")
    out.append(f"- **SRP \"and\"-count:** {and_count}")
    if "risk_score" in candidate:
        signals = candidate.get("risk_signals") or []
        signal_text = ", ".join(f"`{s}`" for s in signals) if signals else "none"
        out.append(f"- **Risk score:** {candidate.get('risk_score')} ({signal_text})")
    out.append(f"- **Score:** {candidate.get('score', '?')}")
    out.append(f"- **SRP sentence (auto):** `{srp}`")
    out.append("")
    if clusters:
        out.append("**Detected clusters:**")
        out.append("")
        out.append("| Cluster | LOC | Symbols |")
        out.append("|---|---|---|")
        for cluster in clusters:
            name = cluster.get("name", "?")
            cl_loc = cluster.get("loc", "?")
            syms = cluster.get("symbols") or []
            sym_preview = ", ".join(f"`{s}`" for s in syms[:6])
            if len(syms) > 6:
                sym_preview += f", … (+{len(syms) - 6} more)"
            out.append(f"| `{name}` | {cl_loc} | {sym_preview} |")
        out.append("")

    if scout:
        bucket = scout.get("bucket", "unverified")
        out.append(f"**Scout verdict:** `{bucket}`")
        if scout.get("srp_rewrite"):
            out.append(f"- **SRP rewrite:** {scout['srp_rewrite']}")
        domains = scout.get("domains_confirmed") or []
        if domains:
            out.append(
                f"- **Domains confirmed:** "
                f"{', '.join(f'`{d}`' for d in domains)}"
            )
        if scout.get("false_positive_reason"):
            out.append(
                f"- **False-positive reason:** "
                f"`{scout['false_positive_reason']}`"
            )
        sketch = scout.get("decomposition_sketch") or []
        if sketch:
            out.append("- **Decomposition sketch:**")
            for piece in sketch:
                new_file = piece.get("new_file", "?")
                syms = piece.get("symbols") or []
                preview = ", ".join(f"`{s}`" for s in syms[:4])
                if len(syms) > 4:
                    preview += f", … (+{len(syms) - 4} more)"
                out.append(f"    - `{new_file}` ← {preview}")
        if scout.get("decomposition_depth_note"):
            out.append(
                f"- **Decomposition-depth note:** "
                f"{scout['decomposition_depth_note']}"
            )
        if scout.get("notes"):
            out.append("")
            out.append(f"> {scout['notes']}")
        out.append("")
        rec_template = BUCKET_RECOMMENDATION.get(bucket, "(no default action)")
        out.append(
            f"**Recommended action:** {rec_template} — scout recommends "
            f"`{scout.get('recommendation', 'none')}`."
        )
    else:
        out.append(
            "**Scout verdict:** `unverified` — no scout file was written "
            "for this candidate within the verification budget."
        )
        out.append("")
        out.append(
            "**Recommended action:** re-run `/find-omnibus` or dispatch "
            "a scout manually before taking action."
        )
    out.append("")
    return "\n".join(out)


def render_report(
    candidates: list[dict[str, Any]],
    scouts: dict[str, dict[str, Any]],
    scan_id: str | None,
    target: str | None,
    scan: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    by_bucket: dict[str, list[tuple[dict[str, Any], dict[str, Any] | None]]] = {
        b: [] for b in BUCKET_ORDER
    }
    for cand in candidates:
        cid = cand.get("candidate_id", "")
        scout = scouts.get(cid)
        bucket = (scout or {}).get("bucket", "unverified")
        if bucket not in by_bucket:
            by_bucket[bucket] = []
        by_bucket[bucket].append((cand, scout))

    bucket_counts = {b: len(by_bucket.get(b, [])) for b in BUCKET_ORDER}
    and_counts = Counter(int(c.get("and_count", 0)) for c in candidates)

    lines: list[str] = []
    title = (
        f"# Omnibus-module audit — {scan_id}"
        if scan_id
        else "# Omnibus-module audit"
    )
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
    if scan is not None:
        lines.append(f"**Status:** `{scan.get('status', 'unknown')}`")
        lines.append(f"**Analyzer:** `{scan.get('analyzer', 'unknown')}`")
        language = str(scan.get("language") or "unknown")
        if language == "java":
            lines.append(
                "**Java toolchain:** `"
                + str(scan.get("actual_java_version") or "not-run")
                + "` (minimum JDK `"
                + str(scan.get("minimum_jdk_version") or "unknown")
                + "`)"
            )
        elif language == "swift":
            lines.append(
                "**Swift compiler:** `"
                + str(scan.get("actual_swift_version") or "not-run")
                + "` (minimum Swift `"
                + str(scan.get("minimum_swift_version") or "unknown")
                + "`)"
            )
            lines.append(
                "**Fact boundary:** compiler typecheck/AST declarations only; "
                "no SwiftSyntax, resolved references, or complete project semantics"
            )
        status = scan.get("status")
        outcome = (
            "clean-within-complete"
            if status == "complete" and not candidates
            else "findings-within-complete"
            if status == "complete"
            else "incomplete"
            if status == "partial"
            else str(status or "unknown")
        )
        lines.append(f"**Outcome:** `{outcome}`")
    lines.append(f"**Raw candidates:** {len(candidates)}")
    lines.append(f"**Scout verifications:** {len(scouts)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---|")
    for bucket in BUCKET_ORDER:
        lines.append(
            f"| {BUCKET_LABELS[bucket]} | {bucket_counts.get(bucket, 0)} |"
        )
    lines.append("")
    lines.append("| `and`-count | Files |")
    lines.append("|---|---|")
    for ac in sorted(and_counts, reverse=True):
        lines.append(f"| {ac} | {and_counts[ac]} |")
    lines.append("")

    for bucket in BUCKET_ORDER:
        pairs = by_bucket.get(bucket, [])
        if not pairs:
            continue
        lines.append(f"## {BUCKET_LABELS[bucket]} ({len(pairs)})")
        lines.append("")
        for i, (cand, scout) in enumerate(pairs, start=1):
            lines.append(_render_candidate(cand, scout, i))

    lines.append("## Next action")
    lines.append("")
    confirmed = by_bucket.get("confirmed_omnibus", [])
    if scan is not None and scan.get("status") != "complete":
        language = str(scan.get("language") or "selected language").capitalize()
        lines.append(
            f"This {language} selection is not a clean omnibus result; repair or widen "
            "the source selection before interpreting zero candidates."
        )
    elif confirmed:
        top_file = confirmed[0][0].get("file", "?")
        lines.append(
            f"1. Decompose `{top_file}` — run "
            f"`/refactor-subsystem <spec-id>` in decomposition mode. "
            f"The spec must be scaffolded at `ai-docs/specs/<id>.md` "
            f"first (Phase 0 of `/refactor-subsystem` handles the stub)."
        )
        if len(confirmed) > 1:
            lines.append(
                f"2. After the first refactor ships, revisit the "
                f"remaining {len(confirmed) - 1} confirmed candidate(s)."
            )
    else:
        lines.append(
            "No confirmed omnibus modules — nothing to decompose this "
            "scan."
        )
    lines.append("")

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(candidates),
            "scout_verifications": len(scouts),
            "bucket_counts": bucket_counts,
            "and_count_distribution": dict(and_counts),
            "findings_total": len(candidates),
            "buckets": bucket_counts,
        },
        "findings": [
            {
                "candidate": cand,
                "scout": scouts.get(cand.get("candidate_id", ""), None),
            }
            for cand in candidates
        ],
    }
    if scan is not None:
        status = scan.get("status", "unknown")
        findings_json["status"] = status
        findings_json["outcome"] = (
            "clean-within-complete"
            if status == "complete" and not candidates
            else "findings-within-complete"
            if status == "complete"
            else "incomplete"
            if status == "partial"
            else status
        )
        findings_json["analysis"] = {str(scan.get("language") or "unknown"): scan}

    return "\n".join(lines), findings_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", required=True, type=Path,
                   help="candidates.jsonl from collapse.py")
    p.add_argument("--scout-dir", required=True, type=Path,
                   help="Directory of scout verdict JSON files")
    p.add_argument("--output-md", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--scan-id", default=None)
    p.add_argument("--target", default=None)
    args = p.parse_args(argv)

    candidates = _read_jsonl(args.candidates)
    scouts = _load_scouts(args.scout_dir)
    scan = _load_scan(args.candidates.with_name("scan.json"))
    report_md, findings_json = render_report(
        candidates, scouts, args.scan_id, args.target, scan
    )

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(report_md)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(findings_json, indent=2))

    print(
        f"[report] candidates={len(candidates)} scouts={len(scouts)}",
        file=sys.stderr,
    )
    print(f"[report] wrote {args.output_md}", file=sys.stderr)
    print(f"[report] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
