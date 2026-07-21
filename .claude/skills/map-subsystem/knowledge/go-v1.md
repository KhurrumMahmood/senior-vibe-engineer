# /map-subsystem — Go v1 contract

`scripts/map_go.go` maps one package directory in the current active build of
one root Go 1.22+ module. The copied selected-skill closure uses only the host
`go` command and the Go standard library.

## Established facts

- `go list -e -json -mod=readonly ./...` establishes the active root-module
  package/import graph.
- `go/parser`/`go/ast` establish active non-generated files, exported
  top-level types/functions/methods/constants/variables, and source import
  spelling including default, alias, dot, and blank imports.
- First-party inbound and outbound edges are package edges, not symbol or call
  edges. An alias changes local spelling but not the resolved package fact.
- The Markdown map and JSON evidence record the current `GOOS`/`GOARCH`, any
  ignored Go files and explicit unavailable fields.

## Boundaries

- One package directory only; individual file, vendor, testdata, missing, and
  symlinked targets are unsupported.
- The map rejects active `go.work`, root-module `replace` directives, and
  non-root modules. It does not map cgo packages.
- Generated source is classified with `ast.IsGenerated` before inventory;
  `_test.go` and testdata never enter Go's active `GoFiles` selection. Any
  `.go` symlink in the selected package directory is rejected before package
  analysis, including a link to an external source file.
- Build-tag/GOOS/GOARCH alternatives are recorded as outside the active-build
  scope. They do not become a claim of full build-matrix coverage.
- No `go/packages`, `go/types`, interface dispatch, reflection, runtime
  loading, call graph, responsibility judgment, lint policy, or refactor
  recommendation.

## Outcome states

Missing or older-than-1.22 Go is a prerequisite failure and produces no map.
`complete` means the active selected package, its exported surface, and its
first-party package edges were established. `partial` retains a useful map but
marks unresolved first-party imports, incomplete `go list` package facts, or
unavailable inbound facts. Ordinary active Go files are parsed before cgo
returns `partial`, so malformed non-cgo source still fails. `unsupported`
writes a terminal map only after tool prerequisites pass but v1 cannot map the
selected module/package. Malformed eligible source writes `failed` JSON and
Markdown and exits non-zero.
