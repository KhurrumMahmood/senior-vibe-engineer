# skill-comply — recall axis (C9) + proposer-completeness oracle: verification report

_Date: 2026-06-12. Completes an interrupted task: the under-broad fixture and
`oracle_proposer_completeness.py` were on disk (uncommitted) from a prior
agent; this pass verified the oracle live, fixed one defect, and updated
DESIGN.md. All work uncommitted by instruction._

## Fixture verdict matrix (live run, `scripts/skill_comply/validate.py`)

| Fixture | Expected verdict | Expected consequential fails | Result |
|---|---|---|---|
| conformant    | pass | —         | VALIDATED |
| defective     | fail | C4 + C9   | VALIDATED |
| over-broad    | fail | C8        | VALIDATED |
| poisoned-good | fail | C3        | VALIDATED |
| wrong-name    | fail | C4 + C9   | VALIDATED |
| under-broad   | fail | **C9 only** | VALIDATED |

`OVERALL: PASS` — all six fixtures scored exactly as expected, including the
exact consequential-failure sets (the pre-existing five fixtures' verdicts are
unchanged apart from defective/wrong-name honestly picking up C9, asserted in
`validate.py` EXPECTATIONS).

## Oracle live runs (`scripts/skill_comply/oracle_proposer_completeness.py`)

Ground truth: fresh `seed_fixture.py` manifest, 3 `planted_instances`
(checkout-post-quantity, reports-self-request-page, reports-aliased-get-limit).

### Case 1 — complete proposal (all planted instances found) → exit 0

```
Proposer-completeness oracle — verdict: PASS
  planted instances : 3
  findings reported : 3
  recall            : 1.0  precision: 1.0
  FOUND   checkout-post-quantity  (finding F1)
  FOUND   reports-self-request-page  (finding F2)
  FOUND   reports-aliased-get-limit  (finding F3)
```

### Case 2 — miss (aliased-receiver instance dropped) → exit 1

```
Proposer-completeness oracle — verdict: FAIL
  planted instances : 3
  findings reported : 2
  recall            : 0.6667  precision: 1.0
  FOUND   checkout-post-quantity  (finding F1)
  FOUND   reports-self-request-page  (finding F2)
  MISSED  reports-aliased-get-limit
```

### Case 3 — false positive (phantom finding in benign decoy cart.py) → exit 1

```
Proposer-completeness oracle — verdict: FAIL
  planted instances : 3
  findings reported : 4
  recall            : 1.0  precision: 0.75
  FOUND   checkout-post-quantity  (finding F1)
  FOUND   reports-self-request-page  (finding F2)
  FOUND   reports-aliased-get-limit  (finding F3)
  FALSE+  finding F4 matches no planted instance
```

## Defect found & fixed

A non-integer `line` in findings.json escaped `_normalize_findings` as an
uncaught `ValueError` traceback with **exit 1** — colliding with the
documented "verdict fail" exit code (contract says malformed input = exit 2).
Fixed with a try/except in `_normalize_findings`; re-verified:

```
error: finding #1 has a non-integer 'line': 'abc'
exit=2
```

## Verification ladder

- `tests/test_skill_comply.py` — **4 passed** (six-fixture validate run,
  under-broad fails-only-C9, oracle happy path, oracle miss+false-positive).
- `scripts/skill_comply/validate.py` — OVERALL: PASS (six fixtures).
- `ruff check scripts/skill_comply/` — clean.

## Doc updates

- `scripts/skill_comply/DESIGN.md` — new Stage 3 section: C9 design
  (seed `reports.py` sibling forms, `recall_files`, C8-mirrored skip
  contract, tag-field hit counting), under-broad fixture + updated
  verdict-space table, `planted_instances` ground-truth contract
  (`_line_of`-computed lines, HEAD-live instances only), the oracle's full
  contract + live-verification results, and the remaining Bucket-B oracle
  candidates from `.claude/tasks/ecosystem-review/02b-behavioral-conformance.md`
  (fix-workflow characterization-test oracle next, then explain-proposer
  completeness, diagnose reproduction-loop, plan/spec schema oracles).
