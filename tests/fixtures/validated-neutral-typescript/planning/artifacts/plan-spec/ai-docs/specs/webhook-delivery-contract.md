---
id: webhook-delivery-contract
title: Webhook delivery contract
status: draft
motivating_decision: "0001"
code_roots: [src/api/webhook.ts, src/worker/delivery.ts]
---

# Provenance

Promoted from plan `webhook-delivery-contract`
(`ai-docs/plans/webhook-delivery-contract.md`).

- Plan §1-2 → Goals
- Plan §3, §5 → Architecture
- Plan §4, §3 → Implementation (test-first)
- Plan §5, §6 → Exceptions

# Webhook delivery contract

## Goals

- Preserve acceptance of valid signed requests while rejecting invalid
  signatures before worker enqueue.
- Carry one stable delivery identifier from `src/api/webhook.ts` to
  `src/worker/delivery.ts`.

## Architecture

`src/api/webhook.ts` owns HTTP signature validation and produces a validated
delivery contract. `src/worker/delivery.ts` consumes that contract without
parsing HTTP credentials, conforming to ADR `0001`.

## Implementation

- AR-1: characterize a valid signed request reaching one worker handoff.
- AR-2: characterize an invalid signature creating no worker handoff.
- IM-1: introduce the validated delivery contract at `src/api/webhook.ts`.
- IM-2: consume the delivery identifier at `src/worker/delivery.ts`.

## Learnings

_Reserved for /refactor-subsystem Phase 2b._

## Exceptions

- Dashboard aggregation cadence is deferred from plan §6 P1 until delivery
  volume is measured.
