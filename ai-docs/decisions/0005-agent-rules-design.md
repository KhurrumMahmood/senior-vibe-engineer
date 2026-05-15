---
id: "0005"
title: Agent rules surface uses lean root + load-on-demand tiered storage
status: accepted
date: 2026-05-07
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to:
  - .claude/CLAUDE.md
  - .claude/docs/
  - .claude/tasks/lessons.md
  - ai-docs/decisions/
  - .augment/rules/imported/
  - .augment/context.md
  - .augment/requirements.md
tags: [agent-rules, claude-md, cross-tool, doc-design, skill-ecosystem]
related_smell: null
related_pattern: null
---

# Agent rules surface uses lean root + load-on-demand tiered storage

## Context

This project gives durable instructions to three coding agents — Claude
Code, Codex, Augment — across at least seven surfaces: `.claude/CLAUDE.md`
(symlinked to root `AGENTS.md` for Codex), `.claude/docs/*.md`,
`.claude/tasks/lessons.md`, `ai-docs/decisions/`, `.augment/rules/imported/*.md`,
`.augment/context.md`, `.augment/requirements.md`, plus per-package
local `CLAUDE.md` signposts. Without an explicit placement convention,
every contributor re-derives "where does this rule go?" each time, and
the answer drifts. Two failure modes follow:

1. **Always-loaded surface bloats.** New rules pile into the root
   `CLAUDE.md` because that is the most visible file. Past a certain
   size the file stops shaping behavior and starts competing with
   itself for attention. Claude Code surfaces feedback when the
   always-loaded surface grows past tens of thousands of characters,
   but signal-to-noise ratio degrades well before that — the soft
   budget below sits under the practical complaint band, not at it.
2. **Cross-tool drift.** Rules added only to one tool's surface
   (Claude-only via `.claude/CLAUDE.md`, or Augment-only via
   `.augment/rules/imported/`) silently diverge from the other tools'
   versions of the same project. Engineers picking different agents
   for the same repo get different guidance.

The repo has accumulated three implicit conventions that resolve this
informally — captured in `cross-tool-agent-governance.md` (cross-tool
sync ladder), the supplementary-docs table in `.claude/CLAUDE.md`
(load-on-demand triggers), and two Claude-memory entries
(`feedback_claude_md_hygiene`, `feedback_memory_vs_shared_docs`).
External writing in early 2026 (Karpathy's Jan 2026 thread on AI-coding
failure modes; the *4 Lines Every CLAUDE.md Needs* article that
followed) reframed the same observation as a "configuration paradox":
behavioral constraints transfer better than feature checklists, and
past a threshold rule volume hurts. That external framing is the
trigger for promoting these conventions into an ADR; the underlying
discipline already existed in this repo.

Without an ADR, the conventions remain folklore: invisible to new
contributors, easy to override during a busy refactor, impossible to
audit mechanically.

## Decision

Agent rules use a tiered storage hierarchy with **explicit placement
criteria** and a **single decision tree** for new content. The root
`.claude/CLAUDE.md` (and its `AGENTS.md` symlink) stays lean — the file
that is *always loaded* carries behavioral discipline, project
identity, terminology pointers, and a map of where to find everything
else. Durable reference material lives in load-on-demand
`.claude/docs/*.md` files declared with explicit "Read when…" triggers
in CLAUDE.md's supplementary-docs table.

The placement decision tree, in order of preference:

1. **Behavioral discipline** (how the agent should think — frame, ask,
   trace, verify) → `.claude/CLAUDE.md` Workflow & Implementation
   Discipline section. Bullet form, ≤3 sentences each. Not domain-
   specific.
2. **Project identity / terminology / shared paths** (venv path, test
   commands, terminology pointers, server credentials, what NOT to do)
   → `.claude/CLAUDE.md` top-level sections. Brief; full content lives
   downstream.
3. **Durable architectural / domain reference** (subsystem inventories,
   conventions catalogues, deployment guides, pipeline docs) →
   `.claude/docs/<topic>.md`, registered in CLAUDE.md's Supplementary
   Documentation table with an explicit trigger row ("Read when…").
