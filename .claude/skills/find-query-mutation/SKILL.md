---
name: find-query-mutation
description: Detect read-named methods that mutate persisted state. Runs an AST scan for functions named `get_*` / `fetch_*` / `load_*` / `list_*` / `find_*` / `check_*` whose body calls `.save()` / `.delete()` / `.update()` / `.create()` / `.bulk_create()` / `.bulk_update()` / `.update_or_create()` / `.get_or_create()`; collapses hits per function, fans out scout sub-agents to bucket each candidate (rename / split / legitimate warming / stdlib false positive), and produces a report that hands off to `/fix-workflow cluster:<symbol>`. Detection-only — never edits production code.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Read-named methods (`get_*`, `fetch_*`, `load_*`, `list_*`, `find_*`,
  `check_*`) that mutate persisted state via `.save()` / `.delete()` /
  `.update_or_create()`. Targets the query-mutation smell.
not_for: |
  Mutator-named methods that don't actually mutate (use /find-dormant
  for the unused side). Refactor execution (use /fix-workflow
  cluster:<symbol>). Stringly-typed status comparisons (use
  /find-implicit-state).
language: python
framework: django
scout_model: cheap
---

# /find-query-mutation

You are the **orchestrator** for a query-mutation audit. Your job is
to drive a pipeline of detectors and sub-agent verifiers; the bucket
judgment calls live in the scout brief and the knowledge files, not in
this prompt.

The smell (read-named function mutates persisted state), the four
buckets (rename_to_mutator, split_reader_and_mutator,
legitimate_cache_warming, false_positive_stdlib_wrapper), and the
verification checklist are documented in `knowledge/verification.md` —
scouts read it, you don't.

## How success is judged

- Every reported candidate carries a Stage 3 scout verdict at
  `scout/<candidate_id>.json` in one of the four buckets
  (`rename_to_mutator` / `split_reader_and_mutator` /
  `legitimate_cache_warming` / `false_positive_stdlib_wrapper`) —
  no detector hit reaches `report.md` ungraded or silently dropped.
- Actionable symbols in the report resolve as `/fix-workflow
  cluster:<symbol>` arguments; `# hidden-mutation:` markers honored.
- Zero edits to production code — detection-only audit.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Must be a
  directory.
- **Project root:** this worktree's root.
- **Python:** `python3` (the detectors are stdlib-only and run without
  the venv).
- **Project-specific defaults** (known receiver shapes, legitimate
  cache-warming sites, hidden-mutation conventions, detection gaps):
  in `knowledge/`.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `python3` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/query-mutation/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/query-mutation/latest
```

### Stage 1 — Detect

**Pre:** target directory exists. **Post:** `${REPORT_DIR}/hits.jsonl`
present.

```bash
python3 .claude/skills/find-query-mutation/scripts/detect.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/hits.jsonl"
```

The detector honors `# hidden-mutation: <reason>` markers and drops
those hits before writing the file. It does not resolve receivers
(the scout does that at Stage 3) — a `dict.update({...})` call inside
a `get_context_data` method will surface as a hit and get bucketed as
`false_positive_stdlib_wrapper` by the scout.

### Stage 2 — Collapse

**Pre:** `hits.jsonl`. **Post:** `${REPORT_DIR}/candidates.jsonl` —
one record per `(file, symbol)` bucket with hit count, confidence
tier, and mutation methods touched.

```bash
python3 .claude/skills/find-query-mutation/scripts/collapse.py \
  --hits "${REPORT_DIR}/hits.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl"
```

Confidence tiers (assigned by mutation shape):

- `high` — function calls `save` / `delete` / `create` /
  `bulk_create` / `bulk_update` (Django persistence shapes; strong
  signal the read-named function mutates a persisted row).
- `medium` — function calls `update` / `update_or_create` /
  `get_or_create`. `update` especially is ambiguous — also
  `dict.update` and `set.update` on non-queryset receivers; scouts
  disambiguate.
