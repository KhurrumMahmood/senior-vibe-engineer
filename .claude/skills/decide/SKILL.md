---
name: decide
description: Author or amend an Architectural Decision Record under ai-docs/decisions/. Smallest first-class artifact in the senior-engineer skill ecosystem; used at any tier (Quick / Feature / System / Maintenance) when a real choice is being made. Reads canonical-patterns.md and architectural-smells.md to suggest related-pattern / related-smell backrefs and avoid duplicating an existing decision. Read-only against the rest of the codebase — only writes under ai-docs/decisions/. Hands off to /plan-feature, /scope-feature, or implementation work.
argument-hint: "<slug> | --amend <id> | --supersede <id> --slug <new-slug> | --list"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: cross-cutting
job: decide
best_for: |
  A choice is being made that (a) constrains future work, (b) excludes
  an alternative explicitly, or (c) sets an expiration. Used at any
  tier whenever a meaningful design fork happens — at planning time,
  during a refactor, or when a maintenance pass surfaces a convention.
not_for: |
  Lessons learned (use .claude/tasks/lessons.md — informal diary).
  Project status / activity logs (use commit messages / PR descriptions).
  Pure documentation of how the code currently works (use the relevant
  docs/<area>.md). Trivial preferences with no future-binding effect.
escalate_to: |
  /plan-feature when the decision motivates a multi-file feature spec.
  /scope-feature when the decision motivates a new subsystem.
delegate_from: |
  /plan-feature Stage 3 (decision stubs) calls /decide for each
  material fork it encounters. /architecture-fit emits decision
  proposals that route through /decide.
language: any
framework: any
---

# /decide

You are the **author** of a single Architectural Decision Record (ADR)
under `ai-docs/decisions/`. The decision registry is the substrate that
makes prior reasoning recallable — every meaningful choice that
constrains future work, excludes an alternative explicitly, or sets an
expiration gets recorded so future engineers and AI agents can trace it.

You do NOT edit production code in this skill. The only artifact you
write is the new or amended ADR file. Backref suggestions to
`canonical-patterns.md` / `architectural-smells.md` are recommended in
your summary, not executed by you (an explicit edit task lands those
backrefs after human review).

## How success is judged

- The new/amended ADR passes Stage 3 verification:
  `scripts/decisions.py audit` and `link-check` come back clean.
- Stage 1 confirmed no existing decision already covers the topic —
  a duplicate aborts into `--amend` or supersession, never a second
  ADR for the same choice.
- `related_smell` / `related_pattern` backrefs are set where one
  applies, and the summary recommends the matching `Decided in: NNNN`
  lines — recommended, not self-executed.
- Nothing outside `ai-docs/decisions/` was written.
Write toward these gates from Stage 0.

## Core beliefs

1. **The threshold for a decision is real.** Any choice that (a)
   constrains a future skill or refactor, (b) excludes an alternative
   explicitly, or (c) sets an expiration date is a candidate. Surprises,
   debugging notes, and project status are NOT decisions — those go in
   `.claude/tasks/lessons.md`, commit messages, or task lists.
2. **One ADR per choice.** If the work spans two coupled choices, write
   two ADRs. A single ADR documenting two independent forks is hard to
   supersede, hard to link, and turns into a graveyard entry.
3. **Backrefs make the registry navigable.** Every ADR should set
   `related_smell` and/or `related_pattern` frontmatter when one applies,
   AND your summary recommends adding `Decided in: NNNN` backrefs to the
   matching `canonical-patterns.md` / `architectural-smells.md` entries.
   Without backrefs the registry is write-only.
4. **Supersession over deletion.** A superseded decision stays in the
   registry with `status: superseded` and `superseded_by: NNNN`. Never
   delete an ADR — the chain is the audit trail.
5. **Target cadence: 2-5/quarter.** More than that across a single
   project signals over-recording — the ledger turns into a junk drawer.
   If you find yourself drafting the third ADR in a week, pause and ask
   whether the latter ones are really decisions or just preferences.
6. **Retro-authored ADRs are valid.** A long-standing convention that
   constrains future work deserves an ADR even if it predates the
   registry. Mark it as such in the body (`> Retro-authored ADR.`).

## Argument parsing

Four forms — pick exactly one.

### Form A — New ADR (default)

```
/decide <slug>
```

