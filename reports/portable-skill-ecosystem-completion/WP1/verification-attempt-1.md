# WP1 fresh-context verification attempt 1

Verifier: `/root/wp1_fresh_verifier`, GPT-5. Revision:
`e20e521ab236ad08fa5706a4ed0e04ad9bce4320` (clean at start; required
pytest/Ruff commands appended only automatic test telemetry, whose full patch
and hashes were reported by the verifier and then removed by the coordinator).

Overall: **FAIL**.

| AC | Verdict | Finding |
|---|---|---|
| AC-1.1 | PASS | Versioned schema separates every required vocabulary and the future-language data-only test passed. |
| AC-1.2 | FAIL | Guard missed a dictionary-based hidden stack catalog assigned to an unrecognized name. |
| AC-1.3 | FAIL | Arbitrary evidence strings, an empty placeholder script, a false command, invalid digest, and imaginary platform could satisfy strict `any`/`scans` validation. |
| AC-1.4 | FAIL | Promotion trusted claimant-supplied truthy fields instead of validating fixture artifacts, tool ranges, commands, hashes, platform, and the scan target's support ceiling. |
| AC-1.5 | PASS | ADRs 0038–0042, decision gates, and the WP1 distribution-prototype boundary passed. |
| AC-1.6 | FAIL | Bare `verified` strings with no evidence satisfied the completion floor; claims were not bound to AC-1.4 evidence or pinned surface versions. |
| AC-1.7 | PASS | Fresh D3 rerun preserved the corpus hash, 1.0 precision/recall, budgets, and explicit unsupported candidates. |

Required corrections before re-verification:

1. Detect dictionary and arbitrarily named duplicate stack registries.
2. Resolve and validate executable evidence/provenance for `language:any` and
   every `scans:` target.
3. Make support evaluation derive fixture, version, platform, command, and
   evidence-hash validity from artifacts rather than booleans; enforce provider
   support ceilings.
4. Require completion-floor cells and agent surfaces to carry valid verified
   evidence, not labels alone.

The verifier reported no unsupported D3 or D1 claims beyond these four
gameable validation paths.
