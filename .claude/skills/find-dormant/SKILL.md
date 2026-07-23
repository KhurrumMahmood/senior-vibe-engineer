---
name: find-dormant
description: Detect dead and quasi-dead code without changing source. Python retains vulture, AST, URL, silent-catch, and scout verification stages; TypeScript/TSX, checked JavaScript, Go, Java, and Rust have narrow static review branches for human review. Never infers safe deletion from static evidence.
argument-hint: "--target <directory-or-file> [--language python|typescript|javascript|go|java|rust]"
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
  Go v1 reports only unexported package-level functions and function-valued
  variables with zero `go/types` uses in the selected active-build package.
  Java v1 reports only private methods with zero compiler-resolved source uses.
not_for: |
  Removing findings (use /fix-workflow delete:<id>). Architectural
  smells like omnibus or layer violation (use those /find-* skills).
  Semantic duplication where two live behaviors coexist (use
  /find-semantic-duplication). Routes/endpoints, error swallowing,
  dynamic imports, external consumers, registry/event/framework reachability,
  or safe-deletion decisions are outside the static v1 contract.
language: any
framework: any
scans: [python, typescript, javascript, go, java, rust]
install_with: [map-subsystem]
scout_model: cheap
---

# /find-dormant

## Rust v1

Rust v1 reports private free functions with no bounded resolved source use as
`review_required`; `certain_delete` is always zero. Feature roots, callbacks,
traits/generics, macros, unsafe/FFI, reflection, and external consumers remain
deferred. The copied closure includes sibling `map-subsystem`.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-dormant"
python3 "${SKILL_ROOT}/scripts/detect_rust_dormant.py" \
  --project-root "$PWD" --target . \
  --output-dir "$PWD/reports/find-dormant/rust"
```
<!-- Legacy copied-install metadata token: scans: [python, typescript] -->
<!-- Legacy Go metadata token: scans: [python, typescript, javascript, go] -->

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
  ".agents/skills/on-demand/find-dormant" \
  ".agents/skills/find-dormant" \
  ".claude/skills/find-dormant"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-dormant is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
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

<!-- installed-command:javascript-scan:start -->
```bash
: "${TARGET:?Set TARGET to the checked-JavaScript file or directory to audit}"
JSCONFIG="${JSCONFIG:-jsconfig.json}"
REPORT_NAME="${REPORT_NAME:-javascript-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-dormant" \
  ".agents/skills/find-dormant" \
  ".claude/skills/find-dormant"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-dormant is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/detect_typescript_dormant.mjs" \
  --target "${TARGET}" --project-root "$(pwd)" --tsconfig "${JSCONFIG}" \
  --report-dir "reports/find-dormant/${REPORT_NAME}" --language javascript
```
<!-- installed-command:javascript-scan:end -->

This is a standalone host-root command: it resolves the selected skill itself
and does not inherit `SKILL_ROOT` from the TypeScript command above.

CommonJS exports and matching string/dynamic-registration evidence are
conservative boundaries, not dormant candidates. The result remains
human-review-only and never authorizes deletion.

## Go v1

Use this separate branch only with Go 1.22+ on `PATH`. One family-local,
batched helper uses the host toolchain's `go list` package/build facts plus
stdlib `go/parser`, `go/types`, and `go/importer`. It reports only
**unexported package-level functions and function-valued variables** with zero
resolved uses in their selected active-build package. Methods and types are
intentionally out of scope.

Every result is `review_required` with `human_review_only`; `certain_delete`
is always zero, and the Go branch must never infer safe deletion from static
evidence. An exact matching string name and a `//go:linkname` reference
are emitted as `uncertain`, rather than candidates. Reflection, generated
registration, plugin loading, cgo, and assembly stay explicit uncertainty
boundaries. Cgo/type/package facts that cannot be established, and
build-constrained files, produce a final `partial` report; they are never
silently clean. Malformed Go, missing/old Go, unsafe report paths, or symlink
targets exit 2.

The Go detector accepts a `.go` file or directory target, never follows a
symlink, applies project-root-relative exclusions to broad and direct targets,
and writes only `reports/find-dormant/<scan>/report.md` and `findings.json`.
It has no `go/packages`, toolkit venv, repository helper, sibling skill, or
network dependency after installation.

