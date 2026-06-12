---
name: find-duplication
description: Detect structural and lexical code duplication. Runs jscpd and the AST visitor in parallel, collapses overlapping clone pairs into method-identity findings, fans out sub-agent investigators, and produces a triage report with a dormant-code side-channel. Hands off to `/fix-workflow` for execution.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Lexical / structural copy-paste — two methods with identical or
  near-identical bodies. Runs jscpd + AST visitor in parallel,
  collapses overlapping clone pairs into method-identity findings,
  produces a P0/P1/P2 triage report.
not_for: |
  Semantic duplication where the code differs but the workflow
  overlaps (use /find-semantic-duplication). Refactor execution (use
  /fix-workflow cluster:<id>). Cross-layer drift (template/JS/Python
  for one workflow — use /find-workflow-duplication).
language: python
framework: django
---

# /find-duplication

You are the **orchestrator** for a duplication audit. Your job is to drive a
pipeline of scripts and sub-agent investigators; the judgment calls live in
the scout brief and the knowledge files, not in this prompt.

## How success is judged

- `${REPORT_DIR}/triage.md` + `findings.json` exist, and every
  investigated finding carries a Stage 4 scout verdict at
  `scout/<finding_id>.json` — nothing dropped silently between
  `ranked.json` and `classified.json`.
- Cluster IDs in the triage report resolve as `/fix-workflow
  cluster:<id>` arguments; dormant candidates flow to the
  side-channel, never get acted on here.
- Zero edits to production files — this is a read-only audit.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Must be a directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **Project-specific defaults** (ignore paths, dispatch registries, shadow
  helper names, test suites): in `knowledge/`.

## Pipeline stages (each one has a contract)

Each stage reads files the previous stage wrote and writes files the next
stage reads. Run scripts with `.venv/bin/python` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/duplication/scan-${TS}"
mkdir -p "${REPORT_DIR}/jscpd" "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/duplication/latest
```

### Stage 1 — Detect (parallel)

**Pre:** target directory exists. **Post:** `jscpd/jscpd-report.json` and
`ast_findings.json` both present and non-empty.

Run both commands concurrently in one Bash message:

```bash
# lexical clones (Type 1 + near-Type 2). The wrapper pins jscpd and uses
# a deterministic npm cache; --offline-ok writes a skipped-lexical report
# so the AST side can still run when npm/network is unavailable.
.venv/bin/python scripts/lint/run_jscpd.py <target> \
  --output "${REPORT_DIR}/jscpd" --offline-ok

# AST patterns (shadow helpers, bare_int_request, cross-module clones, ...)
.venv/bin/python scripts/duplication_audit.py <target> \
  > "${REPORT_DIR}/ast_findings.json"
```

### Stage 2 — Collapse

**Pre:** Stage 1 outputs exist. **Post:** `${REPORT_DIR}/collapsed.json` —
jscpd pairs grouped by method identity, AST categories normalized to the
common finding shape, intentional-repeat names filtered.

```bash
.venv/bin/python .claude/skills/find-duplication/scripts/collapse.py \
  --jscpd-report "${REPORT_DIR}/jscpd/jscpd-report.json" \
  --ast-findings "${REPORT_DIR}/ast_findings.json" \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/collapsed.json"
```

### Stage 3 — Rank

**Pre:** `collapsed.json`. **Post:** `${REPORT_DIR}/ranked.json` — each
finding has a `rank_meta` block (priority, tier, effort hint); findings are
sorted P0 → P2, highest priority first.

```bash
.venv/bin/python .claude/skills/find-duplication/scripts/rank.py \
  --input "${REPORT_DIR}/collapsed.json" \
  --output "${REPORT_DIR}/ranked.json"
