---
name: find-semantic-duplication
description: Detect semantic duplication — independently-written, both-live workflows or functions that solve the same problem with different code. Builds an inventory + call graph via semantic_inventory.py, fans out summarizing/comparing/confirming scouts, collapses multi-way clusters, and produces a ranked triage report with capability matrices. Hands off to `/fix-workflow` for execution.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Two independently-written functions or workflows that solve the same
  problem with different code shape — both live, both maintained.
  Builds a call graph + fan-out scout comparators; ranks clusters with
  capability matrices.
not_for: |
  Lexical near-clones (use /find-duplication). Dead code (use
  /find-dormant). Refactor execution (use /unify-shadows for the
  proposal then /fix-workflow semantic:<id>).
language: python
framework: django
---

# /find-semantic-duplication

You are the **orchestrator** for a semantic-duplication audit. Your job is to
drive a pipeline of scripts and sub-agent scouts; the judgment calls live in
the scout briefs and `knowledge/` files, not in this prompt.

Semantic duplication fills a gap between `/find-duplication` (syntactic
clones) and `/find-dormant` (dead code). Two bodies with 0% token overlap
can still solve the same problem — this skill finds those.

## How success is judged

- No finding reaches `triage.md` without a Stage 5 Confirm scout
  verdict at `scout/<finding_id>.json` — Compare nominations alone
  are never reported.
- Every confirmed cluster has its capability matrix at
  `capability_matrices/<finding_id>.md`; `uncertain` and
  `false_positive` verdicts flow through honestly, not forced.
- Finding IDs resolve as `/fix-workflow semantic:<id>` arguments.
- Zero edits to production files — this is a read-only audit.
- The closeout pastes artifact truth: validation `PASS: N/N` lines,
  Stage 4/6/7 script output, and the path to `triage.md`. A claim that
  scouts ran is not enough without the files and validator output.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Must be a directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for Django-touching scripts; `python3` is
  fine for `semantic_inventory.py` (stdlib-only).
- **Project-specific defaults** (domain taxonomy, framework-mandated skips,
  split-by-design exclusions, known suspects): `knowledge/`.
- **Rejection classes** (seven for function-level, three for structural):
  `knowledge/false-positives.md` — scouts apply these, not you.

## Scout dispatch contract

Every Agent dispatch must declare its judged artifact:

| Stage | Prompt | Judged output |
|---|---|---|
| Summarize | `agents/summarize.md` | JSONL at the substituted `{{output_path}}`, validated with `semantic_inventory.py validate --schema summary` |
| Compare | `agents/compare.md` | JSON object at `candidates_<domain>.json`; empty `{"candidates": []}` is valid |
| Confirm | `agents/confirm.md` | `scout/<finding_id>.json`; confirmed findings also write `capability_matrices/<finding_id>.md` |

The orchestrator judges the run only by those artifacts. Scout replies are
status pings; they are not the source of truth.

## Pipeline stages (each one has a contract)

Each stage reads files the previous stage wrote and writes files the next
stage reads. Run scripts with the correct interpreter and capture stderr so
failures surface. You (the orchestrator) **never read `knowledge/` files** —
they're for the scout sub-agents.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/semantic-duplication/scan-${TS}"
mkdir -p "${REPORT_DIR}/prompts" "${REPORT_DIR}/summary_batches" \
         "${REPORT_DIR}/scout" "${REPORT_DIR}/capability_matrices"
ln -sfn "scan-${TS}" reports/semantic-duplication/latest
```

### Stage 1 — Inventory

**Pre:** target directory exists. **Post:** `inventory.jsonl`,
`workflows.jsonl`, `callers.jsonl`, `artifacts.jsonl` all present and valid.

Run `collect` first (later subcommands need its output), then `graph`,
`callers`, and `artifacts` in parallel:

```bash
python3 scripts/semantic_inventory.py collect <target> \
  -o "${REPORT_DIR}/inventory.jsonl"
```

For a focused scan that needs broader caller/context visibility, scan the
context root and tag the subsystem as focus:

```bash
python3 scripts/semantic_inventory.py collect \
  --focus <target> --context-root <context-root> \
  -o "${REPORT_DIR}/inventory.jsonl"
```

Then in one Bash message:

```bash
python3 scripts/semantic_inventory.py graph "${REPORT_DIR}/inventory.jsonl" \
  -o "${REPORT_DIR}/workflows.jsonl"
python3 scripts/semantic_inventory.py callers "${REPORT_DIR}/inventory.jsonl" \
  --repo-root "$(pwd)" -o "${REPORT_DIR}/callers.jsonl"
python3 scripts/semantic_inventory.py artifacts --repo-root "$(pwd)" \
  -o "${REPORT_DIR}/artifacts.jsonl"
