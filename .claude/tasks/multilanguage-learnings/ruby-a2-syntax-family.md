# Ruby A2 syntax-family handoff

Base revision: `98dff014d19aaa94c297d67b3f6f2ce444f41e4d`

## Bounded outcomes

The four frozen Ruby A2 consumers now reach their existing useful final
artifacts from a copied external-library closure over the dependency-free
plain-Ruby gem fixture. Ruby 3.4.1, bundled/default Prism 1.2.0, and Bundler
2.6.2 were already installed. This lane installed or updated nothing and made
no network call.

| Skill | Final value | Final artifacts |
|---|---|---|
| `audit-decisions` | Finds direct Prism comment references `decision:0001` and orphan `decision:9999`, then carries them through the existing registry/link audit. | `drift.md`, `raw-drift.json`, `registry-audit.json`, `link-check.txt` |
| `find-complexity-hotspots` | Finds only `route_invoice` with a direct-method branch score of 9; the lambda-body decoy scores 0. | `detections.jsonl`, `findings.json`, `report.md` |
| `find-omnibus` | Creates one syntax candidate from four paired method-name clusters and reaches a scout-graded `confirmed_omnibus` result. | `omnibus.jsonl`, `candidates.jsonl`, `scan.json`, `findings.json`, `report.md` |
| `find-standard-gaps` | Counts two direct `parse_invoice` calls, one syntactically inside a `begin`/`rescue` enclosure and one gap. | `coverage.json`, `coverage.md` |

`tests/fixtures/ruby-syntax-family` includes positive source, clean method-name
decoys, test/generated/vendor/build/report/symlink role decoys, source-shaped
strings, native test/smoke executables, decision records, scout evidence, and a
malformed selected file.

## Ruby-local fact contract

`_ruby-syntax/ruby_syntax_facts.py` is a separate language-local producer. It
does **not** extend the A1 project/lexical provider: A1 owns inventory and
direct declaration/method spelling for its five lexical consumers, while A2
needs a distinct exact Prism payload for comments, direct method-body branch
nodes, direct calls, and `begin`/`rescue` syntax enclosures. Combining those
would broaden A1's ownership and make the lexical provider the accidental
authority for four different final outcomes.

The A2 producer owns only:

- full `.rb`, Ruby-shebang, config, role, and symlink inventory;
- Ruby 3.3+ and Bundler 2.6+ preflight, bundled/default Prism proof, separate
  `ruby --disable-gems -c` checks, frozen isolated `bundle check`, and the
  supplied direct Ruby test/smoke commands;
- source/configuration manifest and post-tool preservation proof;
- comment spans, direct `def` syntax, direct branch node counts, direct calls,
  and lexical `begin`/`rescue` enclosure facts; and
- atomic terminal artifacts with `partial` always returning exit code `2`.

Each consumer keeps its own drift/hotspot/scout/coverage meaning and final
schema. It is an external-library-only closure: optional consumer-only
installation must fail closed as `ruby_syntax_fact_producer_missing` rather
than duplicate the producer or silently import the repository.

Exact executable closures are:

| Consumer | Required copied files | Bytes |
|---|---|---:|
| `audit-decisions` | `_ruby-syntax/ruby_syntax_facts.py`, `audit_ruby.py`, `audit.py` | 81,045 |
| `find-complexity-hotspots` | `_ruby-syntax/ruby_syntax_facts.py`, `run_ruby.py` | 36,998 |
| `find-omnibus` | `_ruby-syntax/ruby_syntax_facts.py`, `run_ruby.py` | 39,311 |
| `find-standard-gaps` | `_ruby-syntax/ruby_syntax_facts.py`, `scan_coverage_ruby.py` | 38,862 |

The focused test copies exactly those files below `.agents/skills/`, executes
them with isolated Python (`-I -S`) from outside the checkout, and proves that
removing `_ruby-syntax` changes the terminal outcome to `partial`/exit `2`.

## Lifecycle, boundary, and native proof

Every consumer proves valid → failed frozen Bundler check → valid at the same
destination. Failed artifacts replace previous final results and contain no
stale audit references, hotspots, omnibus findings, or scanned standards.
Missing Ruby, Ruby 3.2.9, and malformed selected source are `partial` and exit
`2`; a failing Bundler executable is `failed` and exits `1`. Dynamic dispatch
and a Rails loader marker are `partial`, never clean.

