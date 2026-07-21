# Go `map-subsystem` v1 learning packet

Go mapping is useful without a semantic platform when it is stated as an
**active-build package map**, not as a whole-program symbol graph. The copied
on-demand closure discovers Go 1.22+ from `PATH`, requires one root module,
and uses `go list -e -json -mod=readonly ./...` for package/import facts plus
one bundled standard-library `go/parser`/`go/ast` helper for active source,
exported declarations, and import spelling.

The final artifact is both `.claude/docs/subsystems/<name>.md` and
`reports/map/<name>/go-map.json`. It records the package import path, current
`GOOS`/`GOARCH`, active non-generated source inventory, exported types,
functions, methods, constants and variables, parser-recorded default/alias/
dot/blank imports, first-party package inbound/outbound edges, and explicit
unavailable fields. Native `go test ./...` is
separate host verification and source fingerprints prove the map itself is
read-only.

`go list` establishes package edges, not symbol/call identity. The pilot does
not use `go/packages`, `go/types`, gopls, a third-party module, or a shared Go
runtime. It also does not infer responsibility clusters, lint policy,
interface/reflection dispatch, dynamic loading, a call graph, or build-matrix
coverage. Generated source is classified with `ast.IsGenerated` before the
inventory. `_test.go`, testdata, vendor, symlinks, cgo, active workspaces,
root-module replacements, and non-root modules stay outside the accepted
source model.

The locked fixture reaches complete active-build output with two source files,
six exports, two first-party outbound imports, two inbound imports (default
and alias forms), one ignored build-tag file, and a generated file excluded
before inventory. A missing first-party import produces a
visible partial map; malformed selected source produces a failed Markdown/JSON
pair even when cgo is active; package/source symlinks are rejected, including
an external `.go` link; artifact-path containment protects source. Missing or
old Go is a prerequisite failure with no promised artifact. The copied
selected-skill command runs outside the checkout
and contains no repository runtime or external Go-module dependency.

This is the second accepted use of `go list` package facts after
`propose-boundary`, but it does not justify extracting a shared helper: the
proposal's topology deferrals and candidate/caller-impact analysis differ from
this map's active-build inventory and durable-document contract. Reconsider a
generated, copied source-policy template only if a later accepted consumer has
the same package discovery, source-boundary, and closure requirements and it
reduces total maintenance code. Do not introduce `go/types` merely to broaden
this map's claim.
