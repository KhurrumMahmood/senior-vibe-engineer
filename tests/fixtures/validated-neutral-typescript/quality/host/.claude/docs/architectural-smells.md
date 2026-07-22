# Architectural smells

## Omnibus modules

One module should not own unrelated ingress validation, retry policy, and
operator reporting. Keep the boundary and its state transitions explicit.

## Layer violation

Transport-facing modules must not reach into worker internals to schedule or
inspect retries. Pass a validated command across a named boundary instead.

## Format-equivalence gaps

When two writers create the same operational record, one writer must be
canonical and the other must delegate or be removed.
