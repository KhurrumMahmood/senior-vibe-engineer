# Inline pattern-library lookup template

A paste-into-context companion to the `/query-patterns` skill, for
low-friction lookups during exploratory work when a full skill
invocation is overkill.

> Read this when: working through an open-ended problem and want to
> check prior art in `.claude/patterns/` without spawning a sub-agent or
> running a skill; reviewing whether the inline template should evolve.

## When to use which

| Surface | Cost | Best for |
|---|---|---|
| `/query-patterns` skill | one process invocation, one effectiveness-log entry | planning chains (`/plan-feature`, `/scope-feature`), audit cadence |
| Inline template (this file) | zero process invocations | exploratory work, ad-hoc reads, "is there prior art for X?" mid-conversation |
| Direct file open (`.claude/patterns/<slug>.md`) | one Read | you already know the slug |

Both surfaces read the same files. They produce the same answer for the
same query, modulo prompt sensitivity vs token-overlap matching.

## How the inline template works

The block below is a prompt template. Pasting it into a chat (or
including it in a sub-agent prompt) gives the agent enough to do a
lookup without running the skill:

1. The agent lists the contents of `.claude/patterns/` via `Glob`.
2. For each `.md` file, the agent reads the frontmatter
   (`problem_class`, `pros`, `cons`, `composes_with`, `status`,
   `generalizability`) and the first paragraph of `## Problem fit`.
3. The agent ranks by relevance to the problem description, mentally
   weighting `problem_class` and the "Use this when X" headline the
   highest.
4. The agent returns the top 1-3 matches with one-line rationale each,
   or "no clear match — consider `/track-idea intake`" if nothing fits.

Token-overlap matching is the formal version of this; LLM judgment
typically does better because it understands synonyms and intent. The
trade-off is that the inline lookup is not logged in the effectiveness
log, so it can't be audited later — use the skill when audit history
matters.

## The template

Paste this block into the conversation when you want an inline lookup:

```
Inline pattern-library lookup.

Problem: <PROBLEM DESCRIPTION>

Steps:
1. Glob `.claude/patterns/*.md`.
2. For each file, read the frontmatter (problem_class, pros, cons,
   composes_with, status, generalizability, domain, tags) and the
   "Use this when X" line from the Problem fit section.
3. Rank by relevance to the problem. Exclude `status: deprecated`
   unless the user asks for them.
4. Return the top 1-3 matches in this shape:

   - `<slug>` — <title>
     Use this when: <headline>
     Composes with: <composes_with or "(none)">
     Why this fits: <one-line rationale>

5. If no pattern matches, say so explicitly and recommend
   `/track-idea intake` to capture the problem.

Do NOT modify any pattern file. Do NOT add a new pattern. The output is
the recommendation; the caller decides whether to adopt or capture.
```

## Composability with the skill

The inline lookup and the skill are not redundant — they target
different friction profiles. A planning chain that wants reproducible,
auditable lookups uses the skill. A conversational read that just wants
to confirm prior art uses the inline template.

When the inline template returns "no clear match," the natural escalation
is `/track-idea intake` (capture) followed by, if a similar problem
keeps recurring, `/query-patterns` (formal lookup to confirm the
absence) and `/promote-idea-to-pattern` (once the new idea reaches
`adoption_count >= 1`).

## Format evolution

The template's output shape mirrors the skill's rendered top-N section.
Keep them aligned: when the skill changes its render shape (e.g. adds a
new highlighted field), update this template at the same time.

If the inline template proves to produce systematically different
rankings than the skill, that's signal — surface a ledger entry with
`subsystem_kind: prompt-template` and the marker `needs-research` to
investigate the divergence.

## Cross-references

- Skill: `.claude/skills/query-patterns/SKILL.md`
- Pattern format: `.claude/docs/pattern-library.md`
- Tier 1 schema: `.claude/docs/idea-ledger.md`
- ADR motivating this system:
  `ai-docs/decisions/0013-idea-tracking-system.md`
