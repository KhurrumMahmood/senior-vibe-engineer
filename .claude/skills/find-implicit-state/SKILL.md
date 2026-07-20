---
name: find-implicit-state
description: Detect Django stringly-typed state and tuple-inferred identity patterns, plus narrow TypeScript and checked-JavaScript closed-state branches. The compiler branches distinguish first-party bare state operations from typed authorities, vendor wire boundaries, tests/fixtures, unrelated status text, and open-ended strings. Detection-only — never edits production code.
argument-hint: "--target <directory> [--language typescript|javascript]"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Stringly-typed status / phase / state comparisons against bare
  literals; `.filter(status=..., *_at__...)` tuple-inferred identity.
  Targets the stringly-typed-state smell. Decided in: 0001
  (TextChoices for state).
  In TypeScript, closed state receivers with repeated bare string
  comparisons or assignments and a host-owned Compiler API.
not_for: |
  Refactor execution — hands off to /extract-enum or /introduce-fk
  for the proposal, then /fix-workflow for execution. Lexical
  duplication on jscpd-only matches (use /find-duplication).
  Untyped/open-ended TypeScript strings, TypeScript ORM semantics, and a
  generic TypeScript lint generator.
language: any
framework: any
scans: [python, typescript, javascript]
scout_model: cheap
---

# /find-implicit-state

You are the **orchestrator** for an implicit-state audit. Your job is
to drive a pipeline of detectors and sub-agent verifiers; the bucket
judgment calls live in the scout brief and the knowledge files, not in
this prompt.

The two sub-patterns (stringly-typed state, tuple-inferred identity),
the four buckets (extract_enum_candidate, introduce_fk_candidate,
enum_already_used, legacy_allow_list), and the verification checklist
are documented in `knowledge/verification.md` — scouts read it, you
don't.

## How success is judged

- Every reported candidate carries a Stage 3 scout verdict at
  `scout/<candidate_id>.json` in one of the four buckets
  (`extract_enum_candidate` / `introduce_fk_candidate` /
  `enum_already_used` / `legacy_allow_list`), with the hit evidence
  attached — nothing reaches `report.md` ungraded.
- The closeout pastes the real Stage 1/2/4 stderr lines
  (`[detect_implicit_state]`, `[collapse_implicit_state]`,
  `[report_implicit_state]`) plus the scout JSON count; claims without
  those artifacts do not satisfy the audit.
- Each actionable candidate is routed to its named handoff:
  `/extract-enum <symbol>` or `/introduce-fk <symbol>`.
- Zero edits to production code — detection-only audit.
Write toward these gates from Stage 0.

## TypeScript closed-state branch

Use this branch only for .ts / .tsx code whose first-party
state/status/phase receiver resolves to a closed string-literal union or
project-native enum. Its supported outcome is evidence for replacing repeated
first-party bare literals with an exported as const runtime value object and a
derived union type. It does not claim a TypeScript ORM, migration,
tuple-identity, or general text-literal detector.

The bounded syntax contract covers direct property comparisons, reversed
comparisons, one-hop local `const` aliases initialized directly from the
property, plain and `??=` assignments, and every property target in a chained
assignment. Vendor attribution comes from an explicit semantic receiver type
named `Vendor*Payload|Request|Response|Event|Message|Wire`; filenames and
nearby text never establish a vendor boundary. Parentheses are transparent
around state operands, direct alias initializers, literals, and chained
assignment expressions. Computed properties, other assertion wrappers, and
general dataflow remain out of scope. Invalid TypeScript exits 2.

**Host prerequisites:** the target project owns a compatible typescript package
and a readable tsconfig.json. The launcher resolves typescript from that
project's package.json; it never uses a toolkit, global, or downloaded
compiler. A missing package or tsconfig is a clear exit 2, not a lexical
fallback.

