---
name: brainstorm-ideas
description: Generate a batch of candidate ledger intakes for a topic or context file, deduplicate against the existing ledger, and bulk-write the survivors as proposed-state intakes with origin AI-suggestion. The orchestrator does the creative work (reading the topic, current ledger state, project docs, and producing N candidates with title / summary / hypothesis / subsystem_kind / markers); the helper script validates against duplicates and writes. Read .claude/docs/idea-ledger.md when authoring or debugging this skill.
argument-hint: "<topic> [--context <path>] [--n <max>] [--subsystem-kind <kind>]"
allowed-tools: Bash, Read, Write, Edit, WebSearch, WebFetch
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Generating a batch of candidate ideas at the start of an exploratory
  session, around a vague topic, or after reading a plan/spec that
  surfaces several adjacent thoughts worth capturing. Useful when the
  alternative is to lose 5 of 7 surfaced thoughts because only 2 made
  it into the next /track-idea intake.
not_for: |
  Capturing a single idea (use /track-idea intake — one record).
  Maturing an existing idea (use /mature-existing-ideas).
  Promoting to the pattern library (use /promote-idea-to-pattern).
  Brainstorming code structure / architecture forks (use /design-it-twice).
  Sourcing decision alternatives (use /decide — alternatives are part of
  the ADR template).
escalate_to: |
  /mature-existing-ideas when one of the brainstormed candidates clearly
  benefits from external research before further work.
  /design-it-twice when a brainstormed idea has 2+ defensible
  implementation forks worth comparing.
language: any
framework: any
---

# /brainstorm-ideas

You are the **bulk capture** surface — the orchestrator that turns a
topic plus optional context into a batch of N candidate intakes,
deduplicates them against the existing ledger, and writes the survivors.

You do NOT mature existing ideas — that's `/mature-existing-ideas`. You
do NOT promote to Tier 2 — that's `/promote-idea-to-pattern`. You do
NOT design alternatives for a binding choice — that's `/decide` and
`/design-it-twice`.

The ledger schema, projection rules, and the full table of skill ↔
ledger interactions live in `.claude/docs/idea-ledger.md`. **Read that
file** before reasoning about a non-trivial batch.

## Core beliefs

1. **Capture is the bottleneck.** Brainstorm sessions surface
   five-to-ten ideas; without bulk capture, the strongest two get
   written down and the rest evaporate. The whole point of this skill
   is to keep that asymmetry from happening.
2. **Slug-level dedup is mandatory.** Re-creating an existing intake
   is the most common write-time error. The helper checks every
   candidate slug against existing intakes and skips matches; you
   surface the skips so the user can decide whether to event them
   instead.
3. **Origin: AI-suggestion (or convo+research).** Brainstormed intakes
   are explicitly machine-generated; future readers should be able to
   distinguish them from human-captured intakes when reviewing the
   ledger. The origin field carries that signal.
4. **Quality markers default to `underdeveloped`.** A brainstormed
   intake by definition needs more thinking. Auto-clear later when
   someone develops the idea.
5. **The conversation seeds the brainstorm; the user steers it.** Read
   the topic, the optional context file, and the ledger's existing
   subsystem_kind vocabulary; produce candidates; surface them BEFORE
   writing so the user can prune. After approval, the helper writes the
   batch in one call.

## Argument parsing

```
/brainstorm-ideas "<topic>" [--context <path>] [--n <max>]
                            [--subsystem-kind <kind>]
                            [--external-research]
```

- `<topic>` — free-text seed. Required.
- `--context <path>` — file to read for additional context (a plan
  file, spec, doc, memory file, conversation transcript). Optional.
- `--n <max>` — soft cap on candidates. Default 7. Hard floor at 1.
- `--subsystem-kind <kind>` — bias all candidates to one kind. Useful
  when brainstorming around extraction, UI, or skill-meta.
- `--external-research` — allow Web/Context7 lookups during candidate
  generation. Off by default (cost + speed); flip on for unfamiliar
  domains.

## Pipeline

### Stage 0 — Setup

**Pre:** topic received. **Post:** ledger loaded, vocabulary seeded.

```bash
python3 .claude/skills/track-idea/scripts/track.py list 2>/dev/null
```

