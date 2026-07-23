# Dart 3.12 language-level contract map

Status: implementation-ready work packet; no Dart capability is published by
this document

Base revision: `c691fb3c4a8bf040774e7d75b50fb6bd6aac81c7`

## Decision and batch order

Dart should start as a plain-Dart, SDK-pinned language profile, not as a
translation of a TypeScript walker and not as a Flutter profile. The useful
unit is a contract family with its own final outcome. One serial spine and
eight implementation batches cover all 22 language-level skills:

| Order | Batch | Owned skills | Count | Prerequisite |
|---|---|---|---:|---|
| D0 | plain-Dart spine | none; no support claim | 0 | accepted packet |
| D1 | project and lexical facts | `adapt-project`, `find-concept-divergence`, `find-folder-topology-drift` | 3 | D0 |
| D2 | comments and declared-policy syntax | `audit-decisions`, `find-comment-drift`, `find-standard-gaps` | 3 | D0; owns the syntax producer |
| D3 | declaration and body structure | `explain-code`, `find-complexity-hotspots`, `find-duplication`, `find-omnibus` | 4 | D2 syntax producer |
| D4 | semantic topology | `find-dormant`, `map-subsystem`, `rename-concept` | 3 | D0; owns the LSP provider |
| D5 | semantic behavior and state | `find-implicit-state`, `find-incomplete-sweep`, `find-semantic-duplication` | 3 | D4 LSP provider |
| D6 | accepted state consumers | `extract-enum`, `prevent-regression` | 2 | accepted D5 `find-implicit-state` evidence |
| D7 | read-only proposals | `propose-boundary`, `propose-folder-reorganization`, `unify-shadows` | 3 | accepted D1/D4/D5 evidence as named below |
| D8 | transactional mutation | `move-path` | 1 | D2 syntax spans and D4 semantic identity accepted |

After D0, D1, D2, and D4 can be implemented in separate worktrees. D3 waits
for D2's producer contract; D5 waits for D4's provider contract. D6 and D7 can
then run in parallel. D8 may be developed independently after D2/D4, but its
integration and mutation tests remain serial and last. Promotion is per skill,
not per batch; a stopped row remains `dart-pending-implementation`.

## Local tool evidence and acquisition boundary

The local probe on 2026-07-22 found:

- `/opt/homebrew/bin/dart` resolves to the Homebrew Dart SDK 3.12.2 stable,
  macOS arm64.
- `dart language-server --protocol=lsp` is an SDK command. Its initialize
  response names `Dart SDK LSP Analysis Server` 3.12.2 and advertises
  document/workspace symbols, definition, references, implementation, type
  definition, call hierarchy, and rename.
- A fresh read-only LSP probe passed `documentSymbol`, definition, references,
  `workspace/symbol`, `prepareRename`, and rename-edit preview. Its external
  `--cache` directory was about 5 MB and no project file changed. Relative
  imports resolved without package configuration; package imports did not.
  Supplying an existing `--packages` configuration resolved package imports.
  Therefore the provider must canonicalize macOS paths, filter SDK symbols,
  keep cache output outside the audited host, hash the package configuration,
  and refuse complete package semantics when it is absent or unresolved.
- `dart analyze` has fatal-info and fatal-warning gates but no advertised JSON
  output. Use it as a native pass/fail gate; use LSP for structured semantic
  facts.
- `dart format --output=none --set-exit-if-changed` is SDK-owned and needs no
  Pub package. Its behavior/version is tied to the SDK.
- `dart pub deps --json` provides the resolved package graph after Pub
  resolution. `dart pub get --offline --enforce-lockfile` is the reproducible
  dependency preflight for a locked fixture or closure-owned tool package.
- `dart test` is only a command front end. The runner is the host's
  `package:test`, not a dependency-free SDK facility.
- The initial Pub cache contained `analyzer` 6.3.0 and `test` 1.24.9. A Dart
  3.12 package template required newer packages. An unguarded `dart test`
  implicitly resolved the template and populated the cache with `analyzer`
  14.1.0, `test` 1.31.2, and `lints` 6.1.0; subsequent locked offline replay
  passed. That cache mutation is evidence that a doctor must never probe by
  running `dart test` before locked/offline Pub preflight. It is not evidence
  that a fresh user cache is ready.