`<slug>` is a short kebab-case topic identifier (e.g.
`textchoices-for-state`, `spec-first-refactor`,
`celery-safe-dispatch`). The orchestrator picks the next available
4-digit `id` (the lowest unused integer, zero-padded), stems the title
from the slug, and scaffolds a `proposed`-status ADR.

### Form B — Supersede an existing ADR

```
/decide --supersede <existing-id> --slug <new-slug>
```

Writes a new ADR (next id, status `proposed`) with
`supersedes: [<existing-id>]`. Also stages an edit to the superseded
ADR's frontmatter (`status: superseded`, `superseded_by: <new-id>`)
but does NOT commit it — the new ADR must be human-approved first.

### Form C — Amend an existing ADR

```
/decide --amend <id>
```

Edit one of: `status`, `superseded_by`, `applies_to`, `tags`,
`related_smell`, `related_pattern`. Body edits are out of scope (open
the file directly for those — amending an ADR's *decision* is itself a
decision, so it should usually be a supersession instead).

### Form D — List

```
/decide --list
```

Shorthand for `python3 scripts/decisions.py list`. No new file written.

Present the parsed spec back to the user (intent + target id +
`related_smell`/`related_pattern` candidates surfaced from
`canonical-patterns.md` / `architectural-smells.md`) and wait for
approval before writing in Forms A and B. Form C / D execute
immediately.

The approval-token contract matches `/extract-enum` and `/fix-workflow`:
first non-whitespace token must be `approved`, `approve`, `go`, `lgtm`,
`proceed`, or `yes`.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** next-id resolved (Forms A, B);
target file path resolved (Form C); `${REPO_ROOT}/ai-docs/decisions/`
exists.

```bash
# Find next id (Forms A, B)
NEXT_ID=$(python3 -c "
import pathlib, re
ids = []
for p in pathlib.Path('ai-docs/decisions').glob('[0-9][0-9][0-9][0-9]-*.md'):
    m = re.match(r'(\d{4})-', p.name)
    if m: ids.append(int(m.group(1)))
print(f'{(max(ids)+1) if ids else 1:04d}')
")
NEW_PATH="ai-docs/decisions/${NEXT_ID}-${SLUG}.md"
```

If the slug already exists at any id, abort and recommend `--amend`
on the existing ADR.

### Stage 1 — Context gathering

**Pre:** target id known. **Post:** related-pattern and related-smell
candidates identified.

Read these files (small, fast, scoped to the topic):

- `ai-docs/decisions/README.md` — registry conventions
- `.claude/docs/canonical-patterns.md` — search for pattern names that
  match the decision topic (case-insensitive grep on slug words)
