# /map-subsystem — TypeScript / TSX v1 contract

Use `scripts/map_typescript.mjs` only with a named `--tsconfig` owned by the
target project. The script resolves the target host's pinned `typescript`
package with Node's project-local resolution and uses its Compiler API. It is
not a shared parser, lint, or analysis platform.

## What the final map establishes

- Eligible `.ts` and `.tsx` file inventory under the requested file/directory.
- Exported module surface, including explicit re-export status.
- Static `import`, `export … from`, and `import = require` edges. Relative
  specifiers and `compilerOptions.paths` aliases are resolved by the one named
  tsconfig resolver.
- Inbound project importers that resolve to selected source files, plus a
  barrel-boundary marker for imports resolved to `index.ts`/`index.tsx`.
- Workflow-map references in `.claude/docs/workflows/`, TypeScript diagnostic
  counts, and an explicit ESLint-unavailable status.

The Markdown map and JSON evidence must agree. JSON `status: "complete"`
means the map's source inventory, exported surface, and static-module
resolution are complete for the eligible target. `status: "partial"` means at
least one selected file has an unresolved or symlink-blocked static import;
inspect `unresolved_imports` rather than treating the remaining records as a
complete dependency graph.

## Deliberate boundaries

- No responsibility clusters, behavioral explanations, framework identity,
  dynamic imports, runtime loading, call graph, reference search, or safe
  deletion claim.
- No ESLint invocation or inferred lint configuration. ESLint is explicitly
  unavailable until a separate host-policy contract is accepted.
- `.d.ts`, generated, vendor, minified, bundle, test/spec/fixture, dependency,
  build, and declared-tsconfig exclusions never enter inventory—even when a
  direct invocation names the excluded directory or file.
- Exclusions are checked project-root-relatively after normalization. Directory
  symlinks are never traversed; a symlink target is rejected rather than used
  to bypass project containment or an exclusion.

## Failure modes

Exit code 2 with a clear message for a missing target, target outside the
project root, symlink target, missing/invalid tsconfig, unavailable host
TypeScript package, or TypeScript syntax error. A normal TypeScript type error
is retained as a diagnostic count in the final map; it does not recast module
facts as a syntax failure.
