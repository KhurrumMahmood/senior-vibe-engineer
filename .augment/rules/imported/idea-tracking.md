---
type: "always_apply"
---

# Idea tracking

When an idea worth remembering surfaces — feature, refactor, prompt
shape, harness pattern, research probe, rejected approach with a
lesson — use the idea-tracking system instead of an ad-hoc note. The
bar for entry is *"would future-me want this back?"*; capture
liberally, prune via `/find-orphaned-ideas`.

Before ending a strategy/design conversation that produced
agreed-but-unexecuted items, silent decisions, or reusable ideas, sweep
the conversation and capture them as ledger intakes via `/track-idea` —
capture beats curation.

The system is two-tier (ADR 0013):

- **Tier 1 — Idea ledger** at `.claude/ideas/log.jsonl`. Append-only
  JSONL. One intake per idea; events for transitions, markers, edges,
  adoption notes.
- **Tier 2 — Pattern library** at `.claude/patterns/<slug>.md`. One
  Markdown file per pattern, promoted at `adoption_count >= 1`.

## Skills

- `/track-idea` — canonical write surface for Tier 1
- `/find-orphaned-ideas` — multi-mode detector (file-orphan, stall,
  plan-dropout, harvest-opportunity, dormant-with-potential)
- `/query-patterns` — Tier 2 lookup for planning flows
- `/brainstorm-ideas` — exploration / bulk capture (single writer)
- `/mature-existing-ideas` — periodic research pass
- `/extract-existing-ideas` — bootstrap from `BACKLOG.md` / `lessons.md`

For ad-hoc pattern lookups mid-conversation, use the inline template
at `.claude/docs/query-patterns-inline.md` rather than spinning up the
full `/query-patterns` skill.

## What does not go in the ledger

- Bug fixes with no design content (commit messages)
- One-off implementation details (`.claude/tasks/lessons.md`)
- Conversation transcripts (cross-link instead of copying)
- Secrets, credentials, API keys (the ledger is checked in)

## Cross-references

- Schema: `.claude/docs/idea-ledger.md` (Tier 1),
  `.claude/docs/pattern-library.md` (Tier 2)
- Workflow: `.claude/docs/skill-catalog.md` IDEAS section
- ADR: `ai-docs/decisions/0013-idea-tracking-system.md`
- Validation harness: `.venv/bin/python .claude/tests/ideas/run_harness.py`
  (run before changes to `.claude/skills/_common/ideas_lib.py` or any
  IDEAS skill)
