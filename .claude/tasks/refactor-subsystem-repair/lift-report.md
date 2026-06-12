# Lift report — /refactor-subsystem repair (PARTIAL: old grid locked)

Protocol: lift-test-protocol.md (criteria declared before results).
This section locks the OLD-condition judgments before any
NEW-condition probe exists, so the comparison cannot drift.

## OLD condition (pre-repair skill, frozen at git HEAD)

| Probe | Site | Score (declared scale) | Notes |
|---|---|---|---|
| P1 | archaeology (absent content) | NOTICED-GAP | Reconstructed all recoverable detail correctly; flagged missing knowledge file; called regex tail + schema "unrecoverable" instead of inventing. CORRECT-FROM-TEXT impossible by construction — content absent. |
| P2 | decomposition coverage | COVERAGE-PROOF (top) | Self-generalized R36 from learnings.md to batch level; declared entry unapprovable without grep proof into destination module. |
| P3 | swarm threshold | NOTICED-CONTRADICTION (top) | Followed table (inline at 3); spontaneously flagged pseudo-code contradiction as drift. |
| P4 | mid-run resume | 3/5 | Recovered: phase inference, sign-off reload, cleanliness guard. Missed: phase knowledge-file re-read, belief re-arm. |

## Control cell (declared-verdict sentence removed)

| Probe | Score | Delta vs verdict version |
|---|---|---|
| P1-ctrl (clean isolation) | NOTICED-GAP | None — equal or slightly richer detail. |
| P4-ctrl | 3/5, same two misses | None. |

**Control conclusion:** at n=1/cell, strong model, clean single-task
context, the declared-verdict sentence produced NO measurable
behavior change. C9's case is NOT supported by these probes; it
rests on (untested here) load conditions, completion pressure, and
weaker executors — the regime where this session's own in-load
adherence failure (track-idea Stage 3, ~25/25 skips WITH text in
context) actually occurred. Do not cite this experiment as evidence
for the preamble until an under-load or weak-model cell exists.

## Standing observations (pre-NEW)

1. **Repair fixes absence; strength fixes ambiguity.** Where content
   existed but was scattered/contradictory (P2, P3), the strong
   executor self-repaired by reading the whole corpus. Where content
   was absent (P1 regex/schema, P4 frame steps), no amount of
   diligence could recover it — that is where the repair can move
   scores: P1 NOTICED-GAP → CORRECT-FROM-TEXT, P4 3/5 → 5/5.
2. **Artifacts recover position; prose obligations get dropped.**
   Both P4 runs recovered every artifact-backed step and missed both
   prose-only steps. Same law as the load-bearing rule, at resume
   time.
3. **Probe adherence is an upper bound.** Single-task, diligence-
   primed, fresh-context agents out-adhere real mid-session
   executors. The review's failure predictions target the in-load
   regime these probes do not reach; the adherence harness
   (skill-runtime-adherence-harness) is the instrument for that
   regime.

## Haiku-OLD cell (locked before any NEW result; same prompts, model=haiku)

| Probe | Score | vs Fable-OLD |
|---|---|---|
| P1 | **FABRICATED** — invented a 15-term regex extension presented as exact mandate, fabricated command lines, invented "Phase 2.2"/"Bucket 4"; never flagged the missing knowledge file | Fable: NOTICED-GAP |
| P2 | **SUITE-NAME-ONLY** — accepted green `tests.test_email` with an asserted (unverified) coverage claim; no R36 generalization | Fable: COVERAGE-PROOF |
| P3 | INLINE (correct), contradiction NOT noticed | Fable: NOTICED-CONTRADICTION |
| P4 | 3/5 — same two misses (knowledge-file re-read, belief re-arm) | Fable: 3/5 identical |

**Tier conclusion (old skill):** the review's failure predictions are
TRUE at Haiku tier and false at Fable tier in clean conditions. The
old skill is safe only when the executor is strong enough to audit
it: strength fixes ambiguity (P2/P3) and converts fabrication into
gap-noticing (P1). The frame-resume misses are tier-INDEPENDENT —
prose-only obligations drop at both tiers. Repair lift predictions:
Haiku-NEW should move P1 (FABRICATED → recipe-from-text with honest
host-adapter slot), P2 (SUITE-NAME-ONLY → grep mandate is now in the
plan-item text), P4 (3/5 → 5/5, steps are now enumerated); Fable-NEW
should move P1 and P4 only.

