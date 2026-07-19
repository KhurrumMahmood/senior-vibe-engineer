---
name: find-omnibus
description: Detect omnibus modules — files answering questions from 3+ independently-understandable domains. Uses exact Python AST spans, a legacy JavaScript heuristic, and a bundled TypeScript Compiler API parser for ESM `.ts`/`.tsx` top-level functions, typed arrows, and classes; then groups symbols by head-noun cluster, ranks candidates, and produces decomposition evidence. Never edits code.
argument-hint: "--target <directory> [--language python|javascript|typescript]"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Files answering questions from 3+ unrelated domains — the SRP "and"
  test counts 3+ "and"s. Ranks by responsibility count, then boosts
  files that mix credentials, admin APIs, CSRF/auth, command/network
  diagnostics, persistence, raw SQL, import/export, task dispatch, or
  filesystem writes; produces decomposition candidates that hand off
  to /refactor-subsystem. Covers Python (exact) and JavaScript/
  TypeScript (Compiler API syntax spans for ESM top-level functions, typed
  arrows, and classes; findings carry analyzer provenance). TypeScript needs
  Node and the host's project-local `typescript` package, but no tsconfig or
  framework.
not_for: |
  Single-responsibility files that are merely large (cohesive >500 LOC
  is fine — avoid splitting for size alone). Layer violations
  specifically in views (use /find-layer-violation). Refactor
  execution (use /refactor-subsystem in decomposition mode).
  Languages without an extraction adapter yet — check
  /find-perimeter-gaps for what is and isn't covered.
language: any
framework: any
scans: [python, typescript]
scout_model: cheap
---

# /find-omnibus

You are the **orchestrator** for an omnibus-module audit. Your job is
to drive a detector + a scout-verification fan-out; the judgment calls
(facet vs domain, known false-positive shapes, decomposition sketch)
live in the scout brief and the knowledge files, not in this prompt.

The four buckets (`confirmed_omnibus`, `borderline`,
`coordination_omnibus`, `facets_not_domains`), the facet-vs-domain
evaluation rule, and the
decomposition-sketch format are documented in
`knowledge/verification.md` — scouts read it, you don't.

## How success is judged

- Every reported candidate carries a Stage 3 scout verdict at
  `scout/<candidate_id>.json`, bucketed by the facet-vs-domain rule
  (`confirmed_omnibus` / `borderline` / `coordination_omnibus` /
  `facets_not_domains`) — no detector hit reaches `report.md` ungraded.
- The closeout pastes the real Stage 1/2/4 stderr lines
  (`[detect_omnibus]`, `[collapse]`, `[report]`) plus the scout JSON
  count; claims without those artifacts do not satisfy the audit.
- The substrate gate (ADR 0032 rule 3) ran before any decomposition
  recommendation; failing layers get "substrate ADR first", not a spec.
- The handoff is named: `/refactor-subsystem <spec-id>` for confirmed
  candidates, `/map-product-workflow` for `coordination_omnibus`.
- Zero code edits — read-only audit.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Must be a
  directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (detectors are stdlib-only, but this
  repo runs them through the venv for consistent tooling).
- **TypeScript v1:** Node plus `typescript` resolvable from the target
  project's `package.json`. The bundled parser needs syntax spans only; it
  deliberately does not read `tsconfig`, resolve modules, inspect types, or
  infer framework behavior. Missing prerequisites fail Stage 1 clearly.
- **Project-specific defaults** (generic-verb strip list, skip
  patterns, directory-package precedent, known false-positive
  shapes): in `knowledge/`.
- **Coordination omnibus rule:** broad workflow coordinators such as
  `app/views/site_config.py` may be real omnibus files even when most
  domain behavior has moved out. Bucket them as `coordination_omnibus`
  when the next improvement is a workflow registry or route ownership
  map, not another service extraction.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `.venv/bin/python` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/omnibus/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/omnibus/latest
```

### Stage 1 — Detect

**Pre:** target directory exists. **Post:** `omnibus.jsonl` with one
record per flagged file (score-sorted by responsibility count, then
security/side-effect sensitivity, then LOC).

```bash
.venv/bin/python .claude/skills/find-omnibus/scripts/detect.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/omnibus.jsonl"
```

### Stage 2 — Collapse

**Pre:** `omnibus.jsonl`. **Post:** `${REPORT_DIR}/candidates.jsonl` —
top-30 candidates with `candidate_id` assigned.

```bash
.venv/bin/python .claude/skills/find-omnibus/scripts/collapse.py \
  --detections "${REPORT_DIR}/omnibus.jsonl" \
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
a specific subset (e.g., "only the views"), filter before dispatch.

