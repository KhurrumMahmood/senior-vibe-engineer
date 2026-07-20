# Go `propose-boundary` learning packet

## Accepted Go v1 contract

The Go proposal path is a read-only, family-local command. It discovers a
PATH Go tool at version 1.22 or newer, uses `go list -e -json -mod=readonly
./...` to establish the active root-module package/import graph, and uses only
`go/parser` and `go/ast` for target declarations, import syntax, and local
call candidates. It writes `inspection.json` and `proposal.md` under
`reports/propose-boundary/<name>/`.

A recommendation requires two named top-level symbol domains, a resolved Go
package import path, and complete first-party direct/alias importer evidence.
The proposal lists uppercase API candidates, package-private cross-domain call
candidates, a temporary package-facade compatibility plan, and `gofmt` plus
`go test ./...` verification. It never edits source.

## Tool and closure decision

`go list` is necessary because parser-only import text cannot establish the
active package path or module-selected importer graph. `go/packages` is not
used: it is an external `golang.org/x/tools` dependency and would make a
copied, offline selected-skill closure depend on a module cache or network.
`go/types` is intentionally not introduced because this outcome needs
package/import facts, not a new semantic platform. Local call evidence is
therefore labelled `syntax_candidate` rather than resolved call identity.

The installed command runs the bundled `propose_go.go` via the host `go` tool.
It has no toolkit Python, sibling-skill, shared-script, third-party module, or
network import. Missing Go prints an explicit unsupported status before it
attempts `go run`; an old Go writes unsupported evidence. Malformed source
writes failed syntax evidence and exits nonzero.

## Locked evidence

`tests/fixtures/propose-boundary-go/` contains standalone `go 1.22` modules:

- `positive`: a `quote`/`settlement` package with direct and aliased importers,
  tied candidate scores, exported API candidates, and a package-private
  cross-domain call.
- `cohesive`: a one-domain shipping package that defers.
- `ambiguous` and `ambiguous-caller`: build-tag and dot-import evidence that
  must defer.
- `unresolved`, `malformed`, and `excluded`: package resolution failure,
  parser failure, and generated/vendor must-not-fire targets.

The focused suite fingerprints Go source and module files before/after the
proposal, runs `go fmt ./...` and `go test ./...` on the positive fixture, and
copies only `propose-boundary` into `.agents/skills/` before running the exact
documented command.

## Limits and follow-up

Go v1 does not claim support for build matrices, cgo, workspaces, `replace`,
reflection, interface dispatch, dynamic runtime behavior, external consumers,
or `go/types` symbol identity. It also does not treat package-private calls as
external private imports: they are human-reviewed migration blockers for a
future package split. Keep this resolver local until a second accepted
consumer proves the same package/import facts and copied offline closure are
actually reusable.
