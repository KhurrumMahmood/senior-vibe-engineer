---
name: find-frontend-duplication
description: Detect duplicated UX shells, hand-rolled primitives, and JS helper forks across templates/ and static/js/. Compares Tailwind class chains and JS function definitions against the existing cotton primitive inventory to surface "should be a c-primitive but isn't" candidates. Hands off to /extract-cotton-primitive for proposals.
argument-hint: "[--templates templates --js static/js]"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Hand-rolled UX shells (modal frames, badge styles, alert frames,
  dropdowns, button variants) repeated across templates instead of
  using a cotton primitive. JS helper forks (showToast / escapeHtml /
  siteEndpoint defined in multiple files). Inline CSRF / fetch
  patterns that should funnel through one wrapper. Use after a
  consolidation work-period or before adding a new UI surface.
not_for: |
  Python code duplication (use /find-duplication or
  /find-semantic-duplication). Implicit JS<->template global contracts
  (use /find-frontend-contract-drift). Cross-layer workflow drift
  (use /find-workflow-duplication). UI extraction execution itself
  (use /extract-cotton-primitive).
language: python
framework: django
---

# /find-frontend-duplication

You are the **orchestrator** for a frontend-duplication audit. Drive the
detection scripts, collapse their output into ranked consolidation
candidates, fan out sub-agent investigators on the top candidates, and
produce a triage report. Do **not** read the candidate class chains or
function bodies yourself — that is what the investigator sub-agents are
for.

## Scope

- **Template root:** `templates/` (default).
- **JS root:** `static/js/` (default).
- **Component primitive root:** declared by the project's `component_profile`
  (`.engineering/manifest.json`, `definitions_root` field), read by
  `cotton_inventory.py`. No baked-in path — when no `component_profile` is
  declared (`kind: none`) the inventory is simply empty.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **No code edits.** Read-only audit.
- Project-specific filters and known false positives in
  `knowledge/` and `knowledge/false-positives.md`.

## Pipeline stages

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `.venv/bin/python` and capture stderr
so failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/frontend-duplication/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/frontend-duplication/latest
```

### Stage 1 — Detect (parallel)

**Pre:** target dirs exist. **Post:** the three inventories below are
present and non-empty.

Run all three commands concurrently in one Bash message:

```bash
.venv/bin/python .claude/skills/find-frontend-duplication/scripts/cotton_inventory.py \
  --out "${REPORT_DIR}/cotton-inventory.json"

.venv/bin/python .claude/skills/find-frontend-duplication/scripts/frontend_class_chain_scanner.py \
  --out-dir "${REPORT_DIR}/class-chains"

.venv/bin/python .claude/skills/find-frontend-duplication/scripts/frontend_helper_scanner.py \
  --out "${REPORT_DIR}/helpers.json"
```

### Stage 2 — Collapse

**Pre:** Stage 1 outputs exist. **Post:** `${REPORT_DIR}/candidates.json` —
class-chain buckets and helper findings collapsed into candidate
consolidations, each with a category (`modal-shell`, `pill-shell`,
`alert-shell`, `dropdown-menu`, `csrf-fetch`, `helper-fork`,
`hand-rolled-primitive`) and an existing-primitive lookup.

```bash
.venv/bin/python .claude/skills/find-frontend-duplication/scripts/collapse.py \
  --cotton "${REPORT_DIR}/cotton-inventory.json" \
  --class-chains-raw "${REPORT_DIR}/class-chains/raw.json" \
  --class-chains-norm "${REPORT_DIR}/class-chains/tone-norm.json" \
  --helpers "${REPORT_DIR}/helpers.json" \
  --output "${REPORT_DIR}/candidates.json"
```

### Stage 3 — Rank

**Pre:** `candidates.json`. **Post:** `${REPORT_DIR}/ranked.json` — each
candidate scored by (occurrence_count × file_span × consolidation_value)
and bucketed P0 / P1 / P2.

P0: 20+ occurrences across 5+ files, no existing primitive **or**
existing primitive being bypassed.
P1: 10-19 occurrences across 3+ files.
P2: 3-9 occurrences across 2+ files.

```bash
.venv/bin/python .claude/skills/find-frontend-duplication/scripts/rank.py \
  --input "${REPORT_DIR}/candidates.json" \
  --output "${REPORT_DIR}/ranked.json"
