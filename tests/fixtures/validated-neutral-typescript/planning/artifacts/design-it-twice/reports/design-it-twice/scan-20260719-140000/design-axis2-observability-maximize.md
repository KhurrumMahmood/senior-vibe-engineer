# Design: observability maximize

## Design

Send every retry request through a dedicated scheduler that records lifecycle
events before returning an execution lease to the delivery worker.

## Strengths under this axis

- Retry states have one auditable lifecycle.
- Operators can distinguish scheduled, leased, and exhausted work.
- Backoff policy is visible as scheduler data.

## Weaknesses where this axis hurts

- A scheduling hop adds latency.
- The scheduler becomes another operational dependency.
- Small workloads pay a larger coordination cost.

## What you'd change if asked to soften the axis

- Lease only delayed retries and keep the first retry inline.
