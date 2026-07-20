---
name: find-dormant
description: Detect dead and quasi-dead code without changing source. Python retains vulture, AST, URL, silent-catch, and scout verification stages; TypeScript/TSX and checked JavaScript use a host-pinned Compiler API Program/TypeChecker to report non-exported, statically unreferenced top-level implementation candidates for human review. Never infers safe deletion from static evidence.
argument-hint: "--target <directory-or-file> [--language python|typescript|javascript]"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  TypeScript private implementations that appear statically unreferenced and
  need a conservative dormant-code review with no safe-deletion claim.
  Detecting dead and quasi-dead Python code, unused URL patterns,
  defined-but-unreferenced symbols. Validates against real call sites
  and template URL-name usage; cross-checks git-log recency. Never
  deletes — surfaces evidence for /fix-workflow delete:<id>. TypeScript/TSX
  v1 reports only non-exported top-level implementations with zero resolved
  static symbol references, and always requires human runtime review.
not_for: |
  Removing findings (use /fix-workflow delete:<id>). Architectural
  smells like omnibus or layer violation (use those /find-* skills).
  Semantic duplication where two live behaviors coexist (use
  /find-semantic-duplication). Routes/endpoints, error swallowing,
  dynamic imports, external consumers, registry/event/framework reachability,
  or safe-deletion decisions are outside the static v1 contract.
language: any
framework: any
scans: [python, typescript, javascript]
scout_model: cheap
---

# /find-dormant

<!-- Legacy copied-install metadata token: scans: [python, typescript] -->

You are the **orchestrator** for a dormant-code audit. Your job is to
drive a pipeline of detectors and sub-agent verifiers; the judgment
calls live in the scout brief and the knowledge files, not in this
prompt.

The four flavors of dormant (literal-dead, orphan-endpoint,
silently-broken, orphan-entry-with-live-internals) and the 6-step
verification are documented in
`knowledge/verification.md` — scouts read it, you don't.

## TypeScript / TSX v1

Use this separate branch only when the host supplies a named, project-local
`tsconfig.json` and a `typescript` package installed under that host. The
family-local Compiler API `Program` and `TypeChecker` identify **non-exported
top-level functions, classes, and function-valued variables** with no resolved
static symbol references in eligible `.ts`/`.tsx` project files.

The result is a human-review candidate, never a deletion verdict. Dynamic and
external consumers, registries, event handlers, framework callbacks, routes,
endpoints, error swallowing, and runtime imports are outside the static model.
The TypeScript branch must never infer safe deletion from a static result.
In particular, registry, event, and framework callback shapes must not become
static deletion candidates merely because their runtime dispatch is unknown.
An exact matching string name is emitted as `uncertain`, not a candidate. A
missing/invalid `tsconfig`, missing project-local Compiler API, or TypeScript
syntax error exits 2. Unresolved static module specifiers produce a final
`partial` report; they are never silently represented as a clean project.

The TypeScript detector accepts a file or directory target, applies the same
project-root-relative exclusion policy to broad and direct targets, and never
follows an internal or external symbolic link. It writes only
`reports/find-dormant/<scan>/report.md` and `findings.json`; report directories
outside that location or through a symlink are rejected before a write.

### Installed TypeScript command

Set `FIND_DORMANT_SOURCE` to the pinned skill source/ref, then install exactly
this selected skill. From the host root, run the second command with the target
and tsconfig that should be audited. It uses no toolkit Python environment,
repository script, sibling skill, or network access after installation.

<!-- installed-command:stock-install:start -->
```bash
: "${FIND_DORMANT_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${FIND_DORMANT_SOURCE}" \
  --skill find-dormant --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

<!-- installed-command:typescript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the TypeScript/TSX file or directory to audit}"
TSCONFIG="${TSCONFIG:-tsconfig.json}"
REPORT_NAME="${REPORT_NAME:-typescript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/find-dormant" \
  ".claude/skills/find-dormant"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-dormant is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript_dormant.mjs" \
  --target "${TARGET}" \
  --project-root "$(pwd)" \
  --tsconfig "${TSCONFIG}" \
  --report-dir "reports/find-dormant/${REPORT_NAME}"
```
<!-- installed-command:typescript-scan:end -->

