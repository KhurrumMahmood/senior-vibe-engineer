# C# SDK/Roslyn semantic read-only family

Keep this directory beside one selected consumer in the external on-demand
library. The host must provide the exact dependency-free
`csharp-semantic-project.json` contract, selected C# sources/tests, and .NET SDK
`10.0.302` with runtime/reference pack `10.0.10`.

Produce one content-addressed fact pack without restore or network access:

```bash
SEMANTIC_ROOT=".agents/skills/on-demand/_csharp-semantic"
DOTNET="${DOTNET:?Set the exact .NET SDK 10.0.302 executable}"
python3 -I -S "$SEMANTIC_ROOT/csharp_semantic_facts.py" \
  --project-root "$PWD" \
  --manifest csharp-semantic-project.json \
  --output reports/csharp-semantic/facts.json \
  --dotnet "$DOTNET"
```

The provider derives the SDK base from that executable and `dotnet --info`,
then validates the exact `dotnet`, `csc.dll`, Roslyn assemblies, and complete
reference-pack manifest before direct native app/test compilation. It compiles
and executes the pinned helper from the SDK assemblies; it does not use NuGet,
restore, workloads, or an inferred solution graph.

Use the selected skill's `knowledge/csharp-v1.md` command to render its final
artifact. Fact status, root, content hash, and every selected/generated/vendor
input hash are revalidated on each consumer run. A mismatch replaces the old
artifact with a claim-free partial result.

This boundary covers selected static declarations, references, overload call
targets, constructor arguments, assignments, overrides, and partial metadata.
Runtime reachability and behavior, interface/virtual/dynamic dispatch,
delegates, reflection/runtime names, generated code, source generators,
analyzers, external callers, solution/project references, conditional build
variants, frameworks, serialization, trimming/AOT, interop, binary
compatibility, deletion, equivalence, and mutation remain outside the claim.
