---
title: Delivery retry boundary
status: architected
subsystems: [webhook, delivery, observability]
---

# Delivery retry boundary

## 1. Scope & Bounds

Add durable retry state without changing webhook payload semantics.

## 2. Success Criteria

- A retry record preserves the delivery identifier.
- The worker can report an explicit retry outcome.

## 3. Impact Map

- `src/api/webhook.ts` creates the validated delivery contract.
- `src/worker/delivery.ts` consumes the delivery contract and requests retry
  execution.
- `src/observability/metrics.ts` records the final retry outcome.

## 4. Behaviors to Preserve

- A valid initial delivery remains accepted.
- A rejected signature never reaches the worker.

## 5. Architecture Fit

**Decision conformance.**

- No constraining priors: this host has no accepted retry-execution ADR; the
  pending fork is intentionally visible below.

**Pattern alignment.**

- Boundary validation — `src/api/webhook.ts` owns request validation before
  the worker sees a delivery contract.

**Smells avoided.**

- Layer violation — the worker does not read HTTP request or response state.
- Stringly-typed state — retry outcomes are represented by one declared
  outcome vocabulary.

## 6. Open Decisions

**P0 — must resolve before promotion.**

- **delivery-retry-execution** — execute retries inline in the worker versus
  introduce a dedicated scheduler boundary; run
  `/design-it-twice delivery-retry-execution` before `/decide`.

**P1 — should resolve before implementation.**

- Dashboard aggregation cadence — defer until the execution boundary is
  selected.
