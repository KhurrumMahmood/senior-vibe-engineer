---
name: query-patterns
description: Search the Tier 2 pattern library at .claude/patterns/ for prior art that matches a problem description. Reads every pattern file's frontmatter (problem_class, pros, cons, domain, status, generalizability) plus the body's "Problem fit" / "Use this when X" headline, scores by token overlap, and returns ranked matches. Read-only. Read .claude/docs/pattern-library.md when authoring or debugging this skill.
argument-hint: "<problem description> [--top N] [--json]"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  An agent or human is about to start work on a problem and wants to
  check whether the project already has a recommended shape for it.
  Used at planning time (`/plan-feature`, `/scope-feature`,
  `/architecture-fit`) and during exploratory work. Cheap, fast, no
  side effects.
not_for: |
  Capturing a new idea (use /track-idea intake).
  Recording a decision (use /decide).
  Finding orphaned ledger entries (use /find-orphaned-ideas).
  Detailed pattern authoring or editing (open the .md file directly).
  General code search (use grep / Glob / map-subsystem).
escalate_to: |
  /track-idea intake when the query returns no matches and the problem
  is worth capturing as a new ledger entry.
delegate_from: |
  /plan-feature and /scope-feature may invoke /query-patterns as a
  sub-stage to check whether a touched workflow has prior-art patterns.
language: any
framework: any
---

# /query-patterns

You are the **lookup surface** for the project's Tier 2 pattern library
at `.claude/patterns/`. You read every pattern file's frontmatter and
body, score against a free-text problem description, and return the
top-N ranked matches.

You do NOT modify the pattern library — promotion is
`/promote-idea-to-pattern`, deprecation is a manual edit, research is
`/mature-existing-ideas`. You do NOT search the Tier 1 ledger —
unpromoted ideas don't have validated value yet, and surfacing them by
default would dilute the signal.

The pattern format, promotion gate, qualifier graduation rules, and
status lifecycle live in `.claude/docs/pattern-library.md`. **Read that
file** before reasoning about a query that the matcher handles
ambiguously.

A lower-friction companion to this skill is the inline prompt template
at `.claude/docs/query-patterns-inline.md` — paste-into-context for
ad-hoc reads when a full skill invocation is overkill.

## Core beliefs

1. **Read frontmatter first, body second.** The most-queried field is
   `problem_class`; the next is `pros` + `cons` + the "Use this when X"
   one-liner from the Problem fit section. Don't expand to the whole
   body unless the frontmatter doesn't match — patterns are designed so
   the frontmatter is the headline.
2. **"No match" is a valid output.** If the library has nothing that
   fits, say so. Don't fabricate a fit. The matcher's exit-1 path is the
   correct answer when the problem is genuinely new to the project.
3. **Surface composability.** When a pattern matches, also surface its
   `composes_with` / `lineage_parents` / `lineage_children` frontmatter
   so the reader can follow the graph one hop without re-querying.
4. **Status filters defaults.** By default, exclude `deprecated`
   patterns from the ranked list. Surface them only when explicitly
   requested via `--include-deprecated`.

## Argument parsing

Single positional argument: a free-text problem description. Flags
modify presentation.

```
/query-patterns <problem description> [--top N] [--json] [--include-deprecated]
```

Examples:

```
/query-patterns extract structured product data from a Next.js site
/query-patterns reduce LLM cost on a per-site discovery loop
/query-patterns deduplicate three-way clone clusters detected by jscpd
```

If the argument is empty, abort with usage guidance.

## Pipeline

### Stage 0 — Setup

**Pre:** problem description received. **Post:** patterns directory
located.

The patterns live at `${REPO_ROOT}/.claude/patterns/*.md`. If the
directory is empty (Tier 2 not yet populated), exit 0 with a message
recommending `/track-idea` for capture and `/promote-idea-to-pattern`
once an idea reaches `adoption_count >= 1`.

### Stage 1 — Run the matcher

**Pre:** problem description and patterns directory in hand. **Post:**
matcher output captured.

```bash
python3 .claude/skills/query-patterns/scripts/query.py "${PROBLEM}" \
  [--top N] [--json] [--include-deprecated] [--project-root DIR]
```

The pattern library is read from `<project-root>/.claude/patterns/`;
`--project-root` defaults to the git toplevel of the cwd (else the cwd).

The matcher returns:

