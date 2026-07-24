# C# foundation learning packet

The proven environment is .NET SDK 10.0.302, discovered through the resolved
`dotnet` executable rather than a hardcoded installation path. The portable
native path is an offline restore followed by `dotnet build --no-restore`, a
self-test run, and an executable smoke run. All generated `obj` and `bin`
content stays in an ephemeral project copy; the host project is fingerprinted
before and after execution.

The reusable foundation is deliberately narrow: case-normalized `.cs`
inventory and roles, exact lowercase compile items in a single root SDK-style
.csproj, strict explicit ownership, exact `global.json` SDK evidence, cleared
NuGet sources, tool capability, compiler diagnostics, source preservation, and
one terminal JSON artifact.
Valid-to-failed-to-valid reruns replace that same artifact, so stale success
cannot survive a failed compilation.

The SDK-bundled Roslyn compiler is reproducibly exercised by MSBuild, but this
cohort consumes no reusable Roslyn syntax or semantic API. It therefore claims
project compilation, not declaration, symbol, reference, call, type, flow, or
rewrite facts. Solutions, multiple projects, packages, generators, analyzers,
workloads, project references, and alternate target frameworks remain outside
the boundary.

The next cohort should reuse the inventory, exact project evidence, native
gate, fingerprints, and terminal lifecycle. It should add a separately tested,
SDK-version-pinned Roslyn helper only when a real consumer needs syntax or
semantic facts; it must not infer those facts from compiler success or regexes.

The foundation `scripts/csharp_language_provider.py` and the lexical
`_csharp/csharp_facts.py` have different contracts and copied closures. The
foundation owns strict project/native evidence; the lexical provider owns its
consumer-facing fact shape. They are not duplicate authorities, and future
maintainers should not extract a shared abstraction unless two real consumers
prove that their exact mechanics and lifecycle obligations genuinely overlap.