- `low` — (reserved; currently no rule maps here).

### Stage 3 — Verify (parallel fan-out)

**Pre:** `candidates.jsonl`. **Post:**
`${REPORT_DIR}/scout/<candidate_id>.json` for every verified candidate.

This is the **only stage where LLM judgment runs**. You do not verify
candidates yourself — dispatch one sub-agent per candidate. Each
sub-agent receives:

- the candidate JSON (one line from `candidates.jsonl`),
- the prompt template from `agents/verify.md`,
- paths to the `knowledge/*` files,
- an output path it must write to.

**Budget:** verify up to **10 high-confidence candidates by default**,
prioritizing in this order:

1. `high` confidence (`save` / `delete` / `create` / `bulk_*`).
2. `medium` confidence on `get_or_create` / `update_or_create` (the
   singleton-warmer and upsert shapes).
3. Remaining `medium` candidates (most of these are
   `dict.update`/`set.update` false positives the scout disposes of
   quickly).

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
classify against the four buckets in `verify.md` (`rename_to_mutator`
/ `split_reader_and_mutator` / `legitimate_cache_warming` /
`false_positive_stdlib_wrapper`). The scout reads the enclosing function
and resolves the receiver type (model instance vs `dict` / `set`), no
cross-file synthesis, no shell. Safe on Haiku-class scouts.

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
        .claude/skills/find-query-mutation/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-query-mutation" \
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
interactively and the user is watching, or (b) the receiver is
genuinely ambiguous (e.g., a `get_or_create` hit where the cache-
warming vs upsert distinction depends on caller context the scout
can't easily see).

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
python3 .claude/skills/find-query-mutation/scripts/report.py \
  --scout-dir "${REPORT_DIR}/scout" \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

# Effectiveness log — one line per run. Buckets come from findings.json.
python3 scripts/log_effectiveness.py \
  --skill find-query-mutation \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (rename_to_mutator / split_reader_and_mutator /
  legitimate_cache_warming / false_positive_stdlib_wrapper),
- counts by mutation method (`save` / `delete` / `update` / …),
- top 3 candidates (one line each: file, symbol, recommendation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command (`/fix-workflow cluster:<symbol>`
  for top actionable, or `/find-query-mutation` again after cleanup).

The report is the source of truth — do not enumerate every candidate.

## Non-goals

- Writing the rename / split proposal (that's `/fix-workflow
  cluster:<symbol>`).
- Executing any refactor (that's `/fix-workflow` after proposal
  approval).
- Running tests — read-only audit; tests run during the refactor
  skill.
- CI gates — periodic audit, not a per-commit check. The lint rule
  `query-mutation` covers per-commit guarding for new code.
- Resolving dynamic dispatch / method aliases — the detector only
  matches `<attr>.<method>(...)` calls; dispatched calls are a
  documented detection gap.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 detect.py finds 0 hits | Target has no query-mutation smell (best outcome) — or the directory argument is wrong. Re-run with a valid `--target <dir>` |
| Stage 1 detect.py is slow (>2 min) | Shouldn't happen on a typical source tree — check for `__pycache__` entries in target. Add more `--skip-file-glob` flags if needed |
| Stage 2 reports 0 candidates | Same as Stage 1 zero — or collapse ignored all hits (check stderr) |
| Stage 3 scout buckets everything as `false_positive_stdlib_wrapper` | Scout is being too permissive. Inspect one output; re-dispatch with "re-check whether the receiver is `self` inside a `models.Model` subclass" |
| Scout recommends `rename_to_mutator` for a `get_context_data` override | Receiver-resolution rule was skipped — re-dispatch citing `cbv_context_data` |
| Report lists `# hidden-mutation:`'d candidates as actionable | Detector bug — the marker should have exempted the hit before collapse. Investigate, fix the detector's `HIDDEN_RE` range check |

## Repository layout

```
.claude/skills/find-query-mutation/
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
