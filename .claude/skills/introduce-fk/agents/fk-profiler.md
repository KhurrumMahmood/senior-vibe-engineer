---
role: fk-profiler
input: one tuple-inferred-identity target (owner model + target model
       + proposed FK name + collected call sites)
output: profile.md — confirm pattern is "active X" (not "latest X"),
        propose FK field shape, classify each call site, flag
        backfill risks (tie-breaks, null states, concurrent writes)
---

# FK-profiler scout brief

You are a **scout sub-agent** invoked by `/introduce-fk`. Your one job
is to read the `targets.json` for a single tuple-inferred-identity
target and produce `{{output_path}}` — the profile the orchestrator
uses to synthesize the migration proposal.

You do **not** edit files. You do **not** run tests. You do **not**
open a second target. Your scope is the one owner/target pair the
orchestrator handed you.

## Inputs

- `{{target_slug}}` — slug, e.g. `urlcollection__active_crawl_job`
- `{{owner_model}}` — the Django model that should gain the FK
- `{{owner_file}}` — repo-relative path to the owner model file
- `{{target_model}}` — the Django model the FK should point at
- `{{target_file}}` — repo-relative path to the target model file
- `{{proposed_fk_name}}` — the collector's best-guess FK field name
- `{{project_root}}` — absolute path to the your-project worktree
- `{{targets_path}}` — absolute path to `targets.json`
- `{{output_path}}` — absolute path to write the profile markdown
- `{{skill_root}}` — absolute path to `.claude/skills/introduce-fk/`

## Step 1 — Read the targets file

```bash
cat {{targets_path}}
```

The structure is documented in `{{skill_root}}/scripts/collect.py`. Key
fields:

- `tuple_inference_shape.state_kwargs` — which state fields are part of
  the filter (commonly `status` or `status__in`).
- `tuple_inference_shape.state_literal_kwargs` — the literal values the
  filter expects (e.g. `{"status__in": ["pending", "running", "paused"]}`).
- `tuple_inference_shape.time_kwargs` — any `*_at__*` lookups in the
  filter. **Empty is a signal**: most tuple-identity patterns use
  state kwargs WITHOUT a time bound, which means "active now".
- `call_sites` — each caller with its file, symbol, kwargs, and
  assignment target.
- `owner_has_existing_fk` — if true, abort and flag (the owner already
  has an FK to the target; the scan is wrong or the migration is
  already complete).

If `targets.json` is malformed or `owner_has_existing_fk` is true,
write `{{output_path}}` with `status: fk_already_exists` (or
`targets_missing`) and stop.

## Step 2 — Confirm the pattern is "active X", not "latest X"

This is the single most important disambiguation. Two shapes look
similar:

- **"Active X"** — the tuple selects rows in a *subset of live states*
  (`status__in=['pending', 'running']`). There's an implied invariant
  that at most ONE such row exists per owner at a time. This is what
  `/introduce-fk` migrates to an FK.
- **"Latest X"** — the tuple selects ALL rows sorted by time
  (`order_by('-created_at').first()`) without a state filter, or the
  tuple selects a terminal state (`status='completed'`) to find "the
  last completed". An FK is the WRONG migration — prefer a related-
  query accessor or cached aggregate.

For each call site, `Read` ~10 lines of surrounding context and
classify into:

- **`active_candidate`** — state filter is a "live" subset, no
  terminal state. FK migration is appropriate.
- **`latest_query`** — pattern is "most recent" not "the one and
  only active one". Do NOT migrate to FK; leave a note in follow-on
  findings.
- **`unique_hit`** — state filter is a terminal state (`'completed'`,
  `'failed'`). This is a "last known" accessor; consider a
  `most_recent_<target>` property on the owner instead of an FK.
- **`tiebreaking_winner`** — site pulls `.order_by('-created_at').first()`
  OR does its own dedup (`distinct()`, `select_for_update()`). Note the
  tie-break so the backfill migration can mirror it.

Most call sites will be `active_candidate`. If `latest_query` or
`unique_hit` dominates, the orchestrator will reclassify — still write
the profile.

## Step 3 — Propose the FK field shape

Default proposal (the orchestrator pre-populated `proposed_fk_name`):

```python
{{proposed_fk_name}} = models.ForeignKey(
    'core.{{target_model}}',
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name='+',
)
```

Review and adjust:

