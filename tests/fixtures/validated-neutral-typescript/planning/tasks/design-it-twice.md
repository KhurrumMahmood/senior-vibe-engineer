# Natural task: explore delivery retry execution

You are working in the TypeScript planning host. A durable retry record is
needed, but it is not yet clear whether the worker should execute retries
inline, hand them to a dedicated scheduler, or use a small hybrid dispatcher.
This is costly to reverse because it changes operational ownership and failure
visibility.

Explore three deliberately divergent axes: lowest added latency,
operationally observable execution, and strongest isolation from worker
throughput. Synthesize agreements, actual differences, and a recommendation;
do not author an ADR or modify source code.
