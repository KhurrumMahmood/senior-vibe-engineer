---
name: refactor-subsystem
description: Execute a large-subsystem refactor (split a bloated module, extract a service, reorganize a domain) using an orchestrator/scout pattern driven by a spec file in `ai-docs/specs/`. Operates in seven phases — Inventory, Characterize+Extract, Plan, Approve, Execute, Verify, Crystallize — with mandatory three-output scouts (primary brief + findings.md + extracted-behaviors.md), spec-first enforcement via `scripts/specs.py`, ledger updates via `scripts/ledger.py`, and a conservative default that unknown code STAYS until explicit human approval. Refactors are behavior-preserving; bug fixes surfaced along the way become separate commits.
argument-hint: "<spec-id>  (e.g., async-tasks, page-value-discovery)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent, Task
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Large-subsystem refactors driven by a spec at `ai-docs/specs/<id>.md`
  — split a bloated module, extract a service, reorganize a domain.
  Seven phases (Inventory → Characterize+Extract → Plan → Approve →
  Execute → Verify → Crystallize) with three-output scout discipline.
  Behavior-preserving; bug fixes split into separate commits.
not_for: |
  Single-cluster cleanups (use /fix-workflow). Detection (use the
  find-* SUSPECT skills). Authoring the spec from scratch when
  there's no prior plan (start with /scope-feature → /impact-feature
  → /architecture-fit → /plan-spec to produce one).
language: python
framework: django
---

# /refactor-subsystem

> **Legacy code is a specification written in the wrong language. The first
> refactor of a subsystem is not a refactor — it's an excavation.**

You are the **orchestrator** for a multi-file, multi-commit structural
refactor. Unlike `/fix-workflow` — which handles a single cluster of
duplication or dead code — this skill produces the spec-driven, scout-fanned,
human-approved split of a bloated module or subsystem.

Procedural detail lives in five knowledge files:

- `knowledge/` — worktree paths, scripts, venv conventions,
  archaeology recipe, test matrix, report layout. Read at the start of
  Phase 1.
- `knowledge/execution-playbook.md` — Phase 5 batch execution protocol,
  two-commit discipline, micro-fix swarm dispatch, convention enforcement
  decision loop, caller-update wave. Read at Phase 5 start.
- `knowledge/solid-gate-tests.md` — pass/fail rubric for the three-level
  SOLID quality gate plus the Phase 1.2.5 worked example. Read only
  when running Phase 6.3 (dispatched to sub-agent, not by orchestrator).
- `knowledge/bootstrap.md` — Phase 0 stub-scaffolding playbook. Read
  only when `specs.py show` exits non-zero.
- `knowledge/learnings.md` — 36 rules (R1–R36) distilled from prior
  refactors. Read on ambiguity; don't front-load. An L-number index at
  the bottom maps shakedown lessons to R-numbers.
- `.claude/skills/_common/interface-depth.md` — shared rubric for
  deletion test, caller-knowledge hiding, test surface, and adapter
  reality. Read when Phase 3 proposes new public modules/services or
  Phase 6 reviews the result.

Two scout brief templates live in `agents/`:

- `agents/inventory-scout.md` — Phase 1.3 template with `{{placeholder}}`
  slots the orchestrator fills in.
- `agents/micro-fix-scout.md` — Phase 5.3.5 swarm template.

## Core beliefs

1. **The spec is the plan.** If the spec says `[x] IM-N`, the code must
   reflect it. If it says `[ ]`, the work hasn't happened. Drift between
   the two blocks commits (`scripts/specs.py coverage <id>` is the gate).
2. **Bidirectional retrofit.** The first pass against legacy code is not
   a one-way transformation. You read code, extract behavior that was
   never written down, feed it back into the spec, AND THEN refactor.
   The spec grows during the run. **Bootstrap corollary:** legacy code
   with no spec is the canonical case — not an error state. Scaffold
   the stub in Phase 0.
3. **Conservative default for unknowns.** If you read a function and
   cannot explain why it exists — via a spec item, an
   `extracted-behaviors.md` entry, or git archaeology — it **stays**.
   Deletion requires explicit human approval at Phase 4.
4. **Behavior preservation ≠ correctness.** A correct refactor of broken
   code is still a correct refactor. Never bundle a bug fix into the
   structural commit. Two-commit discipline.
5. **Scouts produce THREE outputs, not one.** Every scout returns (a)
   the primary brief, (b) `findings.md`, (c) `extracted-behaviors.md`.
   Scouts that return only the primary brief are incomplete and must be
   rerun.
6. **Read toward the standard, not the neighbor.** Conventions live in
   CLAUDE.md's Canonical Patterns section and in `.claude/docs/*.md`
   loaded per subsystem. Scouts extract conventions alongside behavior
   AND flag where the subsystem fails them. Gaps are findings.
7. **Deepen, don't just rearrange.** A split or service extraction only
   earns its keep when callers learn less and behavior concentrates
   behind a stable interface. Use the shared interface-depth rubric to
   reject pass-through modules and hypothetical seams.
8. **The ownership boundary is the target.** A refactor is not done
   because the old file went quiet. After a split, scan the whole new
   family: old shim, new package files, sibling modules with the same
   ownership prefix, URL-registered prototype routes, templates/JS loaded
   by those routes, and newly-created services. Boundary clean beats
   filename clean.
9. **For omnibus views, ownership beats file count.** Extract one
   behavior-backed responsibility at a time into a named service, keep
   public HTTP contracts stable, add a negative guard that prevents the
   responsibility from returning to the view, and only then decide
   whether package/file splitting is still useful.

## Scope

See `knowledge/` for exact paths, venv rules, and the
cleanliness guard. Summary:

- **Worktree:** run wherever invoked. Confirm with `git rev-parse
  --show-toplevel` before Phase 1.
- **Python:** `.venv/bin/python` for Django; plain `python3` for
  `scripts/specs.py`, `scripts/ledger.py`, `scripts/chunk_file.py` (all
  stdlib-only).
- **Cleanliness guard:** `code_roots` must be clean (no unrelated
  uncommitted edits) before Phase 1 AND before every Phase 5 batch.
  Commands in `knowledge/`.
- **Argument:** a spec id that resolves to `ai-docs/specs/<id>.md`.
  Validate with `python3 scripts/specs.py show <id>`. If the spec
  doesn't exist, run Phase 0 — do not abort.

## Mode detection

Determined at the start of Phase 1 via the SOLID audit (§1.2.5):

### Standard mode (service extraction)
**Trigger:** `code_roots` names multiple files, OR a single file whose
SOLID audit shows 0–2 SRP "and"s.
**Primary axis:** IM item → service extraction.
**Plan shape:** `IM-N: extract X into service Y`.

