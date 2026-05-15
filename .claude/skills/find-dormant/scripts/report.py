#!/usr/bin/env python3
"""Render report.md + findings.json from scout verifications.

Reads a directory of scout JSON files (one per candidate) and bundles
them into the final `report.md` that the user sees + a machine-readable
`findings.json` that `/fix-workflow` can parse.

Each scout file has the schema documented in
`knowledge/verification.md` (section "Output schema").

Usage:
  python report.py \\
      --scout-dir <dir> \\
      --candidates <candidates.jsonl> \\
      --output-md <report.md> \\
      --output-json <findings.json> \\
      --scan-id <scan-20260417-120000> \\
      [--target <dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BUCKET_ORDER: tuple[str, ...] = (
    "certain_delete",
    "orphan_endpoint",
    "quasi_dead_broken",
    "false_positive",
)
BUCKET_LABELS: dict[str, str] = {
    "certain_delete": "Certain delete",
    "orphan_endpoint": "Orphan endpoint",
    "quasi_dead_broken": "Quasi-dead / broken",
    "false_positive": "False positives filtered",
}
BUCKET_RECOMMENDATION: dict[str, str] = {
    "certain_delete": "`/fix-workflow delete:{name}` (after user authorization)",
    "orphan_endpoint": "`/fix-workflow delete:{name}` (confirm endpoint path with user first)",
    "quasi_dead_broken": "`/fix-workflow fix:{name}` (repair + regression test; deletion is a separate decision)",
    "false_positive": "Drop from candidates",
}


def _load_scouts(scout_dir: Path) -> list[dict[str, Any]]:
    if not scout_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(scout_dir.glob("*.json")):
        try:
            out.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            print(f"[report] WARN: bad JSON in {path}", file=sys.stderr)
    return out


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _render_evidence(evidence: dict[str, Any]) -> list[str]:
    if not evidence:
        return []
    lines = ["**Evidence:**"]
    order = [
        ("url_wired", "URL-wired"),
        ("url_path", "URL path"),
        ("url_name", "URL name"),
        ("template_hits", "Template hits"),
        ("js_hits", "JS hits"),
        ("admin_refs", "Admin refs"),
        ("command_refs", "Management-command refs"),
        ("signal_refs", "Signal refs"),
        ("external_api_risk", "External API risk"),
        ("git_last_touched", "Git last-touched"),
        ("git_only_rename_commits", "Only rename commits"),
    ]
    for key, label in order:
        if key in evidence:
            lines.append(f"- **{label}:** `{evidence[key]}`")
    import_sites = evidence.get("import_sites") or []
    if import_sites:
        lines.append(f"- **Import sites:** {len(import_sites)}")
        for s in import_sites[:5]:
            lines.append(f"    - `{s}`")
    call_sites = evidence.get("call_sites") or []
    if call_sites:
        lines.append(f"- **Call sites:** {len(call_sites)}")
        for s in call_sites[:5]:
            lines.append(f"    - `{s}`")
    return lines


def _render_candidate(scout: dict[str, Any], idx: int) -> str:
    name = scout.get("name", "?")
    qname = scout.get("qualified_name", name)
    file = scout.get("file", "?")
    line = scout.get("line", "?")
    flavor = scout.get("flavor", "?")
    bucket = scout.get("bucket", "?")
    rec = scout.get("recommendation", "none")

    out: list[str] = []
    out.append(f"### {idx}. `{qname}` at `{file}:{line}`")
    out.append("")
    out.append(f"- **Candidate ID:** `{scout.get('candidate_id', '?')}`")
    out.append(f"- **Kind:** {scout.get('kind', '?')}")
    out.append(f"- **Flavor:** {flavor}")
    out.append(f"- **Source:** {scout.get('source', '?')}")
    if scout.get("false_positive_reason"):
        out.append(f"- **False-positive reason:** `{scout['false_positive_reason']}`")
    out.append("")
    out.extend(_render_evidence(scout.get("evidence") or {}))
    if scout.get("notes"):
        out.append("")
        out.append(f"> {scout['notes']}")
    out.append("")
    rec_template = BUCKET_RECOMMENDATION.get(bucket, "(no default action)")
    out.append(
        f"**Recommended action:** "
        f"{rec_template.format(name=name)} — scout recommends `{rec}`."
    )
    out.append("")
    return "\n".join(out)


def render_report(
    scouts: list[dict[str, Any]],
    raw_candidates: list[dict[str, Any]],
    scan_id: str | None,
    target: str | None,
) -> tuple[str, dict[str, Any]]:
    by_bucket: dict[str, list[dict[str, Any]]] = {b: [] for b in BUCKET_ORDER}
    for s in scouts:
        by_bucket.setdefault(s.get("bucket", "false_positive"), []).append(s)

    flavor_counts = Counter(str(s.get("flavor", "?")) for s in scouts)
    source_counts = Counter(s.get("source", "?") for s in scouts)

    lines: list[str] = []
    title = f"# Dormant-code audit — {scan_id}" if scan_id else "# Dormant-code audit"
    lines.append(title)
    lines.append("")
    if target:
        lines.append(f"**Target:** `{target}`")
    lines.append(f"**Raw candidates:** {len(raw_candidates)}")
    lines.append(f"**Scout verifications:** {len(scouts)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---|")
    for bucket in BUCKET_ORDER:
        lines.append(
            f"| {BUCKET_LABELS[bucket]} | {len(by_bucket.get(bucket, []))} |"
        )
    lines.append("")
    lines.append("| Flavor | Count |")
    lines.append("|---|---|")
    for flavor in sorted(flavor_counts):
        lines.append(f"| Flavor {flavor} | {flavor_counts[flavor]} |")
    lines.append("")
    lines.append("| Source | Count |")
    lines.append("|---|---|")
    for source in sorted(source_counts):
        lines.append(f"| {source} | {source_counts[source]} |")
    lines.append("")

    for bucket in BUCKET_ORDER:
        items = by_bucket.get(bucket, [])
        if not items:
            continue
        lines.append(f"## {BUCKET_LABELS[bucket]} ({len(items)})")
        lines.append("")
        for i, scout in enumerate(items, start=1):
            lines.append(_render_candidate(scout, i))

    lines.append("## Next action")
    lines.append("")
    top_delete = by_bucket.get("certain_delete", [])
    top_orphan = by_bucket.get("orphan_endpoint", [])
    top_broken = by_bucket.get("quasi_dead_broken", [])
    if top_delete:
        n = top_delete[0].get("name", "?")
        lines.append(f"1. Confirm `{n}` deletion: `/fix-workflow delete:{n}`")
    if top_orphan:
        n = top_orphan[0].get("name", "?")
        lines.append(
            f"2. Review orphan endpoint `{n}` — confirm it's not an "
            f"internal-only API, then `/fix-workflow delete:{n}`"
        )
    if top_broken:
        n = top_broken[0].get("name", "?")
        lines.append(
            f"3. Fix quasi-dead `{n}`: `/fix-workflow fix:{n}` (regression "
            f"test first, deletion decision after)"
        )
    if not (top_delete or top_orphan or top_broken):
        lines.append("All candidates were false positives — no action needed.")
    lines.append("")

    findings_json = {
        "scan_id": scan_id,
        "target": target,
        "summary": {
            "raw_candidates": len(raw_candidates),
            "scout_verifications": len(scouts),
            "bucket_counts": {b: len(by_bucket.get(b, [])) for b in BUCKET_ORDER},
            "flavor_counts": dict(flavor_counts),
            "source_counts": dict(source_counts),
        },
        "findings": scouts,
    }

    return "\n".join(lines), findings_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scout-dir", required=True, type=Path,
                   help="Directory of scout JSON files (one per candidate)")
    p.add_argument("--candidates", required=True, type=Path,
                   help="Raw candidates.jsonl from collapse.py (for counts)")
    p.add_argument("--output-md", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--scan-id", default=None)
    p.add_argument("--target", default=None)
    args = p.parse_args(argv)

    scouts = _load_scouts(args.scout_dir)
    raw_candidates = _read_candidates(args.candidates)
    report_md, findings_json = render_report(
        scouts, raw_candidates, args.scan_id, args.target
    )

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(report_md)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(findings_json, indent=2))

    print(f"[report] scouts={len(scouts)} raw_candidates={len(raw_candidates)}",
          file=sys.stderr)
    print(f"[report] wrote {args.output_md}", file=sys.stderr)
    print(f"[report] wrote {args.output_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
