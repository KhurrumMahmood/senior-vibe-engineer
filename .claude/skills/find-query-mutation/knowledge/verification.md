# Verification procedure + bucket taxonomy — query-mutation

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly what to check for one candidate and how to classify
the result.

## The smell

A function whose name promises a pure read — `get_active_job`,
`fetch_pending_row`, `load_config`, `list_unprocessed`,
`find_by_status`, `check_freshness` — actually writes to the database
in its body. The caller, reading `job = get_active_job()`, has no
signal that the line mutated state. Three problems follow:

1. **Unexpected side effects.** Test fixtures that call `get_*` to set
   up state get silent writes. Concurrent readers race on the write.
2. **Refactoring hazard.** Adding caching on "a read" breaks the
   pipeline the write was secretly feeding.
3. **Review opacity.** A PR renaming `get_active_job` to
   `fetch_active_job` looks cosmetic; it hides a schema-mutating call.

See smell 3 in `.claude/docs/architectural-smells.md` for the
canonical taxonomy. The `query-mutation` lint rule catches new
occurrences at commit time; this skill surfaces pre-existing ones.

## Bucket definitions

Write exactly one of these into ``bucket`` on your JSON output:

| Bucket | Criteria | Recommendation |
|---|---|---|
| **rename_to_mutator** | The receiver is a Django `Model` instance or `QuerySet`, and the mutation is not cache warming. The write is a core part of what the function does. | `/fix-workflow cluster:<symbol>` — rename to `get_or_create_*`, `fetch_and_heal_*`, `touch_*`, or split (see below). |
| **split_reader_and_mutator** | The function does both — returns data to callers AND writes a side effect most callers don't need. A subset of callers legitimately want the write; the rest should get a pure read. | `/fix-workflow cluster:<symbol>` — split into a pure reader and a separate mutator; migrate callers. |
| **legitimate_cache_warming** | The mutation is a singleton populator / cache warmer the read genuinely depends on. `get_or_create` on a settings row or a row-locked counter. | Add `# hidden-mutation: cache warming` comment on the mutation line. Do not rename. |
| **false_positive_stdlib_wrapper** | The receiver is a `dict`, `set`, `list`, or other stdlib container. `.update()` / `.create()` hits are the usual culprits. | Drop from candidates. Recommend no action. |

### When to choose rename vs split

Count the callers. If every caller wants the mutation (e.g.
`get_or_create_row` always writes the first time), **rename**. If some
callers want a pure read and others want the mutation, **split**.
Default to `rename_to_mutator` when call-site counts are unknown — the
rename-first flow is safer and easier to reverse than a split.

## Verification checklist (apply in order)

### 1. Read the enclosing function.

Open the candidate's `file` and read the full enclosing `FunctionDef`
/ `AsyncFunctionDef`. The candidate JSON gives you `symbol` and
`func_lineno` — find the `def <symbol>(...)` block starting at that
line and read it through to its `return` or block end.

### 2. Identify the receiver of every mutation call.

For each entry in the candidate's `hits` list, look at the evidence
line. The call shape is `<receiver>.<method>(...)`. The scout needs to
answer: **what is `<receiver>` bound to?**

- **Walk backward in the function body** to find the receiver's
  binding (`<receiver> = <something>` or parameter declaration).
- **If `<receiver>` is `self`**, read the enclosing class's body:
  - Does the class inherit from `models.Model` (or a mixin that does)?
    → genuine instance receiver.
  - Does the class inherit from `View`, `TemplateView`,
    `ListView`, `DetailView`? → check if the receiver is `ctx` from
    `super().get_context_data(...)` — that's a dict.
- **If `<receiver>` is a local variable**, check the assignment:
  - `set()` / `{}` / `dict()` / `list()` → stdlib container.
  - `<Model>.objects.get(...)` / `.filter(...).first()` → genuine
    queryset result (model instance).
  - `<Model>(...)` constructor → model instance.

Bucket as `false_positive_stdlib_wrapper` when **every** mutation hit
in the candidate has a stdlib-container receiver. Mixed hits (one
genuine, one false positive) → bucket by the genuine one.

### 3. Check for the `# hidden-mutation:` allow-list marker.

The detector honors `# hidden-mutation: <reason>` and drops marked
hits before writing `hits.jsonl`. **A hit surfacing in the candidate
means no marker was found.** If the scout spots a marker the detector
missed (e.g. on a continuation line), note it in `notes` and bucket as
`legitimate_cache_warming` with `false_positive_reason:
"hidden_mutation_marker_missed"`.

### 4. Classify the mutation's role.

For genuine mutation receivers, decide between
`legitimate_cache_warming`, `rename_to_mutator`, and
`split_reader_and_mutator`:

- **Cache warming test.** Is the mutation `get_or_create(...)` or a
  first-time populator that returns the newly-created row the read
  needs? Is the function a getter on a singleton
  (`GlobalSettings.get_settings()` is the canonical example)?
  → `legitimate_cache_warming`.
- **Every-caller test.** Is the mutation something every caller
  expects — healing a stale row, bumping a counter, stamping a
  last-seen timestamp?  → `rename_to_mutator` with a name that
  signals the mutation (`fetch_and_heal_*`, `touch_*`, `refresh_*`).
- **Some-callers test.** Does some caller want "just the row" and
  other callers want "the row, healed"? → `split_reader_and_mutator`.

### 5. Pick `recommendation_hint_symbol`.

For bucketed candidates that need a refactor, the report's next-action
section needs a symbol to pass to `/fix-workflow cluster:<symbol>`.
This is almost always the candidate's own `symbol`, but if the scout
sees a cluster of related functions (e.g. `get_active_job` and
`get_active_job_for_site` in the same file), pick the most
heavily-used one.

## Output schema

Write a JSON file at `{{output_path}}`:

```json
{
  "candidate_id": "query-mutation-0001",
  "file": "core/models/settings.py",
  "symbol": "get_settings",
  "func_lineno": 181,
  "bucket": "legitimate_cache_warming",
  "confidence": "medium",
  "hit_count": 1,
  "mutation_methods": ["get_or_create"],
  "recommendation_hint_symbol": "get_settings",
  "notes": "1-3 sentence scout summary: what receiver you identified and why this bucket.",
  "false_positive_reason": null
}
```

`false_positive_reason` is set when `bucket` is
`false_positive_stdlib_wrapper` or `legitimate_cache_warming`. One of:

- `stdlib_dict_update` — receiver is a `dict`.
- `stdlib_set_update` — receiver is a `set`.
- `stdlib_list_mutation` — receiver is a `list` (`.append`,
  `.extend`, etc. aren't detected, but defensive).
- `cbv_context_data` — receiver is `ctx` from
  `super().get_context_data(...)`.
- `singleton_populator` — `get_or_create` on a settings / counter row
  the read depends on.
- `hidden_mutation_marker_missed` — scout spotted the allow-list
  marker but the detector missed it.

## Rules for your output

1. **Default conservatively.** When the scout cannot resolve the
   receiver with confidence, bucket as `rename_to_mutator` — the
   subsequent `/fix-workflow` step will catch genuine false positives
   in code review. Under-reporting is worse than over-reporting here.
2. **Keep `notes` tight.** 1 to 3 sentences. The hit evidence carries
   the detail.
3. **Never propose the rename yourself.** Your job is to bucket. The
   `/fix-workflow cluster:<symbol>` skill owns the rename / split
   proposal.
4. **Respect the `# hidden-mutation:` allow-list.** It is a deliberate
   decision; `legitimate_cache_warming` is not a failure state.
