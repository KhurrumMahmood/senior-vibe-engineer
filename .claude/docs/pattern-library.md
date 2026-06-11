# Pattern library — Tier 2 curated reusable patterns

Curated knowledge layer over the Tier 1 idea ledger (`idea-ledger.md`).
Where Tier 1 captures every idea — proposed, in-flight, stalled,
harvested, rejected — Tier 2 holds entries that have been adopted at
least once and are worth recommending to future work.

> Read this when: promoting a ledger entry to a pattern; writing a
> `query-patterns` / `promote-idea-to-pattern` / `mature-existing-ideas`
> skill; authoring or reviewing a `.claude/patterns/<slug>.md` file;
> deciding whether a pattern's qualifier should graduate.

## Location

`.claude/patterns/<slug>.md` — one Markdown file per pattern. The slug
matches the Tier 1 ledger entry it was promoted from, so the
back-reference is implicit. `audit-pattern-library` flags drift if a
pattern file's slug does not resolve to a ledger entry.

## What "pattern" means here

A reusable shape — code, prompt, workflow, harness, UI component, doc
structure — that has been used successfully at least once and is worth
recommending when the same problem class returns. Patterns are
*recipes*; ADRs are *case law*. Overlap exists (a mandated pattern often
motivates an ADR) but the lanes are distinct.

A pattern entry is not a tutorial. It assumes the reader has a problem
in hand and is asking "is there prior art?" — the Problem fit section
exists to confirm match in seconds.

## Promotion gate

A ledger entry becomes a pattern when **all three** hold:

1. `adoption_count >= 1` — single use validates value-for-one-constraint-set
2. The adoption evidence is recorded in the ledger (file path, PR, commit,
   workflow artifact)
3. `state == done` with `outcome in {adopted, harvested}`, OR `state ==
   in-flight` and the in-flight work *is* the adoption

The promotion is performed by `promote-idea-to-pattern`. It scaffolds
the Markdown file from the ledger entry's projection, opens the
qualifier at `single-constraint-set`, and writes the back-reference.

### Why ≥1 and not ≥3

A single adoption proves the idea has pieces that are valuable for at
least one set of constraints. It may not be generalizable yet — that's
what the qualifier captures. Waiting for 3 adoptions before recording
the pattern loses the freshness of the first author's reasoning and
risks the second author re-deriving everything from scratch.

This is a deliberate departure from the ≥3-siblings rule that gates
folder packaging (ADR 0006) and cotton-primitive extraction
(`cotton-components.md`). Folder/component promotion is *structural* —
the cost of premature packaging is real navigation friction. Pattern
promotion is *documentary* — the cost of premature recording is one
Markdown file. The asymmetry justifies the lower threshold.

## Frontmatter schema

```yaml
---
id: hydration-fast-path                # matches ledger id
title: Use __NEXT_DATA__/__NUXT_DATA__ as extraction fast path
ledger_entry: hydration-fast-path      # explicit back-reference
status: validated                      # proposed | validated | mandated | deprecated
generalizability: single-constraint-set  # | validated-across-N | broadly-applicable
domain: extraction
problem_class: "SSR-framework site, pre-hydration JSON available, want to skip AI extraction"
pros:
  - "Field coverage in the 60-80% range without an AI call"
  - "Basic-tier scrape is sufficient"
  - "Deterministic; no hallucination risk"
cons:
  - "Only works for SSR frameworks that ship hydration payloads"
  - "Payload shape varies by version; needs per-framework parser"
constraints:
  - "Site must render server-side"
  - "Hydration JSON must be present in HTML response, not lazy-loaded"
composes_with:
  - json-ld-fallback
lineage_parents: []
lineage_children: []
adoption_evidence:
  - app/services/extraction_compiler/hydration_fast_path.py
quality_markers: []
last_research_at: null
---
```

Field semantics:

- **`id`** / **`ledger_entry`** — same slug; `id` is the file's identity,
  `ledger_entry` is the explicit pointer that `audit-pattern-library`
  checks
- **`status`** — see *Status lifecycle* below
- **`generalizability`** — adoption-count qualifier; see *Qualifier
  graduation* below
- **`domain`** — broad topic; aligns with subsystem_kind tags in the
  ledger but may be coarser
- **`problem_class`** — one-line description of when this is the right
  reach; the most-queried field
- **`pros` / `cons`** — short bullets; each pro/con holds under at
  least one constraint set
- **`constraints`** — preconditions that must hold for the pattern to
  apply
- **`composes_with` / `lineage_parents` / `lineage_children`** — pattern
  slugs (not ledger slugs); enables cross-pattern traversal in
  `query-patterns`
- **`adoption_evidence`** — copied forward from the ledger at promotion;
  `audit-pattern-library` keeps it in sync as new adoptions accrue
- **`quality_markers`** — projection of the ledger's markers at
  promotion; may diverge if the pattern outlives the marker (e.g. a
  `has-more-potential` ledger marker cleared at adoption may persist on
  the pattern as a "remaining open question")
- **`last_research_at`** — set by `mature-existing-ideas`; null means
  the pattern has never been research-checked

## Body sections

Every pattern file uses this section structure. Sections may be empty if
the pattern is recently promoted and the author hasn't filled them yet —
the empty section signals the gap.