Run this branch instead of Python Stages 1–4:

    REPORT_DIR="reports/implicit-state/scan-typescript-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$REPORT_DIR"
    node .claude/skills/find-implicit-state/scripts/detect_typescript_state.mjs \
      --target "$(pwd)" \
      --project-root "$(pwd)" \
      --tsconfig "$(pwd)/tsconfig.json" \
      --output "$REPORT_DIR/findings.jsonl"

Grade the run from the emitted JSONL and stderr line
[detect_typescript_state]: it must contain first-party operations only for the
migration candidate, while retaining classification records for typed
authorities, vendor wire boundaries, tests/fixtures, unrelated status text,
and open-ended strings. Hand that exact JSONL to the TypeScript branch of
/extract-enum; do not run the Django collapse/scout/report stages on it.

## Checked JavaScript closed-state branch

Use this branch only with a host-local `typescript` Compiler API and an
explicit `jsconfig.json` or `tsconfig.json` that enables both `allowJs` and
`checkJs`. It accepts `.js`, `.jsx`, `.mjs`, and `.cjs`, but promotes an
operation only when the receiver has a demonstrated finite JSDoc authority;
untyped/open strings remain classification evidence, never a migration lead.
The manifest records the config, diagnostics, unresolved modules, uncovered
sources, compiler-parsed JSDoc, and TypeChecker inference. A missing tool or
config is unsupported, malformed selected JS is syntax-error, and any
unresolved/excluded source is partial. Do not use `npx`, a global compiler,
or framework inference.

```bash
node .claude/skills/find-implicit-state/scripts/detect_typescript_state.mjs \
  --target src --project-root "$(pwd)" --tsconfig "${JSCONFIG:-jsconfig.json}" \
  --output reports/implicit-state/javascript.jsonl \
  --manifest reports/implicit-state/javascript.manifest.json --language javascript
```

## Scope

- **Target path:** the required `--target` argument. Must be a
  directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` in this repository; the bundled detector,
  collapse, and reporter are stdlib-only and run with host `python3` after a
  stock installation.
- **Project-specific defaults** (known enums, tuple-identity hot
  spots, noqa conventions, detection gaps): in
  `knowledge/`.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `.venv/bin/python` and capture stderr so
failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/implicit-state/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/implicit-state/latest
```

### Stage 1 — Detect

**Pre:** target directory exists. **Post:** `${REPORT_DIR}/hits.jsonl`
present.

```bash
.venv/bin/python .claude/skills/find-implicit-state/scripts/detect.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/hits.jsonl"
```

The detector surfaces four hit shapes: `stringly_compare`,
`stringly_field`, `possible_state_literal`, `tuple_identity`. It does
not resolve cross-module enum references; the scout does that at
Stage 3.

### Stage 2 — Collapse

**Pre:** `hits.jsonl`. **Post:** `${REPORT_DIR}/candidates.jsonl` —
one record per `(file, pattern)` bucket with hit count, confidence
tier, fields/symbols touched, and a recommendation hint.

```bash
.venv/bin/python .claude/skills/find-implicit-state/scripts/collapse.py \
  --hits "${REPORT_DIR}/hits.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl"
```

Confidence tiers:

- `high` — every `tuple_identity` hit, or any `stringly_compare` group
  with ≥3 hits on the same field in one file.
- `medium` — `stringly_field` groups, `stringly_compare` below the
  ≥3-same-field threshold, `possible_state_literal` groups in files
  that also have a `stringly_compare` hit.
- `low` — `possible_state_literal` in files with no compare hits.

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

1. `tuple_identity` hits first — rare and load-bearing.
2. `stringly_compare` groups with ≥3 hits on the same field.
3. `stringly_field` groups (model declarations).
4. Remaining medium-confidence groups.

If the user asked for a deeper scan, raise the budget. If the user
asked for a specific file, filter candidates to that path before
dispatch.

