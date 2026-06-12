# Lift-test protocol — does the repair change executor behavior?

A/B behavioral probes at four repaired defect sites. Condition OLD =
pre-repair skill (frozen at /tmp/refactor-skill-old from git HEAD);
condition NEW = post-repair skill (frozen copy taken after the
verifier passes the repair). Same probe prompts, same model tier,
fresh agents, no shared context, blind to this repair effort and to
each other. Probes instruct: "your output will be judged on whether
it matches what the skill actually mandates" — declared verdict,
neutral about gaps (we measure whether the TEXT causes noticing, so
probes are NOT primed to hunt for missing content).

Judging criteria (declared before any probe returns):

**P1 — archaeology recipe (F1 site).** Scenario: Phase 1.4 on a
1,200-LOC file with 73 commits; asked for exact commands, filter,
recording format. OLD predicted failure: fabricates a subject-word
regex and report format confidently, citing knowledge/ it cannot have
read. NEW pass: reproduces the operations.md recipe (thresholds,
full filter or its declared host-adapter bound, schema, archaeology
tag), or explicitly stops at a declared gap. Score: FABRICATED /
NOTICED-GAP / CORRECT-FROM-TEXT.

**P2 — decomposition coverage proof (F2 site).** Scenario: write the
Phase 3 plan item 7 per-batch test strategy for a batch moving
tasks/email_dispatch.py → services/dispatch/, with tests.test_email
green. OLD predicted: names the suite, done. NEW pass: includes grep
evidence the named suite imports/patches the DESTINATION module, or
refuses to accept green without a coverage path (cites R36 logic).
Score: SUITE-NAME-ONLY / COVERAGE-PROOF.

**P3 — swarm threshold (F5 site).** Scenario: Phase 5.3.5, exactly 3
instances of one naming violation found; swarm or inline, cite the
rule. OLD text is self-contradictory (table: 1–4 inline; pseudo-code:
count<=10 → swarm). Record which rule the executor follows and
whether it notices the contradiction. NEW pass: inline, citing the
consistent threshold. Score: SWARM / INLINE / NOTICED-CONTRADICTION.

**P4 — mid-run resume (F7 site).** Scenario: fresh session, "resume
the refactor for spec extraction-pipeline mid-run"; first five
actions. OLD predicted: improvised resume (maybe sensible, but
unanchored — no sign-off reload, no playbook re-read). NEW pass: the
Resuming-mid-refactor steps in order (coverage+reports to infer
phase, re-read phase knowledge file, reload sign-off scope, re-arm
beliefs, cleanliness guard). Score: count of the five mandated
actions present (0–5).

**Control cell (added after OLD results, before judging them as
final — declared before its results exist):** OLD-P1-ctrl and
OLD-P4-ctrl re-run the two headroom sites with the IDENTICAL prompt
minus the declared-verdict sentence ("your output will be judged on
whether it matches what the skill actually mandates"). Rationale: all
four OLD probes contained that sentence and all four executors
audited rather than improvised — the probe design may have been
measuring old-skill+declared-verdict, not old-skill. Scoring is
unchanged (P1: FABRICATED / NOTICED-GAP / CORRECT-FROM-TEXT; P4:
0–5 mandated actions). If the ctrl probes score materially lower,
that is direct evidence for the C9 preamble's mechanism,
independent of all other repairs.

Lift = per-probe movement toward pass states. Honest bounds: n=1 per
cell, single model tier, probe scenarios authored by the repairer
(me) — a probe the repair trivially satisfies is possible; mitigated
by P3/P4 measuring behavior shape rather than content recall.
Results: lift-probes/{old,new}-P{1..4}.md, judged in
lift-report.md.
