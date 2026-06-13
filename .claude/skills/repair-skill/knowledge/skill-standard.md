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
