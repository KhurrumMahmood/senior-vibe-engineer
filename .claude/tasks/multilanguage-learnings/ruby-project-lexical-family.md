# Ruby A1 project/lexical family handoff

Base revision: `febc76141feed564de628bde6d99f20f85191ebb`

## Outcome and recommended dispositions

Five independent read-only consumers now reach their existing final artifact
boundaries from copied external-library closures. The host is a dependency-free
plain-Ruby gem layout. Ruby 3.4.1, RubyGems 3.6.2, Bundler 2.6.2, and Ruby's
bundled Prism 1.2.0 were already installed; this lane installed or updated
nothing and used no network.

| Skill | Proved value | Final artifacts | Recommended disposition |
|---|---|---|---|
| `adapt-project` | Counts six authored Ruby files, identifies the locked Bundler project, emits the syntax/check/test/smoke commands it actually executes, and makes no framework or layout-health claim. | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` | `ruby-supported` for objective bounded plain-Ruby/gem project facts |
| `explain-code` | Annotates direct Prism class, module, and method syntax such as `Billing::Invoice`, `Billing::InvoiceState`, and `Billing::Parser#cancelled_order`, with exact spans/hashes and unresolved dynamic signals. | explanation Markdown, `targets.json`, `scan.json`, per-declaration annotations, `unexplained.txt`, `surprises.txt` | `ruby-supported` for direct syntax explanation, never runtime identity or behavior |
| `find-concept-divergence` | Finds the glossary avoid term `cancelled_order` once in authored source with an exact span/hash while all role decoys stay excluded; the preferred-only run is clean. | `findings.jsonl`, `report.md`, `findings.json`, `scan.json` | `ruby-supported` for strict glossary-backed text evidence |
| `find-duplication` | Finds exactly the two seven-line methods with identical normalized Prism body spelling; a different method and identical decoy bodies do not fire. | `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, `scan.json` | `ruby-supported` for exact method-body spelling evidence, not safe-consolidation proof |
| `find-folder-topology-drift` | Finds one three-file `billing_*` direct-sibling cluster; test, generated, vendor, build, report, and symlink three-file clusters remain decoys, and threshold four is clean. | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` | `ruby-supported` for explicit-root direct-sibling filename evidence |

The accepted Ruby `find-comment-drift` and bounded `map-subsystem` paths are
untouched. Their artifacts, runtime limits, and copied closures remain
independent of this family.

## Ruby-local fact contract

`.claude/skills/_ruby-project-lexical/ruby_project_lexical_facts.py` is the one
shared implementation. All five immediate consumers use it for the same facts
and mechanics:

- full pre-eligibility inventory for `.rb`, Ruby-shebang, Gemfile/lock,
  Rakefile, gemspec, test, generated tree/marker, vendor, build, report,
  entrypoint, configuration, and symlink roles;
- content-derived source/configuration manifests and post-tool preservation;
- Ruby 3.3+ and Bundler 2.6+ resolution with explicit missing, old, broken,
  and unrecognized states;
- bundled/default Prism proof, separate `ruby --disable-gems -c` execution for
  every authored/test/entrypoint file, and direct declaration/method spans;
- frozen `bundle check` with isolated temporary configuration, disabled
  version checks, dead proxy endpoints, and no install/update command;
- explicit dependency-free native test and smoke execution;
- atomic artifacts, stale-artifact clearing, and terminal return policy; and
- dynamic-signal and non-claim evidence shared without interpreting it.

Consumers retain adaptation, explanation, glossary, clone, and topology
meaning plus distinct final schemas. No universal AST, result/lifecycle
platform, cache, daemon, package manager, or cross-language provider was added.

## Interface depth and economics

Deleting the provider forces all five consumers to recover tool resolution,
version policy, source roles, Ruby/Prism/Bundler commands, temporary native
state, native test/smoke policy, manifests, preservation, and terminal
lifecycle. The focused test asserts that every consumer imports
`collect_snapshot` and embeds none of the provider's Bundler, Prism, or
generated-role policy.

Maintained physical LOC:

| Component/design | Physical LOC | Nonblank LOC |
|---|---:|---:|
| Shared Ruby provider `H` | 684 | 620 |
| Five consumers plus focused test `C` | 1,378 | 1,256 |
| Shared design `C + H` | 2,062 | — |
| Duplicated design `C + 5H` | 4,798 | — |
| Deleted maintenance `4H` | 2,736 | — |

The shared design reduces maintained adapter-plus-test LOC by **57.02%**,
clearing ML-025's 25% gate. The six-file installed union is 56,007 bytes;
duplicating the provider into all five skills would be 156,851 bytes. Sharing
reduces installed union bytes by **64.29%**. Every selected consumer closure
still contains exactly one adapter and one provider, so per-consumer closure
growth is **0.00%**.

Seven alternating warm trials compared the sibling shared provider with the
same provider duplicated under each skill (only the adapter's local provider
path changed). Each trial executed all five positive final outcomes, including
the same native process matrix:

- shared seconds: `3.025286, 3.050155, 3.043129, 2.971619, 3.144209, 3.091823, 3.126622`;
- duplicated seconds: `3.016143, 3.050126, 3.187894, 3.346444, 3.143952, 3.141560, 3.224481`;
- shared median: `3.050155s`;
- duplicated median: `3.143952s`; and
- measured median latency growth: **-2.983%**.

No cache, extra native pass, dependency, network call, or subprocess was added
by the seam. Both closure and latency remain inside the 10% growth gates.

