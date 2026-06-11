# /decide — threshold heuristics and ADR anti-patterns

Reference for skill maintainers and future scout sub-agents. The
`/decide` orchestrator does NOT read this file — its rules are baked
into `SKILL.md`. This file exists so when somebody asks "why does the
skill reject X?" the rationale is recoverable.

---

## When a choice qualifies as a decision

A choice is an ADR candidate if **any** of the following hold:

1. **It constrains future work.** "Every status field uses TextChoices"
   binds every future model migration. "We use Postgres" binds every
   future query. "Celery dispatches go through `safe_dispatch`" binds
   every future task.
2. **It excludes an alternative explicitly.** "We picked `models.TextChoices`
   over plain `Enum`" makes the rejection retrievable. Without the
   ADR, a future engineer can rediscover plain `Enum` and re-litigate
   the choice from scratch.
3. **It sets an expiration.** "Migrate off the legacy crawl_jobs table
   by 2026-Q3" is a decision because the date is the contract. The
   ADR is the future trigger to come back.

A choice is **not** an ADR candidate if it's only:

- A preference (`# noqa: E501` style choices, naming conventions).
- A debugging note (those go in `.claude/tasks/lessons.md`).
- A status report ("we shipped the X feature" — commit message / PR).
- A tutorial ("how to add a new site" — that's documentation).
- An execution detail of an already-decided rule (handled by
  `canonical-patterns.md` / `architectural-smells.md` entries).

---

## ADR anti-patterns this skill is architected to prevent

### "Diary ADR" — recording what happened, not what we decided

Bad:

> ## Decision
> On 2026-04-15 we noticed that the crawl_job table was growing 2GB/week.
> We added an index on (site_id, status) and the dashboard query
> dropped from 4s to 100ms.

This is a fix log, not a decision. The actionable rule (if any) is
"all crawl_job queries must filter by site_id+status" or "we cap the
table at 30 days of history" — those would be the decision.

### "Junk drawer ADR" — three independent choices stuffed together

Bad: an ADR titled "Crawl job conventions" that bundles
`(table-naming, status enum, retry policy)`. Each clause is
independently supersedable; bundling them means superseding any one
forces a rewrite of the whole.

Rule: one ADR per choice. If the work has three choices, write three
ADRs that cross-reference each other via `tags:`.

### "Restating the code" ADR

Bad: an ADR whose Decision section is just "use `safe_dispatch`" with
no Context, no Alternatives, no Consequences. That's a
canonical-patterns entry, not a decision — the entry doesn't tell
future-you why the alternative was rejected.

Rule: if you can't write two real Alternatives and at least one
non-trivial Consequence, the choice is probably a pattern (lives in
`canonical-patterns.md`), not a decision.

### "Phantom ADR" — proposed but never accepted, never superseded

A `proposed` ADR older than 30 days is a smell. Either accept it
(it's load-bearing), reject it (move to `status: deprecated`), or
supersede it (pick a different choice). The registry's `audit`
command flags these.

Rule: every ADR's status moves to a terminal state (accepted,
superseded, deprecated) within 30 days of creation. `proposed` is for
under-review work, not a parking lot.

### "Overstuffed registry" — 20 ADRs/quarter

Sustained high-volume ADR creation usually means the team is
recording preferences as decisions, OR is in a genuine architectural
upheaval that warrants a single coordinating spec instead of a swarm
of micro-decisions.

Rule: target 2-5/quarter. If exceeded, audit for diary / preference /
junk-drawer ADRs and consolidate.

---

## Backref convention

Every ADR that has a matching pattern or smell should:

1. Set `related_pattern: <anchor>` and/or `related_smell: <anchor>` in
   frontmatter.
2. Recommend (in the `/decide` summary) adding `Decided in: <NNNN>` to
   the matching `canonical-patterns.md` / `architectural-smells.md`
   entry.

The backref is the navigation aid that turns the registry from a flat
log into a graph. Without it, a future engineer reading
`architectural-smells.md` cannot find the decision that defined the
smell — they have to grep the registry hoping the slug overlaps.

The backref is added by a separate, human-approved edit — not by
`/decide` itself. The skill *recommends* the addition; the user
applies it (or asks the next agent to). This protects the docs from
auto-edits the user didn't review.

---

## Form B (supersession) gotchas

When superseding ADR `<existing>` with new ADR `<new>`:

- New ADR's `supersedes: [<existing>]` is the source of truth.
- Existing ADR's `superseded_by: <new>` is a redundant convenience
  pointer that `decisions.py link-check` validates.
- Both must be set, or `link-check` reports a broken chain.
- The skill writes `<new>` immediately, but stages the
  `superseded_by` edit on `<existing>` as a Form C amend that the
  user runs after approval. This avoids touching an `accepted` ADR
  before the new ADR is itself approved.

If `<existing>` is already superseded (it has a non-null
`superseded_by`), walk the chain to the leaf and supersede the leaf
instead — superseding a non-leaf creates a Y-shaped chain that's
visually confusing.

---

## Cross-references

- `ai-docs/decisions/README.md` — registry conventions, format spec.
- `.claude/docs/canonical-patterns.md` — current-state law (each entry
  may carry a `Decided in: NNNN` backref).
- `.claude/docs/architectural-smells.md` — current-state problem
  recognition (same backref slot).
- `scripts/decisions.py` — CLI (`init | list | show | rebuild | audit
  | link-check`).
- `.claude/skills/_common/skill-frontmatter.md` — the agent decision
  contract this skill complies with.
