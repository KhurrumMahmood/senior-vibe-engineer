---
id: 0001
title: Use TextChoices for all status / phase / state fields
status: accepted
date: 2026-04-30
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [app/]
tags: [stringly-state, lint, models]
related_smell: stringly-typed-state
related_pattern: stringly-status
---

# Use TextChoices for all status / phase / state fields

> Retro-authored ADR. The convention has been in force since the
> `stringly-status` lint rule landed; this ADR pins the rationale so
> future engineers and AI agents can trace it back.

## Context

Several state fields in `app/models/` (e.g. `crawl_job.status`,
`brand_download.status`, `field_extraction_config.phase`) historically
stored bare strings — `"pending"`, `"in_progress"`, `"failed"` — with
comparisons made against literal strings throughout `app/views/`,
`app/services/`, and `app/tasks/`.

This created three durable problems:

1. **Silent typos.** A typo in `obj.status == "in_porgress"` produces a
   no-op comparison that passes type checking and looks correct in
   isolation, but never matches at runtime. Fixtures wired to the
   correct string mask the bug entirely.
2. **No call-site discoverability.** Renaming a value or auditing all
   producers/consumers required a string grep with no IDE assistance.
3. **No exhaustive switch.** New states could be added without forcing
   any caller to handle them.

The pattern recurred enough that `/find-implicit-state` was built
specifically to surface it (see `architectural-smells.md` smell 2).

## Decision

Every `models.Model` field named `status`, `phase`, or `state` (or any
field whose values come from a fixed enumeration) must be declared as a
`models.TextChoices` enum, with the field's `choices=` argument
referencing the enum class.

Every comparison in application code against such a field must reference
the enum member, not the bare string. `obj.status == JobStatus.PENDING`,
not `obj.status == "pending"`.

The `stringly-status` ruff rule (`scripts/lint/no_stringly_typed_status.py`)
enforces both halves at commit time, scoped to changed files only.

## Alternatives considered

- **Bare strings + `# noqa` discipline.** Rejected: relies on author
  diligence; the original failure mode is exactly that. Lint rules that
  permit a bare-string escape valve get used as one.
- **Plain Python `Enum`.** Rejected: doesn't integrate with Django's
  `choices` admin/form rendering or with `get_<field>_display()`.
  `TextChoices` is the project's native enum primitive; using anything
  else fragments the codebase.
- **String constants module (`STATUS_PENDING = "pending"`).** Rejected:
  doesn't constrain field values, doesn't render in admin, doesn't
  produce an IDE-assisted enumeration.

## Consequences

**Easier:**
- Auditing all producers/consumers of a state — IDE find-references
  works on the enum member.
- Adding a new state — every consumer that switches on the field gets
  surfaced by the type system or `get_<field>_display()` callers.
- Catching typos — the comparison is now an `AttributeError`, not a
  silent no-op.

**Harder:**
- Adding a one-off "scratch" state requires editing the enum class.
  This is by design — the whole point is that state values are part of
  the model contract.

**Now disallowed (lint-enforced):**
- Bare-string comparison against `.status` / `.phase` / `.state` fields.
- Declaring such a field without `choices=`.

**Allow-list:** `# noqa: stringly-status: <reason>` with a non-empty
reason. Use sparingly; the reason must explain why the enum form is
genuinely impossible (e.g. value comes from an external API and the
enum would lag).

## Verification

- **Lint rule**: `scripts/lint/no_stringly_typed_status.py`, scoped via
  diff to changed files. CI gate.
- **Tests**: `tests/lint/no_stringly_typed_status_bad.py` and
  `_good.py` exercise the rule's positive and negative paths.
- **Doc backref**: `.claude/docs/canonical-patterns.md` `stringly-status`
  entry carries `Decided in: 0001`.
- **Smell catalog**: `.claude/docs/architectural-smells.md` smell 2
  (stringly-typed state) carries `Decided in: 0001`.
