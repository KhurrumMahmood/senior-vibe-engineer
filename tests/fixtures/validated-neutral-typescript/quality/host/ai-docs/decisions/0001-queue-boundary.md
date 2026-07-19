---
id: "0001"
status: accepted
title: Queue boundary
applies_to: src/worker/**
---

# Queue boundary

## Context

Ingress accepts webhook requests while the worker owns retry scheduling.

## Decision

The ingress layer creates a verified command and the queue adapter owns retry
scheduling. A thin adapter is allowed to translate that command at the queue
boundary.

## Consequences

Ingress must not construct retry timers directly. Queue-specific backoff is
visible behind the adapter rather than duplicated in request handlers.