- `.claude/docs/architectural-smells.md` — same search for smell names
- `python3 scripts/decisions.py list --json` — full registry (so you
  don't accidentally re-decide an already-decided question)

For Form B (supersede), also read the superseded ADR's body so the
new ADR can name what changed. Quote the superseded decision's
*Decision* sentence directly, then explain the divergence.

### Stage 2 — Draft the ADR

**Pre:** context gathered. **Post:** `${NEW_PATH}` written (Forms A,
B) or `--amend`'d field updated (Form C).

ADR shape — every section is required, even if the content is "(none)":

```markdown
---
id: <NNNN>
title: <Capitalized title sentence — verb-led if possible>
status: proposed              # proposed | accepted | superseded | deprecated
date: <YYYY-MM-DD today>
deciders: [<user>]            # ask if uncertain — typically the repo owner
supersedes: []                # populated only in Form B
superseded_by: null
applies_to: [<dir or file glob>]
tags: [<topic>, <area>]
related_smell: <smell-anchor or null>      # from architectural-smells.md
related_pattern: <pattern-anchor or null>  # from canonical-patterns.md
---

# <title>

<Optional retro-authored disclaimer>

## Context

<2-4 paragraphs explaining the prior state, the recurring problem, and
the trigger for this decision. Be specific — cite real files, real
incidents, real failure modes. Vague context = un-supersedable later.>

## Decision

<One short paragraph stating the rule, then bullet points if there are
multiple sub-rules. The Decision section is the single load-bearing
sentence; everything else exists to support it.>

## Alternatives considered

- **<Alt 1 name>.** <One-line statement>. Rejected: <reason>.
- **<Alt 2 name>.** <One-line statement>. Rejected: <reason>.
- (At least two alternatives; "no decision" usually counts as one.)

## Consequences

**Easier:**
- <durable improvement>

**Harder:**
- <trade-off the decision accepts>

**Now expected / now disallowed:**
- <new constraint that lints, reviewers, or future agents will enforce>

## Verification

- **Tooling**: <lint rule / test / audit command, with file path>
- **Doc backref**: <which canonical-patterns.md / architectural-smells.md
  entry will carry `Decided in: <NNNN>`>
- **Existing artifacts**: <pointer to specs / commits / PRs that
  already conform>
```

For Form C (amend), edit only the requested frontmatter field via the
`Edit` tool. Do NOT touch the body. If the amend would set `status:
superseded` without a `superseded_by`, abort and ask for the
superseding id.

### Stage 3 — Verify

**Pre:** ADR written. **Post:** `decisions.py audit` and `link-check`
exit 0.

```bash
python3 scripts/decisions.py audit && \
  python3 scripts/decisions.py link-check
```

If either fails, surface the diagnostic and STOP — the ADR is on disk
but not registered. Common failures:
- `proposed > 30 days` — only relevant for older ADRs (won't happen on
  a freshly-authored one)
- `broken supersedes` — Form B's superseded-ADR edit didn't land
- `applies_to path missing` — fix the `applies_to` glob

### Stage 4 — Effectiveness log

**Pre:** verify passed. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
python3 scripts/log_effectiveness.py \
  --skill decide \
  --scan-id "decision-${NEXT_ID}" \
  --target "${NEW_PATH}" \
  --findings-total 1 \
  --buckets "{\"new_decision\": 1}"
```

For Form C (amend), bucket is `{"amended_decision": 1}` and findings-
total stays 1.

### Stage 5 — Summarize

Report to the user in ≤8 lines:

- Path to the new (or amended) ADR.
- ID and title.
- Related-pattern and related-smell backref candidates surfaced in
  Stage 1, with the exact line each entry should grow:
  `Decided in: ${NEXT_ID}` under the matching pattern/smell.
- Suggested next command:
  - Form A/B: human review → mark `status: accepted` via
    `/decide --amend ${NEXT_ID}` once approved.
  - Form C: nothing — the amend is the work.

Do NOT edit `canonical-patterns.md` / `architectural-smells.md`
yourself. Surfacing the backref candidate is the work; the human
decides whether to land it.

## Non-goals

- Editing `canonical-patterns.md` or `architectural-smells.md`
  (recommend the backref, don't write it — that's a separate review).
- Adding a lint rule (that's `/prevent-regression`'s job; the ADR may
  recommend one in its Verification section).
- Building a new feature / refactor (the ADR motivates the work; the
  work is `/plan-feature` or `/refactor-subsystem`).
- Recording lessons or surprises (those go in `.claude/tasks/lessons.md`).
- Exceeding 2-5 ADRs/quarter without a corresponding spike in real
  cross-cutting choices — pause and reassess.

## When things go sideways

| Symptom | Action |
|---|---|
| Slug already exists at another id | Abort; recommend `--amend <existing>` instead |
| `--supersede` target doesn't exist | Abort; ask for the correct id (`/decide --list` to confirm) |
| `--amend` target's frontmatter field is unknown | Abort; list the supported fields (status, superseded_by, applies_to, tags, related_smell, related_pattern) |
| `decisions.py audit` exits 1 | Surface the exact diagnostic; do NOT log effectiveness; ask user to fix the registry before retry |
| `link-check` finds a broken `Decided in: NNNN` reference somewhere | Report it but do NOT edit the broken reference; that's a separate cleanup |
| Form B asked to supersede an already-superseded ADR | Walk the chain to the leaf and supersede the leaf instead; flag the chain depth in the summary |
| Stage 1 finds an existing decision that already covers this topic | Abort the new-ADR draft; recommend the user `/decide --amend <existing>` to expand `applies_to` or escalate via supersession |

## Repository layout

```
.claude/skills/decide/
├── SKILL.md                  # this file — orchestrator
└── knowledge/
    └── rules.md              # ADR threshold heuristics, anti-patterns
```

The orchestrator (you) does NOT read `knowledge/rules.md` — that file
is an offline reference for designers / future maintainers explaining
the threshold rules and common ADR anti-patterns the skill is
architected to avoid. Future scout sub-agents (if added) would read it.