### Decomposition mode (domain splitting)
**Trigger:** `code_roots` names a single file ≥ 2,000 LOC with 3+ SRP
"and"s.
**Primary axis:** responsibility cluster → new file.
**Plan shape:** `Domain cluster D → new file <basename>/<domain>.py`.
**What changes:** Phase 1 adds a SOLID audit (§1.2.5), Phase 3 organizes
the plan by domain cluster (§3.2.1), Phase 5 adds a caller-update wave
(execution-playbook §5.6). The 7-phase workflow and safety net are
unchanged.

**Edge case:** multi-file `code_roots` where ONE file dominates (e.g.,
10K LOC + 4 × 200 LOC satellites). Run the SOLID audit on the dominant
file. If it scores 3+ "and"s, decomposition mode applies to that file;
the satellites go through standard mode as part of the same spec.

### Packaging mode (flat-cluster consolidation)
**Trigger:** `code_roots` names a flat cluster of ≥3 sibling files
sharing a common prefix (e.g. `app/api/settings_*.py`,
`app/pages/site_config_*.py`), where the work is *topology
rearrangement* — pack siblings into a folder named for the prefix and
strip the prefix from each filename — not service extraction or domain
splitting. ADR 0006 (folder-organization ≥3-siblings) is the
authorizing decision; ADR 0010 (pages-mirror-routes) adds a
route-segment constraint when the cluster lives under `app/pages/`.
**Primary axis:** Cluster prefix → folder name. Per-file prefix
stripped on the move so the folder + filename together reconstruct the
old name without duplication (`api/settings_global.py` →
`api/settings/global.py`, NOT `api/settings/settings_global.py`).
**Plan shape:** `IM-N: package <prefix>_*.py into <prefix>/`. Each IM
item lists the move table: `(old_path → new_path, callers to update,
templates to update)`.
**What changes:**
- Phase 1 SOLID audit is **skipped** — no SRP work; the cluster's
  responsibilities don't change, only their location.
- Phase 1 inventory becomes a **move table**: every file in the
  cluster, every import statement that references it, every template
  `{% include %}` and `template_name=` that names it, every URL
  pattern that imports its view. The scout's job is to enumerate, not
  classify.
- Phase 3 plan organizes IMs by cluster (one IM per prefix, not per
  file).
- Phase 5 batches one cluster at a time. For each cluster:
  (1) `git mv` each file with prefix-stripped destination,
  (2) update every import found in the move table,
  (3) update every template/URL reference,
  (4) add `__init__.py` re-exports if any caller imports from the
      parent (`from api import settings_global` → must keep working
      via `__init__.py`, OR every such caller updates in the same
      commit),
  (5) run the always-suite + targeted backend suite.
- Phase 6 verification: the topology-drift detector reports zero
  findings under the cluster's new path; pre-commit lint registry
  resolves cleanly with `--all`; one Playwright pass on any UI route
  whose template references moved.

**Edge cases:**
- **Mixed cluster** — most files share a prefix but 1–2 don't. Either
  (a) include the outliers if a prefix-rename would naturally fit, or
  (b) leave them flat and document why in the spec's §Exceptions.
  Don't force-fit.
- **ADR 0010 route-mirror constraint** — pages clusters get an extra
  rule: the parent folder must mirror a URL route segment. So
  `app/pages/sites/wizard.py` mirrors `/sites/.../wizard/`. The
  packaging move and route-mirror placement happen together; the
  `find-folder-topology-drift` `pages_route_mirror` band catches
  filenames that forgot to drop the parent prefix.
- **Wire identifiers (R44)** — packaging IS a rename. Apply the
  three-bucket triad: Python imports follow the move; wire
  identifiers (URL `app_name`, `template_name=` strings, FK string
  literals if any) stay frozen unless explicitly migrating; doc
  prose follows.
- **Mixed-mode spec** — a single spec can carry packaging IMs
  alongside decomposition IMs (e.g. phase-2: pack `api/settings/`
  AND decompose `services/ai_sidecar/`). Run packaging IMs
  first — they're the lower-risk cleanup, and a clean cluster makes
  decomposition planning easier.

## Phase 0 — Bootstrap (only when the spec does not exist)

Run `python3 scripts/specs.py show <spec-id>` at the top of Phase 1. If
it exits 0, skip Phase 0 entirely. If it exits 1 ("no spec with id"),
read `knowledge/bootstrap.md` and follow steps 0.1–0.4 to scaffold the
stub, commit it, and then start Phase 1. Any other non-zero exit is an
abort signal — report and stop.

Key invariants (no need to load the playbook to remember these):

- The scaffold locks in `code_roots` — confirm scope with the human
  BEFORE running `specs.py init`.
- A stub spec has `status: STUB`; Phase 1.1.5's inventory gate will
  recognize that and allow scouts to populate the narrative.
- Commit the stub as a single-file commit before any Phase 1 work.

## Phase 1 — Inventory

Goal: know every file, symbol, public surface, and import edge in the
subsystem. No interpretation yet.

### 1.1 Load spec and ledger

```bash
python3 scripts/specs.py show <spec-id>
python3 scripts/specs.py coverage <spec-id>
python3 scripts/ledger.py list --decision split_queued,monitor
```

Record: `code_roots`, current `[ ]` / `[~]` / `[x]` states, ledger
entries for files in `code_roots`.

Verify the venv before Django commands (fall back to `$PYTHON_VENV_PATH`
if the worktree lacks its own `.venv`):

```bash
if [ -z "${PYTHON_VENV_PATH:-}" ] && [ ! -x .venv/bin/python ]; then
  echo "ERROR: no venv. Install dependencies per CLAUDE.md."
  exit 1
fi
```

If `coverage` reports drift (checkmark lag or orphan refs), **fix the
drift first** — either as a sub-task or abort and report. A spec that
already drifts is not a safe refactor target.

### 1.1.5 Inventory gate — verify the spec matches reality (mandatory)

The spec's narrative inventory can lag actual file contents. Running
scouts against a stale narrative silently orphans load-bearing code
(R14).

```bash
python3 scripts/specs.py inventory-check <spec-id>
```

Gate outcomes:

- **Clean** — counts and names match. Proceed to 1.2.
- **Drift ≤ 10%** — minor. Log the delta in
  `reports/refactor/<spec-id>/phase-1-inventory-gate.md` and add missing
  symbols to the chunking plan. No spec edit required.
- **Drift > 10%** OR spec is `status: draft` / has stub-inventory warning
  — **pause and update the spec first**. New symbols become new or
  expanded IM items in `ai-docs/specs/<spec-id>.md`. Re-run until clean.
- **STUB (from Phase 0 scaffold)** — expected. Scouts populate the
  narrative at Phase 1.3; stub warnings get removed at Phase 2b
  consolidation. Not a blocker.
