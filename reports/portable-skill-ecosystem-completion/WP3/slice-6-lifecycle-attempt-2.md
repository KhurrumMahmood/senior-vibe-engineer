# WP3 Slice 6 lifecycle verification attempt 2

Date: 2026-07-16
Verifier: `/root/lifecycle_64d66_qa`
Model: GPT-5 Codex; exact variant and effort were not exposed
Revision: `64d66dffd4f5ced3ebbf550fb6b06feab8712edd`
Tree: `0e76a6ce140b0bd42f5af0593e79a1c68d829670`
Workspace: clean isolated worktree

## Verdict

- Bounded lifecycle repair: **PASS**
- Findings: 0 P0, 0 P1
- Full IM-15 and native IM-16 matrix: **OPEN**
- Native runtime discovery: unavailable; no credit granted

## Verified boundary

All seven attempt-1 repair classes passed: lifecycle data is re-derived from
an externally rooted verified bundle; callers cannot inject an adapter;
unsupported native discovery is honest; migration preview derives from the
verified legacy table; recovery authenticates provenance before mutation;
rollback is repeat-stable; directory cleanup is limited to recorded ownership;
and update applicability/binding hashes are exact.

Coordinator review then reproduced an additional defect in the first repair:
a marker-only transaction directory without an active journal could be
recursively removed with unrelated bytes. Revision `64d66df` changed this to
fail closed without deletion and to block active recovery in the presence of
any unbound transaction. The verifier passed 16 lifecycle tests, 104 trust/
schema/table tests, and two independent byte-preservation probes. Legitimate
manifest-bound recovery still restores prior bytes and removes only its bound
transaction. Ruff, self-lint, plan/spec audits, and the exact 70/70 installer
symbol inventory passed.

Main-line integration through `682c3be` passed an expanded 188-test combined
lifecycle/dispatch/trust matrix plus Ruff, self-lint, plan audit, spec coverage,
and strict inventory. Exact-main re-verification is still required before any
larger IM-14/IM-15 credit.
