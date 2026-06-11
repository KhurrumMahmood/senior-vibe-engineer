# `.claude/patterns/` — Tier 2 pattern library

Curated reusable patterns promoted from Tier 1 ideas
(`.claude/ideas/log.jsonl`) at ≥1 adoption. One Markdown file per
pattern. Filename matches the source ledger slug.

## How to use

- Query: `query-patterns` (skill for planning flows) or the inline
  prompt template in `.claude/docs/query-patterns-inline.md`
- Promote a ledger entry: `promote-idea-to-pattern` (gated by ≥1
  adoption with documented evidence)
- Periodic research pass: `mature-existing-ideas` updates research
  logs and `last_research_at` on each entry

## Schema

Full specification in `.claude/docs/pattern-library.md`. Frontmatter
fields (id, status, generalizability, problem_class, pros, cons,
constraints, composes_with, lineage_parents, lineage_children,
adoption_evidence) drive ranking and traversal.

## Status lifecycle

- `proposed` — promoted, not yet reviewed
- `validated` — reviewed; value-for-one-constraint-set claim holds
- `mandated` — repo convention; new work must consider this first
- `deprecated` — superseded or no longer recommended

## Generalizability qualifier

- `single-constraint-set` — 1 adoption (entry condition)
- `validated-across-N` — 2-3 adoptions across distinct contexts
- `broadly-applicable` — 4+ adoptions across distinct contexts

Graduation is proposed by `audit-pattern-library`; humans confirm.

## What does not go here

- Patterns without `adoption_evidence` (capture as Tier 1 intake instead)
- Tutorials (save for `docs/`)
- Constraints that exclude alternatives (those motivate ADRs;
  cross-link)