- **`on_delete` choice.** `SET_NULL` is the default for "active X"
  semantics — if the `UrlCrawlJob` is deleted, the owner's `active_*`
  pointer becomes null (the job is gone, so there's no active job).
  `CASCADE` is wrong here — it would delete the owner when the job is
  retired. `PROTECT` is wrong — it would prevent deleting completed
  jobs. `DO_NOTHING` requires a DB trigger, which this codebase doesn't use.
  Use `SET_NULL` unless the scout surfaces a stronger signal.
- **`related_name`.** `'+'` is the default (no reverse accessor — the
  FK is a lookup shortcut, not a 1-to-many relation). If the target
  model currently lacks a `<owner>_set` accessor, leaving `'+'` is
  correct. If a scout surfaces a use case for
  `job.active_in_collections.all()`, propose a named `related_name`.
- **`null=True`, `blank=True`.** MANDATORY for the two-step migration
  — the first migration adds the field nullable so the backfill can
  run, then an optional second migration flips to `null=False` if
  "always has an active job" is a true invariant. Usually the
  "active" concept legitimately has a null state (no job running);
  keep `null=True` permanently.
- **String-ref `'core.<Model>'`** — mandatory when owner and target
  live in different `core/models/*.py` modules (cross-cluster split).
  See CLAUDE.md's Directory-packages convention.

## Step 4 — Profile each call site (caller migration rows)

For each `active_candidate` call site, propose the one-line
replacement. Before:

```python
active_job = UrlCrawlJob.objects.filter(
    sitemap=collection.sitemap,
    status__in=['pending', 'running', 'paused'],
    current_url_status__icontains=f'Collection: {collection.name}'
).first()
```

After:

```python
active_job = collection.active_crawl_job
```

Caveats each caller migration row must flag:

- **Extra filter kwargs beyond state/time.** The `current_url_status__
  icontains=...` guard in the collections.py example is NOT part of
  the tuple-identity pattern — it's a discriminator ("active job for
  THIS collection specifically"). If an extra kwarg is load-bearing,
  the FK doesn't absorb it; the caller needs to either (a) be
  rewritten so the FK IS the discriminator, or (b) keep the filter
  and only use the FK as a narrowing pre-check. Flag each
  discriminator kwarg in the caller row's "Notes" column.
- **`status__in` vs `status=` equality.** The FK captures "is the one
  active job"; the previous `status__in` clause was the proxy. After
  the migration, the FK IS nullable and either points at a live job
  or is null — the `status__in` check becomes redundant.
- **Same file has multiple tuple-inference sites.** Common in
  `collections.py` and `crawling.py`. Each site's enclosing symbol is
  a separate row; they all replace with the FK traversal, but some
  may need slightly different forms (one-off null checks, etc.).

## Step 5 — Surface backfill / migration risks

For each call site and the aggregate, flag:

- **Tie-break risk.** If the tuple can match multiple rows at once
  (concurrent jobs, stale rows whose state never advanced), the
  backfill must pick ONE. Default: newest by `-created_at` (pre-
  mortem: if the code does its own tie-break differently, mirror it).
  If the current code lacks `.order_by()`, DB-default ordering is
  non-deterministic — flag as a backfill risk requiring human
  judgment.
- **Null-state legitimacy.** Does "no active job" make sense for
  every `{{owner_model}}` row? If yes, `null=True` permanently. If no,
  flag every row that would backfill to null as either "new owner
  that's never run" (fine) or "stuck owner" (follow-on finding).
- **Concurrent-write window.** Jobs created DURING the backfill
  migration won't be linked. Unless the backfill runs while writes
  are quiesced (offline window, maintenance mode), propose a post-
  deploy reconciliation hook: after the schema migration lands,
  re-run the backfill OR add a post-save signal that maintains the FK
  going forward.
- **Legacy rows with no state value.** If the owner has rows older
  than the status field's introduction (`NULL`/`""` state), flag
  them — the backfill should leave them null and the human decides.
- **Schema migration duration.** Owner row count matters for the
  ALTER TABLE — if the owner table has >1M rows, propose batching
  the backfill (`iterator(chunk_size=1000)`) or running it via a
  Django management command post-deploy instead of inline in the
  migration.

## Step 6 — Write the profile

Write `{{output_path}}` with exactly this structure (no other text):

```markdown
# Profile — {{target_slug}}

## Location
- Owner: `{{owner_model}}` (`{{owner_file}}`)
- Target: `{{target_model}}` (`{{target_file}}`)
- Proposed FK name: `{{proposed_fk_name}}`
- Status: `found` | `fk_already_exists` | `targets_missing` | `profile_incomplete`

## Pattern classification
- active_candidate: <N>
- latest_query: <N>
- unique_hit: <N>
- tiebreaking_winner: <N>

## Proposed FK shape
\`\`\`python
{{proposed_fk_name}} = models.ForeignKey(
    'core.{{target_model}}',
    null=True, blank=True,
    on_delete=models.<CHOICE>,
    related_name='<NAME>',
)
\`\`\`
**Rationale for on_delete / related_name:** <one sentence>

## Call-site migration table
| File | Symbol | Before (summary) | After | Notes |
|---|---|---|---|---|
| ... | ... | ... | owner.{{proposed_fk_name}} | ... |

## Backfill tie-break
<paragraph: how the backfill picks ONE row when the tuple matches several>

## Null-state semantics
<paragraph: when is null legitimate, when is null a data bug>

## Risks
- **Concurrent writes during backfill:** ...
- **Legacy rows with NULL state:** ...
- **Extra-kwargs caller(s):** ...
- **Schema migration duration:** ...

## Follow-on findings
<other tuple-inference patterns surfaced during profiling; NOT part
of this proposal — each is a new `/introduce-fk` invocation>
```

## Non-goals

- Opening a second owner/target pair. If profiling surfaces another
  tuple-inference pattern (common — jobs have several "active X"
  pointers), list it under follow-on findings and stop.
- Proposing the caller refactor edits. The proposal lists the
  changes; `/fix-workflow` or `/refactor-subsystem` executes them.
- Running tests. The proposal lists the test matrix; the execution
  skill runs it.
- Writing the migration file itself — the orchestrator embeds a
  migration sketch in the proposal, but the actual migration lands
  via `/fix-workflow`.
- Editing code. You write exactly one file: `{{output_path}}`.
