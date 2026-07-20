# Go `find-complexity-hotspots` learning packet

The P3 detector is a read-only, syntax-only Go pilot. Its bundled
`detect_go_complexity.go` uses only `go/parser`, `go/ast`, `go/token`, and
`ast.IsGenerated` through the host Go toolchain; Go >= 1.22.0 is required and
discovered from `PATH`. Local verification used Go 1.26.5 at
`/opt/homebrew/bin/go`, but the installed command never hardcodes that path.

It emits `high-branch-function` only for named functions and receiver methods.
The score counts direct `if`, `for`, `range`, `switch`, type-switch, `select`,
`&&`, and `||`; nested function literals are excluded. The existing threshold
is unchanged. It does not resolve packages/imports, types, interfaces, calls,
or framework facts, so it remains a `measure-first` structural lead.

The locked Go module proves two positive score-18 shapes, a clean negative,
nested-function exclusion, `_test.go`, vendor, generated path/name/marker,
malformed source, missing/old toolchain, source immutability, `gofmt -d`,
`go test ./...`, and an isolated copied skill run. Explicit `//go:build` and
legacy `// +build` files are deliberately withheld as
`build-constraint-ambiguous`; successful reports are `partial` rather than
clean and retain the limitation in JSON and Markdown.

What transferred: final-artifact tests, host-native tool preflight, explicit
analyzer provenance, direct-target exclusion tests, copied closure, and source
fingerprints. What did not: the TypeScript walker, receiver formatting,
generated-file conventions, and build-constraint behavior. Keep the Go
launcher family-local until a second accepted Go consumer needs the exact same
toolchain, source-boundary, failure, and selected-install closure.