For each candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{output_path}}`) and dispatch with
`subagent_type=general-purpose`. Send all Agent calls in a **single
message** so they run concurrently.

Declare the verdict to every scout: its output is accepted only if it
writes valid JSON at `{{output_path}}`, uses one of the four buckets,
records `domains_confirmed` and `facets_collapsed`, and provides
`decomposition_depth_note` for confirmed omnibus files. When merging,
reject or re-dispatch malformed scout files; do not let `report.py`
turn an unverified candidate into a decomposition recommendation.

If a scout returns invalid JSON or flags the verification as aborted,
re-dispatch once with a stricter "respond only with file-write
confirmation" nudge; skip the candidate if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the four buckets in `verify.md` (`confirmed_omnibus` /
`borderline` / `coordination_omnibus` / `facets_not_domains`), no cross-
file synthesis, no shell. That makes it safe on Haiku-class scouts.

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
        .claude/skills/find-omnibus/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-omnibus" \
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
`borderline` and a stronger model's judgment is worth the cost.

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-omnibus/scripts/report.py \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --scout-dir "${REPORT_DIR}/scout" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

```

The four scripts in this skill are self-contained; a host may record an
effectiveness event separately, but that optional repository concern is not
part of the selected-skill runtime.

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (`confirmed_omnibus` / `borderline` /
  `coordination_omnibus` / `facets_not_domains` / `unverified`),
- top 3 candidates (one line each: file, and-count, risk signals,
  recommendation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command — for the worst confirmed candidate,
  `/refactor-subsystem <spec-id>` in decomposition mode. Remind the
  user that the spec must be scaffolded first under
  `ai-docs/specs/<id>.md` (Phase 0 of `/refactor-subsystem` handles
  the stub).
  For `coordination_omnibus`, prefer `/map-product-workflow` and
  `/extract-workflow-registry` before decomposition.

**Substrate gate (ADR 0032 rule 3).** Before recommending
decomposition for any confirmed candidate, check the target layer's
substrate: (a) a module/import mechanism, (b) test infrastructure
that can pin behavior across the split, (c) infrastructure helpers
(fetch/escape/log wrappers) that exist once, not per-file. Python
targets in a tested package pass trivially. A script-tag JavaScript
file with no module system fails (a) and usually (b) — splitting it
just multiplies globals. When any leg fails, the recommendation is
**re-architect: substrate ADR first** (module mechanism, test story,
shared-helper home), with a grandfathered size-growth lint as the
interim control — not a decomposition spec. Findings from heuristic
adapters (``analyzer != python-ast``) deserve a skim of the actual
file before this call; coarse extraction can over- or under-cluster.

The report is the source of truth — do not enumerate every candidate.

## Replay case

When `detect.py`, `collapse.py`, `report.py`, or the scout JSON schema
changes, replay a disposable Python target with one file containing
three independently understandable domains (for example credentials
loading, export rendering, and task dispatch) plus one cohesive helper
file. Expected evidence: Stage 1 writes exactly one omnibus candidate
for the multi-domain file; Stage 2 preserves that candidate; after a
hand-written scout JSON that buckets it as `confirmed_omnibus`, Stage 4
writes `report.md` and `findings.json` with one decomposition
recommendation and no finding for the cohesive helper.

## Non-goals

- Executing decompositions (that's `/refactor-subsystem` after user
  approval).
- Editing or deleting code — read-only audit.
- Detecting duplication (that's `/find-duplication` /
  `/find-semantic-duplication`).
- Detecting layer violations (that's `/find-layer-violation`).
- Running tests — the report is the output; tests run during
  `/refactor-subsystem`.
- CI gates — periodic audit, not a per-commit check.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 detector reports 0 candidates | Target has no omnibus files (best outcome) — or scope is too narrow; try a wider target like the source root |
| Any script exits non-zero | Stop at the failing stage, paste the exact command and stderr, and do not summarize downstream artifacts from a previous run |
| Stage 1 reports a clearly-cohesive file | Raise the `and_count >= 3` threshold in `detect.py` OR add the file's shape to `knowledge/` false-positive filter |
| Stage 2 caps too aggressively | Pass `--top 50` or higher to `collapse.py` |
| Stage 3 scout buckets everything as `facets_not_domains` | Scout is being too aggressive at collapsing — re-dispatch citing the "3+ confirmed domains" rule from `verification.md` |
| Stage 3 scout buckets everything as `confirmed_omnibus` | Scout isn't applying the facet rule — re-dispatch citing the refactor-subsystem §1.2.5 worked examples in `verification.md` |
| Report's `recommendation` field disagrees with bucket | Scout error; reconcile using the bucket-recommendation mapping in `report.py` |

## Repository layout

```
.claude/skills/find-omnibus/
├── SKILL.md                  # this file — orchestrator
├── scripts/
│   ├── detect.py             # Stage 1 — Python/JS/TS cluster extraction
│   ├── detect_typescript_symbols.mjs  # bundled Compiler API TS/TSX spans
│   ├── collapse.py           # Stage 2 — cap to top-N, assign ids
│   └── report.py             # Stage 4 — render report.md + findings.json
├── agents/
│   └── verify.md             # Stage 3 scout brief
└── knowledge/                # sub-agent context, never loaded by orchestrator
    └── verification.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
