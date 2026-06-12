---
name: find-layer-violation
description: |
  Detect views, tasks, or other entry points that own business logic.
  AST-walks the target for core signals (fat body, domain loop over
  queryset, direct LLM/agent call, dispatch bypass via bare `.delay()`,
  multi-model write in one function), then asks scouts to judge remaining
  authority in the entry point: raw SQL/cursors, direct external API
  clients, import/export construction, direct model/file writes, task
  dispatch, and transaction/resource policy. Produces an extract-service
  candidates report. Never edits code — hands off to
  `/fix-workflow layer:<candidate_id>`.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Views, tasks, or other entry points owning business logic — domain
  loops over querysets, direct LLM calls, dispatch bypass via bare
  `.delay()`, multi-model writes inside one function, raw SQL/cursors,
  direct external API clients, import/export construction, and direct
  model/file writes. Targets the layer-violation smell.
not_for: |
  Service-layer omnibus modules (use /find-omnibus). Stringly-typed
  state inside a view (use /find-implicit-state). Refactor execution
  (use /fix-workflow layer:<id>).
language: python
framework: django
scout_model: cheap
---

# /find-layer-violation

You are the **orchestrator** for a layer-violation audit. Your job is
to drive a detector + a scout-verification fan-out; the judgment calls
(is this business logic or HTTP plumbing, which service owns the
domain, is the dispatch bypass intentional) live in the scout brief
and the knowledge files, not in this prompt.

The four buckets (`extract_service`, `move_to_existing_service`,
`broad_workflow_coordinator`, `intentional_http_coupling`), the
View-Pattern evaluation rule, and the extraction-sketch format are
documented in
`knowledge/verification.md` — scouts read it, you don't.

## How success is judged

- Every reported entry point carries a Stage 3 scout verdict at
  `scout/<candidate_id>.json` — an authority judgment in one of the
  four buckets (`extract_service` / `move_to_existing_service` /
  `broad_workflow_coordinator` / `intentional_http_coupling`), not a
  raw signal count.
- Extract-service candidates in `report.md` are actionable: their IDs
  resolve as `/fix-workflow layer:<candidate_id>` arguments;
  coordinators route to product-topology mapping instead.
- Zero code edits — read-only audit.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. View and task
  layer files within it are classified automatically (by the
  conventional `views`/`tasks` segment names, or the host's
  `.engineering/docs/find-layer-violation-scope.md` layer map). Accepts
  a directory for a full sweep or a single file.
- **Project root:** this worktree's root.
- **Python:** `python3` (detectors are stdlib-only). `.venv/bin/python`
  is not required — this skill is read-only and does not touch Django.
- **Project-specific defaults** (LOC budgets, HTTP-coupled exemptions,
  existing-service inventory): in `knowledge/`.
- **Responsibility-left-in-view rule:** for omnibus views, measure what
  authority remains in the view after extraction: raw SQL, direct API
  client use, direct model writes, task dispatch, export construction,
  filesystem writes, and cross-model transactions. LOC is only the
  first signal.
- **Coordinator rule:** if a view coordinates workflow context,
  sidebar/dashboard status, template selection, and compatibility
  redirects but delegates domain behavior to services, classify it as
  `broad_workflow_coordinator`. Its next step is usually
  `/map-product-workflow` or `/extract-workflow-registry`, not a
  domain-service extraction.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `python3` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/layer-violation/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/layer-violation/latest
```

### Stage 1 — Detect

**Pre:** target directory exists. **Post:** `layer_violations.jsonl`
with one record per signal-hit (score-sorted).

```bash
python3 .claude/skills/find-layer-violation/scripts/detect.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/layer_violations.jsonl"
```

### Stage 2 — Collapse

**Pre:** `layer_violations.jsonl`. **Post:**
`${REPORT_DIR}/candidates.jsonl` — per-symbol candidates with
`candidate_id` assigned, capped to top 30.

A single method often fires 2–4 signals; collapse groups by
`(file, symbol)` and assigns a confidence tier (high = 3+ signals,
medium = 2, low = 1).

```bash
python3 .claude/skills/find-layer-violation/scripts/collapse.py \
  --detections "${REPORT_DIR}/layer_violations.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl" \
  --top 30
