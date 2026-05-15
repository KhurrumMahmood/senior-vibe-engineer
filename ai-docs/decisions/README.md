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
id: 0001
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
