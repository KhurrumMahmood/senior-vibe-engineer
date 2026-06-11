---
id: "0013"
namespace: core
title: Two-tier idea-tracking system (ledger + pattern library)
status: accepted
date: 2026-05-13
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to:
  - .claude/ideas/
  - .claude/patterns/
  - .claude/skills/
  - .claude/docs/
embodied_by: ["skill:track-idea", "script:scripts/ledger.py"]
tags: [knowledge-management, lifecycle, capture, curation]
related_smell: null
related_pattern: null
---

# Two-tier idea-tracking system (ledger + pattern library)

## Context

AI-grown projects produce many ideas. Many die — not from explicit
rejection (which leaves a trail), but from being **forgotten**:

- Plan dropouts: a multi-item plan ships items 1-3 and 5-7, and item 4
  silently vanishes. The AI that wrote the plan, the human that
  approved it, and the AI that implemented it all moved on.
- Harvested-then-dropped: a spike yielded one usable helper; the
  remaining 80% of the idea — which had more value — was set aside and
  never revisited.
- Half-finished spikes: a branch named `spike/<thing>` carries a
  prototype, a Markdown note, and a final commit from three months
  ago. No ledger says whether it succeeded, failed, or stalled.
- Rejected-but-instructive: an approach was tried, didn't work, and
  the lessons live only in the conversation transcript that produced
  it.

Existing project surfaces each capture a slice:

| Surface | Captures |
|---|---|
| `reports/BACKLOG.md` | open work items (intent ≠ idea lifecycle) |
| `.claude/tasks/lessons.md` | distilled learnings (no source-idea context) |
| `.claude/docs/precedents.yml` | curated case law for *mechanisms* (not for *ideas*) |
| `ai-docs/decisions/` | case law for *constraints* (ADRs; 2-5/quarter) |
| `ai-docs/plans/`, `ai-docs/specs/` | in-flight design + execution detail |
| Conversation transcripts | everything that didn't make it to a file |
| `git log`, `git branch -a` | shipped work, in-progress branches (no rejection signal) |

None of these capture the full lifecycle from `proposed` to
`adopted` / `rejected` / `harvested` / `superseded`, with composability
edges (which ideas feed into which composites), with lineage (which
ideas are evolutions of which prior ones), and with persistent lessons
that survive rejection.

The recurrence pattern: every few months, a thought from three months
ago surfaces in conversation, the author asks "did we try this?", and
the answer is some combination of "I think so?" and "let me grep the
repo." This is the signal that the lifecycle is leaking.

## Decision

Adopt a **two-tier idea-tracking system** with explicit capture and
curation surfaces:

**Tier 1 — Idea ledger** at `.claude/ideas/log.jsonl`. Append-only
JSONL. One intake record per idea; subsequent event records for
transitions, marker changes, edge additions, and adoption notes;
lesson records for distilled learnings. Bar for entry: *"would
future-me want this back?"* Schema in `.claude/docs/idea-ledger.md`.

**Tier 2 — Pattern library** at `.claude/patterns/<slug>.md`. One
Markdown file per pattern, promoted from a ledger entry when
`adoption_count >= 1`. Frontmatter carries `generalizability`
qualifier (`single-constraint-set` | `validated-across-N` |
`broadly-applicable`) that graduates as adoptions accumulate. Schema
in `.claude/docs/pattern-library.md`.

**Six skills** cover the lifecycle:

1. `track-idea` — capture and update (canonical write surface for
   Tier 1)
2. `find-orphaned-ideas` — multi-mode detector: file-orphan, stall,
   plan-dropout, harvest-opportunity, dormant-with-potential
3. `query-patterns` — explicit Tier 2 lookup for planning flows
4. `brainstorm-ideas` — exploration: web research + AI ideation
   emitting `proposed` intakes
5. `mature-existing-ideas` — periodic research pass against best
   practices / failure modes / alternatives; updates pattern research
   logs and ledger markers
6. `extract-existing-ideas` — one-shot bootstrap that mines existing
   surfaces (BACKLOG, lessons, precedents, memory, plans, ADRs,
   scratch dirs, TODO comments, branches) for candidate ledger
   entries

Plus an **inline prompt template** at
`.claude/docs/query-patterns-inline.md` — a low-friction sibling to
the `query-patterns` skill for ad-hoc lookups during exploratory work.

**Promotion gate dropped to ≥1 adoption.** Single use validates "value
for at least one set of constraints." This is a deliberate departure
from the ≥3-siblings rule for folder packaging (ADR 0006) and
cotton-primitive extraction. The asymmetry: structural promotion costs
real navigation friction if premature; documentary promotion costs one
Markdown file. The cheaper failure mode justifies the lower threshold.