- `query` — verbatim problem text
- `total_patterns` — count of pattern files scanned
- `matches[]` — ranked list with score, slug, title, headline (Use this
  when X), status, generalizability, problem_class, composes_with,
  lineage_parents, lineage_children

Exit code 0 = at least one match scored above the relevance threshold.
Exit code 1 = no match; the script still prints an informative message.
Exit code 2 = usage error.

### Stage 2 — Render the recommendation

**Pre:** matcher output in hand. **Post:** user sees the ranking.

Default Markdown render shape:

```
Query: <verbatim problem>
Library size: N patterns (deprecated excluded)

## Top matches

### 1. `<slug>` — <title> [status / generalizability]
**Use this when**: <one-line headline from Problem fit>
**Problem class**: <frontmatter problem_class>
**Composes with**: <slug>, <slug>  (or "(none)")
**Lineage**: ← parents: <slug>, → children: <slug>  (omit if both empty)
Score: <N>

### 2. ...
```

When `--json` is passed, print the matcher payload verbatim.

When `total_patterns == 0`:

```
Library size: 0 patterns.

No patterns recorded yet. Capture the problem with /track-idea intake
and promote with /promote-idea-to-pattern when it reaches adoption_count
>= 1.
```

When matches is empty:

```
Query: <verbatim>
Library size: N patterns
Top match score: 0 (below threshold)

No patterns in the library match this problem closely. Either:
- The problem is genuinely new — capture with /track-idea intake.
- The match heuristic missed it — re-query with different wording.
```

### Stage 3 — Effectiveness log

**Pre:** ranking delivered. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
python3 scripts/log_effectiveness.py \
  --skill query-patterns \
  --scan-id "query-$(date +%s)" \
  --target "${PROBLEM_SLUG}" \
  --findings-total ${N_MATCHES} \
  --buckets "{\"matched\": ${N_MATCHES}, \"no_match\": ${ZERO_OR_ONE}}"
```

The log enables a future audit: "how often does /query-patterns return
no matches?" — high frequency signals an under-populated library, not a
broken matcher.

### Stage 4 — Stop

Do not invoke a downstream skill. The ranking is the work. The user
decides whether to adopt a pattern, capture a new idea, or proceed
unaided.

## Non-goals

- Writing to the pattern library (that's `/promote-idea-to-pattern`).
- Editing pattern files (open them directly for content edits).
- Searching the Tier 1 ledger (use `/track-idea list` instead).
- Recommending external libraries / docs (this is project-local prior
  art only — `context7` MCP server is the right tool for library docs).
- Composing a new pattern from multiple matches — surface the matches;
  the user composes.

## When things go sideways

| Symptom | Action |
|---|---|
| Empty problem description | Abort with usage example |
| `.claude/patterns/` doesn't exist | Exit 0 with capture guidance |
| Pattern file has malformed YAML | Surface the file path and parse error; skip the file; continue with the others |
| All scores 0 | Render the "no match" template; suggest re-wording |
| Same pattern slug appears twice (file system case-collision) | Surface both; do not silently dedupe |
| `--include-deprecated` flips a deprecated pattern to top rank | Render it; mark `[deprecated]` in the status field clearly |

## Repository layout

```
.claude/skills/query-patterns/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    └── query.py              # the matcher (uses scripts/_lib/yaml_frontmatter)
```

The matcher uses the shared YAML frontmatter parser at
`scripts/_lib/yaml_frontmatter.py` — same one `decisions.py`,
`plans.py`, `skill_meta.py`, `specs.py`, and `which-skill/match.py`
depend on.

## Future evolution

The matcher is a token-overlap heuristic, identical in spirit to
`/which-skill`. When the library grows past ~50 patterns and patterns
of mis-ranking emerge, it will likely evolve toward LLM-assisted
matching — the frontmatter is written as natural-language sentences
specifically so a language-model matcher can read them.

Until then, the heuristic version is more debuggable, faster, and
free.

## Cross-references

- Schema, promotion gate, status lifecycle:
  `.claude/docs/pattern-library.md`
- Tier 1 ledger schema: `.claude/docs/idea-ledger.md`
- Inline lower-friction lookup: `.claude/docs/query-patterns-inline.md`
- ADR motivating this system:
  `ai-docs/decisions/0013-idea-tracking-system.md`
- Companion skills: `/track-idea`, `/find-orphaned-ideas`