- **Orphan regions** (contiguous spans unmentioned by the spec) get
  dedicated "orphan chunks" in Phase 1.3.0 — higher-ROI scout targets
  than spec-planned chunks.

### 1.2 Determine the relevant convention docs

Map `code_roots` to the right convention sources so every scout flags
the same violations with the same naming:

1. **Always in scope:** `.claude/CLAUDE.md` Canonical Patterns section
   and any `ai-docs/specs/<id>.md` whose `code_roots` overlap.
2. **Conditionally in scope** — pick from the "Supplementary
   Documentation" table in `.claude/CLAUDE.md`. The docs live under
   `.claude/docs/`, so write the full path in
   `convention-sources.md`:
   - Crawling / sitemaps / downloads → `.claude/docs/pipelines.md`
   - Extraction / AI training → `.claude/docs/known-issues.md`
   - PTID work → `.claude/docs/ptid-pipeline.md`
   - Custom-site imports → `.claude/docs/custom-site-data.md`
   - Models / views / services / tasks structure → `.claude/docs/architecture.md`
   - Deployment / env vars → `.claude/docs/configuration.md`
3. **Out of scope:** any doc whose trigger doesn't match. Context is
   expensive.

Write the resolved list to
`reports/refactor/<spec-id>/convention-sources.md`. Every scout brief
references this file.

**Scope each rule with a path predicate.** A convention extracted
from `docs/pipelines.md` that only applies to crawl tasks must not be
flagged as a violation in a view or service file. For every
convention entry, record:

