---
name: introduce-fk
description: Turn a tuple-inferred-identity pattern (`.filter(status=X, created_at__gt=Y).first()`) into an explicit ForeignKey + two-step data migration proposal. Consumes an introduce-fk candidate from /find-implicit-state (or an explicit `OWNER_FILE::OwnerModel -> TARGET_FILE::TargetModel [via fk_name]` target) and emits reports/introduce-fk/<target>/proposal.md with the FK field shape, backfill migration sketch, caller migration table, tie-break strategy, and risks. Read-only — no code edits. Hands off to /fix-workflow or /refactor-subsystem.
argument-hint: "<implicit-state:ID or explicit OWNER::Model -> TARGET::Model [via fk_name]>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  Tuple-inferred-identity patterns surfaced by /find-implicit-state
  (e.g. `.filter(status=X, created_at__gt=Y).first()`) where an
  explicit ForeignKey would replace the tuple. Produces a two-step
  data migration proposal with FK shape, backfill plan, caller
  migration table, and tie-break strategy. Read-only — proposal only.
not_for: |
  Stringly-typed status enums (use /extract-enum). Detection of the
  pattern itself (use /find-implicit-state). Refactor execution (use
  /fix-workflow or /refactor-subsystem after the proposal).
language: python
framework: django
---

# /introduce-fk

You are the **orchestrator** for turning a tuple-inferred-identity
pattern into an implementation-ready ForeignKey proposal.
`/find-implicit-state` already flagged the target model with a
`tuple_identity` pattern; your job is to read the call sites in full,
dispatch a scout to profile "active X" vs "latest X" disambiguation,
propose the FK field shape, draft the two-step data migration, and
consolidate into a proposal the human reviews before handing off to
`/fix-workflow` or `/refactor-subsystem`.

You do NOT write production code in this skill. You never edit the
owner model, the target model, the callers, or a migration file. The
only artifact you produce is `reports/introduce-fk/<target-slug>/
proposal.md` plus its supporting `targets.json` and `profile.md`;
Stage 4 may also append one effectiveness row under `reports/_meta/`.

## How success is judged

- `proposal.md` carries the FK field shape, the mandatory two-step
  migration (nullable + backfill first; `NOT NULL` only if the
  invariant is real), the caller migration table, and an explicit
  tie-break strategy for multi-match backfill rows.
- The run's truth artifacts exist and are cited: `targets.json`,
  `profile.md`, `proposal.md`, plus the exact `collect.py` stderr
  summary line and the profile status/classification counts.
- The scout's "active X" vs "latest X" call is respected — a
  `latest_query` / `unique_hit` classification produces a documented
  misclassification note, not a forced FK.
- One owner/target pair per run; extra tuple-identity patterns land
  under Follow-on findings. Zero code or migration edits — execution
  belongs to `/fix-workflow` or `/refactor-subsystem`.
Write toward these gates from Stage 0.

## Core beliefs

1. **Job identity is an explicit FK, never inferred from
   `(status, timestamp, nullness)` tuples.** The CLAUDE.md Canonical
   Pattern "Job identity is an explicit FK" is the end state. Tuple-
   inferred identity breaks under concurrent jobs and hides in test
   fixtures; the FK makes the invariant schema-enforced. See
   `.claude/docs/architectural-smells.md` smell 2 (tuple-identity
   sub-shape) for the full diagnosis.
2. **"Active X" is NOT "latest X".** The scout must confirm the
   pattern selects rows in a subset of live states (with an implied
   at-most-one invariant per owner). `.order_by('-created_at').first()`
   on ALL rows — or a filter on a terminal state like `'completed'` —
   is NOT tuple-identity; it's "latest X" or "last known X" and does
   NOT migrate to a FK. If the scout classifies the target as
   `latest_query` or `unique_hit`, the proposal documents the
   misclassification and recommends a different approach (related-
   query accessor or `most_recent_<target>` property).
3. **Two-step migration is mandatory.** Migration 1 adds the FK as
   nullable + runs the backfill. Migration 2 (optional) flips to
   `NOT NULL` only when the "always has one" invariant is real.
   Usually Migration 2 is skipped because "no active job" is a
   legitimate null state.
4. **Tie-break is load-bearing.** The backfill must pick ONE row when
   the tuple matches several. The proposal states the tie-break
   explicitly (default: `-created_at`) and flags sites where the
   current code uses a different tie-break so the backfill mirrors it.
