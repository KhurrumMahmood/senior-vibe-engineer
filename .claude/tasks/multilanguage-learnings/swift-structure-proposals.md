# Swift structure-proposal learning packet

## Bounded result

- `propose-boundary` consumes one final confirmed Swift omnibus row plus one
  current complete `swift-semantic-facts-v2` pack. Its supported fixture moves
  exactly `loadExports`, `saveExports`, and `renderExports` behind internal
  `ExportOperations`, while the original public `DomainOperations` methods
  remain same-module shims.
- `propose-folder-reorganization` consumes one final Swift topology row plus
  the same fact-pack contract. Its supported fixture moves exactly four direct
  `Billing*.swift` siblings into the SwiftPM target's recursive `Billing/`
  subfolder without changing `Package.swift`, target/module identity, type
  identity, or API signatures.
- Candidate acceptance and proposal acceptance are separate, content-addressed
  verdicts. A proposal verdict cannot silently substitute for acceptance of the
  producer candidate or compiler fact closure.
- The shared helper is local to the two real proposal consumers. It validates
  accepted inputs, derives the exact plan, and runs the existing schema-v2
  provider only on disposable current/after trees; it does not discover scope.

## What generalizes

- Bind human authority to both the detected candidate and the fully derived
  proposal. Recompute both hashes at consumption time.
- Replaying the accepted current tree before testing the after tree catches
  tool or fact drift that an after-only build can hide.
- File moves change location-derived compiler IDs. Compare moved declarations
  and resolved edges by stable logical declaration shape plus the explicit
  source-path mapping, not by raw IDs.
- Refusal bundles must atomically replace prior success bundles and contain no
  declarations, callers, references, moves, edits, creates, or native-success
  claims. A repaired acceptance must recover at the same destination.

## Nonclaims and stop conditions

- Compiler-resolved calls/references do not prove dynamic dispatch,
  reflection, macro expansion, generated code, external callers, ABI, or
  release compatibility.
- Xcode projects/workspaces, mixed-language targets, protocols/conformances,
  actors, Objective-C/dynamic dispatch, macros/conditional compilation, and
  ABI-sensitive annotations are refused rather than approximated.
- The native result covers only Apple Swift 6.3.3, the selected dependency-free
  SwiftPM library target, the named configuration/products, and exact expected
  check/smoke output.
- The artifacts are read-only proposals; they grant no source mutation or
  release authority.

## Focused proof

Use the product runtime explicitly:

```bash
/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python -m pytest -q tests/test_swift_structure_proposals.py # host-ref-allow: task-pinned product runtime
```

The fixture proves accepted boundary/folder outcomes, copied-skill closure,
independent scope application, host-source preservation, atomic
valid-refused-valid replacement, stale/tampered refusal, unsupported-condition
refusal, unsafe-output refusal, and native-failure refusal.
