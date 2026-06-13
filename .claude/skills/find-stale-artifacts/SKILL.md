---
name: find-stale-artifacts
description: Detect stale working artifacts — abandoned plans, proposed plans untouched past a soft staleness budget, aged `scan-*` report directories, and orphan top-level report files. Defends attention against the accumulation of working artifacts that outlive the work. SUSPECT skill, sibling to /find-dormant for non-code surfaces.
argument-hint: "[--root . --max-plan-age-days 60 --max-scan-age-days 30 --max-toplevel-age-days 30]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Periodic (monthly / quarterly) hygiene of working-artifact directories
  that accumulate cruft as side effects of active work — `ai-docs/plans/`,
  `ai-docs/specs/`, and `reports/`. Surfaces deletion candidates with
  evidence: abandoned plans, plans untouched past a soft staleness budget,
  aged `reports/<skill>/scan-<TS>/` directories not pointed at by
  `latest`, and orphan top-level `reports/*.md` files. Pairs with manual
  delete or a thin executor; never deletes unilaterally.
not_for: |
  Code-side dead-code detection (use /find-dormant).
  Agent-rules surface drift in `.claude/CLAUDE.md` or `.claude/docs/`
  (use /find-rule-surface-drift) — that one defends ADR 0005's tiered
  storage convention.
  Decision-registry drift in `ai-docs/decisions/` (use /audit-decisions).
  Acting on findings — manual delete or a thin executor; the skill is
  read-only.
language: python
framework: any
scans: [markdown]
---

# /find-stale-artifacts

You are the orchestrator for a SUSPECT skill that audits working-artifact
directories for accumulated cruft. Sibling to `/find-dormant` (which
covers code) — this one covers plans, specs, and report scan dirs.

## Why this exists

Skills like `/find-*`, `/triage-debt`, and `/audit-decisions` write
per-run output under `reports/<skill>/scan-<TS>/`. Plans and specs land
under `ai-docs/plans/` and `ai-docs/specs/` and pick up status frontmatter
(`abandoned`, `proposed`, `complete`, etc.) over their lifecycle. Without
a periodic forcing function, both surfaces accumulate:

- Plans that were `abandoned` months ago and now just sit there.
- Plans frozen at `proposed` because the work was deferred and never
  picked back up.
- Scan directories from old runs that nobody will ever read again.
- Top-level `reports/*.md` notes (merge-time WIP, ad-hoc audits) that
  outlive their relevance.

The discipline this skill enforces is **status frontmatter + age +
reference-graph** — three signals across a small fixed list of artifact
directories. If a candidate doesn't fit those three signals, it doesn't
belong in this skill.

## Scope

- Default project root: `.` (the current working directory).
- Default plans dir: `<root>/ai-docs/plans/`.
- Default reports dir: `<root>/reports/`.
- Output: `reports/find-stale-artifacts/<scan-id>/`.
- No deletes; detection only.

## How success is judged

- The run creates a fresh scan dir under
  `reports/find-stale-artifacts/<scan-id>/` with `detections.jsonl`,
  `report.md`, and `findings.json`.
- Each command's exit code is honored; stop on non-zero and report the
  failing command instead of rendering stale detections.
- Handoff identifiers are valid: every `findings.json` record uses one of
  the `pattern` names in Findings and carries `file` / `lineno` evidence.
- No silent drops: the JSONL record count matches
  `findings.summary.findings_total` and the `findings` array length.
- A zero-finding run is successful only when those artifacts exist and
  `report.md` says `Findings: 0`.

## Pipeline

```bash
set -euo pipefail
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-stale-artifacts/$SCAN_ID"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-stale-artifacts/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-stale-artifacts/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target "ai-docs/plans+reports/"

# Update the latest symlink
ln -snf "$SCAN_ID" "reports/find-stale-artifacts/latest"
```

## Findings

- `abandoned_plan`: an `ai-docs/plans/*.md` declares `status: abandoned`.
  Always fires. Recommendation: delete the file (the abandonment is
  recorded in git history; the file itself is no longer load-bearing). If
  the work paused rather than terminated, capture the pointer in the
  relevant backlog and delete the plan anyway — empty templates with
  status notes are noise.

- `stale_plan`: an `ai-docs/plans/*.md` is in an "in-flight" status
  (`draft`, `proposed`, `scoped`, `impacted`, `architected`) but its
  frontmatter `date:` is older than the soft budget (default 60 days).
  Recommendation: refresh, promote, or abandon. A plan that sits in
  `proposed` for two months without progress is signal that the work
  was either silently shelved or silently completed via a different
  surface.