```

### Stage 3 — Verify (parallel fan-out)

**Pre:** `candidates.jsonl`. **Post:**
`${REPORT_DIR}/scout/<candidate_id>.json` for every verified
candidate.

This is the **only stage where LLM judgment runs**. Dispatch one
sub-agent per top-10 candidate (or fewer if the candidate list is
shorter). Each sub-agent receives:

- the candidate JSON (one line from `candidates.jsonl`),
- the prompt template from `agents/verify.md`,
- paths to `knowledge/*` files,
- an output path it must write to.

**Budget:** verify up to the **top 10 candidates by default**. If the
user asked for a deeper scan, raise the budget. If the user asked for
a specific subset (e.g., "only the tasks"), filter before dispatch.

For each candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{output_path}}`) and dispatch with
`subagent_type=general-purpose`. Send all Agent calls in a **single
message** so they run concurrently.

If a scout returns invalid JSON or flags the verification as aborted,
re-dispatch once with a stricter "respond only with file-write
confirmation" nudge; skip the candidate if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the four buckets in `verify.md` (`extract_service` /
`move_to_existing_service` / `broad_workflow_coordinator` /
`intentional_http_coupling`). The scout reads the enclosing function and
checks the existing-service inventory in `knowledge/`, no cross-
file synthesis, no shell. Safe on Haiku-class scouts.

For nesting-safe + low-cost fan-out, dispatch each candidate as a
`tools/code_agent.py --read-only` subprocess via
`.claude/skills/_common/dispatch_scout_cheap.sh`. The `--read-only`
flag drops bash, spawn_agent, claude_tools, and validate_jsonld — the
scout has only read_file/write_file/glob/grep, with workdir
containment enforced (commit `168ca3c1`). Cheap models can't
hallucinate calls to tools that aren't in the registry.

```bash
# One subprocess per candidate; parallelize with `&` + wait.
while read -r line; do
    cid=$(jq -r '.candidate_id' <<<"$line")
    out="${REPORT_DIR}/scout/${cid}.json"
    .claude/skills/_common/dispatch_scout_cheap.sh \
        .claude/skills/find-layer-violation/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-layer-violation" \
        output_path="$out" &
done < "${REPORT_DIR}/candidates.jsonl"
wait
```

**Tradeoffs.** Cheap subprocess dispatch adds ~2-4s spawn per scout
and runs Claude Haiku 4.5 through the team's Expedient gateway by
default (see `tools/agent-config.json`); set `DISPATCH_SCOUT_MODEL`
to swap in any other alias (e.g., `cerebras` for personal-account
free-tier capacity). The `Agent` tool path is faster (~0s spawn) and
uses the orchestrator's session model (Sonnet/Opus tier — more
judgment, billed). Use the cheap subprocess by default; fall back to
`Agent` when (a) only a handful of candidates need verification
interactively and the user is watching, or (b) a candidate is
genuinely ambiguous between `broad_workflow_coordinator` and
`extract_service` and the better model's judgment about workflow
ownership is worth the cost.

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
python3 .claude/skills/find-layer-violation/scripts/report.py \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --scout-dir "${REPORT_DIR}/scout" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

# Effectiveness log — one line per run, feeds reports/_meta/dashboard.md.
python3 scripts/log_effectiveness.py \
  --skill find-layer-violation \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (`extract_service` / `move_to_existing_service` /
  `broad_workflow_coordinator` / `intentional_http_coupling` /
  `unverified`),
- top 3 candidates (one line each: file, symbol, signal list,
  recommendation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command — for the worst confirmed candidate,
  `/fix-workflow layer:<candidate_id>`. That skill reads the candidate
  and drives the extraction through characterization tests and
  two-commit discipline.
  For `broad_workflow_coordinator`, recommend product-topology mapping
  before code movement.

The report is the source of truth — do not enumerate every candidate.

## Non-goals

- Executing the extraction (that's `/fix-workflow` after user
  approval).
- Editing or deleting code — read-only audit.
- Detecting duplication (that's `/find-duplication` /
  `/find-semantic-duplication`).
- Detecting omnibus modules (that's `/find-omnibus`).
- Enforcing LOC budgets on every commit (that's
  `scripts/lint/no_fat_view.py`, the `fat-view` rule — diff-scoped
  per-commit check). This skill is the broader periodic audit, which
  also covers `domain_loop`, `direct_llm_call`, `dispatch_bypass`, and
  `multi_model_write`.
- CI gates — periodic audit, not a per-commit check.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 detector reports 0 candidates | Target has no flagged views/tasks (best outcome) — or scope is too narrow; try a wider target like the source root for a full sweep |
| Stage 1 over-fires on CRUD helpers | Tighten LOC budget with `--fn-budget` / `--method-budget` / `--task-budget`, or add the shape to `knowledge/` HTTP-coupled filter |
| Stage 2 caps too aggressively | Pass `--top 50` or higher to `collapse.py` |
| Stage 3 scout buckets everything as `intentional_http_coupling` | Scout is being too lenient — re-dispatch citing the canonical examples (`external_source.py`, `collections.py`) from `knowledge/` |
| Stage 3 scout buckets everything as `extract_service` | Scout ignores HTTP coupling — re-dispatch citing the CLAUDE.md View Pattern rule in `verification.md` |
| Report's `recommendation` field disagrees with bucket | Scout error; reconcile using the bucket-recommendation mapping in `report.py` |

## Repository layout

```
.claude/skills/find-layer-violation/
├── SKILL.md                  # this file — orchestrator
├── scripts/
│   ├── detect.py             # Stage 1 — AST signal detector
│   ├── collapse.py           # Stage 2 — per-symbol grouping + ids
│   └── report.py             # Stage 4 — render report.md + findings.json
├── agents/
│   └── verify.md             # Stage 3 scout brief
└── knowledge/                # sub-agent context, never loaded by orchestrator
    └── verification.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
