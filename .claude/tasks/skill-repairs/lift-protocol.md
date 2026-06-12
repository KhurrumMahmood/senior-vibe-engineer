# Scaled lift protocol — diagnose / scope-feature / which-shape repairs

Scaled per the refactor-subsystem finding: lift concentrates at the
weakest tier on absent-content sites, so probe ONLY model=haiku, one
probe at each skill's headline defect site, old (frozen at
/tmp/skill-repairs-old/) vs new (working tree). Fresh agents, blind to
the repair, declared-verdict sentence included in both conditions
(its null effect was established in the prior control cell). Criteria
locked before any probe returns.

## P-D — /diagnose F1+F2 site (root-cause acceptance)

Scenario: mid-Phase-4; H1's probe produced output consistent with H1;
H2–H4 unprobed; executor asked to write root-cause.md and move to the
fix. Score:
- ACCEPTS-NARRATIVE: writes a prose root cause, proceeds to Phase 5.
- PARTIAL-BAR: requires the probe transcript OR addresses competing
  hypotheses, not both.
- FULL-BAR: requires (a) pasted probe command+output in
  root-cause.md AND (b) elimination/downgrade of each remaining
  hypothesis (or records them as residual uncertainty) before any fix.
Prediction: old=ACCEPTS-NARRATIVE (no proof standard exists in text);
new=FULL-BAR (C1+C2 are in-phase mandates).

## P-S — /scope-feature F1 site (advancing status)

Scenario: §1–2 drafted after a good scoping conversation; executor
asked "what remains before you advance the plan to scoped?" Score:
- FORMAT-ONLY: runs plans.py audit / checks sections, advances.
- PARTIAL-BAR: mentions contract quality but no mechanical test.
- FULL-BAR: generates three hypothetical borderline changes, verifies
  §1 adjudicates each without asking the user, tightens on ambiguity —
  before Stage 5.
Prediction: old=FORMAT-ONLY (audit is the only stated gate);
new=FULL-BAR (Stage 4.5 exists in-phase).

## P-W — /which-shape F1+F6 site (cue-free prompt)

Scenario: route "help me with the thing we discussed" for a user; the
script returns Bug Fix / low / "fallback shape candidate". Score:
- CONFIDENT-ARBITRARY: presents Bug Fix as the recommendation.
- HEDGED: presents it with caveats but still as the single route.
- GATED: refuses single-shape presentation; offers top alternatives +
  one discriminating question; pastes script output lines.
Prediction: old=CONFIDENT-ARBITRARY or HEDGED; new=GATED.
(Run after the which-shape implementation verifies.)

Bounds: n=1/cell, scenario probes authored by the spec author,
clean-context upper bound — same caveats as the refactor-subsystem
grid. Judged in lift-report.md here.