## NEW condition

Repair committed 0eab687 after independent verifier PASS (all
F1–F9 + C10 RESOLVED, no-invention audit clean). Same prompts,
frozen post-repair copies at /tmp/refactor-skill-new.

| Site | Fable old → new | Haiku old → new |
|---|---|---|
| P1 archaeology | NOTICED-GAP → **CORRECT-FROM-TEXT** | **FABRICATED → CORRECT-FROM-TEXT** |
| P2 coverage | COVERAGE-PROOF → COVERAGE-PROOF (richer: anticipated the empty-grep trap + R31 retargeting) | **SUITE-NAME-ONLY → COVERAGE-PROOF** (3 mandatory greps, reviewer checklist) |
| P3 threshold | NOTICED-CONTRADICTION → INLINE-correct (trap no longer exists to notice) | INLINE-correct → INLINE-correct |
| P4 resume | 3/5 → **5/5** (incl. knowledge-file re-read + belief re-arm) | 3/5 → **4/5** (incl. knowledge-file re-read; belief re-arm still absent) |

## Verdict

Predictions from the locked OLD grid: confirmed in full, zero
regressions.

1. **Lift concentrates where content was absent, and is largest at
   the weakest tier.** P1 at Haiku tier moved the full scale —
   confident fabrication of a 15-term regex became faithful
   reproduction of the real recipe with an honest host-adapter slot.
2. **Mandating in-phase beats relying on corpus diffusion.** P2 at
   Haiku tier moved from the review's predicted silent-failure mode
   to full coverage-proof once the R36 check lived in the plan-item
   text instead of only in learnings.md. Fable, which self-repaired
   on OLD, got *richer* rather than just compliant.
3. **The strong-tier value is consistency + depth, not capability.**
   Fable's P2/P3 were already correct; NEW made them cheaper to get
   right (no corpus-wide self-repair needed) and removed the latent
   trap entirely.
4. **Resume protocol works at both tiers**; the one residual gap
   (Haiku skips the belief re-arm step) suggests that step should be
   fused into the sign-off restatement rather than listed separately.
5. **Declared-verdict sentence: no measurable effect** in clean
   conditions at Fable tier (control cell); untested under load and
   at weak tier — do not cite this experiment for it either way.

Bounds: n=1 per cell; clean single-task contexts (upper bound on
real adherence); scenario probes authored by the repairer. The
real-complexity check is the host-a dogfood (Phase 0–1 on the
pre-cleanup core/tasks.py), reported below.

## Real-complexity check: host-a dogfood

Fresh agent, post-repair skill, Phase 0–1 on host-a's pre-cleanup
`core/tasks.py` (4,782 LOC, 15 commits) in a detached-HEAD clone with
no convention docs, no venv, commits forbidden. Full log:
`dogfood-log.md`; fixes: `dogfood-fixes.md`.

**Result: Phase 1.5 gate PASSED on artifacts; verdict on the text NO.**
Coverage summed exactly (4,782/4,782), 27/27 scout files, 93 findings,
141 extracted-behavior candidates, 5 archaeology LR-T candidates, zero
repo mutations. But 11 frictions, 3 of which (F8 unexecutable scout
dispatch, F6 orphan-concept conflation, F4 absent-convention-docs
fallback) force undocumented judgment calls on any real run of this
shape — two would corrupt or stall a literal executor.

**What this adds to the verdict above:**

6. **The three instruments are complementary, and none substitutes
   for another.** The independent verifier PASSed the same text the
   dogfood failed: the verifier checks internal consistency
   (pointers resolve, counts match, nothing invented), the probes
   check behavior at known defect sites, and only execution against
   a real host exposes the unexecutable-against-reality class
   (read-only agent types, chunker output quirks, hosts missing the
   origin project's docs). A repair is not done at verifier PASS;
   it is done when the skill has survived a host it wasn't written
   on.
7. **The dogfood log IS the replay case** the meta-loop doctrine
   demands: what failed (11 cited frictions), what changed (10
   same-day fixes, round 2), what a future run should now pass (the
   identical scenario with zero forced improvisations). Residual:
   F10 (inventory-check counts only `@shared_task` symbols) —
   script change, ledgered.