```

### Stage 4 — Investigate (parallel fan-out)

**Pre:** `ranked.json`. **Post:** `${REPORT_DIR}/scout/<finding_id>.json` for
every investigated finding; a single `${REPORT_DIR}/classified.json`
aggregating them.

This is the **only stage where LLM judgment runs**. You (the orchestrator)
do **not** read the clone bodies — you dispatch one sub-agent per finding
(or batch if there are many). Each sub-agent receives:

- the finding JSON,
- the prompt template from `agents/investigate.md`,
- paths to `knowledge/*` files,
- an output path it must write to.

Budget: investigate **top 10 by priority** by default. If there are fewer
than 10 findings, investigate them all. If the user asked for a deeper
scan, raise the limit.

For each finding, expand the `agents/investigate.md` template (substitute
`{{finding_id}}`, `{{finding_json}}`, `{{project_root}}`, `{{skill_root}}`,
`{{output_path}}`) and dispatch with `subagent_type=general-purpose`. Send
all Agent calls in a **single message** so they run concurrently.

After the sub-agents return, combine their JSON files:

```bash
.venv/bin/python -c "
import json, glob, pathlib
out = {'findings': [], 'dormant_candidates': []}
for p in sorted(glob.glob('${REPORT_DIR}/scout/*.json')):
    d = json.loads(pathlib.Path(p).read_text())
    out['findings'].append(d)
    out['dormant_candidates'].extend(d.get('dormant_candidates') or [])
pathlib.Path('${REPORT_DIR}/classified.json').write_text(json.dumps(out, indent=2))
"
```

### Stage 5 — Report

**Pre:** `ranked.json`, `classified.json`. **Post:** `${REPORT_DIR}/triage.md`
and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-duplication/scripts/report.py \
  --input "${REPORT_DIR}/ranked.json" \
  --classified "${REPORT_DIR}/classified.json" \
  --output-md "${REPORT_DIR}/triage.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}"

# Effectiveness log — one line per run, feeds reports/_meta/dashboard.md.
# Derive counts from findings.json; shape is {duplication, shadow,
# dormant, pattern-violation, other}. See `.claude/skills/_common/skill-conventions.md`.
python3 scripts/log_effectiveness.py \
  --skill find-duplication \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(.venv/bin/python -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("findings", [])))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys,collections; f=json.load(open(sys.argv[1])).get("findings", []); c=collections.Counter(x.get("shape","other") for x in f); print(json.dumps(dict(c)))' "${REPORT_DIR}/findings.json")"
```

### Stage 6 — Summarize

Report to the user in ≤10 lines:

- counts by shape (duplication, dormant, shadow, pattern-violation),
- top 3 clusters by priority (one line each),
- any latent-bug risks flagged,
- path to `${REPORT_DIR}/triage.md` and the `latest` symlink,
- recommended next slash command.

The triage report is the source of truth — do not enumerate every finding.

## Non-goals

- Executing fixes (that's `/fix-workflow`).
- Dead-code detection as a primary task (that's `/find-dormant`; dormant
  findings here are a side-channel).
- Editing files or running tests (this is a read-only audit).
- Per-commit CI gates — this is a periodic audit.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 jscpd is skipped | Check `${REPORT_DIR}/jscpd/skipped-lexical.json`; lexical evidence is unavailable but AST findings can still proceed |
| Stage 2 reports 0 findings | Target probably excluded — check `ignore_patterns` in `collapsed.json`, verify target has non-test Python files |
| Stage 4 sub-agent returns invalid JSON | Re-dispatch with a stricter "respond with only the file write confirmation" nudge; skip finding if it fails twice |
| Scout says "dormant" on a registered class | It skipped the registry-dispatch check — re-dispatch citing `knowledge/false-positives.md` explicitly |
| Priority ranking puts a sprawl pattern above a genuine clone | Expected — the multiplicity cap (`MULT_CAP` in rank.py) bounds sprawl influence; inspect by hand if it still dominates |

## Repository layout

```
.claude/skills/find-duplication/
├── SKILL.md                      # this file — orchestrator
├── scripts/
│   ├── collapse.py               # Stage 2
│   ├── rank.py                   # Stage 3
│   └── report.py                 # Stage 5
├── agents/
│   └── investigate.md            # Stage 4 scout brief
└── knowledge/                    # sub-agent context, never loaded by orchestrator
    ├── false-positives.md
    └── learnings.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those are for
the scout sub-agents. Keeping them out of your context is the whole point
of this architecture.
