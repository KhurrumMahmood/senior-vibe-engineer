---
name: map-product-workflow
description: Map a user-visible product workflow across routes, views, templates, JavaScript, docs, status providers, and compatibility redirects. Produces `.claude/docs/workflows/<name>.md`. MAP skill for topology-level quality.
argument-hint: "<workflow-name>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: map
best_for: |
  A user-visible product workflow that is easy to understand in the
  UI but hard to locate in code — spans routes, views, templates,
  JavaScript, docs, status providers, and compatibility redirects.
  Produces `.claude/docs/workflows/<name>.md` as the topology map.
not_for: |
  Single-subsystem inventory (use /map-subsystem). Behavioral
  annotation of a known file (use /explain-code). Detection of
  workflow-step duplication (use /find-workflow-duplication).
language: python
framework: django
---

# /map-product-workflow

You are the orchestrator for a product-topology MAP skill. Use this
when a user-visible workflow is easy to understand in the UI but hard
to locate in code.

## How success is judged

- The generator prints two real artifact lines: `wrote
  .claude/docs/workflows/<name>.md` and `wrote
  reports/product-topology/<scan-id>/<name>.json`. Paste those lines in
  the handoff.
- The Markdown map includes a `Descriptor Scope` section with counts for
  workflow steps, target patterns, UI template patterns, and UI script
  patterns.
- When `.engineering/docs/product-workflows.md` is absent or declares no
  patterns, the map honestly says it is expected to be mostly empty.
  An empty map in this repo is not a product topology verdict; it is a
  descriptor-absent result.
- The JSON scratch artifact carries the same descriptor-scope counts, so
  follow-on SUSPECT skills can tell the difference between "no workflow
  drift" and "no workflow was declared."
Write toward these gates from Stage 0.

Grade only by the generated Markdown, JSON, and pasted command output.
Do not assert a route/template/JS relationship unless it appears in one
of those artifacts.

## Scope

- Workflow name: any label you pass. Its shape (steps, route shape, UI
  template/script globs) is host-authored in
  `.engineering/docs/product-workflows.md`; with no descriptor the map is
  mostly empty rather than assuming a project's layout.
- Output: `.claude/docs/workflows/<name>.md`.
- Scratch JSON: `reports/product-topology/<scan-id>/<name>.json`.
- Python: `.venv/bin/python`; scripts are stdlib-only.
- No production code edits.

## Pipeline

```bash
SCAN_ID="workflow-map-$(date -u +%Y%m%d-%H%M%S)"
.venv/bin/python .claude/skills/map-product-workflow/scripts/generate.py \
  <workflow-name> \
  --scan-id "$SCAN_ID"
```

The map inventories:

- descriptor-scope counts and whether the workflow was actually
  declared,
- workflow steps and canonical route names,
- page routes and site-scoped API routes,
- view-to-template render ownership,
- template-injected `window.*` boot globals and JS reads,
- JS modules participating in the workflow,
- status-provider candidates,
- redirects and route mentions in docs.

## When To Use

- Start of a new product area: before code spreads across routes,
  templates, JS, and services.
- Inheriting a large project: before local smell scans, so each file is
  read in product context.
- After major work: refresh the map, then run the targeted SUSPECT
  skills for drift.

## Decision Points

- **Descriptor scope count is zero:** stop after producing the map and
  tell the user the host has not declared a workflow descriptor. Do not
  route to drift scanners as if the empty tables proved the workflow is
  clean.
- **Descriptor scope exists but expected routes/templates are missing:**
  report the missing artifacts from the map and route to the relevant
  SUSPECT skill below.
- **The workflow name is only a label:** do not fuzzy-match code paths
  from the name. The descriptor defines scan scope; the name only labels
  the output files.

## Next Skills

- Route ownership unclear: `/find-route-sprawl`.
- Step knowledge repeated: `/find-workflow-duplication`.
- Template/JS globals implicit: `/find-frontend-contract-drift`.
- Docs disagree with routes: `/find-doc-route-drift`.
- Registry shape is ready: `/extract-workflow-registry`.

## When things go sideways

| Symptom | Action |
|---|---|
| `.engineering/docs/product-workflows.md` is absent | Generate the mostly-empty map, paste the `wrote ...` lines, and state that no host workflow was declared |
| Descriptor exists but has malformed `## Steps` rows | The parser skips malformed rows; report the zero or low step count and tell the user to fix the descriptor before trusting the map |
| Output path cannot be written | Stop and report the exact path/write error; do not claim the map exists |
| JSON scratch artifact is missing after Markdown writes | Treat the run as incomplete; re-run once, then report the missing JSON if it persists |
| The workflow name implies a product area but descriptor scope is zero | Do not infer from the name; ask for or create the descriptor in a separate authorized task |

## Replay case

After material edits to this skill or its script, prove both the
descriptor-absent path and artifact writes:

```bash
.venv/bin/python .claude/skills/map-product-workflow/scripts/generate.py \
  sample-workflow \
  --scan-id replay-map-product-workflow \
  --output /tmp/map-product-workflow.md \
  --json-output /tmp/map-product-workflow.json \
  --skip-effectiveness-log
```

The expected output is exactly two `wrote ...` lines. Inspect the
Markdown `Descriptor Scope` table before treating the map as product
evidence.
