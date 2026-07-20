# move-path Go pilot learning

The Go mutation pilot deliberately supports one leaf, non-`main` package
directory move inside one root module. The only automated code edits are exact
`ImportSpec.Path` string literals established by `go/parser`; aliases, package
names, and comments remain unchanged.

The copied `move-path` skill carries a small Go helper and uses host `go` and
`gofmt` without installing dependencies. It discovers the root module and its
declared Go version, rejects workspaces and nested modules, and runs targeted
`gofmt`, an exact after-tree source oracle, and `go test ./...`. Any failed
post-apply check restores the moved tree and rewritten files.

Generated/vendor/cgo/build-tag/generator/symlink/package-tree cases are not
partial implementations of a refactor engine: they return unsupported before
writes. A detected old module path outside an import literal is partial because
it may be a runtime or generated-path reference; it is never rewritten.

Reusable: virtual after-tree movement, explicit status/reporting, copied-skill
closure, and transaction rollback. Non-transferable: TypeScript/JavaScript
resolver behavior and Go workspace or symbol semantics. A later Go expansion
needs separate evidence, not an extension of this pilot by default.
