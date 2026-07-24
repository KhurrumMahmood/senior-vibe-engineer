# C# `move-path` learning packet

Status: bounded implementation complete; publication remains root-owned

## Final value proved

One authored C# implementation file can move to another source directory in a
strict dependency-free `net10.0` executable while retaining its filename,
file-scoped namespace, internal top-level type identity, assembly identity, and
source bytes. The representative transaction moves `src/Invoice.cs` to
`src/billing/Invoice.cs` and changes only the exact matching `Compile Include`
in `CSharpMovePilot.csproj`.

Dry-run validates one root SDK project, the exact explicit authored `src/` and
`tests/` compile closure, the reviewed .NET 10 SDK pin, and a `NuGet.Config`
with no package sources. It runs offline restore, build, direct self-test, and
exact-output smoke against disposable copies of both the current and virtual
after-tree. The host receives no `obj`, `bin`, package, or source mutation.

`evidence.json` content-addresses the plan, standalone adapter, complete host
byte/mode/symlink tree, exact compile-item and source-location changes, tool and
project facts, namespace/type/assembly/source-byte identity, native evidence,
and expected after-tree. Apply requires the reviewed evidence SHA-256,
recomputes the preview, performs the real mutation, repeats the disposable
native boundary, and checks the exact tree and old-path residue. Any
post-mutation failure restores the complete pre-apply snapshot. Check proves
the approved after-state and final executable output.

## Honest refusal boundary

This is a source-location move, not a namespace, type, filename, assembly,
public API, or ABI refactor. It supports exactly one authored `.cs`
implementation file below `src/`, keeps the same filename and identity, and
requires one closed executable with no external consumers.

The adapter stops before writes for public, protected, partial, or file-local
moved types; multiple declarations or namespaces; preprocessor variants;
reflection, runtime paths, resources, interop, or unsafe boundaries involving
the moved identity; generated, vendor, build, tooling, test, script,
mixed-language, unknown-role, or symlink source; incomplete or wildcard compile
items; solutions, multiple projects, project/package/framework references,
generators, analyzers, imported build metadata, workloads, package sources,
multiple moves, and directory moves. It does not claim library compatibility,
inactive configuration completeness, external-consumer completeness, or a
general Roslyn refactoring engine.

## Reuse decision

The implementation is one Python-standard-library adapter. Copying only
`csharp_source_move.py` outside the checkout and invoking it with isolated,
no-site Python completes dry-run and approved apply against a copied fixture.
It imports neither the repository C# foundation provider nor inventory helpers.
No generic mutation framework or cross-language project abstraction was added.

The transferable lesson is narrow: for an explicitly compiled C# source file,
source-directory location is independent of type and assembly identity only
inside a closed project whose complete inputs and configuration are known.
Unchanged source bytes plus exact project metadata make the invariant
inspectable; compiler, direct test, and smoke evidence prove the bounded
executable outcome; dynamic and compatibility claims remain refusals.

## Verification and limits

The focused suite proves 22 outcomes: the executable documented command, full
preview/approve/apply/check, exact source/project changes,
namespace/type/assembly/source-byte preservation,
offline disposable native execution, a complete→failed→complete refusal
lifecycle, sixteen uncertainty families, missing/wrong/stale authority, exact
rollback after native failure, and a copied single-file closure. The fixture
uses .NET SDK 10.0.302 and a dependency-free `net10.0` executable.

Root alone owns shared capability matrices, routers, plan indexes, and catalogue
publication after merge and preserved-family replay.
