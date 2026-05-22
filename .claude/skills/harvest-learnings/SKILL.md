---
name: harvest-learnings
description: Distill a host project's forged learnings (lint suite, precedents, ADRs, idea ledger, known-issues) AND latent production-grade standards the project skips into PORTABLE standards — each carrying an attributed exemplar + durable host back-link, a portability verdict (ports / stays-home via a translation test), and a lifecycle×stakes activation tag (ADR 0020). Recurring; two-source (extractive + generative); proposal-only — never edits code or auto-adopts. Use to mine a project for cross-project standards, refresh the portable corpus, or convert one-off discoveries into reusable guardrails.
argument-hint: "[host-project root or a specific forged surface — defaults to the current repo's lint suite + precedents + ADRs + ledger + known-issues]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: construct
best_for: |
  Mining a forged host project for portable standards: every lint rule,
  precedent, ADR, and known-issue is a learning that cost something to
  find — harvest distills each to its portable core with an attributed
  exemplar, then runs a translation test to decide if it ports off this
  stack. Also surfaces production-grade standards the project SHOULD hold
  but a "hit-the-goal" pass skipped (idempotency, fail-closed, cost
  bounds, default-closed authz, races). Recurring — re-run as the project
  forges more.
not_for: |
  Capturing a single project-local idea mid-task (use /track-idea or
  /extract-existing-ideas). Documenting one already-known pattern (use
  /teach-pattern). Coverage-checking a standard that already exists (use
  /find-standard-gaps). Running reactively inside an unrelated feature or
  bug task. A greenfield project with no forged surfaces (no lints /
  precedents / ADRs) — only the generative source would fire, which alone
  is just "list good practices," low value.
escalate_to: |
  /decide when a harvested standard rises to durable doctrine (an ADR).
  /plan-skill when a harvested standard warrants its own detector skill.
  /find-standard-gaps to give an adopted standard an executable detector.
language: any
framework: any
lanes: [quality-kernel, knowledge-harvest]
consumes: [host_project_forged_surfaces, latent_production_standards]
produces: [portable_standard_candidates, portability_verdicts]
max_overhead: "Stop if nothing forged exists to extract and the generative source is the only input — that is a checklist, not a harvest."
---

# /harvest-learnings

You are the orchestrator for a CONSTRUCT skill. You mine a **host project** for
learnings and emit **portable standards** — each carrying the thing that makes a
principle usable by an AI reader instead of inert: a specific, attributed
**exemplar** and a **back-link** to the incident that forged it, plus a
**portability verdict** and an **ADR-0020 activation tag**.

