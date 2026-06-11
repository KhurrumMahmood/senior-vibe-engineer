#!/usr/bin/env python3
"""Export a counts-only evidence attestation from a host project (ADR 0035).

Run INSIDE a host checkout that has the skill ecosystem installed. Walks the
host's local evidence surfaces and emits a YAML attestation of per-skill usage —
**counts, dates, and booleans only**: no code, no paths, no commit SHAs, no file
contents. The output is committed in the core repo under
`.claude/contracts/provenance/attestations.yaml`, keyed by the host's public
alias, so contracts can claim `dogfood_kind: host-attested` against a durable,
reviewable record instead of evidence stranded in a private repo.

Surfaces read (all optional — absent surfaces contribute zeros):
  .claude/skill-use/log.jsonl            per-skill invocation counts + date range
  reports/_meta/effectiveness.jsonl      per-skill scan records + findings totals
  reports/<skill>/scan-*/                per-skill scan-directory counts
  .claude/skills/<skill>/knowledge/learnings.md   tuning-knowledge marker
  ai-docs/{specs,plans}/                 host-level artifact counts
  .claude/ideas/log.jsonl                host-level ledger record count

Usage (from the host root):
  python3 /path/to/core/scripts/host_attest.py --alias host-a \\
      --attested-by "<name>" --out attestation.yaml

Stdlib-only; read-only against the host.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records


def _date_of(rec: dict) -> str | None:
    for key in ("ts", "timestamp", "event_at", "created_at", "date"):
        v = rec.get(key)
        if isinstance(v, str) and len(v) >= 10:
            return v[:10]
    return None


def collect(host: Path, extra_roots: list[Path] | None = None) -> dict:
    """Merge evidence across the host root and any worktree roots, deduplicated.

    Worktrees branched from the same state carry copies of the same baseline
    logs, so records are deduplicated — effectiveness by (skill, scan_id),
    skill-use by the full canonical record — and scan dirs by their
    timestamped names. Counts are unions, never sums of copies.
    """
    roots = [host] + [r for r in (extra_roots or []) if r.is_dir()]
    skills_root = host / ".claude" / "skills"
    skill_names = sorted(
        p.name for p in skills_root.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    ) if skills_root.is_dir() else []

    use_records: list[dict] = []
    seen_use: set[str] = set()
    eff_records: list[dict] = []
    seen_eff: set = set()
    for root in roots:
        for rec in _read_jsonl(root / ".claude" / "skill-use" / "log.jsonl"):
            key = json.dumps(rec, sort_keys=True)
            if key not in seen_use:
                seen_use.add(key)
                use_records.append(rec)
        for rec in _read_jsonl(root / "reports" / "_meta" / "effectiveness.jsonl"):
            key = (rec.get("skill"), rec.get("scan_id")) if rec.get("scan_id") \
                else json.dumps(rec, sort_keys=True)
            if key not in seen_eff:
                seen_eff.add(key)
                eff_records.append(rec)

    per_skill: dict[str, dict] = {}
    for name in skill_names:
        uses = [r for r in use_records if r.get("skill") == name]
        effs = [r for r in eff_records if r.get("skill") == name]
        dates = sorted(d for d in (_date_of(r) for r in uses + effs) if d)
        scan_names: set[str] = set()
        for root in roots:
            rdir = root / "reports" / name
            if rdir.is_dir():
                scan_names.update(p.name for p in rdir.glob("scan-*") if p.is_dir())
        scan_dirs = len(scan_names)
        learnings = any(
            (root / ".claude" / "skills" / name / "knowledge" / "learnings.md").is_file()
            for root in roots
        )
        row = {
            "invocations": len(uses),
            "effectiveness_records": len(effs),
            "findings_total": sum(
                r.get("findings_total", 0) for r in effs
                if isinstance(r.get("findings_total"), int)
            ),
            "scan_dirs": scan_dirs,
            "learnings_file": learnings,
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
        }
        if any((row["invocations"], row["effectiveness_records"], row["scan_dirs"], learnings)):
            per_skill[name] = row

    return {
        "skills_installed": len(skill_names),
        "skills_with_evidence": len(per_skill),
        "skill_use_records_total": len(use_records),
        "effectiveness_records_total": len(eff_records),
        "ideas_ledger_records": len(_read_jsonl(host / ".claude" / "ideas" / "log.jsonl")),
        "specs": sum(1 for p in (host / "ai-docs" / "specs").glob("*.md")
                     if p.name != "README.md") if (host / "ai-docs" / "specs").is_dir() else 0,
        "plans": sum(1 for p in (host / "ai-docs" / "plans").glob("*.md")
                     if p.name != "README.md") if (host / "ai-docs" / "plans").is_dir() else 0,
        "per_skill": per_skill,
    }


def emit_yaml(alias: str, attested_by: str, data: dict) -> str:
    today = _dt.date.today().isoformat()
    lines = [
        "# AUTO-GENERATED by scripts/host_attest.py (ADR 0035) — counts-only evidence",
        "# attestation exported from a host checkout. No code, paths, or SHAs. The",
        "# alias->identity mapping lives OUTSIDE this repository.",
        "schema_version: 1",
        "hosts:",
        f"  {alias}:",
        f"    attested_by: {json.dumps(attested_by)}",
        f"    attested_on: \"{today}\"",
    ]
    for key in ("skills_installed", "skills_with_evidence", "skill_use_records_total",
                "effectiveness_records_total", "ideas_ledger_records", "specs", "plans"):
        lines.append(f"    {key}: {data[key]}")
    lines.append("    per_skill:")
    for name, row in data["per_skill"].items():
        lines.append(f"      {name}:")
        for k, v in row.items():
            lines.append(f"        {k}: {json.dumps(v)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Counts-only host evidence attestation (ADR 0035).")
    ap.add_argument("--host-root", type=Path, default=Path("."),
                    help="Host checkout root (default: cwd)")
    ap.add_argument("--extra-root", type=Path, action="append", default=[],
                    help="Additional checkout/worktree root to merge (repeatable); "
                         "records are deduplicated, never double-counted")
    ap.add_argument("--alias", required=True,
                    help="The host's PUBLIC alias (e.g. host-a) — never its real name")
    ap.add_argument("--attested-by", required=True,
                    help="Human attesting the export (name or handle)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output path (default: stdout)")
    args = ap.parse_args(argv)

    host = args.host_root.resolve()
    if not (host / ".claude" / "skills").is_dir():
        print(f"error: {host} does not look like a host with the ecosystem installed "
              "(no .claude/skills/)", file=sys.stderr)
        return 2

    text = emit_yaml(args.alias, args.attested_by,
                     collect(host, [p.resolve() for p in args.extra_root]))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
