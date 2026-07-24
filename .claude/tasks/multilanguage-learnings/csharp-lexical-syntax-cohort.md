# C# lexical/filesystem/syntax cohort

## Scope

Implemented bounded C# 14 / .NET 10 support for `adapt-project`,
`explain-code`, `find-concept-divergence`, `find-duplication`,
`find-folder-topology-drift`, `audit-decisions`,
`find-complexity-hotspots`, `find-omnibus`, and `find-standard-gaps`.

The copied runtime closure is `_csharp/CSharpSyntaxFacts.cs`,
`_csharp/csharp_facts.py`, and `_csharp/csharp_consumers.py`. Each skill owns a
thin C# entrypoint. The provider accepts only exact lowercase `.cs` source and
test paths declared by `csharp-project.json`. It discovers SDK 10.0.302 from
the selected `dotnet` executable, invokes bundled `csc.dll` directly against
the installed .NET 10 reference pack, and uses the same SDK's bundled Roslyn
assemblies offline.

## C# identity retained

- Roslyn facts preserve namespace and declaring-type context.
- Overloaded methods retain distinct spelled signatures.
- Records remain distinct declaration kinds and extension methods retain the
  receiver spelling from their `this` parameter.
- Direct invocation spellings and enclosing `if` syntax remain unresolved
  source facts; no callee binding is inferred.
- Generated, vendor, build, tooling, test, symlink, and agent-runtime source
  roles remain explicit or excluded from authored-source conclusions.

## Value proof

The representative fixture compiles app and tests from the exact manifest
closure, runs both framework-dependent executables, and checks exact stdout
(`csharp-lexical:12:queued` and `csharp-lexical-tests:ok`). The nine consumers
produce final artifacts for overload-aware explanation, strict identifier
drift, an exact method-body clone, a filename cluster, resolved/orphan ADR
comment references, an eight-branch hotspot, an explicitly scouted omnibus
candidate, and a two-site/one-gap standard census.

Copied-closure testing found an important language-specific boundary: unlike
a Python-only provider, the Roslyn helper itself is a `.cs` file. When copied
under a host `.agents/skills` tree it must be excluded from host project
discovery, or the exact source manifest correctly refuses the unexpected
input. Agent-runtime roots are therefore excluded explicitly.

## Limits and rebase dependency

The provider does not evaluate projects through MSBuild or NuGet and makes no
claim about source generators, analyzers, conditional build variants,
multi-targeting, resolved symbols, overload selection, dispatch, data flow,
reflection, compiler IR, runtime behavior, or refactor safety. It compiles a
deliberately small direct-manifest contract with installed SDK assets only.

This lane intentionally does not publish shared routers, language matrices,
doctor/inventory data, generic profiles, or catalog entries. Foundation work
must later register this local C# provider and its nine entrypoints on rebase.
