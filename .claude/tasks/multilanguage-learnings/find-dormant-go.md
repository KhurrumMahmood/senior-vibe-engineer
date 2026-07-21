# Go `find-dormant` learning packet

## Accepted v1 outcome

Go v1 writes `reports/find-dormant/<scan>/report.md` and `findings.json` for
**unexported package-level functions and function-valued variables** with zero
`go/types`-resolved uses in the selected active-build package. Every result is
`review_required` and `human_review_only`; `certain_delete` is always zero.
Methods and types are deliberately excluded.

This is a static review queue, not a dead-code deletion decision. Exact
matching strings and `//go:linkname` references become `uncertain`; reflection,
generated registration, plugin loading, cgo, and assembly are documented
runtime boundaries. Build-constrained, cgo, missing-package, and unavailable
type facts produce a visible `partial` report rather than a clean result.

## Tool and closure decision

The copied `find-dormant` root contains a small Python launcher plus one
batched Go helper. The launcher resolves Go 1.22+ from `PATH`, validates
project/report containment, invokes one `go run` helper over the requested
target, and atomically writes the final Markdown/JSON. The helper uses only
the host toolchain and Go standard library: `go list -deps -export`,
`go/parser`, `go/types`, and `go/importer`.

`go/packages` was not added: this v1 needs only active-package file selection,
export data for imports, and in-package object uses. The helper is family-local
because its review-only candidates, uncertainty schema, and no-deletion report
do not match any accepted Go consumer. No shared `go list`/`go/types` platform
was created.

## Locked proof

`tests/test_find_dormant_go.py` uses `tests/fixtures/find-dormant-go` and
proves the final artifact, source hashes, host `go test ./...` before and after,
copied isolated closure, direct static-reference negatives, method/type
exclusion, generated registration uncertainty, string uncertainty, malformed
source, missing/old Go, build partiality, direct vendor exclusion, and report
symlink rejection.

The fixture includes a private positive and function-valued-var positive;
direct use, exported API, and `http.HandleFunc` registration stay clean because
their identifier references resolve. A generated file referencing the private
function is intentionally excluded from use resolution and is surfaced as a
runtime uncertainty, never as proof of dormancy.

## Translation limits

This branch does not resolve interface dispatch, methods, types, reflection,
linker directives, generated registration, plugins, cgo, assembly, cross-build
configurations, or runtime/external consumers. It should not grow into a
deletion assistant. Reconsider shared Go project facts only after a second G2
skill demonstrates the same selected-install closure and an identical fact
contract.
