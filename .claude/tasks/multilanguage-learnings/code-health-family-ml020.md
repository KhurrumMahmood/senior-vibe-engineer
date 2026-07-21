# ML-020 code-health family learning packet

## Outcome

Adopt the bounded family pattern for this one read-only health journey. Five
paired GPT-5.6 Luna trials preserved every accepted outcome and source byte.
Compressed parallel execution reduced controlled prompt context by 78.84%,
reported aggregate tokens by 22.23%, and median end-to-end wall time by 52.68%
versus three full skills plus synthesis run serially. A fresh unseen host and
separate invalid-standards serial/parallel sentinels also passed.

The compact evidence is `.claude/tasks/ml020-code-health-results.json`; raw
per-call prompts, events, usage, artifacts, and checkpoints remain under the
gitignored `reports/ml020-code-health-run/` directory.

## Transferable rules

1. Compress shared invariants, not the evidence boundary. The 4,439-byte
   family core/member set retained read-only ownership, exclusion rules,
   partial/unsupported states, final-artifact authority, and no-clean-on-
   incomplete behavior from 41,912 bytes of full skill guides.
2. A family is a user journey, not a bag of vaguely related skills. This set
   has one outcome, fixed lane order, explicit host dependencies, at most three
   independent read-only members, and one synthesis owner. Individual skills
   remain directly invocable.
3. Parallelize only independent reads. The compressed serial condition cut
   context and tokens but only modestly changed median latency; concurrency is
   what produced the 52.68% wall-time improvement. Mutations and user decisions
   remain serial.
4. “One result” must mean one consolidated result, not one selected finding.
   The first synthesis preflight read all artifacts but chose only one finding.
   Making preservation of every actionable final-artifact finding explicit
   fixed the ambiguity without disclosing the hidden oracle.
5. Grade artifacts, not model prose. Each lane had to execute its exact copied
   tool, produce and read its final JSON, pass native checks, and preserve the
   non-report tree digest. The hidden oracle compared canonical projections and
   incomplete states; natural-language phrasing was free to vary.
6. Keep failure sentinels outside timed trials. Invalid standards had to make
   `/find-standard-gaps` incomplete in both serial and parallel conditions.
   Timing those fast failures would have made the latency median gameable.
7. Measure controlled context honestly. Prompt UTF-8 bytes are exact, while
   Codex system/tool context and OS read bytes are not exposed. Structured
   `turn.completed.usage` is the separate check against merely moving repeated
   context into tool reads.
8. Resumability is part of model evaluation. Atomic per-call checkpoints made
   the 72-call gate recoverable without replaying successful calls. One
   pre-freeze synthesis correction and one interrupted call remain explicit
   rather than silently entering the gate. A post-run review found that a
   partially resumed condition compared against its then-current host rather
   than the frozen baseline; the harness now stops before any new model call
   when those digests differ.
9. Route the exact benchmark wording before spending evaluation calls. The
   completed live harness invoked the three lane tools directly, and review
   found that several natural prompts did not activate the product family.
   All five now route in product tests, and future benchmark preparation
   freezes a route projection for every timed and validation prompt.
10. Carry routing exclusions through execution. The first launcher rebuilt its
    lanes from filesystem inputs and could therefore run a host-disabled skill.
    The launcher now applies the same host active/inactive contract, while both
    router and launcher reject standards sets without a minimally valid,
    compilable `ast` or `grep` detector.

## Limits and next reuse gate

This result supports one family manifest, concise contracts, router sidecar,
and family-local launcher. It does not justify a universal DAG, shared context
cache, autonomous mutation coordinator, or immediate compression of all 76
skills. The production launcher is 551 lines and the benchmark harness is 931
lines; before extracting shared coordination, prove a second family has the
same execution invariants and that reuse reduces total maintained code.

For later language/framework expansion, reuse the family contract only when
all members already have honest support on that host. Route unsupported or
inactive members to explicit skips; never let family selection inflate an
individual skill's language claim.