## Exact copied closures and fixture

Manifests hash sorted `repository-relative path + NUL + file SHA-256 + LF`
rows. Every consumer was copied below a temporary `.agents/skills/` library and
executed with isolated Python (`-I -S`) from a copied host outside the checkout.

| Closure | Files | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| Provider | 1 | 25,211 | `6847187b312ad7be0a5f97ca149cad825907a98a6f67e275fd77fcca0deb10b1` |
| `adapt-project` | 2 | 29,399 | `bf0ee348746f2e952ae5a2e77b4d389f9f9c6a55f600c83b590f36b7145cf3d7` |
| `explain-code` | 2 | 30,755 | `023ddbc6a7ae012cda5cd85c2789064a875fea0f7e750725b1fcaf1870aa4096` |
| `find-concept-divergence` | 2 | 35,326 | `34bf37564113f38ba6c29d2138fc74b8c8b3131613349876111a376a8baed794` |
| `find-duplication` | 2 | 31,311 | `34f379ebd3d9cf272a66ca11e5a73f186dcf2d12b728b568aabe9939b74d6952` |
| `find-folder-topology-drift` | 2 | 30,060 | `6f1d341ca8ff6040b1f2d6044cf25c4ec77d61cca7fabec7e7cfce66f769b25e` |

The provider content SHA-256 is
`0af0ed745137a4aa36746832c8aeaf9a15d5b98d45d622b504dac1831d57577d`.
The 33-file fixture is 4,464 bytes with manifest
`847e9becaf305a30389229ecbb9eb53585d4f70905c355b7c22056a9e38138bc`.

## Lifecycle, failure honesty, and native proof

The focused suite runs every consumer through a valid -> failed Bundler check
-> valid transition at the same destination. Failed artifacts contain no prior
findings or selected declarations, and recovery restores the independent final
outcome. Every consumer also proves:

- missing Ruby, Ruby 3.2.9, and missing `Gemfile.lock` are `partial`, never a
  false clean or permanent unsupported claim;
- a Bundler 2.6.2-shaped executable whose check fails is `failed`;
- an unreferenced malformed selected `.rb` file is `partial` while valid facts
  remain useful;
- positive, preferred-only clean, exact-clone clean, and below-threshold
  topology outcomes are distinguished;
- role decoys include test, generated tree/marker, vendor, build, report,
  symlink, configuration, and entrypoint inputs;
- identical long method bodies and `cancelled_order`/`billing_*` spellings in
  excluded roles cannot become findings; and
- source and configuration bytes remain unchanged across every run.

The independent native replay verifies Ruby 3.4.1, bundled Prism 1.2.0,
Bundler 2.6.2, `ruby -c` per selected first-party/test/entrypoint file, frozen
`bundle check`, the exact `ruby-native-test:ok` output, and the exact
`ruby-lexical-smoke:300` output. Focused copied replay passed `21` tests in
`22.75s`; preserved Ruby comment/map/spine replay passed `23` tests in
`24.98s`. Targeted Ruff and the five-skill artifact-drift gate passed.

## Honest Ruby limitations

- Prism declarations and method bodies are syntax/spelling candidates. They
  do not establish runtime constant identity, method visibility, dispatch,
  ownership, callers, types, pre/postconditions, or behavior.
- Dynamic `require`/`load`, `$LOAD_PATH` mutation, autoload, Rails, Zeitwerk,
  and other framework loader conventions remain unresolved.
- Class/module reopening, monkey patches, refinements, ancestor changes,
  overriding, and execution order remain unresolved.
- `send`/`public_send`, `const_get`/`const_missing`, `method_missing`, eval
  variants, `define_method`, reflection, callbacks, DSLs, native extensions,
  and runtime-generated code remain unresolved.
- Exact normalized method-body spelling is an advisory clone lead; it never
  authorizes consolidation.
- Strict glossary text can occur in a comment/string and is not symbol or
  conceptual identity.
- Filename clusters do not prove namespace ownership, load behavior, import
  impact, Rails conventions, or a safe move.

## Root integration and replay instructions

This lane intentionally changes no shared `SKILL.md`, profile/inventory/doctor,
router/catalog, coverage/matrix/ledger, README/installer, `_common`, or
other-language surface. Root should integrate and publish serially:

1. Install `_ruby-project-lexical/ruby_project_lexical_facts.py` beside every
   selected Ruby A1 consumer. Treat all five as external-library-only and
   reject consumer-only closures; do not duplicate the provider for optional
   install optics.
2. Add the Ruby command, two-file closure, exact native test/smoke arguments,
   artifacts/statuses, role exclusions, and bounded limitations to each of the
   five shared `SKILL.md` files without changing preserved language commands.
3. Change exactly these five Ruby coverage rows from pending implementation to
   the accepted bounded dispositions. Keep `find-comment-drift` and
   `map-subsystem` unchanged. Regenerate matrix/projections through the existing
   builder, then update catalogs/routers and installed closure manifests.
4. Replay `tests/test_ruby_project_lexical_family.py`,
   `tests/test_find_comment_drift_ruby.py`, `tests/test_map_subsystem_ruby.py`,
   and `tests/test_ruby_pilot_spine.py` after integration. Then run the shared
   matrix/router, installed external-library closure, artifact drift, and
   no-host-reference gates before publishing.
5. Preserve consumer schemas and keep syntax candidates out of future semantic
   producers. A3 may use different project-aware facts; it must not broaden
   this provider into runtime identity or Rails/Zeitwerk semantics.
