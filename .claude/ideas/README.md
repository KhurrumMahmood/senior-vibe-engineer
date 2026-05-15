# `.claude/ideas/` — Tier 1 idea ledger

Append-only capture for every idea worth remembering: features,
refactors, prompts, harness shapes, research probes, workflow
patterns. Tier 2 (curated patterns) lives in `.claude/patterns/`.

## Files

- `log.jsonl` — the ledger. One JSON object per line, sorted by
  `created_at` on append. Never edit a prior line; emit new event
  records that reference the original by `id`.

The ledger may not yet exist on disk if no entries have landed —
`track-idea` creates it on first write.

## How to use

- Capture: `track-idea` (canonical entry point) or `brainstorm-ideas`
  (bulk, for exploration)
- Update: `track-idea` (transitions, marker changes, edge additions,
  adoption notes)
- Bootstrap from an existing project: `extract-existing-ideas` (one-shot;
  emits candidate intakes for review)
- Detect orphans: `find-orphaned-ideas` (file-orphan, stall,
  plan-dropout, harvest-opportunity, dormant-with-potential modes)
- Audit integrity: `audit-ideas` (lineage back-pointers, supersession
  resolution, stale-flag transitions)

## Schema

Full specification in `.claude/docs/idea-ledger.md`. ADR motivating the
system: `ai-docs/decisions/0013-idea-tracking-system.md`.

## Direct reads (no skills available)

Each line is a JSON object with `record_kind in {intake, event,
lesson}`. To project an idea's current state, filter by `id` and apply
events in `event_at` order. The projection rules are in the schema
doc.

## What does not go here

- Bug fixes with no design content (commit messages)
- One-off implementation details (`.claude/tasks/lessons.md`)
- Conversation transcripts (cross-link instead of copying)
- Secrets, credentials, API keys (the ledger is checked in)
