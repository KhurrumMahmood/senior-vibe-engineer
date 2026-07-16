---
name: find-perimeter-gaps
description: Audit every canonical host-profile root × language cell and count coverage only from installed, registry-compatible detectors whose hashed scan implementation and support fixture execute successfully. Use during host adaptation, whole-codebase audits, or detector changes; stale or missing evidence becomes a visible gap, and accepted exclusions require reasons. Detection-only; never edits code.
argument-hint: "[--project-root <path>] [--host-profile <json>] [--min-loc 3000] [--accept root:language=reason]"
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
   a recorded decision (`--accept root:language=reason`), not an emergent
   property of detector globs.
2. **Coverage claims must be executable.** In host-profile mode a declaration
   counts only when the installed skill's capability contract, registry
   version, file hashes, tool versions, platform, fixture command, and exact
   scan implementation all validate and execute. `language: any` never means
   "scans everything." See ADRs 0032 and 0038.
3. **LOC is the trigger, judgment is the verdict.** The script flags
   cells above `--min-loc`; whether a gap warrants a new adapter, an
   accepted-blind-spot entry, or a host-side lint is your synthesis,
   not the script's.

## How success is judged

- The run creates a fresh scan dir under
  `reports/find-perimeter-gaps/<scan-id>/` with `report.md` and
  `perimeter.json`.
- The `scan.py` exit code is honored; `--fail-on-gap` exit 1 is an
  intentional failing verdict, not a crash.
- Handoff identifiers are valid: every `gaps` row in `perimeter.json`
  is also present in `cells` with the same `root` and `language`.
- No silent drops: every significant matrix row printed in `report.md`
  is represented in `perimeter.json` `cells`, and every PERIMETER GAPS
  row appears in `gaps`.
- A zero-gap run is successful only when artifacts exist and `report.md`
  says `No perimeter gaps above threshold`.
- Machine output retains rejected coverage candidates and their evidence
  reasons, profile exclusions, and reason-bearing accepted exclusions.

## Pipeline

### Stage 1 — Run the scan

```bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-.}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-perimeter-gaps/$SCAN_ID"
EXTRA_ARGS=()
# Optional overrides:
# EXTRA_ARGS+=(--skills-root "$PROJECT_ROOT/.claude/skills")
# EXTRA_ARGS+=(--min-loc 3000)
# EXTRA_ARGS+=(--accept 'generated:templates=generated build output')
# EXTRA_ARGS+=(--skip-root data)
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-perimeter-gaps/scripts/scan.py \
  --project-root "$PROJECT_ROOT" \
  --host-profile .engineering/project/host-profile.json \
  "${EXTRA_ARGS[@]}" \
  --output "$REPORT_DIR/perimeter.json" \
  > "$REPORT_DIR/report.md"
```

Deterministic, stdlib-only. Data-like files (> `--max-file-loc`, default
10K lines) and artifact trees (media, fixtures, snapshots, crawled…) are
skipped automatically.

### Stage 2 — Classify each gap

For every PERIMETER GAPS row, classify:

- **data, not code** → re-run with `--skip-root` or a reason-bearing
  `--accept root:language=reason`; retain that decision in both outputs.
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

## Replay case

When `scripts/scan.py` changes, replay a disposable host with one
executable-evidence TypeScript detector and a significant TypeScript root.
Expected result: the valid detector covers the cell; changing its attested
script makes the same cell a gap; a reason-bearing acceptance removes it from
`gaps` while remaining visible in JSON.

## When things go sideways

| Case | Signal | Response |
|---|---|---|
| Target absent | `scan.py` prints `[perimeter] ERROR: ... is not a directory` and exits 2. | Stop; report the bad `--project-root` and rerun against a real host repo. |
| Zero findings | `report.md` says `No perimeter gaps above threshold` and `perimeter.json` has an empty `gaps` list. | Treat as clean only after confirming `--skills-root`, `--min-loc`, `--skip-root`, and `--accept` match the intended audit. |
| Script non-zero exit | Exit 1 with `--fail-on-gap`, or exit 2 for usage/target errors. | For exit 1, hand off the PERIMETER GAPS rows; for exit 2, fix invocation before classifying gaps. |

## Cross-references

- ADR 0032 — language-general detection (why this skill exists).
- `_common/portability-roadmap.md` — the language/framework layering.
- `/check-ecosystem-consistency` — internal ecosystem audit (sibling).
- `/adapt-project` — host adoption flow that should run this skill.
