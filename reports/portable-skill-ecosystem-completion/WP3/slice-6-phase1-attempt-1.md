# WP3 Slice 6 phase-1 verification attempt 1

Date: 2026-07-16
Verifier: `/root/wp3_im13_im14_phase1_verify`
Model: GPT-5 Codex; exact variant and effort were not exposed
Revision: `7c1306ae13bd5bbea566bb0a2b597a10d88a819f`
Tree: `08bf43f41df680a33d71200087ab663ada203e2c`
Workspace: clean detached clone

## Verdict

- IM-13: **PASS**
- IM-14 phase 1: **FAIL**
- Full IM-14: **OPEN**
- Findings: 0 P0, 4 P1, 1 P2

## IM-13 evidence

- The exact three-portfolio snapshot rebuilt byte-for-byte at SHA-256
  `7767cb4ed3576651844c60bb351c6aaebd8371e073dc60f23f7362c37cf456d9`.
- Core-only and TypeScript/React each contain 16 core procedures, select only
  core, and have zero framework-native hits; TypeScript makes no WP6 claim.
- Django preserves all 76 AR-1 names at set hash
  `e7ed28551e071089e2f11c76713f1c1ec7c2d342107109a22630c6f9828ff138`
  and selects exactly the `django` and `python` non-core bindings.
- All rows bind source path/hash, rendered hash, layer, bindings, and aliases.
- Across five surfaces × three portfolios, router-only is exactly two names,
  initial named activation exactly three, and full discovery exactly
  16/16/76 while preserving host-owned discovery separately.
- Production aliases are empty and both alias states use the exact typed
  unavailable record. Fixture-only `plan-feature-v1` produces the required
  named/cumulative sets without entering any release artifact.
- Core leakage and 76/76 strict skill metadata checks passed.

## IM-14 phase-1 blockers

1. The production semantic validator assumes rather than executes the
   structural Draft 2020-12 gate, so unknown fields can pass it.
2. Attempt two can reuse the failed dispatch ID.
3. Declared procedure, binding, and task digests are not recomputed from their
   inline bytes/canonical values.
4. A generated manifest path is not bound to its selected surface identity.

The verifier also found that the focused command omitted the three new suites;
descendant `f0f16dd` repairs that P2. The four P1s require implementation and a
new fresh-context phase-1 verifier. No IM-14 credit is granted by this report.

## Execution evidence

- Combined phase-1 suite: 130 passed.
- Ruff: clean.
- Spec coverage: only IM-13 and IM-14 were implementation-ahead, with zero lag
  or orphan references.
- Strict inventory: `distribution_probe.py` 44/44 and contract-schema tests
  35/35.
- Five specs, 34 decisions and links, and seven plans were clean.
