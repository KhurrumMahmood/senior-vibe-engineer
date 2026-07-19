---
title: Webhook delivery contract
status: promoted
successor_spec: webhook-delivery-contract
subsystems: [webhook, delivery]
---

# Webhook delivery contract

## 1. Scope & Bounds

Add a validated HTTP-to-worker delivery contract without changing payload
schemas.

## 2. Success Criteria

- Rejected signatures never create worker jobs.
- A delivery identifier survives API-to-worker handoff.

## 3. Impact Map

- `src/api/webhook.ts` creates the validated delivery contract.
- `src/worker/delivery.ts` consumes it and records retry intent.

## 4. Behaviors to Preserve

- Valid signed requests remain accepted.
- Invalid signatures remain outside worker execution.

## 5. Architecture Fit

**Decision conformance.**

- ADR `0001` (Webhook signature boundary) — validate before the worker
  contract is created.

**Pattern alignment.**

- Boundary validation keeps request credentials out of worker state.

## 6. Open Decisions

**P0 — must resolve before promotion.**

- None.

**P1 — should resolve before implementation.**

- Dashboard aggregation cadence — defer operational dashboard work until
  delivery volume is measured.
