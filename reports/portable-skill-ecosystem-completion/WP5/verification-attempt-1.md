# WP5 final verification attempt 1

Date: 2026-07-16
Verifier: `/root/wp5_final_ac_verify`
Model: Codex based on GPT-5; exact variant and effort were not exposed
Revision: `f60dbb140ecc672933d4330218d0ef757f353359`
Tree: `6d215180e4ae4c3ad3c4538982e52fddc8f393ea`
Verdict: **FAIL — do not mark WP5 verified**

## Criterion verdicts

| Criterion | Verdict | Result |
|---|---|---|
| AC-5.1 | PASS | Product package, schemas, stable identity, public help, and prototype isolation passed. |
| AC-5.2 | PASS | Five native tools plus Python/TypeScript parser members retained native and raw provenance. |
| AC-5.3 | PASS | All declared provider failure classes and clean-zero versus failed-empty behavior passed. |
| AC-5.4 | FAIL | The controlling public command block omitted required tool identities and parser trust roots, referenced a nonexistent judgment fixture, and scanned before/after in incompatible workspace roots. |
| AC-5.5 | PASS | Judgment, digest, consumers, packets, and harness-owned rescan/delta gates passed. |
| AC-5.6 | PASS | The required five-host live boundary passed with no skips and ADR 0036 names product paths. |
| AC-5.7 | PASS | Network/model denial, judgment gates, bounds, and harness-bypass rejection passed. |

## Recomputed evidence

- Full suite with live and browser skips forbidden: 851 passed, 0 skipped.
- Controlling focused suite: 79 passed.
- Parser/fact suite: 89 passed; complexity smoke passed.
- Broad WP5 focus: 268 passed; five live tests were run separately.
- Required live boundary: 11 passed, 17 deselected, 0 skipped.
- Renderer/browser: 4 passed, 0 skipped.
- WP4 entry gate: 65 passed plus live Darwin and cross-platform replay.
- Ruff, capability consumers, 76/76 skill metadata, 34 decisions and links,
  seven plans, five spec audits, and strict inventory were clean.
- A verifier-constructed same-root public replay succeeded with mixed before=6,
  after=0, six fixed IDs, no new/persisting IDs, and six actionable judgments.
- The controlling documented command exits were help=0, both scans=2, diff=3,
  and digest=3.

## Blocking findings and disposition

1. P1: the exact public command proof was stale and incompatible with the
   trusted parser workspace model.
2. P1: the master tracker credited AR-1–AR-12 while the successor spec left all
   twelve boxes unchecked.

Both findings were repaired at descendant `5f99d39`: the spec now constructs
one temporary Git host, passes all explicit native tool identities and trust
roots, imports checked outcomes, and runs public scan, judgment, digest, diff,
and ratchet. The live test executes the same public before/after boundary for
all five hosts, and spec coverage reports 28/28 with zero lag. This report does
not confer acceptance credit; a new fresh-context verifier is required.
