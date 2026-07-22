# Design It Twice: delivery-retry-execution

## Fork

Durable retries must choose between immediate worker execution, a scheduler
that prioritizes visible lifecycle state, and a dispatcher that isolates retry
throughput from the main delivery path.

## Divergence axes

- **Axis 1: latency minimize** — prefer the fewest handoffs.
- **Axis 2: observability maximize** — prefer an auditable retry lifecycle.
- **Axis 3: throughput isolate** — prefer independent retry capacity.

These axes expose the real tension between fast recovery, operational evidence,
and isolation. A framework or queue replacement axis was skipped because it
would change implementation technology rather than the retry ownership choice.

## Designs

- [Design 1: latency minimize](design-axis1-latency-minimize.md)
- [Design 2: observability maximize](design-axis2-observability-maximize.md)
- [Design 3: throughput isolate](design-axis3-throughput-isolate.md)

## Where they agreed

- A durable retry record needs the stable delivery identifier.
- HTTP signature validation stays outside retry execution.

## Where they diverged

- Inline execution optimizes the first retry's latency; the scheduler makes
  every lifecycle transition explicit; the dispatcher protects worker
  throughput at the cost of another handoff.
- Backoff policy belongs to the worker, scheduler, or dispatcher respectively.

## Recommendation

**Axis: observability maximize.** A dedicated scheduler makes delayed retry
state inspectable before retry volume grows, which is more valuable here than
the small added handoff. The accepted trade is operating one additional
boundary and characterizing its lease behavior.

## Not chosen — why

- **latency minimize:** slow receivers could consume general worker capacity.
- **throughput isolate:** independent scaling is premature before retry load is
  measured.

## Hand-off

Next: `/decide delivery-retry-execution` with this analysis as the Context
section of the ADR.
