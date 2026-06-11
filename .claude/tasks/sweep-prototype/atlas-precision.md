# External-corpus precision measurement: find-omnibus on Atlas App

**Date:** 2026-06-11 · **Corpus:** Atlas/App `src/libs` (shallow clone, head only) —
667k LOC TypeScript, 1,679 files scanned by the ADR 0032 js-heuristic adapter in 0.49s.
**Method:** all 43 omnibus candidates judged independently by 4 parallel Haiku judges
(strict read budgets: head-60 + greps + provided metadata: loc, symbol clusters,
importers, @deprecated, TODOs). This is the first detector measurement against an
external corpus with team-acknowledged debt — the validation mode the June 2026
effectiveness audit demanded, replacing self-scan circularity.

## Results

| Metric | Value |
|---|---|
| Raw precision (true-debt / flagged) | **13/43 = 30%** |
| Precision@5 (by detector score) | **5/5 = 100%** |
| Precision@10 | 8/10 = 80% |
| Precision@15 | 11/15 = 73% |
| Recall vs 9 known/acknowledged God-files | **7/9** (missed: actions/IOU/index.ts, SidebarUtils.ts) |
| Judge verdict split | 13 true-debt / 29 legitimate-large / 1 data-file / 0 unsure |

Judged true-debt (all confirmed by blast-radius + multi-domain evidence):
ReportUtils (13.4k LOC, 74 clusters, 456 importers), actions/Report/index (7.9k),
actions/Policy/Policy (7.6k, 481 importers), SearchUIUtils, ReportActionsUtils,
PolicyUtils, TransactionUtils/index, OptionsListUtils/index, actions/User,
actions/Card, actions/BankAccounts, actions/CompanyCards, DebugUtils.

## Interpretation

1. **Ranking quality is excellent; the raw set is noisy by design.** The detector's
   score ordering put true-debt in all top-5 slots. Below rank ~15, candidates are
   mostly cohesive-but-large single-domain modules (DateUtils, ValidationUtils,
   Navigation hub) that a judge correctly clears using the facet-vs-domain rule.
2. **The two-stage shape (free detect → cheap judge) is mandatory, not optional.**
   Same conclusion the Daedalus scout produced from the opposite direction
   (disciplined repo, raw signals fire, judgment disarms). Raw manifest counts must
   never drive fixes or rankings directly — which is also the effectiveness audit's
   "noisiest detector wins" complaint, now with a measured basis.
3. **Cluster count alone does not separate debt from infrastructure** (Navigation.ts:
   13 clusters, 1,287 importers, judged legitimate hub). The discriminating signal the
   judges actually used: clusters × importers × *unrelatedness of cluster domains* —
   the third factor is inherently a judgment call, supporting judge-in-the-loop.
4. **The two recall misses are threshold artifacts** worth one tuning pass:
   actions/IOU/index.ts (recently decomposed into submodules — arguably a true
   negative) and SidebarUtils.ts.

## Cost

Scan: 0 tokens / 0.49s. Judges: 4 × Haiku ≈ 139k tokens total, ~70s wall (parallel).
Whole measurement ≈ 140k tokens, ~90% Haiku.

## Feeds

- The sweep-harness design (judgment stage becomes a first-class battery phase).
- ADR 0032 verification (js adapter validated at scale) and the future sweep ADR.
- Effectiveness-audit response: first non-self-referential precision datum.
