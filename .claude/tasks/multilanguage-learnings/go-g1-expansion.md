# Go G1 expansion learning

G1 moved Go coverage from three pilot skills to eleven of the twenty-two
language-level skills. Eight additional skills now reach their actual user
artifact from copied on-demand closures, pass the locked module's native tests,
and preserve source bytes for read-only work.

The main transferable pattern is outcome-level, not AST-level: inventory the
whole first-party source boundary, state what is excluded or unresolved, use
the smallest native parser needed by that skill, and verify the final report.
The Go-specific details were less uniform. Audit must fail atomically on one
unreadable source file; standards coverage can retain a useful partial report;
omnibus refuses build selection it cannot establish; and explanation keeps
aliases and constrained files visible as unexplained regions.

Fresh review exposed the reusable Go fixture checklist. Include explicit and
filename build constraints, generated files whose marker follows long line or
block comments, `_test.go`, `testdata`, fixtures, vendor/dependency trees,
narrowed targets, malformed source, missing/old tools, and ordinary filenames
that merely contain a platform token. Generated classification must precede
build classification, and only the final filename suffix carries an implicit
GOOS/GOARCH constraint.

The review also established a general artifact-lifecycle lesson: a failed
target-keyed rerun must invalidate every prior user-facing artifact, but cleanup
must first prove that its output is a real artifact file—not source, a source
directory, or a symlink escape. `explain-code` now publishes `latest` only
after the final document and sidecars succeed.

There is repeated Go source-policy code now, but a shared runtime helper would
make selected skills depend on a hidden repository import. Keep the launchers
family-local. Reconsider a generated/tested source-policy template only when it
reduces total code and the installer can carry each consumer's explicit closure.
Do not build a universal parser or introduce `go/packages`/`go/types` until the
semantic cohort demonstrates shared project facts across at least two skills.
