# WP3 Slice 5 evidence — IM-10 / IM-12

Evidence date: 2026-07-16.

Exact reviewed main revision:
`420e9f9e0473035917251804bd18f73b61ab3f0f`, tree
`c183a81d69d3a893bfc03cd7d6f6e2bf54516271`. The fresh verifier used an
isolated detached clone, made no tracked edits, and finished with an empty Git
status. Its actual model identity was GPT-5 Codex.

The verified integrated commits are `c9863fe`, `653d51e`, `ef4a066`,
`013a457`, `8bf1d39`, and `420e9f9`. The conflict resolution removed only
future installer/dispatcher commands whose files do not yet exist. Those
surfaces remain in unchecked IM-13 through IM-18 rather than appearing in the
current acceptance-command block.

## Delivered boundary

- Exactly 16 distribution-ready skills project as complete, hashed procedure
  trees across Claude Code, Codex, Augment, Cursor, and Gemini formats.
- The reviewed bundle includes every load-bearing skill file, contract/index
  row, and reference. Untracked or ignored load-bearing inputs, committed
  caches, path traversal, remap/manifest collisions, alias collisions/cycles/
  stale targets, incomplete catalog sets, malformed inventory, and tampered
  runtime evidence all fail closed.
- Canonical invocation names remain unchanged; no aliases are currently
  required. The alias mechanism is nevertheless structurally and
  adversarially validated.
- Runtime evidence is content-bound to the exact revision, tree, bundle,
  inventory, fixture, command, and output hashes. Native non-model discovery
  verifies Claude Code 2.1.211, Codex 0.144.1, and Gemini 0.45.0. Augment and
  Cursor are recorded unavailable without fabricated probes.
- ADR 0042 remained byte-identical (`75119261175d10f3f725ddfb8f4b77dac514dc85`)
  across integration. Router-only remains the default and full discovery an
  explicit opt-in; Slice 5 does not claim the unchecked lifecycle/dispatcher.

## Independent verdict

```text
IM-10: PASS
IM-12: PASS
IM-11: OPEN
AC-3.2: OPEN
P0/P1 findings: none

focused WP3 suite: 114 passed
full suite: 793 passed, 11 skipped, 804 collected
surface matrix: 5 surfaces / 16 ready skills, PASS
strict intent drift: 76 skills / 76 contracts / 0 findings
core leakage: 16 migrated skills clean
metadata: 76/76 clean
decisions: 34 clean
plans: 7 clean
spec inventory: 44/44 symbols clean
Ruff: clean
```

The 11 full-suite skips are unavailable optional/live environments and do not
stand in for IM-11. IM-11 and AC-3.2 remain open until exact-version Augment
and Cursor runtime discovery evidence exists. This report makes no installer,
transactional lifecycle, dispatch, or complete WP3 acceptance claim.