5. **One target per run.** If the scout surfaces another tuple-
   identity pattern in the same file (common — jobs have several
   "active X" pointers), log it under follow-on findings and stop.
6. **The proposal is read-only.** No code edits, no migrations, no
   test edits. `/fix-workflow` owns execution.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for `scripts/collect.py` (stdlib-only).
  The skill does not import Django or touch the DB.
- **Worktree guard:** read-only — no guard required here. The
  execution skill (`/fix-workflow`) does its own worktree check.
- **No shipped knowledge overlay:** this skill has no `knowledge/`
  files. The scout uses only `targets.json`, the source files it reads,
  and `agents/fk-profiler.md`. If the host has extra tuple-identity
  notes, the user must provide them in the prompt or the proposal must
  mark the missing evidence explicitly.

## Argument parsing

Two forms:

### Form A — Finding ID from /find-implicit-state

Pattern: `implicit-state:<id>` or `<id>` where `<id>` matches
`implicit-state-NNNN`. Resolves against
`reports/implicit-state/latest/findings.json`. The orchestrator reads
the candidate's `pattern` and `recommendation_hint` — this skill
rejects any pattern other than `tuple_identity` and recommends
`/extract-enum` for `stringly_state` candidates.

The finding's `hits` array identifies the **target** model (via
`model_hint`) but NOT the owner. The user must supply the owner via
`--owner-spec FILE::OwnerModel`, either in the argument or after the
orchestrator prompts. Example:

```
/introduce-fk implicit-state-0007 --owner-spec core/models/sitemaps.py::UrlCollection
```

If the findings file is missing, abort and tell the user to run
`/find-implicit-state` first — do NOT fall back to scanning.

### Form B — Explicit target spec

Pattern:

```
<owner_file>::<OwnerModel> -> <target_file>::<TargetModel> [via <fk_name>]
```

Example:

```
/introduce-fk "core/models/sitemaps.py::UrlCollection -> core/models/crawl_jobs.py::UrlCrawlJob via active_crawl_job"
```

The `via <fk_name>` suffix is optional — when omitted, the collector
picks an FK name from the most common `assigned_to` variable among
call sites (e.g. ``active_job``) or falls back to
``active_<snake_case_of_target_model>``.

Present the parsed spec back to the user (`target_slug`,
`owner_model`, `target_model`, `proposed_fk_name`) and wait for
approval (same approval-token contract as `/fix-workflow`: first non-
whitespace token must be `approved`, `approve`, `go`, `lgtm`,
`proceed`, `yes`). This is the only interactive step before Stage 0.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed, approval received (Form B only). **Post:**
`${REPORT_DIR}` exists, `latest` symlink.

```bash
TARGET_SLUG="<owner>__<fk_name>"    # urlcollection__active_crawl_job, ...
REPORT_DIR="reports/introduce-fk/${TARGET_SLUG}"
mkdir -p "${REPORT_DIR}"
ln -sfn "${TARGET_SLUG}" reports/introduce-fk/latest
```

`reports/introduce-fk/` uses target slugs directly (not timestamps)
so successive runs against the same owner/target pair overwrite. The
proposal shape is deterministic per FK pair.

### Stage 1 — Collect call sites + FK metadata

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json` with
owner/target metadata, tuple-inference shape, and every call site.

**Form A:**

```bash
.venv/bin/python .claude/skills/introduce-fk/scripts/collect.py \
  --from-finding "${FINDING_ID}" \
  --findings reports/implicit-state/latest/findings.json \
  --owner-spec "${OWNER_FILE}::${OWNER_MODEL}" \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

**Form B:**

