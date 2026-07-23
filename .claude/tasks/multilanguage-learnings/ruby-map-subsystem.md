# Ruby `map-subsystem` P7 learning packet

## Accepted bounded outcome

The cohort produces a durable paired map for one or more ordinary production
`.rb` targets in a locked plain-Ruby/gem host:

- `.claude/docs/subsystems/<name>.md`
- `reports/map/<name>/ruby-map.json`

The coverage-level contract is supported because the bounded static-map
implementation reaches its declared final outcome. The artifact intentionally
reports runtime `partial` completeness: project/configuration inventory
and hashes, selected targets, Prism module/class/method declarations, literal
`require`/`require_relative`/`load` calls, syntactic namespace/reopening and
mixin evidence, conservative constant candidates, and explicit native checks.
Semantic reachability remains `partial` because these facts do not prove Ruby
runtime identity.

The representative fixture maps `lib/billing`. It observes the literal
`invoice_service.rb -> invoice_registry.rb` edge, the conventional
`invoice_kit.rb -> billing/invoice_service.rb` load-path edge, one literal
`load` edge, three mixin spellings, two syntax definitions of
`Billing::InvoiceService`, and the lexical candidate from
`Billing::InvoiceService`'s `InvoiceRegistry` spelling to the declared
`Billing::InvoiceRegistry`. Every candidate is labeled as not runtime identity.

## Provider, native proof, and copied closure

`scripts/map_ruby.py` is one stdlib-only Python file. It uses the host-selected
Ruby 3.3+ runtime and its bundled Prism, plus Bundler 2.6+. It installs no gem,
contacts no package service, imports no sibling skill or repository runtime,
and does not use RBS/TypeProf merely because their executables are present.

The mapper runs `ruby --disable-gems -c` once per eligible production, test,
and executable input; frozen `bundle check` with isolated report-local config;
and only the explicitly named test and smoke files. The fixture's test prints
`native-test:ok`; the executable smoke prints the final JSON invoice label.
The focused test copies just `map_ruby.py` under a host `.agents/skills/`
directory, executes the full map outside the checkout closure, re-runs native
verification, and proves project source/configuration hashes are unchanged.

## Lifecycle and safety evidence

- Valid -> malformed/failed -> recovered runs replace the same Markdown/JSON
  destinations, so no successful declarations or errors survive improperly.
- Missing, too-old, and failing Ruby/Bundler probes are distinct unsupported
  terminal artifacts. Missing plain-gem metadata is unsupported; malformed
  Ruby, malformed Gemfile/frozen Bundler, failed test, and failed smoke are
  failed artifacts with nonzero exit.
- Repeated targets retain complete facts for valid production selections and
  record unsupported source roles/languages beside them.
- Generated, vendor, build, test/spec, entrypoint, signature, configuration,
  and symlink roles stay visible. Symlink source and target contents are never
  traversed.
- CLI targets cannot escape the project. Artifact paths are constrained below
  the durable map/report roots and reject symlink traversal before clearing or
  writing anything.
- `--expected-source-sha256` rejects stale input. A second manifest after all
  tool probes and native runs detects source/configuration mutation.

## Honest Ruby boundary

The output never promotes Prism syntax into a call graph. Dynamic
`require`/`load`, load-path changes, autoload, Rails/Zeitwerk, `const_get`,
`const_missing`, `send`/`public_send`, `method_missing`, eval variants,
`define_method`, refinements, runtime reopening/monkey patches, callbacks,
native extensions, framework DSLs, and generated code remain explicit
non-claims. Where Prism can see a relevant call shape, the artifact records a
dynamic signal and leaves the corresponding completeness partial.

Static class/module duplicates are evidence that reopening syntax exists, not
that every runtime reopening or execution order is known. A mixin constant is
a spelling in a lexical owner, not proof that the module resolved or applied.
Likewise a conventional `lib/` load match is a literal layout edge, not proof
that `$LOAD_PATH` or a framework loader used it at runtime.

## Measured economics

Measured on the final focused cohort before commit:

| Metric | Value |
|---|---:|
| Copied provider files | 1 |
| Copied provider bytes | 36,753 |
| Copied provider SHA-256 | `1e49afca79846c2475664ba248b77d99b0a406b78dec8c958d2e4fbec5d79c01` |
| Ruby adapter physical LOC | 899 |
| Ruby adapter nonblank LOC | 813 |
| Ruby final-outcome test physical LOC | 443 |
| Ruby final-outcome test nonblank LOC | 385 |
| Adapter + test physical / nonblank LOC | 1,342 / 1,198 |
| Fixture regular files / bytes | 22 / 3,234 |
| Fixture manifest SHA-256 | `bf1d5dc8dc441e1a86ad25902979b343252d313284ac07be144779427ce56979` |
| Final focused Ruby map run | 13 passed in 14.75 s |
| Ruby map + spine + root-independent profile gates | 31 passed, 1 root-census test deselected |
| Root-independent inventory gates | 3 passed, 1 root-census test deselected |
| Doctor/lifecycle/skill conformance gates | 23 passed |

The fixture manifest hashes sorted regular-file rows as `relative path + NUL +
content SHA-256 + newline`. The copied provider is the executable closure;
knowledge, fixture, and tests do not travel with it at runtime.

## Transferable seams and local mechanics

Transferable final-outcome seams are paired atomic artifacts, explicit
terminal states, same-destination stale clearing, source manifests before and
after external tools, optional caller-provided snapshot hashes, role-aware
symlink refusal, mixed-target rows, copied execution, and final native output
assertions.

Ruby-local mechanics are Prism's syntax tree, lexical namespace candidates,
class/module reopening evidence, include/extend/prepend spelling, conventional
gem `lib/` matching, separate `ruby -c` invocations, and frozen Bundler state.
They do not justify a shared semantic graph. A later consumer should reuse the
questions and lifecycle, not this parser or Ruby's candidate-resolution rules.

## Minimal root integration

This lane intentionally does not edit shared surfaces. Root integration should:

1. add Ruby to `map-subsystem` frontmatter/description, the orchestrator branch,
   installed command, success criteria, and a pointer to `knowledge/ruby-v1.md`;
2. publish `map-subsystem` as `ruby-supported` only after the consolidated copied
   closure and existing-language regression replay passes;
3. update the two already-known generic census expectations: add `ruby` and
   `.rb: ruby` in `test_language_support_profile.py`, and add `ruby` to the
   ordered inventory-language expectation in `test_source_inventory.py`; and
4. update Ruby coverage/router/matrix/ledger artifacts centrally without
   widening the claim to Rails/Zeitwerk or runtime reachability.

The lane started the 55-test cross-language map family and observed 42 passing
tests before stopping it at root's request to avoid duplicate Swift/Java tool
contention. That interrupted run has no final-suite claim; root owns one
consolidated post-integration replay.
