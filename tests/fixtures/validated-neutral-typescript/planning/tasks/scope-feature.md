# Natural task: scope webhook replay protection

You are working in the TypeScript planning host. Scope a System-tier initiative
that spans the HTTP webhook entry point, worker delivery retries, and delivery
metrics. The product problem is that a replayed signed request can be delivered
more than once and operators cannot distinguish a rejected replay from a retry.

Confirm a bounded scope: replay-key storage and lookup, rejection at the HTTP
boundary, worker propagation of a stable delivery identifier, and one replay
metric are in scope. Retry scheduling policy, an admin replay UI, and replacing
the queue implementation are out of scope. Use observable acceptance criteria
and leave unknown retention duration explicit rather than inventing it.