Read the existing ledger projection. Note:
- Existing slugs (to dedupe later)
- Subsystem_kind vocabulary in use (don't invent a new kind unless the
  topic genuinely doesn't fit one of the existing tags)
- Subsystem_kind frequencies (the dominant kinds suggest the project's
  current focus)

If `--context <path>` is set, read the file. Capture the titles,
bullets, headings, and any "open questions" or "future work" sections
as seed material.

### Stage 1 — Generate candidates

**Pre:** topic, context, ledger vocabulary in hand. **Post:**
N candidate dicts.

Each candidate is a dict shape:

```json
{
  "slug": "small-kebab-case-slug",
  "title": "One-line title",
  "subsystem_kind": "<kind from vocabulary>",
  "summary": "2-5 sentence problem-fit description.",
  "hypothesis": "What we expect to be true if the idea works.",
  "quality_markers": ["underdeveloped"],
  "tags": ["topic", "area"],
  "composes_with": []
}
```

Heuristics:

- **Diversity.** Don't generate 5 variations of the same idea; spread
  across angles (mechanism / scope / target site / cost / risk).
- **Adjacent, not redundant.** If the existing ledger already has
  `hydration-fast-path`, don't propose another `hydration-detection-tier`
  unless the angle is genuinely different.
- **Real, not aspirational.** Each candidate should be plausibly
  trackable — concrete enough that future-me reads the summary and
  knows what experiment or change to run.
- **Origin honesty.** If you used external research (`--external-research`)
  to enrich a candidate, note the source in the summary and set
  `origin: convo+research`; otherwise `origin: AI-suggestion`.

### Stage 2 — Present and prune

**Pre:** candidates generated. **Post:** approved batch resolved.

Present the candidates in a compact list with one-line summaries:

```
Brainstorm batch (topic: <verbatim>):

1. `<slug-1>` — <title-1>  [<kind>] [<markers>]
   <one-line summary>
2. ...

Existing ledger entries that overlap (will be skipped):
- `<slug>` matches existing intake "<title>" — consider /track-idea event
  on the existing instead.
```

Ask the user which to keep / drop / rewrite. Apply edits to the batch.
Per the project's "no confirmation gates" rule, treat the user's
implicit approval (e.g. "go", "looks good", silence + continued
conversation) as authorization to write. If the user pushes back on
any candidate, drop it.

### Stage 3 — Bulk write

**Pre:** approved batch in hand. **Post:** N intake records appended.

Write a temporary JSON file with the batch:

```bash
TMPFILE=$(mktemp -t brainstorm-XXXXXX.json)
cat > "${TMPFILE}" <<'EOF'
[
  {"slug": "...", "title": "...", "subsystem_kind": "...",
   "summary": "...", "hypothesis": "...", "origin": "AI-suggestion",
   "quality_markers": ["underdeveloped"], "tags": ["..."],
   "composes_with": []},
  ...
]
EOF
python3 .claude/skills/brainstorm-ideas/scripts/brainstorm.py "${TMPFILE}"
rm -f "${TMPFILE}"
```

The helper:
- Loads the JSON batch
- Loads the existing ledger
- Skips any candidate whose slug already has an intake (reports the
  skip to stderr)
- Validates each survivor via `ideas_lib.validate_record`
- Writes the survivors via `ideas_lib.append_record`
- Exits 0 on success (even with skips); exits 1 on validation failure

### Stage 4 — Report

**Pre:** writes complete. **Post:** user sees what landed.

```
Wrote N intakes:
- <slug-1> (state=proposed, markers=[underdeveloped])
- ...

Skipped M existing slugs (use /track-idea event to update them):
- <slug>
- ...

Suggested next:
- /find-orphaned-ideas after a week to catch any that go stale
- /mature-existing-ideas <slug> for any flagged needs-research
```

### Stage 5 — Stop

Do not auto-promote any new intake. Do not auto-research. Surface the
suggestions in the report; let the caller drive.

## Non-goals

- Editing prior ledger lines (the ledger is append-only).
- Maturing brainstormed ideas (`/mature-existing-ideas`).
- Promoting to the pattern library.
- Writing ADRs from brainstormed ideas (`/decide` is the right move
  when a candidate hardens into a binding choice).
- Brainstorming code structure / architecture forks
  (`/design-it-twice` does that with 3-way fan-out).

## When things go sideways

| Symptom | Action |
|---|---|
| Existing intake collides with every candidate | Stop; recommend `/track-idea event` against the existing instead |
| `validate_record` fails on a candidate | Surface the diagnostic; let the user edit or drop |
| `--external-research` requested but no internet | Skip the research enrichment; proceed with the conversation-only brainstorm; flag the limitation in the report |
| User asks "what are the best N ideas?" expecting a ranking | This skill doesn't rank — surface the candidates flat. Ranking is a separate concern handled by /query-patterns once entries are promoted |
| Batch contains 0 survivors after dedup | Report it explicitly; the existing ledger already covers the topic |

## Repository layout

```
.claude/skills/brainstorm-ideas/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    └── brainstorm.py         # bulk intake writer
```

## Cross-references

- Schema: `.claude/docs/idea-ledger.md`
- Sibling skills: `/track-idea`, `/find-orphaned-ideas`, `/mature-existing-ideas`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
