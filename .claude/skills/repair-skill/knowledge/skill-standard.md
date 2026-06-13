# The skill activation standard

What separates a skill an executor *follows* from dry prose it may or
may not follow. Derived from measured repair campaigns (lift probes at
haiku tier, dogfoods, text-alone reviews): every element below moved
behavior when added and its absence correlated with execution failure.
A skill can be defect-free prose and still be below standard — that is
itself repair-loop intake evidence; no incident is required.

## Elements

1. **Declared verdict.** A "How success is judged" block near the top
   naming the run's concrete gates (real artifacts, handoffs, status
   transitions, read-only constraints). Executors write toward declared
   gates; undeclared gates are reconstructed wrong or not at all.
2. **Artifact-truth gates.** Wherever the skill asserts something
   happened, it must demand the pasted output (test run, probe, hit
   count, exit code), not a claim. "Grade only by artifacts and
   re-runnable verifiers, never by run claims."
3. **Decision-point mandates.** Rules placed in the stage where they
   are consumed, phrased imperatively, naming their instrument and
   consumer. Aspirational notes and mandates diffused in a knowledge
   corpus do not reach weak executors (measured: +1.3/3 vs +0.3/3).
4. **Executable-as-written contracts.** Every command, path, flag, and
   referenced file works verbatim from the text alone — script
   invocations match the real argparse surface; a fresh executor needs
   no session context. (Text-alone review is the cheap detector.)
5. **Declared-verdict dispatch.** Every sub-agent dispatch tells the
   sub-agent how its output will be judged, and blind probes never
   reveal the condition under test.
6. **Load-bearing or deleted.** Every mandated step has a consumer the
   text can name. Ceremony invites skipping — and teaches executors
   that mandates are optional.
7. **Honest failure paths.** What to do when a step cannot run (state
   which and why; never simulate, never fabricate a transcript), and a
   "When things go sideways" table for the predictable failures.
8. **Replay case.** Material revisions carry evidence a future run can
   be checked against (campaign record, conformance fixture, probe
   protocol) — loop-generated updates without replay cases drift.

## Exemplars (repaired skills — copy the *shape*, instantiate the content)

Each element has a measured in-tree instance. Sweep/uplift agents:
read the exemplar before writing, then instantiate with the target
skill's own artifacts — a transplanted block with foreign nouns is the
boilerplate failure the citation-table check exists to catch.

1. Declared verdict — `repair-skill/SKILL.md` ("How success is
   judged", gate-per-instrument) and the inline-bold variant at the
   top of `refactor-subsystem/SKILL.md`; `prevent-regression/SKILL.md`
   shows one with machine-checkable gates (BAD_RC/GOOD_RC pasted).
2. Artifact-truth gates — `diagnose/SKILL.md` (root cause requires the
   confirming probe's exact command and output; `evidence_gate.py
   check` exits 0 and its summary line is pasted); `repair-skill`
   Stage 6 (verbatim transcripts are the SOLE judging input) and
   Stage 8 (detector output pasted as hit counts).
3. Decision-point mandates — `repair-skill` Stage 6 (the probe-harness
   contract sits exactly where the dispatch happens);
   `refactor-subsystem` resume step (belief re-arm fused into the
   scope restatement, not a separate aspirational note).
4. Executable-as-written — `repair-skill` Stage 0 freeze and Stage 7
   acquisition (exact commands, verbatim-runnable); proven by its
   text-alone review cycle (NO → 6 fixes → YES, see
   `.claude/tasks/skill-repairs/repair-skill-text-alone-review.md`).
5. Declared-verdict dispatch — `repair-skill` Stage 6: the sub-agent
   is told "your output will be judged on whether it matches what the
   skill actually mandates"; blind = no mention of repair, diff, or
   the other condition.
6. Load-bearing or deleted — the Class-2 fixes in
   `.claude/tasks/skill-repairs/class-sweeps-spec.md` (e.g.
   `audit-decisions` raw-drift.json: false consumer claim corrected
   to "debug artifact, no downstream consumer yet").
7. Honest failure paths — `repair-skill` Stage 7 ("never simulate a
   dogfood") and its sideways table; `diagnose` (reproduction.md
   records why no repro was possible and the run stops).
8. Replay case — the campaign records under
   `.claude/tasks/skill-repairs/<skill>/` (prevent-regression's is the
   fullest: intake → … → machine-check → lift-report → closeout);
   machine form: skill-comply C4 historical-fire.

## Using this file

- **Triage:** a skill missing elements is BELOW-STANDARD even with
  zero prose defects; route to /repair-skill (standards-uplift intake)
  or a class sweep when the gap is uniform across the catalog.
- **Class sweeps first.** Most elements are class-shaped: define the
  cheapest detector per element, sweep the catalog once, batch-fix —
  per-skill loops are for idiosyncratic defects and doctrine-bearing
  or execution-heavy skills.
- **Birth:** /plan-skill intakes and (when built) starter templates
  must satisfy every element from the first draft.
- **Machine checks:** skill-comply fixtures/oracles are the executable
  form of elements 2, 4, and 6; prefer extending them over re-arguing
  conformance in prose.
