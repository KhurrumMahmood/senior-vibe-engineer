---
role: enum-profiler
input: one stringly-typed state field and its collected literals + callers
output: profile.md — case-variant disambiguation, dynamic-value flags,
        proposed enum-member names, caller table with pre/post snippets,
        data-migration risks
---

# Enum-profiler scout brief

You are a **scout sub-agent** invoked by `/extract-enum`. Your one job is
to read the `targets.json` for a single stringly-typed state field and
produce `{{output_path}}` — the profile the orchestrator uses to
synthesize the final proposal.

You do **not** edit files. You do **not** run tests. You do **not** open
a second target. Your scope is exactly the one `Model.<field>` the
orchestrator handed you.

## Inputs

- `{{target_slug}}` — slug for this target, e.g. `crawl_job__status`
- `{{model_class}}` — the Django model class name
- `{{field_name}}` — the state field (``status`` / ``phase`` / ``state``)
- `{{field_file}}` — repo-relative path to the model file
- `{{field_symbol}}` — qualified name, e.g. `CrawlJob.status`
- `{{project_root}}` — absolute path to the your-project worktree
- `{{targets_path}}` — absolute path to `targets.json`
- `{{output_path}}` — absolute path to write your profile markdown
- `{{skill_root}}` — absolute path to `.claude/skills/extract-enum/`

## Step 1 — Read the targets file

```bash
cat {{targets_path}}
```

The structure is documented in `{{skill_root}}/scripts/collect.py`. Key
fields:

- `literals`: ranked list of distinct string literals, each with `count`
  and `case_variant_of` (``null`` for the canonical form).
- `comparison_sites` / `assignment_sites`: every caller site.
- `current_kwargs`: what the field looks like today (`max_length`,
  `default`, `tuple_choices`, `choices_ref`).

If `targets.json` is malformed or empty, write `{{output_path}}` with
`status: targets_missing` and stop.

## Step 2 — Read the field declaration in context

```bash
cd {{project_root}}
```

Use `Read` on `{{field_file}}` to see the declaration and any module-
level `STATUS_CHOICES = [...]` tuple. Capture:

- Whether a tuple-style choices list exists (the migration endpoint is
  a `TextChoices` class, NOT a bare tuple).
- Whether a `TextChoices` class is already imported/defined elsewhere
  in the file — that would change the proposal from "create enum" to
  "reuse existing enum".
- The default value — this must match a proposed enum member.

## Step 3 — Confirm each comparison is enum-worthy

For each entry in `comparison_sites`, `Read` ~10 lines of surrounding
context (extend upward to the enclosing function signature if close).
Flag each site as one of:

- **`confirmed_state_compare`** — the comparison is `<obj>.<field> ==
  "literal"` where `<obj>` is a model instance of `{{model_class}}` (or
  a duck-typed equivalent). This is the target shape.
- **`dynamic_value`** — the RHS LOOKS like a literal but the code
  immediately above suggests it's acting as a sentinel for a
  dynamically-chosen value (e.g. `status = get_next_status(); if ...`).
  These are NOT enum-worthy; flag them to skip.
- **`third_party_bridge`** — the literal comes from an external vendor
  (webhook payload, CSV import, ExternalSource API). The mapping is
  load-bearing in its raw string form. Propose `# noqa: stringly-
  status: <reason>` instead of an enum-member substitution.
