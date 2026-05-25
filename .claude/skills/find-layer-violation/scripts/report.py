#!/usr/bin/env python3
"""Render report.md + findings.json for /find-layer-violation.

Reads ``candidates.jsonl`` (per-symbol candidates, score-ordered) and a
``scout/`` directory of per-candidate verdict JSON files written by the
Stage-3 scouts. Bundles them into a markdown report (one section per
candidate, grouped by bucket) plus a machine-readable findings.json that
downstream skills can parse.

Scout JSON schema (see knowledge/verification.md):

    {
      "candidate_id": "layer-0001",
      "file": "core/views/external_source.py",
      "symbol": "ExternalSourceExtractView.post",
      "bucket": "extract_service | move_to_existing_service | broad_workflow_coordinator | intentional_http_coupling",
      "signals_confirmed": ["fat", "multi_model_write"],
      "signals_dismissed": [
        {"signal": "dispatch_bypass", "reason": "fire-and-forget log — safe"}
      ],
      "business_logic_summary": "1-2 sentences naming the domain work the view owns",
      "extraction_sketch": [
        {"new_function": "ExternalSourceService.extract_from_url(...)",
         "moved_from_lines": "412-530"}
      ],
      "interface_depth_note": "Deletion test passes because retry, transaction, and result-shaping policy would otherwise spread across three views.",
      "false_positive_reason": "http_coupled | already_service_call | null",
      "notes": "1-3 sentence scout summary",
      "recommendation": "extract_service | move_to_existing_service | keep"
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
    "extract_service",
    "move_to_existing_service",
    "broad_workflow_coordinator",
    "intentional_http_coupling",
    "unverified",
)
BUCKET_LABELS: dict[str, str] = {
    "extract_service": "Extract new service (business logic in HTTP layer)",
    "move_to_existing_service": "Move to existing service (wrong home)",
    "broad_workflow_coordinator": "Broad workflow coordinator (map topology first)",
    "intentional_http_coupling": "Intentional HTTP coupling (false positive)",
    "unverified": "Unverified (scout budget exceeded)",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "extract_service": (
        "`/fix-workflow layer:<candidate_id>` — extract a new "
        "`core/services/<domain>/` method; keep the view as a thin HTTP wrapper"
    ),
    "move_to_existing_service": (
        "`/fix-workflow layer:<candidate_id>` — move logic into the named "
        "existing service; delete the duplicate in the view"
    ),
    "broad_workflow_coordinator": (
        "`/map-product-workflow` then `/extract-workflow-registry` — make "
        "the product workflow owner explicit before extracting another service"
    ),
    "intentional_http_coupling": (
        "Drop — the logic is deeply HTTP-coupled (proxy setup, gzip, IP lookup) "
        "and should stay in the view per CLAUDE.md View Pattern"
    ),
    "unverified": "Re-run `/find-layer-violation` with a higher scout budget",
}


SIGNAL_LABELS: dict[str, str] = {
    "fat": "Fat body (exceeds LOC budget)",
    "domain_loop": "Domain loop over queryset",
    "direct_llm_call": "Direct LLM / agent call",
    "dispatch_bypass": "Dispatch bypass (bare `.delay`)",
    "multi_model_write": "Multi-model write in one function",
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


def _render_candidate(
    candidate: dict[str, Any],
    scout: dict[str, Any] | None,
    idx: int,
) -> str:
    cid = candidate.get("candidate_id", "?")
    file = candidate.get("file", "?")
    symbol = candidate.get("symbol", "?")
    loc = candidate.get("loc", "?")
    kind = candidate.get("kind", "?")
    signals = candidate.get("signals") or []
    signal_count = candidate.get("signal_count", len(signals))
    evidence = candidate.get("evidence") or {}

    out: list[str] = []
    out.append(f"### {idx}. `{file}` — `{symbol}`")
    out.append("")
    out.append(f"- **Candidate ID:** `{cid}`")
    out.append(f"- **Kind:** `{kind}`")
    out.append(f"- **LOC:** {loc}")
    out.append(f"- **Signal count:** {signal_count} "
               f"(confidence: `{candidate.get('confidence', '?')}`)")
    out.append(f"- **Score:** {candidate.get('score', '?')}")
    out.append("")
    if signals:
        out.append("**Detected signals:**")
        out.append("")
        out.append("| Signal | Evidence |")
        out.append("|---|---|")
        for s in signals:
            label = SIGNAL_LABELS.get(s, s)
            ev = evidence.get(s, "")
            out.append(f"| `{s}` ({label}) | {ev} |")
        out.append("")

    if scout:
        bucket = scout.get("bucket", "unverified")
        out.append(f"**Scout verdict:** `{bucket}`")
        if scout.get("business_logic_summary"):
            out.append(
                f"- **Business-logic summary:** "
                f"{scout['business_logic_summary']}"
            )
        confirmed = scout.get("signals_confirmed") or []
        if confirmed:
            out.append(
                f"- **Signals confirmed:** "
                f"{', '.join(f'`{s}`' for s in confirmed)}"
            )
        dismissed = scout.get("signals_dismissed") or []
        if dismissed:
            out.append("- **Signals dismissed:**")
            for d in dismissed:
                sig = d.get("signal", "?") if isinstance(d, dict) else str(d)
                reason = d.get("reason", "") if isinstance(d, dict) else ""
                out.append(f"    - `{sig}` — {reason}")
        if scout.get("false_positive_reason"):
            out.append(
                f"- **False-positive reason:** "
                f"`{scout['false_positive_reason']}`"
            )
        sketch = scout.get("extraction_sketch") or []
        if sketch:
            out.append("- **Extraction sketch:**")
            for piece in sketch:
                new_fn = piece.get("new_function", "?")
                src = piece.get("moved_from_lines", "")
                src_label = f" (from `{src}`)" if src else ""
                out.append(f"    - `{new_fn}`{src_label}")
        if scout.get("interface_depth_note"):
            out.append(
                f"- **Interface-depth note:** "
                f"{scout['interface_depth_note']}"
            )
        if scout.get("notes"):
            out.append("")
            out.append(f"> {scout['notes']}")
        out.append("")
        rec_template = BUCKET_RECOMMENDATION.get(bucket, "(no default action)")
        rec_template = rec_template.replace("<candidate_id>", cid)
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
            "**Recommended action:** re-run `/find-layer-violation` with a "
            "higher scout budget or dispatch a scout manually."
        )
    out.append("")
    return "\n".join(out)


def render_report(
    candidates: list[dict[str, Any]],
    scouts: dict[str, dict[str, Any]],
    scan_id: str | None,
    target: str | None,
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
    signal_counts: Counter[str] = Counter()
    for cand in candidates:
        for s in cand.get("signals") or []:
            signal_counts[s] += 1

    lines: list[str] = []
    title = (
        f"# Layer-violation audit — {scan_id}"
        if scan_id
        else "# Layer-violation audit"
    )
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
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
    if signal_counts:
        lines.append("| Signal | Hits across candidates |")
        lines.append("|---|---|")
        for sig in sorted(signal_counts, key=lambda s: -signal_counts[s]):
            lines.append(
                f"| `{sig}` ({SIGNAL_LABELS.get(sig, sig)}) | "
                f"{signal_counts[sig]} |"
            )
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
    extract = by_bucket.get("extract_service", [])
    move = by_bucket.get("move_to_existing_service", [])
    step = 1
    if extract:
        top = extract[0][0]
        lines.append(
            f"{step}. Extract a service for `{top.get('file', '?')}`::"
            f"`{top.get('symbol', '?')}` — run "
            f"`/fix-workflow layer:{top.get('candidate_id', '?')}`. Follow the "
            f"`core/services/<domain>/` directory-package precedent."
        )
        step += 1
        if len(extract) > 1:
            lines.append(
                f"{step}. After the first extraction ships, revisit the "
                f"remaining {len(extract) - 1} `extract_service` candidate(s)."
            )
            step += 1
    if move:
        top = move[0][0]
        lines.append(
            f"{step}. Move `{top.get('file', '?')}`::"
            f"`{top.get('symbol', '?')}` into its existing service — "
            f"run `/fix-workflow layer:{top.get('candidate_id', '?')}`."
        )
        step += 1
    if not extract and not move:
        lines.append(
            "No layer violations requiring action — all flagged symbols are "
            "either HTTP-coupled or unverified."
        )
    lines.append("")

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(candidates),
            "scout_verifications": len(scouts),
            "bucket_counts": bucket_counts,
            "signal_counts": dict(signal_counts),
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
    report_md, findings_json = render_report(
        candidates, scouts, args.scan_id, args.target
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
