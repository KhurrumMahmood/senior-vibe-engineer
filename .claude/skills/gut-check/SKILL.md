---
name: gut-check
description: Instinctive senior-engineer "does this look dumb?" reaction pass over a plan markdown, a commit diff, or a free-form architecture summary. Emits 3-5 cited smell reactions split into un-decided smells (no precedent / ADR covers them — raw signal) and decided-but-still-smell (an ADR or precedent explains why the project did it this way, but the smell still surfaces — surface both so the human can decide whether to re-litigate). Confidence-banded (strong-smell / weak-smell / style-preference). Prompt-only, no helper script.
argument-hint: "<target-path-or-inline-summary> [--mode plan|build|architecture] [--include-style]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: teach
best_for: |
  Quick instinct check on a plan markdown, a commit diff, or an
  architecture summary right before the work goes from "designed" to
  "built" — the moment when a senior engineer skimming it cold would
  flinch at a wrong shape, over-engineering, or hidden coupling. Highest-
  leverage use is decision-conflict flagging: surfaces smells that
  already conflict with the host project's decision registry or
  precedent registry so the human knows BOTH that the smell exists AND
  that a deliberate decision contradicts it. Lean instinct, not
  checklist review.
not_for: |
  Mechanical lint enforcement (use the host project's linter). Detection
  of named architectural smells across a codebase (use the matching
  /find-* SUSPECT skill). Authoring an ADR (use /decide). Pattern-rule
  briefing — "explain why we do X" (use /teach-pattern). Code review of
  a PR (use the host project's review skill). Plan validation against
  decisions (use /architecture-fit). Anything that needs ground truth —
  gut-check produces SIGNAL, not VERDICT.
escalate_to: |
  /decide when a repeat smell suggests a decision should be revisited;
  /architecture-fit when the plan needs systematic decision-registry
  validation (not just instinct); the matching /find-* SUSPECT skill
  when the smell deserves a real audit pass across the codebase.
language: any
framework: any
---

<!--
Generalization Checklist (engineering-skills mirror)

This skill is host-project-agnostic. When porting / regenerating:

- No hardcoded paths beyond the conventional ones every project hosting
  this skill ecosystem already exposes: `ai-docs/decisions/`,
  `.claude/docs/architectural-smells.md`, `.engineering/docs/subsystems/`,
  `.claude/docs/precedents.yml` (optional — see "Optional inputs"
  below).
- No project-specific ADR ids in worked examples — use placeholders
  like "ADR NNNN (slug)" and "your decision registry."
- No project-specific subsystem names (`SiteConfiguration`, `PartShare`,
  etc.) — worked examples reach for generic shapes
  (DispatchService / FacadeAdapter / etc.).
- No project-specific lint names. Worked examples reference the
  shape of a smell, not a host-project lint rule name.
- The "Optional inputs" section flags `.claude/docs/precedents.yml` as
  optional. If a host project doesn't ship that file, the skill skips
  precedent-conflict flagging and falls back to ADR-only matching.
- Mode inference rules reference common plan locations
  (`ai-docs/plans/`, `ai-docs/specs/`, `.claude/plans/`) but not any
  project-specific path. Hosts that organize plans differently can
  override via `--mode`.

If you find yourself injecting a project-specific reference, instead
declare it under "Optional inputs" with a fallback shape and document
the override as a per-project deviation.
-->

# /gut-check

You are a senior engineer reading the artifact cold. Your job is to
write down what makes you flinch — instinctively, before you've fully
reasoned through it. Reactions can be wrong; the value is surfacing
them so the human can decide.

This is **signal, not verdict**. The output names smells. The human
decides what to do with each one. Decision-conflict flagging is the
highest-leverage output — never suppress a smell just because an ADR
or precedent covers it. Surface both: "this looks dumb, but ADR X
explains why we did it this way."

## How success is judged

- Every reaction in `reports/gut-check/scan-<TS>/<target-slug>.md` is
  cited (the line/section that triggered the flinch), confidence-banded
  (`strong-smell` / `weak-smell` / `style-preference`), and split into
  un-decided vs decided-but-still-smell against the decision sources.
- Decision sources were actually loaded — when `precedents.yml` is
  absent, the report says precedent matching was unavailable for this
  run rather than silently skipping it.
- "No instinctive smells" is a valid, stated outcome — never pad with
  low-confidence filler. Signal, not verdict; zero production touches.
Write toward these gates from Stage 0.

## Core beliefs

1. **Instinctive smell, not mechanical scoring.** This skill is the
   half-second flinch when an experienced engineer reads a design and
   thinks "wait, why?" — not a structured rubric pass. Lean into "what
   would a senior engineer flinch at" rather than "what does the
   checklist say."
2. **Decision-conflict flagging is the load-bearing feature.** A smell
   that re-surfaces despite an ADR is meaningful: it either means the
   reader doesn't have the context the decision encodes, OR it means
   the decision deserves a fresh look. The split into "un-decided
   smells" vs "decided-but-still-smell" turns noisy "feels bad" output
   into actionable signal.
3. **Confidence-banded output, hide weak signal by default.** Three
   bands: `strong-smell` (push back hard), `weak-smell` (first read
   flinched), `style-preference` (would write it differently, not
   wrong). The default emits the first two only; `--include-style`
   surfaces the third for cases where the user actually wants taste-
   level feedback.
4. **No reactions is a valid output.** If nothing instinctively looks
   dumb, say so — don't pad with low-confidence smells to fill space.
   "No instinctive smells" is information.
5. **Repeat reactions across multiple invocations are a signal to
   level-up.** When the same smell shows up across runs, that's a hint
   to upgrade it to a named entry in the host project's
   `architectural-smells.md` or to open a `/decide`. The skill mentions
   this in its summary when it notices the pattern.

## Scope

- **Target:** a markdown file path, a directory path (commit diff or
  recent-changes snapshot), or an inline architecture summary passed
  as the argument.
- **Project root:** this worktree's root.
- **Read:**
  - `ai-docs/decisions/` (read filenames + frontmatter; only deep-read
    an ADR when its slug matches a smell you're emitting).
  - `.claude/docs/architectural-smells.md` — use this vocabulary when
    naming a smell.
  - `.engineering/docs/subsystems/<slug>.md` (architecture mode only, when
    the inline summary names a known subsystem).
    On a schema-2 host, use `.claude/docs/subsystems/<slug>.md` only when the
    canonical file is absent, and surface a host-state migration warning. If
    both exist, stop rather than treating them as separate authorities.
- **Optional inputs:**
  - `.claude/docs/precedents.yml` — implementation case law. If the
    host project ships this file, precedent-conflict matching feeds the
    `decided-but-still-smell` bucket alongside ADR matches. If the file
    is absent, rely on ADR matching only and state in the report that
    precedent matching was unavailable for this run.
- **Write:** `reports/gut-check/scan-<TS>/<target-slug>.md`.
- **No code edits.** No file moves. No production touches. The skill
  writes one report and reports the path back.

## Argument parsing & mode inference

Three placement modes. The skill infers the mode unless the user
passes `--mode plan|build|architecture` explicitly.

### Mode inference rules

1. If the argument is a file path ending in `.md` AND lives under a
   plan / spec directory (commonly `ai-docs/plans/`, `ai-docs/specs/`,
   `.claude/plans/`, `~/.claude/plans/`) → **plan mode**.
2. If the argument is a file path ending in `.md` with a different
   shape — read the first 30 lines:
   - Plan-like headings (`## Scope`, `## Impact`, `## Architecture
     Fit`, `## Open decisions`) → **plan mode**.
   - Architecture-like prose (no spec-style headings, free narrative
     about components / boundaries / data flow) → **architecture
     mode**.
3. If the argument is a directory path → assume it's a recent-changes
   snapshot; **build mode**.
4. If the argument starts with text that isn't a path (no `/`, no
   `.md` ending) AND is longer than 80 chars → **architecture mode**,
   treat the argument as the inline summary.
5. If nothing fits, ask the user to disambiguate with `--mode`.

The user can always override the inference with
`--mode plan|build|architecture`.

### `--include-style` flag

By default, only `strong-smell` and `weak-smell` reactions are emitted.
Pass `--include-style` to surface `style-preference` reactions too.
Style preferences pad the output and bury signal — keep them off
unless the user asked for taste-level feedback.

## Pipeline

### Stage 0 — Setup

```bash
TS=$(date +%Y%m%d-%H%M%S)
TARGET="<arg>"
# Slug: replace / and . with -, lowercase, strip leading dashes.
SLUG="$(echo "${TARGET}" | tr '/.' '--' | tr '[:upper:]' '[:lower:]' \
        | sed 's/^-*//; s/-*$//' | cut -c1-80)"
[ -z "${SLUG}" ] && SLUG="inline-summary"
REPORT_DIR="reports/gut-check/scan-${TS}"
mkdir -p "${REPORT_DIR}"
ln -sfn "scan-${TS}" reports/gut-check/latest
```

### Stage 1 — Resolve target + load context

1. Resolve the target per the mode-inference rules above.
2. Read the target:
   - **plan mode** — read the entire plan file.
   - **build mode** — `cd` to the directory and run
     `git diff HEAD~1` (or `git diff --staged` if HEAD~1 doesn't
     exist) to get the recent changes. If the target is a specific
     commit ref (`<sha>`, `<branch>..<branch>`), pass it to `git
     diff`. If neither works, read the directory's recently-modified
     files (`git status --short` then read each).
   - **architecture mode** — the inline summary IS the target; if a
     file path was passed, read the file.
3. Load decision sources in this order (cheap reads first):
   - `.claude/docs/precedents.yml` — if present, full file (it's
     small). If absent, skip and note that precedent matching is
     unavailable for this run.
   - `ai-docs/decisions/` — list filenames; read the first 20 lines
     of each (title + frontmatter only). Note the slugs.
   - `.claude/docs/architectural-smells.md` — full file. Use its
     named smells as the vocabulary when citing.
   - **Architecture mode only**: if the summary names a known
     subsystem, try to read `.engineering/docs/subsystems/<slug>.md`.

If the target doesn't resolve (bad path, empty inline summary, can't
read), stop and write a `reports/gut-check/scan-<TS>/<slug>.md`
recording the failure mode (`target_not_found`, `target_empty`).

### Stage 2 — React (the actual gut-check)

This is the only stage that is real judgment work, not mechanical.
Read the target the way a senior engineer would skim it cold — once,
without re-reading — and write down the things that make you flinch.

**What to look for per mode:**

**Plan mode** — react to *plan shape*:
- Missing context (no current-state, no constraint enumeration).
- Over-engineering relative to the problem (3-layer abstraction for
  a 1-call-site need).
- Scope creep (the plan started as one thing and grew tentacles).
- Unverifiable claims ("this will be faster" with no benchmark).
- Weird sequencing (Phase 3 depends on Phase 5; rollback path
  unclear).
- Mismatched verification (heavy plan, no test plan section; or vice
  versa).
- "And"-sized scope — a plan whose title joins three independent
  goals with "and" almost always means three plans crammed together.
- Phantom users / phantom requirements — features designed for an
  unnamed audience.

**Build mode** — react to *code shape*:
- Dumb abstractions — an interface for one impl, a factory for one
  product, a strategy pattern over a two-case if.
- Premature generality — config for a case that doesn't exist yet.
- Defensive code for impossible states (null-checks after assignment,
  re-validation of already-validated input).
- Weird naming (`process_data`, `handle_thing`, `do_stuff` —
  uncommunicative; or `XHandlerStrategyFactoryImpl` — over-
  ceremonial).
- Dead code paths (branches that can't trigger, exception handlers
  that catch and re-raise unchanged, logging in code that's already
  unreachable).
- Comment debt (block comments restating what the code says, stale
  TODOs from years past, "obvious" comments that signal the
  surrounding code isn't obvious).
- Test ceremony without coverage (10-line setup for a 1-line
  assertion; mocked-everything tests that pass tautologically).
- Inconsistent error handling within the same change.

**Architecture mode** — react to *architectural shape*:
- Leaky boundaries (component A reaches into B's internals; B
  exposes too much).
- "And"-named components (`UserAndOrderManager`, `ValidationAndLog
  Service`) — almost always doing two jobs.
- Hidden coupling (A and B "don't depend on each other" but every
  change to A requires a change to B).
- Over-symmetry — five components each doing approximately the same
  thing because the layout demanded symmetry, not because the
  problem has five shapes.
- Ceremony without payoff — patterns invoked because the team
  "should use the X pattern" rather than because the problem fits it.
- Missing seams in the obvious places (no clear data-in / data-out
  boundary, no testable unit between IO).
- Single source of truth violations (two writers, no canonical
  producer — the format-equivalence-gap smell in
  `architectural-smells.md`).
- Layering inversions (the lowest-layer module imports from the
  highest).

**Score each reaction** with one of:
- `strong-smell` — "this looks really wrong, I'd push back hard."
- `weak-smell` — "this might be fine, but my first read flinched."
- `style-preference` — "I'd write this differently but it's not
  wrong." (Hidden unless `--include-style` is set.)

**Cap reactions** at 3-5 per band. If you have more than 5
strong-smells, you're checklist-scanning, not gut-reacting; cull to
the top 5. If you have fewer than 3, that's fine — instinct is
sparse.

### Stage 3 — Cross-check against decisions / precedents

For every reaction (strong + weak), check:

1. **Precedents (if `.claude/docs/precedents.yml` exists)** — does
   any `id:` entry's `applies_to:` glob cover the surface this
   reaction touches, AND does the entry's `summary:` describe a
   positive form of the smell you're flagging? If yes, the reaction
   is "decided-but-still-smell."
2. **ADRs** — match the reaction's smell shape against the ADR
   slugs you read in Stage 1. If a slug obviously matches the
   reaction's smell (e.g. an ADR titled "TextChoices for State"
   matches a stringly-typed reaction), deep-read that ADR's
   `## Decision` and `## Consequences` sections. If the ADR
   explicitly justifies the shape that triggered your smell, the
   reaction is "decided-but-still-smell."

When you find a decided-but-still-smell, name the decision
explicitly: `[strong-smell, contradicted by ADR NNNN (slug)]`.
Include the one-line summary of what the decision says, and a
`Re-confirm the decision?` line — yes/no with a one-sentence reason.
Sometimes a smell that re-surfaces is the signal that an ADR
deserves a fresh look; sometimes it just means the reader doesn't
have the context.

When you find a precedent match, cite it as `[weak-smell,
contradicted by precedent <id>]` using the precedent's `id:` value.

If a reaction doesn't conflict with any precedent or ADR, it stays in
the un-decided bucket — raw smell signal, nothing in the case law
either explains it away or contradicts it.

### Stage 4 — Write the report

Write `${REPORT_DIR}/${SLUG}.md` using the exact template below. Cite
specific lines / sections of the target where possible; for inline
architecture summaries, quote the offending phrase verbatim.

```markdown
# /gut-check — <target>

**Mode:** <plan|build|architecture>
**Target:** <path or "(inline summary)">
**Generated:** <ISO-8601 UTC>

## Reactions (un-decided smells)

1. **[strong-smell]** <one-line reaction>
   - *Why this looks dumb:* <2-3 sentence explanation>
   - *What a senior would expect instead:* <alternative>
   - *Cited line/section in target:* `<quote or line ref>`

2. **[weak-smell]** <one-line reaction>
   - ...

3. **[style-preference]** <one-line reaction>   <!-- only if --include-style -->
   - ...

## Reactions (decided-but-still-smell)

1. **[strong-smell, contradicted by ADR NNNN (slug)]** <one-line reaction>
   - *Why this still looks dumb:* <explanation>
   - *What ADR NNNN says:* <one-line summary of the decision>
   - *Re-confirm the decision?* <yes/no with reason — sometimes a smell that re-surfaces is signal the decision deserves a fresh look>
   - *Cited line/section in target:* `<quote or line ref>`

2. **[weak-smell, contradicted by precedent <id>]** <one-line reaction>
   - ...

## No reactions

(Only if both buckets above are empty.)

> No instinctive smells. Either the artifact is well-shaped, or the
> gut-check missed something — humans should still review.

## Notes (orchestrator judgment)

A short prose section. Use it for:

- Repeat-smell observations — "this is the third time this branching
  shape has triggered an instinct flag; consider promoting it to
  `architectural-smells.md` or filing a `/decide`."
- Calibration warnings — "the target is a prototype plan; smell bar
  should be lower than for a System-tier spec."
- Cross-reference hints — "smell N above sounds like
  `/find-layer-violation` territory; consider an actual audit pass."

## Honest framing

- These reactions are *signal*, not *verdict*. Each can be wrong.
- Decision-conflict flagging is the highest-leverage output of this
  skill — if a smell is contradicted by an ADR or precedent, the human
  should both KNOW the smell exists AND know that a deliberate
  decision contradicts it. Don't suppress either half.
- If the same reaction surfaces across multiple `/gut-check` runs on
  different targets, that's a hint to upgrade it to a named entry in
  the host project's `architectural-smells.md` or to file `/decide`
  on the underlying rule.
```

### Stage 5 — Summarize

Report to the user in ≤8 lines:

- Counts by band (`strong-smell` / `weak-smell` /
  `style-preference` if shown).
- Counts by bucket (`un-decided` / `decided-but-still-smell`).
- Top reaction per bucket (one line each, with citation).
- Path to `${REPORT_DIR}/${SLUG}.md` and the `latest` symlink.
- One recommended next move only if a strong-smell warrants it —
  `/decide` if a decided-but-still-smell deserves re-litigation, the
  matching `/find-*` SUSPECT skill if a code-shape reaction deserves
  a real audit, `/architecture-fit` if a plan-mode strong-smell hits
  the decision registry.

If no reactions surfaced, say so plainly. Do NOT pad the summary.

## Worked examples

### Plan mode — `/gut-check ai-docs/plans/dispatch-layer-redesign.md`

Plan-style markdown under `ai-docs/plans/`; mode inferred as `plan`.

The skill reads the plan, the (optional) precedents, the ADR list, and
`architectural-smells.md`. Reactions might look like:

- `[strong-smell]` The plan proposes a 4-layer abstraction
  (DispatchService → DispatchHandler → DispatchRouter →
  DispatchExecutor) for a routing problem with three discrete
  modes. A senior would expect a 1-function dispatcher with a
  pattern-match or dict lookup; the layered version is solution-
  pattern theater.
- `[weak-smell, contradicted by ADR NNNN (sidecar-types-split)]`
  The plan re-couples two subsystems that an existing ADR explicitly
  split. *Re-confirm the decision?* No — the plan should narrow the
  payload to the feature-only sub-shape rather than re-litigate the
  split.

### Build mode — `/gut-check services/dispatch/`

Directory target; mode inferred as `build`. Skill runs
`git diff HEAD~1 -- services/dispatch/` and reacts to the diff.

- `[strong-smell]` `DispatchHandler.handle()` catches the top-level
  exception base class, logs, and returns a sentinel. A senior would
  expect the dispatcher to let unexpected exceptions surface upward
  and only catch the documented `DispatchError` subclass.
- `[weak-smell]` A new file `dispatch_handler_strategy_factory.py`
  contains 8 lines: a single class with one factory method that
  returns one of three handlers based on a discriminator field. A
  senior would expect a 4-line module-level function.

### Architecture mode — `/gut-check "We're proposing an AccountAdapter abstraction that wraps PrimaryProfile, OAuthCredentials, and BillingProfile in a single facade, so callers can do account_adapter.fetch_dashboard() without knowing which profile source applies."`

Long inline argument; mode inferred as `architecture`.

- `[strong-smell]` The "single facade" is the omnibus-module smell
  (see `architectural-smells.md`) at the service layer. OAuth
  credentials and billing profile answer different questions;
  collapsing them into one facade obscures ownership. A senior
  would expect each profile source to keep its own service and the
  facade to be replaced by a thin caller-side helper that knows
  the routing rule.
- `[weak-smell]` "without knowing which profile source applies"
  signals coupling-hiding, not coupling-removal. If the caller
  *should* know which source applies, the facade is fighting the
  problem; if it shouldn't, the routing rule itself is the
  abstraction worth naming.

## Non-goals

- This is not a code-quality linter. It's an instinct skill, not a
  rule-based checker.
- This is not a substitute for `/architecture-fit` (systematic plan
  validation against the decision registry).
- This is not a substitute for a real PR-level review skill
  (adversarial code review on a PR).
- This is not a substitute for the `/find-*` SUSPECT skills. When
  the same smell surfaces three times, escalate to the real audit.
- This does NOT touch code, configs, or specs. The only output is
  the markdown report under `reports/gut-check/`.

## When things go sideways

| Symptom | Action |
|---|---|
| Mode inference picks wrong mode | Re-run with explicit `--mode plan\|build\|architecture` |
| Target is too small for instinct (< ~30 lines of plan or < ~5 changed lines of code) | Note "below the instinct threshold" in the report and emit no reactions; suggest re-running after the change grows or skipping the skill entirely |
| Every reaction is style-preference | Re-read the target more critically; if there's genuinely nothing strong/weak, emit the "No reactions" output rather than padding |
| Reactions all conflict with the same ADR | The ADR may itself be due for a fresh look — surface that observation in the Notes section and recommend `/decide` to amend, or `/audit-decisions` if the ADR's `applies_to:` paths look stale |
| Inline summary is ambiguous | Push back: ask for a file path, a snippet, or a longer description; gut-check needs concrete grounding |
| Host project has no `precedents.yml` | Use ADR-only matching and write a report note that precedent matching was unavailable for this run |

## Repository layout

```
.claude/skills/gut-check/
└── SKILL.md          # this file — the whole skill, prompt-only
```

No helper script. The whole skill is the LLM reading the artifact +
decision sources and emitting the structured output. The simplicity
is intentional — the moment a helper script tries to "score" smells
mechanically, the instinctive character of the skill is lost.

## Related

- `.claude/docs/architectural-smells.md` — the host project's named
  smells. When `/gut-check` repeatedly surfaces an unnamed pattern,
  the follow-up is adding a new smell entry there.
- `.claude/docs/precedents.yml` — optional implementation case law.
  The split into `un-decided` vs `decided-but-still-smell` reads from
  this file when present.
- `ai-docs/decisions/` — the ADR registry. Decision-conflict flagging
  reads filenames + frontmatter at scan time.
- `/architecture-fit` — systematic plan validation against the
  decision registry. `/gut-check` is the cheaper, more instinctive
  sibling.
- `/teach-pattern` — when a `/gut-check` reaction needs a full rule
  briefing ("what does this rule actually mean?"), escalate there.
- `/decide` — when a repeat reaction suggests the underlying rule
  deserves an ADR, or when a decided-but-still-smell should be
  re-litigated.
