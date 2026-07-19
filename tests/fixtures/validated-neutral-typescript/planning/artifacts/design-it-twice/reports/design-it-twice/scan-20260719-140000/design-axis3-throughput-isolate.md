# Design: throughput isolate

## Design

Use a small dispatcher to separate retry admission from both request handling
and delivery execution, with workers claiming ready retry records.

## Strengths under this axis

- Slow retries do not block HTTP or primary delivery work.
- Retry capacity can be scaled independently.
- Queue pressure has a narrow owner.

## Weaknesses where this axis hurts

- More moving parts need characterization tests.
- Ownership between dispatcher and worker needs a clear lease rule.
- Operational tracing crosses an additional boundary.

## What you'd change if asked to soften the axis

- Start with one process boundary but retain the explicit admission record.
