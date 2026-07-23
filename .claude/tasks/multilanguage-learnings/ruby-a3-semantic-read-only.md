# Ruby A3 RBS semantic read-only family

Base revision: `4e3aa410a3f14d1957a5fd7eeb94b3926e3ea6e9`

## Bounded outcome

This packet adds one Ruby-local, copied external-library provider and five
separate read-only consumer artifacts for a locked plain Ruby gem that already
owns `sig/**/*.rbs`:

| Skill | Useful final artifact | Bounded value |
|---|---|---|
| `find-dormant` | `reports/find-dormant/ruby/findings.json`, `report.md` | A private RBS method with one non-reopened source definition and no direct selected-source call becomes a review-only dormant candidate. |
| `find-implicit-state` | `reports/find-implicit-state/ruby/findings.json`, `report.md` | An RBS `String` state attribute, one project-owned literal alias, and matching direct source writes becomes a candidate-hash-bound human review request. |
| `find-incomplete-sweep` | `reports/find-incomplete-sweep/ruby/findings.json`, `report.md` | One RBS optional constructor keyword with at least two direct selected-source uses and exactly one omission becomes a review-only sweep gap. |
| `find-semantic-duplication` | `reports/semantic-duplication/ruby/analysis.json`, `triage.md` | Two non-reopened public methods with the same location-free RBS method-type shape, identical direct body spelling, and distinct direct source caller contexts become a candidate-hash-bound lead. |
| `rename-concept` | `reports/rename-concept/ruby/assessment.json`, `assessment.md` | One RBS declaration and one direct source declaration for a new name, alongside any retained old declaration, assesses a staged rename without editing it. |

`_ruby-semantic/ruby_semantic_facts.py` validates project-authored RBS with
`rbs --no-collection -I sig validate`, reads only the local RBS AST with
`rbs --no-collection --no-stdlib -I sig ast ...`, and runs a Ruby 3.3+
Prism source collector strictly for spans, direct spelling, source roles, and
dynamic-boundary inventory. It also requires per-file `ruby --disable-gems -c`,
frozen Bundler `check`, and the supplied native test/smoke commands. RBS is the
semantic authority; Prism does not resolve a call, constant, type, or load.

The focused fixture has 21 regular host files / 4,728 bytes, with manifest
SHA-256 `5530a648761b14e795cc71b33442c17935ae5be3fdc6b9fab1715f47bcfcac0c`.
The copied provider is one 31,582-byte file with SHA-256
`b8fe8579fd6b1f7adbbd595244a6998f0ff5c16a4e1fc8235f48edea7a311171`.

## Boundary and lifecycle evidence

The fixture proves positive output, valid clean output, generated/vendor/build
decoys, a visible untraversed symlink role, dynamic `public_send` in a separate
owner, stale fact-pack rejection, stale candidate-hash verdict rejection,
valid-to-malformed-RBS replacement at the same destination, recovery, copied
isolated execution, and source preservation.

The provider distinguishes missing, too-old, and failing Ruby/Bundler/RBS
tools; missing project RBS signatures; malformed RBS; malformed Ruby;
missing project metadata; frozen Bundler failure; native test/smoke failure;
and unexpected source mutation. Incomplete evidence writes a fresh `partial`
artifact and exits `2`; execution/native failures write a fresh `failed`
artifact and exit `1`. It does not install a gem, update a lockfile, resolve a
collection, or use network.

The RBS command is deliberately project-owned configuration evidence, not an
ambient fallback. No `sig/**/*.rbs` tree means every A3 consumer safely defers;
the absence of RBS, Sorbet, or Steep is never an unsupported-language claim.
The representative host uses Ruby 3.4.1, Bundler 2.6.2, Prism 1.2.0, and RBS
3.4.0 already installed on the developer machine.

Explicit non-claims remain: Ruby dynamic dispatch; `send`/`public_send`;
reflection; `const_get`/`const_missing`; callbacks; `method_missing`; eval;
`define_method`; refinements; reopening; monkey patches; dynamic load and
`$LOAD_PATH`; autoload; Rails/Zeitwerk; framework DSLs; external APIs; native
extensions; runtime identity; true reachability; closed state domains;
behavioral equivalence; safe deletion; safe consolidation; and safe rename.

## ML-025 economics

The comparison counts the provider, the five adapters, and their focused
family test. A literal design means each adapter/test closure owns a complete
copy of the same RBS/Ruby/Bundler/Prism/roles/lifecycle/native fact producer;
it does not posit a universal semantic schema.

| Metric | Shared Ruby-local design | Five literal producer copies |
|---|---:|---:|
| Provider physical LOC (`H`) | 835 | 4,175 |
| Adapters + focused test (`C`) | 1,509 | 1,509 |
| Maintained physical LOC (`C + H` / `C + 5H`) | 2,344 | 5,684 |
| Maintained LOC reduction | 58.76% | — |
| Copied provider + adapter union bytes | 76,167 | 202,495 |
| Union closure reduction | 62.39% | — |
| Individual consumer closure growth | 0.00% | baseline |

Five warm disposable-host trials ran the identical provider plus five
fact-consuming adapters against five separate adapter runs that each collected
their own full fact pack. Shared seconds were `1.862093`, `1.820464`,
`1.789629`, `1.792900`, and `1.822612`; literal seconds were `8.237548`,
`7.921660`, `8.402381`, `8.357918`, and `8.634325`. The medians are
`1.820464s` shared and `8.357918s` literal: **-78.22%** median latency. The
provider clears the ML-025 LOC, closure, and latency gates.

This is library-level fact reuse, not a claim that a normal multi-lens request
is batched: each adapter can still collect its own fact pack when `--facts` is
not supplied. There is no cache, daemon, universal Ruby graph, cross-language
AST, shared consumer verdict schema, or mutation helper.

## Verification

```text
.venv/bin/python -m ruff check \
  .claude/skills/_ruby-semantic/ruby_semantic_facts.py \
  .claude/skills/find-dormant/scripts/detect_ruby_dormant.py \
  .claude/skills/find-implicit-state/scripts/detect_ruby_state.py \
  .claude/skills/find-incomplete-sweep/scripts/detect_ruby_incomplete_sweep.py \
  .claude/skills/find-semantic-duplication/scripts/detect_ruby_semantic.py \
  .claude/skills/rename-concept/scripts/assess_ruby_rename.py \
  tests/test_ruby_semantic_family.py

.venv/bin/python -m pytest -q tests/test_ruby_semantic_family.py
```

Focused result: `14 passed`.

## Existing Ruby map disposition assessment

No A3 fact changes the existing `map-subsystem` disposition. Its bounded static
map remains a complete, useful Ruby outcome with explicit runtime-partial
completeness: it intentionally maps source/configuration, Prism declarations,
literal load/layout relationships, reopening/mixin spelling, and conservative
constant candidates without claiming runtime identity. This A3 provider needs
a project-owned RBS contract and still does not resolve Ruby dynamic identity;
it cannot upgrade map reachability or make the static map conditional on RBS.
Under the accepted coverage/runtime distinction, root should preserve the map
row as `ruby-supported` with runtime partial limitations, not reimplement it
or downgrade it to coverage partial.

## Root handoff

This worker owns only Ruby providers/adapters, the Ruby fixture, focused test,
and this packet. Root retains `SKILL.md` prose, coverage, matrix/catalog,
router, profile, shared dispatch, active ledger, and durable docs. On
integration, publish each A3 consumer only as its bounded RBS-backed contract;
configuration without project-owned RBS must remain a visible runtime partial,
not an unsupported Ruby claim.
