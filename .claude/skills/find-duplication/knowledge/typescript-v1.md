# TypeScript v1 evidence boundary

## Invariant

When substantially repeated TypeScript text appears in eligible production
source, give a reviewer one stable lexical-cluster artifact with the original
source ranges and enclosing symbols that can be mapped reliably. The artifact
must not claim behavioral equivalence, ownership compatibility, or a safe
consolidation.

## Tool decision

`jscpd@4.0.5` is the family-local detector because the accepted outcome is
lexical/near-lexical cloning, not type-aware analysis. The wrapper pins the
version, stages only eligible source, and uses stock `npx --offline` plus an
explicit npm cache. This is deterministic once a host has deliberately
provisioned the cache, and it fails rather than reaching the network during an
audit.

The accompanying Python span mapper is deliberately narrow. It masks comments
and strings, identifies function declarations and block-bodied arrow functions,
and discards a clone pair unless each complete range fits one real source
symbol. It retains exact occurrence ranges and joins raw pairs only when their
occurrences overlap, rather than joining every pair that happens to name the
same file and symbol. It is a family-local formatter/validator for jscpd
ranges, not a reusable TypeScript parser.

The wrapper validates the emitted jscpd 4.0.5 JSON schema before path
normalization or completion metadata: an object with statistics, a duplicate
list, and valid duplicate file/range records. A zero exit plus malformed JSON
is a detector failure, not a clean scan.

## Rejected alternatives

- A shared Compiler API service: too broad for one lexical consumer and would
  require a named TypeScript runtime/module-resolution contract.
- Regex-only duplicate detection: would duplicate jscpd's mature near-clone
  tokenization while being less trustworthy about clone thresholds.
- Runtime `npx` network fallback: makes the result depend on network state and
  violates the copied-install/offline replay contract.
- Reporting module-level or guessed enclosing symbols: would make spans look
  more precise than this lexical v1 can prove.

## Boundary reminders

- Exclude generated, tests, declarations, vendor, build, and dependency trees.
- Drop overload signatures, even if a raw jscpd input contains them.
- Keep behaviorally different code clean when it has no lexical clone evidence.
- Treat every reported cluster as a human-review lead, never a change request.
