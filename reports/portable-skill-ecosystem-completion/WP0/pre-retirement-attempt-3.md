# WP0 pre-retirement inheritance review attempt 3

- Verifier: `/root/wp0_preretirement_final` (Codex GPT-5; exact variant
  unavailable)
- Revision: `3042c39`
- Workspace: clean
- Predecessor state: `scoped`, retirement pending
- Verdict: **FAIL — DO NOT RETIRE**

W1, W2, W3, Success 1–3, and Success 6 passed. The remaining findings were:

- W4 did not explicitly preserve the established `find-route-sprawl` clean
  exemplar or classify already-landed Class A work as a regression baseline.
- AC-3.7's early ADR 0028 safety gate was ambiguous with the formal W5 order,
  and an accepted-ADR escape could bypass that order without amending this plan.
- W6 did not literally require the three skills to run standalone or say that
  governance is optional.
- Success 5 did not explicitly forbid requiring the kernel document.
- The status-projection plan still named WP5/WP9 as ADR 0003's owner even
  though AC-8.9 had moved formal closure to WP8.

The repair adds a recorded Class A/route-sprawl oracle to AC-2.6; declares
AC-3.7 safety-only and removes the sequence escape; makes standalone,
governance-optional, and no-kernel onboarding objective; and corrects the
active owner. A later reviewer must independently issue the zero-unmapped
verdict.
