# Ruby A5 `move-path` learning

## Outcome

The frozen Ruby mutation cohort now reaches one useful final outcome: move
`lib/billing/invoice_registry.rb` to
`lib/invoicing/invoice_registry.rb`, change the declared namespace from
`Billing` to `Invoicing`, update the resolved `require_relative` consumer, and
rewrite the statically attributable `InvoiceRegistry` reference. The native
test still prints `native-test:ok`, and the executable smoke still prints
`invoice:INV-42:125`.

Dry-run is source-preserving and writes content-addressed evidence. Apply
requires both that evidence file and its reviewed SHA-256. Check requires the
same evidence and proves the completed tree. A changed plan, source byte, file
mode, tool binary, or adapter makes the authority stale before mutation.

## Native and mutation boundary

The standalone `ruby_module_move.py` adapter requires Ruby 3.3+, Bundler 2.6+,
and bundled Prism. It runs per-file `ruby --disable-gems -c`, a frozen
`bundle check` with configuration outside the host and dead proxies, the
declared direct native test, and the declared smoke command before and after
mutation. The whole host—regular-file bytes and modes plus symlink targets—is
fingerprinted against the exact virtual after tree.

Any post-mutation native failure or out-of-plan write restores the complete
pre-apply snapshot. Focused tests inject both cases and require exact rollback.
They also prove complete → failed → complete report reuse clears prior mutation
authority, stale evidence refuses without writes, and a copied single-file
adapter runs outside this repository under isolated/no-site Python.

The honest refusal boundary includes relevant dynamic `require`, `autoload`,
`const_get`/`const_missing`, constant reopening, non-relative `require`/`load`,
Rails or Zeitwerk ownership, relevant excluded-source identity, symlinked move
paths, malformed Ruby, and missing/old/broken tools. Unrelated dynamic Ruby in
the frozen host remains preserved and does not become a global refusal. The
adapter rewrites only exact literal `require_relative` targets and reviewed
constant identities; it does not infer Ruby runtime identity from a path.

## Reuse decision

Ruby mutation policy stays in one standalone stock-selected script. It does
not modify the generic mover or create a shared mutation platform. Snapshot,
authority, report, and rollback vocabulary resemble the accepted Rust and Dart
cohorts, but Ruby constant lookup, load behavior, reopening, framework
autoloading, and native commands are language-local. No second Ruby mutation
consumer demonstrates a safe extraction seam.

The focused implementation is 985 adapter lines plus 574 test lines (1,559
physical / 1,397 nonblank lines, 58,869 bytes). It reuses the unchanged frozen
12-file, 2,700-byte Ruby fixture, whose sorted
`relative-path + NUL + file-SHA-256 + LF` manifest is
`3b7ec6d29a5c02d1fa7c7a32cdedddb410310185a0db81ea0533832b6b7af118`.
The final focused replay passes 19 tests.

## Limits

This is not a Rails/Zeitwerk migration, a class or method rename, a directory
move, an autoload-path change, a general constant resolver, or a framework
codemod. It does not rewrite strings, comments, reflection, `eval`,
metaprogramming, variable loads, generated/vendor/build sources, or runtime
dispatch. Broader Ruby mutation support requires a new representative cohort
and its own final-output evidence.
