# C# semantic read-only family

Status: implementation complete in the language-local cohort; shared
publication remains root-owned.

## Bounded authority

The family resolves SDK state from the selected `dotnet` executable and
`dotnet --info`; product code does not assume a home directory or system
installation prefix. The accepted offline authority is:

- .NET SDK `10.0.302`, runtime and `Microsoft.NETCore.App.Ref` `10.0.10`;
- `csc.dll` SHA-256
  `c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81`;
- `Microsoft.CodeAnalysis.dll` SHA-256
  `eabc44a97ca36c415af0d7a4db353c170fad26da897b11862927bdb3402f3786`;
- `Microsoft.CodeAnalysis.CSharp.dll` SHA-256
  `daff05fe558690b194b93e99d1299f2a85afba55c41fba5718dba6bdfd36bfe9`;
- 167 reference assemblies with manifest SHA-256
  `9719ee9a053103d3de4b3bfb91f230d9a58325f47e7ac90a2147649d288f2fdd`;
  and
- the exact helper, provider, project-contract, manifest, and selected source
  hashes recorded in every fact pack.

Direct `csc` native app/test builds and exact `dotnet` test/smoke output gate
the Roslyn read. No restore, package download, workload, analyzer, or ambient
project mutation occurs. The self-contained manifest is the complete selected
project boundary for this cohort rather than an inferred solution graph.

## Outcomes and closure

One `_csharp-semantic` fact pack supplies compiler-resolved declarations,
references, overload call targets, constructor arguments, assignments,
override/partial metadata, and explicit uncertainty boundaries. Five thin
selected-skill wrappers retain independent artifacts:

- `find-dormant`: private methods with no selected resolved reference, always
  review-required and never safe-delete authority;
- `find-implicit-state`: selected direct string-property literal domains,
  never a closed-domain or automatic-migration claim;
- `find-incomplete-sweep`: one omitted optional constructor argument among a
  three-call resolved group, without inferring chronology or intent;
- `find-semantic-duplication`: matching resolved method contracts, normalized
  bodies, and direct callers, without behavioral-equivalence authority; and
- `rename-concept`: selected resolved type declarations/references and an
  assess-only incomplete/complete verdict, never a codemod.

The copied runtime closure for each outcome is the selected wrapper plus the
entire `_csharp-semantic` directory. Focused tests copy that closure outside
the repository skill tree, run the copied provider and wrapper, and assert the
same final artifact. They also prove exact source preservation and replace a
complete artifact with a claim-free partial artifact on stale input, then
restore complete output at the same destination.

## Explicit non-claims

Override/interface/runtime dispatch, delegates and callbacks, reflection and
runtime names, dynamic dispatch, partial declarations, generated/vendor
inputs, source generators, analyzers, external callers, solution and project
references, conditional build variants, NuGet packages, workloads, framework
registration, serialization, trimming/AOT, interop, and binary compatibility
remain outside the selected static claim. None of the five outcomes mutates
source or grants deletion, migration, equivalence, or release authority.

## Transfer lessons

1. SDK-bundled Roslyn is reproducibly callable without restore: compile a
   small helper directly with the SDK `csc.dll`, reference the exact framework
   pack and Roslyn assemblies, place the two Roslyn assemblies beside the
   helper, and run it with an exact runtimeconfig.
2. Resolve the SDK base from `dotnet --info`, then hash the compiler,
   semantic assemblies, and complete reference-pack manifest. A path-only or
   version-only check is insufficient for a private compiler boundary.
3. Roslyn operations expose defaulted constructor arguments as synthesized
   `DefaultValue` arguments. Sweep consumers must distinguish those from
   explicit arguments instead of treating parameter presence as authored
   presence.
4. Documentation-comment IDs give stable selected-project symbol identity for
   types and members; display signatures remain useful human evidence but are
   not the identity key.
5. Generated/vendor exclusions should still be content-addressed and emitted
   as boundaries. Silently ignoring them would overstate rename, dormancy, and
   state completeness.
6. This provider shape is reusable inside C# only. It does not justify a
   cross-language symbol schema or a generic compiler runtime.

Focused verification:

```bash
.venv/bin/python -m pytest -q tests/test_csharp_semantic_family.py
```

Result: `3 passed`.
