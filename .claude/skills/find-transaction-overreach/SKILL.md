---
name: find-transaction-overreach
description: Detect Django `transaction.atomic()` blocks (and `@transaction.atomic` functions) that hold a DB connection while doing slow / external work. Runs an AST scan for HTTP calls, AI/SDK calls, cloud uploads, `time.sleep`, subprocess, and Celery dispatch inside atomic regions; collapses hits per block, fans out scout sub-agents to bucket each candidate (narrow / split / defer / legitimate / false positive), and produces a report that hands off to `/fix-workflow cluster:<symbol>`. Detection-only — never edits production code.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  `with transaction.atomic():` blocks or `@transaction.atomic` functions
  whose body issues an HTTP request, AI/SDK call, cloud upload, sleep,
  subprocess, or Celery dispatch — anything that holds a database
  connection during external work. Targets a runtime-failure-mode
  smell that passes structural review but starves the connection
  pool under load.
not_for: |
  Long DB-only transactions (many `update_or_create` calls in a loop
  are usually fine — that's a different smell). Read-named methods
  that mutate persisted state (use /find-query-mutation). Bare Celery
  dispatches outside transactions (the `safe-dispatch` lint covers
  those at commit time). Refactor execution (use /fix-workflow
  cluster:<symbol>).
language: python
framework: django
scout_model: cheap
---

# /find-transaction-overreach

You are the **orchestrator** for a transaction-overreach audit. Your
job is to drive a pipeline of detectors and sub-agent verifiers; the
bucket judgment calls live in the scout brief and the knowledge files,
not in this prompt.

The smell (a Django transaction wraps slow / external work and pins a
connection during it), the five buckets (`narrow_transaction`,
`split_transaction`, `defer_via_on_commit`,
`legitimate_long_transaction`, `false_positive`), and the verification
checklist are documented in `knowledge/verification.md` — scouts read
it, you don't.

## How success is judged

- `${REPORT_DIR}/report.md` and `findings.json` agree — every finding
  traces to a Stage 3 scout verdict at `scout/<candidate_id>.json`
  with the atomic-block span and slow-op category as evidence.
- Each candidate lands in one of the five buckets; `# atomic-overreach:`
  markers and `transaction.on_commit` deferrals are honored, never
  reported as actionable.
- Actionable symbols resolve as `/fix-workflow cluster:<symbol>`
  arguments.
- Zero edits to production code — detection-only audit.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Accepts either
  a directory or a single file.
- **Project root:** this worktree's root.
- **Python:** `python3` (the detectors are stdlib-only and run without
  the venv).
- **Project-specific defaults** (known false-positive helper names,
  `transaction.on_commit` conventions, `safe_dispatch` semantics,
  detection gaps): in `knowledge/`.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `python3` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/transaction-overreach/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/transaction-overreach/latest
```

### Stage 1 — Detect

**Pre:** target exists. **Post:** `${REPORT_DIR}/hits.jsonl` present.

```bash
python3 .claude/skills/find-transaction-overreach/scripts/detect.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/hits.jsonl"
```

The detector honors `# atomic-overreach: <reason>` markers and drops
those hits before writing the file. It also drops calls inside
`transaction.on_commit(lambda: ...)` since those are explicitly
deferred. It does not resolve helper-function bodies (the scout does
that at Stage 3) — a `self._build_payload(...)` call inside an atomic
block won't surface unless the helper name matches the
`network_helper` rules.

### Stage 2 — Collapse

**Pre:** `hits.jsonl`. **Post:** `${REPORT_DIR}/candidates.jsonl` —
one record per atomic block with hit count, confidence tier, and
slow-op categories touched.

```bash
python3 .claude/skills/find-transaction-overreach/scripts/collapse.py \
  --hits "${REPORT_DIR}/hits.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl"
```

Confidence tiers (assigned by category mix):

- `high` — block contains at least one `http` / `ai` / `cloud` /
  `subprocess` / `sleep` hit (each is guaranteed-slow).
- `medium` — block contains only `celery` hits (dispatch can be safe
  under `transaction.on_commit`; the scout disambiguates by reading
  the surrounding code).
- `low` — block contains only `network_helper` hits (ambiguous wrapper
  names; the scout reads the helper to decide).

### Stage 3 — Verify (parallel fan-out)

**Pre:** `candidates.jsonl`. **Post:**
`${REPORT_DIR}/scout/<candidate_id>.json` for every verified candidate.

This is the **only stage where LLM judgment runs**. Dispatch one
sub-agent per candidate; each receives:

- the candidate JSON (one line from `candidates.jsonl`),
- the prompt template from `agents/verify.md`,
- paths to the `knowledge/*` files,
- an output path it must write to.

**Budget:** verify up to **10 high-confidence candidates by default**,
prioritizing in this order:

1. `high` confidence (`http` / `ai` / `cloud` / `subprocess` / `sleep`).
2. `medium` confidence on `celery` (the `transaction.on_commit`
   disambiguation).
3. Remaining `low` candidates (most of these are wrapper-named helpers
   the scout disposes of quickly).

If the user asked for a deeper scan, raise the budget. If the user
asked for a specific file, filter candidates to that path before
dispatch.

For each selected candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{output_path}}`) and dispatch with
`subagent_type=general-purpose`. Send all Agent calls in a **single
message** so they run concurrently.

If a scout returns invalid JSON, re-dispatch once with a stricter
"respond only with file-write confirmation" nudge; skip the candidate
if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the five buckets in `verify.md` (`narrow_transaction`
/ `split_transaction` / `defer_via_on_commit` /
`legitimate_long_transaction` / `false_positive`). The scout reads the
enclosing block and resolves whether the slow op can move outside or
needs to defer via `on_commit`. No cross-file synthesis, no shell.
Safe on Haiku-class scouts.

For nesting-safe + low-cost fan-out, dispatch each candidate as a
`tools/code_agent.py --read-only` subprocess via
`.claude/skills/_common/dispatch_scout_cheap.sh`.

```bash
while read -r line; do
    cid=$(jq -r '.candidate_id' <<<"$line")
    out="${REPORT_DIR}/scout/${cid}.json"
    .claude/skills/_common/dispatch_scout_cheap.sh \
        .claude/skills/find-transaction-overreach/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-transaction-overreach" \
        output_path="$out" &
