# Swift accepted shadow proposal

`unify-shadows` consumes the existing complete Swift A3 fact pack, accepted
`find-semantic-duplication` analysis, and a separate content-addressed human
acceptance. It does not import or run detection and does not parse or scan
Swift source. The accepted disposition must be compatible with the upstream
verdict; keeping the pair separate is a complete outcome.

The consumer is product-agnostic: it rejoins each accepted definition and all
accepted callers through schema-v2 `resolved_calls` and their exact
`containing_caller` identities, then derives the constructed type, initializer
owner/overload/labels, return shape, shared callees, and caller sets from the
hash-bound finding and fact pack. It proves this for both
`buildStatement`/`summarizeInvoice` with `Statement(label:total:)` and
`makeReceipt`/`summarizeReceipt` with `Receipt(cents:code:)`; no type or field
names are embedded in the proposer. The real `wrapperDecoy`, `Void`, and `Int`
callers remain visible, while typed factory-reference decoys do not become call
sites.

Freshness and authority bind the facts, source manifest, accepted analysis,
candidate, provider, proposer, all boundary verdicts, and all eight successful
native evidence rows. A successful or refused run atomically replaces exactly
`proposal.md`, `evidence.json`, and `scope.json`, removes stale artifacts, and
preserves host source bytes. Refusal scope is deliberately claim-free.

The focused copied-closure test covers proposal, keep-separate, incompatible
verdict, tampered analysis, stale facts, unsafe output, every invalid boundary
gate, refusal replacement, and valid-invalid-valid recovery. Static compiler
shape remains insufficient for behavior, runtime equivalence, dynamic or
protocol dispatch, concurrency isolation, generated or conditional inputs,
external callers and package variants, framework/resource/error semantics,
ABI approval, source mutation, or release authority.
