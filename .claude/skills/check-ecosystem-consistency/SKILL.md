---
name: check-ecosystem-consistency
description: Diff-aware ecosystem consistency audit for engineering-skills. Snapshots skills, shape routing references, docs skill-count claims, and catalog coverage; compares with the last reviewed state so significant skill changes surface follow-up obligations such as updating /which-shape.
argument-hint: "[--changed-from REF|--staged] [--update-state]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Running after significant changes to the skill ecosystem: adding or
  removing skills, changing skill contracts, editing /which-shape
  shapes.yml, or updating the README/ONBOARDING/catalog surfaces that
  describe the ecosystem. Especially useful before handoff or commit.
not_for: |
  Choosing the next operating loop for product work (use /which-shape).
  Tactical skill lookup (use /which-skill). Proving a specific scanner
  is correct (run that scanner's focused tests). Blocking every tiny
  docs-only edit; this is an advisory consistency check.
language: any
framework: any
lanes: [ecosystem-governance]
stage: verify
entrypoint: false
consumes: [skill_registry, shape_registry, docs, previous_ecosystem_state]
produces: [ecosystem_consistency_report, ecosystem_state]
evidence_required: [report, state_snapshot, findings]
risk_triggers: [new-skill, removed-skill, shape-registry-drift, stale-catalog, stale-count]
max_overhead: "Run one snapshot/diff pass; update the stored state only after the findings have been reviewed."
---

# /check-ecosystem-consistency

Audit whether the skill ecosystem still agrees with itself after a
material change.

This skill exists because new skills create coordination obligations:
the skill may need catalogue coverage, count updates, tests, and
possibly a `/which-shape` registry update. Not every new skill belongs
in a shape, but every new skill should be consciously reviewed against
the shape registry.

## How success is judged

- The script exit code is honored. If
  `.claude/skills/check-ecosystem-consistency/scripts/check.py` exits
  nonzero, report the failure and do not call the ecosystem consistent.
- `report.md`, `state.json`, `findings.json`, and `evidence.json` are
  written under `reports/check-ecosystem-consistency/scan-<UTC>/`
  (`previous-state.json` is included when a baseline exists).
- Every `findings.json` row is relayed complete in the user-facing
  findings table: `pattern`, `severity`, `file`, `summary`, and
  `recommendation`.
- `--update-state` is run only after the findings have been reviewed and
  any needed catalogue or `/which-shape` updates have landed.

## Forms

```bash
/check-ecosystem-consistency
/check-ecosystem-consistency --changed-from main
/check-ecosystem-consistency --staged
/check-ecosystem-consistency --update-state
```

Script form:

```bash
.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py
```

Execution contract:

| Form | Script command | Contract |
|---|---|---|
| `/check-ecosystem-consistency` | `.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py` | Snapshot the full ecosystem, compare to `.claude/ecosystem/last-state.json`, and write a timestamped report |
| `/check-ecosystem-consistency --changed-from REF` | `.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py --changed-from REF` | Include `git diff --name-only REF` paths in `report.md`; the ecosystem snapshot is still full, not limited to those paths |
| `/check-ecosystem-consistency --staged` | `.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py --staged` | Include staged `git diff --name-only --cached` paths in `report.md`; the ecosystem snapshot is still full |
| `/check-ecosystem-consistency --update-state` | `.venv/bin/python .claude/skills/check-ecosystem-consistency/scripts/check.py --update-state` | Write `.claude/ecosystem/last-state.json` only after the preceding report's findings were reviewed and required follow-up landed |

## What It Checks

- skill inventory and frontmatter snapshot;
- added, removed, or changed skills since the last reviewed state;
- `/which-shape/shapes.yml` schema and referenced skill slugs;
- new skills that should be reviewed for shape-router impact;
- README/ONBOARDING skill-count claims;
- new skills missing obvious `.claude/docs/skill-catalog.md` coverage.

## State And Reports

Reports are written under:

```text
reports/check-ecosystem-consistency/scan-<UTC>/
```

The scan contains `report.md`, `state.json`, `previous-state.json` when
available, `findings.json`, and `evidence.json`.

The durable baseline lives at:

```text
.claude/ecosystem/last-state.json
```

The script reads that state by default, but it only writes it when
`--update-state` is passed. Use `--update-state` after the consistency
findings have been reviewed and any needed catalogue or `/which-shape`
updates have landed.

## When things go sideways

| Symptom | Action |
|---|---|
| `--changed-from REF` names a bad git ref and `Changed Paths` is empty unexpectedly | Re-run `git diff --name-only REF` to verify the ref, then rerun with a valid `REF`; do not treat an empty changed-path list as proof nothing changed |
| Shape registry schema error appears in `findings.json` as `shape_registry_schema_error` | Honor the script's nonzero exit, fix `.claude/skills/which-shape/shapes.yml`, and rerun before updating state |
| Report or state write fails | State which artifact failed to write; do not claim `report.md`, `state.json`, `findings.json`, `evidence.json`, or `.claude/ecosystem/last-state.json` landed |
| Baseline is missing and `baseline_missing` appears in `findings.json` | Review the first report as the baseline, then rerun with `--update-state` only after accepting that snapshot |

## Relationship To `/which-shape`

When a skill is added or materially repurposed, review
`.claude/skills/which-shape/shapes.yml`. Add the skill to a shape only
when it changes a durable problem-solving loop. If the skill is purely
tactical, leaving it out is fine; updating the ecosystem state records
that the omission was reviewed.
