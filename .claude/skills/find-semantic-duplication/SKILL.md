---
name: find-semantic-duplication
description: Detect behavioral duplication in Python functions through a scout triage pipeline, or produce conservative TypeScript/TSX, checked-JavaScript, Go, Java, PHP, Ruby, Rust, and Dart function-level leads using host-native semantic facts. Semantic branches report bounded static candidates with human review; they do not infer behavioral equivalence, workflows, structural duplication, or safe refactors.
argument-hint: "--target <directory> [--language python|typescript|javascript|go|java|php|ruby|rust|dart]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Two independently-written, live functions that plausibly solve the same
  problem with different code shape. Python uses scout confirmation; TypeScript
  Go, and Java use typed return-shape and direct-call evidence before human review.
not_for: |
  Lexical near-clones (use /find-duplication). Unreferenced implementations
  (use /find-dormant). Consolidation execution follows /unify-shadows proposal
  approval. Unsupported v1 modes are
  workflows, structural/module analysis, protocol/class-method semantics,
  dynamic dispatch, framework behavior, and automatic consolidation.
language: any
framework: any
scans: [python, typescript, javascript, go, java, php, ruby, rust, dart, c, cpp]
install_with: [map-subsystem]
---

# /find-semantic-duplication

## C++20 branch

Use `scripts/detect_cpp_semantic.py` with `_cpp-semantic`; run the script with
`--help` for the exact CLI. It emits static structural leads only for exact
aggregate snippets with distinct direct caller contexts in a current complete
C++20 compiler-owned graph. Namespace/signature/overload identity is exact;
behavioral equivalence, ODR/ABI, specializations, dispatch, external variants,
and consolidation safety are not claimed.

## C17 branch

Use `scripts/detect_c_semantic.py` with the sibling `_c-semantic` provider; run
`python3 scripts/detect_c_semantic.py --help` for the exact CLI. This external-
library branch emits static direct-return/caller review leads only. Aliasing,
undefined behavior, side effects, function pointers, external behavior,
equivalence, and consolidation safety remain unresolved.

## PHP and Ruby

For a selected PHP or Ruby run, load `../_php-semantic/GUIDE.md` or
`../_ruby-semantic/GUIDE.md`. Matching bounded type/constructor shapes become
hash-reviewed leads only, never behavioral-equivalence or consolidation
authority.

## Dart v1

Dart v1 consumes the selected-configuration SDK-LSP fact pack produced by the
sibling `map-subsystem` closure. It emits conservative review leads only for
authored, synchronous, top-level, non-generic free functions with explicit
return types, matching named-constructor return fields, matching resolved
first-party callees, and resolved callers on distinct surfaces. A candidate is
not behavioral equivalence: a content-addressed human verdict is required, and
`keep_separate_document_why` is a valid completed result.

Run from the host root after resolving the two selected on-demand skills:

```bash
FIND_ROOT=".agents/skills/on-demand/find-semantic-duplication"
MAP_ROOT=".agents/skills/on-demand/map-subsystem"
python3 "${MAP_ROOT}/scripts/dart_lsp_facts.py" \
  --project-root "$PWD" --target . \
  --output-dir "$PWD/reports/semantic-duplication/dart/facts"
python3 "${FIND_ROOT}/scripts/detect_dart_semantic.py" \
  --project-root "$PWD" --target . \
  --facts "$PWD/reports/semantic-duplication/dart/facts/facts.json" \
  --output-dir "$PWD/reports/semantic-duplication/dart"
```

The detector excludes generated, test, example, vendor, method, extension,
generic, wrapper, dynamic-dispatch, and partial-evidence shapes. It writes
machine candidates, capability matrices, review templates, and final findings
without editing host source. Generated/part/augmentation/conditional behavior,
reflection, external consumers, Flutter/framework semantics, side effects, and
safe consolidation remain outside the contract.

## Rust v1

Rust v1 emits review leads for bounded free functions with overlapping resolved
return/caller capability facts. It does not prove behavioral equivalence or
authorize consolidation; traits/generics, macros/cfg, unsafe/FFI, runtime
dispatch, and external APIs remain deferred. Copy sibling `map-subsystem`.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-semantic-duplication"
python3 "${SKILL_ROOT}/scripts/detect_rust_semantic.py" \
  --project-root "$PWD" --target . \
  --output-dir "$PWD/reports/semantic-duplication/rust"
