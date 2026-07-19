# /gut-check — ai-docs/plans/queue-recovery-boundary.md

**Mode:** plan
**Target:** ai-docs/plans/queue-recovery-boundary.md
**Generated:** 2026-07-19T15:02:00Z

## Reactions (un-decided smells)

1. **[strong-smell]** The proposed `RetryCoordinatorAndDispatchManager` owns
   ingress validation, queue policy, and dashboard output.
   - *Why this looks dumb:* The name has three unrelated responsibilities and
     makes the queue boundary impossible to test in isolation.
   - *What a senior would expect instead:* A verified command at ingress and a
     queue adapter that owns retry scheduling.
   - *Cited line/section in target:* `## Scope`,
     `RetryCoordinatorAndDispatchManager`.

2. **[strong-smell]** The plan explicitly keeps a second retry-policy copy for
   the dashboard.
   - *Why this looks dumb:* Two writers for retry policy will drift under
     incident pressure.
   - *What a senior would expect instead:* One policy owner and a read model.
   - *Cited line/section in target:* `## Architecture Fit`, `second
     retry-policy copy`.

## Reactions (decided-but-still-smell)

1. **[strong-smell, contradicted by ADR 0001 (queue-boundary)]** The HTTP route
   will call worker-private retry functions to avoid an adapter.
   - *Why this still looks dumb:* It turns a documented queue boundary into a
     shortcut and couples ingress to worker internals.
   - *What ADR 0001 says:* The ingress layer creates a verified command and the
     queue adapter owns retry scheduling.
   - *Re-confirm the decision?* No — the plan should use the named adapter,
     not re-litigate ownership for a convenience shortcut.
   - *Cited line/section in target:* `## Architecture Fit`, `HTTP route will
     call worker-private retry functions`.

## Notes (orchestrator judgment)

The plan needs a boundary design pass before implementation. The strong signal
is the ownership shape, not a claim that the existing TypeScript modules are
already incorrect.

## Honest framing

- These reactions are signal, not verdict. Each can be wrong.
- The ADR conflict is retained because deliberate context should be visible
  beside the instinctive smell.