4. **Repeated / non-obvious operational fixes** ("rule + why + how to
   apply", append-only diary) → `.claude/tasks/lessons.md`.
5. **Current-state operational gotchas** (site quirks, anti-bot
   patterns, template traps) → `.claude/docs/known-issues.md`,
   updated in place.
6. **Binding choices that constrain future work or exclude
   alternatives** → `ai-docs/decisions/<NNNN>-<slug>.md` (this file is
   an example).
7. **Claude-personal context** (the user's preferences, conversation
   habits, cross-project notes) → Claude memory at
   `~/.claude/projects/.../memory/`. Project guidance does **not** go
   here — it does not cross-tool-mirror.

Cross-tool mirroring follows the ladder already in
`cross-tool-agent-governance.md`: rules placed in (3) live as the
durable architecture doc; (1) and (2) get condensed into
`.augment/rules/imported/*.md`; (4–6) are read by all agents through
the durable artifact, not duplicated. Codex follows
`.claude/CLAUDE.md` directly via the `AGENTS.md` symlink.

The `.claude/CLAUDE.md` root file has a **soft size budget of ≈30,000
characters** — high enough that the legitimate project context (lean
overview, environment, verification policy, workflow discipline,
supplementary-docs map) fits comfortably, low enough to push back when
always-loaded content drifts past the practical signal-density ceiling.
Past the budget, content gets demoted to load-on-demand docs, not
subdivided into more bullets at root.

Each `.claude/docs/*.md` has a **declared trigger** in CLAUDE.md's
Supplementary Documentation table. A doc with no trigger row is
dormant and a candidate for removal or consolidation.

## Alternatives considered

- **Single comprehensive `CLAUDE.md`.** The naïve approach implied by
  the *4 Lines* article's framing — collapse all guidance to a few
  behavioral lines plus build commands. Rejected: works for solo
  prototypes, fails for this project. this ecosystem has cross-tool sync
  requirements, non-derivable domain terminology (Site vs Site,
  extraction_recipe, NormalizedData), tier-specific verification
  policies, and a multi-stage maintenance loop that legitimately
  requires reference material the agent can't infer from code. The
  configuration paradox is real, but the cure is *load-on-demand*,
  not *delete*.
- **Per-tool authoritative files (no shared root).** Each agent reads
  its own native rule file directly; nothing shared. Rejected:
  guarantees cross-tool drift and triples the maintenance cost of
  every rule change. The `.claude/CLAUDE.md` ↔ `AGENTS.md` symlink and
  the `.augment/rules/imported/` mirror exist specifically to avoid
  this.
- **Use Claude memory as the primary doctrine surface.** Claude memory
  is durable across conversations and easier to write to. Rejected:
  memory is Claude-Code-specific; it does not reach Codex or Augment.
  Project guidance must live in artifacts every agent can read. The
  existing `feedback_memory_vs_shared_docs` memory entry already
  encodes this principle informally; this ADR formalizes it.
- **Rely on convention without an ADR.** Status quo: the placement
  rules exist as folklore plus two memory entries. Rejected: folklore
  doesn't survive contributor turnover or AI-agent edits, and
  un-ADR'd conventions can't be audited. The whole point of the
  decision registry is to make these rules legible to future agents
  and humans without requiring archaeological context.
- **Hard char limit instead of soft budget.** A pre-commit hook that
  refuses commits exceeding N characters. Deferred (see Verification),
  not rejected: a soft budget plus an audit skill is the right first
  step; promote to a hard gate only after the audit shows the budget
  is repeatedly violated.

## Consequences

**Easier:**

- Adding a new rule has a deterministic placement step instead of a
  judgment call. The decision tree above is the answer.
- Auditing the agent-rules surface — a planned `find-rule-surface-drift`
  skill (see Verification) can mechanically detect oversized files,
  dormant docs (table entry but no greppable references), cross-tool
  sync drift, and content placed in the wrong tier.
- Onboarding a new contributor (human or AI agent) — the ADR plus
  `cross-tool-agent-governance.md` together are a complete tour of how
  this project communicates with its agents.

**Harder:**

- Casual rule additions. "Just add it to `CLAUDE.md`" is no longer
  always the right answer; the contributor must consult the decision
  tree. This is the intended cost — the alternative is an always-loaded
  file that decays into noise.

**Now expected:**

- Every `.claude/docs/*.md` carries a trigger row in CLAUDE.md's
  Supplementary Documentation table. Docs without a trigger are
  dormant and get removed or absorbed.
- Rules that protect correctness, data safety, AI-provider routing,
  production writes, or benchmark validity escalate from doctrine
  (3–6) to executable guardrails (lints, hooks, CI checks) — the
  enforcement ladder in `cross-tool-agent-governance.md`. Doctrine
  alone is not a quality gate.
- New always-loaded content (1–2) keeps the root `.claude/CLAUDE.md`
  under the soft 12,000-char budget. Demote, don't subdivide, when
  the budget tightens.

## Verification

- **Doc backref.** `cross-tool-agent-governance.md` carries a
  paragraph pointing at this ADR for content-placement governance
  (the doc continues to own enforcement-ladder mechanics).
- **Existing artifacts.** The current state largely follows the
  decision: `.claude/CLAUDE.md` is lean by design and explicitly says
  so (currently ~16K, well within the ≈30K soft budget); `.claude/docs/`
  holds 25+ load-on-demand docs each declared with a trigger row, with
  a handful of legitimate inventory docs (e.g. `architecture.md`,
  `pipelines.md`) running past the per-doc soft ceiling — these are
  exemptions, not drift; `ai-docs/decisions/` holds binding choices;
  `.claude/tasks/lessons.md` is the diary; `.augment/rules/imported/`
  mirrors the always-apply rules.
- **Planned skill** (Stage B sketch): `.claude/skills/find-rule-surface-drift/`
  is a SUSPECT-tier skill that scans for:
  - **Oversized files** (Stage 1): `.claude/CLAUDE.md` exceeding the
    soft 30K budget, individual `.claude/docs/*.md` over a per-doc
    threshold (default 50K).
  - **Doc-table drift** (Stage 1): every entry in CLAUDE.md's
    Supplementary Documentation table → does the file exist? every
    file in `.claude/docs/` → does it have a trigger row in the table?
  - **Dormant docs** (Stage 1): docs with no greppable references from
    any other `.claude/` artifact (excluding worktree mirrors).
  - **Cross-tool sync drift** (Stage 2 — deferred): rule fragments
    present in `.claude/CLAUDE.md` but absent from
    `.augment/rules/imported/*.md`, or vice versa. Requires
    content-level comparison heavier than a filename check; add when an
    actual drift incident motivates the cost.
  Detection-only; reports under
  `reports/find-rule-surface-drift/scan-<TS>/`. Pairs with
  `/fix-workflow` for migrations.
- **Planned guardrail** (Stage B sketch): a pre-commit hook checking
  the soft `CLAUDE.md` char budget; a CI check for cross-tool drift.
  Promoted from soft to hard only after the audit skill establishes
  the budget is workable in practice.
- **Memory consolidation.** `feedback_claude_md_hygiene` and
  `feedback_memory_vs_shared_docs` memory entries become redundant
  pointers to this ADR; they remain as Claude-personal cross-project
  reminders but are no longer the authoritative source for this
  project's policy.