```

Validate every output before proceeding (the script emits `PASS: N/N records valid`):

```bash
python3 scripts/semantic_inventory.py validate "${REPORT_DIR}/inventory.jsonl" --schema auto
python3 scripts/semantic_inventory.py validate "${REPORT_DIR}/workflows.jsonl" --schema workflow
python3 scripts/semantic_inventory.py validate "${REPORT_DIR}/callers.jsonl" --schema caller_info
python3 scripts/semantic_inventory.py validate "${REPORT_DIR}/artifacts.jsonl" --schema artifact
```

### Stage 2 — Summarize (parallel fan-out)

**Pre:** `inventory.jsonl` valid. **Post:** `${REPORT_DIR}/summaries.jsonl`
with one record per eligible definition (tier = light / full / priority).

Split the inventory's definitions into batches of ~40 (skip `tier=skip`),
write each batch to `${REPORT_DIR}/summary_batches/batch_<N>.jsonl`, then
expand `agents/summarize.md` per batch (substitute `{{input_path}}`,
`{{output_path}}`, `{{project_root}}`, `{{skill_root}}`) and dispatch every
Agent call in a **single message** so they run concurrently.

After all scouts return, concatenate and validate:

```bash
cat "${REPORT_DIR}/summary_batches/out_"*.jsonl > "${REPORT_DIR}/summaries.jsonl"
python3 scripts/semantic_inventory.py validate "${REPORT_DIR}/summaries.jsonl" --schema summary
```

If validation fails, re-dispatch the offending batch with a note on which
fields were wrong. Do not hand-fix records — the scout should do it.

### Stage 3 — Compare (parallel fan-out per domain)

**Pre:** `summaries.jsonl` valid. **Post:** one
`${REPORT_DIR}/prompts/candidates_<domain>.json` per domain group.

Generate per-domain prompt files:

```bash
python3 scripts/semantic_inventory.py prompts \
  "${REPORT_DIR}/summaries.jsonl" --output-dir "${REPORT_DIR}/prompts"
```

If the focus cuts across package/domain names and the prompt size remains
reasonable, add `--include-cross-domain`; the script writes one bounded
`prompt_cross_domain.json` in addition to per-domain prompts. If the focus is
single-domain or the cross-domain prompt would be too large, skip this pass
honestly and record the reason in the Stage 8 summary.

For each `prompt_<domain>.json` the script wrote, expand `agents/compare.md`
(substitute `{{prompt_path}}`, `{{output_path}}` → `candidates_<domain>.json`
in the same dir, `{{skill_root}}`) and dispatch every scout in a **single
message** so they run concurrently.

The Compare bar is intentionally low — scouts nominate pairs scoring ≥3
(≥4 for Light tier). Better to over-nominate; Confirm has full source and
will filter.

### Stage 4 — Collapse

**Pre:** `prompts/candidates_*.json`. **Post:**
`${REPORT_DIR}/candidates.json` — per-domain pairs merged into multi-way
clusters via union-find on shared `(file, qualified_name)` sites.

```bash
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/collapse_candidates.py \
  --prompts-dir "${REPORT_DIR}/prompts" \
  --output "${REPORT_DIR}/candidates.json"