The problem this solves: a portable principle with no exemplar is operationally
inert — "validate input" tells an agent nothing about *when it bit*. The forge
(a host project's lints, precedents, ADRs, incidents) is where the teeth are.
This skill carries the teeth across, and refuses to emit a principle without
them.

## Core beliefs

1. **The exemplar is the teeth.** A portable standard with no attributed
   exemplar + back-link is shallow by construction — do not emit it. The absence
   of an `exemplars:` field in the portable corpus today *is* its shallowness.
2. **Portability is earned, not assumed.** Every candidate faces one question:
   *strip the framework, the language, the domain — does the rule survive?*
   Survives → ports. Dies → stays home (still valuable; recorded project-local).
   A harvest where **nothing** stays home means the test never bit — suspect it.
3. **Two sources, not one.** Extractive (forged surfaces) AND generative
   (production standards the project skips). Generative alone is a checklist;
   extractive alone misses the latent gaps.
4. **Activation, not just a rule (ADR 0020).** Tag each standard `baseline`
   (always) or a rung with `{min_maturity, min_stakes}`. An untagged standard
   can't be gated — it will nag a prototype or be ignored.
5. **Proposal only.** Emit a report. Adoption into the corpus is a reviewed,
   downstream step. Never edits code; never auto-adopts.

## Scope

- **Input:** a host project root (default: current repo).
- **Output:** `reports/harvest/scan-<TS>/harvest.md` (+ `harvest.json`). Never
  edits code; never auto-adopts.
- **N=1 honesty:** with one forge, "ports" is a *hypothesis*
  (`single-constraint-set`), not a proven generalization — it graduates to
  `validated-across-N` only when a second project confirms it (pairs with the
  pattern-library qualifier ladder). Mark every ported item's confidence so.

## Pipeline

### Stage 0 — Setup
```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/harvest/scan-${TS}"
mkdir -p "$REPORT_DIR"
```

### Stage 1 — Extractive gather (the forged surfaces)
Enumerate each surface where a learning was forged. Each is a candidate. Prefer
**durable handles** (rule name, ADR id, precedent id) as back-links over raw
`file:line`, which rots.
- **Lint suite** — every project AST/regex lint IS a forged learning. (pnci:
  `silent-catch`, `stringly-status`, `query-mutation`, `fat-view`,
  `safe-dispatch`, `site-intelligence-boundary`, `pies-image-dict`,
  `no-retailer-references`.) Find them via the linting docs + lint sources.
- **`precedents.yml`** — implementation case law (exemplars, guards, exceptions).
- **ADRs** (`docs/decisions/` or `ai-docs/decisions/`) — choices that constrain.
- **Idea ledger**, **memories**, **known-issues** — recurring fixes, gotchas.
For each: capture the rule, the originating exemplar (what bit), the back-link.

### Stage 2 — Generative enumerate (the skipped standards)
Independently, enumerate production-grade standards the project *should* uphold
that a "hit-the-goal" pass skips — from latent senior-eng knowledge, not the
project's existing rules: idempotency on retried writes, fail-closed on
irreversible paths, default-closed authz, structured/correlated logging,
resource + cost bounds on unbounded loops, data lifecycle / PII, reversible
migrations, concurrency / races. For each, look in the host project for a
**witness** (a place it's violated) — that witness becomes the exemplar. No
witness → mark generative-only (lower teeth; flag it).

### Stage 3 — Portability translation test
For every candidate (both sources), strip three layers and ask if the rule
survives — see `knowledge/output-schema.md` for the full test:
- **Ports** → portable standard (de-stacked statement + original-stack exemplar).
- **Stays home** → project-local; record it (still valuable), do NOT emit portable.
- **Principle-ports-mechanism-stays** → port the principle, leave the mechanism.

**Self-check (the filter must bite):** if zero candidates stayed home, re-examine
Stage 3 — you almost certainly let a stack-specific rule through.

### Stage 4 — Activation tag (ADR 0020)
Tag each ported standard `baseline: true` (maintainability/consistency + cheap
common-sense safety — always on) OR `rungs` each with `{min_maturity,
min_stakes}`. Note its depth ladder if it has one (cheap rung baseline; heavier
rungs stakes-gated). Schema + worked examples in `knowledge/output-schema.md`.

### Stage 5 — Emit + summarize
Write `harvest.md` + `harvest.json` per the schema. Report in ≤12 lines: counts
(ported / stayed-home / generative-only); the highest-value ported standards; the
items that stayed home (proof the filter bit); the N=1 confidence caveat; the
report path. Routing adopted items into the corpus is a follow-up (`escalate_to`).

## Non-goals

- Editing code or adopting standards — proposal only.
- Capturing a project-local idea (→ `/track-idea` / `/extract-existing-ideas`).
- Documenting one known pattern (→ `/teach-pattern`).
- Coverage-checking an existing standard (→ `/find-standard-gaps`).
- Proving generalization from one project — that is the pattern-library's
  `validated-across-N` job; a single harvest yields hypotheses.

## When things go sideways

| Symptom | Action |
|---|---|
| Nothing stayed home | The translation test didn't bite — re-run Stage 3; you let stack-specific rules through |
| A "portable" item has no exemplar | Drop it or find the witness — a bare principle is the shallowness this skill exists to cure |
| Only the generative source produced anything | No forged surfaces, or Stage 1 was skipped — a harvest with no extraction is a checklist (see `max_overhead`) |
| Back-links are raw `file:line` | Re-cite durable handles (lint name, ADR id, precedent id); `file:line` rots |

## Repository layout

```
.claude/skills/harvest-learnings/
├── SKILL.md                  # this file — orchestrator (prompt-driven judgment)
└── knowledge/
    └── output-schema.md      # the per-item output contract + the translation test
```
