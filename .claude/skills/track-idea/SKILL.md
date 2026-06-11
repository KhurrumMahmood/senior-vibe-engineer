---
name: track-idea
description: Append an intake, event, or lesson record to the Tier 1 idea ledger at .claude/ideas/log.jsonl. The capture surface for everything that could be reused or forgotten — features, refactors, prompts, harnesses, research probes, workflow tweaks. Validates the record against the schema in .claude/docs/idea-ledger.md before writing, then projects the idea's current state. Read .claude/docs/idea-ledger.md when authoring or debugging this skill.
argument-hint: "intake <slug> | event <slug> --kind <kind> | lesson <slug> | list | show <id>"
allowed-tools: Bash, Read, Edit, Write
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Capturing an idea, transition, marker change, edge addition, adoption,
  development note, or distilled lesson against the project's idea
  ledger. Used at any tier whenever the conversation surfaces something
  reusable: a prompt template that worked, a research probe to remember,
  a harness shape, a UI idea, a workflow tweak, a friction observation
  from building a skill. Also the projection surface — `list` / `show`
  read the current state.
not_for: |
  Decisions that constrain future work (use /decide → ADR).
  Bug fixes with no design content (commit message is enough).
  Work-item tracking (use reports/BACKLOG.md; the ledger is upstream).
  Project status / activity logs (use commit messages).
  Conversation transcripts (link the artifact, don't copy it in).
escalate_to: |
  /decide when the captured thinking has hardened into a binding choice
  that constrains future work or excludes an alternative.
language: any
framework: any
---

# /track-idea

You are the **capture surface** for the project's idea ledger at
`.claude/ideas/log.jsonl`. Every kind of writable record routes through
this skill: new ideas (`intake`), state changes and metadata events
(`event`), and distilled learnings (`lesson`). You also serve the two
basic read paths (`list`, `show`) because they directly inform what to
track next.

You do NOT promote ledger entries to the Tier 2 pattern library — that's
`/promote-idea-to-pattern`. You do NOT detect orphans — that's
`/find-orphaned-ideas`. You do NOT extract historical ideas from the
filesystem — that's `/extract-existing-ideas`.

The ledger schema, projection rules, state machine, and the full table
of skill ↔ ledger interactions live in `.claude/docs/idea-ledger.md`.
**Read that file** before reasoning about a non-trivial capture; this
SKILL.md only documents the orchestration.

## Core beliefs

1. **Capture beats curation.** If the captor's question is "is this
   worth recording?", the answer is almost always yes. The bar is "would
   future-me wish I'd written this down?" — that bar is intentionally
   low. Curation happens in Tier 2.
2. **The conversation is the input.** When the user invokes
   `/track-idea` without explicit flags, fill the required fields from
   the conversation context. The completion-trained failure mode is
   asking the user a second time for things you can already infer.
3. **One record per event.** Don't bundle a transition + adoption + edge
   into one record. Append separate events so the projection rules apply
   uniformly and the audit trail is clean. Append-only is a hard rule:
   never edit prior lines.
4. **Validation runs locally, every time.** The script enforces
   `validate_record` from `ideas_lib.py` before writing. If validation
   fails, fix the input and retry — don't bypass.
5. **Skills are first-class ideas.** When the user builds, tests, or
   iterates on a skill, capture it as `subsystem_kind: skill` and emit
   `dev-note` events for the development history. See *Skill
   meta-tracking* in `idea-ledger.md`.

## Argument parsing

Five forms — pick exactly one. Form A and Form D accept either explicit
flags or implicit conversation-context filling; the helper script always
takes explicit flags.

### Form A — Append intake

```
/track-idea intake <slug>
```

Required (the helper script enforces): `--title`, `--origin`,
`--subsystem-kind`, `--summary`. Optional: `--state` (default
`proposed`), `--quality-markers`, `--feeds-into`, `--composes-with`,
`--lineage-parents`, `--tags`, `--hypothesis`.

When the user invokes `/track-idea intake <slug>` without filling
fields, you fill them from the conversation context, then call the
helper.

### Form B — Append event

```
/track-idea event <slug> --kind <transition|marker|edge|adoption|dev-note|note>
```

Per `event_kind`:

- **transition**: `--to-state <state>` and, if `to_state == done`,
  `--outcome <outcome>`. Optional `--from-state`.
- **marker**: `--markers-added <a,b>` and/or `--markers-removed <a,b>`.
- **edge**: `--edges-added '{"feeds_into": [...], "composes_with": [...],
  "lineage_parents": [...]}'` (JSON dict).
- **adoption**: `--adoption-evidence <path|PR|ref>`.
- **dev-note**: `--summary "..."`. For friction, prefix the summary with
  `friction: ` so future queries can filter.
- **note**: `--summary "..."`.

### Form C — Append lesson

```
/track-idea lesson <slug>
```

Required: `--title`, `--body`. Optional `--generalizes-to <kind,kind>`.
Lessons are independent of state — a rejected idea can carry valuable
lessons.

### Form D — List

```
/track-idea list [--state <state>] [--marker <marker>] [--subsystem <kind>]
```

Print one line per idea: `<id>  <state>  <markers>  <title>`. Filter
by `--state`, `--marker`, or `--subsystem` if narrowing.

### Form E — Show

```
/track-idea show <id>
```

Print the full projection (state, markers, edges, adoption count,
lessons, recent events) for one idea.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** ledger path resolved; conversation
context summarized into the required fields if implicit.

The ledger lives at `${REPO_ROOT}/.claude/ideas/log.jsonl`. Create the
parent directory if it doesn't exist (the helper does this).

If the form is A or C and the user invoked the skill without filling
fields, summarize the conversation context into the required fields
yourself before calling the helper. Don't ask the user a question whose
answer is already in the last few turns.

### Stage 1 — Fill missing fields (Form A and C only)

**Pre:** Form A or C selected, conversation context available. **Post:**
all required flags resolved.

For Form A (intake), produce values for:
- `--title` — one-line, present-tense. Capitalize the first letter.
- `--origin` — one of `convo`, `plan:<path>`, `ADR-NNNN`,
  `AI-suggestion`, `spike:<branch>`, `TODO:<file:line>`. Pick the closest
  match.
- `--subsystem-kind` — free-form tag aligned with the project's
  vocabulary. Common examples across projects: `extraction`, `UI`,
  `agent-loop`, `lint`, `infra`, `prompt-template`, `harness-shape`,
  `skill`. Pick the best match; new tags are allowed but flag them in
  the summary so the project's tag space can evolve consciously.
- `--summary` — 2-5 sentences explaining what this is, why it might
  matter, what success would look like.

Optional but valuable:
- `--hypothesis` — what we expect to be true if the idea works. Add
  when non-trivial; skip if obvious.
- `--quality-markers` — set `underdeveloped` if the formulation is
  rough; `needs-research` if external research would help;
  `has-more-potential` rarely on intake (more common at harvest time).
- `--composes-with` — slug-list of sibling ideas this works with.
- `--tags` — short topical tags for query routing.

For Form C (lesson), produce:
- `--title` — short headline naming the rule.
- `--body` — rule + why + how to apply. 2-5 sentences.
- `--generalizes-to` — subsystem kinds where the lesson might apply
  elsewhere.

### Stage 2 — Append the record

**Pre:** all required flags resolved. **Post:** record written; projection
re-read.

```bash
python3 .claude/skills/track-idea/scripts/track.py <form> <args>
```

The script validates against `ideas_lib.validate_record` and writes
through `ideas_lib.append_record`. On validation failure, the script
exits non-zero with the diagnostic; surface that to the user and stop —
don't paper over.

For Form B (event), the script auto-resolves `--from-state` from the
current projection if not provided (so callers don't have to know the
prior state). It always sets `event_at` to the current UTC time.

### Stage 3 — Project and report

**Pre:** record written. **Post:** user sees the projected state.

```bash
python3 .claude/skills/track-idea/scripts/track.py show <id> --quiet-on-list-fields
```

Surface to the user in ≤8 lines:

- For Form A: confirmation + the slug + a one-line "next:" hint
  (e.g. `next: /track-idea event ${SLUG} --kind transition --to-state
  in-flight when work starts`).
- For Form B: the new state / markers / edges / adoption count plus a
  one-line promotion hint if `adoption_count >= 1`
  (e.g. `eligible for promotion to .claude/patterns/`).
- For Form C: the lesson is appended; if `generalizes_to` is set, note
  which other subsystem kinds may benefit.
- For Form D / E: the read output is the work; no further action.

### Stage 4 — Stop

Do not invoke `/promote-idea-to-pattern`, `/find-orphaned-ideas`, or
any downstream skill. Surface the suggestion in the report; let the
caller decide.

## Non-goals

- Editing prior ledger lines (append-only — the script enforces this).
- Promoting to the pattern library (use `/promote-idea-to-pattern`).
- Detecting stale or orphaned ideas (`/find-orphaned-ideas`).
- Bulk import from filesystem (`/extract-existing-ideas`).
- Cross-project mirroring (the ledger is project-local).
- Asking the user for fields that are already in the conversation
  context. Fill them yourself.

## When things go sideways

| Symptom | Action |
|---|---|
| Slug already has an intake | Form A: abort, suggest Form B (event) or `--show` |
| Slug has no intake yet | Form B / C: abort, suggest Form A (intake) first |
| `validate_record` fails | Surface the diagnostic verbatim; fix the input and retry |
| `--to-state done` without `--outcome` | Abort; ask which outcome (adopted / rejected / deferred / harvested / superseded) |
| Marker name not in `VALID_MARKERS` | Abort; surface the allowed set (`underdeveloped`, `needs-research`, `has-more-potential`) |
| `--edges-added` JSON is malformed | Abort with the JSON parse error; fix and retry |
| Append succeeds but show fails | The write landed; surface the show error but report success on append |

## Repository layout

```
.claude/skills/track-idea/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    └── track.py              # the writer (uses _common/ideas_lib.py)
```

The orchestrator (you) does not read the script source. The script
contract is the argument parser plus exit codes. Schema invariants live
in `_common/ideas_lib.py`; any change there reaches every idea skill.

## Cross-references

- Schema, projection rules, state machine: `.claude/docs/idea-ledger.md`
- Pattern library (Tier 2): `.claude/docs/pattern-library.md`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
- Shared library: `.claude/skills/_common/ideas_lib.py`
- Detection skill: `/find-orphaned-ideas`
- Query skill: `/query-patterns`