- With the resolved lock, the generated plain-Dart package passed locked
  offline Pub get, fatal analysis, format check, one `package:test` test, and
  an exact executable smoke.

Product commands must use
`/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python`. <!-- # host-ref-allow: required frozen P7 runtime -->
The product must not install Dart, Pub packages, or test dependencies into a
host. D0 reports exact paths/versions and whether required package artifacts
are already available. A package dependency must be either declared and locked
by the host, or declared and locked by a copied closure-owned Dart tool package.
It is never downloaded silently.

Pin the first implementation to Dart `>=3.12.0 <3.13.0`. Pin the syntax tool's
public `analyzer` dependency exactly (the locally exercised candidate is
14.1.0) and retain its lockfile. A newer SDK or analyzer package is
`partial/untested_toolchain` until its fixtures pass; analyzer API churn is not
hidden behind a broad constraint.

## D0 spine contract

D0 owns a dependency-free plain-Dart workspace fixture and the Dart profile,
doctor, role inventory, status vocabulary, source manifest, and artifact
lifecycle. It earns no skill disposition.

The fixture should be a locked Pub workspace with a library package and a
small executable package, plus `lib/`, `bin/`, `test/`, `tool/`, `example/`, a
public barrel, direct and relative imports/exports, one exact smoke value, and
decoys for every source role. A committed lock is required even though
published library packages often omit one; this is a verification fixture, not
packaging advice.

