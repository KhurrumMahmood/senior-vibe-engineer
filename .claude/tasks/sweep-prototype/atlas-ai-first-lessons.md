# Lessons from Atlas for an AI-first toolkit

**Date:** 2026-06-11 · **Source:** four parallel probes (3 Haiku, 1 Fable) + the
precision measurement (atlas-precision.md) over Atlas/App head
(667k LOC TS, 6,319 files, 1000+ contributors). Total probe cost ≈ 160k tokens.

Atlas is uniquely instructive because it is *already half-migrated to
AI-first*: a 317-line CLAUDE.md, `.claude/skills/coding-standards/` with 30+
atomic rule files (PERF-N, CONSISTENCY-N, each with applicability conditions),
an LLM "ProposalPolice" that withdraws duplicate contributor proposals,
AI_ETIQUETTE.md, RFC-2119 normative `philosophies/` docs — grafted onto a
quality system built for renting judgment from 1000+ paid strangers. The graft
lines are where the lessons are.

## Headline lesson: diff-scoped guards cannot see integral-scoped rot

The single deepest finding. ReportUtils.ts (13,400 LOC, ~456 functions, 456
importers) survived elite discipline — strict TS, custom lints, a ratcheting
baseline, RFC-2119 philosophy docs — **because** of three mechanisms:

1. **The placement rule manufactures the sprawl.** `philosophies/DIRECTORIES.md`
   is precise about pages/components but says only "non-UI goes in src/libs" —
   no granularity rule, so 114 flat `*Utils.ts` files are *fully compliant*.
2. **Every guard evaluates the delta.** ESLint, seatbelt, compiler checks are
   all line/diff-scoped. Structural drift is the integral of locally-clean
   diffs; no reviewer ever sees the integral.
3. **Decomposition happens by accretion, never subtraction.** New facets get
   new sibling files (ReportNameUtils, ReportTitleUtils, …) while the old mass
   never moves — no PR has the mandate to break 456 importers.

**Implication:** the SUSPECT family (find-omnibus, folder-topology-drift,
fan-in budgets) is the layer even elite human orgs structurally lack — not a
nice-to-have. Strongest external validation of the toolkit thesis to date.

## Convergent evolution: their practice ↔ our concept

| Atlas (independently evolved) | Toolkit concept validated |
|---|---|
| CLAUDE.md = 317-line systems map + non-negotiable post-edit checklist; style deliberately excluded | Lean always-loaded root + load-on-demand (ADR 0005) |
| `.claude/skills/coding-standards/` — one rule per file, ruleId, reasoning, examples, applicability conditions | Skill-per-concern, atomic condition-tagged rules |
| `eslint.seatbelt.tsv` — 2,119-row file×rule×count baseline, CI-owned, bot-tightened, one-way ratchet | prevent-regression + ratchet, with mechanics we lacked |
| 128 no-restricted-import guards from their module registry | Boundary lints / propose-boundary |
| `philosophies/OVERENGINEERING.md`: "Solutions MUST address only the stated problem" | Smallest-responsible-fix, verbatim |
| ProposalPolice (LLM gate on contributor proposals) | Adversarial review lane |
| ONYXKEYS.ts / ROUTES.ts typed registries | `.claude/contracts/`, canonical registries |
| Prose-vs-enforced measured: ~35% of STYLE.md lint-backed; PERFORMANCE/STYLING ≈ 0% and rotting | "Prose is the layer that already failed" — enforcement hierarchy |

## New concepts the probes generated (we did not have these)

1. **The structural seatbelt.** Generalize the ratchet beyond lint rules to
   structural metrics: `ReportUtils.ts  max-lines  13400`, fan-in budgets,
   responsibility counts — baseline auto-tightened, never regressing. The
   mechanism exists in their repo; it is pointed at the wrong granularity.
2. **Baselines invert under agents: amnesty → work queue.** Grandfathered
   violations exist because humans cannot fix 1,359 old casts before shipping.
   An agent can burn the baseline down nightly. The seatbelt becomes a
   machine-readable backlog with an assigned drainer — connects directly to
   the sweep harness (the baseline IS a manifest; draining IS batched packets).
3. **The optimal module-size band.** Context economics punish both extremes:
   13.4k-LOC monoliths cost 8–10k tokens to load before any edit, but 565
   one-per-command API param files force 4+ file coordination per change.
   Module size has an interior optimum set by working-set token cost — ADR
   0006 gates on sibling *count*; an AI-first convention gates on *token cost
   of the working set*. Candidate amendment to 0006 / input to ADR 0034 W2.
4. **Typed contract registries as a deliberate pattern.** ONYXKEYS/ROUTES are
   the highest-value retrieval artifact per token in the repo (the entire
   state + URL surface learnable from two files, type-enforced at use sites).
   Emerged accidentally (merge-conflict centralization); generalize: one typed
   registry per cross-cutting surface (events, flags, commands).
5. **Placement conventions must include granularity rules** or they
   manufacture omnibus modules. A folder convention without a module-size
   rule is an omnibus factory.

## AI-first deltas (what changes when agents write most code)

- **Unnecessary:** proposal competition, duplicate policing, etiquette docs,
  most onboarding prose — machinery for socializing strangers.
- **More important:** normative philosophy docs (advisory for humans;
  *executable context* for agents) and the structural guard layer.
- **Inverts:** ratchets (amnesty → work queue); reviewer checklists (memory
  aid → test spec — their own AI_ETIQUETTE concedes "if fully automatable,
  automate it for everyone"); decomposition cost (humans defer it; agents pay
  it for free → decomposition-by-default at write time, with an integral
  check rejecting placement into over-budget files).
- **Context architecture at 667k LOC: map, don't summarize.** Three tiers:
  always-loaded map (~300 lines) → retrievable atomic norms → **generated
  structural indexes** (the tier they're missing — no machine answer to
  "what owns reports?", so every agent session rediscovers the hairball and
  adds function #457 where the other 456 live; map-subsystem output is the
  missing tier).

## Candidate next actions

- Prototype the **structural seatbelt** (baseline file + ratchet check) as the
  GUARD-side complement of the sweep harness; the sweep manifest and the
  baseline are the same artifact at two moments.
- Fold the **module-size band** into ADR 0006/0034 thinking (granularity rules
  as part of placement conventions).
- Ledger intakes: structural-seatbelt, baseline-as-work-queue,
  module-size-band, contract-registry pattern, generated-structural-index tier.
- The sweep ADR now has its full evidence set: Hermes (throughput),
  Daedalus (precision/judgment), Atlas (scale + the measured
  precision data + this lessons set).