Run the host's native `npm run typecheck` and tests before and after the audit.
The detector reports its own named-tsconfig resolution state, but does not
repair host diagnostics or establish runtime reachability.

## Checked JavaScript v1

Use this branch only with an explicit host `jsconfig.json` or `tsconfig.json`
that sets both `compilerOptions.allowJs` and `compilerOptions.checkJs` to
`true`, plus the project's own installed `typescript` package. It accepts
`.js`, `.jsx`, `.mjs`, and `.cjs`, records compiler-parsed JSDoc and
TypeChecker-inferred evidence, and never falls back to `npx`, a global
compiler, framework naming, or lexical reachability guesses. Unresolved
modules, diagnostics, and selected files absent from that config make the
final artifact `partial`; malformed selected JS is a syntax-error and a
missing compiler/config is unsupported.

```bash
node "${SKILL_ROOT}/scripts/detect_typescript_dormant.mjs" \
  --target "${TARGET}" --project-root "$(pwd)" --tsconfig "${JSCONFIG:-jsconfig.json}" \
  --report-dir "reports/find-dormant/${REPORT_NAME:-javascript-scan}" --language javascript
```

CommonJS exports and matching string/dynamic-registration evidence are
conservative boundaries, not dormant candidates. The result remains
human-review-only and never authorizes deletion.

## How success is judged

- Every Python deletion candidate in `${REPORT_DIR}/report.md` carries a
  Stage 3 scout verdict at `scout/<candidate_id>.json` with call-site
  evidence and a bucket (`certain_delete` / `orphan_endpoint` /
  `quasi_dead_broken` / `false_positive`); recency was checked.
- `external_api_risk` orphan endpoints are flagged for human
  confirmation, never bucketed `certain_delete` silently.
- Every TypeScript final report carries explicit `review_required` and
  `uncertain` counts plus `certain_delete: 0`; no static finding crosses into a
  Python scout/deletion bucket.
- Nothing is deleted — recommendations route to `/fix-workflow
  delete:<name>` or `fix:<name>` after user authorization.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Python requires a
  directory; TypeScript v1 accepts a `.ts`/`.tsx` file or directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **TypeScript v1:** Node plus a project-local `typescript` package and named
  tsconfig. Its static program/type-checker model is intentionally separate
  from the Python/Django detector and scout pipeline.
- **Project-specific defaults** (grep locations, Django false
  positives, dynamic-dispatch patterns, candidate skip list): in
  `knowledge/`.

## Feature Graduation Sweep

Run a focused dormant sweep after a prototype graduates into a real
workflow or after a page/JS entry point is removed. Dead prototype
templates, routes, and static JS with no unique product knowledge
should be deletion candidates, not kept alive with compatibility
aliases. Git history is the archive; live code should be loaded,
explicitly quarantined with a reason, or removed.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `.venv/bin/python` and capture
stderr so failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/dormant/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/dormant/latest
```

### Stage 1 — Detect (four in parallel)

**Pre:** target directory exists. **Post:** four files present:
`vulture.txt`, `url_patterns.jsonl`, `unreferenced_defs.jsonl`,
`silent_catches.jsonl`.

Run all four commands concurrently in one Bash message. None depends
on another — they all write independent outputs that collapse merges.

```bash
# 1. vulture — standard dead-code tool, min-confidence 80 for precision.
#    `|| true` because vulture exits non-zero on any finding.
.venv/bin/python -m vulture <target> \
  --min-confidence 80 \
  --exclude "migrations/,tests_*.py,test_*.py,vendor_*.py,staticfiles/,sites/*/scrape.py" \
  > "${REPORT_DIR}/vulture.txt" 2>&1 || true

