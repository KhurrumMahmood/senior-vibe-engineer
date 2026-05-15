#!/usr/bin/env python
"""
Stage 5 of /find-frontend-duplication: produce triage.md + findings.json.

Reads:
  --input       ranked.json
  --classified  classified.json (Stage 4 sub-agent output, optional)
  --scan-id     scan-YYYYMMDD-HHMMSS
Writes:
  --output-md   triage.md
  --output-json findings.json (machine-readable subset)
"""

import argparse
import json
import sys
from pathlib import Path


def fmt_files(files, max_show=4):
    if len(files) <= max_show:
        return ", ".join(files)
    return ", ".join(files[:max_show]) + f" (+{len(files) - max_show} more)"


def render_md(ranked, classified, scan_id):
    out = []
    out.append(f"# Frontend duplication triage — `{scan_id}`")
    out.append("")
    counts = ranked.get("priority_counts", {})
    out.append(f"**Counts:** P0={counts.get('P0', 0)}, P1={counts.get('P1', 0)}, "
               f"P2={counts.get('P2', 0)}, skipped={counts.get('skip', 0)}")
    out.append("")
    by_cat = ranked.get("by_category", {})
    if by_cat:
        out.append("**By category:** " + ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))
        out.append("")

    classified_index = {}
    if classified:
        for c in classified.get("candidates", []):
            classified_index[c["id"]] = c

    for tier in ("P0", "P1", "P2"):
        tier_candidates = [c for c in ranked["candidates"]
                           if c["rank_meta"]["priority"] == tier]
        if not tier_candidates:
            continue
        out.append(f"## {tier} candidates ({len(tier_candidates)})")
        out.append("")
        for c in tier_candidates:
            out.append(f"### {c['title']}")
            out.append(f"- **ID:** `{c['id']}`")
            out.append(f"- **Category:** `{c['category']}` (source: `{c['source']}`)")
            out.append(f"- **Score:** {c['rank_meta']['score']}")
            out.append(f"- **Files ({c['evidence']['file_count']}):** {fmt_files(c['evidence']['files'])}")
            if c.get("existing_primitive"):
                ep = c["existing_primitive"]
                out.append(f"- **Existing primitive:** `<c-{ep['name']}/>` "
                           f"({ep['callsite_count']} adopting callsites) "
                           f"— **bypass:** `{c['primitive_bypass']}`")
            if c.get("notes"):
                out.append(f"- **Note:** {c['notes']}")

            scout = classified_index.get(c["id"])
            if scout:
                out.append("")
                out.append("**Investigator finding:**")
                out.append(f"- Recommendation: **{scout.get('recommendation', '?')}**")
                out.append(f"- Confidence: {scout.get('confidence', '?')}")
                if scout.get("rationale"):
                    out.append(f"- Rationale: {scout['rationale']}")
                if scout.get("blockers"):
                    out.append(f"- Blockers: {scout['blockers']}")
                if scout.get("next_skill"):
                    out.append(f"- Next: `/{scout['next_skill']}`")
            out.append("")
        out.append("")

    skipped = [c for c in ranked["candidates"]
               if c["rank_meta"]["priority"] == "skip"]
    if skipped:
        out.append(f"## Skipped ({len(skipped)})")
        out.append("")
        out.append("Layout utilities and other non-extractable patterns. "
                   "See `ranked.json` for the full list.")
        out.append("")

    return "\n".join(out) + "\n"


def render_findings_json(ranked, classified):
    classified_index = {}
    if classified:
        for c in classified.get("candidates", []):
            classified_index[c["id"]] = c

    findings = []
    for c in ranked["candidates"]:
        if c["rank_meta"]["priority"] == "skip":
            continue
        finding = {
            "id": c["id"],
            "category": c["category"],
            "shape": c["category"],  # alias for the effectiveness logger
            "priority": c["rank_meta"]["priority"],
            "score": c["rank_meta"]["score"],
            "title": c["title"],
            "file_count": c["evidence"]["file_count"],
            "occurrence_count": c["evidence"]["occurrence_count"],
            "files": c["evidence"]["files"],
            "primitive_bypass": c.get("primitive_bypass", False),
        }
        scout = classified_index.get(c["id"])
        if scout:
            finding["scout"] = {
                "recommendation": scout.get("recommendation"),
                "confidence": scout.get("confidence"),
                "next_skill": scout.get("next_skill"),
            }
        findings.append(finding)
    return {"findings": findings, "candidates": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--classified", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--scan-id", type=str, required=True)
    args = parser.parse_args()

    ranked = json.loads(args.input.read_text())
    classified = json.loads(args.classified.read_text()) if args.classified and args.classified.exists() else None

    md = render_md(ranked, classified, args.scan_id)
    findings = render_findings_json(ranked, classified)

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(md, encoding="utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
