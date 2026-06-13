# Implementation — /prevent-regression repair (Stage 4)

> **Limitation.** Implemented INLINE by the campaign orchestrator (spend
> constraint) — the spec author and implementer are the same context.
> Compensating control: Stage 5 verification is a fresh-context
> sub-agent told to refute.

Edits to `.claude/skills/prevent-regression/SKILL.md` only; no script
changes, so no script tests were required.

- **C1** — inserted `## How success is judged` (5 bullets) after the
  intro's "The human reviews and executes." paragraph. Every bullet
  restates a gate already mandated in the body (Phase 3 verify_rule RCs,
  Phase 6 historical fire + clean HEAD, Phase 3 fixture doctrine,
  Phase 3b test-only branch). Wording for bullet 1 instantiates the
  class-sweeps gate line verbatim-in-spirit ("emitted, never installed
  unilaterally").
- **C2a** — inserted the staging-contract paragraph immediately before
  the verdict block (proposal-dir staging at repo-relative destination
  paths; wiring as ready-to-apply diff blocks in proposal.md; Phase
  Pre/Post read against staged paths). Constraint phrased "no guard
  artifact or wiring edit lands in the working tree" per the scout's
  telemetry-append carve-out.
- **C2b** — Step 7 final bullet now reads "human reviews the proposal,
  installs the staged artifacts and wiring diffs, and commits — or abort
  if verification failed."
- **C3** — "Three forms." → "Four forms."
- **C4a** — intro pointer list reframed: direct pointer to
  `_common/skill-conventions.md`; `knowledge/` named a host-overlay slot
  that ships empty. ("three knowledge files" framing removed.)
- **C4b** — Repository layout: phantom `(host-overlay specifics).md`
  entry removed; `knowledge/` annotated as the empty host-overlay slot.
- **C5** — JS exemplar sentence now marks `no_site_endpoint_sprawl.py`
  as the source host's exemplar, not shipped here, with an explicit
  `<!-- host-adapter: ... -->` slot; the portable shape list is retained
  as normative.

Judgment calls:
- C1 bullet 4 says "the precision/recall gates a conformance harness
  re-runs by side-effect" — a pointer to the Bucket-A grading reality
  named in the spec's declared verdict; no harness path or manifest is
  named in the skill (spec constraint honored).
- Phases 2–5 Pre/Post lines were left textually untouched; the global
  staged-paths reading rule covers them (smallest edit; no renumbering).

Skill-local validate command: grepped the target's SKILL.md and scripts
for `--validate`/test invocations — **none found** (verify_rule.py is a
proposal-time gate, not a skill self-check). Ran the ecosystem-level
check instead: `.venv/bin/python scripts/skill_meta.py lint` →
"OK — 74 skills, 74 declaring new contract".

Not committed (campaign constraint).
