# C# 14 / .NET 10 subsystem map v1

## Supported boundary

C# v1 maps exactly one regular file or directory selected from the authored
`sources` in two root manifests: `csharp-project.json` and
`csharp-semantic-project.json`. Both manifests must be current, must list the
same non-empty ordered `sources` and `tests`, and both providers must report the
same current SHA-256 for each source/test path. Generated and vendor paths may
appear only as explicit semantic exclusions. The lexical provider inventories
the whole host and owns namespace/file facts; the semantic provider owns
Roslyn-bound symbols and edges.

The selected skill is a copied closure with two sibling provider directories:

```text
.agents/skills/
├── _csharp/
├── _csharp-semantic/
└── map-subsystem/
    └── scripts/map_csharp.py
```

The command installs nothing, performs no restore or MSBuild evaluation, and
does not edit host C# or either manifest. It writes only the requested Markdown
and JSON, the semantic fact pack under `reports/csharp-semantic/map-subsystem/`,
and the lexical provider's disposable `.native-build` outputs.

## Evidence and complete claims

A complete result requires all of the following in one invocation:

1. The lexical provider accepts the exact first-party source/test inventory,
   runs direct `csc` source and test compilation, replays the declared native
   test and smoke programs, reads Roslyn syntax, and proves its source snapshot
   unchanged.
2. The semantic provider accepts its exact manifest inventory, repeats direct
   `csc` compile/test/smoke gates, compiles and runs the pinned helper, reports
   no Roslyn error diagnostic, and proves its snapshot unchanged.
3. The mapper verifies ordered source/test agreement, current manifest bytes,
   per-path source/test hashes, provider/helper hashes, and the semantic
   fact-pack object hash before rendering structural rows.
4. Authority is exactly .NET SDK `10.0.302`, runtime/reference pack `10.0.10`,
   the pinned `dotnet`, `csc`, `Microsoft.CodeAnalysis`, and
   `Microsoft.CodeAnalysis.CSharp` hashes, the 167-assembly reference manifest,
   lexical syntax-helper SHA-256
   `65474b5a3e53cee8bfe035f925ad14d97f291f21baac1c4de5c12ae2f6ffdd16`,
   and semantic helper SHA-256
   `0475a903da8973491775d627da2ca48c274e0c0684063ec229a26e439f5ed980`.

Within that boundary, the JSON and Markdown inventory every manifest source
and test with its current hash, mark the selected source paths, and report
selected namespaces, types, methods, properties, signatures, symbol IDs,
declared accessibility, override/explicit-interface metadata, and partial
metadata. Direct call/reference rows preserve Roslyn's resolved target symbol,
signature, caller where available, source location, and exact direction:
`internal`, `outbound`, or `inbound`. Direction is based only on a target symbol
ID matching a manifest declaration; constructors or external symbols without a
mapped declaration owner are not guessed into the selected subsystem.

## Terminal lifecycle

Every invocation clears the previous Markdown, JSON, and intermediate fact
pack, then uses atomic file replacement. A missing provider, missing semantic
manifest, unavailable pinned tool, stale/mismatched manifest universe or
snapshot, malformed input, compiler failure, helper hash mismatch, malformed
helper output, or SDK authority mismatch produces a visible terminal artifact.
All namespace, file, declaration, surface, edge, and observed-boundary arrays
are empty in that artifact, so an earlier complete result cannot survive as a
current claim. Correcting the prerequisite and rerunning replaces the terminal
artifact with a new complete map.

## Deliberate non-claims

Roslyn static binding does not prove runtime reachability or behavior. Virtual,
override, interface, delegate/method-group, and dynamic dispatch remain
unresolved. Reflection and runtime-name lookup remain boundary evidence rather
than edges. Generated/vendor files, source generators, analyzers, compiler
plugins, conditional-compilation variants, and generated partial declarations
are outside authored-source completeness.

The mapper also does not evaluate solution/project-reference graphs, NuGet
restore, MSBuild properties or multi-targeting, external callers, framework
routing or dependency injection, serialization, trimming/AOT, interop, ABI
compatibility, or mutation authority. These boundaries appear explicitly in
both complete and incomplete artifacts.
