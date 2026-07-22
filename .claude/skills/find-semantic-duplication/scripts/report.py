#!/usr/bin/env python3
"""Render triage.md + findings.json from a ranked semantic-duplication scan.

Inputs:
  --input          ranked.json from scripts/rank.py
  --output-md      triage.md path
  --output-json    findings.json path (machine-readable for /fix-workflow)
  --scan-id        scan-<TS> identifier (for the report header)
  --matrices-dir   Relative path from triage.md to capability_matrices/
                   (defaults to 'capability_matrices' — sits alongside the md)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _members_table(members: list[dict[str, Any]]) -> str:
    rows = []
    for m in members:
        file = m.get("file") or "?"
        qn = m.get("qualified_name") or m.get("name") or "?"
        line = m.get("line") or ""
        size = m.get("size") or ""
        callers = m.get("caller_count")
        callers_txt = str(callers) if isinstance(callers, int) and callers >= 0 else "?"
        rows.append(f"- `{file}:{line}` — `{qn}` ({size} lines, {callers_txt} callers)")
    return "\n".join(rows)


def _fmt_finding(f: dict[str, Any], matrices_dir: str) -> str:
    meta = f.get("rank_meta") or {}
    level = (f.get("level") or "function").upper()
    domains = ", ".join(f.get("domains") or []) or "?"
    shared = f.get("shared_core_description") or "(no description)"
    shape = f.get("consolidation_shape") or "?"
    notes = f.get("notes") or ""
    matrix_rel = f.get("matrix_path") or f"{matrices_dir}/{f['finding_id']}.md"
    tests = ", ".join(f.get("tests_that_guard_this_area") or []) or "(none listed)"

    acc = (f.get("divergence") or {}).get("accidental") or []
    ldg = (f.get("divergence") or {}).get("load_bearing") or []

    lines = [
        f"### {f['finding_id']}: {shared[:80]} [{level}]",
        "",
        "**Members:**",
        _members_table(f.get("members") or []),
        "",
        f"**Domain(s):** {domains}   **Multiplicity:** {f.get('multiplicity', len(f.get('members') or []))}",
        f"**Priority:** {meta.get('priority', '?')}   **Tier:** {meta.get('tier', '?')}",
        f"**Risk:** {meta.get('maintenance_risk', '?')} × level {meta.get('level_multiplier', '?')}   "
        f"**Shared lines:** {meta.get('shared_lines', '?')}   **Migration cost:** {meta.get('migration_cost', '?')}",
        "",
        f"**Shared core:** {shared}",
        "",
        f"**Accidental divergence:** {'; '.join(acc) if acc else '(none noted)'}",
        f"**Load-bearing divergence:** {'; '.join(ldg) if ldg else '(none noted)'}",
        "",
        f"**Consolidation shape:** `{shape}`",
        f"**Tests that guard this area:** {tests}",
        "",
        f"**Notes:** {notes}",
        "",
        f"**Capability matrix:** `{matrix_rel}`",
        f"**Recommended next step:** `/fix-workflow semantic:{f['finding_id']}`",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _fmt_nonconfirmed(title: str, findings: list[dict[str, Any]]) -> str:
    if not findings:
        return ""
    out = [f"## {title}\n"]
    for r in findings:
        fid = r.get("finding_id", "?")
        status = r.get("investigation_status", "?")
        reason = r.get("reason_code", "?")
        notes = r.get("notes", "")
        out.append(f"- **{fid}** ({status}, `{reason}`): {notes}")
    out.append("")
    return "\n".join(out)


def render(
    ranked: dict[str, Any], scan_id: str, matrices_dir: str
) -> tuple[str, dict[str, Any]]:
    findings = ranked.get("findings") or []
    uncertain = ranked.get("uncertain") or []
    rejected = ranked.get("rejected") or []
    tier_counts = ranked.get("tier_counts") or {"P0": 0, "P1": 0, "P2": 0}

    by_tier: dict[str, list[dict[str, Any]]] = {"P0": [], "P1": [], "P2": []}
    for f in findings:
        by_tier[(f.get("rank_meta") or {}).get("tier", "P2")].append(f)

    md_parts: list[str] = [
        f"# Semantic-duplication triage — {scan_id}",
        "",
        f"**Confirmed findings:** {len(findings)}   "
        f"**P0:** {tier_counts['P0']}   **P1:** {tier_counts['P1']}   **P2:** {tier_counts['P2']}   "
        f"**Uncertain:** {len(uncertain)}   **Rejected:** {len(rejected)}",
        "",
    ]

    for tier in ("P0", "P1", "P2"):
        bucket = by_tier[tier]
        if not bucket:
            continue
        md_parts.append(f"## {tier} — {len(bucket)} findings\n")
        for f in bucket:
            md_parts.append(_fmt_finding(f, matrices_dir))

    md_parts.append(_fmt_nonconfirmed("Uncertain candidates", uncertain))
    md_parts.append(_fmt_nonconfirmed("Rejected candidates", rejected))

    md = "\n".join(md_parts)

    # Machine-readable findings.json
    findings_json = {
        "scan_id": scan_id,
        "skill": "find-semantic-duplication",
        "tier_counts": tier_counts,
        "findings": [
            {
                "id": f["finding_id"],
                "level": f.get("level"),
                "domains": f.get("domains"),
                "multiplicity": f.get("multiplicity"),
                "members": f.get("members"),
                "shared_core_description": f.get("shared_core_description"),
                "consolidation_shape": f.get("consolidation_shape"),
                "priority": (f.get("rank_meta") or {}).get("priority"),
                "tier": (f.get("rank_meta") or {}).get("tier"),
                "matrix_path": f.get("matrix_path"),
                "tests_that_guard_this_area": f.get("tests_that_guard_this_area"),
            }
            for f in findings
        ],
    }
    return md, findings_json


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output-md", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--scan-id", required=True)
    p.add_argument("--matrices-dir", default="capability_matrices")
    args = p.parse_args()

    try:
        ranked = json.loads(args.input.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[report] ERROR reading {args.input}: {e}", file=sys.stderr)
        return 2

    md, findings_json = render(ranked, args.scan_id, args.matrices_dir)
    args.output_md.write_text(md)
    args.output_json.write_text(json.dumps(findings_json, indent=2))
    print(f"[report] wrote {args.output_md} ({len(findings_json['findings'])} findings)")
    print(f"[report] wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