```bash
.venv/bin/python .claude/skills/introduce-fk/scripts/collect.py \
  --target "${OWNER_FILE}::${OWNER_MODEL} -> ${TARGET_FILE}::${TARGET_MODEL}${FK_NAME:+ via ${FK_NAME}}" \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

The collector writes to stderr a one-line summary:
`<OwnerModel> -> <TargetModel> (N call sites, proposed_fk_name=X,
owner_has_existing_fk=<bool>)`.

**Handle early failure cases:**

- Exit 1 (zero call sites): target model has no tuple-inference call
  sites — the candidate was stale or the owner/target pair was wrong.
  Abort and report.
- Exit 2 (invocation error): bad argument shape (owner/target file
  doesn't exist, owner model not declared in the owner file, etc.).
  Surface stderr to the user verbatim.
- Output field `owner_has_existing_fk == true`: abort Stage 2 and
  jump to Stage 3 with a "FK already exists" proposal — the scan was
  wrong OR the migration is already partially complete. The proposal
  documents the existing FK and recommends the caller-migration piece
  only.

### Stage 2 — Profile the target (single scout)

**Pre:** `targets.json` exists, `owner_has_existing_fk == false`.
**Post:** `${REPORT_DIR}/profile.md` exists.

Dispatch ONE scout (not fan-out) with `agents/fk-profiler.md`.
Substitute placeholders:

- `{{target_slug}}`, `{{owner_model}}`, `{{owner_file}}`,
  `{{target_model}}`, `{{target_file}}`, `{{proposed_fk_name}}` —
  from `targets.json`
- `{{project_root}}` — `$(pwd)` absolute
- `{{targets_path}}` — absolute path to `${REPORT_DIR}/targets.json`
- `{{output_path}}` — absolute path to `${REPORT_DIR}/profile.md`
- `{{skill_root}}` — absolute path to
  `.claude/skills/introduce-fk/`

Use `subagent_type=general-purpose`.

The dispatch prompt must state the verdict contract: the scout's output
will be judged only by `profile.md` existing at `{{output_path}}`, the
`Status:` field, the four classification counts, the call-site table,
and source-file citations for any risk or misclassification claim.
Ungrounded prose is not evidence. The scout writes exactly one file and
prints a one-line file-write confirmation naming the status and counts.

If the scout returns `profile_incomplete` or `targets_missing`, re-
dispatch once with a stricter "respond only with file-write
confirmation" nudge. If it fails twice, proceed with a partial
profile and flag the gap in the proposal.

If the scout's classification totals show `latest_query` or
`unique_hit` dominates (≥50% of call sites), the pattern is NOT
tuple-identity — the proposal's primary action is "re-classify; do
NOT introduce an FK; consider a related-query accessor instead."
Still write the proposal, but flip Stage 3's body template.

### Stage 3 — Synthesize the proposal

**Pre:** profile exists. **Post:** `${REPORT_DIR}/proposal.md`
written.

Read `targets.json` + `profile.md`. Write `proposal.md` with this
structure (adjust for the `latest_query` / `unique_hit` reclassified
case — see "When things go sideways" below):

````markdown
# Proposal — introduce-fk: <OwnerModel>.<fk_name>

## Target
`<owner_file>::<OwnerModel>` gains a new ForeignKey pointing at
`<target_file>::<TargetModel>`. Currently the relationship is
inferred from
`<TargetModel>.objects.filter(<state kwargs>).first()` at <N> call
sites.

## Tuple-inference shape
From `targets.json.tuple_inference_shape`:

- state kwargs: <state_kwargs with literal values>
- time kwargs: <time_kwargs or "none — 'active now' semantics">
- extra kwargs: <extra_kwargs — flagged as discriminators>
- terminal: <first / index0 / both>

## Proposed FK
```python
<proposed_fk_name> = models.ForeignKey(
    'core.<TargetModel>',
    null=True, blank=True,
    on_delete=models.<CHOICE>,
    related_name='<NAME>',
)
```

**Rationale for `on_delete` / `related_name`** (from profile):
<one-paragraph summary from `profile.md`; if the profile lacks evidence,
use the default `SET_NULL` / `related_name='+'` and mark the rationale
as an evidence gap>.

## Migration plan (two-step)

### Migration 1 — schema + backfill (nullable)

1. `makemigrations` generates `AddField` for the new FK (nullable).
2. Custom `RunPython` operation walks the owner table, picks the
   tuple-winning row per owner, sets the FK. Sketch:

```python
def backfill_<target_slug>(apps, schema_editor):
    Owner = apps.get_model('core', '<OwnerModel>')
    Target = apps.get_model('core', '<TargetModel>')
    for owner in Owner.objects.iterator(chunk_size=1000):
        winner = (
            Target.objects.filter(
                <owner_fk>=owner,
                <state kwargs from tuple_inference_shape>,
            )
            .order_by('-created_at')     # tie-break
            .first()
        )
        if winner is not None:
            owner.<proposed_fk_name> = winner
            owner.save(update_fields=['<proposed_fk_name>'])

def reverse(apps, schema_editor):
    pass    # no-op; dropping the column is reversal enough
