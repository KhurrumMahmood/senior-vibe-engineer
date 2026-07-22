---
title: Webhook replay protection
status: scoped
subsystems: [webhook, delivery, observability]
---

# Webhook replay protection

## 1. Scope & Bounds

**Problem.** A replayed signed webhook can create more than one delivery, and
operators cannot distinguish a rejected replay from an ordinary retry.

**In scope.**

- Replay-key storage and lookup at `src/api/webhook.ts` before a delivery is
  accepted.
- Propagating one stable delivery identifier from `src/api/webhook.ts` to
  `src/worker/delivery.ts`.
- Recording replay rejection and retry outcomes through
  `src/observability/metrics.ts`.

**Out of scope.**

- Retry scheduling policy.
- An admin replay UI.
- Replacing the queue implementation.

**Non-goals.**

- Redesigning webhook payload schemas.
- Guaranteeing global exactly-once delivery across third-party receivers.

**Prior constraints.**

- Layer violation — HTTP request validation stays at the boundary; the worker
  receives a validated delivery contract rather than HTTP transport state.
- Stringly-typed state — delivery outcomes remain a declared finite set rather
  than ad-hoc strings.

## 2. Success Criteria

- A replay fixture with the same replay key is rejected before a second worker
  job is created.
- A first delivery fixture carries the same delivery identifier through the API
  and worker handoff.
- Metrics distinguish `rejected` replay attempts from `retried` delivery
  attempts.
- Retention duration remains an explicit unresolved product input rather than
  a guessed default.