```

The collapse step exists because Compare emits (A,B), (A,C), (B,C) as three
pair candidates when three members share semantics — the same A-B / A-C
jscpd pair-explosion gotcha the `/find-duplication` collapse fixes, applied
here at the semantic level.

### Stage 5 — Confirm (parallel fan-out per finding)

**Pre:** `candidates.json`. **Post:**
`${REPORT_DIR}/scout/<finding_id>.json` for every investigated finding, plus
its capability matrix at
`${REPORT_DIR}/capability_matrices/<finding_id>.md`.

This is the **deep-read stage**. Scouts read full bodies and apply **all ten
rejection classes** from `knowledge/false-positives.md` (Compare only
applied the cheap ones).

Budget: investigate the **top 20 findings** from `candidates.json`
(pre-sorted by `similarity_max` then `multiplicity`). Raise the budget if
the user asked for a deeper scan.

For each selected finding, expand `agents/confirm.md` (substitute
`{{candidate_json}}`, `{{finding_id}}`, `{{project_root}}`, `{{skill_root}}`,
`{{output_json_path}}` → `scout/<finding_id>.json`, `{{output_matrix_path}}`
→ `capability_matrices/<finding_id>.md`, `{{callers_jsonl_path}}` →
`callers.jsonl`) and dispatch every scout in a **single message**.

The sibling syntactic-duplication report is optional. Confirm scouts check
`reports/duplication/latest/triage.md` only if it exists; when absent, their
JSON `notes` field records `sibling duplication report absent` and they still
apply the direct token-overlap rejection class.

### Stage 6 — Rank

**Pre:** `scout/*.json`, `callers.jsonl`. **Post:**
`${REPORT_DIR}/ranked.json` — each confirmed finding has a `rank_meta`
block (priority, tier, shared_lines, migration_cost); findings sorted P0 → P2.

```bash
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/rank.py \
  --confirmed "${REPORT_DIR}/scout" \
  --callers "${REPORT_DIR}/callers.jsonl" \
  --output "${REPORT_DIR}/ranked.json"
```

Ranking formula:
`ROI = (shared_lines × maintenance_risk × level_multiplier) / max(migration_cost, 1)`.
Level multiplier weights workflow (1.5) over structural (1.3) over function
(1.0). See `rank.py` header for the tier cutoffs.

### Stage 7 — Report

**Pre:** `ranked.json`. **Post:** `${REPORT_DIR}/triage.md` and
`${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/report.py \
  --input "${REPORT_DIR}/ranked.json" \
  --output-md "${REPORT_DIR}/triage.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}"

# Effectiveness log — one line per run, feeds reports/_meta/dashboard.md.
# Buckets = P0/P1/P2 counts by priority tier. See `.claude/skills/_common/skill-conventions.md`.
python3 scripts/log_effectiveness.py \
  --skill find-semantic-duplication \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(.venv/bin/python -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("findings", [])))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys,collections; f=json.load(open(sys.argv[1])).get("findings", []); c=collections.Counter(x.get("priority","unknown") for x in f); print(json.dumps(dict(c)))' "${REPORT_DIR}/findings.json")"
```

### Stage 8 — Summarize

Report to the user in ≤10 lines:

- Counts by tier (P0 / P1 / P2) and by level (workflow / structural / function),
- Top 3 findings by priority (one line each),
- Path to `${REPORT_DIR}/triage.md` and the `latest` symlink,
- Recommended next slash command (typically `/fix-workflow semantic:<id>`).

The triage report is the source of truth — do not enumerate every finding.

## Non-goals

- Executing fixes (that's `/fix-workflow`).
- Syntactic-clone detection (that's `/find-duplication`; if bodies are
  >70% token-similar the Confirm scout will reject with
  `reason_code: "token_similar_belongs_in_find_duplication"`).
- Dead-code detection (that's `/find-dormant`; if a confirmed implementation
  has zero callers, the Confirm scout notes it and the report surfaces it).
- Editing files or running tests (this is a read-only audit).
- External embedding APIs — LLM-native pairwise scoring is sufficient at this
  codebase size. Document embedding as a v2 path in the report, not here.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 `collect` returns 0 defs | Target wrong or all files in skip patterns — check `knowledge/` exclusions |
| Stage 2 validation fails on a batch | Re-dispatch that batch with the failing field names in the prompt; don't hand-edit |
| Stage 3 emits 0 candidates for a domain | Expected for small domains; skip and continue. If it happens for a big domain, lower the scoring threshold in `compare.md` to ≥2 and re-dispatch that domain |
| Stage 4 `candidates.json` empty | Compare found nothing worth confirming — report that honestly, don't force findings |
| Stage 5 scout returns `uncertain` | Valid outcome; it flows through to `ranked.json` as a low-priority tier. Don't re-dispatch just to force a verdict |
| Stage 5 scout returns `false_positive` with reason_code | Counts toward rejection stats; Rank filters it out |
| `reports/duplication/latest/triage.md` is absent during Confirm | Continue; the Confirm brief requires a direct token-overlap check and an explicit note that the sibling report was absent |
| Stage 6 ranks a Light-tier finding above a Priority-tier one | Check `rank_meta.migration_cost`: cheap migration can dominate. Inspect by hand before escalating |
| Multi-way cluster scout fails with "too many members" | Split the cluster: confirm the two highest-similarity pairs separately, note the N-way relationship in the triage |

## Replay case

When changing this skill's owned scripts, replay the smallest script-level
contracts:

```bash
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/collapse_candidates.py --help
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/rank.py --help
.venv/bin/python .claude/skills/find-semantic-duplication/scripts/report.py --help
```

For a full pipeline change, keep a tiny `reports/semantic-duplication/scan-*`
fixture and prove `candidates.json` → `ranked.json` → `triage.md` with pasted
script output. Do not report semantic findings from Compare-only artifacts.

## Repository layout

```
.claude/skills/find-semantic-duplication/
├── SKILL.md                      # this file — orchestrator
├── scripts/
│   ├── collapse_candidates.py    # Stage 4
│   ├── rank.py                   # Stage 6
│   └── report.py                 # Stage 7
├── agents/
│   ├── summarize.md              # Stage 2 scout brief
│   ├── compare.md                # Stage 3 scout brief
│   └── confirm.md                # Stage 5 scout brief
└── knowledge/                    # scout context, never loaded by orchestrator
    ├── false-positives.md
    └── learnings.md
```

`scripts/semantic_inventory.py` (at project root, outside this skill
directory) provides the `collect` / `graph` / `callers` / `artifacts` /
`prompts` / `validate` subcommands used by Stages 1 and 3. It is stdlib-only.

The orchestrator (you) **never reads files in `knowledge/`**. Those are for
the scout sub-agents. Keeping them out of your context is the whole point
of this architecture.