```

3. After deploy, add a `post_save` signal on `<TargetModel>` (or a
   scheduled reconciliation task) so jobs created during the backfill
   window don't leak — see risks below.

### Migration 2 — optional `NOT NULL`

Only if "every owner always has an active <target>" is a true
invariant. Usually skipped — "no active job" is a legitimate state.
The proposal recommends: **<apply Migration 2 | skip>** based on the
scout's null-state assessment.

## Caller migration table

<table from profile.md: file | symbol | before (summary) | after | notes>

Callers with extra-discriminator kwargs (flagged in the "notes"
column) need hand-review during `/fix-workflow` — the FK does not
absorb those kwargs.

## Backfill tie-break strategy

<paragraph from profile.md describing how the backfill picks ONE
row when the tuple matches several. Default: `-created_at`. Flag any
site whose current code uses a different tie-break so the backfill
mirrors it.>

## Null-state semantics

<paragraph from profile.md: when is null legitimate (no job running),
when is null a data bug (stuck owner, legacy row)>.

## Risks

- **Concurrent writes during backfill.** Jobs created during the
  backfill window may not be linked. <mitigation from profile>.
- **Stale rows with orphan state.** `status='running'` rows whose
  workers died look active but aren't. Recommend running the stale-
  job reaper before the backfill.
- **Extra-kwargs callers.** <list them; these need hand-review>.
- **Legacy NULL-state rows.** <count if known; these backfill to
  null by design>.
- **Schema migration duration.** Owner row count drives the backfill
  time. For tables >1M rows, run the backfill as a post-deploy
  management command instead of inline in the migration.
- **Cross-cluster model split.** If owner and target are in different
  `core/models/<cluster>.py` modules, use `'core.<TargetModel>'`
  string ref to avoid import cycles.

## Test matrix

Baseline (from `.claude/skills/_common/skill-conventions.md`):

```bash
.venv/bin/python manage.py test \
  tests.test_site_capabilities tests.test_hydration_detector \
  --settings=app.settings_test_sqlite -v 2