# 2. URL patterns — for the orphan-endpoint check. Follows include() to
#    find patterns defined in api_urls.py, admin_urls.py, etc.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_urls.py \
  --root-urls <path/to/urls.py> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/url_patterns.jsonl"

# 3. AST "defined but never referenced" — errs toward candidates;
#    scouts do the real verification.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_unreferenced.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/unreferenced_defs.jsonl"

# 4. Silent catches — Flavor-3 detector. Every `except Exception: pass`
#    / `return None` / `continue` / log-and-return handler in the tree.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_silent_catches.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/silent_catches.jsonl"
```

### Stage 2 — Collapse

**Pre:** all four Stage-1 outputs. **Post:** `${REPORT_DIR}/candidates.jsonl` —
one record per candidate with `candidate_id`, `sources`, `hints`.

Silent catches stay as their own candidates. Vulture and unreferenced
dedupe when they flag the same (file, line, name). URL patterns are
passed through as a lookup table the scout reads in 6a; they do not
become standalone candidates.

```bash
.venv/bin/python .claude/skills/find-dormant/scripts/collapse.py \
  --vulture "${REPORT_DIR}/vulture.txt" \
  --url-patterns "${REPORT_DIR}/url_patterns.jsonl" \
  --unreferenced "${REPORT_DIR}/unreferenced_defs.jsonl" \
  --silent-catches "${REPORT_DIR}/silent_catches.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl"