```markdown
| Rule short | Canonical helper | Anti-pattern regex | Applies when path matches |
|---|---|---|---|
| AR-safe-dispatch | TaskDispatchService.safe_dispatch | `\.delay\(|\.apply_async\(` | `core/(views|tasks|services)/.*\.py` |
| AR-ensure-site | SiteConfig.ensure_for_site | `get_or_create\(site=` | `core/.*\.py` (any file that imports SiteConfig) |
| AR-safe-int-user-input | core.input_utils.safe_int | bare `int\(request\.(POST|GET)` | `core/views.*\.py` (views only — not services, tasks, or management commands) |
```

Scouts must check the `Applies when` column before flagging a
violation — a task file using `get_or_create` for a non-Site
model is NOT a violation of AR-ensure-site. Bare application of
"the convention doc says X" without the path predicate turns local
norms into false global failures and buries real issues in noise.

### 1.2.5 SOLID audit (decomposition mode — mandatory when triggered)

**Skip in standard mode.** When decomposition mode is active, run this
audit BEFORE chunking. It produces the responsibility clusters that
guide chunking, scout briefs, and the Phase 3 split plan.

**Step 1: SRP sentence test.** Describe the file in one sentence: "This
file handles X and Y and Z." Count the "and"s:
- 0 → cohesive. Switch to standard mode.
- 1–2 → check whether responsibilities are facets of one job or
  genuinely separable domains. Facets = standard mode.
- 3+ → decomposition mode. Each "and" clause maps to a cluster.

Evaluation rule: "and"s connecting facets of one domain count as 0;
"and"s connecting independently-understandable domains count as 1 each.
See `knowledge/solid-gate-tests.md` for worked examples.

**Step 2: Responsibility cluster mapping.** Group every top-level
function/class by domain. Use `scripts/chunk_file.py --format markdown`:

```markdown
| Cluster | Functions | LOC | Target file |
|---|---|---|---|
| Import & Validation | import_products_task, ... | 171 | <basename>_import.py |
| Crawling | bulk_crawl_task, ... | 1983 | <basename>_crawling.py |
```

Clusters under ~100 LOC are merge candidates.

**Step 3: Intra-file DRY scan.** Use structural AST comparison (R27).
`scripts/specs.py solid` (Gate 2) normalizes `ast.dump()` output. Look
for identical try/except shapes, duplicated setup sequences, multiple
implementations of the same abstraction.

Record each as a cross-cutting concern:

```markdown
### Cross-cutting concerns
1. **Task lifecycle** — 94 identical try/except blocks → @task_lifecycle decorator
2. **Proxy setup** — 11 duplicated sequences → service consolidation
3. **Progress tracking** — 2 incompatible systems → unified abstraction
```

Cross-cutting concerns become **Batch 1** of Phase 5 — consolidate
BEFORE splitting by domain (R26).

**Step 4: Linear flow test.** For 3 representative functions (small,
medium, large), trace the execution path. Functions that call helpers
thousands of lines away (past unrelated clusters) fail linearity — the
helper should move with its caller.

Write the audit to
`reports/refactor/<spec-id>/phase-1-solid-audit.md`. It feeds Phase 3's
split plan.

### 1.3.0 Chunk oversized files (mandatory for files > 2,000 LOC)

A single scout on a 10K-LOC file produces shallow output (R15). Every
file in `code_roots` whose LOC exceeds 2,000 gets chunked.

```bash
python3 scripts/chunk_file.py <file> --token-budget 8000 --format json \
  --output reports/refactor/<spec-id>/inventory/<basename>__chunks.json

python3 scripts/chunk_file.py <file> --token-budget 8000 --format markdown \
  --output reports/refactor/<spec-id>/inventory/<basename>__chunks.md
```

Rules:

- **Defaults:** `--token-budget 8000 --loc-budget 2500`. Tune only when
  scouts overflow or coordination breaks down.
- **Orphan chunks from 1.1.5 are first-class.** Create `orphan-1`,
  `orphan-2`, ... for every orphan region. Rank orphan IM proposals
  first in Phase 2.2 (R14; original lesson L-12).
- **Spec-guided cleavages:** if the spec enumerates IM-group line
  boundaries, pass `--loc-hints <start:end,...>` to bias toward them.
- **Files ≤ 2,000 LOC skip chunking.** One scout per file, basename-keyed
  outputs.
- **Non-Python files:** chunker only handles Python. Flag in `__chunks.md`
  for manual planning if needed.
- **Basename-qualify every chunk ID before dispatch (R35).** The
  chunker emits raw IDs `C-01`, `C-02`, `orphan-1`. Two chunked files
  in the same spec run (e.g., `tasks.py` and `services.py`) both
  produce `C-01`, which silently clobbers scout outputs and collides
  provisional-ID regex at Phase 2.2. Before writing the chunk map, the
  orchestrator rewrites every raw ID to `<basename>__<raw-id>`:
  `tasks__C-01`, `services__C-01`, `tasks__orphan-1`. Files that skip
  chunking get a single chunk id `<basename>__C-01` so the scheme is
  uniform. Output files, provisional item IDs, and the canonical
  short-code regex (R21) all use the qualified form.

Write the chunk map to
`reports/refactor/<spec-id>/inventory/<basename>__chunks.md`:

```markdown
# Chunk map — <file> (<LOC> LOC total)

| Chunk ID | Lines | LOC | ~Tokens | Declarations | Archaeology owner |
|---|---|---|---|---|---|
| tasks__C-01 | 1–1480 | 1480 | 7900 | imports, logger, ... (14 total) | orchestrator |
| tasks__C-02 | 1481–2875 | 1395 | 7200 | bulk_crawl_sitemaps_task, ... (8 total) | orchestrator |
| tasks__orphan-1 | 9240–10118 | 879 | 4600 | auto_generate_exports_task, ... (11 total) | orchestrator |
```

### 1.3 Dispatch the inventory scouts (parallel)

For each chunk (or each small file that skipped chunking), dispatch one
`Explore` sub-agent. Scouts run in parallel — one message, N tool calls.

**Use `agents/inventory-scout.md` as the brief template.** Substitute
every `{{placeholder}}` with the chunk's values (file path, line range,
chunk id, spec id, archaeology owner, worktree, venv path, declarations
from the chunker). Do not summarize the template.

Archaeology: if the chunk map marks the archaeology owner as "scout",
the brief tells the scout to run `git log --follow` on its range. If
marked "orchestrator", the orchestrator handles Phase 1.4 for that file
in parallel with scout dispatch. (Ownership split by churn — L-7.)

#### Dispatch mode — Agent tool vs subprocess

The `Agent` tool works only one level deep. If `/refactor-subsystem` is
itself invoked as a sub-agent (e.g. a bigger workflow spawns it), the
orchestrator has no `Agent` tool to fan out with and silently collapses
to single-threaded inventory — a bad outcome on a 10K-LOC target.

For nesting-safe fan-out, dispatch each chunk as a `claude -p`
subprocess via `.claude/skills/_common/dispatch_scout.sh`. Each
subprocess is a brand-new Claude Code process with the full tool set,
so this works at any nesting depth.

```bash
# One subprocess per chunk; parallelize with `&` + wait. The scout
# writes its three output files itself (primary brief, findings,
# extracted); dispatch_scout.sh verifies the primary brief path.
while read -r chunk; do
    cid=$(jq -r '.chunk_id' <<<"$chunk")
    file=$(jq -r '.file' <<<"$chunk")
    ls=$(jq -r '.line_start' <<<"$chunk")
    le=$(jq -r '.line_end' <<<"$chunk")
    basename=$(basename "${file%.*}")
    out="reports/refactor/${SPEC_ID}/inventory/${cid}__L${ls}-L${le}.md"
    .claude/skills/_common/dispatch_scout.sh \
        .claude/skills/refactor-subsystem/agents/inventory-scout.md \
        "$out" \
        file="$file" line_start="$ls" line_end="$le" chunk_id="$cid" \
        spec_id="$SPEC_ID" basename="$basename" \
        declarations="$(jq -r '.declarations' <<<"$chunk")" \
        archaeology_owner="$(jq -r '.archaeology_owner' <<<"$chunk")" \
        worktree="$(git rev-parse --show-toplevel)" \
        venv=".venv/bin/python" \
        branch="$(git branch --show-current)" &
done < "reports/refactor/${SPEC_ID}/inventory/chunks.jsonl"
wait
```

**Tradeoffs.** Subprocess dispatch adds ~4–8s spawn + full context reload
per scout vs ~0s for `Agent`. Use `Agent` when the skill runs at the top
level (cheaper, no spawn overhead). Use subprocess dispatch when the
skill may be invoked nested, or when scout context isolation is worth
more than the spawn cost.

The same pattern applies to Phase 5.3.5's micro-fix swarm — see
`knowledge/execution-playbook.md` for the swarm-specific wrapper.

### 1.4 Git archaeology (trigger-based, NOT optional)

See `knowledge/` for the full recipe. Summary:

- **≤ 500 LOC AND ≤ 20 commits** → scout runs it inline.
- **Everything else** → orchestrator runs it in parallel with scouts.
- **≥ 50 commits** → archaeology is **mandatory** (R17). The archaeology
  file must include at least 3 load-bearing LR-T candidates with
  `<!-- archaeology: <hash> -->` tags.

The recipe uses a subject-word filter (`fix|retry|timeout|crash|...`) to
find high-signal commits. Record findings in
`reports/refactor/<spec-id>/archaeology/<basename>.md` per the schema
in `knowledge/`.

### 1.5 Consolidate the inventory

Write `reports/refactor/<spec-id>/phase-1-inventory.md`:

- File-by-file table: path, LOC, symbol count, public imports, outbound
  imports.
- Chunk table for every chunked file: chunk id, line range, LOC,
  declaration count, scout status, archaeology owner.
- Dependency graph (ASCII or DOT).
- Hot-spot list (functions/classes above complexity thresholds).
- Counts: total LOC in scope, public surface, chunks dispatched, orphan
  chunks, inventory-gate delta.

**Gate for Phase 2** (chunk-level, not file-level — R2):

1. **Coverage** — `sum(end - start + 1) == LOC` for every chunked file.
2. **Three outputs per chunk** — all three scout files on disk.
3. **Archaeology present where required** — every ≥ 50-commit file has
   ≥ 3 LR-T candidates; every ≤ 500 LOC / ≤ 20 commits file has inline
   archaeology or a note.
4. **No empty primary briefs** — silent-fail signal. Re-dispatch.

Missing outputs → re-dispatch. Do not proceed until all four conditions
hold for every chunk.

## Phase 2 — Characterize + Extract (parallel)

Goal: freeze current behavior with tests, AND pull the "why" out of code
into the spec. These run in parallel and inform each other.

### 2.1 Characterization tests

Write temporary tests in `tests/test_<spec-id>_characterization.py` that
capture the **current** behavior of the public surface. They must pass
against HEAD.

Per public function / class entry point:

- **Import-level safety tests** —
  `import core.tasks; assertTrue(hasattr(core.tasks, 'foo_task'))` for
  every public name. Cheap, catches "forgot to re-export."
- **Behavior snapshots** for non-trivial logic: fixture in, expected
  dict out. Golden files in `snapshots/` for anything > 10 keys.
- **Skip private helpers** — they move with callers.
- Mark the file with `# spec:<spec-id>::characterization` — transient,
  deleted in Phase 7.

**Decomposition-mode characterization pins *structure*, not *behavior*
(L-44).** The right test shape is a `TaskImportabilityTest` (every public
symbol importable from the original path), `TaskSignatureTest` (function
signatures unchanged), and `TaskRegistrationTest` (Celery tasks still
registered with their original names + options). Behavior tests are the
domain test suites' job.

**Shim compatibility is mandatory for Django module splits.** When an
old view/task/service module becomes a package or re-export shim, add
characterization tests that pin:

- imports from the old module path (`core.views.site_config`,
  `core.views.brand_downloads`, etc.),
- imports from the parent package (`core.views` when it re-exports view
  classes),
- the old URL names and view callables that remain registered.

Move callers only when there is a behavior reason. Preserving imports
first keeps large splits reviewable and lets tests fail at the public
contract instead of at random import sites.

Run the tests and confirm they pass on HEAD:

```bash
.venv/bin/python manage.py test tests.test_<spec-id>_characterization \
  --settings=app.settings_test_sqlite -v 2
```

If any fail on HEAD, either the test is wrong (fix it) or the current
behavior is already broken (flag P0, do NOT adjust the test).

### 2.2 Extraction pass

Read `reports/refactor/<spec-id>/extracted/*.md` (all scout outputs) and
consolidate into `reports/refactor/<spec-id>/extracted-behaviors.md`.

Each scout output is named `{chunk_id}__L{start}-L{end}.md` (see
`knowledge/` "Report directory layout" and the
completeness contract in `agents/inventory-scout.md`). Missing or
mis-named files indicate an incomplete scout — re-dispatch rather than
proceeding.

**Provisional-to-canonical ID reassignment (R16).** Scouts propose IDs
with basename-qualified chunk-id prefixes (`tasks__C-03-EX-2`,
`services__orphan-1-IM-1`). The consolidation pass reassigns surviving
entries to canonical IDs by incrementing the highest existing number
in the spec's AR/EX/IM/LR-T sections. The basename qualifier in every
prefix (R35) guarantees no collision across parallel scouts even when
two different chunked files share a raw chunk number.

**Merge by summary before assigning canonical IDs.** Every extracted
entry carries a one-line purpose summary. Merge semantically-identical
entries across chunks BEFORE reassigning IDs — two scouts proposing
`*-AR-N: safe_dispatch catches all exceptions` from different call
sites merge into one canonical entry with a `**Seen in chunks:**` line.

Rank orphan-chunk IM proposals first (R14). Orphan candidates were
drifting out of spec — higher extraction ROI than spec-planned ones.

Consolidated file structure:

```markdown
# Extracted behaviors — <spec-id>

## IM candidates     (behaviors worth a new IM item)
## AR candidates     (structural constraints worth an AR item)
## EX candidates     (non-obvious rules — gotchas)
## LR-T candidates   (technical lessons — "why" behind defensive blocks)
## Remove candidates (appear dead. STAY until Phase 4 sign-off.)
## Investigate       (unclear semantics. Default if in doubt.)
```

**The extraction pass is the most important step.** If rushed, the
refactor silently destroys load-bearing code. For a 10K-LOC subsystem,
Phase 2.2 takes longer than Phase 5 (R12).

### 2.3 Findings consolidation

Read `reports/refactor/<spec-id>/findings/*.md` from all scouts and
consolidate into `reports/refactor/<spec-id>/findings.md`. Filename
convention matches §2.2 — `{chunk_id}__L{start}-L{end}.md` per the
inventory-scout completeness contract. Two sub-steps:

**2.3.1 Cross-scout dedup (R18)** — run BEFORE tiering. Parallel scouts
overlap when one chunk cross-references call sites in another. Build a
`(file, line-range, convention-violated)` fingerprint and merge duplicates:

```markdown
## P2: bare task.delay() at views_training.py:526
**File:** core/views_training.py:526
**Reported by:** chunk T-6 (tasks.py range), chunk D-1 (task_dispatch.py range)
**Observation:** `training_task.delay(site_id)` — bypasses safe_dispatch
**Convention violated:** AR-2 (TaskDispatchService.safe_dispatch)
**Why it matters:** No Celery retry; silent failure under broker outage
**Recommended disposition:** fix
```

Rules:
- **Strongest disposition wins** on disagreement; note the disagreement.
- **List all source scouts** in `**Reported by:**` — the micro-fix
  swarm uses this as a provenance trail.

**2.3.2 Tier the deduplicated findings** into P0→P3:

```markdown
## P0 — blocks the refactor
## P1 — must be addressed this cycle (separate commits)
## P2 — should be addressed soon, not this cycle
## P3 — nice to have, parking lot

## Convention adoption rates (from `specs.py violations <spec-id>`)
| Convention | Canonical | Compliant | Violating | Compliance % | Top offenders |
```

Run `python3 scripts/specs.py violations <spec-id>` to populate the
Convention Adoption table (R13). The full violation list is repo-wide;
Phase 5.4 filters it to `code_roots` unless whole-repo enforcement was
approved at Phase 4.

## Phase 3 — Plan

Goal: concrete split plan, informed by inventory + extracted behaviors
+ findings.

### 3.1 Update the spec with extracted behaviors

**Spec-first enforcement.** New IM / AR / EX / LR-T items from
`extracted-behaviors.md` get added to `ai-docs/specs/<spec-id>.md`
**before** any code moves. Enter as `[ ]` (or `[x]` for AR/EX that
document pre-existing decisions with no code work needed). Each new item
gets a unique incremented ID — do not reuse.

Run coverage to confirm the spec is still parseable:

```bash
python3 scripts/specs.py show <spec-id>
python3 scripts/specs.py coverage <spec-id>
```

`documented_only` / `checkmark_lag` growth is expected at this phase
(new items have no refs yet). `is_clean: false` is fine here.

### 3.2 Write the split plan

`reports/refactor/<spec-id>/phase-3-plan.md` contains:

1. **Target file tree after the refactor** — every new file, every
   survivor, every deletion.
2. **Symbol → destination map** — every public symbol mapped to its new
   home, with its `# spec:<spec-id>::IM-N` comment.
3. **Shim strategy** — re-export shim with enumerated re-export lines,
   or caller updates required.
4. **Endpoint contract matrix** for view/API modules — every endpoint
   in scope classified by route name/path, auth level
   (anonymous/user/staff), method, CSRF expectation, side effects,
   response shape, and external boundary (network, credentials,
   command execution, filesystem, Celery).
5. **Parallel renderer matrix** — every renderer/presenter of the same
   concept. Examples: dashboard rows, polling JSON, sidebar statuses,
   prototype rows, settings page forms, and admin diagnostic panes. The
   plan must name the canonical producer before moving presentation
   logic into services.
6. **Batch plan** — each batch leaves the repo green and is individually
   revertable. Rule of thumb: one `[batch-tag]` prefix per batch, passes
   its test scope independently. For 10K LOC, expect 5–15 batches.
7. **Test strategy per batch** — which modules' tests need to pass.
8. **Interface depth checks** — for every new public service/module,
   shared helper, or adapter seam, include the compact section from
   `.claude/skills/_common/interface-depth.md`: deletion test, caller
   knowledge removed, test surface, adapter count, and decision.
9. **Guard strategy** — negative test or lint proposal that prevents the
   extracted responsibility from returning to the old layer. Guard tests
   and lint guards are peers; choose the cheaper shape that protects the
   invariant.
10. **Rollback plan** — revert the batch, keep characterization tests,
   re-plan.
11. **Risks** — concrete failure modes with mitigations.

### 3.2.1 Decomposition-mode plan structure

**Skip in standard mode.** When decomposition mode is active, the Phase
3 plan uses a different primary axis.

**Primary axis: domain cluster → new file** (from the SOLID audit), not
IM item → service.

```markdown
## Target file tree
<basename>/
  __init__.py              → re-export shim
  common.py                → shared imports, constants, cross-cluster helpers
  crawling.py              → Crawling cluster
  discovery.py             → Discovery cluster
  extraction.py            → Extraction & AI cluster
```

**Directory packages over flat naming (R29).** Prefer
`<basename>/<domain>.py` over `<basename>_<domain>.py`. The
`__init__.py` is the natural re-export shim; it matches Django
conventions. Match existing flat naming for consistency if the codebase
already uses it.

**CRITICAL: File→directory migration is atomic.** Python cannot have
both `tasks.py` and `tasks/` simultaneously (`import core.tasks` becomes
ambiguous). The migration is a single commit:

1. `git mv core/tasks.py core/tasks_old.py`
2. `mkdir core/tasks/` + create `__init__.py` + create domain modules
   (read source from `tasks_old.py`)
3. `rm core/tasks_old.py`

For modules with many callers, flat naming is lower-risk because it
avoids the atomic rename.

**Within each cluster:**
- All functions/classes for the domain move as a unit.
- Helpers called only by that domain move with them.
- Shared helpers stay in `common.py`.
- Service extraction happens within clusters, not across.

**Cross-cutting consolidation as Batch 1** (R26). Cross-cutting concerns
from the SOLID audit land FIRST — task lifecycle decorator, shared
utility abstractions, common constants. Domain-split batches (Batch 2+)
reference consolidated abstractions instead of cloning boilerplate.

**Re-export shim is permanent** — NOT a Phase 7 cleanup target.
Breaking every `from core.<basename> import X` is high-blast-radius for
low value.

**Import management for domain modules (R32).** Domain modules get
their imports from `from .common import *`. Auto-detecting per-function
imports fails on real code (3 failed attempts in the tasks-decomp
dogfood before settling on `common import *`).

**`__all__` is mandatory in `common.py` (R30).** `from X import *`
silently skips `_prefixed` names. Explicit `__all__` lists every
underscore-prefixed name any domain module or external caller uses.

**Cross-cluster calls use lazy imports.** Module-level cross-cluster
imports create circular dependencies. Lazy-import inside the function
body.

### 3.3 Triage the Remove candidates

Every REM candidate must pass the **dormant verification checklist**
before entering the plan:

1. **Import/call-site grep** across the repo (excluding definition).
2. **URL wiring** in `core/urls.py` and included modules.
3. **Template/JS references** in `templates/` and `static/`.
4. **Admin/management registration.**
5. **Dispatch/registry membership** — dispatch dicts, signal handlers,
   Celery registrations.

Only candidates passing ALL 5 checks proceed to the plan. Failures get
reclassified as `keep as-is` with the failing check noted.

Entry format:

```markdown
### <name> at <file>:<line>
**Dormant verification:** all 5 checks passed
**Evidence of death:** <grep summary>
**Archaeology:** <last meaningful commit>
**Recommendation:** delete / keep as-is / ledger-monitor
**If removed:** <callers, URL patterns, admin regs, tests to clean up>
```

Default recommendation: **keep as-is** unless evidence is overwhelming
and removal is trivially reversible.

## Phase 4 — Approve

Goal: human reviews THREE outputs and signs off before any code changes.

### 4.1 Present the review package

Three files, in this order:

1. `phase-3-plan.md` — split plan + remove candidates
2. `extracted-behaviors.md` — harvested behaviors
3. `findings.md` — P0/P1/P2/P3 findings

Summarize each in ≤5 lines. Don't paste the contents — the files are on
disk. End with an explicit question:

> Ready to execute? Approve the split plan, the remove list, and the
> finding triage. I will block on your response — I do not proceed past
> Phase 4 without explicit approval.

### 4.2 Wait for explicit approval

Do not start Phase 5 on implicit "looks good" signals. The user must
respond with an **unconditional, standalone approval**. Only accept
the message if:

1. The first non-whitespace token is one of: `approved`, `approve`,
   `go`, `ship it`, `lgtm`, `proceed`. Substring matches don't count
   (`"looks ok but defer REM-3"` does NOT start with an approval
   token).
2. No conjunctions or qualifiers follow on the same turn (`but`,
   `except`, `however`, `only if`, `defer`, `pending`, `hold on`,
   `wait`). Any of these flip the reply from approval to change
   request.
3. If the user approved a *subset* ("approve split plan and P1 fixes,
   defer REM-3 and REM-5"), the reply is a **partial approval** —
   update `phase-3-plan.md` §Sign-off to list only the approved scope
   and loop back to Phase 3 for the deferred items. Do NOT execute
   the partial as though it were full approval.

Questions, counter-proposals, or any reply that doesn't satisfy (1)
AND (2) → loop back to Phase 3. When uncertain, ask the user to
re-confirm with a clean approval token — do not guess intent.

### 4.3 Record the sign-off

Append to `phase-3-plan.md`:

```markdown
## Sign-off
**Approved by:** <user handle>
**Approved at:** <ISO timestamp>
**Approved scope:**
- Split plan as written
- Remove candidates: <list of approved deletions — explicit>
- Findings triage: <which P1s → immediate fix commits, which P2s → ledger>
- Convention enforcement: subsystem-only (default) / repo-wide (opt-in)
**Not approved (deferred):** <remove candidate or P1 the user punted>
```

## Phase 5 — Execute

Goal: make the planned changes, one batch at a time.

**Read `knowledge/execution-playbook.md` in full before starting.** It
covers: spec-markers-before-implementation (§5.1), batch execution
protocol with concurrency re-check (§5.2), two-commit discipline for
bug fixes (§5.3), micro-fix swarm for 5+ mechanical fixes (§5.3.5),
convention enforcement decision loop (§5.4), ledger updates as live
state (§5.5), and the decomposition-mode caller-update wave (§5.6).

Key invariants (orchestrator-level):

- **Spec markers move BEFORE code moves** — `# spec:<spec-id>::IM-N`
  comments bootstrap the code→spec link.
- **Re-run the concurrency check at the start of every batch** (R6).
- **If any test fails, stop.** Do not accumulate broken state.
- **Two commits for refactor + bug fix** — never bundled.
- **Micro-fix swarm: sub-agents edit only, orchestrator commits
  serially.** Parallel agents share one git index — concurrent staging
  causes cross-contamination (R19).
- **Convention enforcement scoped to `code_roots` by default.** Whole-
  repo enforcement requires explicit Phase 4 sign-off.

## Phase 6 — Verify

Goal: confirm the refactor is complete, the spec reflects reality, no
drift exists.

### 6.0 Ownership-boundary scan

Before running tests, scan the whole ownership boundary named by the
plan, not just the retired file. Include:

- the old shim and new package/directory files,
- sibling files with the same ownership prefix
  (`core/views/site_config*.py`, `core/views/settings*.py`, etc.),
- public URL routes and prototype routes still registered,
- templates and JS loaded by those routes,
- new services created by the extraction.

Report the result as `target clean` vs `repo still has known findings`
when a wider quality scan sees debt outside the approved scope. Do not
declare a split complete while the same responsibility still lives in a
registered sibling/prototype path.

When reporting lint health, distinguish touched/diff-scoped cleanliness
from whole-file or repo-wide legacy debt. A full-file Ruff failure in a
legacy file is different from new service code being dirty; name which
surface is clean and which surface still carries inherited findings.

### 6.1 Full verification suite

```bash
# Baseline (always)
.venv/bin/python manage.py test \
  tests.test_site_capabilities tests.test_hydration_detector \
  --settings=app.settings_test_sqlite -v 2

# Subsystem-specific (from spec / Phase 3 test strategy)
.venv/bin/python manage.py test <subsystem-test-modules> \
  --settings=app.settings_test_sqlite -v 2

# Characterization tests — still must pass
.venv/bin/python manage.py test tests.test_<spec-id>_characterization \
  --settings=app.settings_test_sqlite -v 2
```

### 6.1.5 `__all__` export gate on new shared modules

Any new module that:

1. Is named `common.py` within a directory package, OR
2. Is imported elsewhere via `from .<module> import *`

MUST declare an explicit `__all__` listing every exported name
(including `_`-prefixed helpers that callers depend on). `from X
import *` silently skips underscore-prefixed names — a missing
`__all__` turns into `NameError` at runtime in the domain modules
that relied on the export (R30).

```bash
# 1. Find star-imported modules produced by this refactor:
git diff --name-only <pre-refactor-rev> HEAD -- '*.py' | while read f; do
  if [ -f "$f" ] && ! grep -q '^__all__' "$f"; then
    # Check if anyone star-imports it:
    mod_path=$(echo "$f" | sed -E 's|/|.|g; s|\.py$||')
    if git grep -qE "from [^ ]*${mod_path##*.} import \*" -- '*.py'; then
      echo "GATE-FAIL: $f is star-imported but has no __all__"
    fi
  fi
done
```

Any `GATE-FAIL` line blocks Phase 7 — add the `__all__`, re-run the
Phase 6.1 test suite, then continue.

### 6.2 Spec coverage gate

```bash
python3 scripts/specs.py coverage <spec-id>
```

**Hard gate — `is_clean: true` required.** If any of these appear, block:

- `checkmark_lag` — IM item marked `[x]` but no `# spec` code reference.
  Either the code didn't land or the marker is wrong.
- `orphan_refs` — `# spec` comment in code but no matching spec item.
  Typo or unplanned addition.
- `implementation_ahead` — code refs exist but item still `[ ]`. Phase 5
  forgot to flip the marker.

Fix every drift before Phase 7. Re-run after each fix.

### 6.3 SOLID quality gates on new files

Three-level harness. **All three levels run.** Levels 1+2 are
**blocking**. Level 3 (judgment) failures are **non-blocking** — flag as
Phase 7 follow-ups.

**Level 1 + 2 (automated):**

```bash
python3 scripts/specs.py solid <spec-id>
# Exit 0 = L1+L2 pass. Exit 1 = at least one failure.
# --json emits structured output for L3 dispatch.
```

L1 (artifact gate) checks `phase-1-solid-audit.md` exists and has all
four required sections. L2 (code checks) runs structural AST-based DRY
detection and LOC ceilings on `code_roots` files. L1+L2 catches "agent
skipped the SOLID audit" and "agent claimed DRY but code has 50 identical
blocks."

**Level 3 (sub-agent judgment — Gate 1 + Gate 3):**

SRP and linear-flow gates require judgment that can't be mechanically
checked. Dispatch **one** Explore sub-agent with the independent-review
brief. **The orchestrator does NOT evaluate these gates itself** —
dispatching prevents rubber-stamping its own work.

The scout reads `knowledge/solid-gate-tests.md` (the rubric) and
`phase-6-solid.json` (L1+L2 output) to evaluate every `.py` file in
`code_roots`. Writes verdicts to
`reports/refactor/<spec-id>/phase-6-solid-agent.md`.

After the scout returns, read the verdict file. FAIL → flag files as
Phase 7 follow-ups.

Gate definitions (SRP / DRY / Linear flow / Size advisory) and worked
PASS/FAIL scenarios live in `knowledge/solid-gate-tests.md`. Summary:
0–1 "and"s per file, no structurally-duplicated blocks across new
files, no private-helper calls into a sibling domain module, LOC re-
check at 800 and hard ceiling at 1000. Cohesion override (R24):
500–600 LOC files representing one cohesive concern do NOT require
splitting — slightly larger cohesive files beat many over-split ones.

For service extractions, run the same SRP/DRY/linear-flow lens on the
new service owner. Moving view logic into `FooService` is an improvement
only if the service owns a cohesive responsibility; otherwise the
refactor traded a fat view for a god service. Record service-shape
findings as Phase 7 follow-ups unless they create duplicated logic,
leaky interfaces, or sibling-domain private helper calls.

### 6.3.5 Interface depth review

Read `.claude/skills/_common/interface-depth.md` and review every new
or reshaped public module, service method, shared helper, and adapter
created by the refactor. Write
`reports/refactor/<spec-id>/phase-6-interface-depth.md` with one compact
check per interface.

Blocking failures:

- **Pass-through module/helper** — deletion test says complexity would
  mostly vanish rather than reappear across callers.
- **Leaky interface** — callers still need the old invariants, ordering
  rules, retry policy, or resource ownership details.
- **Wrong test surface** — durable tests must reach private helpers to
  prove behavior.
- **Hypothetical seam** — a port/adapter was added with only one real
  adapter and no justified test stand-in.

If the failure is confined to a decomposition-mode domain file whose
purpose is only to co-locate cohesive code, record it as a Phase 7
follow-up rather than blocking. Service/interface failures block Phase 7.

## Phase 7 — Crystallize

Goal: leave the repo in a durable state for future agents.

### 7.1 Delete the characterization tests

Read each and decide:

- **Delete** if it's an import-level check or a snapshot now covered by
  real tests.
- **Promote** into the spec as an LR-T item if it encodes durable
  behavior (e.g., "task dispatcher silently retries on
  `BrokerConnectionError`"). Move the test logic into a real test file
  if the real suite doesn't already cover it.

Commit with `[spec-id:cleanup] Delete characterization tests`.

### 7.2 Update the ledger

```bash
# Old file is now a shim
.venv/bin/python scripts/ledger.py update core/tasks.py \
  --decision monitor \
  --rationale "Split complete per <spec-id>. Now a re-export shim; growth indicates regression."

# New files start life in the ledger with a baseline snapshot.
# `update` is an upsert — it creates the entry if it doesn't exist
# yet. ledger.py has no separate `add` subcommand.
.venv/bin/python scripts/ledger.py update core/tasks_discovery.py \
  --decision monitor \
  --rationale "Created by <spec-id> refactor. Monitor for growth."
```

### 7.2.5 Update quality-tool memory

When a flat omnibus file is retired or a new ownership package becomes
canonical, update the cleanup tools' memory in the same cleanup phase:

- skill examples and known-retired target notes,
- target enumerators/product-topology scanners that still point at the
  retired file,
- subsystem/workflow maps that describe the old ownership shape,
- guard tests that assert a retired flat implementation file has not
  returned when that is the invariant.

This is not product documentation churn. It prevents future cleanup
skills from treating yesterday's smell as today's architecture.

### 7.3 Append to the learnings log

Add a cluster entry to `reports/duplication/learnings.md`:

```markdown
## Cluster N: <spec-id> subsystem refactor (P0)

**Date:** <YYYY-MM-DD>
**Commits:** <batch-1 sha>..<cleanup sha> — "<first and last titles>"
**Type:** Subsystem split / service extraction / domain reorganization

### What was flagged
<stub spec identified <LOC> of bloat in <file> and proposed <N> IM items>

### What was actually true
<Phase 2.2 extraction count; surprises>

### What changed
<file tree delta, LOC delta per file, new spec items, remove candidates
actioned>

### Tests
<characterization tests written / deleted / promoted; suites run;
regression tests from P1 findings>

### Skill-worthy patterns
<what this taught that isn't already in knowledge/learnings.md R1-R36>
```

### 7.4 Final spec marker sweep

```bash
python3 scripts/specs.py coverage <spec-id>
```

Confirm `is_clean: true`. Any residual `[~]` or `documented_only` items
become a note in the learnings entry so the next maintainer knows
what's still open.

### 7.5 Effectiveness log

Append one line to `reports/_meta/effectiveness.jsonl` so the skill-
effectiveness dashboard can track refactor output over time. Schema
in `.claude/skills/_common/skill-conventions.md`. `findings_total` is the number
of batch commits landed in Phase 5; `buckets` keys on commit verbs
(`Dedup` / `Delete` / `Promote` / `Migrate` / `Fix`) derived from
`git log` over the refactor range.

```bash
python3 scripts/log_effectiveness.py \
  --skill refactor-subsystem \
  --scan-id "<spec-id>-$(git rev-parse --short HEAD)" \
  --target "<primary code_roots path>" \
  --findings-total <N-batch-commits> \
  --buckets '{"dedup": N, "delete": N, "promote": N, "migrate": N, "fix": N}' \
  --notes "<spec-id> · <one-line summary of what shipped>"
```

## Non-goals

- **Spec authoring from scratch.** Phase 0 scaffolds a stub; the human
  drives narrative (goals, constraints, non-goals).
- **Single-cluster cleanups.** Use `/fix-workflow`. This skill's
  overhead is wasted on a 50-LOC fix.
- **Cross-subsystem refactors in one run.** One spec, one refactor. The
  ledger and coverage tools don't compose across specs.
- **Auto-approval of deletions.** Phase 4 is always human. No `--yes`
  flag.
- **Editing files in the main worktree.** The concurrency guard exists
  for a reason.
- **Running live integration suites as a gate.** Phase 6 is the SQLite
  matrix. Live suites are expensive, flaky, not a gating signal.
- **Documentation files (README, .md) unless the user asks.** Learnings
  log and `reports/refactor/<spec-id>/*.md` files are working artifacts.
- **Refactoring anything adjacent to the spec's scope.** A scout's
  out-of-scope P1 finding becomes a ledger `monitor` entry — not a
  bonus commit.

## Failure modes and recovery

- **Scout returns only primary brief, no findings/extracted-behaviors:**
  Re-dispatch with a stricter brief. Incomplete scouts cannot be
  trusted. Do not proceed to Phase 2 with partial outputs.
- **Phase 2.2 surfaces behavior that contradicts the spec:** Pause. The
  spec or the code is wrong. Escalate as P0. Do not resolve unilaterally.
- **Batch N breaks Batch N-1's tests:** Revert Batch N. Re-read the plan
  — the batches weren't actually independent. Re-plan.
- **Coverage gate fails with `orphan_refs`:** A `# spec` comment has a
  typo or references a removed item. Fix the comment or re-add the
  item. Do NOT delete the comment to silence the gate.
- **Coverage gate fails with `checkmark_lag`:** An IM item was marked
  `[x]` prematurely. Either finish the work or revert the marker to
  `[~]`.
- **Remove candidates approved at Phase 4 are referenced via dispatch
  dict at Phase 5:** Do NOT delete. Revert the remove batch, update the
  REM candidate's evidence with the new dispatch reference, escalate
  back to Phase 4 for re-approval.
- **Concurrency collision with main worktree mid-refactor:** Stop the
  current batch. Usually: abort the refactor, let the main-worktree
  change land, restart with a fresh Phase 1 inventory.
- **Human asks to skip Phase 2.2 "to save time":** Refuse politely.
  Cite R12. The skill's contract is that extraction runs on every file
  in `code_roots`. If the user insists, get the refusal in writing and
  exit — do not start a refactor you know will discard behavior.

## Repository layout

```
.claude/skills/refactor-subsystem/
├── SKILL.md                    # this file — orchestrator
├── agents/                     # scout brief templates
│   ├── inventory-scout.md      # Phase 1.3 — parallel inventory scouts
│   └── micro-fix-scout.md      # Phase 5.3.5 — mechanical-fix swarm
└── knowledge/                  # loaded on demand
    ├── execution-playbook.md   # Phase 5 sub-sections
    ├── solid-gate-tests.md     # Phase 6.3 sub-agent rubric + 1.2.5 worked example
    ├── bootstrap.md            # Phase 0 stub-scaffolding playbook
    └── learnings.md            # R1–R36 from prior refactors
```