done < "${REPORT_DIR}/candidates.jsonl"
wait
```

Use the cheap subprocess by default; fall back to `Agent` when only a
handful of candidates need verification interactively and the user is
watching, or when the receiver helper is genuinely ambiguous (e.g.,
a project-internal name the scout can't resolve from the local file).

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
python3 .claude/skills/find-transaction-overreach/scripts/report.py \
  --scout-dir "${REPORT_DIR}/scout" \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

python3 scripts/log_effectiveness.py \
  --skill find-transaction-overreach \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (`narrow_transaction` / `split_transaction` /
  `defer_via_on_commit` / `legitimate_long_transaction` /
  `false_positive`),
- counts by slow-op category (`http` / `ai` / `celery` / `cloud` /
  `subprocess` / `sleep` / `network_helper`),
- top 3 candidates (one line each: file, symbol, recommendation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command (`/fix-workflow cluster:<symbol>`
  for top actionable, or `/find-transaction-overreach` again after
  cleanup).

The report is the source of truth — do not enumerate every candidate.

## Non-goals

- Writing the narrow / split / defer proposal (that's
  `/fix-workflow cluster:<symbol>`).
- Executing any refactor (that's `/fix-workflow` after proposal
  approval).
- Running tests — read-only audit; tests run during the refactor
  skill.
- CI gates — periodic audit, not a per-commit check. (No corresponding
  lint rule yet — if recurrence justifies one, file a `/decide` to
  spec it.)
- Resolving helper-function bodies — the detector only matches direct
  named calls; helpers that internally do HTTP/AI work are a documented
  detection gap. Scouts may flag them as `false_positive` with a note.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 detect.py finds 0 hits | Target has no transaction-overreach smell (best outcome) — or the directory argument is wrong. Re-run with a valid `--target <dir>` or widen to `--target .` |
| Stage 1 detect.py is slow (>2 min) | Shouldn't happen on a typical source tree — check for `__pycache__` entries in target. Add more `--skip-file-glob` flags if needed |
| Stage 2 reports 0 candidates | Same as Stage 1 zero — or collapse ignored all hits (check stderr) |
| Stage 3 scout buckets everything as `false_positive` | Scout is being too permissive on `celery` hits. Inspect one output; the `safe_dispatch` + `transaction.on_commit` combination IS legitimate, but `safe_dispatch` alone (no on_commit) inside an atomic block is still worth flagging |
| Scout recommends `narrow_transaction` for a `select_for_update().get()` followed by row update | That's the canonical row-locking pattern — should be `false_positive` (the only "external" thing inside is a row read, not a slow op). Re-dispatch with the `knowledge/` row-locking note cited |
| Report lists `# atomic-overreach:`'d candidates as actionable | Detector bug — the marker should have exempted the hit before collapse. Investigate, fix the detector's `ALLOWLIST_RE` range check |

## Repository layout

```
.claude/skills/find-transaction-overreach/
├── SKILL.md                  # this file — orchestrator
├── scripts/
│   ├── detect.py             # Stage 1
│   ├── collapse.py           # Stage 2
│   └── report.py             # Stage 4
├── agents/
│   └── verify.md             # Stage 3 scout brief
└── knowledge/                # sub-agent context, never loaded by orchestrator
    └── verification.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