```

### Stage 3 — Verify (parallel fan-out)

**Pre:** `candidates.jsonl`. **Post:** `${REPORT_DIR}/scout/<candidate_id>.json`
for every verified candidate.

This is the **only stage where LLM judgment runs**. You do not verify
candidates yourself — dispatch one sub-agent per candidate (or batch
if there are many). Each sub-agent receives:

- the candidate JSON (one line from `candidates.jsonl`),
- the prompt template from `agents/verify.md`,
- paths to `knowledge/*` files and `url_patterns.jsonl`,
- an output path it must write to.

**Budget:** verify up to **25 candidates by default**, prioritizing in
this order:

1. **silent_catches first** — Flavor-3 surfaces hide real bugs.
2. **unreferenced with `url_wired_hint: true`** — likely orphan
   endpoints (Flavor 2/4).
3. **vulture ∪ unreferenced** — literal-dead candidates (Flavor 1).

If the user asked for a deeper scan, raise the budget. If the user
asked for a specific subset (e.g., "only the silent catches"), filter
before dispatch.

For each candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{url_patterns_path}}`, `{{output_path}}`) and
dispatch with `subagent_type=general-purpose`. Send all Agent calls in
a **single message** so they run concurrently.

If a scout returns invalid JSON or flags the verification as aborted,
re-dispatch once with a stricter "respond only with file-write
confirmation" nudge; skip the candidate if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the four flavors in `verify.md`, no cross-file
synthesis, no shell. That makes it safe on Haiku-class scouts and the
right place to dogfood the cheap-fan-out path.

For nesting-safe + low-cost fan-out, dispatch each candidate as a
host `tools/code_agent.py --read-only` subprocess via
`.claude/skills/_common/dispatch_scout_cheap.sh`. The `--read-only`
flag drops bash, spawn_agent, claude_tools, and validate_jsonld — the
scout has only read_file/write_file/glob/grep, with workdir
containment enforced (commit `168ca3c1`). Cheap models can't
hallucinate calls to tools that aren't in the registry.

Caveat: the cheap-dispatch path requires the host `tools.code_agent` backend (`<!-- host-adapter -->`); when it is absent, fall back to inline scouting for Stage 3 and record that fallback.

```bash
# One subprocess per candidate; parallelize with `&` + wait.
while read -r line; do
    cid=$(jq -r '.candidate_id' <<<"$line")
    out="${REPORT_DIR}/scout/${cid}.json"
    .claude/skills/_common/dispatch_scout_cheap.sh \
        .claude/skills/find-dormant/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-dormant" \
        url_patterns_path="${REPORT_DIR}/url_patterns.jsonl" \
        output_path="$out" &
done < "${REPORT_DIR}/candidates.jsonl"
wait
```

**Tradeoffs.** Cheap subprocess dispatch adds ~2-4s spawn per scout
and runs the host adapter's default Haiku-class model; the optional
model alias registry (`tools/agent-config.json`) is a
`<!-- host-adapter -->` file and is not shipped in this toolkit repo.
Set `DISPATCH_SCOUT_MODEL` only when the host adapter provides that
alias. The `Agent` tool path is faster (~0s spawn) and uses the
orchestrator's session model (Sonnet/Opus tier — more judgment,
billed). Use the cheap subprocess by default when the host backend is
available; fall back to inline scouting when it is not, or to `Agent`
when (a) only a handful of candidates need verification interactively
and the user is watching, or (b) a candidate's flavor is genuinely
ambiguous and warrants the better model.

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-dormant/scripts/report.py \
  --scout-dir "${REPORT_DIR}/scout" \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

# Effectiveness log — one line per run, feeds reports/_meta/dashboard.md.
# Buckets come straight from findings.json's summary.buckets field
# (certain_delete / orphan_endpoint / quasi_dead_broken / false_positive /
# unverified_budget). See `.claude/skills/_common/skill-conventions.md`.
python3 scripts/log_effectiveness.py \
  --skill find-dormant \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (certain_delete / orphan_endpoint / quasi_dead_broken / false_positive),
- top 3 candidates (one line each: name, file:line, recommendation),
- any `external_api_risk: true` orphan-endpoint flags (webhooks need
  human confirmation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command (`/fix-workflow delete:<name>`,
  `/fix-workflow fix:<name>`, or `/find-dormant` again after cleanup).

The report is the source of truth — do not enumerate every candidate.

## Non-goals

- Executing deletions (that's `/fix-workflow` after user authorization).
- Fixing silently-broken code (surface it, recommend
  `/fix-workflow fix:<name>`).
- Refactoring adjacent code.
- Running tests — read-only audit; tests run during `/fix-workflow`.
- Detecting duplication (that's `/find-duplication` /
  `/find-semantic-duplication`).
- CI gates — periodic audit, not a per-commit check.
- TypeScript safe deletion, framework/API ownership, dynamic dispatch, or any
  route/endpoint/error-swallowing assessment.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 vulture missing | `pip install vulture` into `.venv`; or skip `--vulture` flag in Stage 2 — unreferenced+silent_catches still produce candidates |
| Stage 1 detect_urls reports 0 patterns | Check the root URLconf exists; re-run with `--root-urls` pointing at the right file |
| Stage 1 detect_unreferenced is slow | Each def triggers a `git grep` — expect 1–2 minutes on a large source tree (10k+ defs). Reduce scope with a smaller `<target>` |
| Stage 2 reports 0 candidates | Target has no orphans (best outcome) — or detectors all failed; check stderr from each Stage-1 command |
| Stage 3 scout buckets everything as `false_positive` | Scout is being too conservative; inspect one output and re-dispatch with tighter instruction |
| Scout flags webhook-shaped URL as `certain_delete` | Rule 2 in `verify.md` was skipped — re-dispatch citing `external_api_risk` |
| Report's `recommendation` field disagrees with bucket | Scout error; reconcile using the cheat-sheet in `agents/verify.md` |

## Repository layout

```
.claude/skills/find-dormant/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   ├── detect_urls.py               # Stage 1
│   ├── detect_unreferenced.py       # Stage 1
│   ├── detect_silent_catches.py     # Stage 1
│   ├── collapse.py                  # Stage 2
│   ├── report.py                    # Stage 4
│   └── detect_typescript_dormant.mjs # TypeScript v1 final report
├── agents/
│   └── verify.md                    # Stage 3 scout brief
└── knowledge/                       # sub-agent context, never loaded by orchestrator
    ├── verification.md
    └── learnings.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
