# WP0 pre-retirement inheritance review attempt 2

- Verifier: `/root/wp0_preretirement_recheck` (Codex GPT-5; exact variant
  unavailable)
- Revision: `3c8475044af3acab6eb7a8be77a31028eacdf507`
- Workspace: clean
- Predecessor state: `scoped`, retirement pending
- Verdict: **FAIL — DO NOT RETIRE**

## Verdict summary

| Item | Verdict | Reason |
|---|---|---|
| W1 | FAIL | Actual WP3 moves could land before the generalized ADR 0024/0028 criteria; ADR 0024's `avoid:`/two-band/prose proof was partial. |
| W2 | PASS | Named example/default relocation, frontmatter truth, and literal core leakage rules were exact. |
| W3 | PASS | Exemplar-first sequencing and all five mandatory families were exact. |
| W4 | PASS | AC-2.6 was complete. |
| W5 | FAIL | The successor closed ADR 0003 before 0026–0030, contrary to the predecessor's binding order. |
| W6 | PASS | Distribution/onboarding obligations were complete. |
| Success 1 | PASS | Router, perimeter, and non-Django install behavior were exact. |
| Success 2 | PASS | Literal no-Django/Celery core-body rule and lint were exact. |
| Success 3 | PASS | Django exemplar oracle and round-trip were exact. |
| Success 4 | FAIL | No exact strict-reduction/no-regression comparison existed for the stated 0026–0031 + 0003 baseline. |
| Success 5 | PASS | Named starter and timed first value were exact. |
| Success 6 | PASS | All four named commands and dangling-reference checks were exact. |

Active inbound references passed and the predecessor remained correctly
unretired. The required repair is now encoded in AC-3.7, the expanded AC-7.2,
the binding W5 order, ordered AC-7.6/AC-7.7/AC-8.8/AC-8.9 closure, and the
baseline-relative AC-8.10 regression gate. A later reviewer must independently
confirm those changes before retirement.