For each selected candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{output_path}}`) and dispatch with
`subagent_type=general-purpose`. Send all Agent calls in a **single
message** so they run concurrently.

Declare the verdict to every scout: its output is accepted only if it
writes valid JSON at `{{output_path}}`, uses one of the four buckets,
preserves the `candidate_id`, and includes the hit evidence fields from
the schema. When merging, reject or re-dispatch malformed scout files;
do not let `report.py` turn an unverified candidate into an actionable
handoff.

If a scout returns invalid JSON, re-dispatch once with a stricter
"respond only with file-write confirmation" nudge; skip the candidate
if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the four buckets in `verify.md` (`extract_enum_candidate`
/ `introduce_fk_candidate` / `enum_already_used` / `legacy_allow_list`).
The scout reads the enclosing function and one noqa-grep, no cross-file
synthesis, no shell. Safe on Haiku-class scouts.

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
        .claude/skills/find-implicit-state/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-implicit-state" \
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
interactively and the user is watching, or (b) a tuple-identity
candidate is genuinely ambiguous between identity and freshness usage
and warrants the better model.

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-implicit-state/scripts/report.py \
  --scout-dir "${REPORT_DIR}/scout" \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

# Effectiveness log — one line per run. Buckets come from findings.json.
.venv/bin/python scripts/log_effectiveness.py \
  --skill find-implicit-state \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (extract_enum_candidate / introduce_fk_candidate /
  enum_already_used / legacy_allow_list),
- counts by pattern (stringly_compare / stringly_field /
  possible_state_literal / tuple_identity),
- top 3 candidates (one line each: file, pattern, recommendation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command (`/extract-enum <symbol>`,
  `/introduce-fk <symbol>`, or `/find-implicit-state` again after
  cleanup).

The report is the source of truth — do not enumerate every candidate.

## Replay case

When `detect.py`, `collapse.py`, `report.py`, or the scout JSON schema
changes, replay a disposable Python target with one model containing
`status = models.CharField(...)` without `TextChoices`, one function that
compares `job.status == "pending"`, and one tuple-identity
`.filter(status=..., *_at__...).first()` shape. Expected evidence:
Stage 1 writes `hits.jsonl` with both stringly-state and tuple-identity
hits; Stage 2 writes at least two candidates; after hand-written scout
JSON files for one `extract_enum_candidate` and one
`introduce_fk_candidate`, Stage 4 writes `report.md` and `findings.json`
whose bucket counts match the scout files.

## Non-goals

- Writing the TextChoices enum proposal (that's `/extract-enum`).
- Writing the FK + data-migration proposal (that's `/introduce-fk`).
- Executing any refactor (that's `/fix-workflow` after proposal
  approval).
- Running tests — read-only audit; tests run during the refactor
  skill.
- CI gates — periodic audit, not a per-commit check. The lint rules
  `stringly-status` and `query-mutation` cover per-commit guarding.
- Resolving cross-module TextChoices references — the detector skips
  these; the scout reads the model file to confirm.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 detect.py finds 0 hits | Target has no implicit state (best outcome) — or the directory argument is wrong. Re-run with a valid `--target <dir>` |
| Any script exits non-zero | Stop at the failing stage, paste the exact command and stderr, and do not summarize downstream artifacts from a previous run |
| Stage 1 detect.py is slow (>2 min) | Shouldn't happen on a typical source tree — check for `__pycache__` entries in target. Add more `--skip-file-glob` flags if needed |
| Stage 2 reports 0 candidates | Same as Stage 1 zero — or collapse ignored all hits (check stderr) |
| Stage 3 scout buckets everything as `enum_already_used` | Scout is being too permissive. Inspect one output; re-dispatch with "consult `knowledge/` for known enum list" |
| Scout recommends `/introduce-fk` for a freshness-check hit | Rule 1 in `verify.md` was skipped — re-dispatch citing `freshness_not_identity` |
| Report lists noqa'd candidates as actionable | Detector-only bug — the scout should have bucketed as `legacy_allow_list`. Re-dispatch with a `# noqa` grep in the prompt |

## Repository layout

```
.claude/skills/find-implicit-state/
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
