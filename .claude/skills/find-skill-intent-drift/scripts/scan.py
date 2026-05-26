#!/usr/bin/env python3
"""find-skill-intent-drift — advisory SUSPECT guard for skill intent contracts.

Compares per-skill intent contracts (.claude/contracts/skills/<name>.yaml, schema v2)
against the actual skills (.claude/skills/<name>/), flagging drift in four bands:

  missing    skill has no intent contract              (intent never captured)
  orphaned   contract exists, skill does not            (intent for a deleted skill)
  malformed  contract missing required schema-v2 keys   (intent capture incomplete)
  stale      SKILL.md changed in commits AFTER the       (intent may have drifted
             contract's last commit                       without the contract updating)

This is the "no easy reversion of intent" guard: it cannot block an edit, but it makes
silent intent erosion VISIBLE. Advisory by default (always exits 0, prints findings);
--strict exits 1 on any finding (for CI). Side effect: regenerates
<contracts-dir>/_index.yaml.

Portable: every location is a flag defaulting to the conventional repo layout, so the
same script runs unchanged against a separate engineering-skills (ES2) checkout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

import yaml

REQUIRED = ["skill", "job", "problem_class", "intent", "solves", "born",
            "dogfood_kind", "provenance_confidence"]
BORN_KEYS = ["commit", "date"]
CONF_AXES = ["textual", "structural", "temporal", "dogfood"]
DOGFOOD_KINDS = {"subsystem-refactor", "self-installed-guard", "fixture-pair", "none-found"}
CONF_LEVELS = {"high", "med", "low"}


def git_last_epoch(path: Path) -> int | None:
    """Author/commit time of the last commit touching `path`, or None if untracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.CalledProcessError, ValueError):
        return None


def load_contract(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}, None
    except (yaml.YAMLError, OSError) as e:
        return None, f"load error: {e}"


def check_malformed(data: dict) -> list[str]:
    problems: list[str] = []
    for k in REQUIRED:
        if k not in data or data[k] in (None, "", []):
            problems.append(f"missing/empty `{k}`")
    born = data.get("born") or {}
    if isinstance(born, dict):
        for k in BORN_KEYS:
            if not born.get(k):
                problems.append(f"born.{k} empty")
    conf = data.get("provenance_confidence") or {}
    if isinstance(conf, dict):
        for ax in CONF_AXES:
            v = conf.get(ax)
            if v not in CONF_LEVELS:
                problems.append(f"provenance_confidence.{ax}={v!r}")
    dk = data.get("dogfood_kind")
    if dk is not None and dk not in DOGFOOD_KINDS:
        problems.append(f"dogfood_kind={dk!r}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skills-root", default=".claude/skills")
    ap.add_argument("--contracts-dir", default=".claude/contracts/skills")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding (CI)")
    ap.add_argument("--no-index", action="store_true", help="skip _index.yaml regen")
    args = ap.parse_args()

    skills_root = Path(args.skills_root)
    contracts_dir = Path(args.contracts_dir)

    skills = sorted(
        d.name for d in skills_root.iterdir()
        if d.is_dir() and d.name != "_common" and (d / "SKILL.md").exists()
    )
    contracts = {p.stem: p for p in contracts_dir.glob("*.yaml") if not p.name.startswith("_")}

    missing = [s for s in skills if s not in contracts]
    orphaned = sorted(s for s in contracts if s not in skills)

    malformed: dict[str, list[str]] = {}
    stale: list[str] = []
    index_rows: list[dict] = []

    for name in skills:
        cp = contracts.get(name)
        if cp is None:
            continue
        data, err = load_contract(cp)
        if err:
            malformed[name] = [err]
            continue
        probs = check_malformed(data)
        if probs:
            malformed[name] = probs

        c_epoch = git_last_epoch(cp)
        s_epoch = git_last_epoch(skills_root / name / "SKILL.md")
        if c_epoch is None:
            stale_state = "baseline (contract uncommitted)"
        elif s_epoch and s_epoch > c_epoch:
            stale.append(name)
            stale_state = "STALE (SKILL.md newer than contract)"
        else:
            stale_state = "ok"

        conf = data.get("provenance_confidence") or {}
        index_rows.append({
            "skill": name,
            "born": (data.get("born") or {}).get("date"),
            "problem_class": data.get("problem_class"),
            "dogfood_kind": data.get("dogfood_kind"),
            "dogfood_confidence": conf.get("dogfood"),
            "duplication_risks": len(data.get("duplication_risk") or []),
            "stale": stale_state,
        })

    print(f"skills={len(skills)} contracts={len(contracts)}")

    def section(title: str, items: list[str]) -> None:
        print(f"\n[{title}] {len(items)}")
        for it in items:
            print(f"  - {it}")

    section("missing-contract", missing)
    section("orphaned-contract", orphaned)
    section("stale", stale)
    print(f"\n[malformed] {len(malformed)}")
    for n, ps in malformed.items():
        print(f"  - {n}: {'; '.join(ps)}")

    if not args.no_index:
        idx = {
            "_note": "AUTO-GENERATED by find-skill-intent-drift/scripts/scan.py — do not hand-edit.",
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_count": len(index_rows),
            "skills": index_rows,
        }
        out = contracts_dir / "_index.yaml"
        out.write_text(
            yaml.safe_dump(idx, sort_keys=False, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"\nwrote {out} ({len(index_rows)} skills)")

    findings = len(missing) + len(orphaned) + len(stale) + len(malformed)
    print(f"\nTOTAL findings: {findings}")
    if args.strict and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
