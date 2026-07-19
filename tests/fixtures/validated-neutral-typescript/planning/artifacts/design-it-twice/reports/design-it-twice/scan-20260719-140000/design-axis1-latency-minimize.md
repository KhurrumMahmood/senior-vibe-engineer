# Design: latency minimize

## Design

The delivery worker retries inline after recording the next attempt, avoiding a
second scheduling hop.

## Strengths under this axis

- Lowest retry handoff latency.
- One execution process to inspect.
- No additional dispatcher contract.

## Weaknesses where this axis hurts

- Slow receivers occupy worker capacity.
- Retry visibility shares the worker's operational surface.
- Backoff policy is coupled to delivery execution.

## What you'd change if asked to soften the axis

- Add a bounded inline retry budget before dispatching later attempts.
