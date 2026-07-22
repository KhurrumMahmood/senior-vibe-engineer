# Natural task: assess delivery retry architecture

You are working in the TypeScript planning host. An impacted System-tier plan
will add a durable retry record shared by `src/api/webhook.ts`,
`src/worker/delivery.ts`, and `src/observability/metrics.ts`. Assess its
architecture fit. Preserve the HTTP boundary as the entry validation layer and
avoid making the worker reach back into HTTP transport state.

There is one genuine P0 fork: should retry execution happen inline in the
delivery worker or through a dedicated scheduler boundary? Record the fork
instead of choosing speculatively, and recommend a divergent-design exploration
before an ADR.
