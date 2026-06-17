---
name: teach-pattern
description: Cross-cutting teach skill — converts a topic (smell name, decision id, subsystem name, canonical-pattern anchor, or free-form rule) into a layered briefing at `reports/teach-pattern/scan-<TS>/<topic>.md`. Five-section structure — rule (one line), why (smell + decision link), exemplar (real spec/decision/code reference), counter-example (real find-* finding), enforcement (lint or "none yet — file a /decide"). The `--for-agent` flag re-frames the briefing as "given THIS PR context, here's why X is right and Y is wrong" so an agent can use the output directly mid-task.
argument-hint: "<topic>  [--for-agent <PR/file context>]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: teach
best_for: |
  Onboarding a new agent / team member to a project convention; mid-PR
  agent reasoning ("why is the linter telling me to do X?"); converting
  a one-line rule from CLAUDE.md into the full backstory (why it
  exists, where it's enforced, what breaks without it). The
  `--for-agent` mode is the primary use; human-readable mode is
  secondary.
not_for: |
  Authoring a new pattern (the pattern must already exist in
  canonical-patterns.md, architectural-smells.md, or as an ADR).
  Authoring a new ADR (use /decide). Detecting violations (use a
  find-* SUSPECT skill).
escalate_to: |
  None — this is a read-only briefing skill. If the user wants to
  change the rule, recommend /decide. If they want to find violations,
  recommend the matching /find-* skill.
delegate_from: |
  /which-skill recommends /teach-pattern for prompts like "explain why
  we use X", "what does the Y rule mean", "should I do A or B here".
  Mid-orchestration, /plan-feature and /architecture-fit MAY invoke
  /teach-pattern --for-agent when they need to brief themselves on a
  rule before deciding.
language: python
framework: django
---

# /teach-pattern

You are the **orchestrator** for the cross-cutting teach skill. The
deliverable is a single markdown file at
`reports/teach-pattern/scan-<TS>/<topic-slug>.md` containing a layered
briefing on one rule, smell, decision, or pattern.

The skill answers two distinct questions in one shape:

1. **For a human:** "what is this rule, why does it exist, where do I
   see it in real code?"
2. **For an agent (`--for-agent`):** "given this PR / file / change,
   here is why approach X conforms to the rule and approach Y violates
   it — concretely tied to the lines you're about to write."

Both modes share the five-section template; the `--for-agent` mode adds
a sixth "applied to your context" section at the top.

## How success is judged

- All five sections of the briefing are grounded in real artifacts:
  the rule from its canonical source, the why naming both smell and
  decision links, an exemplar citing an actual spec/ADR/file, a
  counter-example from a real find-* finding — never an invented
  snippet.
- Where no real exemplar, smell entry, ADR, or enforcement exists,
  the briefing says so explicitly ("none yet — file a /decide"),
  because naming the gap is the deliverable.
- Read-only beyond `reports/teach-pattern/scan-<TS>/<topic-slug>.md`.
Write toward these gates from Stage 0.

## Core beliefs

1. **Layered briefing > flat documentation.** Rule first (one line),
   then why, then exemplar, then counter-example, then enforcement.
   Agents and humans both stop reading at the depth they need.
2. **Real exemplars beat synthetic ones.** Cite the actual spec id,
   decision id, file path, or find-* finding — not invented snippets.
   If no real exemplar exists, say so explicitly ("no production
   exemplar yet — file an ADR via /decide").
3. **Enforcement is part of the rule.** A pattern with no lint, hook,
   or fixture is opt-in folklore. Naming the gap is the briefing's job.
4. **--for-agent mode is the high-leverage use.** Mid-PR agents need
   "should I write A or B here" answered concretely. Generic teach
   mode supports onboarding; agent mode supports decisions in flight.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** no helper script is shipped; use shell reads/greps only.
- **Read:** `.claude/docs/canonical-patterns.md`,
  `.claude/docs/architectural-smells.md`,
  `ai-docs/decisions/`,
  `ai-docs/specs/`,
  `reports/<smell>/latest/` (on-disk report dirs omit the `find-`
  prefix, e.g. `reports/omnibus/`, not `reports/find-omnibus/`),
  `.claude/CLAUDE.md`,
  `.pre-commit-config.yaml` and `pyproject.toml` (for lint enforcement
  evidence).
- **Write:** `reports/teach-pattern/scan-<TS>/<topic-slug>.md`.

## Pipeline

### Stage 0 — Setup

```bash
TS=$(date +%Y%m%d-%H%M%S)
TOPIC="<arg>"
TOPIC_SLUG="$(echo "${TOPIC}" | tr '[:upper:] /' '[:lower:]--' | tr -cd 'a-z0-9-')"
REPORT_DIR="reports/teach-pattern/scan-${TS}"
mkdir -p "${REPORT_DIR}"
ln -sfn "scan-${TS}" reports/teach-pattern/latest
```

If the user passed `--for-agent <context>`, capture the context (file
path, PR description, snippet) — you'll use it in Stage 5.

### Stage 1 — Identify topic kind

Topic resolution priority:

1. If topic matches `^\d{4}-?` → ADR id; load `ai-docs/decisions/<id>-*.md`.
2. If topic matches a heading in `.claude/docs/architectural-smells.md`
   → smell.
3. If topic matches a heading in `.claude/docs/canonical-patterns.md`
   → pattern.
4. If topic matches a `.claude/docs/subsystems/<topic>.md` → subsystem
   convention briefing.
5. Else free-form: grep all four sources for the topic words, pick the
   strongest match, note the kind.

Abort with a clear "topic not found in canonical sources — recommend
running /which-skill or /map-subsystem first" if no match.

### Stage 2 — Extract the rule (one line)

The rule is the briefing's headline. Sources:

- **ADR:** the `## Decision` section's first sentence.
- **Smell:** the smell's "rule" or "do not" line.
- **Pattern:** the pattern's first imperative sentence.
- **Subsystem:** the subsystem doc's "responsibility" cell that the
  topic touches.

Reject vague rules. If the source rule is "this is generally bad",
push back: rewrite the rule as a positive imperative ("status fields
MUST use TextChoices subclass"). Record the rewrite in the briefing's
notes.

### Stage 3 — Locate the why (smell + decision link)

For each rule, the briefing must name BOTH:

- The **smell** the rule prevents (link to
  `architectural-smells.md#<anchor>` if applicable). If no smell entry
  exists, note "no smell entry — recommend filing one alongside the
  enforcement".
- The **decision** that codified the rule (link to ADR id if
  applicable). If no ADR exists for a strict rule, note "no ADR — this
  is folklore; recommend `/decide <slug>` to formalize".

The why section is two paragraphs max. First paragraph: the smell shape
("when X happens, Y rots"). Second paragraph: the consequence
("downstream we lose Z because W can't be inferred").

### Stage 4 — Find one exemplar + one counter-example

**Exemplar** — code or spec where the rule is followed correctly.
Search order:
1. `ai-docs/specs/` for a spec with `motivating_decision: <id>` or
   text matching the rule.
2. ADR's `## Verification` section if the topic is an ADR.
3. Grep production code for the canonical-pattern anchor's example
   text.

Cite as: `<file>:<symbol>` or `<spec-id>::IM-N`. No raw line numbers
(rot fast).

**Counter-example** — a real find-* finding showing the rule violated.
Search order:
1. `reports/<smell>/latest/triage.md` for an entry that names the rule's
   smell shape (e.g., for the stringly-status rule, look at
   `reports/implicit-state/latest/`). On-disk dirs use the smell name
   without the `find-` prefix (`reports/omnibus/`, not
   `reports/find-omnibus/`).
2. `reports/_meta/effectiveness.jsonl` for past finds tagged with the
   matching skill+bucket.

Cite as: `reports/<smell>/latest/<file>::<finding-id>`. If no real
counter-example exists, say so explicitly ("no real counter-example on
record — the rule is preventive, not reactive").

### Stage 5 — Identify enforcement

Three buckets:

- **Lint enforced** — name the rule (e.g., `silent-catch`,
  `stringly-status`) and the file it lives in (`.pre-commit-config.yaml`,
  `scripts/lint_*.py`, `pyproject.toml`).
- **Test enforced** — name the test file/case if there's a fixture-based
  guardrail.
- **None yet** — explicit gap. Recommend filing a `/decide` to debate
  whether this rule is worth a lint, then `/prevent-regression
  topology:<template>` if applicable.

### Stage 6 — `--for-agent` overlay (if flag set)

When `--for-agent <context>` is passed, prepend a section that
**applies the rule to the context**. Read the context (file path or
inline snippet), look at what the agent is about to write or has just
written, and produce:

```markdown
## Applied to your context

**Your context:** `<file-path-or-summary>`

**Right (conforms):** _what to write here, citing the rule_
- Example shape: `_short snippet or symbol reference_`

**Wrong (violates):** _what NOT to write here, citing the smell_
- Example shape: `_short snippet showing the violation_`

**Why this matters in your context specifically:** _one sentence
linking the agent's work to the rule's consequence_
```

This section is the deliverable for `--for-agent` mode. The general
five-section briefing follows it as supporting depth.

### Stage 7 — Write the briefing

Output file `${REPORT_DIR}/${TOPIC_SLUG}.md`:

```markdown
# Pattern briefing — <topic>

_Topic kind: <ADR / smell / pattern / subsystem / free-form>_
_Generated: <ISO timestamp>_

[--for-agent overlay if applicable, see Stage 6]

## Rule (one line)
> <imperative sentence>

## Why
<two paragraphs — smell shape then consequence>

- Smell: `<smell-name>` (`.claude/docs/architectural-smells.md#<anchor>`)
  or _no smell entry yet_.
- Decision: ADR `NNNN` (`<title>`) or _no ADR — folklore_.

## Exemplar (rule followed correctly)
- `<file::symbol>` or `<spec-id>::IM-N` — _why this is exemplary_.

## Counter-example (rule violated in the wild)
- `reports/<smell>/latest/<file>::<finding-id>` — _what's wrong here_.
  (Or: _no real counter-example on record_.)

## Enforcement
- **Lint:** `<rule-name>` in `<config-file>` — _diff-scoped on commit_.
  (Or: _no lint yet_.)
- **Test:** `<test-module::test-name>` — _if applicable_.
- **Gap:** _explicit gap if neither lint nor test exists_.

## Notes
- _Any rewrites done in Stage 2 (vague-rule → imperative)._
- _Recommended next skill: `/decide` to formalize, `/prevent-regression
  topology:<template>` to install a lint, or none if the rule is
  already enforced._
```

### Stage 8 — Summarize

Report to the user in ≤6 lines:

- Path to the briefing file.
- Topic kind and the one-line rule.
- Whether enforcement exists (lint / test / gap).
- If `--for-agent`, one-line "applied to <context>" summary.
- Recommended next command if there's a gap.

## Non-goals

- Authoring new ADRs (that's `/decide`).
- Authoring new patterns or smells (those live in `.claude/docs/`
  edited by humans).
- Detecting violations (that's `/find-*`).
- Installing lints (that's `/prevent-regression`).
- Editing production code.

## When things go sideways

| Symptom | Action |
|---|---|
| Topic matches multiple sources (e.g., a smell AND an ADR) | Cite both; the briefing has slots for smell + decision links |
| Topic doesn't match any canonical source | Abort; recommend `/decide` to formalize a folklore rule, OR `/which-skill` to find a different starting point |
| `--for-agent` context is too vague | Push back: ask for a file path or snippet; agent-mode requires concrete grounding |
| No exemplar found in production | State explicitly "no exemplar yet — the rule is aspirational" rather than fabricating one |
| No counter-example found | State explicitly "preventive rule, no on-record violations" |
| Multiple ADRs cover the same rule | Cite all; recommend `/audit-decisions` if they conflict (broken supersedes chain) |
