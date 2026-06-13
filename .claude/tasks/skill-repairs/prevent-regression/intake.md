# /repair-skill campaign — prevent-regression — Stage 0 intake

Date: 2026-06-12. Target: `.claude/skills/prevent-regression/` (SKILL.md
419 lines + `agents/rule-designer.md` + `scripts/{generate_rule,verify_rule}.py`
+ empty `knowledge/`). A prior repair attempt died before producing any
artifact; this campaign starts from Stage 0.

## Evidence of execution-time failure

1. **Class-1 hit — missing `## How success is judged` block.**
   `.claude/tasks/skill-repairs/class-sweeps-spec.md` (Class 1 hit table,
   prevent-regression row, citation SKILL.md:191): the skill is a
   multi-phase pipeline (Phases 1–6 + Step 7) with no declared-verdict
   block. Spec-gate wording to instantiate: "Verdict: guard artifact +
   verification recipe emitted; never installed unilaterally."
2. **Bucket-A status.** `.claude/tasks/ecosystem-review/02b-behavioral-conformance.md`
   classifies prevent-regression as the sole Bucket-A skill: its output is
   machine-gradeable by the conformance-by-side-effect harness
   (`scripts/skill_comply/`, checks C1–C9). The skill's output contract must
   therefore stay conformant with what the scorer grades (staged guard
   artifacts; verify_rule pass; historical-fire; bounded incidental firing;
   recall on sibling variants).

## Pre-repair freeze

`mkdir -p /tmp/skill-repairs-old && cp -R .claude/skills/prevent-regression
/tmp/skill-repairs-old/prevent-regression` — done; probes read the old
condition from there.

## Scale gate

By the loop's own gate this skill is execution-heavy (multi-phase, emits
script artifacts), which points at Full loop. This campaign runs a
**task-scaled loop**: Stages 1–2 inline (no sub-agent fan-out — spend
constraint; shared-context limitation recorded in each artifact), Stages
3–5 per the loop (Stage 5 verifier dispatched as a fresh-context
sub-agent), one blind haiku probe pair at the headline defect site
(Stage 6), and a **machine-check lane** standing in for the Stage 7
dogfood: one guard proposal produced by following the repaired SKILL.md
against the harness's seeded fixture, scored by
`scripts/skill_comply/score_conformance.py`. The harness is owned by a
parallel agent: read/run only, never edited; baseline
`scripts/skill_comply/validate.py` = OVERALL PASS (6 fixtures) confirmed
before any work.

Findings honesty: Stage 1+2 surfaced 1 headline (class-1) + 1 moderate
(write-site contradiction) + 3 minor drift items — more than a pure
"≤2 minor" LIGHT declaration, fewer than ≥3 high-severity. Scaled loop
as above, no inflation, no shrinkage.

## Constraints

- Do not commit (task constraint; overrides the loop's per-unit commits).
- Campaign files use repo-relative or `~`/`/tmp` paths; the source host is
  referred to only as "host-a".
- `scripts/skill_comply/` is read/run-only for this campaign.