The focused suite also proves native `ruby -c` per selected candidate/test/
entrypoint, frozen `bundle check`, exact `ruby-syntax-native-test:ok` and
`ruby-syntax-smoke:7` output, and source preservation on every successful,
failed, malformed, and safe-defer path.

Prism facts remain syntax-level only. They do not establish runtime constant
or method identity, visibility, dispatch, loading, metaprogramming,
Rails/Zeitwerk behavior, semantic equivalence, safe decomposition, or refactor
authority. Dynamic `require`/`load`, `send`/`public_send`, `const_get`,
`method_missing`, eval variants, `define_method`, class/module reopening,
monkey patches, refinements, callbacks, DSLs, native extensions, and runtime
generated code remain unresolved. `find-omnibus` therefore requires separate
human scout evidence and its recommendation explicitly preserves human
authority.

## ML-025 economics and interface depth

Deletion of the producer would force all four consumers to re-own Ruby/Bundler
resolution, isolated frozen bundle policy, Prism invocation/parsing, roles,
source preservation, native gates, terminal status, and every dynamic/framework
boundary. Consumers contain none of the provider's Prism invocation or
`bundle check` policy. Their durable public interface is `produce(...)`; tests
exercise its final artifacts through the four executable consumers.

| Design | Physical LOC |
|---|---:|
| Shared producer `H` | 921 |
| Four adapters plus focused family test `C` | 1,087 |
| Shared design `C + H` | 2,008 |
| Literal duplicated design `C + 4H` | 4,771 |
| Removed maintenance (`3H`) | 2,763 |

The shared design reduces maintained adapter-plus-test LOC by **57.91%**,
above ML-025's 25% threshold. The shared exact-closure union is 99,211 bytes;
literal per-consumer producer copies total 196,216 bytes, a 49.44% union
reduction. Each individual closure has **0.00%** growth because it carries the
same one provider either way.

Five alternating warm complete-family trials, each running all four final
outcomes from copied closures outside the checkout, measured:

- shared seconds: `2.285597, 2.385084, 3.601997, 2.798409, 3.105538`;
- literal duplicated seconds: `2.192108, 3.090322, 3.013570, 2.270657, 2.768826`;
- shared median: `2.798409s`;
- duplicated median: `2.768826s`; and
- median latency growth: **1.068%**.

The producer therefore passes all ML-025 gates. It remains Ruby-local: no
cross-language AST/result abstraction, cache, daemon, package manager, or
shared semantic layer is justified.

## Verification and root handoff

Worker checks passed:

```bash
<product-repo>/.venv/bin/python -m pytest -q tests/test_ruby_syntax_family.py
<product-repo>/.venv/bin/python -m ruff check \
  .claude/skills/_ruby-syntax/ruby_syntax_facts.py \
  .claude/skills/audit-decisions/scripts/audit_ruby.py \
  .claude/skills/find-complexity-hotspots/scripts/run_ruby.py \
  .claude/skills/find-omnibus/scripts/run_ruby.py \
  .claude/skills/find-standard-gaps/scripts/scan_coverage_ruby.py \
  tests/test_ruby_syntax_family.py
<product-repo>/.venv/bin/python -m pytest -q \
  tests/test_ruby_project_lexical_family.py tests/test_find_comment_drift_ruby.py \
  tests/test_map_subsystem_ruby.py tests/test_ruby_pilot_spine.py
```

Root should integrate and publish serially:

1. Install `_ruby-syntax/ruby_syntax_facts.py` together with all four A2
   adapters in the external on-demand library; preserve A1's separate
   `_ruby-project-lexical` provider.
2. Update only the root-owned Ruby command/closure/limitations publication
   surfaces for these four skills, without changing existing language paths.
3. Publish the four Ruby coverage/matrix/router/catalog dispositions and their
   installed-closure manifests through the existing root process.
4. Refresh root-owned copied-library baseline allow-lists before rerunning
   `tests/test_language_support_conformance.py`; this worker intentionally did
   not modify them. The host conformance suite otherwise reports the expected
   new `find-omnibus/scripts/run_ruby.py` file as un-published additive state.
5. Replay the focused A2 family, preserved Ruby A1/comment/map/spine tests,
   matrix/router, installed external-library, artifact-drift, no-host-reference,
   and committed host conformance gates before publishing.