**Quality markers as orthogonal axis.** `underdeveloped`,
`needs-research`, `has-more-potential` are markers (not states) that
persist across transitions. They steer attention; they do not gate
workflow. `mature-existing-ideas` uses `needs-research` to pick targets;
`find-orphaned-ideas` uses `has-more-potential` in
harvest-opportunity mode.

**Composability edges as first-class.** `feeds_into`,
`composes_with`, `lineage_parents` are required fields on intake
records, defaulting to empty arrays. This is the foundation for
evolutionary exploration: small ideas chain into composite workflows;
remixes and evolutions trace back to their parents; siblings cluster
into composition graphs.

**Self-referential bootstrap.** The first ledger entry is the
idea-tracking system itself, intake state `in-flight`, markers
`[needs-research, has-more-potential]`, generalizability
`single-constraint-set`. The first pattern entry mirrors it, with a
pre-populated Research log noting that `mature-existing-ideas` should
be the first skill run against the system. This demonstrates the
lifecycle on its own genesis and seeds the harness with a real
fixture.

## Alternatives considered

- **Single-tier (ledger only).** Rejected. Without a curated consumer
  surface, planning workflows would have to grep a growing JSONL file
  for relevance — query-hostile by construction. Curation is the
  consumer's interface.

- **Single-tier (curated patterns only).** Rejected. Drops the messy
  capture step where most lifecycle value lives. Plan dropouts,
  harvested-then-dropped fragments, and rejected-but-instructive
  experiments never reach the curation surface because they never
  prove themselves out — yet they are exactly the entries the
  rediscovery pattern keeps surfacing.

- **In-conversation tracking only (no files).** Rejected. The whole
  point of this work is durability across context windows. Anything
  that lives only in transcripts dies the moment a session ends.

- **Higher promotion threshold (≥3 adoptions).** Considered and
  rejected. The ≥3-siblings rule fits structural promotion where
  premature packaging causes real friction. Pattern promotion is
  documentary — the cost is one Markdown file. Waiting for 3
  adoptions loses the freshness of the first author's reasoning and
  costs the second author re-derivation effort. The `generalizability`
  qualifier captures the difference between "tried once" and "robust
  across contexts" without requiring abstinence.

- **Markdown for Tier 1 instead of JSONL.** Rejected for Tier 1.
  Tier 1 needs structured query and append-only event histories;
  Markdown frontmatter doesn't scale to dozens of events per idea.
  JSONL gives both, with the cost of being less hand-friendly than
  Markdown — mitigated by the `track-idea` skill carrying validation.

- **HTML + web components for Tier 2 now.** Rejected for v1, but
  tracked as a future direction with `has-more-potential` marker. The
  trigger for revisiting is when multiple AI toolchains parse the
  same HTML semantics and a web-component vocabulary stabilizes. The
  v1 commitment is schema stability so conversion is mechanical.

- **Closed enum for `subsystem_kind`.** Rejected. The user note that
  *ideas can apply to all kinds of sub-systems, based on the project
  type and its role in the real world* foreclosed any closed enum.
  Free-form tags, seeded by `extract-existing-ideas` from existing
  folder and document structure, scale across project types.

- **No skills, just the schemas.** Rejected. A schema without skills
  is a write-only surface — captures happen only when discipline is
  perfect, which it never is. The skills are how the system survives
  contact with real workflows.

- **Defer Phase 2 (the skills).** Considered briefly during scoping;
  rejected with self-recursive amusement. Deferring the idea-tracking
  system commits the exact failure mode the system is designed to
  prevent. Either it ships seriously or it doesn't ship at all.

## Consequences

**Easier:**

- Cross-conversation continuity: the next conversation that touches an
  idea reads its history without re-deriving context from transcripts
- Structured query for "have we tried this?" — `query-patterns` for
  curated, ledger projection for raw
- Lessons survive rejection — the value of "we tried X, it didn't
  work because Y" persists even when the idea ends
  `done outcome=rejected`
- Composability is first-class — small ideas can be traced into the
  composite workflows they feed; remixes back-track to their lineage
- Plan-dropouts surface mechanically rather than from rediscovery
- New surfaces (this very ADR; the format-evolution note for HTML
  patterns; the bootstrap entry) all get captured from day one rather
  than relying on someone remembering to write them down

**Harder:**

- Discipline cost: every idea worth capturing requires a `track-idea`
  call. Mitigation: `track-idea` is one command; `brainstorm-ideas`
  and `extract-existing-ideas` capture in bulk; the inline prompt
  template lowers the activation energy further.