<!-- installed-command:go-scan:start -->
```bash
: "${TARGET:?Set TARGET to the Go file or directory to audit}"
REPORT_NAME="${REPORT_NAME:-go-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-dormant" \
  ".agents/skills/find-dormant" \
  ".claude/skills/find-dormant"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-dormant is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/detect_go_dormant.py" \
  --target "${TARGET}" --project-root "$(pwd)" \
  --report-dir "reports/find-dormant/${REPORT_NAME}"
```
<!-- installed-command:go-scan:end -->

Run the host's `go test ./...` before and after the audit. The detector reports
active-build package facts only; it does not establish runtime reachability or
authorize deletion.

## Java v1

Use this branch only with a JDK 17+ `java`/`javac` host. The family-local
source launcher runs `JavacTask.parse()` plus `analyze()` with `--release 17`
and `-proc:none`, then uses `Trees.getElement` for source use identity. It
reports only **private methods** with zero compiler-resolved Java source uses;
every result is `review_required`, `human_review_only`, and
`certain_delete: 0`. Reflection, DI, framework callbacks, JNI, generated or
Kotlin source, external consumers, Maven/Gradle/classpath/module-path
resolution, annotation processors, and runtime reachability remain explicit
boundaries. Syntax errors stop; unresolved compilation is a final `partial`
report. Full details are in `knowledge/java-v1.md`.

<!-- installed-command:java-scan:start -->
```bash
: "${TARGET:?Set TARGET to the Java file or directory to audit}"
REPORT_NAME="${REPORT_NAME:-java-scan}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/find-dormant" \
  ".agents/skills/find-dormant" \
  ".claude/skills/find-dormant"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"; break; fi
done
if [ -z "${SKILL_ROOT}" ] || ! command -v java >/dev/null 2>&1; then
  printf '%s\n' "find-dormant Java v1 requires an installed skill and JDK 17+" >&2; exit 2
fi
java "${SKILL_ROOT}/scripts/detect_java_dormant.java" \
  --target "${TARGET}" --project-root "$(pwd)" \
  --report-dir "reports/find-dormant/${REPORT_NAME}"
```
<!-- installed-command:java-scan:end -->

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
- Every Go final report carries explicit `review_required` and `uncertain`
  counts plus `certain_delete: 0`; no Go static finding crosses into a Python
  scout/deletion bucket or a safe-deletion recommendation.
- Every Java final report carries the same review-only counts and compiler
  resolution state; no Java static finding authorizes deletion.
- Nothing is deleted — recommendations route to `/fix-workflow
  delete:<name>` or `fix:<name>` after user authorization.
Write toward these gates from Stage 0.

## Scope

- **Target path:** the required `--target` argument. Python requires a
  directory; TypeScript v1 accepts a `.ts`/`.tsx` file or directory; Go v1
  accepts a `.go` file or directory; Java v1 accepts a `.java` file or directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **TypeScript v1:** Node plus a project-local `typescript` package and named
  tsconfig. Its static program/type-checker model is intentionally separate
  from the Python/Django detector and scout pipeline.
- **Go v1:** Go 1.22+ from `PATH`. Its active-build package/use model is
  intentionally separate from Python/Django and TypeScript branches.
- **Project-specific defaults** (grep locations, Django false
  positives, dynamic-dispatch patterns, candidate skip list): in
  `knowledge/`.

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

#### Dispatch mode

Use the declared cheap, read-only scout path when the host adapter is
available; otherwise use inline verification and record the fallback. Keep
the 25-candidate budget and the evidence contract above unchanged.

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
- Go method/type analysis, interface/runtime reachability, reflection,
  `//go:linkname`, generated registration, plugin, cgo, assembly, or any
  safe-deletion assessment.
- Java safe deletion, non-private method analysis, reflection/DI/framework/JNI
  reachability, Kotlin, generated-source, or build-tool resolution.

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
│   ├── detect_typescript_dormant.mjs # TypeScript v1 final report
│   ├── detect_go_dormant.py          # Go v1 final report launcher
│   ├── detect_go_dormant.go          # Go v1 batched package/use helper
│   └── detect_java_dormant.java      # Java v1 final report launcher
├── agents/
│   └── verify.md                    # Stage 3 scout brief
└── knowledge/                       # sub-agent context, never loaded by orchestrator
    ├── java-v1.md
    ├── verification.md
    └── learnings.md
```

The orchestrator (you) **never reads files in `knowledge/`**; those are for scout sub-agents.