```

### Stage 4 — Investigate (parallel fan-out)

**Pre:** `ranked.json`. **Post:** `${REPORT_DIR}/scout/<candidate_id>.json`
for every investigated candidate; a single
`${REPORT_DIR}/classified.json` aggregating them.

> **Run from the main session.** Stage 4 needs `Agent` dispatch, which
> the runtime only exposes to the top-level session. If this skill is
> invoked from a sub-agent context (e.g. another skill chained it via
> `/which-skill`), Stage 4 will fail to dispatch — surface that as a
> hard error and stop. Do **not** inline-read class chains as a fallback;
> that silently violates the orchestrator-doesn't-read-markup rule.

This is the **only stage where LLM judgment runs**. You (the
orchestrator) do **not** read the class chains, JS function bodies, or
template snippets. You dispatch one sub-agent per candidate (or batch if
there are many). Each sub-agent receives:

- the candidate JSON,
- the prompt template from `agents/investigate.md`,
- paths to `knowledge/*` files,
- an output path it must write to.

Budget: investigate **top 8 by priority** by default. If there are fewer
than 8 candidates, investigate them all. If the user asked for a deeper
scan, raise the limit.

For each candidate, expand the `agents/investigate.md` template
(substitute `{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{output_path}}`) and dispatch with
`subagent_type=general-purpose`. Send all Agent calls in a **single
message** so they run concurrently.

After the sub-agents return, combine their JSON files:

```bash
.venv/bin/python -c "
import json, glob, pathlib
out = {'candidates': []}
for p in sorted(glob.glob('${REPORT_DIR}/scout/*.json')):
    out['candidates'].append(json.loads(pathlib.Path(p).read_text()))
pathlib.Path('${REPORT_DIR}/classified.json').write_text(json.dumps(out, indent=2))
"
```

### Stage 5 — Report

**Pre:** `ranked.json`, `classified.json`. **Post:**
`${REPORT_DIR}/triage.md` and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-frontend-duplication/scripts/report.py \
  --input "${REPORT_DIR}/ranked.json" \
  --classified "${REPORT_DIR}/classified.json" \
  --output-md "${REPORT_DIR}/triage.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}"

# Effectiveness log
python3 scripts/log_effectiveness.py \
  --skill find-frontend-duplication \
  --scan-id "scan-${TS}" \
  --target templates+static/js \
  --findings-total "$(.venv/bin/python -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("candidates", [])))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys,collections; c=collections.Counter(x.get("category","other") for x in json.load(open(sys.argv[1])).get("candidates", [])); print(json.dumps(dict(c)))' "${REPORT_DIR}/findings.json")"
```

### Stage 6 — Summarize

Report to the user in ≤10 lines:

- counts by category (`modal-shell`, `csrf-fetch`, `helper-fork`, ...),
- top 3 candidates by priority (one line each: category, occurrence_count, lead file),
- existing-primitive bypass count (callsites that should adopt an
  existing `<c-...>` but use raw markup),
- path to `${REPORT_DIR}/triage.md` and the `latest` symlink,
- recommended next slash command — usually `/extract-cotton-primitive`
  for the top candidate, or `/prevent-regression` to add a guardrail
  for an already-extracted primitive being bypassed.

The triage report is the source of truth — do not enumerate every
candidate.

## Non-goals

- Executing extractions or migrations (that's
  `/extract-cotton-primitive` for the proposal,
  `/refactor-subsystem` for the migration).
- Detecting Python code duplication (that's `/find-duplication` and
  `/find-semantic-duplication`).
- JS<->template implicit global contracts (that's
  `/find-frontend-contract-drift`).
- Editing files (this is a read-only audit).

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 cotton-inventory empty | No `component_profile` declared (`kind: none`), or its `definitions_root` is unset/missing on disk; check `.engineering/manifest.json` |
| Stage 2 reports 0 candidates | min-tokens / min-count thresholds may be too high — re-run scanners with `--min-count 2 --min-tokens 2` |
| Stage 4 sub-agent recommends "extract" for a single-callsite chain | Re-dispatch citing `knowledge/extraction-thresholds.md` (3+ callsites across 2+ templates) |
| Stage 4 confabulates a non-existent file path | Re-dispatch with stricter "verify each cited file exists by listing it" preamble; skip if it fails twice |
| Class chain bucket has 30+ occurrences but is a Tailwind utility cluster (e.g. `flex items-center justify-between`) | Expected — these are layout primitives, not extractable shells. Mark as `category: layout-utility` and drop from rankings |
| Stage 4 cannot dispatch sub-agents (`Agent` tool unavailable) | You are running as a sub-agent yourself; Stage 4 is main-session only. Stop and surface to the user — do not inline-read markup as a fallback. |

## Repository layout

```
.claude/skills/find-frontend-duplication/
├── SKILL.md                      # this file — orchestrator
├── scripts/
│   ├── cotton_inventory.py             # Stage 1 — cotton primitive inventory
│   ├── frontend_class_chain_scanner.py # Stage 1 — Tailwind class chains
│   ├── frontend_helper_scanner.py      # Stage 1 — JS helper forks
│   ├── collapse.py                     # Stage 2
│   ├── rank.py                         # Stage 3
│   └── report.py                       # Stage 5
├── agents/
│   └── investigate.md            # Stage 4 scout brief
└── knowledge/                    # sub-agent context, never loaded by orchestrator
    ├── false-positives.md
    └── extraction-thresholds.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those are
for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.

All five pipeline scripts — the three Stage-1 scanners plus collapse,
rank, and report — live under this skill's `scripts/` directory, so the
skill is **self-contained**: deploying it carries its own detectors. The
Stage-1 scanners are stdlib-only and scan the host project relative to
the current working directory (`--root` defaults to cwd), so
`/extract-cotton-primitive` and manual review can reuse them via this
skill path.
