# Go final language-level coverage learning packet

Status: accepted at `2b83ccd` and `7f3da12` after focused product review and
preserved TypeScript behavior. A requested blank-context review could
not be allocated because the task-thread limit was full; an independent
existing product-review lane supplied the final adversarial check.

## Useful outcomes

`find-incomplete-sweep` now turns resolved direct Go calls into a deliberately
narrow review lead. It requires keyed option-struct literals, a four-call/75%
majority, exactly one omission, one consistent comparable value, and newer Git
trajectory at every present site. The detector never declares the omission a
bug: its manifest feeds the existing scout packet, human verdict, and triage
workflow.

`propose-folder-reorganization` treats a Go directory as a package boundary,
not a filename container. Three matching filenames are only navigation
evidence. A move plan becomes ready only when an explicit project convention
authorizes that exact internal-package split and language constraints do not
block it. The plan is read-only, scopes import impact to the current module,
and names `go test ./...` plus `go vet ./...` as before/after obligations.

## What transferred

- Use the host's Go 1.22+ toolchain and compiler facts; do not download an
  analyzer or import repository-only runtime code.
- Keep selected on-demand closures self-contained and replay their documented
  commands outside the source checkout.
- Distinguish complete, partial, unsupported, failed, blocked, and deferred
  outcomes instead of weakening a claim to obtain broad support.
- Treat native facts as evidence. Git history does not establish intent, and a
  filename threshold does not establish a desired package boundary.
- Scope whole-project analysis to first-party module packages. Dependency
  export data may support type checking, but dependency source is not a
  current-module impact surface.
- A first-party package graph with unresolved compiler facts cannot support a
  complete impact claim, even when the target package itself parses.

## What remains family-local

The two tools share Go bootstrap mechanics but not a useful result model. Call
grouping, Git trajectory, and human-verdict packets belong to incomplete-sweep.
Convention precedence, package-boundary blockers, move rows, and import impact
belong to folder proposals. Sharing those policies would make both skills less
clear.

Repeated bootstrap code is now a credible future extraction candidate, but the
project's abstraction gate still applies: wait until one concrete repair must
be made in two installed consumers, then extract only the vendorable bootstrap
or path primitive and replay both final outcomes.

## Transfer to later languages

- Define the final user artifact before choosing compiler APIs.
- Separate language safety from project or framework conventions; neither
  should silently override the other.
- A history heuristic should feed human judgment, not mutation authority.
- For folder work, model the language's real compilation/package boundary and
  its framework conventions before applying generic filename heuristics.
- Keep move execution separate from read-only impact planning, and verify the
  host's native build/test obligations before and after any mutation.