```

Plus subsystem-specific suites — grep `<OwnerModel>` and
`<TargetModel>` in `tests/test_*`:

- `tests.test_<suite_a>` — covers the callers in <path>
- `tests.test_<suite_b>` — covers the callers in <path>

**Characterization tests (before migration):** pin the tuple-inference
behavior of every site in the caller table so the FK rewrite is
proven behavior-preserving. One test per unique caller symbol.

**New concurrent-write test:** create two target rows with the
tuple-matching state, then assert `owner.<proposed_fk_name>` selects
the tie-break winner deterministically.

**Migration test:** run `makemigrations --check` to verify the
schema migration is clean; run the backfill on a fixture DB and
assert post-backfill invariants.

Ruff baseline on the affected files:

```bash
.venv/bin/ruff check <owner_file> <target_file> <caller files>
```

## Stop condition

- FK added on `<OwnerModel>`, migration file generated and applied.
- Backfill completed; every owner with a tuple-matching row has the
  FK set.
- Every call site in the caller table traverses the FK — zero
  `.filter(...).first()` tuple-inference patterns remain for this
  owner/target pair.
- Characterization tests pass unchanged pre/post migration.
- Baseline + subsystem-specific test matrix passes.
- `/find-implicit-state` re-run shows zero tuple_identity hits for
  `<TargetModel>` in this code path.

## Follow-on findings

<other tuple-inference patterns surfaced during profiling; NOT part
of this proposal — each is a new `/introduce-fk` invocation>

## Authorization

Human review required before execution. If approved, hand the
proposal path to `/refactor-subsystem` for a multi-file migration, or
to `/fix-workflow` only as an approved free-form execution brief. Do
not invent an `introduce-fk:<target-slug>` fix-workflow variant.
````

The risk section must cover the evidence present in `profile.md`:
concurrent-job races, stale-job reaper needs, cross-cluster model
splits, schema migration duration, extra discriminator kwargs, and any
known tuple-identity hotspot supplied by the user. If one of those cannot
be assessed from artifacts, say so in the risk row instead of inventing
coverage.

### Stage 4 — Effectiveness log

**Pre:** proposal written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
CALL_SITES=$(.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))['call_sites']))" "${REPORT_DIR}/targets.json")
OWNER=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['owner_model'])" "${REPORT_DIR}/targets.json")
TARGET=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['target_model'])" "${REPORT_DIR}/targets.json")
OWNER_FILE=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['owner_file'])" "${REPORT_DIR}/targets.json")
TARGET_FILE=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['target_file'])" "${REPORT_DIR}/targets.json")
HAS_EXISTING=$(.venv/bin/python -c "import json,sys; print(str(json.load(open(sys.argv[1]))['owner_has_existing_fk']).lower())" "${REPORT_DIR}/targets.json")

.venv/bin/python scripts/log_effectiveness.py \
  --skill introduce-fk \
  --scan-id "${TARGET_SLUG}" \
  --target "${OWNER_FILE}::${OWNER} -> ${TARGET_FILE}::${TARGET}" \
  --findings-total "${CALL_SITES}" \
  --buckets "{\"call_sites\": ${CALL_SITES}, \"owner_has_existing_fk\": ${HAS_EXISTING}}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Target (`<OwnerModel> -> <TargetModel> via <fk_name>`).
- Call-site count + classification breakdown (active_candidate /
  latest_query / unique_hit / tiebreaking_winner).
- Proposed `on_delete` choice.
- Top-3 risks (one line each).
- Path to `${REPORT_DIR}/proposal.md`.
- Recommended next step: human reviews `${REPORT_DIR}/proposal.md`;
  if approved, invoke `/refactor-subsystem` with the proposal path for
  execution planning.

Do NOT start the execution step yourself. The proposal is the
handoff artifact.

## Non-goals

- Executing the refactor (that's `/fix-workflow` /
  `/refactor-subsystem`).
- Detecting new tuple-identity patterns (that's
  `/find-implicit-state`).
- Writing the actual migration file — the proposal embeds a migration
  sketch; the real migration lands via `/fix-workflow`.
- Running the backfill against production data. The proposal
  describes it; the operator runs it post-deploy after human review.
- Opening more than one target per run. A second tuple-identity
  pattern surfaces as a follow-on finding; re-invoke the skill to
  handle it.
- Proposing an FK when the scout classifies the pattern as
  `latest_query` or `unique_hit` (dominant). The proposal documents
  the misclassification and recommends a different approach instead.
- Touching any file outside `reports/introduce-fk/<target-slug>/`.

## When things go sideways

| Symptom | Action |
|---|---|
| Findings file missing (Form A) | Abort; tell user to run `/find-implicit-state` |
| Finding's `pattern` is `stringly_state` | Abort; tell user to run `/extract-enum` — this finding is not tuple-identity |
| Form A without `--owner-spec` | Abort; the finding tells us the target but not the owner — prompt user for `--owner-spec FILE::OwnerModel` and retry |
| `collect.py` returns 0 call sites | Target has no tuple-inference sites — the candidate was stale OR the owner/target pair was wrong; abort and list the models seen in tuple patterns for the user to pick again |
| `collect.py` exits 2 | Invocation or input error. Paste stderr verbatim, fix the argument shape or missing file, and do not dispatch the scout |
| `owner_has_existing_fk == true` | Short-circuit: the FK is already on the model. The proposal flips to "FK exists; migrate callers only" — skip the schema migration body, keep the caller-migration table and test matrix |
| Scout classifies >50% of sites as `latest_query` | The pattern is not tuple-identity; the proposal recommends a related-query accessor (`owner.<related_set>.order_by('-created_at').first()`) and explicitly does NOT propose an FK |
| Scout classifies >50% of sites as `unique_hit` | The pattern is "last known X" — the proposal recommends a `most_recent_<target>` cached property on the owner, not an FK |
| Cross-cluster owner/target (different `core/models/*.py`) | The proposal must use `'core.<TargetModel>'` string ref; flag in the risk section |
| Scout says `targets_missing` | Re-dispatch once with stricter brief; if still missing, the `targets.json` is malformed — re-run Stage 1 |
| Scout does not write `profile.md` after two dispatches | Continue only with an explicit `profile_incomplete` proposal section that names the missing file and limits the recommendation to re-running the profile |
| `profile.md` lacks status or classification counts | Treat the profile as incomplete; do not infer "active" vs "latest" from memory |
| Tie-break indeterminate across sites (some `order_by('-created_at')`, others unordered) | Flag in the risk section; the backfill defaults to `-created_at` and the proposal asks the human to confirm |
| Owner table has >1M rows | Propose the backfill as a post-deploy management command rather than inline `RunPython`; flag in migration-duration risk |
| Effectiveness logging fails | Keep `proposal.md`; paste the logger error and do not claim the effectiveness row was written |

## Repository layout

```
.claude/skills/introduce-fk/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   └── collect.py                   # Stage 1 (stdlib-only)
├── agents/
│   └── fk-profiler.md               # Stage 2 scout brief
```
