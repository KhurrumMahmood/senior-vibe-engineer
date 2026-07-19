# Triage queue — scan-20260719-150400

_Aggregated from one cached find-* report stream, one spec audit, and zero
decision-drift records over the past 90 days._

## Inputs

- Cache: `reports/triage-debt/cache/current`
- Present: `effectiveness.jsonl`, `specs-audit.json`, `specs-size.json`,
  `decisions-audit.json`, and `reports/omnibus/latest/triage.md`.
- Missing: none required for this cached replay.

## Top 2 (recommended next actions)

### 1. src/worker/retry.ts — score 600
- **Source:** `find-omnibus` (last seen 2026-07-01, hit 3 times)
- **Why ranked here:** Three distinct scans each carry six
  `confirmed_omnibus` findings; recurrence and the P0 band both apply.
- **Recommended next:** `/decide retry-policy-standard`, then extract the
  policy owner, then `/prevent-regression topology:retry-policy-owner`.
- **Escalation:** standardize-and-enforce — band `confirmed_omnibus` × 6.
- **Evidence:** `reports/omnibus/latest/triage.md::omnibus-001`

### 2. ai-docs/specs/webhook-ingress.md — score 180
- **Source:** spec drift (last modified 2026-03-01)
- **Why ranked here:** Unchecked implementation items are older than 60 days.
- **Recommended next:** `/refactor-subsystem webhook-ingress` Phase 2b
  (Crystallize).
- **Evidence:** `reports/triage-debt/cache/current/specs-audit.json`

## Full queue

| Rank | Target | Source skill | Score | Recurrence | P0 | Drift | Park |
|---|---|---|---:|---:|---:|---:|---|
| 1 | src/worker/retry.ts | find-omnibus | 600 | 3 | 6 | 0d | — |
| 2 | ai-docs/specs/webhook-ingress.md | spec drift | 180 | 0 | 0 | 60d | — |

## Park notes

None.

## Stale find-* reports

None: the latest cached omnibus scan is 18 days old at this replay date.
