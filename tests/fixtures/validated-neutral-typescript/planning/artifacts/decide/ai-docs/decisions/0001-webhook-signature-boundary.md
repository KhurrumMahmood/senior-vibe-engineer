---
id: "0001"
namespace: core
title: Webhook signature boundary
status: proposed
date: 2026-07-19
deciders: []
supersedes: []
superseded_by: null
applies_to: [src/api]
embodied_by: []
tags: [webhook, boundary]
related_smell: layer-violation
related_pattern: null
---

# Webhook signature boundary

## Context

Webhook requests enter through one HTTP adapter and later become worker jobs.
Without a boundary rule, callers can move signature verification into a worker
or repeat it inconsistently when another HTTP entry point is added.

## Decision

Verify the signature at the HTTP boundary before a delivery contract is
created. The worker receives only the validated contract and does not own HTTP
signature parsing or transport credentials.

## Alternatives considered

- **Verify only in the delivery worker.** Rejected: invalid requests would
  consume queue capacity and move HTTP-bound credentials into worker code.
- **Verify at both boundaries.** Rejected: duplicate verification obscures the
  ownership rule and creates inconsistent failure reporting.
- **Accept unsigned requests.** Rejected: the delivery contract would not
  establish a trustworthy boundary.

## Consequences

**Easier:**

- New HTTP entry points can reuse one validation responsibility.

**Harder:**

- The HTTP adapter must supply a complete validated contract to the worker.

**Now expected / now disallowed:**

- HTTP signature parsing belongs to entry adapters; worker-only verification is
  disallowed.

## Verification

- **Tooling:** a signed and rejected-signature fixture covers the entry
  boundary without changing worker source.
- **Doc backref:** evaluate a `Decided in: 0001` link under the layer-violation
  smell after human review.
- **Existing artifacts:** `src/api/webhook.ts` and `src/worker/delivery.ts`
  identify the affected boundary.
