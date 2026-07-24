# Swift A3 compiler-AST semantic read-only family

Status: accepted in the isolated Swift lane, pending root publication. This
lane does not edit shared routers, matrices, catalogues, profiles, READMEs, or
the execution plan.

## Foundation decision

SourceKit-LSP is not the semantic foundation. Its advertised stable requests
were not reproducible on a cold Command Line Tools installation. Pinned Apple
Swift 6.3.3 `swiftc -typecheck -dump-ast`, by contrast, completed over the
multi-file fixture in 1.29 seconds cold and 0.66 seconds repeated. After
absolute-root and process-address normalization, both runs produced the same
SHA-256. With an explicit same-name `Statement.init(total:label:)` overload,
the cold/repeated runs remained 1.18/0.56 seconds and shared normalized SHA-256
`fdc0f36dc670be4868e9846c9ece232e3abce4d66780d955e15002596986a4d3`.

The compiler output proves exact declaration signatures and source identities,
direct declaration references/calls, selected overload declaration and
interface type, omitted default arguments bound to their exact owner/parameter,
member assignments paired with direct string literals, and static function
return/callee/constructor shape. Comments and string rename decoys are absent
from resolved compiler references. Malformed source fails with a compiler
diagnostic in 0.61 seconds; a missing or non-6.3.3 compiler produces a terminal
non-complete pack.

## Five outcomes

One content-bound Swift-local fact pack supports five read-only consumers:

- `find-dormant` emits review-only zero-direct-reference private function
  candidates while reflection/string spellings defer promotion.
- `find-implicit-state` emits compiler-resolved direct `String` field literal
  operations and requires candidate-hash-bound human acceptance.
- `find-incomplete-sweep` binds direct call sites to one defaulted-argument
  declaration before Git trajectory and packet-hash-bound human triage.
- `find-semantic-duplication` compares compiler-resolved constructor and direct
  callee identities plus static return shape. It derives incoming caller sets
  from schema-v2 `resolved_calls` and exact `containing_caller` identities, so
  ordinary `Void` and other-return callers remain visible while callable
  references do not become calls. Lexical clones, resolved wrappers, and
  mismatched policy callees remain rejected.
- `rename-concept` separates exact old/new type references from comments,
  strings, excluded roles, and unrelated lexical matches, and applies no edit.

The positive fixture yields exactly `dormantDiscount`, `Job.state`, the omitted
`charge` audit argument, two independent duplication leads
(`buildStatement`/`summarizeInvoice` constructing `Statement(label:total:)` and
`makeReceipt`/`summarizeReceipt` constructing `Receipt(cents:code:)`), and the
`LegacyStatus`/`CanonicalStatus` assessment. Ordinary `Void` and `Int` callers
are retained for those leads; typed factory-reference decoys are absent from
their caller sets. The clean target reaches complete empty outcomes for all
five.

## Contract and lifecycle

The provider requires a dependency-free SwiftPM regular target, exact Apple
Swift 6.3.3 `swift`/`swiftc`, strict Swift Format, one selected debug or release
configuration, at most 32 selected production files, at most 8 MiB of compiler
AST output, and a 20-second compiler-AST timeout. SwiftPM package/target/source
identity, query plan, toolchain, source hashes, and normalized AST hash are
content-bound.

Every complete pack proves restrictive `dump-package`, `describe`, build,
per-file compiler parse, strict format lint, exact check output, exact smoke
output, and one offline selected-target compiler-AST run. Check and smoke
executables remain separate SwiftPM targets; they are native verification, not
inputs to the selected module AST invocation. No network access or dependency
installation is used.

The copied closure consists only of the provider and seven consumer scripts,
runs with isolated/no-site Python, contains no checkout path, and reaches all
five final artifacts. Missing/old tools, failed builds, malformed manifests,
malformed compiler input, nonfresh supplied state, malformed facts, stale
source hashes, invalid reviews, and valid-invalid-valid recovery are tested.
Outputs replace atomically, stale promoted artifacts disappear, and host source
fingerprints remain unchanged.

## Limits and guidance

This is selected static SwiftPM evidence, not whole-program proof. Conditional
compilation, macros/plugins, generated inputs, reflection, selectors,
Objective-C or dynamic dispatch, protocol/existential runtime dispatch,
external consumers, Xcode schemes/workspaces, Apple frameworks, resources,
dependencies, mixed-language targets, Unicode identifiers, behavior,
reachability, deletion safety, refactor safety, and mutation authority remain
outside the claim.

The reusable lesson is narrow: prefer a bounded compiler output that survives
cold replay over a richer advertised protocol that does not. Normalize only
nondeterministic transport data, retain exact declaration/signature locations,
and make adversarial overload/default/decoy fixtures part of the acceptance
test before any downstream proposal work.