```

You are the **orchestrator** for a semantic-duplication audit. Your job is to
drive a pipeline of scripts and sub-agent scouts; the judgment calls live in
the scout briefs and `knowledge/` files, not in this prompt.

Semantic duplication fills a gap between `/find-duplication` (syntactic
clones) and `/find-dormant` (dead code). Two bodies with 0% token overlap
can still solve the same problem — this skill finds those.

## Go v1

For a Go target, read and follow `knowledge/go-v1.md`; load it only for Go
work. The skill-local analyzer uses Go 1.22+ `go list`, `go/parser`, and
`go/types` to produce static review leads. Even a `confirmed` Go record is not
proof of behavioral equivalence and never authorizes a refactor by itself.

## Java 17 v1

For Java, read `knowledge/java-v1.md`. The family-local JDK compiler-tree
analyzer emits only direct static-method pairs that construct the same project
record, name the same returned components, and have resolved production callers.
Even a `confirmed` record is a bounded static lead, never behavioral equivalence.

## TypeScript / TSX v1

Run this separate branch only when the host provides a named project-local
`tsconfig.json` and a `typescript` package installed under that host. The
family-local `detect_typescript.mjs` creates a Compiler API `Program` and
`TypeChecker`, then considers only **typed, top-level function declarations or
block-bodied arrows** that have an explicit return type and at least two
returned object fields.

The confirmed result is intentionally narrow: two functions have the same
TypeChecker return type and returned object shape, different enough token sets
to stay out of `/find-duplication`, no compiler-resolved direct caller→callee
relationship, and compatible throw/try/await policy. A dynamic element call or
a declaration-only/unresolved direct call is an explicit `uncertain` result;
it is never silently clean. Near-lexical pairs, caller→callee wrappers, and
load-bearing policy divergence are `rejected`. Class methods, protocol
implementations, tests, doubles, generated/vendor/declaration files, workflow
claims, structural claims, framework/runtime dispatch, and safe refactoring
are unavailable, not inferred.

Every TypeScript run writes only beneath
`reports/semantic-duplication/<scan>/`: `analysis.json`, `findings.json`,
`triage.md`, and one capability matrix per confirmed finding. The target and
report directory are project-root relative; direct excluded targets yield an
empty report; internal/external symlink targets and unsafe or symlinked report
paths fail before writing. Invalid syntax, a missing/invalid `tsconfig`, or a
missing project-local Compiler API exits 2.

### Installed TypeScript command

Set `SEMANTIC_DUPLICATION_SOURCE` to the pinned skill source/ref, then install
exactly this selected skill from the target host root.

<!-- installed-command:stock-install:start -->
```bash
: "${SEMANTIC_DUPLICATION_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${SEMANTIC_DUPLICATION_SOURCE}" \
  --skill find-semantic-duplication --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

Run the next block from that host root. It uses the host's installed
TypeScript, not a toolkit venv, root script, sibling skill, or network call.

<!-- installed-command:typescript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the TypeScript/TSX file or directory to audit}"
TSCONFIG="${TSCONFIG:-tsconfig.json}"
REPORT_NAME="${REPORT_NAME:-typescript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-semantic-duplication" \
  ".agents/skills/find-semantic-duplication" \
  ".claude/skills/find-semantic-duplication"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-semantic-duplication is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript.mjs" \
  --target "${TARGET}" \
  --project-root "$(pwd)" \
  --tsconfig "${TSCONFIG}" \
  --report-dir "reports/semantic-duplication/${REPORT_NAME}"
```
<!-- installed-command:typescript-scan:end -->

Run the host's native typecheck before and after the audit. A TypeScript
confirmed lead still requires source/caller/runtime review before any
`/fix-workflow semantic:<id>` action.

## Checked JavaScript v1

Use `detect_typescript.mjs --language javascript` only with a host-local
Compiler API and named `jsconfig.json` or `tsconfig.json` that explicitly sets
`allowJs` and `checkJs`. It accepts `.js`, `.jsx`, `.mjs`, and `.cjs`; it can
confirm only pairs with compatible JSDoc or TypeChecker-inferred return shapes
whose direct calls resolve through the program. Dynamic calls, methods,
framework behavior, workflow semantics, and lexical clones remain deferred or
rejected. The final artifact records config, diagnostics, unresolved/uncovered
sources, plus distinct checked-JS, JSDoc, and inferred evidence. Missing
tools/configs are unsupported, malformed JS is syntax-error, and unresolved
or excluded sources are partial. Never use `npx`, a global compiler, or a
generic language platform.

<!-- installed-command:javascript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the checked-JavaScript file or directory to audit}"
JSCONFIG="${JSCONFIG:-jsconfig.json}"
REPORT_NAME="${REPORT_NAME:-javascript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-semantic-duplication" \
  ".agents/skills/find-semantic-duplication" \
  ".claude/skills/find-semantic-duplication"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-semantic-duplication is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript.mjs" \
  --target "${TARGET}" --project-root "$(pwd)" --tsconfig "${JSCONFIG}" \
  --report-dir "reports/semantic-duplication/${REPORT_NAME}" --language javascript
```
<!-- installed-command:javascript-scan:end -->

