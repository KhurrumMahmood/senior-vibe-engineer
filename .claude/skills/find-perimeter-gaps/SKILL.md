---
name: find-perimeter-gaps
description: Audit the quality perimeter — report every (code root × language) cell with significant LOC and the SUSPECT detectors covering it; flag cells no detector covers. The detector fleet scans what it scans; this skill reports the inverse, so blind spots are a visible decision instead of an accident. Detection-only; never edits code. Born from a real incident — 34.6K lines of JavaScript invisible to an ecosystem whose omnibus detector was Python-only (ADR 0032).
argument-hint: "[--project-root <path>] [--min-loc 3000] [--accept root:language]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Adopting the ecosystem into a new host project (run alongside
  /adapt-project); starting any "audit the whole codebase" request;
  after adding or rescoping a detector skill, to confirm the coverage
  matrix changed the way you think it did. The output is a coverage
  matrix plus an explicit PERIMETER GAPS list.
not_for: |
  Finding smells inside covered code (use the find-* detector for that
  language). Auditing the ecosystem's internal consistency
  (/check-ecosystem-consistency). Judging whether a gap is worth
  closing — that's a human/ADR decision; this skill only makes the gap
  visible. Per-file size policing (that is a lint, not a perimeter
  question).
language: any
framework: any
---

# /find-perimeter-gaps

You are the orchestrator for a SUSPECT skill that audits the **detector
fleet itself**: which parts of the host codebase does no structural
detector cover?

## Core beliefs

1. **A blind spot may be accepted, never invisible.** Vendored code,
   crawled data, generated output — fine to skip, but the skip must be
   a recorded decision (`--accept root:language`), not an emergent
   property of detector globs.
2. **Coverage claims must be honest.** A detector covers a language only
   if its frontmatter `scans:` list says so (or its `language:` field
   names that exact language). `language: any` means "portable
   implementation", not "scans everything" — it covers nothing here.
   See ADR 0032.
3. **LOC is the trigger, judgment is the verdict.** The script flags
   cells above `--min-loc`; whether a gap warrants a new adapter, an
   accepted-blind-spot entry, or a host-side lint is your synthesis,
   not the script's.

## Pipeline

### Stage 1 — Run the scan

```bash
python3 .claude/skills/find-perimeter-gaps/scripts/scan.py \
  --project-root <host repo> \
  [--skills-root <host>/.claude/skills] \
  [--min-loc 3000] [--accept sites:templates] [--skip-root data] \
  [--output reports/perimeter/perimeter.json]
```

Deterministic, stdlib-only. Data-like files (> `--max-file-loc`, default
10K lines) and artifact trees (media, fixtures, snapshots, crawled…) are
skipped automatically.

### Stage 2 — Classify each gap

For every PERIMETER GAPS row, classify:

- **data, not code** → re-run with `--skip-root` or `--accept`, and
  record why in the report you hand back.
- **code, detector exists for the language elsewhere** → the detector's
  `scans:` declaration is stale or its walker globs are too narrow; fix
  the declaration or file the scope bug.
- **code, no detector can scan this language** → candidate for a new
  language adapter on an existing structural detector (ADR 0032 rule 1)
  — not a new per-language skill fork.

### Stage 3 — Report

Write the matrix, the gap classifications, and your recommendation per
gap. Do not silently fix anything. If a gap reveals that remediation
would land in a layer with missing substrate (no module system, no
tests), say so explicitly — that is ADR 0032 rule 3 territory and needs
an ADR, not a refactor.

## Cross-references

- ADR 0032 — language-general detection (why this skill exists).
- `_common/portability-roadmap.md` — the language/framework layering.
- `/check-ecosystem-consistency` — internal ecosystem audit (sibling).
- `/adapt-project` — host adoption flow that should run this skill.
