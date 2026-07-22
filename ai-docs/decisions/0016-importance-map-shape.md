---
id: "0016"
namespace: core
title: Importance Map Shape
status: proposed
date: 2026-05-14
deciders: []
supersedes: []
superseded_by: null
applies_to:
  - .claude/skills/find-orphaned-ideas/
  - .engineering/docs/importance-map.md
embodied_by: ["skill:find-orphaned-ideas"]
tags:
  - idea-tracking
  - audit-tooling
  - declarative-ownership
related_smell: null
related_pattern: null
---

# Importance Map Shape

## Context

`/find-orphaned-ideas` ships six detector modes (stale / harvest /
plan-dropouts / TODO / stale-plans / dead-prototype). None of them
weight findings by importance — a 30-item backlog in a load-bearing
extraction module gets the same audit as 30 items of UI polish.

The plan tracked at `~/.claude/plans/async-rolling-biscuit.md`
(Improvement 3) proposes a seventh mode, `--attention-gap`, that
surfaces neglect in high-value areas. To do that, the skill needs a
declarative map of *what is important* — authored by project owners,
read by tooling, stable enough to inform recommendations.

This ADR resolves the **shape** of that map. The downstream signals,
output columns, ranking algorithm, and the "useful audit" threshold
are deferred to the Improvement 3 implementation work — a post-ADR
addendum to the plan.

Four forks are open:

| Fork | Options |
|---|---|
| Format | Markdown w/ structured headers / YAML / frontmatter on existing atlas files |
| Unit of importance | Folder paths / `subsystem_kind` tags / product workflows / module-glob / mixed |
| Maintenance model | Manual edits / inferred from ADR + adoption recency / drift detector |
| Default when absent | Mode emits "no importance map" and stops / falls back to subsystem-kind frequency / refuses to run |

## Decision

The importance map is a single Markdown file at
`.claude/docs/importance-map.md`, structured as named `## <area>`
sections each declaring **one or more locator lines** (folder paths
and/or `subsystem_kind:` tags) plus a tier label. Maintenance is
manual; a drift detector flags locator lines whose paths no longer
exist. When the file is absent or empty, `--attention-gap` exits
cleanly with a "no importance map declared — see ADR 0016" notice.

In detail:

- **Format: Markdown w/ structured headers.** Devs already author
  markdown; diffs are reviewable in PRs; the ADR
  0005 (`agent-rules-design.md`) convention places agent-readable
  docs under `.claude/docs/`. The skill parser handles minor format
  drift (extra whitespace, trailing punctuation, comment lines).
- **Unit of importance: mixed (folder paths AND `subsystem_kind`).**
  Folder paths match filesystem scans (TODO mode, dead-prototype);
  `subsystem_kind` matches ledger projections (stale, harvest,
  stale-plans). Both are first-class. Product workflows are too
  high-level — the workflow registry skill is still maturing and
  not every project will use it. Glob patterns are allowed in the
  folder-path slot for flexibility.
- **Maintenance: manual + drift detector.** Owners declare what
  matters; the drift detector catches stale paths. No auto-inference
  from ADR adoption — that would erode the declarative intent
  (the map is "what the team decided to defend", not "what the
  system noticed").
- **Default when absent: emit notice, exit clean.** Faking
  importance from `subsystem_kind` frequency would mislead the
  reader into thinking they have a weighted audit when they don't.
  Refusing to run is too harsh. The honest middle is: "audit can't
  run without owner declarations — here's how to author the file."

### File shape

```markdown
# Importance map

> Project owners declare which areas are high-value enough that
> `/find-orphaned-ideas --attention-gap` should surface neglect
> against them.

## <area name>

Tier: <critical | core | supporting>

Locators:
- `path:<folder-path-or-glob>` — <one-line why>
- `kind:<subsystem_kind>` — <one-line why>

Notes (optional): <free-form context, links to ADRs or specs>
```

Tier vocabulary is `critical` (project would break without it),
`core` (load-bearing but replaceable), `supporting` (real work but
not central). The skill ranks `critical` strictly above `core`
strictly above `supporting` in its output.

## Alternatives considered

**YAML format.** Tighter schema, easier programmatic validation,
but worse for human authoring (indent-sensitive, no inline
explanations). Rejected because the map is *primarily* a human
artifact — devs read and edit it during planning. The drift
detector can validate semantic shape without YAML's strictness.

**Frontmatter on existing atlas files** (e.g. each
`.claude/docs/subsystems/<name>.md` declares its own importance).
Distributes the signal but makes "what's important?" a derived
query rather than a glance at one file. Rejected — the audit
wants a one-stop authoritative map; distribution defeats the
declarative purpose.

**Unit = product workflows only.** Higher-level and arguably more
meaningful, but the workflow registry (`/map-product-workflow`) is
not yet ubiquitous. Rejected — would block adoption on a
prerequisite that's not yet stable.

**Unit = `subsystem_kind` only.** Aligns cleanly with ledger
projection, but excludes filesystem-only signals (TODO / dead-
prototype) which know paths, not kinds. Rejected for the same
reason — incomplete coverage.

**Inferred-from-ADR maintenance.** The drift detector can mark
paths stale; we don't need to auto-derive importance from
"how often does this ADR get adopted?" The two ideas are
orthogonal: importance is declarative (what the team
defends), adoption is empirical (what shipped). Conflating them
erodes both signals.

**Default-absent: fall back to frequency.** Tempting because it
makes the mode "always work", but the output would carry the
false claim that the user has a weighted audit. Rejected because
the cost of a misleading report is higher than the cost of an
explicit "you need to author the file" notice.

**Default-absent: refuse to run.** Too aggressive — blocks
exploration. Rejected.

## Consequences

**Easier:**
- Owners can declare importance once and have multiple detectors
  read it (current `--attention-gap`, future `/triage-debt`
  aggregation, possibly `/audit-pattern-library`).
- The map is reviewable in PRs like any other markdown doc; new
  hires can read it to understand what the team defends.
- The drift detector catches stale locator paths without needing
  schema validation.

**Harder:**
- Adoption requires owner judgment — there's no automatic path. A
  team that won't author the file gets no `--attention-gap` mode.
- Adding a new unit kind (e.g. `workflow:<name>`) requires a parser
  update — locators are not free-form.

**Now disallowed:**
- Embedding importance signals in atlas-file frontmatter (use this
  file instead).
- Programmatically auto-generating the importance map from ledger
  activity (would erode declarative intent).
- Falling back to frequency when the file is absent (would create
  a misleading "weighted" audit).

## Verification

- **Drift detector** ships as part of `/find-orphaned-ideas
  --attention-gap` implementation (the post-ADR addendum). It
  walks every locator line and flags `path:` entries whose path
  doesn't exist and `kind:` entries that don't appear in the
  ledger's `subsystem_kind` set.
- **Empty-file behavior** is verified by the plan's verification
  table row 8: "`--mode attention-gap` with no `importance-map.md`
  → 'No importance map — see ADR 0016' notice; clean exit."
- **Malformed-file behavior** is verified by row 10: "malformed
  `importance-map.md` → diagnostic, no crash."
- **`.engineering/docs/importance-map.md`** is the canonical location
  (relocated from `.claude/docs/` by ADR 0021; loaders keep a one-time-warning
  `.claude/docs/` fallback during transition).
  The engineering-skills mirror ships a template (header + commented
  example areas) so adopters know the format. Hosts copy and fill.
