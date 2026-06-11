# Decision registry — case law for the codebase

This directory holds **architectural decision records** (ADRs). Each
ADR pins a choice that constrains future work: an excluded alternative,
a convention that supersedes a prior one, or a tradeoff that future
authors should not relitigate without reading the prose here first.

## When to add a decision

A choice rises to the level of an ADR when it satisfies at least one of:

1. **It constrains future work.** "From now on, status fields use
   `TextChoices`." A new caller can't re-introduce string literals
   without violating the rule.
2. **It excludes an alternative explicitly.** "We chose Celery + Redis
   over RQ because…". A future engineer asking "should we switch to RQ?"
   has the case here, including the rejected reasoning.
3. **It sets an expiration.** "Use the legacy import path until the
   2026-Q3 schema migration; after that, switch to the new API." The
   ADR is the single place the expiration lives.

A choice does **not** rise to the level of an ADR when it is:

- A bug fix (just fix it; commit message is enough).
- A refactor with no convention change (the spec in `ai-docs/specs/`
  carries the execution detail).
- A one-off implementation detail (e.g., "this regex matches FJC v2
  product URLs"). That goes in `lessons.md` if anywhere.

Target cadence: **2-5 ADRs per quarter**. Faster growth signals
over-recording; the noise dilutes the signal. If you find yourself
reaching for `/decide` more than weekly, the threshold is wrong — most
of those choices belong in `lessons.md` or commit messages.

## Format

`<NNNN>-<slug>.md` with this frontmatter:

```yaml
---
id: "0001"              # local display/order; quote it (PyYAML reads 0010 as octal) — NOT the cross-repo identity
namespace: core         # core = portable toolkit; "project" = a host adaptation
title: Use TextChoices for all status fields
status: accepted        # proposed | accepted | superseded | deprecated
date: 2026-04-30
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [core/]
tags: [stringly-state, lint]
related_smell: stringly-typed-state    # → architectural-smells.md anchor
related_pattern: stringly-status       # → canonical-patterns.md anchor
---

## Context
## Decision
## Alternatives considered
## Consequences
## Verification
```

Use `python3 scripts/decisions.py init <slug>` to scaffold; it
auto-assigns the next id.

### Identity: `<namespace>:<slug>`

The **intended canonical identity** of an ADR is `<namespace>:<slug>` — e.g.
`core:textchoices-for-state`. It is semantic, so two repos can't collide on it the way
they collide on `NNNN` (where `core:0019` and a downstream `project:0019` are different
decisions). Two namespaces exist:

- **`core`** — the portable toolkit (this repo). Open-source; its ADRs avoid references
  to any *specific private host* (bare `applies_to` paths and `host:`-prefixed
  placeholder paths are both fine — see "Portable `applies_to` paths" below).
- **`project`** — a host adaptation (e.g. a private downstream repo). Its ADRs may
  `supersede` or refine a `core:` decision and cite it by `core:<slug>`.

**Migration status (honest).** The slug is the *target* identity, not yet load-bearing
end-to-end. `decisions.py show` resolves a slug or `key`, but `supersedes` /
`superseded_by` / `link-check` still match on `NNNN`, and the ~230 existing
`ADR NNNN` backrefs across the docs are not yet rewritten to slugs. So today `NNNN` is
still the key the tooling resolves; the NNNN→slug migration (resolver + backref rewrite)
is tracked, unfinished work — not a delivered guarantee.

### Optional fields: `provenance`, `assumes` / `revisit_when`

Three optional frontmatter fields carry decision hygiene (see
`core:decision-assumptions-and-revisit-triggers`):

- **`provenance:`** — a one-line note that the decision was validated in a downstream
  adaptation and is offered here as a calibrated default. A `core:` ADR with
  `provenance` may legitimately sit at `status: proposed` (core has nothing to enforce
  it against yet) without being stale.
- **`assumes:`** — the falsifiable condition(s) the decision rests on.
- **`revisit_when:`** — the observable trigger that should re-open it (e.g. "the lint
  that enforces this is built in core"). Doubles as the place to record *deferred
  enforcement*: an ADR whose detector isn't built yet names that gap here.

`audit` treats a `proposed` ADR carrying `revisit_when` or `provenance` as
**intentionally proposed** (deferred-on-a-condition / offered default), not 30-day
drift. A bare `proposed` ADR with neither still ages out.

## Portable `applies_to` paths

`applies_to` lists the code paths a decision governs, and `link-check`
verifies each one resolves. But an ADR that ships inside a reusable
skill/ADR pack is authored in one repo and *applied* in another — its
paths resolve in the importing **host project**, not in the pack's own
repo. Prefix those entries with `host:`:

```yaml
applies_to:
  - host:app/services/        # resolves in the host project
  - .claude/docs/linting.md   # resolves here — checked strictly
```

`link-check` resolves a `host:` entry when it is present, so drift is
still caught once the pack is imported, and reports its absence as
advisory rather than drift. Bare entries are always strict. Use `host:`
only for genuinely host-resident paths — an ADR about the pack's own
files (skills, docs, scripts) uses bare paths.

## Relation to other artifacts

Three tiers of knowledge, no overlap:

| Artifact | Role | When |
|---|---|---|
| `.claude/tasks/lessons.md` | Diary — informal append-log of project learnings | Lessons graduate to ADRs when they constrain future work |
| `.claude/docs/canonical-patterns.md`, `.claude/docs/architectural-smells.md` | Current state — law-as-stated, problem recognition | Each entry can carry a `Decided in: NNNN` backref |
| `ai-docs/decisions/` | Provenance + supersession chain — case law | Chronological, never rewritten in-place; superseded ADRs link forward |
| `ai-docs/plans/`, `ai-docs/specs/` | Forward-looking design + behavior-preserving execution checklists | Both carry an optional `motivating_decision: NNNN` field linking back to the ADR that authorized the work |

If you find yourself updating an ADR in place to change its conclusion,
**don't**. Mark the old ADR `status: superseded` with `superseded_by:
NNNN` pointing at a new ADR that explains the change. The chain is the
case law; rewriting destroys the audit trail.

## CLI usage

```bash
# Author a new ADR
python3 scripts/decisions.py init my-new-decision

# List all
python3 scripts/decisions.py list

# Show one in full
python3 scripts/decisions.py show 0001

# Rebuild reports/architecture/decision-index.json
python3 scripts/decisions.py rebuild

# Drift checks (proposed > 30 days, broken supersedes, bad status)
python3 scripts/decisions.py audit

# Link integrity (supersedes resolves; applies_to paths exist)
python3 scripts/decisions.py link-check
```

`audit` and `link-check` exit 1 on any drift — wire them into CI when
you want a hard gate on "no proposed ADR older than 30 days."
