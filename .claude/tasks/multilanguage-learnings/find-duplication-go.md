# Go `find-duplication` learning packet

G1D proved a deliberately narrow Go duplication path. A copied on-demand
`find-duplication` closure discovers Go 1.22+ from `PATH`, invokes one bundled
stdlib-only `go/parser` helper for all eligible files, and fingerprints
`go/format`-normalized bodies of named functions and receiver methods. It uses
no npm package, network access, repository import, type checker, or shared
analysis platform.

The evidence boundary matters more than the detector size. Exact matching does
not prove equivalent behavior, compatible callers, or a safe consolidation.
The final triage therefore tells the agent not to consolidate automatically.
Same-file pairs are labeled separately from cross-file pairs so the report and
ranking do not overstate blast radius.

The fixture and copied-closure replay prove cross-file and same-file positives,
a different-body negative, `_test.go`, testdata, vendor, generated markers,
ordinary names containing an OS token, explicit and implicit build constraints,
malformed source, missing/old Go, and source immutability. Generated-only targets
are unsupported rather than falsely clean. Build-constrained omissions produce
a `partial` status and an explicit warning in the final Markdown, not only JSON.

What transfers to another language is the workflow: batch native parsing,
classify exclusions before interpreting zero findings, preserve limitations at
the final human-facing boundary, replay the selected copied closure, and rerun
prior-language branches. Go AST details, receiver formatting, and build filename
rules do not transfer. Keep this implementation family-local; revisit a shared
source-policy helper only after another accepted Go skill needs the same exact
behavior and measured repetition creates a real maintenance cost.