This is a standalone host-root command: it resolves the selected skill itself
and does not inherit `SKILL_ROOT` from the TypeScript command above.

## Python function-triage branch

The Python branch retains the scout-confirmation journey. Its inventory is now
bundled inside this selected skill and requires `end_line` through every
summary, prompt, candidate, and confirmation record. The prior workflow and
artifact inventory commands are deliberately retired from this branch: they
were generated but never consumed by a confirmation, rank, or report stage, so
claiming them as evidence was misleading. Python remains function-level until a
separately tested workflow/structural consumer exists.

## How success is judged

- No finding reaches `triage.md` without a Stage 5 Confirm scout
  verdict at `scout/<finding_id>.json` — Compare nominations alone
  are never reported.
- Every confirmed cluster has its capability matrix at
  `capability_matrices/<finding_id>.md`; `uncertain` and rejected verdicts
  have separate triage sections, never a shared rejection bucket.
- Finding IDs resolve as `/fix-workflow semantic:<id>` arguments.
- Zero edits to production files — this is a read-only audit.
- The closeout pastes artifact truth: validation `PASS: N/N` lines,
  Stage 4/6/7 script output, and the path to `triage.md`. A claim that
  scouts ran is not enough without the files and validator output.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Must be a directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for the owned ranking/report scripts;
  `python3` is fine for the bundled stdlib-only `semantic_inventory.py`.
- **Project-specific defaults** (domain taxonomy, framework-mandated skips,
  split-by-design exclusions, known suspects): `knowledge/`.
- **Rejection classes:** the function-level entries in
  `knowledge/false-positives.md` — scouts apply these, not you.

## Scout dispatch contract

Every Agent dispatch must declare its judged artifact:

| Stage | Prompt | Judged output |
|---|---|---|
| Summarize | `agents/summarize.md` | JSONL at the substituted `{{output_path}}`, validated with the bundled `semantic_inventory.py validate --schema summary` |
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
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-semantic-duplication}"
INVENTORY="${SKILL_ROOT}/scripts/semantic_inventory.py"
PYTHON="${PYTHON:-python3}"
mkdir -p "${REPORT_DIR}/prompts" "${REPORT_DIR}/summary_batches" \
         "${REPORT_DIR}/scout" "${REPORT_DIR}/capability_matrices"
ln -sfn "scan-${TS}" reports/semantic-duplication/latest
```

### Stage 1 — Inventory

**Pre:** target directory exists. **Post:** `inventory.jsonl` and optional
`callers.jsonl` are present and valid. This function-level branch does not
create unused workflow or artifact inventories.

Run the self-contained `collect` command first. Caller counts are optional
ranking context and may run after inventory collection:

```bash
python3 "${INVENTORY}" collect --target <target> --project-root "$(pwd)" \
  -o "${REPORT_DIR}/inventory.jsonl"
```

```bash
python3 "${INVENTORY}" callers "${REPORT_DIR}/inventory.jsonl" \
  --project-root "$(pwd)" -o "${REPORT_DIR}/callers.jsonl"
```

Validate every output before proceeding (the script emits `PASS: N/N records valid`):

```bash
python3 "${INVENTORY}" validate "${REPORT_DIR}/inventory.jsonl" --schema definition
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
python3 "${INVENTORY}" validate "${REPORT_DIR}/summaries.jsonl" --schema summary
```

If validation fails, re-dispatch the offending batch with a note on which
fields were wrong. Do not hand-fix records — the scout should do it.

### Stage 3 — Compare (parallel fan-out per domain)

**Pre:** `summaries.jsonl` valid. **Post:** one
`${REPORT_DIR}/prompts/candidates_<domain>.json` per domain group.

Generate per-domain prompt files:

```bash
python3 "${INVENTORY}" prompts \
  "${REPORT_DIR}/summaries.jsonl" --output-dir "${REPORT_DIR}/prompts"
