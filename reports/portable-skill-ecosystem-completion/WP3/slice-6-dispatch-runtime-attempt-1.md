# WP3 Slice 6 dispatch-runtime verification attempt 1

Date: 2026-07-16
Verifier: `/root/wp3_im14_trust_bundle/im15_lifecycle_lane/dispatch_runtime_review`
Model: GPT-5; exact variant and effort were not exposed
Revision: `0bd83d13684924299c5504709360c95741368138`
Tree: `1d22dff1c640ad422f5db18f0f8ac9149439013a`
Workspace: clean isolated worktree

## Verdict

- Dispatch-runtime slice: **FAIL**
- Findings: 0 P0, 5 P1
- Full IM-14: **OPEN**

## Findings

1. Attempt-two authorization was not bound to the exact recorded result hash.
   A forged failed result could replace a real success, and an ordinary next
   pack could follow an `unknown` side-effect result.
2. The caller selected `state_root`, so two state roots bypassed the claimed
   project-wide lock.
3. Callers minted executor capability/accounting booleans and a self-hash;
   neither the surface declaration nor actual accounting was trust-bound.
4. Invalid/oversize worker output raised and blocked instead of producing the
   required conservative schema-valid failed result.
5. `start_workflow()` persisted an unchecked identifier that poisoned the
   canonical journal on restart.

The checked-in focused suite passed 20 tests, but disposable attacks reproduced
all five defects. Native worker launchers, five-surface execution, lifecycle,
and artifact retention were explicitly outside this attempt and receive no
credit. Repair revision `d451522ce649c507353c51a872e6fc732dc59576`
requires a new no-context verdict before integration.