- Promotion judgment: the ≥1-adoption gate is mechanical, but
  qualifier graduation (`single-constraint-set` →
  `validated-across-N`) requires human judgment about what counts as
  "distinct context." Mitigation: `audit-pattern-library` proposes
  upgrades; human confirms.
- Bootstrap cost: the first run of `extract-existing-ideas` against an
  established project produces dozens to hundreds of candidate
  entries. Mitigation: bootstrap output is review-first, write-after;
  no auto-write to the live ledger.
- Schema evolution risk: changes to the JSONL schema require
  migration logic in `audit-ideas`. Mitigation: append-only design
  means schema additions are non-breaking; reductions require an
  explicit migration event.

**Now expected:**

- New ideas of any consequence get a ledger entry — features,
  refactors, prompts, harness shapes, research probes
- Harvested or rejected ideas keep their lessons attached as lesson
  records (or cross-link to `.claude/tasks/lessons.md`)
- Patterns are the first stop in planning flows: `/plan-feature`,
  `/scope-feature`, `/architecture-fit` query the library before
  proposing approaches
- Periodic `mature-existing-ideas` runs against patterns with
  `needs-research` markers (cadence: opportunistic; not scheduled
  initially)
- Plan documents reference ledger entries for items they intend to
  execute; `find-orphaned-ideas plan-dropout` mode reads this back
- Composability is recorded at intake when known; back-filled by
  `audit-ideas` from explicit edges

**Now disallowed:**

- Idea-tracking that lives only in conversation transcripts or
  memory entries. Use the ledger.
- Pattern entries without `adoption_evidence` — capture as a ledger
  intake instead.
- In-place edits to ledger lines — use event records.
- Skipping the ledger when starting a spike branch. The spike branch
  name is acceptable as `origin`; the intake record is required.

## Verification

- **Data model specs (landed in this ADR's commit):**
  - `.claude/docs/idea-ledger.md` — Tier 1 JSONL schema, state machine,
    projection rules, examples
  - `.claude/docs/pattern-library.md` — Tier 2 Markdown schema,
    promotion gate, qualifier graduation, status lifecycle, format
    evolution note

- **Validation harness** (P2):
  `.claude/tests/ideas/fixtures/` with 7 scenario tests covering
  stalled-spike detection, plan-dropout detection, harvest-opportunity
  detection, ≥1 promotion eligibility, supersession chain integrity,
  resurrection of `done outcome=rejected` ideas, and an
  extraction-truth-set for `extract-existing-ideas`.

- **Skills** (P3-P5):
  Six skills under `.claude/skills/`:
  - `track-idea/`
  - `find-orphaned-ideas/`
  - `query-patterns/`
  - `brainstorm-ideas/`
  - `mature-existing-ideas/`
  - `extract-existing-ideas/`

  Each skill passes its scenarios in the harness before being marked
  ready. The inline prompt template lands as
  `.claude/docs/query-patterns-inline.md` alongside the skill.

- **Bootstrap** (P5):
  `extract-existing-ideas` runs against the host project that owns the
  ledger; candidate entries are reviewed manually before any write to
  `.claude/ideas/log.jsonl`. The first written entry is the
  self-referential `idea-tracking-system` intake.

- **Integration** (P6):
  - `CLAUDE.md` Supplementary Documentation table adds rows for
    `idea-ledger.md`, `pattern-library.md`, and
    `query-patterns-inline.md`
  - `skill-catalog.md` gains an IDEAS section grouping the six skills
  - `.augment/rules/imported/idea-tracking.md` mirrors the durable
    always-apply discipline (bar-for-entry + what-not-to-capture +
    skill listing)
  - Project `MEMORY.md` / equivalent gets a pointer noting the ledger
    surface
  - `.claude/ideas/README.md` + `.claude/patterns/README.md` provide
    direct-reader summaries for the on-disk surfaces

- **Mirror to engineering-skills** (P7):
  Once the system has survived contact with the host project's
  bootstrap, the generic skills + docs (sans seeded ledger entries)
  mirror to `engineering-skills/`. The bootstrap config (which
  surfaces to scan, what their formats are) becomes a template the
  receiving project fills in. This file is the mirrored copy; the
  authoritative ADR lives in the host project that first adopted the
  system.

- **Self-referential dogfood:**
  The first ledger entry is `idea-tracking-system` itself, with
  markers `[needs-research, has-more-potential]`. The first scheduled
  `mature-existing-ideas` run targets that entry. This ADR's
  motivating reasoning is itself a lesson record attached to that
  entry.