```

For each `prompt_<domain>.json` the script wrote, expand `agents/compare.md`
(substitute `{{prompt_path}}`, `{{output_path}}` → `candidates_<domain>.json`
in the same dir, `{{skill_root}}`) and dispatch every scout in a **single
message** so they run concurrently.

The Compare bar is intentionally low — scouts nominate pairs scoring ≥3
(≥4 for Light tier). Better to over-nominate; Confirm has full source and
will filter.

### Stage 4 — Collapse

**Pre:** `prompts/candidates_*.json`. **Post:**
`${REPORT_DIR}/candidates.json` — per-domain function pairs merged into multi-way
clusters via union-find on shared `(file, qualified_name)` sites.

```bash
"${PYTHON}" "${SKILL_ROOT}/scripts/collapse_candidates.py" \
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

This is the **deep-read stage**. Scouts read full function bodies and apply the
function-level rejection classes from `knowledge/false-positives.md` (Compare
only applied the cheap ones).

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
"${PYTHON}" "${SKILL_ROOT}/scripts/rank.py" \
  --confirmed "${REPORT_DIR}/scout" \
  --callers "${REPORT_DIR}/callers.jsonl" \
  --output "${REPORT_DIR}/ranked.json"
```

Ranking formula:
`ROI = (shared_lines × maintenance_risk × level_multiplier) / max(migration_cost, 1)`.
The current Python reference path ranks function findings at multiplier 1.0.
See `rank.py` for the tier cutoffs.

### Stage 7 — Report

**Pre:** `ranked.json`. **Post:** `${REPORT_DIR}/triage.md` and
`${REPORT_DIR}/findings.json`.

```bash
"${PYTHON}" "${SKILL_ROOT}/scripts/report.py" \
  --input "${REPORT_DIR}/ranked.json" \
  --output-md "${REPORT_DIR}/triage.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}"

```

### Stage 8 — Summarize

Report to the user in ≤10 lines:

- Counts by tier (P0 / P1 / P2) plus confirmed / uncertain / rejected function candidates,
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
| Stage 5 scout returns `uncertain` | Valid outcome; `ranked.json` and `triage.md` retain it in a separate Uncertain section. Don't re-dispatch just to force a verdict |
| Stage 5 scout returns `false_positive` with reason_code | Counts toward rejection stats; Rank filters it out |
| `reports/duplication/latest/triage.md` is absent during Confirm | Continue; the Confirm brief requires a direct token-overlap check and an explicit note that the sibling report was absent |
| Stage 6 ranks a Light-tier finding above a Priority-tier one | Check `rank_meta.migration_cost`: cheap migration can dominate. Inspect by hand before escalating |
| Multi-way cluster scout fails with "too many members" | Split the cluster: confirm the two highest-similarity pairs separately, note the N-way relationship in the triage |

## Replay case

When changing this skill's owned scripts, replay the smallest script-level
contracts:

```bash
python3 .claude/skills/find-semantic-duplication/scripts/semantic_inventory.py --help
python3 .claude/skills/find-semantic-duplication/scripts/collapse_candidates.py --help
python3 .claude/skills/find-semantic-duplication/scripts/rank.py --help
python3 .claude/skills/find-semantic-duplication/scripts/report.py --help
node --check .claude/skills/find-semantic-duplication/scripts/detect_typescript.mjs
python3 .claude/skills/find-semantic-duplication/scripts/detect_go_semantic.py --help
python3 -I -S .claude/skills/find-semantic-duplication/scripts/detect_java_semantic.py --help
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
│   ├── report.py                 # Stage 7
│   ├── semantic_inventory.py     # Python function inventory / prompts
│   ├── detect_typescript.mjs     # TypeScript Compiler API final triage
│   ├── detect_java_semantic.py    # Java launcher / final artifacts
│   └── detect_java_semantic.java  # JDK compiler-tree fact collector
├── agents/
│   ├── summarize.md              # Stage 2 scout brief
│   ├── compare.md                # Stage 3 scout brief
│   └── confirm.md                # Stage 5 scout brief
└── knowledge/                    # scout context, never loaded by orchestrator
    ├── false-positives.md
    └── learnings.md
```

`scripts/semantic_inventory.py` is bundled in this skill and provides the
`collect` / `callers` / `prompts` / `validate` subcommands used by the Python
function path. It is stdlib-only and remains available after a selected-skill
copy install.

The orchestrator (you) **never reads files in `knowledge/`**. Those are for
the scout sub-agents. Keeping them out of your context is the whole point
of this architecture.
