#!/usr/bin/env python3
"""Render triage.md + findings.json from ranked findings.

Reads rank.py's output and writes a human-readable triage plus a
machine-readable findings JSON.  If a scout classification file is supplied
via --classified, its per-finding fix_shape/notes and any dormant-code
side-channel entries are merged in.

Usage:
  python report.py \\
      --input ranked.json \\
      --classified classified.json \\
      --output-md triage.md \\
      --output-json findings.json \\
      --scan-id scan-20260417-120000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MAX_SITES_SHOWN = 12


def _render_finding(
    f: dict[str, Any], idx: int, info: dict[str, Any]
) -> str:
    meta = f.get("rank_meta", {})
    tier = meta.get("priority_tier", "P2")
    lines: list[str] = []
    lines.append(f"#### {tier}-{idx}: `{f['finding_id']}` — {f.get('shape_hint', '')}")
    if f.get("category"):
        lines.append(f"*Category:* `{f['category']}`")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| Multiplicity | {f.get('multiplicity', '-')} |")
    shared = f.get("shared_lines_max")
    if shared is not None:
        lines.append(f"| Shared lines (max) | {shared} |")
    lines.append(
        f"| Divergence risk | {meta.get('divergence_risk', '-')} (heuristic) |"
    )
    lines.append(
        f"| Bug blast radius | {meta.get('bug_blast_radius', '-')} (shape) |"
    )
    lines.append(f"| Effort hint | {meta.get('effort_hint', '-')} |")
    lines.append(f"| Priority | {meta.get('priority', '-')} |")
    if f.get("raw_pairs_collapsed"):
        lines.append(
            f"| Raw pairs collapsed | {f['raw_pairs_collapsed']} |"
        )
    lines.append("")
    lines.append("**Sites:**")
    for s in f.get("sites", [])[:MAX_SITES_SHOWN]:
        method = s.get("method") or "<module>"
        line = s.get("start_line", "?")
        lines.append(f"- `{s.get('file', '?')}:{line}` — `{method}`")
    if len(f.get("sites", [])) > MAX_SITES_SHOWN:
        lines.append(
            f"- ...and {len(f['sites']) - MAX_SITES_SHOWN} more"
        )
    lines.append("")

    if f.get("consolidation_safety") == "unknown_human_review_required":
        lines.append(
            "**Assessment:** Lexical evidence only — semantic equivalence and "
            "refactor safety are unknown."
        )
    elif info.get("fix_shape"):
        lines.append(f"**Recommended fix shape:** {info['fix_shape']}")
    else:
        lines.append("**Recommended fix shape:** *scout investigation pending*")
    if info.get("latent_bug_risk"):
        lines.append(f"**Latent bug risk:** {info['latent_bug_risk']}")
    if info.get("notes"):
        lines.append("")
        lines.append(info["notes"])
    lines.append("")
    if f.get("consolidation_safety") == "unknown_human_review_required":
        lines.append(
            "**Next step:** Review both bodies and callers before proposing any "
            "refactor; this lexical match does not establish safe consolidation."
        )
    else:
        lines.append(f"**Next step:** `/fix-workflow cluster:{f['finding_id']}`")
    lines.append("")
    return "\n".join(lines)


def render_triage(
    ranked: dict[str, Any],
    classified: dict[str, Any] | None,
    scan_id: str | None,
) -> str:
    meta = ranked.get("scan_meta", {})
    findings = ranked.get("findings", [])
    summary = meta.get("rank_summary", {})
    dormant = (classified or {}).get("dormant_candidates", [])
    classified_by_id: dict[str, dict[str, Any]] = {
        c["finding_id"]: c
        for c in (classified or {}).get("findings", [])
        if c.get("finding_id")
    }

    lines: list[str] = []
    title = (
        f"# Duplication triage — {scan_id}"
        if scan_id
        else "# Duplication triage"
    )
    lines.append(title)
    lines.append("")
    lines.append(f"**Target:** `{meta.get('target', '?')}`")
    lines.append(f"**Project root:** `{meta.get('project_root', '?')}`")
    lines.append(f"**Scan status:** `{meta.get('status', 'unknown')}`")
    lines.append(f"**Generated:** {meta.get('generated_at', '?')}")
    lines.append("")

    if meta.get("language") in {"typescript", "javascript", "go", "java"}:
        language_label = {
            "typescript": "TypeScript",
            "javascript": "JavaScript",
            "go": "Go",
            "java": "Java",
        }[meta["language"]]
        evidence_label = (
            "exact normalized function-body clone evidence"
            if meta.get("language") == "go"
            else "exact normalized method/constructor-body clone evidence"
            if meta.get("language") == "java"
            else "lexical/near-lexical clone evidence with source spans and "
            "enclosing symbols"
        )
        lines.append(
            f"> **{language_label} v1 boundary:** This is {evidence_label}. "
            "Do not consolidate "
            "automatically; behavior, callers, overload semantics, and ownership "
            "still require human review."
        )
        lines.append("")

    analysis = meta.get("analysis")
    constrained = 0
    if meta.get("language") == "go" and isinstance(analysis, dict):
        status_counts = analysis.get("file_status_counts")
        if isinstance(status_counts, dict):
            constrained = status_counts.get("build-constraint-ambiguous", 0)
    if meta.get("language") == "go" and meta.get("status") == "partial" and constrained:
        lines.append(
            f"> **Partial Go scan:** {constrained} build-constrained source file(s) "
            "were not analyzed. Findings do not cover those files."
        )
        lines.append("")

    lines.append("## Headline numbers")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| jscpd raw pairs | {meta.get('jscpd_raw_pair_count', 0)} |")
    lines.append(
        f"| jscpd filtered pairs | {meta.get('jscpd_filtered_pair_count', 0)} |"
    )
    lines.append(f"| jscpd findings | {meta.get('jscpd_finding_count', 0)} |")
    lines.append(f"| AST findings | {meta.get('ast_finding_count', 0)} |")
    lines.append(f"| AST filtered | {meta.get('ast_filtered_count', 0)} |")
    lines.append(f"| Total findings | {len(findings)} |")
    lines.append(
        f"| P0 / P1 / P2 | "
        f"{summary.get('p0', 0)} / "
        f"{summary.get('p1', 0)} / "
        f"{summary.get('p2', 0)} |"
    )
    lines.append(f"| Dormant side-channel | {len(dormant)} |")
    lines.append("")

    lines.append("## Priority clusters")
    lines.append("")
    by_tier: dict[str, list[dict[str, Any]]] = {"P0": [], "P1": [], "P2": []}
    for f in findings:
        tier = f.get("rank_meta", {}).get("priority_tier", "P2")
        by_tier.setdefault(tier, []).append(f)

    for tier in ("P0", "P1", "P2"):
        bucket = by_tier.get(tier, [])
        if not bucket:
            continue
        lines.append(f"### Tier {tier} ({len(bucket)})")
        lines.append("")
        for idx, f in enumerate(bucket, start=1):
            info = classified_by_id.get(f["finding_id"], {})
            lines.append(_render_finding(f, idx, info))

    if dormant:
        lines.append("## Dormant-code side-channel")
        lines.append("")
        lines.append(
            "*Not duplication — dead/quasi-dead code found while verifying "
            "call sites. Hand off to `/find-dormant` + `/fix-workflow` for "
            "deletion review.*"
        )
        lines.append("")
        for i, cand in enumerate(dormant, start=1):
            lines.append(f"### Candidate {i}: `{cand.get('name', '?')}`")
            if cand.get("file"):
                lines.append(
                    f"- **File:** `{cand['file']}:{cand.get('line', '?')}`"
                )
            if cand.get("evidence"):
                lines.append(f"- **Evidence:** {cand['evidence']}")
            if cand.get("reachable_via"):
                lines.append(
                    f"- **Reachable via:** {cand['reachable_via']}"
                )
            if cand.get("last_touched"):
                lines.append(
                    f"- **Git last-touched:** {cand['last_touched']}"
                )
            lines.append(
                "- **Recommended action:** `/find-dormant` -> human "
                "authorization -> `/fix-workflow`"
            )
            lines.append("")

    lines.append("## Next action")
    lines.append("")
    if findings:
        top = findings[0]
        if meta.get("language") in {"typescript", "javascript", "go", "java"}:
            lines.append(
                f"Review the evidence for `{top['finding_id']}` before deciding "
                "whether any refactor is appropriate; this report makes no "
                "consolidation recommendation."
            )
        else:
            lines.append(
                f"Run `/fix-workflow {top['finding_id']}` to execute the "
                f"top-ranked cluster,"
            )
        if dormant:
            lines.append(
                "or `/find-dormant` to process the side-channel findings "
                "first."
            )
    else:
        lines.append("No findings to action.")
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render triage.md + findings.json from ranked findings."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--classified", default=None)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--scan-id", default=None)
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        ranked = json.load(fh)

    classified = None
    if args.classified:
        with open(args.classified, encoding="utf-8") as fh:
            classified = json.load(fh)

    triage = render_triage(ranked, classified, args.scan_id)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(triage, encoding="utf-8")

    # Merge scout classification into the machine-readable payload.
    # Without this, triage.md shows fix_shape/notes/dormant_candidates but
    # findings.json strips them — any downstream consumer (fix-workflow,
    # the orchestrator's planner) that reads JSON instead of parsing
    # markdown would silently lose the scout's triage work.
    classified_by_id: dict[str, dict[str, Any]] = {
        c["finding_id"]: c
        for c in (classified or {}).get("findings", [])
        if c.get("finding_id")
    }
    merged_findings: list[dict[str, Any]] = []
    for f in ranked.get("findings", []):
        out = dict(f)
        info = classified_by_id.get(f.get("finding_id"))
        if info:
            out["classification"] = {
                k: v for k, v in info.items()
                if k in {
                    "fix_shape", "notes", "latent_bug_risk",
                    "recommended_next_step", "scout_id",
                }
            }
        merged_findings.append(out)
    payload: dict[str, Any] = {
        "scan_meta": ranked.get("scan_meta", {}),
        "findings": merged_findings,
        "dormant_candidates": (classified or {}).get("dormant_candidates", []),
    }
    if args.scan_id:
        payload["scan_id"] = args.scan_id

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"[report] wrote {args.output_md}", file=sys.stderr)
    print(f"[report] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
