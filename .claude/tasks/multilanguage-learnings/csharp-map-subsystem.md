# C# `map-subsystem` final-outcome learning

## Outcome

The C# lane adds a standalone copied `map_csharp.py` consumer to
`map-subsystem`. It composes the existing lexical and semantic providers rather
than introducing a third C# parser. A complete artifact for one exact
manifest-selected target includes full source/test hashes, selected namespaces,
types, methods, properties and accessibility, direct Roslyn-resolved
call/reference edges, native test/smoke evidence, exact SDK/helper authority,
and source-preservation evidence.

The paired-provider gate is load-bearing. The lexical manifest owns the exact
first-party filesystem universe and namespace syntax. The semantic manifest
owns excluded generated/vendor provenance and Roslyn compilation. The consumer
requires identical ordered source/test lists and current per-path hashes from
both; neither provider can silently widen the other's selected universe.

## Boundary and lifecycle

The SDK authority is deliberately exact: .NET SDK `10.0.302`, runtime and
reference pack `10.0.10`, pinned executable/compiler/Roslyn assembly hashes, a
167-assembly reference manifest, and both lexical and semantic helper hashes.
The consumer also verifies the helper and provider files beside the copied skill and
recomputes the fact-pack object hash before rendering claims.

Bound calls and references are static compiler facts only. Runtime and virtual
reachability, reflection/runtime names, delegate and method-group invocation,
override/interface dispatch, generated/source-generator inputs, analyzers,
project/solution graphs, MSBuild variants, external consumers, and framework
registration remain explicit unresolved boundaries.

Each invocation removes the old Markdown, JSON, and intermediate fact pack and
atomically writes the new terminal state. Missing providers/tools/manifests,
malformed input, stale or incoherent manifests/hashes, helper tampering, native
diagnostics, or authority mismatch leave all structural arrays empty. The
focused copied-closure test proves complete → stale → malformed → missing tool
→ helper hash failure → recovered complete transitions at the same paths and
proves host sources/manifests retain their original hashes.

## Reuse judgment

No shared extraction was added. Provider discovery, safe destinations, atomic
replacement, manifest coherence, and claim-free terminal rendering resemble
the Kotlin map consumer, but C# authority, inventory schemas, accessibility,
symbol identity, and boundary rows are family-specific. A shared abstraction
would currently hide the evidence contract rather than reduce it.