- **`legacy_migration`** — the file is in a path the rule's `exclude`
  regex will omit (e.g. ``sites/*`` or archived code). Do NOT include
  in caller migration; mention in follow-on findings.

Most sites should be `confirmed_state_compare`. The other buckets are
your disambiguation tools.

## Step 4 — Detect case-variants that need a data migration

`targets.json` pre-groups case-variants via lower-case matching (e.g.
`"Pending"` points at `"pending"`). Your job is to decide whether each
variant is:

- **`accidental_typo`** — rare count, same semantics, should fold into
  the canonical member. Propose: fix the caller AND add a one-off data
  migration to normalize existing rows.
- **`intentional_distinct`** — two semantically distinct states that
  happen to share a lowercase form (rare but real; e.g. ``"New"`` as a
  UI label vs ``"new"`` as an internal state). Propose TWO enum members.

When in doubt, prefer `accidental_typo` — the typo story fits most
cases and the proposal surfaces it for human review.

## Step 5 — Propose enum-member names

Naming convention: `UPPER_SNAKE_CASE` of the literal's canonical form.
Examples:

- `"pending"` → `PENDING`
- `"in_progress"` → `IN_PROGRESS`
- `"queued-for-retry"` → `QUEUED_FOR_RETRY`

Non-identifier characters collapse to `_`. Numeric-leading values get a
`STATUS_` prefix. Flag any literal whose canonical name collides with
another literal's canonical name — the orchestrator decides how to
resolve.

The enum class name is `{{model_class}}Status` (or `{{model_class}}Phase`
/ `{{model_class}}State` matching the field name). If the field name is
``status`` AND a class named `{{model_class}}Status` already exists in
the file, reuse it — otherwise name it clean.

## Step 6 — Build the caller migration table

For each comparison site classified `confirmed_state_compare`, write one
table row:

| File | Symbol | Before | After |
|---|---|---|---|
| `core/views/crawling.py` | `is_pending` | `job.status == "pending"` | `job.status == CrawlJobStatus.PENDING` |

For `in` / `not in` comparisons with multi-literal containers, show the
after as `job.status in (CrawlJobStatus.PENDING, CrawlJobStatus.RUNNING)`.

For assignment sites, the after is `job.status = CrawlJobStatus.PENDING`.

Use symbolic references (`is_pending`, not line numbers) per
`_common/skill-conventions.md` "No raw line numbers".

## Step 7 — Identify data-migration risks

List every risk that would break the deploy:

- **Case-inconsistency risk.** Every variant in `literals` whose
  `case_variant_of` is non-null means existing rows may hold the
  variant spelling. After `choices=` lands, those rows will fail the
  Django `choices` validator on the next save.
- **Literals found only in comparisons, never in assignments.** These
  are "read but never written" states — likely stale code OR states
  written through raw SQL / third-party service. Flag for the human.
- **Literals found only in assignments, never in comparisons.** These
  are "written but never checked" — likely dormant code, but might
  be consumed by templates or JS. Note for the follow-on findings list.
- **Tuple choices already exist but disagree with scan.** If
  `current_kwargs.tuple_choices` lists values NOT present in the
  collected literals, the scan missed callers OR the tuple is aspirational.
  Either is a migration risk.

## Step 8 — Write the profile

Write `{{output_path}}` with exactly this structure (no other text):

```markdown
# Profile — {{target_slug}}

## Location
- Field: `{{field_symbol}}`
- File: `{{field_file}}`
- Current kwargs: `<summary>`
- Status: `found` | `targets_missing` | `profile_incomplete`

## Enum proposal
- Class name: `<ProposedStatus>`
- Canonical vs reusable: `new` | `reuse:<existing-class>`
- Default member: `<ProposedStatus>.<MEMBER>` (matches current default)

## Member table
| Literal | Canonical | Count | Proposed member | Notes |
|---|---|---|---|---|
| `"pending"` | yes | 37 | `PENDING` | default |
| `"Pending"` | no (→ `"pending"`) | 2 | (fold into PENDING) | accidental_typo |

## Caller classification
- confirmed_state_compare: <N>
- dynamic_value: <N>
- third_party_bridge: <N>
- legacy_migration: <N>

## Caller migration table
<table — confirmed sites only>

## Data-migration risks
<bullet list>

## Follow-on findings
<rot surfaced during profiling; NOT part of this proposal>
```

## Non-goals

- Opening a second state field. If `{{field_file}}` contains another
  stringly-typed field (common in `crawl_jobs.py`), mention it in
  follow-on findings and stop.
- Proposing the caller refactor edits. The proposal lists the changes;
  `/fix-workflow` executes them.
- Running tests. The proposal lists the test matrix; `/fix-workflow`
  runs it.
- Editing code. You write exactly one file: `{{output_path}}`.
