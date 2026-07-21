# Go semantic-maintenance family learning packet

Status: implemented; fresh product-framed review and capability promotion are
still required.

## Useful outcome

This slice completes a detector-to-proposal journey and a separate rename
assessment:

1. `find-semantic-duplication` uses Go 1.22+ package and type facts to separate
   one bounded static review lead from caller/callee wrappers, near-clones,
   visible policy divergence, and dynamic-call uncertainty.
2. `unify-shadows` consumes exactly one complete confirmed record and emits a
   cited proposal without re-detecting or touching source.
3. `rename-concept` combines the existing strict-text companion with exported
   declaration/reference identity, while retaining locals, fields, aliases,
   external symbols, diagnostics, and inactive files as explicit boundaries.

The common principle is deliberately narrower than “semantic analysis.” Native
facts establish type identity and direct relationships; they do not establish
behavioral equivalence, workflow authority, domain meaning, or codemod safety.

## What transferred

- Use the host's native toolchain, never a downloaded or ancestor substitute.
- Freeze a final user artifact before choosing syntax or semantic facts.
- Make complete, partial, unsupported, and failed distinct.
- Keep proposals as structured consumers of accepted findings rather than a
  second detector.
- Replay the copied on-demand closure and fingerprint source around read-only
  work.

## What did not transfer

The two `go/types` consumers need different semantic models.
`find-semantic-duplication` needs result identity, returned-field shape,
resolved direct calls, token distance, and policy markers. `rename-concept`
needs exported declaration authority plus reference classification. Sharing a
result schema would obscure both contracts. `unify-shadows` needs no analyzer
at all.

## Tooling lesson

Repeated Go package bootstrap is now visible across several accepted skills:
tool/version discovery, `go list -deps -export`, export-data importing, active
source selection, and diagnostic handling. This is a credible tooling
candidate, but not yet a universal analysis service. The smallest safe future
experiment is a vendorable/bootstrap-only component whose exact bytes are
included in each selected on-demand closure. Trigger it when one real repair
must be applied consistently to two consumers; then prove both final artifacts
remain identical. Do not extract AST walks, result schemas, or skill policy.

## Transfer to later languages

- Java, C#, Rust, Swift, and Dart pilots should first define the final review or
  proposal artifact, then select the weakest native compiler fact that supports
  it.
- A proposal skill should normally consume an upstream structured result rather
  than loading the language compiler again.
- Rename completeness needs both lexical/prose coverage and symbol identity;
  neither substitutes for the other.
- “Confirmed” static evidence must be named according to its bounded meaning
  and accompanied by explicit human-review language.