- `aged_scan_dir`: a `reports/<skill>/scan-<TS>/` directory is older than
  the soft budget (default 30 days) AND is not the target of the
  sibling `latest` symlink. Recommendation: delete unless the scan is
  referenced from a tracked artifact (a spec, plan, ADR, or BACKLOG
  entry). The skill emits the grep'd reference list in the finding so
  the human can confirm.

- `orphan_toplevel_report`: a `*.md` at the top level of `reports/`
  (not under any subdirectory) hasn't had a git commit touch it in N
  days (default 30) AND isn't in the known-active list (`BACKLOG.md`,
  `skill-ecosystem-backlog.md`). Recommendation: confirm it's still
  working state or delete. Top-level files have no skill-imposed
  rotation; they accumulate manually until someone notices.

## Calibration

The three thresholds are soft budgets:

- `--max-plan-age-days 60`: plans should move through their workflow in
  weeks, not months. A plan parked at `proposed` for >60 days is almost
  certainly stale.
- `--max-scan-age-days 30`: scan directories are per-run audit trails;
  the most recent run is what `/fix-workflow` and `/triage-debt` read.
  Older scans are kept for archaeology, not active reference. 30 days
  is generous — drop to 14 if `reports/` is growing too fast.
- `--max-toplevel-age-days 30`: top-level reports are working notes by
  convention; if a human hasn't touched one in a month, it's almost
  certainly cruft.

## Replay case

When `scripts/detect.py` changes, replay a disposable project with one
`abandoned_plan`, one `stale_plan`, one old non-latest `aged_scan_dir`,
and one old `orphan_toplevel_report`. Use low age thresholds if needed.
The expected `findings.json` buckets are those four pattern names, and the
record count must match `detections.jsonl`.

## When things go sideways

| Case | Signal | Response |
|---|---|---|
| Target absent | `ai-docs/plans/` or `reports/` is missing under `--root`. | Let the detector's zero-finding output stand if it exits 0; name the absent surface in the report. |
| Zero findings | `detections.jsonl` is empty and `report.md` says `Findings: 0`. | Treat as clean only after confirming the intended `--root`, plans subdir, and reports subdir were used. |
| Script non-zero exit | Any command exits non-zero. | Stop the pipeline, paste the command and stderr, and do not run `report.py` against stale detections. |

## Next Skills

- Manual delete is the usual response. Stage candidates with
  `git rm <plan>` for tracked plans, or `rm -r <scan-dir>` for
  gitignored scan dirs.
- `/decide` if the audit reveals a tradeoff worth recording (e.g. "we
  keep accepting `stale_plan` for our skill-ecosystem work — extend the
  budget or add a `paused` status").
- `/prevent-regression` if a particular drift class recurs often enough
  to justify a CI check (e.g. "no plan stays at `proposed` for >90
  days").

## Notes for the orchestrator

- **Stage 1 skeleton.** The four bands above cover the cases that
  motivated the skill (the canonical-findings-ledger plan, the merge-
  note-wip-refactor.md file, the 56 scan dirs in `reports/`). Future
  bands worth considering only with real evidence:
  - `complete_spec_aged`: specs with `status: complete` / `DONE`
    older than N days. Skipped because completed specs are the audit
    trail and have lower volume.
  - `proposed_decision_with_abandoned_plan`: belongs to
    `/audit-decisions`, not here.
  - `dead_scan_reference`: a tracked file references a scan dir that
    no longer exists. Add when an actual case appears.

- **Age signal preference.** For plans, use the frontmatter `date:`
  field — immune to checkout resets and matches how the lifecycle is
  documented. For top-level reports without frontmatter, use
  `git log -1 --format=%ct` (last commit timestamp). For scan dirs,
  parse the directory name (`scan-YYYYMMDD-HHMMSS`) — the timestamp is
  in the name itself.

- **Reference-graph check.** For `aged_scan_dir`, run `grep -rl
  --exclude-dir=reports` for the scan-id across the repo. A scan dir
  referenced from a tracked plan/spec/ADR/BACKLOG line should NOT fire
  — those references are the audit trail the scan exists to support.

- **Latest symlink.** Skip the directory the sibling `latest` symlink
  points at, regardless of age. The most recent scan is always
  load-bearing.

- **Known-active top-level list.** `BACKLOG.md` and
  `skill-ecosystem-backlog.md` are the working backlog files. Any
  `reports/<file>.md` not in this list is an `orphan_toplevel_report`
  candidate. If the list grows, lift it into a config file.
