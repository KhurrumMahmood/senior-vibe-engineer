# Verification procedure + bucket taxonomy — implicit-state

This file is loaded by **scouts**, not by the orchestrator. It tells a
verifier exactly what to check for one candidate and how to classify
the result.

## The two sub-patterns

| Sub-pattern | Detector hits | What the smell is |
|---|---|---|
| **A. Stringly-typed state** | `stringly_compare`, `stringly_field`, `possible_state_literal` | State lives in bare string literals or a plain `CharField` without `TextChoices`. Typos in `"in_porgress"` silently no-op. |
| **B. Tuple-inferred identity** | `tuple_identity` | "The active job for site X" is computed from `(status, timestamp, nullness)` tuples instead of an explicit FK. Breaks under race conditions. |

Both sub-patterns surface from smell 2 in
`.claude/docs/architectural-smells.md`. Extracting a `TextChoices` enum
fixes sub-pattern A; introducing a FK fixes sub-pattern B.

## Bucket definitions

Write exactly one of these into ``bucket`` on your JSON output:

| Bucket | Criteria | Recommendation |
|---|---|---|
| **extract_enum_candidate** | Sub-pattern A hit. Field uses a bare string literal; no TextChoices enum references the field, or the enum exists but callers haven't migrated. | `/extract-enum <symbol>` — propose `models.TextChoices` + caller migration. |
| **introduce_fk_candidate** | Sub-pattern B hit. The `.filter(...)`/`.first()` result is used as the identity of "the active X" (assigned to variable named `job`/`task`/`run`/`export`/`active`, or later code calls `.save()` / `.delete()` on the returned row). | `/introduce-fk <symbol>` — propose FK + backfill + set-NOT-NULL two-step migration. |
| **enum_already_used** | Sub-pattern A false positive. The comparison uses a variable whose value is a `TextChoices` member (e.g. `job.status == JobStatus.PENDING` — the detector doesn't resolve cross-scope enum references). OR the hit is in code that already imports and uses the enum member elsewhere. | Drop from candidates. |
| **legacy_allow_list** | The hit is noqa'd with `# noqa: stringly-status: <reason>`. The SUSPECT scan sees it because the AST doesn't honor comments. | Leave as-is; note the reason. |

## Verification checklist (apply in order)

### 1. Read the enclosing function.

The scout must open the file at the candidate's line and read the full
enclosing function (or class body for `stringly_field` hits). This
gives context for whether the pattern is genuine.

### 2. Check for an existing TextChoices enum.

For Sub-pattern A candidates, grep the file and its neighbors for:

```bash
git grep -n "class.*Choices\b" core/models/
git grep -n "class.*Status\b" core/models/
git grep -n "class.*State\b" core/models/
git grep -n "class.*Phase\b" core/models/
```

If the model referenced in the hit's file already has a TextChoices
subclass defined — and the comparison uses a variable whose name
matches the enum member (e.g. `status == some_var` where `some_var`
was previously bound to `JobStatus.PENDING`) — bucket as
`enum_already_used`.

The detector only flags bare string literals (`"pending"`), so a hit
with `literal: "pending"` is authoritative that a string literal is
being compared; the question is whether the field has an enum at all.

### 3. Check for the stringly-status noqa marker.

Open the file at the hit's line. If any line in the flagged
construct's range has `# noqa: stringly-status: <reason>` (non-empty
reason), bucket as `legacy_allow_list` and record the reason in
`notes`.

### 4. For `tuple_identity` hits — confirm identity usage.

The detector records `assigned_to` and `active_hint`. The scout must
read the next ~15 lines after the assignment and classify how the
result is used:

- **Identity usage (introduce_fk_candidate):** the result is treated
  as a row to mutate or reference by id: `active_job.save()`,
  `active_job.delete()`, `return {'job_id': active_job.id}`, or stored
  in another model's FK-shaped field.
- **Freshness check (enum_already_used):** the result is only tested
  for truthiness (`if recent_successful_crawl: return cached_value`).
  The time filter is a legitimate query predicate, not identity.

`active_hint: true` is a soft signal — still verify usage before
bucketing. A variable named `active_job` might still be used only as
"has one?" evidence.

### 5. For `stringly_field` hits — confirm the field has no enum.

`stringly_field` fires when `status = models.CharField(...)` has no
`choices=<TextChoices>` kwarg. Read the model class in full:

- If a neighboring field like `STATUS_CHOICES = [...]` is referenced
  via `choices=STATUS_CHOICES`, the scout confirms this is a legacy
  list-of-tuples. Bucket as `extract_enum_candidate` — the lint rule
  treats these as stringly-typed.
- If the scout finds a `models.TextChoices` subclass in the same file
  but the field doesn't reference it (e.g. via `choices=MyChoices.choices`),
  still bucket as `extract_enum_candidate` — the enum is unused.

### 6. For `possible_state_literal` hits — cross-check with compares.

`possible_state_literal` flags dict literals like `{"status":
"pending"}` in files that also have `stringly_compare` hits. These are
often API response payloads that must match the wire format — not
necessarily smells. The scout:

- **If the dict is a response payload** (inside a function that
  returns `JsonResponse(...)` or similar), bucket as `enum_already_used`
  with `notes: "wire format payload, not internal state"`.
- **If the dict is internal state** (stored in memory, passed to
  `.update()` / `.filter()`), bucket as `extract_enum_candidate`.

## Output schema

Write a JSON file at `{{output_path}}`:

```json
{
  "candidate_id": "implicit-state-0001",
  "file": "core/views/crawling.py",
  "pattern": "stringly_compare",
  "bucket": "extract_enum_candidate",
  "confidence": "high",
  "hit_count": 5,
  "fields_touched": ["status"],
  "symbols": ["bulk_crawl_collection_task"],
  "recommendation_hint_symbol": "bulk_crawl_collection_task",
  "notes": "1-3 sentence scout summary of what you verified and why this bucket.",
  "false_positive_reason": null
}
```

`false_positive_reason` is set when `bucket` is `enum_already_used` or
`legacy_allow_list`. One of:

- `enum_member_used_via_variable` — comparison uses a variable bound
  to a `TextChoices` member.
- `wire_format_payload` — dict literal matches a response wire format.
- `noqa_marked` — `# noqa: stringly-status:` present.
- `freshness_not_identity` — tuple-identity shape is a time-window
  existence check, not identity.

## Rules for your output

1. **Default conservatively.** When the function body doesn't clearly
   confirm identity usage, bucket a `tuple_identity` hit as
   `introduce_fk_candidate` **only** if `active_hint: true` AND the
   scout confirms mutation-or-id-access downstream. Otherwise bucket
   as `enum_already_used` with `false_positive_reason:
   "freshness_not_identity"`.
2. **Keep `notes` tight.** 1 to 3 sentences. The full evidence lives
   in the detector hits.
3. **Never propose the refactor yourself.** Your job is to bucket. The
   `/extract-enum` and `/introduce-fk` skills do the proposal work.
4. **Respect the noqa allow-list.** `# noqa: stringly-status:` is a
   deliberate decision; `legacy_allow_list` is not a failure state.