```markdown
# <Title>

## Problem fit
1-2 paragraphs: what is the problem class, and what conditions make this
the right reach? End with a one-line "Use this when X; reach elsewhere
when Y." The one-liner is the headline that `query-patterns` returns.

## Approach
Concrete shape of the pattern: code skeleton, prompt template, workflow
diagram, harness layout. Show enough that a reader can copy and adapt.

## Pros
- Short bullets. Each is a claim that holds for at least one constraint
  set. No marketing.

## Cons
- Honest about limitations. Each names a condition under which the
  pattern fails or wastes effort.

## Constraints
- Preconditions: what must be true about the project / data / runtime
  for this pattern to apply.

## Composability
- Patterns this one composes with (sideways).
- Patterns this one feeds into (forward).
- Patterns this one evolved from (backward).
- Cross-link by pattern slug; `query-patterns` follows these.

## Evolution history
Newest first. Each entry: date, event, link to ledger event id.

- 2026-05-09 — adopted in `app/services/extraction_compiler/hydration_fast_path.py`
  (ledger event 2026-05-09T15:30:00Z)
- 2026-04-25 — moved to in-flight; prototype started
- 2026-04-18 — captured at proposed state

## Open questions
- Known gaps. Promote to `needs-research` marker on the ledger if
  external answers might exist.

## Research log
Appended by `mature-existing-ideas`. Each entry:

- 2026-MM-DD — what was researched, sources surveyed, conclusion, next
  action (or none). Updates frontmatter `last_research_at`.
```

## Status lifecycle

```
   proposed ──► validated ──► mandated
                    │            │
                    └─► deprecated ◄┘
```

- **proposed** — promoted from ledger, not yet reviewed. Default at
  promotion time. Carries the same content as a validated pattern; the
  difference is review state.
- **validated** — reviewed; the value-for-one-constraint-set claim holds.
  Most patterns sit here.
- **mandated** — repository convention; new work in this domain must
  consider this pattern first. Rare. Usually paired with an ADR that
  codifies the constraint.
- **deprecated** — superseded or no longer recommended. Carries a
  supersession pointer in the body. The file is never deleted; the
  reasoning is the value.

Transitions are manual judgment calls; `audit-pattern-library` reports
candidates (e.g. a `validated` pattern with `broadly-applicable`
qualifier that hasn't been mandated despite repo-wide adoption) but does
not auto-promote.

## Qualifier graduation

`generalizability` is upgraded by `audit-pattern-library` based on
accumulated adoption events in the source ledger entry:

- `single-constraint-set` — 1 adoption (entry condition at promotion)
- `validated-across-N` — 2-3 adoptions across distinct contexts
- `broadly-applicable` — 4+ adoptions across distinct contexts

"Distinct contexts" is a judgment field. Two adoptions of the same
helper in two files inside the same subsystem is not two distinct
contexts; one adoption in extraction and one in UI is. The audit
proposes the upgrade; a human confirms.

A qualifier never downgrades except through `deprecated` status. A
pattern that loses adoptions (e.g. callers refactored away) is
deprecated, not demoted.

## Querying the library

Two consumer surfaces:

1. **`query-patterns` skill** — the explicit lookup. Takes a problem
   description; scores every pattern's `problem_class` + `pros` + body
   keywords; returns ranked matches with the one-line headline from
   *Problem fit*. Use in planning flows: `/plan-feature`,
   `/scope-feature`, `/architecture-fit`.

2. **Inline prompt template** — `.claude/docs/query-patterns-inline.md`.
   A short paste-into-context block for low-friction lookups during
   exploratory work. The template is a sibling of the skill, not a
   replacement: the skill is for the planning chain; the template is
   for ad-hoc reads.

Both surfaces read frontmatter for ranking and body for context.

## How patterns interact with ADRs

ADRs constrain future work (case law); patterns describe reusable shapes
(recipes). The interaction:

| Concept | Tier 1 | Tier 2 | ADR |
|---|---|---|---|
| Bar to entry | "would future-me want this?" | ≥1 adoption | constrains future work / excludes alternative / sets expiration |
| Mutability | append-only | edit in place + deprecated state | append-only (supersession via new ADR) |
| Cardinality target | unbounded | dozens to low hundreds | 2-5 per quarter |
| Read frequency | rare (audit-time, bootstrap) | per planning task | per convention question |

The promotion ladder: ledger entry → pattern (≥1 adoption) → mandated
pattern (repo-wide adoption) → ADR (when the convention excludes
alternatives and constrains future work). Not every pattern becomes
mandated; not every mandated pattern needs an ADR.

ADRs can link back: a pattern slug under the ADR's `related_pattern`
frontmatter field.

## Format evolution (forward note)

The current format is Markdown, chosen for portability and AI-friendly
reading. A future direction tracked in the ledger (entry
`idea-tracking-system` with `has-more-potential` marker) is **HTML with
a small web-component library**: default stylesheet plus components for
tables, comparison matrices, pros/cons grids, composition diagrams. The
trigger for revisiting:

- Multiple AI agent toolchains parsing the same HTML semantics
- A web-component vocabulary that survives across rendering targets
- Demand for richer affordances that Markdown can't express cleanly
  (sortable comparison tables, interactive composition diagrams)

The v1 commitment is **schema stability**: frontmatter and section
structure stay compatible enough that conversion to HTML is mechanical
when the time comes. Don't introduce body conventions that bake in
Markdown-only affordances.

## Anti-patterns for pattern entries

- **The wish list.** A pattern entry without adoption evidence is not a
  pattern. Capture as a ledger intake instead.
- **The tutorial.** Patterns are for readers who already have the
  problem in hand. Save tutorials for `docs/`.
- **The disguised ADR.** If the content constrains future work or
  excludes alternatives, it belongs in `ai-docs/decisions/`. Link from
  the pattern.
- **The orphan claim.** Every pro and con must hold under the named
  constraints. Generic "scales well" claims without constraints are
  noise.

## Cross-references

- Tier 1 schema: `idea-ledger.md`
- Inline query template: `query-patterns-inline.md`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
- ADR threshold and surrounding conventions: `ai-docs/decisions/README.md`