Eligible core-Dart source is authored `.dart` below declared workspace package
roots. Inventory, but exclude from findings by default: `test/`, `integration_test/`,
`example/`, `benchmark/`, generated trees and markers (`.dart_tool/`, `build/`,
`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, generated headers), vendor or
vendored Pub caches, reports, symlinks, and files outside selected package
roots. `bin/` and `tool/` are first-party executable/tool roles, not library
surface. `pubspec.yaml`, `pubspec.lock`, `analysis_options.yaml`, and
`.dart_tool/package_config.json` are project metadata, not Dart source.

The exact native matrix is:

1. `dart pub get --offline --enforce-lockfile` for the locked fixture and any
   closure-owned analyzer tool package;
2. `dart pub deps --json` and a content hash of Pub/workspace configuration;
3. `dart analyze --fatal-infos --fatal-warnings .`;
4. `dart format --output=none --set-exit-if-changed` over existing authored
   source roots only;
5. `dart test --reporter=expanded` only after the locked/offline preflight and
   only when the host declares `package:test`;
6. `dart run <smoke-entrypoint>` with exact stdout.

Every batch proves valid -> partial/failed -> valid at the same destination,
atomically replaces old output, fingerprints all selected source/configuration,
and preserves host bytes unless D8 is explicitly in apply mode. Missing or
untested tools/dependencies and unresolved configuration are visible partial
results; malformed eligible source, native command failure, protocol corruption,
unsafe paths, or unexpected mutation are failed. Neither state is clean.

Flutter is a separate future framework profile. A Flutter dependency, Flutter
SDK marker, widget test, generated plugin registrant, platform runner, asset,
route, widget-tree, or `flutter analyze/test` obligation is out of this packet.
Do not infer Flutter behavior from `pubspec.yaml` or accept Flutter-only source
as complete plain-Dart evidence.

## Shared fact boundaries and closure rules

### Facts that may be shared

1. **Dart project snapshot (D1-D8):** selected workspace/package roots, roles
   and exclusions, SDK/Pub/tool versions, Pub graph/configuration hashes,
   source spans/hashes, native-gate results, status, and artifact lifecycle.
   Three D1 consumers immediately use it and later batches consume the same
   provenance.
2. **Dart syntax snapshot (D2-D3, and D8 only for edit spans):** analyzer
   package version, parse diagnostics, real comment tokens, direct declarations,
   import/export/part directives, named function/method body spans, and bounded
   direct-body syntax. Seven real consumers use these facts. This producer is a
   closure-owned locked Dart package; it is not the SDK LSP and it may not use
   `package:analyzer/src/...` private APIs.
3. **Dart semantic query pack (D4-D5 and bounded D7/D8 consumers):** exact SDK
   version, selected package/configuration digest, LSP diagnostics, document and
   workspace symbols, definitions, references, implementations, types where
   returned, call hierarchy, unresolved requests, and query/source lineage.
   It is content-addressed by manifest, SDK, options, and query set. It uses
   `dart language-server --protocol=lsp`; it does not import `package:analyzer`.
4. **Accepted-evidence envelope (D6-D7):** producer/version, terminal status,
   source/config hashes, cited spans, human verdict, acceptance hash, and native
   obligations. Consumers validate it and never silently re-detect.

### Facts that remain consumer-local

Complexity scores, decision-reference meaning, comment-drift rules, clone
normalization/ranking, concept bands, topology thresholds, explanation prose,
dormancy/reachability policy, omission gates and Git trajectory, state-domain
closure, semantic-duplication matrices, subsystem-map schemas, proposal choice,
public compatibility, rewrite plans/spans, rollback, and guard semantics remain
with their skill. Syntax does not prove identity; LSP identity does not prove
runtime behavior; a passing analyzer does not turn reflection or generated code
into a complete graph.

### Extraction economics

The project, syntax, and semantic seams are proposals only until two production
consumers call the same public contract. Measure physical adapter-plus-test LOC
as `C + nH` for duplicated providers versus `C + H` for sharing. Extract only
if `(n - 1)H / (C + nH) >= 25%`, copied closure size and median latency do not
grow by more than 10%, and callers lose tool/lifecycle/role knowledge. With
three project consumers and seven syntax consumers, a 300-500 LOC producer and
600-1,800 LOC of consumers plausibly clears 40-65%; D2 must record actual LOC.
Rust's accepted five-consumer LSP family saved 53.77%, so a six-consumer Dart
provider is plausible, not proven.

The existing Rust stdlib LSP client is a reuse candidate for transport framing,
timeouts, shutdown, and request correlation. Keep the first implementation
Dart-owned: initialization capabilities, Pub workspace roots, diagnostics,
symbol identity, queries, and closure packaging differ. Consider a
cross-language LSP transport extraction only after two real Dart consumers and
the measured gate pass. Do not share a universal AST, semantic result, report,
proposal, or rewrite schema.

Each copied consumer closure contains the selected skill, the D0 project
snapshot/lifecycle module, and only its named provider: the locked D2 analyzer
tool for syntax consumers, the D4 stdlib LSP provider for semantic consumers,
or accepted upstream artifacts for D6/D7. A missing companion produces a
visible terminal artifact and nonzero exit; it never falls back to a weaker
lexer or downloads a dependency.

## D1 — project and lexical facts

Closure: selected skill + D0 project snapshot. No analyzer package or LSP is
required. Batch artifacts are each skill's existing final artifacts plus a
`scan.json` carrying Dart provenance/status. Failure obligations are D0's
lifecycle plus unreadable authored source and unsafe/symlinked report paths.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `adapt-project` | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` count authored Dart roles, workspace packages, and exact native commands without applying host writes. | Two locked workspace packages with library/bin/tool/test/example/generated roles and an exact smoke command. | A conventional one-package core-Dart host yields complete objective facts and no standardization caution. | Dependency names do not imply Flutter/frameworks; tests, examples, generated, cache, build, vendor, reports, and symlinks do not count as authored library roots. | Full D0 matrix; assert reported commands are the commands executed. | Describes observed layout only; no architecture endorsement, semantic graph, or framework inference. |
| `find-concept-divergence` | `findings.jsonl`, `report.md`, `findings.json`, `scan.json` report one glossary avoid-term with exact span/hash. | An old term in authored Dart prose/identifier plus the preferred term elsewhere and decoys in every excluded role. | Preferred term only produces complete zero findings. | Substrings, unrelated homonyms, generated/test/example/vendor/build/report/symlink content, and package names outside the declared glossary do not fire. | Locked Pub/analyze/format/test/smoke; findings must preserve source bytes. | Strict text/glossary evidence only; no symbol identity, conceptual equivalence, or rename-completeness claim. |
| `find-folder-topology-drift` | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` report one policy-backed direct-sibling filename cluster. | Three authored `billing_*.dart` siblings below one explicit `lib/src` root plus excluded decoys. | Two siblings or an explicitly cohesive/allowed folder is clean. | Barrels (`<folder>.dart`), tests, parts/generated files, bin/tool/example/vendor/build/report/symlink paths, below-threshold clusters, and nested cousins do not fire. | Full D0 matrix and exact inventory/hash assertions. | Filename topology is advisory; it proves no library ownership, import impact, move safety, or Flutter convention. |

## D2 — comments and declared-policy syntax

Closure: selected skill + D0 module + one locked, closure-owned Dart tool
package containing the public `package:analyzer` syntax producer. D2 owns that
producer; D3 may consume it after the contract is accepted. No host pubspec is
edited. Cache absence or lock mismatch is `partial/tool_dependency_unavailable`,
not permission to fetch. Parse diagnostics in any selected authored file block
a clean result.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `audit-decisions` | `drift.md`, `raw-drift.json`, `registry-audit.json`, `link-audit.json` retain a real `decision:0001` Dart comment and expose orphan `decision:9999`. | Line, block, and doc comments plus comment-shaped ordinary/raw/multiline strings and excluded-role decoys. | Every real reference resolves and every registry row is referenced; all four complete artifacts remain. | Strings, symbol names, malformed source, generated/test/example/vendor/build/report/symlink files do not become references. Markdown/HTML compatibility remains separately owned. | D0 matrix plus analyzer-token/source-span oracle. | Syntax comments only; it does not judge whether an ADR applies or interpret generated documentation. |
| `find-comment-drift` | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` report one bounded adjacent Dart doc-comment/value mismatch. | A `///` percentage/rate claim immediately attached to a named function whose direct body returns a conflicting fixed numeric literal, plus matching/decoy cases. | Matching adjacent claim and literal yields complete zero findings. | Strings, detached comments, ordinary implementation notes, nested closures, computed values, extensions/mixins without the bounded shape, and excluded roles do not fire. | D0 matrix plus public-analyzer token/AST span assertions. | One advisory fixed-literal rule only; no runtime, data-flow, inherited-doc, macro/codegen, or API-correctness claim. |
| `find-standard-gaps` | `coverage.md`, `coverage.json`, `scan.json` report two direct `parseInvoice` sites, one declared try-enclosure gap, and 50% coverage. | Host-owned standards JSON, one direct call inside `try`, one outside, and declaration/string/tear-off/receiver decoys. | All eligible direct spelled calls satisfy the declared syntactic condition. | Aliases, receiver/extension dispatch, constructors, declarations, tear-offs, strings, dynamic calls, generated/excluded roles, and unsupported condition kinds do not become sites. | D0 matrix plus analyzer AST site/enclosure oracle; invalid standards fail before a clean report. | Direct spelling and one frozen syntax condition only; no callee identity, exception-flow, framework policy, or general Dart lint replacement. |

## D3 — declaration and body structure

Closure: selected skill + D0 module + accepted D2 locked syntax producer. D3
owns no second parser. Its four report schemas and interpretations remain
skill-local. Missing D2 companion, unsupported Dart syntax, or stale producer
hash is terminal partial/failed evidence, never a fallback lexical scan.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `explain-code` | `targets.json`, per-symbol `annotations/*.md`, unexplained/surprises sidecars, and `reports/explanations/<target>.md` explain direct public declarations. | Public class, enum, extension, typedef, and top-level function with private members and an unresolved re-export. | A private-only target yields a complete explicit empty public-surface explanation. | Private declarations, imports, generated parts, tests/examples, inherited/extension members outside target, aliases/re-exports without resolution, and strings do not become explained exports. | D0 matrix; every ranked target has an annotation or explicit unexplained record. | Direct syntax surface only; no callers, runtime behavior, alias/re-export resolution, contracts, or Flutter widget semantics. |
| `find-complexity-hotspots` | `detections.jsonl`, `report.md`, `findings.json`, `scan.json`, and `latest` report one named function above the frozen branch threshold. | Direct-body `if`, loops, switch cases, catch, `&&`/`||`, plus a branch-heavy nested closure/local function decoy. | All named bodies below threshold produce a complete empty report. | Nested closures/local functions do not inflate owners; declarations, strings, generated/test/example/build/symlink roles and malformed files do not become clean findings. | D0 matrix plus exact per-function span/score oracle. | Advisory syntactic score only; patterns, async scheduling, dispatch, runtime frequency/cost, and Flutter rebuild behavior are unresolved. |
| `find-duplication` | `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, `scan.json` report one exact normalized named-body clone pair as a review lead. | Two at-least-five-line named function bodies with identical token-normalized content, plus a behaviorally similar but structurally different decoy. | No repeated body reaches threshold. | Constructors/accessors/closures unless explicitly supported, trivial bodies, generated/test/example/vendor/build/report/symlink roles, formatting-only spans, and cross-language files do not fire. | D0 matrix plus body-span/hash oracle and copied final triage. | Lexical/syntax duplication only; no behavioral equivalence, consolidation safety, or generated-code ownership claim. |
| `find-omnibus` | `omnibus.jsonl`, `candidates.jsonl`, `scout/*.json`, `report.md`, `findings.json`, `scan.json` produce one scout-confirmed decomposition lead. | One authored library with four paired head-noun domains and one cohesive control library; fixed scout verdicts cover both. | Cohesive/facet-only target produces no confirmed omnibus finding. | File size alone, extensions/mixins, generated parts, tests/examples, barrels, strings, excluded roles, and ungraded candidates never become confirmed. | D0 matrix plus D2 declaration spans and complete candidate-to-scout lineage. | Syntax nominates only; human domain judgment is mandatory and no safe split or runtime responsibility is proven. |

## D4 — semantic topology

Closure: selected skill + D0 module + one Dart-owned stdlib JSON-RPC client for
`dart language-server --protocol=lsp`. D4 owns the provider; D5 consumes it.
The provider records advertised capabilities and every unresolved request. It
does not use the closure-owned analyzer package. Invoke the server with an
external temporary `--cache` and the host's pre-existing, hashed `--packages`
configuration; never generate or repair package configuration during analysis.
Canonicalize file URIs/real paths on macOS and exclude SDK symbols from
first-party facts. A complete result requires a clean exact selected Pub
configuration, successful package-import resolution, advertised request
capabilities, and zero error diagnostics; missing package configuration when
package imports exist, conditional imports/exports, augmentations, generated
parts, unresolved URIs, unsupported LSP requests, and incomplete workspace
selection make the result partial.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `find-dormant` | `report.md`, `findings.json`, `facts.json`, `scan.json` emit one private top-level function as `review_required`, with `certain_delete: 0`. | One unreferenced private function, one used private function, public/override/callback/entrypoint/tear-off decoys, and excluded roles. | Every eligible private top-level function has a resolved selected-workspace reference. | Public API, `main`, overrides, callbacks/registrations, dynamic invocation, mirrors, conditional/part/generated code, tests/examples, unresolved files, and external packages do not become deletion leads. | D0 matrix plus LSP definition/reference lineage for every candidate. | No safe-deletion or runtime-reachability claim; reflection, isolates, registries, native/JS interop, and generated callers remain unresolved. |
| `map-subsystem` | `.claude/docs/subsystems/<name>.md` and `reports/map/<name>/dart-map.json` map selected files, direct public surface, and resolved inbound/outbound edges. | Two workspace libraries with direct/relative/package imports, an export barrel, public declarations, inbound callers, and an unresolved conditional edge. | A bounded package subgraph with all selected edges resolved is complete. | Generated/test/example/vendor/build/report/symlink sources, SDK/external dependency internals, strings, and files outside selected roots do not become first-party edges. | D0 matrix plus content-addressed LSP query pack and final doc/JSON hash agreement. | Selected-configuration static map only; conditional platforms, augmentations, reflection, runtime dispatch, code generation, and Flutter routes/widgets remain partial. |
| `rename-concept` | `reports/rename-concept/assessment.json` reports `HALF-APPLIED / INCOMPLETE` for mixed old/new identifier authority and preserves strict-text deferred evidence. | Public old/new types, resolved references, imports/exports, prose/string decoys, external API, and excluded roles. | New authority only, no old resolved identifiers, and separately clean declared prose scope yields complete assessment. | Homonymous locals, strings, reflection names, generated code, SDK/dependency symbols, unresolved conditional imports, and source outside the declared scope do not certify or mutate a rename. | D0 matrix plus LSP definition/reference evidence and the D1 strict-text companion; read-only source hashes. | Assess-only; no codemod, compatibility, reflection/string completeness, generated API, or Flutter asset/route rename safety. |

## D5 — semantic behavior and state

Closure: selected skill + D0 module + accepted D4 LSP provider, invoked once
with the union of bounded consumer queries for a source snapshot. D5 consumers
own candidate policy and human-verdict artifacts. LSP facts may establish
identity and direct selected-workspace calls; they do not establish runtime
behavior or a closed world.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `find-implicit-state` | `candidates.jsonl`, `scout/*.json`, `report.md`, `findings.json`, `facts.json`, `scan.json` emit one `extract_enum_candidate`. | A class `String state` field with resolved assignments/comparisons to three literals, plus enum-typed, local-string, homonym, serialization, dynamic, and excluded decoys. | State is already a Dart enum/sealed value type or lacks sufficient bounded evidence. | Locals, unrelated receivers, map keys, wire literals, reflection, environment/static state, dynamic access, generated parts, tests/examples, and unresolved targets do not become a closed domain. | D0 matrix plus receiver/field definition-reference and operation-span lineage. | Human verdict required; the value domain is not proven closed and serialization/external compatibility remains unresolved. |
| `find-incomplete-sweep` | `findings.md`, `manifest.json`, `scout_packets.json`, fixed `scout_verdicts.json`, `triaged.md` surface one likely omitted named argument. | One resolved function with a named option, three changed direct calls, one omitted direct call, explicit Git trajectory, and wrapper/dynamic/tear-off/extension decoys. | All in-scope resolved direct calls are consistent or explicit verdicts mark differences deliberate. | Same-spelled callees, aliases without identity, wrappers, dynamic/cascade/extension dispatch, spreads, generated/tests, unresolved conditional code, and candidates without Git evidence do not gate in. | D0 matrix, LSP callee identity, repository Git lineage, and complete candidate-to-verdict accounting. | One direct named-argument omission shape; no interprocedural data flow, runtime dispatch, framework convention, or automatic fix. |
| `find-semantic-duplication` | `analysis.json`, `findings.json`, `triage.md`, per-lead capability matrices, `facts.json`, `scan.json` emit one conservative function pair. | Two resolved functions with matching bounded direct callees and return-shape evidence plus a near pair with a policy/protocol difference. | No pair survives the capability/rejection matrix. | Name similarity, lexical clones alone, overrides, dynamic/extension dispatch, generic/type uncertainty, async side effects, FFI/JS interop, generated/external code, and unresolved calls do not confirm equivalence. | D0 matrix plus LSP definition/call-hierarchy lineage and final matrix citations. | Review lead only; no behavioral equivalence, side-effect model, safe consolidation, or runtime/protocol compatibility claim. |

## D6 — accepted state consumers

Closure: selected skill + accepted, content-addressed D5 state artifacts and
the accepted-evidence validator. Neither consumer runs LSP or the analyzer
package. Missing/stale/partial evidence or absent human acceptance stops before
proposal/guard output.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `extract-enum` | `targets.json`, `profile.md`, `proposal.md` turn one accepted state candidate into an implementation-ready Dart enum proposal without editing source. | Accepted D5 finding with exact owner/field/callers/literals plus JSON/wire and public compatibility boundaries. | Accepted evidence says an enum/sealed type already owns the state, yielding an explicit no-proposal result. | Partial/stale findings, open domains, ambiguous receiver/field, generated owners, external API ownership, reflection/serialization uncertainty, and unaccepted candidates do not produce a proposal. | Revalidate hashes; apply the exact proposal only in a disposable copy and run D0 matrix there. | Proposal only; no source edit, migration, exhaustive domain proof, wire compatibility, or Flutter state-management choice. |
| `prevent-regression` | `pattern.md`, `proposal.md`, staged guard/test files, `host-wiring.diff`, `verification.json` show good Dart passes and a reverted `String` field fails. | SHA-bound accepted enum proposal and a project-owned `package:test` type guard fixture with good/bad disposable trees. | Existing equivalent guard is detected and reported without staging a duplicate. | No accepted review, stale hashes, private/generated/external owner, unavailable locked tests, dynamic-only checks, or unrelated state finding stages a guard. | Locked offline Pub, analyze/format/test/smoke on good; bad must fail specifically because of the staged guard. | Stages but never installs; exact reviewed field only, not a universal lint or serialization/runtime invariant. |

## D7 — read-only proposals

Closure: selected skill + accepted-evidence validator + only the named upstream
artifact. `propose-boundary` consumes a D4 query pack for its selected target;
`propose-folder-reorganization` consumes one accepted D1 cluster plus D4 import
impact; `unify-shadows` consumes one accepted D5 semantic-duplication finding.
No D7 consumer re-runs broad detection or shares another consumer's proposal
schema.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `propose-boundary` | `inspection.json`, `proposal.md` cite one coherent library seam, public API, callers, compatibility, tests, and native plan. | Selected child domain with direct declarations, resolved sibling/inbound callers, public barrel, characterization test surface, and a cohesive defer target. | Cohesive or unresolved target yields `defer`, not a forced extraction. | Generated/test evidence as ownership, unresolved/conditional edges, dynamic/reflection callers, external consumers, Flutter conventions, and missing public compatibility do not yield `ready`. | D0 matrix on current tree; exact proposed plan applied only in a disposable copy with the same matrix. | Proposal-only selected configuration; no semver guarantee, runtime graph, framework boundary, or automatic extraction. |
| `propose-folder-reorganization` | `inspection.json`, `proposal.md` contain current/proposed trees, exact moves, import impact, compatibility, and tests for one cluster. | Accepted three-file D1 cluster, explicit human split judgment/convention, resolved direct imports/exports, barrel compatibility, and disposable after-tree. | Below-threshold or human-cohesive cluster yields no move proposal. | Generated/part/test/example files as cluster members, unresolved conditional imports, public package URI/semver uncertainty, symlinks, cross-package moves, and absent convention do not yield `ready`. | D0 matrix before and on disposable exact after-tree; all planned members/edges must be accounted. | Read-only one-cluster plan; no general module move engine, runtime reflection coverage, or Flutter folder convention. |
| `unify-shadows` | `proposal.md`, `evidence.json`, `scope.json` render one cited consolidation shape or explicit keep-separate decision. | Accepted D5 finding with complete capability matrix, source/caller citations, exact selected shape, and divergent keep-separate decoy. | `keep_separate` is a successful final outcome when evidence shows policy/protocol divergence. | Raw source similarity, stale/partial finding, missing callers, generated/external members, dynamic dispatch, unselected shape, and absent human approval do not produce a merge plan. | Revalidate D5 pack/hashes; disposable proposed tree must pass D0 matrix when a merge shape is claimed viable. | No re-detection, behavioral-equivalence certification, mutation authority, public compatibility, or framework semantics. |

## D8 — transactional `move-path`

Closure: `move-path` + D0 module + accepted D2 directive spans + accepted D4
identity facts + a mutation-local planner/transaction/rollback module. Do not
extract a shared mutation executor. D8 integrates last and alone.

| Skill | Useful final outcome and artifacts | Positive fixture obligation | Clean case | Must not fire/refusal | Native verification | Honest limitation |
|---|---|---|---|---|---|---|
| `move-path` | `reports/move-path/report.json`, `report.md`, residue audit, preview diff, and rollback evidence move one conventional private `lib/src` library file, update all resolved first-party import/export URIs, and preserve its public barrel. | File and leaf-directory forms; direct relative/package importers; public re-export; preview/apply/check; stale fingerprint; injected postflight failure; exact before/after trees. | `--check` on the exact applied after-tree reports no old path/residue and no further edits. | `part`/`part of`, augmentations, conditional imports/exports, generated files, symlinks, reflection strings, unresolved/dynamic loads, cross-package/public URI changes, multiple moves, Flutter assets/platform files, or incomplete graph block apply. | Full D0 matrix before/after, exact smoke/output, exact diff/after-tree, source fingerprint authorization, and complete rollback on any failure. | One conventional private core-Dart library move only; not a package rename, public API/semver migration, arbitrary codemod, generated-code move, or Flutter refactor. |

## Batch handoff and integration prohibitions

Every worker packet must include the exact base revision, worktree, absolute
product Python path, owned skills/provider/files, copied closure, fixture,
artifact paths, status/failure vocabulary, and focused verification commands.
Workers may edit only their owned skill adapters, provider/consumer tests,
fixtures, and one batch learning packet. They must not edit:

- shared `SKILL.md` publication prose;
- language coverage JSON, generated matrix/projection, router/catalog, active
  execution plan, installation manifests, or backlog;
- another batch's provider or consumer;
- `_common` or a cross-language LSP platform;
- Flutter/framework profiles; or
- production host source outside D8's disposable fixture tests.

Root integrates serially: D0, D2 provider, D4 provider, read-only consumers,
accepted-evidence consumers, then D8. For each accepted skill, root replays the
exact copied command from outside repository and host, proves same-destination
terminal transitions and source preservation, runs preserved-language family
tests, publishes one coverage row, regenerates projections, and only then
enables routing. A worker's passing candidate artifact is never a capability
claim.

## Tooling gaps and stop gates

1. A fresh offline cache does not currently prove availability of the exact
   analyzer/test closure. D0 must define distribution/preflight without
   modifying the host or using ambient network. Until then D2/D3/D8 stay
   pending even though the local warmed cache works.
2. `dart analyze` lacks an advertised machine-readable output mode. Do not
   parse its human text into semantic facts; use SDK LSP diagnostics/facts and
   keep CLI analysis as a native gate.
3. `dart language-server` is SDK-owned but described as higher-level-tooling
   infrastructure. Pin the SDK, assert initialize capabilities, and treat
   missing/changed requests as partial rather than assuming protocol parity.
   Keep `--cache` external; hash and pass an existing `--packages` file;
   canonicalize macOS paths; filter SDK symbols; and refuse complete package
   semantics if package imports remain unresolved.
4. Pub workspaces, conditional imports/exports, parts, augmentations, code
   generation, dynamic invocation, mirrors, isolates, FFI/JS interop, and
   platform-selected libraries need explicit fixtures. Default-support claims
   stop at the selected locked plain-Dart configuration.
5. `package:test` is host/closure-owned and `dart test` may trigger Pub
   resolution. Never execute it before locked/offline preflight.
6. No Flutter SDK/profile was evaluated. Flutter remains a separate future
   framework lane after core Dart contracts are honest.

## Root next steps

1. Accept or adjust this cohort order; keep all 22 rows pending meanwhile.
2. Implement D0 only and freeze the plain-Dart fixture, doctor output, exact
   SDK range, offline acquisition contract, native matrix, roles, hashes, and
   lifecycle.
3. Pilot one D2 consumer (`audit-decisions`) with public analyzer 14.1.0 and one
   D4 consumer (`map-subsystem`) with SDK LSP. Compare final value, copied
   closure, cold-cache behavior, latency, and adapter-plus-test LOC before
   approving their remaining consumers.
4. After a second real consumer in each family, run the 25%/10% economics gate;
   extract only the Dart-local seams that pass. Record whether the Rust LSP
   transport still appears identical, but do not move it cross-language yet.
5. Expand in the table order with per-skill promotion and fresh product review.
   Integrate D8 last, then publish coverage/matrix/router/catalog changes from
   root-owned serial work only.
