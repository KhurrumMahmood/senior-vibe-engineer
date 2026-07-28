# Real-repository mutation preview

Status: pass at product revision `f1216c4`

## Subject and proposed change

- Repository: `https://github.com/golang/example.git`
- Exact revision: `7f05d217867b2af52b0a28c6d1c91df97e1b5b39`
- Selected module: `hello/` (`golang.org/x/example/hello`)
- Closure: routed `move-path` checked-Go package move
- Preview only on the authoritative checkout: `reverse/` to `backward/`

The original module passed `go test ./...` before and after the journey. Its
Git status remained empty, its revision remained exact, `reverse/` remained in
place, and `backward/` was never created.

## Preview result

The external plan selected one leaf, non-`main` package-directory move. The
external report completed with no blocked or ignored records and exactly two
AST-attributed import edits:

1. `hello.go`: `golang.org/x/example/hello/reverse` becomes
   `golang.org/x/example/hello/backward`.
2. Moved `backward/example_test.go`: the same exact import rewrite.

The package declarations and symbol names remain `reverse`; this is a package
path move, not an unrequested symbol rename. The preview identified Go
1.26.5/gofmt, the module path, and the skill's Go 1.22 tool floor.

## Native and exact-after-tree obligations

The identical plan was applied only to a disposable exact-revision clone. The
closure proved:

- pre-mutation `gofmt -d` passed;
- the one directory move and two expected AST import changes were the complete
  source delta;
- post-mutation `gofmt -w` and `gofmt -d` passed;
- `go test ./...` passed for the root command and moved `backward` package;
- the exact virtual-after-tree oracle passed.

This disposable application demonstrates that the preview is executable while
keeping the authoritative source checkout read-only.

## Refusal and rollback

An invalid external plan attempted the same operation as a single-file Go
move. Dry-run returned `unsupported` with
`go_package_move_must_be_directory`; apply exited 1 before any source write.
The authoritative checkout remained clean and unchanged.

The focused rollback regression forced the post-mutation `go test ./...`
boundary to fail. The closure restored the original package directory and
rewritten consumer bytes and removed the proposed destination. Together with
the normal native application regression, the focused replay passed `2 passed
in 3.45s`.

## Acceptance conclusion

The real preview names the exact proposed delta; the disposable clone proves
the declared native and exact-tree obligations; invalid authority refuses
before writes; a forced postflight failure rolls back; and the pinned source
checkout is untouched. This satisfies real-repository plan criterion E3
without granting mutation authority over the corpus checkout.
